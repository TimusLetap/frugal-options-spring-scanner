"""
api_server.py - Lightweight HTTP API for live dynamic ticker scanning.

Exposes POST /api/scan to dynamically scan any ticker(s) or preset universe
using the real Python quantitative engine (market_data, scanner, zero_dte_scanner,
leaps_scanner) and return only tickers/contracts that meet the strict <= $0.25
Frugal Spring qualification rules.
"""

import json
import logging
import math
import os
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from market_data import MarketScanner, get_market_data_provider
from scanner import run_gamma_scanner
from zero_dte_scanner import run_0dte_scan
from leaps_scanner import run_leaps_scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCAN_LOCK = threading.Lock()

PRESET_UNIVERSES: Dict[str, List[str]] = {
    "indices": ["SPY", "QQQ", "IWM"],
    "ai_semis": ["NVDA", "AMD", "AVGO", "ARM", "TSM", "MU"],
    "high_beta": ["TSLA", "MSTR", "COIN", "PLTR", "HOOD", "SOFI"],
    "mag7": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"],
}


def _clean_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    cleaned: List[Dict[str, Any]] = []
    for row in records:
        out: Dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                out[k] = None
            elif hasattr(v, "item"):
                out[k] = v.item()
            else:
                out[k] = v
        cleaned.append(out)
    return cleaned


def _qualify_long_springs(df: pd.DataFrame, max_premium: float) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cond = (
        (df["Ask"] > 0)
        & (df["Ask"] <= max_premium)
        & (df["Can_Reach_1_00"] == True)
        & (
            (df["Is_In_Coil"] == True)
            | (df["Is_TTM_Squeeze"] == True)
            | (df["Undervaluation_Score"] >= 50)
            | (df["Spring_Score"] >= 45)
        )
    )
    qualified = df[cond].copy()
    if not qualified.empty and "Opportunity_Score" in qualified.columns:
        qualified = qualified.sort_values(by="Opportunity_Score", ascending=False)
    return qualified


def _qualify_0dte_springs(df: pd.DataFrame, max_premium: float) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cond = (
        (df["Ask"] > 0)
        & (df["Ask"] <= max_premium)
        & (df["Can_Reach_1_00"] == True)
        & (
            (df["Is_In_Coil"] == True)
            | (df["Is_TTM_Squeeze"] == True)
            | (df["Undervaluation_Score"] >= 50)
            | (df["Spring_Score"] >= 45)
        )
    )
    qualified = df[cond].copy()
    if not qualified.empty and "Opportunity_Score" in qualified.columns:
        qualified = qualified.sort_values(by="Opportunity_Score", ascending=False)
    return qualified


def _qualify_gamma_coils(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cond = (
        (df["Is_In_Coil"] == True)
        | (df["Is_TTM_Squeeze"] == True)
        | (df["Opportunity_Score"] >= 55)
        | (df["Spring_Score"] >= 55)
    )
    qualified = df[cond].copy()
    if not qualified.empty and "Opportunity_Score" in qualified.columns:
        qualified = qualified.sort_values(by="Opportunity_Score", ascending=False)
    return qualified


def _save_reports(
    long_df: pd.DataFrame,
    zero_df: pd.DataFrame,
    gamma_df: pd.DataFrame,
) -> None:
    for base in [Path("data/reports"), Path("public/data/reports")]:
        base.mkdir(parents=True, exist_ok=True)
        if not long_df.empty:
            long_df.to_csv(base / "long_spring_opportunities.csv", index=False)
        if not zero_df.empty:
            zero_df.to_csv(base / "0dte_spring_opportunities.csv", index=False)
        if not gamma_df.empty:
            gamma_df.to_csv(base / "gamma_squeeze_potential.csv", index=False)


def run_dynamic_scan(payload: Dict[str, Any]) -> Dict[str, Any]:
    preset = str(payload.get("preset", "")).strip().lower()
    raw_tickers = payload.get("tickers", [])
    max_premium = float(payload.get("max_premium", 0.25))
    only_qualified = bool(payload.get("only_qualified", True))

    if isinstance(raw_tickers, str):
        tickers = [t.strip().upper() for t in raw_tickers.replace(",", " ").split() if t.strip()]
    elif isinstance(raw_tickers, list):
        tickers = [str(t).strip().upper() for t in raw_tickers if str(t).strip()]
    else:
        tickers = []

    if not tickers:
        if preset in PRESET_UNIVERSES:
            tickers = PRESET_UNIVERSES[preset]
        else:
            scanner = MarketScanner()
            tickers = scanner.get_universe("options_tickers.txt")

    # Deduplicate preserving order
    seen = set()
    unique_tickers = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique_tickers.append(t)

    provider = get_market_data_provider()
    today = date.today()
    workers = min(8, max(2, len(unique_tickers)))

    with SCAN_LOCK:
        gamma_raw = run_gamma_scanner(
            unique_tickers,
            provider=provider,
            max_workers=workers,
            max_premium=max_premium,
        )
        c0_raw, p0_raw = run_0dte_scan(
            tickers=unique_tickers,
            provider=provider,
            target_date=today,
            max_workers=workers,
            max_premium=max_premium,
        )
        zero_raw = pd.concat([c0_raw, p0_raw], ignore_index=True) if (not c0_raw.empty or not p0_raw.empty) else pd.DataFrame()
        long_raw = run_leaps_scan(
            tickers=unique_tickers,
            provider=provider,
            max_workers=workers,
            max_premium=max_premium,
        )

    if only_qualified:
        long_df = _qualify_long_springs(long_raw, max_premium)
        zero_df = _qualify_0dte_springs(zero_raw, max_premium)
        gamma_df = _qualify_gamma_coils(gamma_raw)
    else:
        long_df = long_raw
        zero_df = zero_raw
        gamma_df = gamma_raw

    qualified_tickers = sorted(
        set(
            (long_df["Ticker"].tolist() if not long_df.empty else [])
            + (zero_df["Ticker"].tolist() if not zero_df.empty else [])
            + (gamma_df["Ticker"].tolist() if not gamma_df.empty else [])
        )
    )
    unqualified_tickers = [t for t in unique_tickers if t not in qualified_tickers]

    _save_reports(long_df, zero_df, gamma_df)

    return {
        "status": "ok",
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scanned_tickers": unique_tickers,
        "qualified_tickers": qualified_tickers,
        "unqualified_tickers": unqualified_tickers,
        "only_qualified": only_qualified,
        "max_premium": max_premium,
        "counts": {
            "scanned": len(unique_tickers),
            "qualified_tickers": len(qualified_tickers),
            "long_springs": len(long_df),
            "zero_dte_springs": len(zero_df),
            "gamma_coils": len(gamma_df),
        },
        "long_springs": _clean_records(long_df),
        "zero_dte_springs": _clean_records(zero_df),
        "gamma_coils": _clean_records(gamma_df),
    }


class ScanRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"status": "ok"})

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json(200, {"status": "ok", "service": "frugal-spring-scanner-api"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/scan":
            self._send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            result = run_dynamic_scan(payload)
            self._send_json(200, result)
        except Exception as exc:
            logger.exception("Dynamic scan error")
            self._send_json(500, {"status": "error", "error": str(exc)})


def main() -> None:
    port = int(os.getenv("SCANNER_API_PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), ScanRequestHandler)
    logger.info("Frugal Options Spring Scanner API listening on http://0.0.0.0:%d", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
