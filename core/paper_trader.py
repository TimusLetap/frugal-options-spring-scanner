"""
core/paper_trader.py - Automated Alpaca Paper Trading Execution from Frugal_Trader.
Submits limit orders for <= $0.25 options spring candidates when ALPACA_API_KEY is configured.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PaperTrader:
    """Handles automated paper execution of <= $0.25 options spring trades on Alpaca."""

    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.trading_client = None
        if self.api_key and self.secret_key:
            try:
                from alpaca.trading.client import TradingClient
                self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
            except Exception as e:
                logger.warning(f"Could not initialize Alpaca TradingClient: {e}")

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self.trading_client:
            return None
        try:
            account = self.trading_client.get_account()
            return {
                "portfolio_value": float(account.portfolio_value),
                "cash": float(account.cash),
            }
        except Exception as e:
            logger.warning(f"Failed to query Alpaca account info: {e}")
            return None

    def place_spring_option_order(self, trade: Dict[str, Any], quantity: int = 1) -> bool:
        """Submits a limit BUY order for a <= $0.25 spring option contract."""
        if not self.trading_client:
            logger.info("Alpaca credentials not set; skipping live broker order submission.")
            return False
        try:
            from alpaca.trading.requests import LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            ticker = str(trade.get("Ticker", "")).replace("-", "").replace(".", "")
            exp = str(trade.get("Expiration_Date") or trade.get("Expiration", ""))
            opt_type = str(trade.get("Option_Type") or trade.get("Type", "CALL"))[0].upper()
            strike = float(trade.get("Strike", 0))
            ask = float(trade.get("Ask") or trade.get("Entry_Ask") or trade.get("Mid", 0.25))

            if ask <= 0 or ask > 0.25:
                logger.warning(f"Refusing order for {ticker}: premium ${ask:.2f} exceeds $0.25 frugal cap.")
                return False

            strike_str = f"{int(round(strike * 1000)):08d}"
            option_symbol = f"{ticker}{exp[2:].replace('-', '')}{opt_type}{strike_str}"

            req = LimitOrderRequest(
                symbol=option_symbol,
                qty=quantity,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=round(ask, 2),
            )
            placed = self.trading_client.submit_order(order_data=req)
            logger.info(f"Submitted Alpaca paper order for {option_symbol} @ ${ask:.2f} (ID: {placed.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to submit Alpaca order: {e}")
            return False
