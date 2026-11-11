"""
zero_dte_scanner.py - 0DTE / Near-Term Intraday Options Spring Scanner (<= $0.25).

Scans for undervalued, coiled-spring 0DTE (and ultra-near-term) option contracts
costing $0.25 or less ($25 max per contract) with high confidence to expand to
$1.00 (4x+) or $10.00+ (40x+) during a volatility coil release or gamma squeeze.
"""

import os
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from tqdm import tqdm
import concurrent.futures

from market_data import MarketDataProvider, get_market_data_provider
from calendar_utils import get_catalyst_flag
from scoring import (
    geometric_mean,
    compute_atr,
    calculate_iv_rank,
    score_atr_distance,
    score_spread_tightness,
    score_unusual_options_activity,
    score_gamma_exposure,
    bs_delta,
    bs_gamma,
    evaluate_spring_setup,
    evaluate_option_undervaluation,
    evaluate_payoff_potential,
    RISK_FREE_RATE_DEFAULT,
    MAX_FRUGAL_PREMIUM_DEFAULT,
)
from trade_logger import (
    has_traded_today,
    append_0dte_trades,
    compute_paper_trading_status,
)

logger = logging.getLogger(__name__)

# --- Configuration Values ---
MIN_UNDERLYING_ADV = float(os.getenv("SCANNER_0DTE_MIN_ADV", "1000000"))
MIN_UNDERLYING_PRICE = float(os.getenv("SCANNER_0DTE_MIN_PRICE", "10.0"))
MIN_CONTRACT_OI = int(os.getenv("SCANNER_0DTE_MIN_OI", "50"))
MIN_VOL_OI_RATIO = float(os.getenv("SCANNER_0DTE_MIN_VOL_OI", "0.5"))
MAX_FRUGAL_PREMIUM = float(os.getenv("SCANNER_MAX_PREMIUM", str(MAX_FRUGAL_PREMIUM_DEFAULT)))
DAILY_ACCOUNT_RISK_PCT = float(os.getenv("SCANNER_0DTE_DAILY_RISK_PCT", "0.02"))
ESTIMATED_ACCOUNT_SIZE = float(os.getenv("SCANNER_ACCOUNT_SIZE", "25000.0"))
MAX_CONCURRENT_POSITIONS = 5
MAX_CONTRACTS_PER_UNDERLYING = 1


def passes_underlying_filter(symbol: str, spot_price: Optional[float], info: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verify underlying filters:
    1. Share price > $10
    2. Average daily volume > 1,000,000 shares
    """
    if spot_price is None or spot_price < MIN_UNDERLYING_PRICE:
        return False, f"Spot ${spot_price} below ${MIN_UNDERLYING_PRICE}"

    adv = (
        info.get("averageVolume")
        or info.get("averageVolume10days")
        or info.get("regularMarketVolume")
        or 0
    )
    if adv < MIN_UNDERLYING_ADV:
        return False, f"ADV {adv:,} below {MIN_UNDERLYING_ADV:,}"

    return True, "Passed"


def passes_contract_spread_filter(
    bid: float,
    ask: float,
    price: float,
    max_premium: float = MAX_FRUGAL_PREMIUM,
) -> bool:
    """
    Contract filter for Frugal Spring Scanner:
    - Enforces price <= max_premium (default $0.25) and > $0.00
    - Bid-ask spread <= $0.03 on quotes in the $0.05-$0.10 range
    - Bid-ask spread <= $0.06 on quotes in the $0.11-$0.25 range
    """
    if ask <= 0 or bid < 0:
        return False
    if price <= 0 or price > max_premium:
        return False
    spread = ask - bid
    if 0.05 <= price <= 0.10:
        if spread > 0.035:
            return False
    elif price < 0.05:
        if spread > 0.025:
            return False
    elif price <= 0.25:
        if spread > 0.065 and (spread / ask) > 0.30:
            return False
    else:
        if (spread / ask) > 0.25:
            return False
    return True


def _resolve_target_expiration(
    expirations: List[str],
    target_exp_str: str,
    target_date: date,
    allow_nearest_short_dte: bool = True,
    max_fallback_dte: int = 5,
) -> Optional[Tuple[str, int]]:
    """
    Resolve target 0DTE expiration string. If exact same-day expiration exists, use it (0 DTE).
    If allow_nearest_short_dte is True and exact date has no chain (e.g. single stocks on Wed),
    select the nearest expiration within max_fallback_dte days.
    """
    if not expirations:
        return None
    if target_exp_str in expirations:
        return target_exp_str, 0
    if not allow_nearest_short_dte:
        return None
    for exp in sorted(expirations):
        try:
            exp_d = datetime.strptime(exp, "%Y-%m-%d").date()
            dte = (exp_d - target_date).days
            if 0 <= dte <= max_fallback_dte:
                return exp, dte
        except ValueError:
            continue
    return None


def scan_single_ticker_0dte(
    symbol: str,
    target_exp_str: str,
    target_date: date,
    provider: MarketDataProvider,
    max_premium: float = MAX_FRUGAL_PREMIUM,
    allow_nearest_short_dte: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Analyze single ticker for <= $0.25 0DTE call and put spring candidates
    targeting $1.00 (4x+) to $10.00+ (40x+) value.
    """
    call_results: List[Dict[str, Any]] = []
    put_results: List[Dict[str, Any]] = []

    try:
        expirations = provider.get_options_expirations(symbol)
        resolved = _resolve_target_expiration(
            expirations,
            target_exp_str,
            target_date,
            allow_nearest_short_dte=allow_nearest_short_dte,
        )
        if resolved is None:
            return [], []
        active_exp_str, dte_days = resolved

        spot_price = provider.get_spot_price(symbol)
        info = provider.get_ticker_info(symbol)

        valid_underlying, _ = passes_underlying_filter(symbol, spot_price, info)
        if not valid_underlying or spot_price is None:
            return [], []

        ohlcv = provider.get_historical_ohlcv(symbol, period="1y")
        if ohlcv is None or ohlcv.empty:
            return [], []

        atr = compute_atr(ohlcv, window=14)
        spring = evaluate_spring_setup(symbol, ohlcv)
        has_catalyst, catalyst_desc = get_catalyst_flag(symbol, target_date)
        catalyst_score = 1.0 if has_catalyst else 0.65

        calls_df, puts_df = provider.get_option_chain(symbol, active_exp_str)
        if calls_df.empty and puts_df.empty:
            return [], []

        traded_today = has_traded_today(symbol, target_date, scan_type="0dte")
        effective_dte = max(0.5, float(dte_days)) if dte_days > 0 else 0.5
        time_years = max(1.0 / (365.0 * 2.0), effective_dte / 365.0)

        for opt_label, chain_df, target_list in [
            ("CALL", calls_df, call_results),
            ("PUT", puts_df, put_results),
        ]:
            if chain_df is None or chain_df.empty:
                continue

            vols = chain_df["volume"].fillna(0) if "volume" in chain_df else pd.Series([0.0])
            avg_vol = float(vols.mean()) if not vols.empty else 0.0
            std_vol = float(vols.std()) if len(vols) > 1 else 0.0

            for _, row in chain_df.iterrows():
                strike = float(row.get("strike", 0) or 0)
                if strike <= 0:
                    continue
                if opt_label == "CALL" and strike <= spot_price * 0.995:
                    continue
                if opt_label == "PUT" and strike >= spot_price * 1.005:
                    continue

                bid = float(row.get("bid", 0) or 0)
                ask = float(row.get("ask", 0) or 0)
                last = float(row.get("lastPrice", 0) or 0)
                price = ask if ask > 0 else last

                # Strict Frugal Cap: must cost <= max_premium ($0.25)
                if price <= 0 or price > max_premium:
                    continue
                if not passes_contract_spread_filter(bid, ask, price, max_premium=max_premium):
                    continue

                volume = float(row.get("volume", 0) or 0)
                oi = float(row.get("openInterest", 0) or 0)
                if oi < MIN_CONTRACT_OI and volume < MIN_CONTRACT_OI:
                    continue
                vol_oi_ratio = volume / (oi + 1.0)
                if vol_oi_ratio < MIN_VOL_OI_RATIO and volume < 50:
                    continue

                iv = float(row.get("impliedVolatility", 0) or 0)
                if iv <= 0.01:
                    iv = 0.30

                # 1. Undervaluation evaluation
                underval = evaluate_option_undervaluation(
                    spot=spot_price,
                    strike=strike,
                    ask_price=price,
                    time_years=time_years,
                    iv=iv,
                    option_type=opt_label.lower(),
                    ohlcv=ohlcv,
                )

                # 2. Payoff potential evaluation ($0.25 -> $1.00 / $10.00+)
                payoff = evaluate_payoff_potential(
                    spot=spot_price,
                    strike=strike,
                    ask_price=price,
                    dte_days=effective_dte,
                    atr=atr,
                    iv=underval.implied_vol,
                    breakout_hv=underval.breakout_hv_85,
                    option_type=opt_label.lower(),
                )

                # 3. Quantitative factor scores
                f_atr_dist = score_atr_distance(spot_price, strike, atr, opt_label.lower())
                g = bs_gamma(spot_price, strike, time_years, RISK_FREE_RATE_DEFAULT, underval.implied_vol)
                delta_val = abs(bs_delta(spot_price, strike, time_years, RISK_FREE_RATE_DEFAULT, underval.implied_vol, opt_label.lower()))
                gamma_dollars = g * oi * 100.0 * (spot_price ** 2) * 0.01
                f_gex = max(0.25, score_gamma_exposure(gamma_dollars, cap=2_500_000.0))
                f_uoa = max(0.25, score_unusual_options_activity(volume, oi, avg_vol, std_vol))
                f_tightness = max(0.30, score_spread_tightness(bid, price))

                # Directional alignment bonus
                dir_aligned = (
                    (opt_label == "CALL" and spring.direction == "BULLISH")
                    or (opt_label == "PUT" and spring.direction == "BEARISH")
                )
                f_spring = spring.spring_score if dir_aligned else max(0.30, spring.spring_score * 0.80)

                factors = [
                    f_spring,
                    underval.undervaluation_score,
                    payoff.payoff_score,
                    f_atr_dist,
                    f_gex,
                    f_uoa,
                    catalyst_score,
                    f_tightness,
                ]
                composite_score = geometric_mean(factors) * 100.0

                contract_symbol = str(row.get("contractSymbol", f"{symbol}_{active_exp_str}_{opt_label[0]}{strike}"))
                max_loss_held_to_zero = price * 100.0 * MAX_CONTRACTS_PER_UNDERLYING
                dist_atr_units = round(abs(strike - spot_price) / atr, 2)

                target_list.append({
                    "Scan_Date": target_date.isoformat(),
                    "Expiration_Date": active_exp_str,
                    "DTE": dte_days,
                    "Ticker": symbol,
                    "Option_Type": opt_label,
                    "Contract_Symbol": contract_symbol,
                    "Strike": strike,
                    "Spot_Price": round(spot_price, 2),
                    "Bid": round(bid, 2),
                    "Ask": round(price, 2),
                    "Spread": round(max(0.0, price - bid), 3),
                    "Entry_Ask": round(price, 2),
                    "Delta": round(delta_val, 3),
                    "Volume": int(volume),
                    "Open_Interest": int(oi),
                    "Vol_OI_Ratio": round(vol_oi_ratio, 2),
                    "IV_Pct": round(underval.implied_vol * 100.0, 1),
                    "Realized_HV_Pct": round(underval.realized_hv_20 * 100.0, 1),
                    "IV_HV_Ratio": underval.iv_hv_ratio,
                    "IV_Rank": underval.iv_rank,
                    "BS_Fair_Value": underval.bs_fair_value_hv,
                    "Valuation_Label": underval.valuation_label,
                    "Undervaluation_Score": round(underval.undervaluation_score * 100.0, 1),
                    "Is_In_Coil": spring.is_in_coil,
                    "Is_TTM_Squeeze": spring.is_ttm_squeeze,
                    "BBW_Percentile": spring.bbw_percentile,
                    "HVR_Pct": spring.hvr_pct,
                    "Layers_Confirmed": spring.layers_confirmed,
                    "Spring_Score": round(f_spring * 100.0, 1),
                    "Spring_Thesis": spring.spring_thesis,
                    "Dist_ATR_Units": dist_atr_units,
                    "Spot_For_1_00": payoff.spot_for_1_00,
                    "Spot_For_10_00": payoff.spot_for_10_00,
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
                    "Gamma_Exposure_Dollars": round(gamma_dollars, 0),
                    "Catalyst_Flag": catalyst_desc,
                    "Spread_Tightness": round(f_tightness, 3),
                    "Opportunity_Score": round(composite_score, 1),
                    "Max_Loss_Held_To_Zero": round(max_loss_held_to_zero, 2),
                    "Suggested_Position_Cap": f"Max {MAX_CONTRACTS_PER_UNDERLYING} contract (${price*100:.0f} risk, <= $25 frugal cap)",
                    "Averaging_Down_Violation_Flag": "VIOLATION: Trade already logged today" if traded_today else "CLEAN: 1st entry of day",
                    "Outcome_Status": "OPEN",
                })

    except Exception as e:
        logger.debug(f"Error scanning 0DTE for {symbol}: {e}")

    return call_results, put_results


def run_0dte_scan(
    tickers: List[str],
    provider: Optional[MarketDataProvider] = None,
    target_date: Optional[date] = None,
    max_workers: int = 10,
    max_premium: float = MAX_FRUGAL_PREMIUM,
    top_k: int = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run 0DTE / near-term spring scan across ticker universe for options <= $0.25.
    Returns: (top_calls_df, top_puts_df)
    """
    if provider is None:
        provider = get_market_data_provider()

    if target_date is None:
        target_date = date.today()

    target_exp_str = target_date.strftime("%Y-%m-%d")
    paper_status = compute_paper_trading_status()
    print(f"\n[0DTE Spring Scanner] Target Date: {target_exp_str} | Max Premium: <= ${max_premium:.2f} | Targets: $1.00 (4x+) & $10.00+ (40x+)")
    print(f"[0DTE Spring Scanner] Mode: {paper_status['status_message']}")
    print(f"[0DTE Spring Scanner] Scanning {len(tickers)} symbols for undervalued 0DTE coiled spring contracts...")

    all_calls: List[Dict[str, Any]] = []
    all_puts: List[Dict[str, Any]] = []

    def _worker(sym: str):
        return scan_single_ticker_0dte(
            sym,
            target_exp_str,
            target_date,
            provider,
            max_premium=max_premium,
            allow_nearest_short_dte=True,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, sym): sym for sym in tickers}
        for fut in tqdm(concurrent.futures.as_completed(futures), total=len(tickers), desc="Scanning 0DTE Springs"):
            try:
                calls, puts = fut.result()
                all_calls.extend(calls)
                all_puts.extend(puts)
            except Exception as e:
                logger.debug(f"Worker failure: {e}")

    top_calls_df = pd.DataFrame()
    top_puts_df = pd.DataFrame()

    if all_calls:
        calls_df = pd.DataFrame(all_calls)
        top_calls_df = calls_df.sort_values(
            by=["Opportunity_Score", "Max_Projected_Value"],
            ascending=[False, False],
        ).head(top_k).reset_index(drop=True)

    if all_puts:
        puts_df = pd.DataFrame(all_puts)
        top_puts_df = puts_df.sort_values(
            by=["Opportunity_Score", "Max_Projected_Value"],
            ascending=[False, False],
        ).head(top_k).reset_index(drop=True)

    os.makedirs("data/reports", exist_ok=True)
    if not top_calls_df.empty:
        top_calls_df.to_csv("data/reports/0dte_top_calls.csv", index=False)
    if not top_puts_df.empty:
        top_puts_df.to_csv("data/reports/0dte_top_puts.csv", index=False)

    # Combined 0DTE report for dashboard
    combined_0dte = pd.concat([top_calls_df, top_puts_df], ignore_index=True)
    if not combined_0dte.empty:
        combined_0dte.to_csv("data/reports/0dte_spring_opportunities.csv", index=False)

    surfaced_trades = []
    if not top_calls_df.empty:
        surfaced_trades.extend(top_calls_df.to_dict(orient="records"))
    if not top_puts_df.empty:
        surfaced_trades.extend(top_puts_df.to_dict(orient="records"))

    if surfaced_trades:
        append_0dte_trades(surfaced_trades)

    return top_calls_df, top_puts_df
