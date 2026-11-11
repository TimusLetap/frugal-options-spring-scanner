"""
core/conviction_tracker.py - Multi-session persistence tracking from Frugal_Trader.
Tracks how many consecutive scan sessions a ticker/contract spring signal persists.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


class ConvictionTracker:
    """Tracks the persistence of spring trading opportunities over time."""

    def __init__(self, tracker_path: str = "data/history/conviction_tracker.json"):
        self.tracker_path = Path(tracker_path)
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        self.previous_trades = self._load_previous_trades()

    def _load_previous_trades(self) -> Dict[str, Dict[str, Any]]:
        if not self.tracker_path.exists():
            return {}
        try:
            with self.tracker_path.open("r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def update_persistence(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Increments Run_Days / Persistence_Count for signals that persist across runs.
        """
        current_map: Dict[str, Dict[str, Any]] = {}
        for t in trades:
            ticker = t.get("Ticker", "")
            opt_type = t.get("Option_Type") or t.get("Type", "CALL")
            strike = t.get("Strike", 0)
            key = f"{ticker}_{opt_type}_{strike}"
            prev_runs = int(self.previous_trades.get(key, {}).get("Persistence_Count", 0))
            t["Persistence_Count"] = prev_runs + 1
            current_map[key] = t

        try:
            with self.tracker_path.open("w") as f:
                json.dump(current_map, f, indent=2, default=str)
        except Exception:
            pass

        return trades
