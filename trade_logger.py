"""
trade_logger.py - Running trade logger, expectancy/win-rate tracker,
$1.00 / $10.00+ milestone outcome evaluator, and paper-trading validation guard.
"""

import os
import logging
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

PAPER_TRADING_ENV = os.getenv("SCANNER_PAPER_TRADING", "true").strip().lower()
PAPER_TRADING_MODE = PAPER_TRADING_ENV in ["true", "1", "yes"]
REQUIRED_PAPER_CYCLES = int(os.getenv("SCANNER_REQUIRED_PAPER_CYCLES", "12"))

RUNNING_0DTE_LOG_PATH = Path("data/history/0dte_running_trade_log.csv")
RUNNING_LEAPS_LOG_PATH = Path("data/history/long_spring_running_trade_log.csv")


def ensure_history_dirs():
    """Ensure data/history and data/reports directories exist."""
    RUNNING_0DTE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path("data/reports").mkdir(parents=True, exist_ok=True)


def load_0dte_running_log() -> pd.DataFrame:
    """Load the running 0DTE trade log."""
    ensure_history_dirs()
    if not RUNNING_0DTE_LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(RUNNING_0DTE_LOG_PATH)
    except Exception as e:
        logger.error(f"Error loading {RUNNING_0DTE_LOG_PATH}: {e}")
        return pd.DataFrame()


def load_leaps_running_log() -> pd.DataFrame:
    """Load the running Long/LEAPS Spring trade log."""
    ensure_history_dirs()
    if not RUNNING_LEAPS_LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(RUNNING_LEAPS_LOG_PATH)
    except Exception as e:
        logger.error(f"Error loading {RUNNING_LEAPS_LOG_PATH}: {e}")
        return pd.DataFrame()


def has_traded_today(symbol: str, target_date: Optional[date] = None, scan_type: str = "0dte") -> bool:
    """
    Enforce 'one entry per underlying per day' / 'no averaging down' rule.
    """
    if target_date is None:
        target_date = date.today()
    date_str = target_date.isoformat()

    df = load_0dte_running_log() if scan_type == "0dte" else load_leaps_running_log()
    if df.empty or "Scan_Date" not in df.columns or "Ticker" not in df.columns:
        return False

    matches = df[(df["Scan_Date"] == date_str) & (df["Ticker"] == symbol)]
    return not matches.empty


def append_0dte_trades(trades: List[Dict[str, Any]]) -> None:
    """Append newly surfaced 0DTE Spring candidates to the running log."""
    if not trades:
        return
    ensure_history_dirs()
    new_df = pd.DataFrame(trades)

    if RUNNING_0DTE_LOG_PATH.exists():
        try:
            existing_df = pd.read_csv(RUNNING_0DTE_LOG_PATH)
            combined = pd.concat([existing_df, new_df], ignore_index=True)
            if "Contract_Symbol" in combined.columns and "Scan_Date" in combined.columns:
                combined.drop_duplicates(subset=["Scan_Date", "Contract_Symbol"], keep="first", inplace=True)
            combined.to_csv(RUNNING_0DTE_LOG_PATH, index=False)
        except Exception as e:
            logger.error(f"Error appending to {RUNNING_0DTE_LOG_PATH}: {e}")
            new_df.to_csv(RUNNING_0DTE_LOG_PATH, index=False)
    else:
        new_df.to_csv(RUNNING_0DTE_LOG_PATH, index=False)


def append_leaps_trades(trades: List[Dict[str, Any]]) -> None:
    """Append newly surfaced Long/LEAPS Spring candidates to the running log."""
    if not trades:
        return
    ensure_history_dirs()
    new_df = pd.DataFrame(trades)

    if RUNNING_LEAPS_LOG_PATH.exists():
        try:
            existing_df = pd.read_csv(RUNNING_LEAPS_LOG_PATH)
            combined = pd.concat([existing_df, new_df], ignore_index=True)
            contract_col = "Contract_Symbol" if "Contract_Symbol" in combined.columns else "Contract"
            if contract_col in combined.columns and "Scan_Date" in combined.columns:
                combined.drop_duplicates(subset=["Scan_Date", contract_col], keep="first", inplace=True)
            combined.to_csv(RUNNING_LEAPS_LOG_PATH, index=False)
        except Exception as e:
            logger.error(f"Error appending to {RUNNING_LEAPS_LOG_PATH}: {e}")
            new_df.to_csv(RUNNING_LEAPS_LOG_PATH, index=False)
    else:
        new_df.to_csv(RUNNING_LEAPS_LOG_PATH, index=False)


def compute_paper_trading_status() -> Dict[str, Any]:
    """
    Verify paper-trading validation threshold (8-12 cycles before live capital sizing).
    """
    df = load_0dte_running_log()
    if df.empty or "Scan_Date" not in df.columns:
        return {
            "paper_trading_mode": PAPER_TRADING_MODE,
            "distinct_cycles": 0,
            "required_cycles": REQUIRED_PAPER_CYCLES,
            "approved_for_live_capital": False,
            "status_message": f"PAPER TRADING ONLY: 0 of {REQUIRED_PAPER_CYCLES} required Mon/Fri cycles logged.",
            "win_rate": 0.0,
            "expectancy": 0.0,
            "total_trades": 0,
        }

    distinct_dates = df["Scan_Date"].dropna().unique()
    distinct_cycles = len(distinct_dates)
    approved = (not PAPER_TRADING_MODE) or (distinct_cycles >= REQUIRED_PAPER_CYCLES)

    total_trades = len(df)
    win_rate = 0.0
    expectancy = 0.0

    if "PnL_Pct" in df.columns and not df["PnL_Pct"].dropna().empty:
        closed_trades = df.dropna(subset=["PnL_Pct"])
        if len(closed_trades) > 0:
            wins = closed_trades[closed_trades["PnL_Pct"] > 0]
            losses = closed_trades[closed_trades["PnL_Pct"] <= 0]
            win_rate = len(wins) / len(closed_trades)
            avg_win = wins["PnL_Pct"].mean() if not wins.empty else 0.0
            avg_loss = abs(losses["PnL_Pct"].mean()) if not losses.empty else 0.0
            expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)

    if approved:
        status_msg = f"VALIDATION COMPLETE: {distinct_cycles}/{REQUIRED_PAPER_CYCLES} cycles logged. Approved for capital sizing."
    else:
        status_msg = (
            f"PAPER TRADING ACTIVE: {distinct_cycles}/{REQUIRED_PAPER_CYCLES} cycles logged. "
            f"Need {REQUIRED_PAPER_CYCLES - distinct_cycles} more cycles before live capital sizing."
        )

    return {
        "paper_trading_mode": PAPER_TRADING_MODE,
        "distinct_cycles": distinct_cycles,
        "required_cycles": REQUIRED_PAPER_CYCLES,
        "approved_for_live_capital": approved,
        "status_message": status_msg,
        "win_rate": round(win_rate * 100, 1),
        "expectancy": round(expectancy, 2),
        "total_trades": total_trades,
    }


def update_0dte_trade_outcomes(market_data_provider) -> int:
    """
    Evaluates past logged 0DTE trades at close/expiration, tracking whether
    the contract reached $1.00+ (4x+) or $10.00+ (40x+).
    """
    df = load_0dte_running_log()
    if df.empty or "Outcome_Status" not in df.columns:
        return 0

    updated_count = 0
    today_str = date.today().isoformat()

    for idx, row in df.iterrows():
        if row.get("Outcome_Status") in ["EXPIRED", "CLOSED"]:
            continue

        exp_date_str = str(row.get("Expiration_Date", ""))
        if exp_date_str and exp_date_str <= today_str:
            ticker = row.get("Ticker")
            strike = float(row.get("Strike", 0))
            opt_type = str(row.get("Option_Type", "call")).lower()
            entry_price = float(row.get("Entry_Ask", 0))

            if entry_price <= 0:
                continue

            spot_close = market_data_provider.get_spot_price(ticker)
            if spot_close is None or spot_close <= 0:
                continue

            if opt_type == "call":
                payoff = max(0.0, spot_close - strike)
            else:
                payoff = max(0.0, strike - spot_close)

            pnl_dollars = (payoff - entry_price) * 100.0
            pnl_pct = ((payoff - entry_price) / entry_price) * 100.0

            df.at[idx, "Close_Price"] = round(spot_close, 2)
            df.at[idx, "Final_Contract_Value"] = round(payoff, 2)
            df.at[idx, "Hit_1_00_Target"] = bool(payoff >= 1.00)
            df.at[idx, "Hit_10_00_Target"] = bool(payoff >= 10.00)
            df.at[idx, "PnL_Dollars"] = round(pnl_dollars, 2)
            df.at[idx, "PnL_Pct"] = round(pnl_pct, 2)
            df.at[idx, "Outcome_Status"] = "EXPIRED"
            df.at[idx, "Updated_Date"] = today_str
            updated_count += 1

    if updated_count > 0:
        df.to_csv(RUNNING_0DTE_LOG_PATH, index=False)

    return updated_count
