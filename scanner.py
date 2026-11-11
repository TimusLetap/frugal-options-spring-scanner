"""
scanner.py - Unified Frugal Options Spring Scanner Pipeline.

Orchestrates:
1. Volatility Coil & Gamma Squeeze Radar (combines Frugal_Trader's 4-layer Coil/Squeeze/EMA/RS engine with options-ticker-universe's multiplicative GEX & acceleration model)
2. 0DTE Spring Scanner (<= $0.25 contracts with high confidence to reach $1.00 to $10.00+)
3. Long Position & LEAPS Spring Scanner (<= $0.25 Swing & Long-Dated contracts with $1.00 to $10.00+ convexity)
4. Conviction persistence tracking, Market Regime/Breadth filtering, Paper-Trading validation guard, and Discord dispatch.
"""

import os
import sys
import math
import logging
import argparse
import functools
import threading
import warnings
import concurrent.futures
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

import numpy as np
import pandas as pd
from tqdm import tqdm
import yfinance as yf

from market_data import (
    get_market_data_provider,
    MarketScanner,
    fetch_bulk_data,
    throttle,
    with_backoff,
)
from calendar_utils import (
    get_target_0dte_trading_day,
    is_today_0dte_trading_day,
    get_current_week_0dte_trading_days,
    determine_market_regime,
    check_market_breadth,
)
from scoring import (
    geometric_mean,
    _clamp01,
    _safe_div,
    bs_delta,
    bs_gamma,
    evaluate_spring_setup,
    evaluate_option_undervaluation,
    evaluate_payoff_potential,
    MAX_FRUGAL_PREMIUM_DEFAULT,
)
from trade_logger import (
    compute_paper_trading_status,
    update_0dte_trade_outcomes,
)
from zero_dte_scanner import run_0dte_scan
from leaps_scanner import run_leaps_scan
from discord_notifier import dispatch_full_scan_report
from core.conviction_tracker import ConvictionTracker
from core.paper_trader import PaperTrader

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Configuration & Tuning Parameters ---
MAX_WORKERS = int(os.getenv("SCANNER_WORKERS", "10"))
MAX_DAYS_TO_NEAREST_EXPIRATION = int(os.getenv("SCANNER_MAX_EXP_DAYS", "10"))
TOP_N = int(os.getenv("SCANNER_TOP_N", "50"))
MAX_FRUGAL_PREMIUM = float(os.getenv("SCANNER_MAX_PREMIUM", str(MAX_FRUGAL_PREMIUM_DEFAULT)))

# Gamma + Spring Scoring Architecture
CORE_WEIGHT = 0.45
SPRING_WEIGHT = 0.25
CONTEXT_WEIGHT = 0.15
ACCEL_WEIGHT = 0.15
CONTEXT_SUB_WEIGHTS = {"put_call_skew": 0.5, "momentum": 0.5}

# Normalization caps
PCR_NEUTRAL_CAP = 0.80
MOMENTUM_CAP_PCT = 10.0
WALL_DISTANCE_CAP_PCT = 10.0
DAYS_TO_COVER_CAP = 10.0
SHORT_PCT_FLOAT_CAP = 0.30
ACCEL_DISTANCE_CLOSING_CAP_PCT = 3.0
ACCEL_GAMMA_FUEL_INCREASE_CAP_PCT = 10.0
ACCEL_DTC_INCREASE_CAP = 2.0

RISK_FREE_RATE = float(os.getenv("SCANNER_RISK_FREE_RATE", "0.045"))
GAMMA_FUEL_RATIO_CAP = float(os.getenv("SCANNER_GAMMA_FUEL_CAP", "0.25"))
GAMMA_CONCENTRATION_CAP = float(os.getenv("SCANNER_GAMMA_CONC_CAP", "0.35"))
PREVIOUS_SCAN_PATH = "data/history/gamma_squeeze_potential.csv"


def score_tier(score: float) -> str:
    if score >= 75:
        return "🔥 High Conviction Spring"
    elif score >= 60:
        return "✅ Strong Coiled Watch"
    elif score >= 45:
        return "👀 Speculative Spring"
    else:
        return "⚪ Low Conviction"


def realized_vol(closes: List[float]) -> float:
    if len(closes) < 3:
        return 0.5
    rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0 and closes[i] > 0
    ]
    if len(rets) < 2:
        return 0.5
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return max(0.05, math.sqrt(var) * math.sqrt(252))


def compute_gamma_exposure(otm_calls: pd.DataFrame, spot_price: float, time_years: float, fallback_iv: float):
    gamma_dollars = []
    for _, row in otm_calls.iterrows():
        iv = row.get("impliedVolatility", 0.0)
        if iv is None or iv != iv or iv <= 0.01:
            iv = fallback_iv
        oi = row.get("openInterest", 0) or 0
        g = bs_gamma(spot_price, row["strike"], time_years, RISK_FREE_RATE, iv)
        gamma_dollars.append(g * oi * 100.0 * (spot_price ** 2) * 0.01)
    annotated = otm_calls.copy()
    annotated["Gamma_Dollars"] = gamma_dollars
    return annotated, sum(gamma_dollars)


_stats_lock = threading.Lock()
STATS = {
    "total": 0,
    "error": 0,
    "no_expiration_in_window": 0,
    "no_call_oi": 0,
    "no_history": 0,
    "no_otm_calls": 0,
    "scored": 0,
}


def _bump(key: str):
    with _stats_lock:
        STATS[key] += 1


def print_stats():
    print("\n--- Scan diagnostics ---")
    for k, v in STATS.items():
        print(f"  {k:28s}: {v}")


def load_previous_scan(path: str = PREVIOUS_SCAN_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        prev_df = pd.read_csv(path)
    except Exception:
        return {}
    lookup = {}
    for _, row in prev_df.iterrows():
        ticker = row.get("Ticker")
        if not isinstance(ticker, str):
            continue
        lookup[ticker] = {
            "Distance_to_Wall_%": row.get("Distance_to_Wall_%"),
            "Gamma_Fuel_vs_ADV_%": row.get("Gamma_Fuel_vs_ADV_%"),
            "Days_to_Cover": row.get("Days_to_Cover"),
        }
    return lookup


def compute_acceleration(symbol, distance_to_wall, gamma_fuel_pct, days_to_cover, has_short_data, previous_lookup):
    prev = previous_lookup.get(symbol)
    if not prev:
        return None
    components = []

    prev_distance = prev.get("Distance_to_Wall_%")
    if prev_distance is not None and prev_distance == prev_distance:
        delta_distance = distance_to_wall - prev_distance
        components.append(_clamp01(-delta_distance / ACCEL_DISTANCE_CLOSING_CAP_PCT))

    prev_fuel = prev.get("Gamma_Fuel_vs_ADV_%")
    if prev_fuel is not None and prev_fuel == prev_fuel:
        delta_fuel = gamma_fuel_pct - prev_fuel
        components.append(_clamp01(delta_fuel / ACCEL_GAMMA_FUEL_INCREASE_CAP_PCT))

    prev_dtc = prev.get("Days_to_Cover")
    if has_short_data and prev_dtc is not None and prev_dtc == prev_dtc:
        delta_dtc = days_to_cover - prev_dtc
        components.append(_clamp01(delta_dtc / ACCEL_DTC_INCREASE_CAP))

    if not components:
        return None
    return sum(components) / len(components)


def trend_label(acceleration):
    if acceleration is None:
        return "NEW"
    elif acceleration >= 0.6:
        return "^^"
    elif acceleration >= 0.4:
        return "^"
    elif acceleration >= 0.2:
        return "-"
    else:
        return "v"


def extract_frugal_spring_ideas(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    days_to_expiration: int,
    exp_str: str,
    symbol: str,
    spot_price: float,
    atr: float,
    spring_metrics,
    ohlcv: pd.DataFrame,
    max_premium: float = MAX_FRUGAL_PREMIUM,
):
    """
    Extracts <= $0.25 0DTE and Long Swing Spring ideas with $1.00 / $10.00+ projections.
    """
    zero_dte_ideas = []
    long_swing_ideas = []

    for opt_type, chain in [("call", calls), ("put", puts)]:
        if chain is None or chain.empty:
            continue
        for _, row in chain.iterrows():
            strike = float(row.get("strike", 0) or 0)
            bid = float(row.get("bid", 0) or 0)
            ask = float(row.get("ask", 0) or 0)
            last = float(row.get("lastPrice", 0) or 0)
            price = ask if ask > 0 else last
            if price <= 0 or price > max_premium:
                continue

            vol = int(row.get("volume", 0) or 0) if pd.notna(row.get("volume")) else 0
            oi = int(row.get("openInterest", 0) or 0) if pd.notna(row.get("openInterest")) else 0
            iv = float(row.get("impliedVolatility", 0) or 0) if pd.notna(row.get("impliedVolatility")) else 0.30
            if iv <= 0.01:
                iv = 0.30

            if vol < 10 and oi < 25:
                continue

            eff_dte = max(0.5, float(days_to_expiration))
            underval = evaluate_option_undervaluation(
                spot=spot_price,
                strike=strike,
                ask_price=price,
                time_years=max(1.0 / 365.0, eff_dte / 365.0),
                iv=iv,
                option_type=opt_type,
                ohlcv=ohlcv,
            )
            payoff = evaluate_payoff_potential(
                spot=spot_price,
                strike=strike,
                ask_price=price,
                dte_days=eff_dte,
                atr=atr,
                iv=underval.implied_vol,
                breakout_hv=underval.breakout_hv_85,
                option_type=opt_type,
            )

            vol_oi_ratio = vol / (oi + 1.0)
            setup_score = (
                geometric_mean([
                    spring_metrics.spring_score,
                    underval.undervaluation_score,
                    payoff.payoff_score,
                ])
                * 100.0
            )

            record = {
                "Ticker": symbol,
                "Expiration": exp_str,
                "DTE": days_to_expiration,
                "Type": opt_type,
                "Strike": strike,
                "Spot_Price": round(spot_price, 2),
                "Bid": round(bid, 2),
                "Premium": round(price, 2),
                "Volume": vol,
                "OI": oi,
                "IV": round(iv, 3),
                "IV_HV_Ratio": underval.iv_hv_ratio,
                "BS_Fair_Value": underval.bs_fair_value_hv,
                "Valuation_Label": underval.valuation_label,
                "Spring_Score": round(spring_metrics.spring_score * 100.0, 1),
                "Is_In_Coil": spring_metrics.is_in_coil,
                "Layers_Confirmed": spring_metrics.layers_confirmed,
                "Spot_For_1_00": payoff.spot_for_1_00,
                "Spot_For_10_00": payoff.spot_for_10_00,
                "ATR_Move_To_1_00": payoff.atr_move_to_1_00,
                "ATR_Move_To_10_00": payoff.atr_move_to_10_00,
                "Proj_Value_3ATR": payoff.proj_value_3atr,
                "Proj_Value_5ATR": payoff.proj_value_5atr,
                "Max_Projected_Value": payoff.max_projected_value,
                "Potential_Multiple": payoff.potential_multiple,
                "Payoff_Tier": payoff.payoff_tier,
                "Setup_Score": round(setup_score, 1),
            }

            if days_to_expiration <= 1:
                zero_dte_ideas.append(record)
            else:
                long_swing_ideas.append(record)

    return zero_dte_ideas, long_swing_ideas


def analyze_ticker(
    symbol: str,
    provider=None,
    previous_lookup: Optional[Dict[str, Any]] = None,
    max_premium: float = MAX_FRUGAL_PREMIUM,
):
    if previous_lookup is None:
        previous_lookup = {}
    if provider is None:
        provider = get_market_data_provider()

    _bump("total")
    try:
        today = date.today()
        options_list = provider.get_options_expirations(symbol)
        exp_dates = {}
        for exp in options_list:
            try:
                exp_dates[exp] = datetime.strptime(exp, "%Y-%m-%d").date()
            except ValueError:
                continue

        candidates = {
            e: d
            for e, d in exp_dates.items()
            if 0 <= (d - today).days <= MAX_DAYS_TO_NEAREST_EXPIRATION
        }

        if not candidates:
            _bump("no_expiration_in_window")
            return None, [], []

        nearest_exp_str = min(candidates, key=lambda e: candidates[e])
        days_to_expiration = (candidates[nearest_exp_str] - today).days

        calls, puts = provider.get_option_chain(symbol, nearest_exp_str)
        total_put_oi = puts["openInterest"].sum() if (not puts.empty and "openInterest" in puts) else 0
        total_call_oi = calls["openInterest"].sum() if (not calls.empty and "openInterest" in calls) else 0

        hist = provider.get_historical_ohlcv(symbol, period="1y")
        if hist is None or hist.empty:
            _bump("no_history")
            return None, [], []

        spot_price = float(hist["Close"].iloc[-1])
        closes = hist["Close"].tolist()
        fallback_iv = realized_vol(closes[-30:])

        spring = evaluate_spring_setup(symbol, hist)
        zero_dte_ideas, long_swing_ideas = extract_frugal_spring_ideas(
            calls,
            puts,
            days_to_expiration,
            nearest_exp_str,
            symbol,
            spot_price,
            spring.atr_14,
            spring,
            hist,
            max_premium=max_premium,
        )

        otm_calls = calls[calls["strike"] > spot_price] if not calls.empty else pd.DataFrame()
        if otm_calls.empty or total_call_oi == 0:
            _bump("no_otm_calls")
            return None, zero_dte_ideas, long_swing_ideas

        put_call_ratio = total_put_oi / total_call_oi if total_call_oi else float("inf")
        pcr_score = _clamp01((PCR_NEUTRAL_CAP - put_call_ratio) / PCR_NEUTRAL_CAP)

        five_day_performance = spring.perf_5d_pct
        momentum_score = _clamp01(five_day_performance / MOMENTUM_CAP_PCT)

        time_years = max(days_to_expiration, 1) / 365.0
        gamma_annotated, total_gamma_dollars = compute_gamma_exposure(otm_calls, spot_price, time_years, fallback_iv)

        if gamma_annotated.empty or total_gamma_dollars <= 0:
            return None, zero_dte_ideas, long_swing_ideas

        gamma_wall_row = gamma_annotated.loc[gamma_annotated["Gamma_Dollars"].idxmax()]
        gamma_wall_strike = float(gamma_wall_row["strike"])
        gamma_dollars_at_wall = float(gamma_wall_row["Gamma_Dollars"])
        distance_to_wall = ((gamma_wall_strike / spot_price) - 1.0) * 100.0
        wall_score = _clamp01(1.0 - (distance_to_wall / WALL_DISTANCE_CAP_PCT))

        gamma_concentration = _safe_div(gamma_dollars_at_wall, total_gamma_dollars)
        gamma_concentration_score = _clamp01(gamma_concentration / GAMMA_CONCENTRATION_CAP)

        info = provider.get_ticker_info(symbol) or {}
        shares_short = info.get("sharesShort", 0)
        avg_volume = info.get("averageVolume10days") or info.get("averageVolume") or 0
        has_dtc_data = bool(avg_volume and shares_short)
        days_to_cover = (shares_short / avg_volume) if has_dtc_data else 0.0
        dtc_score = _clamp01(days_to_cover / DAYS_TO_COVER_CAP) if has_dtc_data else None

        short_pct_float = info.get("shortPercentOfFloat")
        has_spf_data = short_pct_float is not None and short_pct_float == short_pct_float and short_pct_float > 0
        spf_score = _clamp01(short_pct_float / SHORT_PCT_FLOAT_CAP) if has_spf_data else None

        short_fuel_components = [s for s in (dtc_score, spf_score) if s is not None]
        has_short_data = bool(short_fuel_components)
        short_fuel_score = (sum(short_fuel_components) / len(short_fuel_components)) if has_short_data else None

        avg_dollar_volume = (avg_volume or 0) * spot_price
        gamma_fuel_ratio = _safe_div(total_gamma_dollars, avg_dollar_volume)
        gamma_fuel_score = _clamp01(gamma_fuel_ratio / GAMMA_FUEL_RATIO_CAP)

        core_factors = [wall_score, gamma_concentration_score, gamma_fuel_score]
        if has_short_data and short_fuel_score is not None:
            core_factors.append(short_fuel_score)
        core_trigger = geometric_mean(core_factors)

        context = (
            CONTEXT_SUB_WEIGHTS["put_call_skew"] * pcr_score
            + CONTEXT_SUB_WEIGHTS["momentum"] * momentum_score
        )
        acceleration = compute_acceleration(
            symbol,
            distance_to_wall,
            gamma_fuel_ratio * 100.0,
            days_to_cover,
            has_short_data,
            previous_lookup,
        )

        if acceleration is not None:
            composite_score = 100.0 * (
                CORE_WEIGHT * core_trigger
                + SPRING_WEIGHT * spring.spring_score
                + CONTEXT_WEIGHT * context
                + ACCEL_WEIGHT * acceleration
            )
        else:
            rem = CORE_WEIGHT + SPRING_WEIGHT + CONTEXT_WEIGHT
            composite_score = 100.0 * (
                (CORE_WEIGHT / rem) * core_trigger
                + (SPRING_WEIGHT / rem) * spring.spring_score
                + (CONTEXT_WEIGHT / rem) * context
            )

        # Find best <= $0.25 OTM Call on this chain if available
        frugal_calls = otm_calls[
            (otm_calls["ask"] > 0) & (otm_calls["ask"] <= max_premium)
        ] if "ask" in otm_calls else pd.DataFrame()

        if not frugal_calls.empty:
            best_frugal = frugal_calls.sort_values(by="openInterest", ascending=False).iloc[0]
            recommended_strike = float(best_frugal["strike"])
            rec_premium = float(best_frugal["ask"])
        else:
            recommended_strike = gamma_wall_strike
            rec_ask = float(gamma_wall_row.get("ask", 0) or 0)
            rec_premium = rec_ask if rec_ask > 0 else float(gamma_wall_row.get("lastPrice", 0) or 0)

        breakeven_price = recommended_strike + rec_premium if rec_premium > 0 else None

        tier = score_tier(composite_score)
        trend = trend_label(acceleration)
        if has_short_data:
            short_fuel_text = f"DTC {days_to_cover:.1f}x" if has_dtc_data else ""
            if has_spf_data:
                short_fuel_text += f"{', ' if short_fuel_text else ''}{short_pct_float*100:.1f}% of float short"
        else:
            short_fuel_text = "no short-interest data available"

        thesis = (
            f"[{spring.spring_thesis}] {symbol} needs a {distance_to_wall:.1f}% move to reach the "
            f"${gamma_wall_strike:.2f} Gamma Wall (${gamma_dollars_at_wall/1e6:.2f}M per 1% move, "
            f"{gamma_concentration*100:.0f}% of call gamma, exp {nearest_exp_str} in {days_to_expiration}d). "
            f"Short fuel: {short_fuel_text}. 5-day momentum: {five_day_performance:+.1f}%."
        )

        _bump("scored")
        gamma_result = {
            "Ticker": symbol,
            "Opportunity_Score": round(composite_score, 1),
            "Spring_Score": round(spring.spring_score * 100.0, 1),
            "Is_In_Coil": spring.is_in_coil,
            "Is_TTM_Squeeze": spring.is_ttm_squeeze,
            "BBW_Percentile": spring.bbw_percentile,
            "HVR_Pct": spring.hvr_pct,
            "Layers_Confirmed": spring.layers_confirmed,
            "Tier": tier,
            "Trend": trend,
            "Spot_Price": round(float(spot_price), 2),
            "ATR_14": spring.atr_14,
            "Expiration": nearest_exp_str,
            "Days_to_Expiration": days_to_expiration,
            "Put_Call_OI_Ratio": round(put_call_ratio, 3),
            "Gamma_Wall_Strike": gamma_wall_strike,
            "Gamma_Dollars_at_Wall": round(gamma_dollars_at_wall, 0),
            "Gamma_Concentration_%": round(gamma_concentration * 100, 1),
            "Gamma_Fuel_vs_ADV_%": round(gamma_fuel_ratio * 100, 1),
            "Distance_to_Wall_%": round(distance_to_wall, 1),
            "5_Day_Performance_%": round(five_day_performance, 1),
            "Days_to_Cover": round(days_to_cover, 2) if has_dtc_data else None,
            "Short_Pct_Float_%": round(short_pct_float * 100, 1) if has_spf_data else None,
            "Has_Short_Data": has_short_data,
            "Acceleration": round(acceleration, 2) if acceleration is not None else None,
            "Recommended_Strike": float(recommended_strike),
            "Recommended_Premium": round(rec_premium, 2) if rec_premium > 0 else None,
            "Breakeven_Price": round(breakeven_price, 2) if breakeven_price else None,
            "Thesis": thesis,
        }

        return gamma_result, zero_dte_ideas, long_swing_ideas
    except Exception as e:
        logger.debug(f"Error analyzing {symbol}: {e}")
        _bump("error")
        return None, [], []


def run_gamma_scanner(
    raw_tickers: List[str],
    provider=None,
    max_workers: int = MAX_WORKERS,
    max_premium: float = MAX_FRUGAL_PREMIUM,
) -> pd.DataFrame:
    """Run unified Volatility Coil & Gamma Squeeze scanner logic."""
    if provider is None:
        provider = get_market_data_provider()

    previous_lookup = load_previous_scan()
    if previous_lookup:
        print(f"Loaded previous scan for acceleration tracking ({len(previous_lookup)} tickers).")

    print(f"Analyzing {len(raw_tickers)} tickers for Volatility Coils & Gamma Squeeze setups...")
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    Path("data/history").mkdir(parents=True, exist_ok=True)

    # Preload bulk OHLCV for speed if using YFinanceProvider
    if hasattr(provider, "preload_bulk_ohlcv") and len(raw_tickers) <= 80:
        bulk = fetch_bulk_data(raw_tickers, period="1y")
        provider.preload_bulk_ohlcv(bulk, period="1y")

    scored_candidates = []
    all_0dte_ideas = []
    all_swing_ideas = []

    analyze_fn = functools.partial(
        analyze_ticker,
        provider=provider,
        previous_lookup=previous_lookup,
        max_premium=max_premium,
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(
            tqdm(
                executor.map(analyze_fn, raw_tickers),
                total=len(raw_tickers),
                desc="Scanning Coils & Gamma",
            )
        )

    for res, zdte, swing in results:
        if res:
            scored_candidates.append(res)
        if zdte:
            all_0dte_ideas.extend(zdte)
        if swing:
            all_swing_ideas.extend(swing)

    print_stats()

    output_df = pd.DataFrame()
    if scored_candidates:
        output_df = pd.DataFrame(scored_candidates).sort_values(by="Opportunity_Score", ascending=False)
        output_df.insert(0, "Scan_Date", date.today().isoformat())
        output_df.to_csv(PREVIOUS_SCAN_PATH, index=False)
        output_df.to_csv(f"data/history/gamma_squeeze_{date.today().isoformat()}.csv", index=False)
        output_df.to_csv("data/reports/gamma_squeeze_potential.csv", index=False)
        output_df.to_csv("gamma_squeeze_potential.csv", index=False)
        print(
            f"\n[OK] Top Coiled & Gamma Squeeze Opportunities:\n"
            f"{output_df[['Ticker', 'Opportunity_Score', 'Spring_Score', 'Is_In_Coil', 'Tier', 'Distance_to_Wall_%']].head(10)}"
        )

    if all_0dte_ideas:
        pd.DataFrame(all_0dte_ideas).sort_values(by="Setup_Score", ascending=False).to_csv(
            "data/reports/0dte_trade_ideas.csv", index=False
        )
    if all_swing_ideas:
        pd.DataFrame(all_swing_ideas).sort_values(by="Setup_Score", ascending=False).to_csv(
            "data/reports/long_option_trade_ideas.csv", index=False
        )

    return output_df


def main():
    parser = argparse.ArgumentParser(
        description="Frugal Options Spring Scanner (<= $0.25 Entry | $1.00 to $10.00+ Potential)"
    )
    parser.add_argument(
        "--scan",
        type=str,
        default="all",
        help="Scan types to execute: all, gamma, 0dte, leaps (or comma-separated e.g. '0dte,leaps')",
    )
    parser.add_argument(
        "--universe",
        type=str,
        default="default",
        choices=["default", "finviz", "liquidity", "13f", "nasdaq"],
        help="Universe to scan (default: curated high-liquidity options_tickers.txt)",
    )
    parser.add_argument(
        "--max-premium",
        type=float,
        default=MAX_FRUGAL_PREMIUM,
        help="Maximum option contract premium in dollars (default: 0.25 = $25/contract)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Number of parallel worker threads (default: {MAX_WORKERS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry run mode (prints Discord payloads instead of sending webhooks)",
    )
    parser.add_argument(
        "--live-post",
        action="store_true",
        help="Send live Discord notifications (overrides --dry-run)",
    )
    parser.add_argument(
        "--update-outcomes",
        action="store_true",
        help="Update historical trade outcomes in running trade logs",
    )
    parser.add_argument(
        "--force-0dte",
        action="store_true",
        default=True,
        help="Run 0DTE/near-term spring scanner regardless of nominal calendar day",
    )
    parser.add_argument(
        "--execute-paper",
        action="store_true",
        help="Submit top approved <= $0.25 spring candidates to Alpaca Paper Trading if configured",
    )

    args = parser.parse_args()
    dry_run = not args.live_post

    provider = get_market_data_provider()
    market_regime = determine_market_regime(provider)
    breadth_trend = check_market_breadth(provider)
    print(f"\n{'='*72}")
    print(f"🚀 FRUGAL OPTIONS SPRING SCANNER | Max Cost: <= ${args.max_premium:.2f} | Targets: $1.00 (4x+) & $10.00+ (40x+)")
    print(f"📊 Macro Regime: {market_regime} | Market Breadth: {breadth_trend}")
    print(f"{'='*72}")

    if args.update_outcomes:
        print("[Maintenance] Updating historical 0DTE trade outcomes...")
        updated = update_0dte_trade_outcomes(provider)
        print(f"[Maintenance] Updated {updated} historical trades.")

    scanner = MarketScanner()
    raw_tickers = scanner.get_universe(args.universe)
    if not raw_tickers:
        print("No tickers loaded; aborting scan.")
        return

    requested_scans = [s.strip().lower() for s in args.scan.split(",")]
    run_all = "all" in requested_scans

    gamma_results_df = pd.DataFrame()
    top_0dte_calls = pd.DataFrame()
    top_0dte_puts = pd.DataFrame()
    leaps_results_df = pd.DataFrame()

    # 1. Volatility Coil & Gamma Squeeze Scan
    if run_all or "gamma" in requested_scans:
        gamma_results_df = run_gamma_scanner(
            raw_tickers,
            provider=provider,
            max_workers=args.workers,
            max_premium=args.max_premium,
        )

    # 2. 0DTE / Near-Term Intraday Spring Scanner (<= $0.25)
    if run_all or "0dte" in requested_scans:
        today = date.today()
        is_0dte_day, day_label = is_today_0dte_trading_day(today)
        if is_0dte_day or args.force_0dte:
            print(f"\n[Scheduler] Active 0DTE Spring Session: {day_label or 'Daily/Nearest Short-DTE Mode'}")
            top_0dte_calls, top_0dte_puts = run_0dte_scan(
                tickers=raw_tickers,
                provider=provider,
                target_date=today,
                max_workers=args.workers,
                max_premium=args.max_premium,
            )

    # 3. Long Position & LEAPS Spring Scanner (<= $0.25)
    if run_all or "leaps" in requested_scans or "long" in requested_scans:
        if not gamma_results_df.empty:
            top_gamma_tickers = gamma_results_df["Ticker"].head(50).tolist()
        else:
            top_gamma_tickers = raw_tickers
        leaps_results_df = run_leaps_scan(
            tickers=top_gamma_tickers,
            provider=provider,
            max_workers=args.workers,
            max_premium=args.max_premium,
        )

    # 4. Conviction Tracker Persistence Update
    tracker = ConvictionTracker()
    if not leaps_results_df.empty:
        enriched = tracker.update_persistence(leaps_results_df.to_dict(orient="records"))
        leaps_results_df = pd.DataFrame(enriched)
        leaps_results_df.to_csv("leaps_opportunities.csv", index=False)
        leaps_results_df.to_csv("data/reports/long_spring_opportunities.csv", index=False)

    # 5. Optional Alpaca Paper Trading Execution
    if args.execute_paper:
        paper_trader = PaperTrader()
        paper_trader.get_account_info()
        for df_cand in [top_0dte_calls.head(2), top_0dte_puts.head(2), leaps_results_df.head(3)]:
            if df_cand is not None and not df_cand.empty:
                for _, row in df_cand.iterrows():
                    paper_trader.place_spring_option_order(row.to_dict(), quantity=1)

    # 6. Dispatch Discord Intelligence Briefing
    paper_status = compute_paper_trading_status()
    dispatch_full_scan_report(
        gamma_df=gamma_results_df,
        zero_dte_calls=top_0dte_calls,
        zero_dte_puts=top_0dte_puts,
        leaps_df=leaps_results_df,
        paper_status=paper_status,
        dry_run=dry_run,
    )

    print("\n[Done] All Frugal Options Spring Scanner pipeline tasks completed successfully.")


if __name__ == "__main__":
    main()
