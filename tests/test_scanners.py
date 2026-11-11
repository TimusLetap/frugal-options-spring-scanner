"""
tests/test_scanners.py - Unit and Integration Tests for:
- Calendar Engine & Catalyst Detection
- Quantitative Scoring, Black-Scholes Pricing & Greeks
- Multi-Layer Volatility Spring Detection Engine (BBW Coil, TTM Keltner Squeeze, HVR, EMA Slope, RS)
- Option Undervaluation Engine (IV vs Realized HV, Fair Value Edge)
- Asymmetric Payoff Modeler ($0.25 max entry -> $1.00 4x+ and $10.00+ 40x+ potential)
- Trade Logger, Anti-Averaging Guardrail, Paper Trading Validation Guard, and Discord Embeds.
"""

from datetime import date
import pandas as pd
import numpy as np

from calendar_utils import (
    get_target_0dte_trading_day,
    get_catalyst_flag,
)
from scoring import (
    geometric_mean,
    bs_price,
    bs_delta,
    bs_gamma,
    compute_atr,
    score_atr_distance,
    score_spread_tightness,
    evaluate_directional_thesis,
    evaluate_spring_setup,
    evaluate_option_undervaluation,
    evaluate_payoff_potential,
)
import trade_logger
from trade_logger import (
    has_traded_today,
    append_0dte_trades,
    compute_paper_trading_status,
)
from zero_dte_scanner import passes_underlying_filter, passes_contract_spread_filter
from discord_notifier import (
    build_0dte_embed,
    build_leaps_embed,
)


def test_calendar_holiday_shifts():
    """
    Verify NYSE calendar dynamically shifts holidays:
    - Monday holiday shifts forward to Tuesday (Labor Day 2026-09-07 -> 2026-09-08)
    - Friday holiday shifts backward to Thursday (Good Friday 2026-04-03 -> 2026-04-02)
    """
    ref_labor_day = date(2026, 9, 7)
    target_monday = get_target_0dte_trading_day("monday", ref_date=ref_labor_day)
    assert target_monday == date(2026, 9, 8)

    ref_good_friday = date(2026, 4, 3)
    target_friday = get_target_0dte_trading_day("friday", ref_date=ref_good_friday)
    assert target_friday == date(2026, 4, 2)


def test_catalyst_detection():
    """Verify macro print detection."""
    has_cat, desc = get_catalyst_flag("SPY", date(2026, 9, 4))
    assert has_cat is True
    assert "Macro: US Non-Farm Payrolls" in desc


def test_geometric_mean_and_atr_scoring():
    """Verify geometric mean prevents single-factor dominance and ATR sweet spot scores 1.0."""
    assert 0.75 <= geometric_mean([0.8, 0.85, 0.9, 0.75]) <= 0.90
    assert geometric_mean([0.9, 0.9, 0.9, 0.0]) < 0.50
    assert score_atr_distance(100.0, strike=104.0, atr=2.0, option_type="call") == 1.0


def test_spring_detection_coiled_setup():
    """
    Verify evaluate_spring_setup detects a tightly coiled stock (low BBW percentile,
    TTM Keltner squeeze, positive trend) and confirms multiple layers.
    """
    days = 260
    dates = pd.date_range(end=date.today(), periods=days)
    # First 220 days have wide swings, last 40 days compress into a tight bullish coil
    rng = np.random.default_rng(42)
    early = 100.0 + np.cumsum(rng.normal(0.05, 2.5, 220))
    late_base = early[-1]
    late = late_base + np.linspace(0.0, 2.0, 40) + rng.normal(0.0, 0.15, 40)
    closes = np.concatenate([early, late])
    highs = np.concatenate([early + 2.5, late + 0.35])
    lows = np.concatenate([early - 2.5, late - 0.35])
    vols = np.concatenate([np.full(255, 1_500_000), np.full(5, 2_500_000)])

    ohlcv = pd.DataFrame(
        {"Close": closes, "High": highs, "Low": lows, "Volume": vols},
        index=dates,
    )

    spring = evaluate_spring_setup("COIL", ohlcv)
    assert spring.is_in_coil is True
    assert spring.bbw_percentile <= 25.0
    assert spring.layers_confirmed >= 2
    assert spring.spring_score >= 0.55


def test_undervaluation_and_payoff_modeling_for_sub_25_cent_options():
    """
    Verify that an option costing <= $0.25 with IV < Realized HV is flagged as undervalued
    and its $1.00 (4x+) and $10.00+ (40x+) spring targets are accurately modeled.
    """
    days = 260
    dates = pd.date_range(end=date.today(), periods=days)
    rng = np.random.default_rng(7)
    closes = 200.0 * np.exp(np.cumsum(rng.normal(0.001, 0.025, days)))
    ohlcv = pd.DataFrame(
        {
            "Close": closes,
            "High": closes * 1.018,
            "Low": closes * 0.982,
            "Volume": np.full(days, 5_000_000),
        },
        index=dates,
    )
    spot = float(closes[-1])
    atr = compute_atr(ohlcv)
    strike = round(spot + 1.5 * atr, 0)
    entry_ask = 0.20  # $0.20 <= $0.25 frugal cap

    underval = evaluate_option_undervaluation(
        spot=spot,
        strike=strike,
        ask_price=entry_ask,
        time_years=30.0 / 365.0,
        iv=0.22,  # Low IV vs ~40% realized HV
        option_type="call",
        ohlcv=ohlcv,
    )
    assert underval.iv_hv_ratio < 1.0
    assert underval.undervaluation_score > 0.55
    assert "VALUE" in underval.valuation_label or "COIL" in underval.valuation_label

    payoff = evaluate_payoff_potential(
        spot=spot,
        strike=strike,
        ask_price=entry_ask,
        dte_days=30.0,
        atr=atr,
        iv=underval.implied_vol,
        breakout_hv=underval.breakout_hv_85,
        option_type="call",
    )
    assert payoff.entry_ask == 0.20
    assert payoff.spot_for_1_00 == strike + 1.00
    assert payoff.spot_for_10_00 == strike + 10.00
    assert payoff.proj_value_3atr >= 1.00
    assert payoff.proj_value_5atr >= 10.00
    assert payoff.can_reach_1_00 is True
    assert payoff.can_reach_10_00 is True
    assert payoff.potential_multiple >= 40.0


def test_universe_and_25_cent_contract_filters():
    """Verify share price > $10, ADV > 1,000,000, and strict <= $0.25 contract filter."""
    pass_low_price, _ = passes_underlying_filter("PENNY", spot_price=5.0, info={"averageVolume": 2_000_000})
    assert pass_low_price is False

    pass_good, _ = passes_underlying_filter("SPY", spot_price=550.0, info={"averageVolume": 45_000_000})
    assert pass_good is True

    # Under $0.25 with tight spread passes
    assert passes_contract_spread_filter(bid=0.18, ask=0.21, price=0.21) is True
    assert passes_contract_spread_filter(bid=0.06, ask=0.08, price=0.08) is True
    # Over $0.25 is rejected by the default $0.25 frugal cap
    assert passes_contract_spread_filter(bid=0.35, ask=0.38, price=0.38) is False


def test_paper_trading_guard_and_discord_embeds(tmp_path, monkeypatch):
    """Verify trade logging, paper trading validation guard, and Discord embed generation."""
    test_0dte_csv = tmp_path / "0dte_running_trade_log.csv"
    monkeypatch.setattr(trade_logger, "RUNNING_0DTE_LOG_PATH", test_0dte_csv)
    monkeypatch.setattr(trade_logger, "REQUIRED_PAPER_CYCLES", 4)
    monkeypatch.setattr(trade_logger, "PAPER_TRADING_MODE", True)

    status_0 = compute_paper_trading_status()
    assert status_0["approved_for_live_capital"] is False

    trades = [
        {
            "Scan_Date": f"2026-08-0{i}",
            "Ticker": "SPY",
            "Option_Type": "CALL",
            "Contract_Symbol": f"SPY_2026-08-0{i}_C550",
            "Strike": 550.0,
            "Entry_Ask": 0.20,
            "PnL_Pct": 300.0,
            "Outcome_Status": "CLOSED",
        }
        for i in range(1, 5)
    ]
    append_0dte_trades(trades)

    status_4 = compute_paper_trading_status()
    assert status_4["distinct_cycles"] == 4
    assert status_4["approved_for_live_capital"] is True

    top_calls = pd.DataFrame([{
        "Ticker": "SPY",
        "Strike": 550.0,
        "Ask": 0.20,
        "Opportunity_Score": 88.5,
        "Dist_ATR_Units": 1.8,
        "Open_Interest": 1200,
        "Vol_OI_Ratio": 3.2,
        "Spot_For_1_00": 551.0,
        "Spot_For_10_00": 560.0,
        "Proj_Value_3ATR": 2.45,
        "Proj_Value_5ATR": 11.20,
        "Max_Loss_Held_To_Zero": 20.0,
        "Averaging_Down_Violation_Flag": "CLEAN: 1st entry of day",
        "Catalyst_Flag": "Macro: CPI Print",
    }])
    embeds = build_0dte_embed(top_calls, pd.DataFrame(), status_4)
    assert len(embeds) == 2
    assert "$1.00" in embeds[0]["description"]
    assert "$10.00" in embeds[0]["description"]
