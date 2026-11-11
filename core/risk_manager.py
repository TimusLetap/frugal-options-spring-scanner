class RiskManager:
    def __init__(self, settled_cash: float, config: dict):
        self.settled_cash = settled_cash
        self.max_trade_dollars = settled_cash * config["risk"]["max_portfolio_risk_pct"]
        self.allow_averaging = config["risk"]["allow_averaging_down"]
        self.active_positions = set()

    def validate_new_order(self, underlying_symbol: str, contract_price: float, qty: int) -> bool:
        if not self.allow_averaging and underlying_symbol in self.active_positions:
            raise PermissionError(
                f"[GUARDRAIL VIOLATION] Active position in {underlying_symbol} already exists. Averaging down is prohibited."
            )

        total_outlay = contract_price * 100 * qty
        if total_outlay > self.max_trade_dollars:
            raise ValueError(
                f"[RISK BREACH] Trade outlay ${total_outlay:.2f} exceeds cap of ${self.max_trade_dollars:.2f}."
            )
        return True

    def register_entry(self, underlying_symbol: str):
        self.active_positions.add(underlying_symbol)

    def register_exit(self, underlying_symbol: str):
        self.active_positions.discard(underlying_symbol)
