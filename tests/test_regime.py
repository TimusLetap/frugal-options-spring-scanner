import datetime
from core.regime_filter import RegimeFilter


def test_midday_blackout_blocks_entry(config):
    """Entries during 11:30-13:15 ET must be blocked."""
    regime = RegimeFilter(config)
    assert regime.can_open_entry(datetime.time(12, 0)) is False
    assert regime.can_open_entry(datetime.time(11, 30)) is False
    assert regime.can_open_entry(datetime.time(13, 15)) is False


def test_prime_window_allows_entry(config):
    """Entries during 09:45-11:15 ET must be allowed."""
    regime = RegimeFilter(config)
    assert regime.can_open_entry(datetime.time(10, 0)) is True
    assert regime.can_open_entry(datetime.time(10, 45)) is True


def test_terminal_cliff(config):
    """is_terminal_cliff must return True at and after 13:15 ET."""
    regime = RegimeFilter(config)
    assert regime.is_terminal_cliff(datetime.time(13, 15)) is True
    assert regime.is_terminal_cliff(datetime.time(13, 30)) is True
    assert regime.is_terminal_cliff(datetime.time(13, 0)) is False


def test_expected_move_exhaustion(config):
    """check_expected_move rejects when session range >= 75% of straddle."""
    regime = RegimeFilter(config)
    assert regime.check_expected_move(session_range=3.0, straddle_move=5.0) is True
    assert regime.check_expected_move(session_range=4.0, straddle_move=5.0) is False
    assert regime.check_expected_move(session_range=1.0, straddle_move=0.0) is False
