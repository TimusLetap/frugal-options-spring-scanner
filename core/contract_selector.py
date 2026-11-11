import pandas as pd
from typing import Optional


class ContractSelector:
    def __init__(self, config: dict):
        self.min_delta = config["filters"]["min_delta"]
        self.max_delta = config["filters"]["max_delta"]
        self.max_spread = config["filters"]["max_spread"]
        self.max_premium = config.get("pricing", {}).get("max_premium", 0.25)

    def select_best_contract(self, chain_df: pd.DataFrame, direction: str) -> Optional[dict]:
        """
        Filters option chain for contracts matching target Delta and tight bid-ask spreads.
        """
        call_put = "CALL" if direction.upper() == "BULLISH" else "PUT"
        candidates = chain_df[
            (chain_df["type"] == call_put)
            & (chain_df["delta"].abs() >= self.min_delta)
            & (chain_df["delta"].abs() <= self.max_delta)
            & ((chain_df["ask"] - chain_df["bid"]) <= self.max_spread)
        ]
        if candidates.empty:
            return None
        return candidates.sort_values(by="volume", ascending=False).iloc[0].to_dict()

    def select_frugal_spring_contract(
        self,
        chain_df: pd.DataFrame,
        direction: str,
        max_premium: Optional[float] = None,
    ) -> Optional[dict]:
        """
        Filters option chain for <= $0.25 spring contracts with tight spreads and high volume.
        """
        cap = max_premium if max_premium is not None else self.max_premium
        call_put = "CALL" if direction.upper() == "BULLISH" else "PUT"
        candidates = chain_df[
            (chain_df["type"].str.upper() == call_put)
            & (chain_df["ask"] > 0.0)
            & (chain_df["ask"] <= cap)
            & ((chain_df["ask"] - chain_df["bid"]) <= self.max_spread)
        ]
        if candidates.empty:
            return None
        return candidates.sort_values(by="volume", ascending=False).iloc[0].to_dict()
