import pandas as pd
from core.contract_selector import ContractSelector


def _sample_chain() -> pd.DataFrame:
    return pd.DataFrame({
        "type":   ["CALL", "CALL", "CALL", "CALL"],
        "delta":  [ 0.50,   0.40,   0.50,   0.60],
        "bid":    [ 0.20,   0.20,   0.15,   0.20],
        "ask":    [ 0.23,   0.23,   0.25,   0.23],  # row-2: spread=0.10 -> reject
        "volume": [ 100,    200,    300,    400],
    })


def test_filters_exclude_bad_delta_and_spread(config):
    """Contracts with delta < 0.45 or spread > $0.05 must be excluded."""
    selector = ContractSelector(config)
    result = selector.select_best_contract(_sample_chain(), "BULLISH")

    assert result is not None
    assert result["delta"] == 0.50
    assert result["ask"] - result["bid"] <= 0.05


def test_frugal_spring_selector_enforces_25_cent_cap(config):
    """Frugal spring contract selector must reject contracts costing > $0.25."""
    selector = ContractSelector(config)
    chain = pd.DataFrame({
        "type":   ["CALL", "CALL"],
        "delta":  [ 0.20,   0.35],
        "bid":    [ 0.19,   0.40],
        "ask":    [ 0.22,   0.43],
        "volume": [ 500,   1200],
    })
    result = selector.select_frugal_spring_contract(chain, "BULLISH")
    assert result is not None
    assert result["ask"] <= 0.25
    assert result["ask"] == 0.22


def test_bearish_selects_puts(config):
    """Direction='BEARISH' should filter for PUT contracts."""
    selector = ContractSelector(config)
    chain = pd.DataFrame({
        "type":   ["CALL", "PUT"],
        "delta":  [ 0.50, -0.48],
        "bid":    [ 0.20,  0.18],
        "ask":    [ 0.23,  0.22],
        "volume": [ 500,   800],
    })
    result = selector.select_best_contract(chain, "BEARISH")
    assert result is not None
    assert result["type"] == "PUT"
