"""
scoring.py - Quantitative Option Pricing, Undervaluation Engine, Multi-Layer Volatility
Spring Detection, and Asymmetric Payoff Modeling ($0.25 -> $1.00 / $10.00+).

Unifies:
- options-ticker-universe's Black-Scholes Greeks, geometric mean factor model, GEX, UOA, and ATR scoring
- Frugal_Trader's Volatility Coil (BBW + HVR + Keltner Squeeze), EMA Ribbon Trend, Relative Strength, and RSI layers
- Asymmetric Convexity & Undervaluation modeling for <= $0.25 options targeting $1.00 (4x+) and $10.00+ (40x+).
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from scipy.stats import norm

# Standard Constants
GEOMETRIC_MEAN_FLOOR = 0.05
RISK_FREE_RATE_DEFAULT = 0.045
MAX_FRUGAL_PREMIUM_DEFAULT = 0.25
TARGET_VALUE_TIER_1 = 1.00
TARGET_VALUE_TIER_2 = 10.00


def _clamp01(x: float) -> float:
    """Clamp a floating value strictly to the range [0.0, 1.0]."""
    try:
        val = float(x)
        if math.isnan(val):
            return 0.0
        return max(0.0, min(1.0, val))
    except (ValueError, TypeError):
        return 0.0


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Safely divide two numbers, avoiding division by zero or NaN."""
    try:
        if not b or math.isnan(b) or b == 0:
            return default
        res = a / b
        return default if math.isnan(res) else res
    except ZeroDivisionError:
        return default


def geometric_mean(values: List[float], floor: float = GEOMETRIC_MEAN_FLOOR) -> float:
    """
    Compute geometric mean of a list of factor scores (each in [0, 1]).
    Ensures that no single factor dominates, and if any factor is near zero,
    the overall composite score reflects that drag.
    """
    if not values:
        return 0.0
    product = 1.0
    for v in values:
        product *= max(floor, _clamp01(v))
    return float(product ** (1.0 / len(values)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# --- Black-Scholes Option Pricing & Greeks ---

def bs_price(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    iv: float,
    option_type: str = "call",
) -> float:
    """
    Theoretical Black-Scholes European option price (with intrinsic floor).
    """
    opt = option_type.lower()
    intrinsic = max(0.0, spot - strike) if opt == "call" else max(0.0, strike - spot)
    if spot <= 0 or strike <= 0 or time_years <= 0 or iv <= 0:
        return intrinsic
    try:
        sqrt_t = math.sqrt(time_years)
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv * iv) * time_years) / (iv * sqrt_t)
        d2 = d1 - iv * sqrt_t
        if opt == "call":
            theo = spot * float(norm.cdf(d1)) - strike * math.exp(-risk_free_rate * time_years) * float(norm.cdf(d2))
        else:
            theo = strike * math.exp(-risk_free_rate * time_years) * float(norm.cdf(-d2)) - spot * float(norm.cdf(-d1))
        return max(intrinsic, float(theo))
    except (ValueError, ZeroDivisionError, OverflowError):
        return intrinsic


def bs_delta(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    iv: float,
    option_type: str = "call",
) -> float:
    """Black-Scholes Delta for European option contract."""
    if spot <= 0 or strike <= 0 or time_years <= 0 or iv <= 0:
        if option_type.lower() == "call":
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0
    try:
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv * iv) * time_years) / (iv * math.sqrt(time_years))
        if option_type.lower() == "call":
            return float(norm.cdf(d1))
        else:
            return float(norm.cdf(d1) - 1.0)
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def bs_gamma(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    iv: float,
) -> float:
    """Black-Scholes Gamma."""
    if spot <= 0 or strike <= 0 or time_years <= 0 or iv <= 0:
        return 0.0
    try:
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv * iv) * time_years) / (iv * math.sqrt(time_years))
        return _norm_pdf(d1) / (spot * iv * math.sqrt(time_years))
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def bs_vega(
    spot: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    iv: float,
) -> float:
    """Black-Scholes Vega (per 1% / 0.01 change in IV)."""
    if spot <= 0 or strike <= 0 or time_years <= 0 or iv <= 0:
        return 0.0
    try:
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv * iv) * time_years) / (iv * math.sqrt(time_years))
        return (spot * _norm_pdf(d1) * math.sqrt(time_years)) * 0.01
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


# --- Volatility, ATR, and Realized Vol Calculations ---

def compute_atr(ohlcv_df: pd.DataFrame, window: int = 14) -> float:
    """Compute Average True Range (ATR) over the trailing window."""
    if ohlcv_df is None or len(ohlcv_df) < 2:
        return 1.0

    high = ohlcv_df["High"]
    low = ohlcv_df["Low"]
    close = ohlcv_df["Close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean().dropna()

    if atr.empty:
        return float(tr.mean() or 1.0)
    return max(0.01, float(atr.iloc[-1]))


def compute_realized_vol_profile(historical_ohlcv: pd.DataFrame) -> Dict[str, float]:
    """
    Compute 20-day HV, 60-day HV, 52-week min/max HV, 85th-percentile breakout HV,
    and Frugal_Trader's Historical Volatility Rank (HVR 0-100).
    """
    default_profile = {
        "hv_20": 0.30,
        "hv_60": 0.30,
        "hv_min": 0.15,
        "hv_max": 0.60,
        "hv_breakout": 0.45,
        "hvr_pct": 50.0,
    }
    if historical_ohlcv is None or len(historical_ohlcv) < 25 or "Close" not in historical_ohlcv:
        return default_profile

    closes = historical_ohlcv["Close"].astype(float)
    log_rets = np.log(closes / closes.shift(1)).dropna()
    if len(log_rets) < 20:
        return default_profile

    rolling_20 = (log_rets.rolling(window=20).std() * np.sqrt(252)).dropna()
    rolling_30 = (log_rets.rolling(window=min(30, len(log_rets))).std() * np.sqrt(252)).dropna()
    rolling_60 = (log_rets.rolling(window=min(60, len(log_rets))).std() * np.sqrt(252)).dropna()

    if rolling_20.empty:
        return default_profile

    hv_20 = max(0.05, float(rolling_20.iloc[-1]))
    hv_60 = max(0.05, float(rolling_60.iloc[-1])) if not rolling_60.empty else hv_20

    trailing_252 = rolling_20.tail(252)
    hv_min = max(0.05, float(trailing_252.min()))
    hv_max = max(hv_min + 0.01, float(trailing_252.max()))
    hv_breakout = max(hv_20, float(np.quantile(trailing_252, 0.85)))

    # Frugal_Trader HVR (0 - 100 scale based on 30d HV over trailing 252d)
    if not rolling_30.empty:
        hv30_yr = rolling_30.tail(252)
        cur_30 = float(hv30_yr.iloc[-1])
        low_30 = float(hv30_yr.min())
        high_30 = float(hv30_yr.max())
        hvr_pct = ((cur_30 - low_30) / (high_30 - low_30) * 100.0) if high_30 > low_30 else 50.0
    else:
        hvr_pct = ((hv_20 - hv_min) / (hv_max - hv_min) * 100.0)

    return {
        "hv_20": round(hv_20, 4),
        "hv_60": round(hv_60, 4),
        "hv_min": round(hv_min, 4),
        "hv_max": round(hv_max, 4),
        "hv_breakout": round(hv_breakout, 4),
        "hvr_pct": round(max(0.0, min(100.0, hvr_pct)), 2),
    }


def calculate_iv_rank(current_iv: float, historical_ohlcv: pd.DataFrame) -> float:
    """
    Calculate 52-week IV rank/percentile of the underlying using realized 20-day volatility history.
    """
    if historical_ohlcv is None or len(historical_ohlcv) < 20:
        return 0.5

    closes = historical_ohlcv["Close"]
    log_rets = np.log(closes / closes.shift(1)).dropna()
    rolling_vol = (log_rets.rolling(window=20).std() * np.sqrt(252)).dropna()

    if len(rolling_vol) < 5:
        return 0.5

    min_vol = float(rolling_vol.min())
    max_vol = float(rolling_vol.max())

    if max_vol <= min_vol or math.isclose(max_vol, min_vol):
        return 0.5

    iv_rank = (current_iv - min_vol) / (max_vol - min_vol)
    return _clamp01(iv_rank)


# --- Standard Factor Scoring Functions ---

def score_atr_distance(spot: float, strike: float, atr: float, option_type: str = "call") -> float:
    """
    Score strike distance in units of ATR.
    Target sweet spot: ~1.5x to 3.0x ATR OTM.
    Returns a normalized [0, 1] score peaking in that window.
    """
    if atr <= 0:
        return 0.5

    if option_type.lower() == "call":
        dist_atr = (strike - spot) / atr
    else:
        dist_atr = (spot - strike) / atr

    if dist_atr < 0.2:
        return 0.2

    if 1.5 <= dist_atr <= 3.0:
        return 1.0
    elif 0.2 <= dist_atr < 1.5:
        return 0.3 + 0.7 * ((dist_atr - 0.2) / 1.3)
    elif 3.0 < dist_atr <= 5.0:
        return 1.0 - 0.8 * ((dist_atr - 3.0) / 2.0)
    else:
        return 0.05


def score_spread_tightness(bid: float, ask: float) -> float:
    """
    Score bid-ask spread tightness: inverse of bid-ask spread as % of price.
    Returns [0, 1].
    """
    if ask <= 0:
        return 0.0
    spread = max(0.0, ask - bid)
    spread_pct = spread / ask
    tightness = 1.0 - (spread_pct / 0.50)
    return _clamp01(tightness)


def score_unusual_options_activity(
    volume: float,
    oi: float,
    chain_avg_vol: float,
    chain_vol_std: float,
) -> float:
    """Score unusual options activity via volume z-score and Volume/OI ratio."""
    vol_oi_ratio = volume / (oi + 1.0)
    ratio_score = _clamp01(vol_oi_ratio / 4.0)

    if chain_vol_std > 0:
        z_score = (volume - chain_avg_vol) / chain_vol_std
        z_score_norm = _clamp01((z_score + 1.0) / 4.0)
    else:
        z_score_norm = ratio_score

    return 0.6 * ratio_score + 0.4 * z_score_norm


def score_gamma_exposure(gamma_dollars: float, cap: float = 10_000_000.0) -> float:
    """Score dealer gamma exposure near the strike."""
    return _clamp01(gamma_dollars / cap)


def evaluate_directional_thesis(
    historical_ohlcv: pd.DataFrame,
    ticker_info: dict,
) -> Tuple[bool, str, float]:
    """
    Evaluate directional thesis for long-dated options scanner.
    Criteria:
      - Spot > SMA200 (primary macro uptrend)
      - SMA50 > SMA200 (golden cross / momentum confirmation)
      - 6-month return > 0%
    """
    if historical_ohlcv is None or len(historical_ohlcv) < 150:
        return False, "Insufficient history for directional thesis", 0.0

    closes = historical_ohlcv["Close"]
    current_price = float(closes.iloc[-1])

    sma50 = float(closes.rolling(window=50).mean().iloc[-1])
    sma200 = float(closes.rolling(window=min(200, len(closes))).mean().iloc[-1])

    lookback_idx = min(126, len(closes) - 1)
    six_month_ret = ((current_price / float(closes.iloc[-lookback_idx])) - 1.0) * 100.0

    uptrend = current_price > sma200
    moving_avg_alignment = sma50 > sma200
    momentum_pos = six_month_ret > 0.0

    if not (uptrend and momentum_pos):
        thesis = f"Failed thesis: Spot ${current_price:.2f} vs SMA200 ${sma200:.2f}, 6M Ret: {six_month_ret:+.1f}%"
        return False, thesis, 0.0

    score_components = [
        _clamp01((current_price / sma200 - 0.95) / 0.25),
        _clamp01((sma50 / sma200 - 0.98) / 0.15) if moving_avg_alignment else 0.4,
        _clamp01(six_month_ret / 30.0),
    ]
    thesis_score = float(np.mean(score_components))

    summary = (
        f"Bullish Trend: Spot > SMA200 (${sma200:.2f}), "
        f"SMA50 (${sma50:.2f}) > SMA200, 6M Mom: {six_month_ret:+.1f}%"
    )
    return True, summary, thesis_score


# --- Multi-Layer Volatility Spring Detection Engine (Frugal_Trader + Quant GEX) ---

@dataclass
class SpringMetrics:
    """Complete technical & volatility spring profile for an underlying ticker."""
    ticker: str
    spot_price: float
    atr_14: float
    atr_pct: float
    direction: str                  # 'BULLISH' or 'BEARISH'
    is_in_coil: bool                # Layer 1: BBW compression / Keltner TTM squeeze / Low HVR
    is_ttm_squeeze: bool            # Bollinger Bands inside Keltner Channels
    bbw_current: float
    bbw_min_126d: float
    bbw_percentile: float           # 0 - 100 percentile of BBW
    hvr_pct: float                  # Historical Volatility Rank (0 - 100)
    is_trending: bool               # Layer 2: EMA 8/20/50 alignment & slope
    ema_slope: float
    has_relative_strength: bool     # Layer 3: Strong 5d/20d/126d momentum & volume surge
    perf_5d_pct: float
    perf_20d_pct: float
    perf_126d_pct: float
    volume_surge_ratio: float
    has_launchpad_rsi: bool         # Layer 4: RSI coiled in spring launchpad
    rsi_14: float
    layers_confirmed: int           # 0 to 4 layers confirmed
    spring_score: float             # Normalized [0.0, 1.0] spring readiness score
    spring_thesis: str


def evaluate_spring_setup(symbol: str, ohlcv: pd.DataFrame) -> SpringMetrics:
    """
    Evaluates an underlying's 'Spring Opportunity' across 4 technical & volatility layers:
      1. Volatility Compression / Coil (Bollinger Band Width near 6M/1Y lows, TTM Keltner Squeeze, or low HVR)
      2. EMA Ribbon Trend & Slope (EMA 8, 20, 50 alignment & 5-bar slope)
      3. Relative Momentum & Volume Ignition (5d/20d/6m momentum + volume expansion)
      4. RSI Coiled Launchpad (RSI 45-68 for bullish spring or 32-55 for bearish breakdown)
    """
    if ohlcv is None or ohlcv.empty or len(ohlcv) < 25:
        spot = float(ohlcv["Close"].iloc[-1]) if (ohlcv is not None and not ohlcv.empty) else 0.0
        return SpringMetrics(
            ticker=symbol, spot_price=spot, atr_14=max(0.5, spot * 0.02), atr_pct=2.0,
            direction="BULLISH", is_in_coil=False, is_ttm_squeeze=False,
            bbw_current=0.10, bbw_min_126d=0.05, bbw_percentile=50.0, hvr_pct=50.0,
            is_trending=False, ema_slope=0.0, has_relative_strength=False,
            perf_5d_pct=0.0, perf_20d_pct=0.0, perf_126d_pct=0.0, volume_surge_ratio=1.0,
            has_launchpad_rsi=False, rsi_14=50.0, layers_confirmed=0,
            spring_score=0.35, spring_thesis="Insufficient historical bars",
        )

    closes = ohlcv["Close"].astype(float)
    spot = float(closes.iloc[-1])
    atr = compute_atr(ohlcv, window=14)
    atr_pct = (atr / spot * 100.0) if spot > 0 else 2.0

    # --- Layer 1: Volatility Compression / Coil & TTM Squeeze ---
    sma20 = closes.rolling(window=20).mean()
    std20 = closes.rolling(window=20).std()
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20
    bbw_series = ((bb_upper - bb_lower) / sma20).dropna()

    bbw_current = float(bbw_series.iloc[-1]) if not bbw_series.empty else 0.10
    lookback_bbw = bbw_series.tail(min(252, len(bbw_series)))
    bbw_min = float(lookback_bbw.min()) if not lookback_bbw.empty else bbw_current
    bbw_max = float(lookback_bbw.max()) if not lookback_bbw.empty else bbw_current + 0.01
    bbw_percentile = (
        ((bbw_current - bbw_min) / (bbw_max - bbw_min) * 100.0)
        if bbw_max > bbw_min
        else 50.0
    )

    # Keltner Channel (20 EMA +/- 1.5 * ATR) for TTM Squeeze check
    ema20_series = closes.ewm(span=20, adjust=False).mean()
    ema20_last = float(ema20_series.iloc[-1])
    kc_upper = ema20_last + 1.5 * atr
    kc_lower = ema20_last - 1.5 * atr
    bb_up_last = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else spot * 1.05
    bb_low_last = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else spot * 0.95
    is_ttm_squeeze = (bb_up_last <= kc_upper * 1.01) and (bb_low_last >= kc_lower * 0.99)

    vol_profile = compute_realized_vol_profile(ohlcv)
    hvr_pct = vol_profile["hvr_pct"]

    # EMA 8 / EMA 100 convergence check (from Frugal_Trader evaluate_coils)
    ema8_last = float(closes.ewm(span=8, adjust=False).mean().iloc[-1])
    ema50_series = closes.ewm(span=50, adjust=False).mean()
    ema50_last = float(ema50_series.iloc[-1])
    ema100_last = float(closes.ewm(span=min(100, len(closes)), adjust=False).mean().iloc[-1])
    ema_convergence = (abs(ema8_last - ema100_last) / ema100_last < 0.05) if ema100_last > 0 else False

    is_in_coil = (
        is_ttm_squeeze
        or (bbw_percentile <= 30.0)
        or (bbw_current <= bbw_min * 1.18)
        or (hvr_pct <= 30.0)
        or (ema_convergence and bbw_percentile <= 45.0)
    )

    # --- Layer 2: EMA Ribbon Trend & Slope ---
    slope_lookback = min(6, len(ema50_series))
    ema_slope = float((ema50_series.iloc[-1] - ema50_series.iloc[-slope_lookback]) / max(1, slope_lookback - 1))
    norm_slope_pct = (ema_slope / spot * 100.0) if spot > 0 else 0.0

    direction = "BULLISH" if (spot >= ema20_last or ema8_last >= ema20_last) else "BEARISH"
    ribbon_aligned_bull = (spot >= ema20_last) and (ema8_last >= ema20_last * 0.995)
    ribbon_aligned_bear = (spot < ema20_last) and (ema8_last <= ema20_last * 1.005)
    is_trending = (abs(ema_slope) > 0.10) or (abs(norm_slope_pct) > 0.08) or ribbon_aligned_bull or ribbon_aligned_bear

    # --- Layer 3: Relative Momentum & Volume Ignition ---
    idx_5 = min(6, len(closes))
    idx_20 = min(21, len(closes))
    idx_126 = min(126, len(closes))
    perf_5d = ((spot / float(closes.iloc[-idx_5])) - 1.0) * 100.0 if float(closes.iloc[-idx_5]) > 0 else 0.0
    perf_20d = ((spot / float(closes.iloc[-idx_20])) - 1.0) * 100.0 if float(closes.iloc[-idx_20]) > 0 else 0.0
    perf_126d = ((spot / float(closes.iloc[-idx_126])) - 1.0) * 100.0 if float(closes.iloc[-idx_126]) > 0 else 0.0

    vol_surge_ratio = 1.0
    if "Volume" in ohlcv.columns and len(ohlcv) >= 20:
        vols = ohlcv["Volume"].astype(float)
        avg_vol_20 = float(vols.tail(20).mean())
        last_vol = float(vols.iloc[-1])
        if avg_vol_20 > 0:
            vol_surge_ratio = last_vol / avg_vol_20

    if direction == "BULLISH":
        has_relative_strength = (perf_5d > 0.5) or (perf_20d > 2.0) or (perf_126d > 8.0) or (vol_surge_ratio >= 1.15)
    else:
        has_relative_strength = (perf_5d < -0.5) or (perf_20d < -2.0) or (vol_surge_ratio >= 1.15)

    # --- Layer 4: RSI Coiled Launchpad ---
    delta_c = closes.diff()
    gain = delta_c.where(delta_c > 0, 0.0).rolling(window=14).mean()
    loss = (-delta_c.where(delta_c < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)
    rsi_14 = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    if direction == "BULLISH":
        has_launchpad_rsi = (42.0 <= rsi_14 <= 68.0) or (rsi_14 < 35.0)
    else:
        has_launchpad_rsi = (32.0 <= rsi_14 <= 58.0) or (rsi_14 > 68.0)

    layers_confirmed = sum([
        1 if is_in_coil else 0,
        1 if is_trending else 0,
        1 if has_relative_strength else 0,
        1 if has_launchpad_rsi else 0,
    ])

    # Quantitative Spring Score in [0, 1]
    coil_component = _clamp01(1.0 - (min(bbw_percentile, hvr_pct) / 80.0))
    if is_ttm_squeeze:
        coil_component = max(coil_component, 0.90)
    trend_component = _clamp01(0.5 + min(0.5, abs(norm_slope_pct) * 2.0)) if is_trending else 0.35
    mom_component = _clamp01(0.45 + min(0.55, (abs(perf_5d) / 6.0) * 0.35 + (vol_surge_ratio - 0.8) * 0.25))
    rsi_component = 0.85 if has_launchpad_rsi else 0.45

    spring_score = _clamp01(
        0.40 * coil_component
        + 0.25 * trend_component
        + 0.20 * mom_component
        + 0.15 * rsi_component
    )

    thesis_tags = []
    if is_ttm_squeeze:
        thesis_tags.append("TTM Keltner Squeeze")
    elif is_in_coil:
        thesis_tags.append(f"Volatility Coil (BBW {bbw_percentile:.0f}%ile, HVR {hvr_pct:.0f}%)")
    if is_trending:
        thesis_tags.append(f"{direction.title()} EMA Ribbon (Slope {ema_slope:+.2f})")
    if has_relative_strength:
        thesis_tags.append(f"Mom 5d {perf_5d:+.1f}% / Vol {vol_surge_ratio:.1f}x")
    if has_launchpad_rsi:
        thesis_tags.append(f"RSI Launchpad ({rsi_14:.1f})")

    spring_thesis = " + ".join(thesis_tags) if thesis_tags else f"{direction.title()} Technical Setup"

    return SpringMetrics(
        ticker=symbol,
        spot_price=round(spot, 2),
        atr_14=round(atr, 2),
        atr_pct=round(atr_pct, 2),
        direction=direction,
        is_in_coil=is_in_coil,
        is_ttm_squeeze=is_ttm_squeeze,
        bbw_current=round(bbw_current, 4),
        bbw_min_126d=round(bbw_min, 4),
        bbw_percentile=round(bbw_percentile, 1),
        hvr_pct=round(hvr_pct, 1),
        is_trending=is_trending,
        ema_slope=round(ema_slope, 3),
        has_relative_strength=has_relative_strength,
        perf_5d_pct=round(perf_5d, 2),
        perf_20d_pct=round(perf_20d, 2),
        perf_126d_pct=round(perf_126d, 2),
        volume_surge_ratio=round(vol_surge_ratio, 2),
        has_launchpad_rsi=has_launchpad_rsi,
        rsi_14=round(rsi_14, 1),
        layers_confirmed=layers_confirmed,
        spring_score=round(spring_score, 4),
        spring_thesis=spring_thesis,
    )


# --- Option Undervaluation Engine ---

@dataclass
class UndervaluationMetrics:
    """Quantifies whether an option <= $0.25 is statistically undervalued."""
    implied_vol: float
    realized_hv_20: float
    realized_hv_60: float
    breakout_hv_85: float
    iv_hv_ratio: float              # < 1.0 means IV is cheaper than realized volatility
    iv_rank: float                  # 0.0 to 1.0
    bs_fair_value_hv: float         # Theoretical Black-Scholes price using realized HV
    bs_breakout_vol_value: float    # Theoretical Black-Scholes price if IV expands to breakout HV
    gamma_per_dollar: float         # Gamma / Ask (convexity per dollar of premium)
    vega_per_dollar: float          # Vega / Ask (volatility expansion leverage)
    undervaluation_score: float     # Normalized [0.0, 1.0] score
    valuation_label: str


def evaluate_option_undervaluation(
    spot: float,
    strike: float,
    ask_price: float,
    time_years: float,
    iv: float,
    option_type: str,
    ohlcv: pd.DataFrame,
    risk_free_rate: float = RISK_FREE_RATE_DEFAULT,
) -> UndervaluationMetrics:
    """
    Determines if a low-cost option (<= $0.25) is undervalued relative to:
      1. Realized historical volatility (IV / HV ratio)
      2. 52-week IV Rank
      3. Black-Scholes theoretical fair value under realized & coil-breakout volatility
      4. Gamma & Vega convexity per dollar of premium paid.
    """
    vol_prof = compute_realized_vol_profile(ohlcv)
    hv_20 = vol_prof["hv_20"]
    hv_60 = vol_prof["hv_60"]
    hv_breakout = vol_prof["hv_breakout"]

    eff_iv = iv if iv > 0.01 else hv_20
    ref_hv = max(hv_20, hv_60)
    iv_hv_ratio = _safe_div(eff_iv, ref_hv, default=1.0)
    iv_rank = calculate_iv_rank(eff_iv, ohlcv)

    bs_fair_hv = bs_price(spot, strike, time_years, risk_free_rate, ref_hv, option_type)
    bs_breakout_val = bs_price(spot, strike, time_years, risk_free_rate, hv_breakout, option_type)

    g = bs_gamma(spot, strike, time_years, risk_free_rate, eff_iv)
    v = bs_vega(spot, strike, time_years, risk_free_rate, eff_iv)
    safe_ask = max(0.01, ask_price)
    gamma_per_dollar = g / safe_ask
    vega_per_dollar = v / safe_ask

    # Component 1: IV vs HV Discount (IV < HV scores 0.80 - 1.00)
    iv_hv_score = _clamp01(1.35 - 0.65 * iv_hv_ratio)

    # Component 2: Low IV Rank (cheaper percentile of 52w vol range)
    iv_rank_score = _clamp01(1.0 - 0.65 * iv_rank)

    # Component 3: Theoretical Fair-Value & Vol-Expansion Edge vs Ask Price
    theo_ratio = max(bs_fair_hv, bs_breakout_val * 0.75) / safe_ask
    theo_edge_score = _clamp01(theo_ratio / 1.50)

    # Component 4: Convexity (Gamma + Vega per dollar spent)
    convexity_score = _clamp01((gamma_per_dollar / 0.25) * 0.6 + (vega_per_dollar / 0.20) * 0.4)

    underval_score = _clamp01(
        0.30 * iv_hv_score
        + 0.25 * iv_rank_score
        + 0.25 * theo_edge_score
        + 0.20 * convexity_score
    )

    if iv_hv_ratio < 0.85 or bs_fair_hv >= safe_ask * 1.15:
        label = "DEEP VALUE (IV < Realized HV)"
    elif iv_hv_ratio <= 1.05 or bs_breakout_val >= safe_ask * 1.50:
        label = "UNDERVALUED COIL"
    elif iv_rank <= 0.35:
        label = "LOW IV PERCENTILE"
    else:
        label = "HIGH CONVEXITY LOTTO"

    return UndervaluationMetrics(
        implied_vol=round(eff_iv, 4),
        realized_hv_20=round(hv_20, 4),
        realized_hv_60=round(hv_60, 4),
        breakout_hv_85=round(hv_breakout, 4),
        iv_hv_ratio=round(iv_hv_ratio, 2),
        iv_rank=round(iv_rank, 3),
        bs_fair_value_hv=round(bs_fair_hv, 3),
        bs_breakout_vol_value=round(bs_breakout_val, 3),
        gamma_per_dollar=round(gamma_per_dollar, 4),
        vega_per_dollar=round(vega_per_dollar, 4),
        undervaluation_score=round(underval_score, 4),
        valuation_label=label,
    )


# --- Asymmetric Payoff & Convexity Modeler ($0.25 -> $1.00 / $10.00+) ---

@dataclass
class PayoffMetrics:
    """
    Models the asymmetric payoff potential of an option costing <= $0.25
    to reach $1.00 (4x+) and $10.00+ (40x+) in value.
    """
    entry_ask: float
    breakeven_spot: float
    spot_for_1_00: float            # Underlying price where intrinsic value = $1.00
    spot_for_10_00: float           # Underlying price where intrinsic value = $10.00
    move_to_1_00_pct: float         # % move in underlying to reach $1.00 intrinsic
    move_to_10_00_pct: float        # % move in underlying to reach $10.00 intrinsic
    atr_move_to_1_00: float         # ATR units to reach $1.00 intrinsic
    atr_move_to_10_00: float        # ATR units to reach $10.00 intrinsic
    proj_value_2atr: float          # Option value on a 2x horizon-ATR spring move
    proj_value_3atr: float          # Option value on a 3x horizon-ATR spring move
    proj_value_5atr: float          # Option value on a 5x horizon-ATR super-spring move
    max_projected_value: float      # Peak modeled spring value ($1.00 to $10.00+)
    potential_multiple: float       # Max projected value / entry_ask (e.g. 4x to 40x+)
    can_reach_1_00: bool
    can_reach_10_00: bool
    payoff_tier: str
    payoff_score: float             # Normalized [0.0, 1.0] score for composite ranking


def evaluate_payoff_potential(
    spot: float,
    strike: float,
    ask_price: float,
    dte_days: float,
    atr: float,
    iv: float,
    breakout_hv: float,
    option_type: str = "call",
    risk_free_rate: float = RISK_FREE_RATE_DEFAULT,
) -> PayoffMetrics:
    """
    Calculates exact price targets, ATR multiples, and Black-Scholes repriced values
    for a <= $0.25 contract to reach $1.00 (4x+) and $10.00+ (40x+).
    """
    opt = option_type.lower()
    safe_ask = max(0.01, ask_price)
    safe_atr = max(0.05, atr)
    safe_spot = max(0.01, spot)

    # Horizon scaling: over DTE days, expected ATR range scales with sqrt(effective_days)
    # For 0DTE (dte_days <= 1), horizon_scale = 1.0 (single session intraday range)
    # For Swing/LEAPS, we evaluate a spring breakout occurring after ~30% of DTE (with 70% DTE remaining)
    horizon_days = max(1.0, min(float(dte_days), 60.0)) if dte_days > 1 else 1.0
    horizon_atr = safe_atr * math.sqrt(horizon_days)
    remaining_years_on_spring = (max(0.25, float(dte_days) * 0.65) / 365.0) if dte_days > 1 else (1.0 / (365.0 * 3.0))

    if opt == "call":
        breakeven_spot = strike + safe_ask
        spot_1_00 = strike + TARGET_VALUE_TIER_1
        spot_10_00 = strike + TARGET_VALUE_TIER_2
        dist_1_00 = max(0.0, spot_1_00 - safe_spot)
        dist_10_00 = max(0.0, spot_10_00 - safe_spot)

        spot_2atr = safe_spot + 2.0 * horizon_atr
        spot_3atr = safe_spot + 3.0 * horizon_atr
        spot_5atr = safe_spot + 5.0 * horizon_atr
    else:
        breakeven_spot = max(0.01, strike - safe_ask)
        spot_1_00 = max(0.01, strike - TARGET_VALUE_TIER_1)
        spot_10_00 = max(0.01, strike - TARGET_VALUE_TIER_2)
        dist_1_00 = max(0.0, safe_spot - spot_1_00) if strike > TARGET_VALUE_TIER_1 else safe_spot
        dist_10_00 = max(0.0, safe_spot - spot_10_00) if strike > TARGET_VALUE_TIER_2 else safe_spot * 2.0

        spot_2atr = max(0.01, safe_spot - 2.0 * horizon_atr)
        spot_3atr = max(0.01, safe_spot - 3.0 * horizon_atr)
        spot_5atr = max(0.01, safe_spot - 5.0 * horizon_atr)

    move_1_00_pct = (dist_1_00 / safe_spot) * 100.0
    move_10_00_pct = (dist_10_00 / safe_spot) * 100.0

    # Daily ATR units and Horizon-adjusted ATR units
    atr_move_1_00 = dist_1_00 / safe_atr
    atr_move_10_00 = dist_10_00 / safe_atr
    horizon_atr_to_1_00 = dist_1_00 / horizon_atr
    horizon_atr_to_10_00 = dist_10_00 / horizon_atr

    # Expanded IV during a spring breakout (volatility expansion + vanna/vega boost)
    spring_iv = max(iv, breakout_hv, 0.35)

    val_2atr = bs_price(spot_2atr, strike, remaining_years_on_spring, risk_free_rate, spring_iv, opt)
    val_3atr = bs_price(spot_3atr, strike, remaining_years_on_spring, risk_free_rate, spring_iv * 1.10, opt)
    val_5atr = bs_price(spot_5atr, strike, remaining_years_on_spring, risk_free_rate, spring_iv * 1.20, opt)

    # For puts where strike < 10, cap max theoretical value at strike
    if opt == "put":
        val_2atr = min(strike, val_2atr)
        val_3atr = min(strike, val_3atr)
        val_5atr = min(strike, val_5atr)

    max_proj_val = max(val_3atr, val_5atr)
    potential_multiple = max_proj_val / safe_ask

    can_reach_1_00 = (val_3atr >= 1.00) or (horizon_atr_to_1_00 <= 3.0)
    can_reach_10_00 = (val_5atr >= 10.00) and (opt == "call" or strike >= 12.0)

    # Score feasibility of hitting $1.00 (weight 60%) and $10.00+ (weight 40%)
    score_1_00 = _clamp01(1.25 - (horizon_atr_to_1_00 / 4.0))
    val_boost_1_00 = _clamp01(val_3atr / 2.00)
    tier1_component = 0.55 * score_1_00 + 0.45 * val_boost_1_00

    score_10_00 = _clamp01(1.20 - (horizon_atr_to_10_00 / 7.5))
    val_boost_10_00 = _clamp01(val_5atr / 10.00)
    tier2_component = 0.50 * score_10_00 + 0.50 * val_boost_10_00

    payoff_score = _clamp01(0.60 * tier1_component + 0.40 * tier2_component)

    if can_reach_10_00 and val_3atr >= 2.00:
        payoff_tier = "🚀 $10.00+ Super-Spring Potential (40x+)"
    elif can_reach_10_00:
        payoff_tier = "💎 $1.00 Base / $10.00+ Tail Spring"
    elif can_reach_1_00:
        payoff_tier = "🔥 $1.00+ High-Confidence Spring (4x-20x)"
    else:
        payoff_tier = "⚡ Speculative Sub-$0.25 Spring"

    return PayoffMetrics(
        entry_ask=round(safe_ask, 2),
        breakeven_spot=round(breakeven_spot, 2),
        spot_for_1_00=round(spot_1_00, 2),
        spot_for_10_00=round(spot_10_00, 2),
        move_to_1_00_pct=round(move_1_00_pct, 2),
        move_to_10_00_pct=round(move_10_00_pct, 2),
        atr_move_to_1_00=round(atr_move_1_00, 2),
        atr_move_to_10_00=round(atr_move_10_00, 2),
        proj_value_2atr=round(val_2atr, 2),
        proj_value_3atr=round(val_3atr, 2),
        proj_value_5atr=round(val_5atr, 2),
        max_projected_value=round(max_proj_val, 2),
        potential_multiple=round(potential_multiple, 1),
        can_reach_1_00=can_reach_1_00,
        can_reach_10_00=can_reach_10_00,
        payoff_tier=payoff_tier,
        payoff_score=round(payoff_score, 4),
    )
