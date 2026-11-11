"""
market_data.py - Pluggable market data provider & multi-source universe scanner.

Combines:
1. options-ticker-universe's rate-limited MarketDataProvider (YFinanceProvider + LicensedMarketDataStub)
2. Frugal_Trader's MarketScanner (Finviz Quality/Value/Profitability filter, Liquidity Mandate, 13F Superinvestor holdings, and NASDAQ FTP universe)
3. Batch historical OHLCV downloader with in-memory session caching to avoid redundant API hits.
"""

import os
import math
import time
import random
import logging
import urllib.request
from io import StringIO
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from pyrate_limiter import Rate, Limiter, Duration
import yfinance as yf
from tqdm import tqdm

logger = logging.getLogger(__name__)

# --- Rate limiting (prevents YFRateLimitError & silent throttling) ---
YF_REQUESTS_PER_SECOND = float(os.getenv("SCANNER_YF_RPS", "4.0"))
_rate = Rate(max(1, int(YF_REQUESTS_PER_SECOND * 10)), Duration.SECOND * 10)
RATE_LIMITER = Limiter(_rate)


def throttle():
    """Block until the next request slot is free (waits up to 30s)."""
    try:
        RATE_LIMITER.try_acquire("yfinance", timeout=30)
    except Exception:
        time.sleep(0.25)


def with_backoff(max_attempts: int = 4, base_delay: float = 1.5, max_delay: float = 20.0):
    """Exponential backoff decorator for transient API/network hiccups."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    msg = str(e).lower()
                    transient = any(
                        w in msg
                        for w in ["rate limit", "too many requests", "429", "timeout", "connection"]
                    )
                    if not transient or attempt >= max_attempts:
                        raise
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, delay * 0.25)
                    time.sleep(delay)
        return wrapper
    return decorator


class MarketDataProvider(ABC):
    """Abstract interface for options and underlying market data."""

    @abstractmethod
    def get_spot_price(self, symbol: str) -> Optional[float]:
        """Fetch current underlying spot/close price."""
        pass

    @abstractmethod
    def get_options_expirations(self, symbol: str) -> List[str]:
        """Return sorted list of expiration dates (YYYY-MM-DD)."""
        pass

    @abstractmethod
    def get_option_chain(self, symbol: str, expiration: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return (calls_df, puts_df) for the requested expiration."""
        pass

    @abstractmethod
    def get_historical_ohlcv(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """Return OHLCV DataFrame with Datetime index."""
        pass

    @abstractmethod
    def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        """Return metadata such as sharesShort, averageVolume, sector, etc."""
        pass


class YFinanceProvider(MarketDataProvider):
    """
    Production default provider using yfinance with rate-limiting,
    exponential backoff, and in-memory OHLCV/info caching.
    """

    def __init__(self):
        self.risk_free_rate = float(os.getenv("SCANNER_RISK_FREE_RATE", "0.045"))
        self._ohlcv_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
        self._info_cache: Dict[str, Dict[str, Any]] = {}
        self._exp_cache: Dict[str, List[str]] = {}

    def preload_bulk_ohlcv(self, bulk_data: Dict[str, pd.DataFrame], period: str = "1y") -> None:
        """Seed internal OHLCV cache from bulk downloader."""
        for sym, df in bulk_data.items():
            if df is not None and not df.empty:
                self._ohlcv_cache[(sym, period)] = df

    @with_backoff()
    def get_spot_price(self, symbol: str) -> Optional[float]:
        # Check cached OHLCV first
        for (sym, _), df in self._ohlcv_cache.items():
            if sym == symbol and not df.empty and "Close" in df:
                val = float(df["Close"].iloc[-1])
                if val > 0 and not math.isnan(val):
                    return val

        throttle()
        ticker = yf.Ticker(symbol)
        try:
            price = getattr(ticker.fast_info, "last_price", None)
            if price and not math.isnan(price) and price > 0:
                return float(price)
        except Exception:
            pass

        hist = self.get_historical_ohlcv(symbol, period="5d")
        if hist is not None and not hist.empty and "Close" in hist:
            return float(hist["Close"].iloc[-1])
        return None

    @with_backoff()
    def get_options_expirations(self, symbol: str) -> List[str]:
        if symbol in self._exp_cache:
            return self._exp_cache[symbol]
        throttle()
        ticker = yf.Ticker(symbol)
        exps = ticker.options
        res = sorted(list(exps)) if exps else []
        self._exp_cache[symbol] = res
        return res

    @with_backoff()
    def get_option_chain(self, symbol: str, expiration: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        throttle()
        ticker = yf.Ticker(symbol)
        chain = ticker.option_chain(expiration)
        calls = chain.calls if chain and chain.calls is not None else pd.DataFrame()
        puts = chain.puts if chain and chain.puts is not None else pd.DataFrame()
        return calls, puts

    @with_backoff()
    def get_historical_ohlcv(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        cache_key = (symbol, period)
        if cache_key in self._ohlcv_cache:
            return self._ohlcv_cache[cache_key]
        throttle()
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist is not None and not hist.empty:
            self._ohlcv_cache[cache_key] = hist
        return hist

    @with_backoff()
    def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        if symbol in self._info_cache:
            return self._info_cache[symbol]
        throttle()
        ticker = yf.Ticker(symbol)
        info_dict: Dict[str, Any] = {}
        try:
            fast = getattr(ticker, "fast_info", None)
            if fast:
                for k in ["three_month_average_volume", "ten_day_average_volume", "last_volume", "shares", "year_high", "year_low"]:
                    v = getattr(fast, k, None)
                    if v is not None:
                        info_dict[k] = v
                if "three_month_average_volume" in info_dict:
                    info_dict["averageVolume"] = info_dict["three_month_average_volume"]
                if "ten_day_average_volume" in info_dict:
                    info_dict["averageVolume10days"] = info_dict["ten_day_average_volume"]
        except Exception:
            pass

        try:
            full_info = ticker.info
            if full_info and isinstance(full_info, dict):
                info_dict.update(full_info)
        except Exception as e:
            logger.debug(f"Error fetching info for {symbol}: {e}")

        self._info_cache[symbol] = info_dict
        return info_dict


class LicensedMarketDataStub(MarketDataProvider):
    """
    Interface stub for licensed institutional feeds (Polygon.io, Tradier, ThetaData, Schwab API).
    Falls back seamlessly to YFinanceProvider when credentials are not supplied.
    """

    def __init__(self, provider_name: str = "polygon"):
        self.provider_name = provider_name
        self.api_key = os.getenv(f"{provider_name.upper()}_API_KEY", "")
        self._fallback = YFinanceProvider()

    def get_spot_price(self, symbol: str) -> Optional[float]:
        if not self.api_key:
            return self._fallback.get_spot_price(symbol)
        raise NotImplementedError(f"Licensed connector for {self.provider_name} ready for API endpoint wiring.")

    def get_options_expirations(self, symbol: str) -> List[str]:
        if not self.api_key:
            return self._fallback.get_options_expirations(symbol)
        raise NotImplementedError(f"Licensed connector for {self.provider_name} ready for API endpoint wiring.")

    def get_option_chain(self, symbol: str, expiration: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if not self.api_key:
            return self._fallback.get_option_chain(symbol, expiration)
        raise NotImplementedError(f"Licensed connector for {self.provider_name} ready for API endpoint wiring.")

    def get_historical_ohlcv(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        if not self.api_key:
            return self._fallback.get_historical_ohlcv(symbol, period)
        raise NotImplementedError(f"Licensed connector for {self.provider_name} ready for API endpoint wiring.")

    def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback.get_ticker_info(symbol)
        raise NotImplementedError(f"Licensed connector for {self.provider_name} ready for API endpoint wiring.")


def get_market_data_provider() -> MarketDataProvider:
    """Factory function returning the configured market data provider."""
    provider_type = os.getenv("MARKET_DATA_PROVIDER", "yfinance").lower()
    if provider_type == "yfinance":
        return YFinanceProvider()
    elif provider_type in ["polygon", "tradier", "thetadata", "schwab"]:
        return LicensedMarketDataStub(provider_name=provider_type)
    else:
        return YFinanceProvider()


class MarketScanner:
    """
    Multi-source Universe Scanner combining Frugal_Trader's Layer 1 screens
    (Curated Liquid Universe, Finviz Quality/Value, Liquidity Mandate, 13F Superinvestors, NASDAQ FTP).
    """

    def get_universe(self, universe_type: str = "default") -> List[str]:
        utype = universe_type.strip().lower()
        if utype == "finviz":
            return self.get_finviz_quality_universe()
        elif utype == "liquidity":
            return self.get_liquidity_mandate_universe()
        elif utype == "13f":
            return self.get_13f_universe()
        elif utype == "nasdaq":
            return self.get_nasdaq_exchange_tickers()
        else:
            return self.get_default_universe()

    def get_default_universe(self, local_list: str = "options_tickers.txt") -> List[str]:
        if os.path.exists(local_list):
            with open(local_list, "r") as f:
                tickers = [
                    line.strip().upper()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]
                if tickers:
                    return list(dict.fromkeys(tickers))
        return ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "COIN", "PLTR", "SMCI", "MARA"]

    def get_finviz_quality_universe(self) -> List[str]:
        """Frugal_Trader Layer 1: Optionable + Volume > 1M + Value & Profitability."""
        try:
            from finvizfinance.screener.overview import Overview
            foverview = Overview()
            filters = {
                "Option/Short": "Optionable",
                "Average Volume": "Over 1M",
                "P/E": "Under 40",
                "Forward P/E": "Under 35",
                "Debt/Equity": "Under 1",
                "Operating Margin": "Over 5%",
            }
            foverview.set_filter(filters_dict=filters)
            df = foverview.screener_view(verbose=0)
            if df is not None and not df.empty and "Ticker" in df.columns:
                return df["Ticker"].tolist()
        except Exception as e:
            logger.warning(f"Finviz quality universe fallback triggered: {e}")
        return self.get_default_universe()

    def get_liquidity_mandate_universe(self) -> List[str]:
        """Frugal_Trader Priority 1: All optionable stocks with Average Volume > 1M."""
        try:
            from finvizfinance.screener.overview import Overview
            foverview = Overview()
            filters = {
                "Option/Short": "Optionable",
                "Average Volume": "Over 1M",
            }
            foverview.set_filter(filters_dict=filters)
            df = foverview.screener_view(verbose=0)
            if df is not None and not df.empty and "Ticker" in df.columns:
                return df["Ticker"].tolist()
        except Exception as e:
            logger.warning(f"Finviz liquidity mandate fallback triggered: {e}")
        return self.get_default_universe()

    def get_13f_universe(self) -> List[str]:
        """Loads 13F superinvestor holdings if present, else defaults to curated list."""
        universe_file = Path("data/13f_universe.txt")
        if universe_file.exists():
            with open(universe_file, "r") as f:
                tickers = [line.strip() for line in f if line.strip()]
            if tickers:
                return tickers
        return self.get_default_universe()

    def get_nasdaq_exchange_tickers(self) -> List[str]:
        """Fetches full optionable/exchange symbol directory from NASDAQ FTP."""
        all_tickers = []
        urls_and_columns = {"nasdaqlisted.txt": "Symbol", "otherlisted.txt": "ACT Symbol"}
        for filename, symbol_col in urls_and_columns.items():
            try:
                url = f"ftp://ftp.nasdaqtrader.com/symboldirectory/{filename}"
                with urllib.request.urlopen(url, timeout=15) as response:
                    content = response.read().decode("utf-8")
                    data = StringIO(content)
                    df = pd.read_csv(data, sep="|", dtype={symbol_col: str}, skipfooter=1, engine="python")
                    df.dropna(subset=[symbol_col], inplace=True)
                    if "ETF" not in df.columns:
                        df["ETF"] = "N"
                    if "Test Issue" not in df.columns:
                        df["Test Issue"] = "N"
                    valid_symbol_mask = df[symbol_col].str.match(r"^[A-Z\.\-]+$")
                    df_filtered = df[(df["Test Issue"] == "N") & (valid_symbol_mask.fillna(False))]
                    all_tickers.extend(df_filtered[symbol_col].tolist())
            except Exception as e:
                logger.warning(f"Could not fetch {filename}: {e}")
        if not all_tickers:
            return self.get_default_universe()
        return sorted(list(set(all_tickers)))


def fetch_bulk_data(
    tickers: List[str],
    period: str = "1y",
    batch_size: int = 40,
) -> Dict[str, pd.DataFrame]:
    """
    Downloads historical OHLCV data for a list of tickers in batches (Frugal_Trader pipeline).
    """
    all_ticker_data: Dict[str, pd.DataFrame] = {}
    if not tickers:
        return all_ticker_data

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            throttle()
            data = yf.download(batch, period=period, auto_adjust=False, group_by="ticker", threads=False, progress=False)
            if data is not None and not data.empty:
                if len(batch) == 1 and not isinstance(data.columns, pd.MultiIndex):
                    df = data.copy().dropna()
                    if not df.empty:
                        all_ticker_data[batch[0]] = df
                else:
                    top_cols = set(data.columns.get_level_values(0))
                    for ticker in batch:
                        if ticker in top_cols:
                            df = data[ticker].copy().dropna()
                            if not df.empty:
                                all_ticker_data[ticker] = df
        except Exception as e:
            logger.debug(f"Batch download fallback for batch starting at {i}: {e}")

    return all_ticker_data
