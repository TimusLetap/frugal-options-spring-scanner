"""
calendar_utils.py - NYSE Market Calendar, Holiday Shifting, Catalyst Detection,
and Macro Regime / Market Breadth Evaluation.

Combines:
1. options-ticker-universe's NYSE calendar 0DTE session shifting & Macro/Earnings catalyst detector
2. Frugal_Trader's Market Regime (SPY vs 50-day MA) and Market Breadth (^GSPC vs 20-day MA) filters
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict, Set
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf

logger = logging.getLogger(__name__)

_NYSE_CAL = mcal.get_calendar("NYSE")


def get_nyse_calendar():
    """Return the global NYSE market calendar."""
    global _NYSE_CAL
    if _NYSE_CAL is None:
        _NYSE_CAL = mcal.get_calendar("NYSE")
    return _NYSE_CAL


def is_trading_day(target_date: date) -> bool:
    """Return True if target_date is an open NYSE trading session."""
    cal = get_nyse_calendar()
    date_str = target_date.strftime("%Y-%m-%d")
    sched = cal.schedule(start_date=date_str, end_date=date_str)
    return not sched.empty


def get_target_0dte_trading_day(target_day: str = "monday", ref_date: Optional[date] = None) -> date:
    """
    Determine the actual trading day for 'this week's Monday 0DTE' or 'this week's Friday 0DTE'.
    Dynamically shifts:
      - Monday holiday -> shift forward to Tuesday (next trading day)
      - Friday holiday -> shift backward to Thursday (previous trading day)
    Derived strictly from pandas_market_calendars (NYSE calendar).
    """
    if ref_date is None:
        ref_date = date.today()

    current_weekday = ref_date.weekday()
    week_monday = ref_date - timedelta(days=current_weekday)
    week_friday = week_monday + timedelta(days=4)

    cal = get_nyse_calendar()
    sched_start = (week_monday - timedelta(days=3)).strftime("%Y-%m-%d")
    sched_end = (week_friday + timedelta(days=3)).strftime("%Y-%m-%d")
    schedule = cal.schedule(start_date=sched_start, end_date=sched_end)
    open_dates: Set[date] = set(schedule.index.date)

    target_day = target_day.strip().lower()

    if target_day == "monday":
        candidate = week_monday
        while candidate not in open_dates and candidate <= week_friday:
            candidate += timedelta(days=1)
        return candidate
    elif target_day == "friday":
        candidate = week_friday
        while candidate not in open_dates and candidate >= week_monday:
            candidate -= timedelta(days=1)
        return candidate
    else:
        raise ValueError(f"target_day must be 'monday' or 'friday', got '{target_day}'")


def get_current_week_0dte_trading_days(ref_date: Optional[date] = None) -> Tuple[date, date]:
    """Return tuple of (adjusted_monday, adjusted_friday) for the reference week."""
    if ref_date is None:
        ref_date = date.today()
    mon_day = get_target_0dte_trading_day("monday", ref_date)
    fri_day = get_target_0dte_trading_day("friday", ref_date)
    return mon_day, fri_day


def is_today_0dte_trading_day(ref_date: Optional[date] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if the current date is the active Monday or Friday 0DTE trading day.
    Returns: (is_0dte_day, session_label)
    """
    if ref_date is None:
        ref_date = date.today()

    mon_day, fri_day = get_current_week_0dte_trading_days(ref_date)

    if ref_date == mon_day:
        nominal_name = "Monday" if mon_day.weekday() == 0 else f"Monday (Shifted to {mon_day.strftime('%A')})"
        return True, nominal_name
    elif ref_date == fri_day:
        nominal_name = "Friday" if fri_day.weekday() == 4 else f"Friday (Shifted to {fri_day.strftime('%A')})"
        return True, nominal_name

    return False, None


# --- Economic & Earnings Catalyst Detection ---

KNOWN_MACRO_CATALYSTS: Dict[str, str] = {
    "2026-09-04": "US Non-Farm Payrolls (Jobs Report)",
    "2026-09-11": "US CPI Inflation Print",
    "2026-09-16": "FOMC Rate Decision & Press Conference",
    "2026-10-02": "US Non-Farm Payrolls (Jobs Report)",
    "2026-10-14": "US CPI Inflation Print",
    "2026-10-28": "FOMC Rate Decision",
    "2026-11-06": "US Non-Farm Payrolls (Jobs Report)",
    "2026-11-11": "Post-Election / Veterans Session Volatility Window",
    "2026-11-12": "US CPI Inflation Print",
    "2026-12-04": "US Non-Farm Payrolls (Jobs Report)",
    "2026-12-09": "FOMC Rate Decision",
    "2026-12-11": "US CPI Inflation Print",
}


def check_macro_catalyst(target_date: date) -> Optional[str]:
    """Check if target_date has a major scheduled macro release (FOMC, CPI, Jobs)."""
    date_str = target_date.strftime("%Y-%m-%d")
    return KNOWN_MACRO_CATALYSTS.get(date_str)


def check_earnings_catalyst(symbol: str, target_date: date) -> Optional[str]:
    """Check if the company has earnings scheduled on or near target_date."""
    try:
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar
        target_str = target_date.strftime("%Y-%m-%d")

        if isinstance(cal, pd.DataFrame) and not cal.empty:
            for col in cal.columns:
                val = str(cal[col].iloc[0])
                if target_str in val:
                    return f"Earnings on {target_str}"
        elif isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                if isinstance(ed, list):
                    for d in ed:
                        if hasattr(d, "strftime") and d.strftime("%Y-%m-%d") == target_str:
                            return f"Earnings on {target_str}"
                elif hasattr(ed, "strftime") and ed.strftime("%Y-%m-%d") == target_str:
                    return f"Earnings on {target_str}"
    except Exception as e:
        logger.debug(f"Could not fetch earnings for {symbol}: {e}")

    return None


def get_catalyst_flag(symbol: str, target_date: date) -> Tuple[bool, str]:
    """
    Check both company earnings and macro calendar for same-day catalysts.
    Returns: (has_catalyst: bool, description: str)
    """
    macro = check_macro_catalyst(target_date)
    if macro:
        return True, f"Macro: {macro}"

    earnings = check_earnings_catalyst(symbol, target_date)
    if earnings:
        return True, f"Company: {earnings}"

    return False, "None"


# --- Market Regime & Breadth Filters (from Frugal_Trader) ---

def determine_market_regime(provider=None) -> str:
    """
    Determines macro market regime (BULLISH, BEARISH, or NEUTRAL)
    by comparing SPY close to its 50-day moving average.
    """
    try:
        if provider is not None:
            hist = provider.get_historical_ohlcv("SPY", period="3mo")
        else:
            hist = yf.Ticker("SPY").history(period="3mo")
        if hist is None or hist.empty or len(hist) < 20:
            return "NEUTRAL"
        last_close = float(hist["Close"].iloc[-1])
        window = min(50, len(hist))
        ma50 = float(hist["Close"].rolling(window=window).mean().iloc[-1])
        return "BULLISH" if last_close > ma50 else "BEARISH"
    except Exception as e:
        logger.debug(f"Error determining market regime: {e}")
        return "NEUTRAL"


def check_market_breadth(provider=None) -> str:
    """
    Checks S&P 500 short-term breadth trend (SPY / ^GSPC vs 20-day MA).
    """
    try:
        if provider is not None:
            hist = provider.get_historical_ohlcv("SPY", period="2mo")
        else:
            hist = yf.Ticker("^GSPC").history(period="2mo")
        if hist is None or hist.empty or len(hist) < 15:
            return "NEUTRAL"
        last_close = float(hist["Close"].iloc[-1])
        window = min(20, len(hist))
        ma20 = float(hist["Close"].rolling(window=window).mean().iloc[-1])
        return "BULLISH" if last_close > ma20 else "BEARISH"
    except Exception as e:
        logger.debug(f"Error checking market breadth: {e}")
        return "NEUTRAL"
