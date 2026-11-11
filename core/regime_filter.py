import datetime


class RegimeFilter:
    def __init__(self, config: dict):
        self.entry_start = datetime.time.fromisoformat(config["schedule"]["entry_start_et"])
        self.entry_end = datetime.time.fromisoformat(config["schedule"]["entry_end_et"])
        self.midday_start = datetime.time.fromisoformat(config["schedule"]["midday_blackout_start_et"])
        self.midday_end = datetime.time.fromisoformat(config["schedule"]["midday_blackout_end_et"])
        self.terminal_cutoff = datetime.time.fromisoformat(config["schedule"]["terminal_cutoff_et"])
        self.max_exhaustion = config["filters"]["max_expected_move_exhaustion_pct"]

    def can_open_entry(self, current_time: datetime.time) -> bool:
        if current_time < self.entry_start or current_time > self.entry_end:
            return False
        if self.midday_start <= current_time <= self.midday_end:
            return False
        return True

    def is_terminal_cliff(self, current_time: datetime.time) -> bool:
        return current_time >= self.terminal_cutoff

    def check_expected_move(self, session_range: float, straddle_move: float) -> bool:
        if straddle_move <= 0:
            return False
        return (session_range / straddle_move) < self.max_exhaustion
