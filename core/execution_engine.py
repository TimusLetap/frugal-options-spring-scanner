from typing import Any


class ExecutionEngine:
    def __init__(self, broker_client: Any, config: dict):
        self.client = broker_client
        self.sl_pct = config["risk"]["stop_loss_pct"]
        self.tp_pct = config["risk"]["take_profit_pct"]
        self.tier1_target = config["risk"].get("take_profit_tier_1_price", 1.00)
        self.tier2_target = config["risk"].get("take_profit_tier_2_price", 10.00)

    def submit_bracket_entry(self, symbol: str, bid: float, ask: float, qty: int) -> dict:
        entry_mid = round((bid + ask) / 2, 2)
        stop_price = round(entry_mid * (1 - self.sl_pct), 2)
        profit_price = round(entry_mid * (1 + self.tp_pct), 2)

        order_packet = {
            "symbol": symbol,
            "qty": qty,
            "entry_limit": entry_mid,
            "bracket": {
                "take_profit_limit": profit_price,
                "stop_loss_trigger": stop_price,
                "spring_tier_1_target": self.tier1_target,
                "spring_tier_2_target": self.tier2_target,
            },
        }
        return self.client.send_oco_order(order_packet)

    def enforce_terminal_liquidation(self, open_orders: list[dict]) -> None:
        for order in open_orders:
            self.client.cancel_all_and_close(order["symbol"])
