"""
leaps_scanner.py - Long Position & LEAPS Spring Scanner (<= $0.25).

Scans multi-week Swing (7-60 DTE) and Long-Dated / LEAPS (60-730+ DTE) option chains
for undervalued contracts costing $0.25 or less ($25 max per contract) on stocks in
confirmed volatility coils ("Spring Setups") with high confidence to expand to
$1.00 (4x+) or $10.00+ (40x+) in value.

Usage:
    uv run python leaps_scanner.py [--top N] [--max-premium 0.25] [--min-dte 7]
"""

import argparse
import concurrent.futures
import functools
import logging
import os
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
import yaml
from tqdm import tqdm

from market_data import MarketDataProvider, get_market_data_provider, MarketScanner
from scoring import (
    geometric_mean,
    bs_delta,
    bs_gamma,
    compute_atr,
    score_spread_tightness,
    score_unusual_options_activity,
    evaluate_spring_setup,
    evaluate_option_undervaluation,
    evaluate_payoff_potential,
    RISK_FREE_RATE_DEFAULT,
    MAX_FRUGAL_PREMIUM_DEFAULT,
)
from trade_logger import append_leaps_trades

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("leaps_scanner")

ROOT = Path(__file__).parent


def load_config() -> dict:
    cfg_path = ROOT / "config" / "trading_rules.yaml"
    if cfg_path.exists():
        with cfg_path.open() as f:
            data = yaml.safe_load(f) or {}
            if "long_spring" in data and "leaps_scanner" not in data:
                data["leaps_scanner"] = data["long_spring"]
            return data
    return {
        "long_spring": {
            "max_premium": MAX_FRUGAL_PREMIUM_DEFAULT,
            "min_dte": 7,
            "max_dte": 730,
            "max_spread": 0.08,
            "min_open_interest": 25,
            "min_volume": 5,
            "contract_types": ["CALL", "PUT"],
            "top_n_tickers": 50,
        }
    }


def load_top_tickers(cfg: dict) -> list[str]:
    csv_path = ROOT / "gamma_squeeze_potential.csv"
    top_n = cfg.get("top_n_tickers", 50)
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            if not df.empty and "Ticker" in df.columns:
                df = (
                    df.sort_values("Opportunity_Score", ascending=False)
                    .drop_duplicates(subset="Ticker", keep="first")
                    .head(top_n)
                )
                tickers = df["Ticker"].tolist()
                if tickers:
                    log.info("Loaded %d tickers from gamma squeeze scan", len(tickers))
                    return tickers
        except Exception as e:
            log.warning("Could not parse gamma_squeeze_potential.csv: %s", e)

    scanner = MarketScanner()
    tickers = scanner.get_default_universe()[:top_n]
    log.info("Loaded %d tickers from default universe", len(tickers))
    return tickers


def scan_leaps_for_ticker(
    ticker_symbol: str,
    cfg: dict,
    provider: Optional[MarketDataProvider] = None,
) -> list[dict]:
    """
    Fetch option chains for a single ticker and filter for undervalued Long/Swing/LEAPS
    contracts costing <= max_premium (default $0.25) with $1.00 to $10.00+ spring potential.
    """
    if provider is None:
        provider = get_market_data_provider()

    max_premium = float(cfg.get("max_premium", MAX_FRUGAL_PREMIUM_DEFAULT))
    min_dte = int(cfg.get("min_dte", 7))
    max_dte = int(cfg.get("max_dte", 730))
    max_spread = float(cfg.get("max_spread", 0.08))
    min_oi = int(cfg.get("min_open_interest", 25))
    min_vol = int(cfg.get("min_volume", 1))
    contract_types = [ct.upper() for ct in cfg.get("contract_types", ["CALL", "PUT"])]

    results: list[dict] = []

    try:
        spot = provider.get_spot_price(ticker_symbol)
        if spot is None or spot <= 0:
            return results

        ohlcv = provider.get_historical_ohlcv(ticker_symbol, period="1y")
        if ohlcv is None or ohlcv.empty:
            return results

        atr = compute_atr(ohlcv, window=14)
        spring = evaluate_spring_setup(ticker_symbol, ohlcv)

        expirations = provider.get_options_expirations(ticker_symbol)
        if not expirations:
            return results

        today = date.today()
        valid_exps = []
        for exp in expirations:
            try:
                exp_d = datetime.strptime(exp, "%Y-%m-%d").date()
                dte = (exp_d - today).days
                if min_dte <= dte <= max_dte:
                    valid_exps.append((exp, dte))
            except ValueError:
                continue

        if not valid_exps:
            return results

        # Sample up to 6 distinct expirations across Swing (7-45d), Medium (46-180d), and LEAPS (180d+)
        if len(valid_exps) > 6:
            indices = sorted(list({0, 1, len(valid_exps) // 3, (2 * len(valid_exps)) // 3, len(valid_exps) - 2, len(valid_exps) - 1}))
            selected_exps = [valid_exps[i] for i in indices if 0 <= i < len(valid_exps)]
        else:
            selected_exps = valid_exps

        for exp_str, dte in selected_exps:
            time_years = max(1.0 / 365.0, dte / 365.0)
            try:
                calls_df, puts_df = provider.get_option_chain(ticker_symbol, exp_str)
            except Exception:
                continue

            for ct_label, ct_df in [("CALL", calls_df), ("PUT", puts_df)]:
                if ct_label not in contract_types or ct_df is None or ct_df.empty:
                    continue

                ct_df = ct_df.rename(
                    columns={
                        "contractSymbol": "contract",
                        "lastPrice": "last_price",
                        "openInterest": "open_interest",
                        "impliedVolatility": "iv",
                    }
                )
                ct_df["open_interest"] = ct_df["open_interest"].fillna(0)
                ct_df["volume"] = ct_df["volume"].fillna(0)

                vols = ct_df["volume"]
                avg_vol = float(vols.mean()) if not vols.empty else 0.0
                std_vol = float(vols.std()) if len(vols) > 1 else 0.0

                for _, row in ct_df.iterrows():
                    strike = float(row.get("strike", 0) or 0)
                    if strike <= 0:
                        continue

                    bid = float(row.get("bid", 0) or 0)
                    ask = float(row.get("ask", 0) or 0)
                    last_p = float(row.get("last_price", 0) or 0)
                    entry_price = ask if ask > 0 else last_p
                    mid = round((bid + ask) / 2.0, 2) if (bid > 0 and ask > 0) else round(entry_price, 2)
                    spread = round(max(0.0, ask - bid), 2) if ask > 0 else 0.0
                    oi = int(row.get("open_interest", 0) or 0)
                    vol = int(row.get("volume", 0) or 0)

                    # Strict $0.25 Frugal Ceiling on entry price / mid
                    if entry_price <= 0 or entry_price > max_premium:
                        continue
                    if ask > 0 and spread > max_spread and (spread / ask) > 0.35:
                        continue
                    if oi < min_oi and vol < min_vol * 2:
                        continue
                    if vol < min_vol and oi < min_oi * 2:
                        continue

                    iv = float(row.get("iv", 0) or 0)
                    if iv <= 0.01:
                        iv = 0.30

                    delta = abs(bs_delta(spot, strike, time_years, RISK_FREE_RATE_DEFAULT, iv, ct_label.lower()))

                    # 1. Undervaluation evaluation
                    underval = evaluate_option_undervaluation(
                        spot=spot,
                        strike=strike,
                        ask_price=entry_price,
                        time_years=time_years,
                        iv=iv,
                        option_type=ct_label.lower(),
                        ohlcv=ohlcv,
                    )

                    # 2. Payoff potential evaluation ($0.25 -> $1.00 / $10.00+)
                    payoff = evaluate_payoff_potential(
                        spot=spot,
                        strike=strike,
                        ask_price=entry_price,
                        dte_days=float(dte),
                        atr=atr,
                        iv=underval.implied_vol,
                        breakout_hv=underval.breakout_hv_85,
                        option_type=ct_label.lower(),
                    )

                    # Require at least $0.60+ modeled spring value or reasonable ATR move to $1.00
                    if payoff.max_projected_value < 0.50 and payoff.atr_move_to_1_00 > 12.0:
                        continue

                    f_tightness = max(0.35, score_spread_tightness(bid, entry_price))
                    f_uoa = max(0.30, score_unusual_options_activity(vol, oi, avg_vol, std_vol))
                    dir_aligned = (
                        (ct_label == "CALL" and spring.direction == "BULLISH")
                        or (ct_label == "PUT" and spring.direction == "BEARISH")
                    )
                    f_spring = spring.spring_score if dir_aligned else max(0.35, spring.spring_score * 0.80)

                    composite_score = (
                        geometric_mean(
                            [
                                f_spring,
                                underval.undervaluation_score,
                                payoff.payoff_score,
                                f_tightness,
                                f_uoa,
                            ]
                        )
                        * 100.0
                    )

                    horizon_bucket = "LEAPS (180d+)" if dte >= 180 else ("Long Swing (45-179d)" if dte >= 45 else "Swing Spring (7-44d)")

                    results.append({
                        "Scan_Date": today.isoformat(),
                        "Ticker": ticker_symbol,
                        "Spot": round(spot, 2),
                        "Type": ct_label,
                        "Horizon": horizon_bucket,
                        "Strike": strike,
                        "Expiration": exp_str,
                        "DTE": dte,
                        "Bid": round(bid, 2),
                        "Ask": round(entry_price, 2),
                        "Mid": round(mid, 2),
                        "Spread": spread,
                        "Volume": vol,
                        "Open_Interest": oi,
                        "IV": round(underval.implied_vol * 100.0, 1),
                        "Realized_HV": round(underval.realized_hv_20 * 100.0, 1),
                        "IV_HV_Ratio": underval.iv_hv_ratio,
                        "IV_Rank": underval.iv_rank,
                        "BS_Fair_Value": underval.bs_fair_value_hv,
                        "Valuation_Label": underval.valuation_label,
                        "Undervaluation_Score": round(underval.undervaluation_score * 100.0, 1),
                        "Delta_Est": round(delta, 3),
                        "Contract": str(row.get("contract", f"{ticker_symbol}_{exp_str}_{ct_label[0]}{strike}")),
                        "Breakeven": payoff.breakeven_spot,
                        "Breakeven_Move_Pct": round(
                            ((payoff.breakeven_spot - spot) / spot * 100.0)
                            if ct_label == "CALL"
                            else ((spot - payoff.breakeven_spot) / spot * 100.0),
                            1,
                        ),
                        "Is_In_Coil": spring.is_in_coil,
                        "Is_TTM_Squeeze": spring.is_ttm_squeeze,
                        "BBW_Percentile": spring.bbw_percentile,
                        "HVR_Pct": spring.hvr_pct,
                        "Layers_Confirmed": spring.layers_confirmed,
                        "Spring_Score": round(f_spring * 100.0, 1),
                        "Spring_Thesis": spring.spring_thesis,
                        "Spot_For_1_00": payoff.spot_for_1_00,
                        "Spot_For_10_00": payoff.spot_for_10_00,
                        "Move_To_1_00_Pct": payoff.move_to_1_00_pct,
                        "Move_To_10_00_Pct": payoff.move_to_10_00_pct,
                        "ATR_Move_To_1_00": payoff.atr_move_to_1_00,
                        "ATR_Move_To_10_00": payoff.atr_move_to_10_00,
                        "Proj_Value_2ATR": payoff.proj_value_2atr,
                        "Proj_Value_3ATR": payoff.proj_value_3atr,
                        "Proj_Value_5ATR": payoff.proj_value_5atr,
                        "Max_Projected_Value": payoff.max_projected_value,
                        "Potential_Multiple": payoff.potential_multiple,
                        "Can_Reach_1_00": payoff.can_reach_1_00,
                        "Can_Reach_10_00": payoff.can_reach_10_00,
                        "Payoff_Tier": payoff.payoff_tier,
                        "Opportunity_Score": round(composite_score, 1),
                    })

    except Exception as e:
        log.debug("Error scanning %s: %s", ticker_symbol, e)

    # Keep top 4 highest-scoring contracts per ticker to prevent single-ticker flooding
    if results:
        results = sorted(
            results,
            key=lambda r: (r["Opportunity_Score"], r["Max_Projected_Value"]),
            reverse=True,
        )[:4]

    return results


def run_leaps_scan(
    tickers: list[str],
    provider: Optional[MarketDataProvider] = None,
    max_workers: int = 8,
    max_premium: Optional[float] = None,
) -> pd.DataFrame:
    """Entry point for the unified scanner pipeline (scanner.py)."""
    config = load_config()
    leap_cfg = dict(config.get("long_spring") or config.get("leaps_scanner") or {})
    if max_premium is not None:
        leap_cfg["max_premium"] = max_premium

    top_n = leap_cfg.get("top_n_tickers", 50)
    if tickers:
        target_tickers = tickers[:top_n]
    else:
        target_tickers = load_top_tickers(leap_cfg)

    log.info(
        "Scanning Long & LEAPS Springs: premium <= $%.2f | DTE %d-%d | Targets: $1.00 (4x+) & $10.00+ (40x+)",
        leap_cfg.get("max_premium", MAX_FRUGAL_PREMIUM_DEFAULT),
        leap_cfg.get("min_dte", 7),
        leap_cfg.get("max_dte", 730),
    )

    all_results: list[dict] = []
    if max_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            scan_fn = functools.partial(scan_leaps_for_ticker, cfg=leap_cfg, provider=provider)
            results = list(
                tqdm(
                    executor.map(scan_fn, target_tickers),
                    total=len(target_tickers),
                    desc="Scanning Long/LEAPS Springs",
                )
            )
            for r in results:
                all_results.extend(r)
    else:
        for ticker in tqdm(target_tickers, desc="Scanning Long/LEAPS Springs", unit="ticker"):
            hits = scan_leaps_for_ticker(ticker, leap_cfg, provider=provider)
            all_results.extend(hits)

    if not all_results:
        log.warning("No Long/LEAPS Spring opportunities found matching criteria.")
        return pd.DataFrame()

    df = pd.DataFrame(all_results)
    df = df.sort_values(
        by=["Opportunity_Score", "Max_Projected_Value", "Open_Interest"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    os.makedirs("data/reports", exist_ok=True)
    out_path = ROOT / "leaps_opportunities.csv"
    df.to_csv(out_path, index=False)
    df.to_csv(ROOT / "data" / "reports" / "long_spring_opportunities.csv", index=False)
    append_leaps_trades(df.head(20).to_dict(orient="records"))

    log.info("Found %d Long/LEAPS Spring opportunities across %d tickers", len(df), df["Ticker"].nunique())
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Long & LEAPS Spring Scanner (<= $0.25 for $1.00 to $10.00+ potential)")
    parser.add_argument("--top", type=int, help="Override number of tickers to scan")
    parser.add_argument("--max-premium", type=float, default=MAX_FRUGAL_PREMIUM_DEFAULT, help="Override max premium ($), default 0.25")
    parser.add_argument("--min-dte", type=int, help="Override minimum DTE")
    args = parser.parse_args()

    config = load_config()
    leap_cfg = dict(config.get("long_spring") or config.get("leaps_scanner") or {})
    if args.top:
        leap_cfg["top_n_tickers"] = args.top
    if args.max_premium:
        leap_cfg["max_premium"] = args.max_premium
    if args.min_dte is not None:
        leap_cfg["min_dte"] = args.min_dte

    tickers = load_top_tickers(leap_cfg)
    df = run_leaps_scan(tickers, max_workers=8, max_premium=leap_cfg["max_premium"])
    if df.empty:
        return 0

    cols = [
        "Ticker", "Type", "Strike", "Expiration", "DTE", "Ask",
        "Opportunity_Score", "Valuation_Label", "Proj_Value_3ATR", "Proj_Value_5ATR", "Payoff_Tier"
    ]
    present_cols = [c for c in cols if c in df.columns]
    log.info("Top Long Spring Candidates (<= $0.25):\n%s", df[present_cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
