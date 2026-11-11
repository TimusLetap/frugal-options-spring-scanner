import pytest
from core.risk_manager import RiskManager


def test_blocks_averaging_down(config):
    """Buying a second contract on an active underlying must raise PermissionError."""
    rm = RiskManager(settled_cash=1000.0, config=config)
    rm.register_entry("SPY")

    with pytest.raises(PermissionError, match="Averaging down is prohibited"):
        rm.validate_new_order(underlying_symbol="SPY", contract_price=0.20, qty=1)


def test_enforces_settled_cash_cap(config):
    """Order outlay exceeding 15% of settled cash must raise ValueError."""
    rm = RiskManager(settled_cash=1000.0, config=config)  # max trade = $150
    assert rm.validate_new_order(underlying_symbol="QQQ", contract_price=0.25, qty=4) is True  # $100 <= $150

    with pytest.raises(ValueError, match="exceeds cap"):
        rm.validate_new_order(underlying_symbol="QQQ", contract_price=0.25, qty=10)  # $250 > $150


def test_allows_reentry_after_exit(config):
    """Once register_exit is called, a new entry on that underlying is allowed."""
    rm = RiskManager(settled_cash=1000.0, config=config)
    rm.register_entry("SPY")
    rm.register_exit("SPY")
    assert rm.validate_new_order(underlying_symbol="SPY", contract_price=0.20, qty=1) is True
