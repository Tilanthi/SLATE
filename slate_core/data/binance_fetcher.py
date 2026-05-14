"""
Unified Binance Data Fetcher
Consolidates all Binance API data fetching to eliminate duplication
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Literal

from ..config.constants import (
    BINANCE_API_KLINES,
    BINANCE_FUTURES_API_BASE,
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_FILE_PATTERN
)


class BinanceFetcher:
    """Unified Binance data fetching with caching support."""

    def __init__(self, use_cache: bool = True, cache_dir: str = DEFAULT_CACHE_DIR):
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_futures: bool = False
    ) -> pd.DataFrame:
        """
        Fetch historical candle data from Binance.

        Parameters:
        - symbol: Trading pair (e.g., "BTCUSDT")
        - interval: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d, etc.)
        - days: Number of days to fetch (used if start_date not provided)
        - start_date: Specific start date
        - end_date: Specific end date
        - use_futures: Use futures API instead of spot

        Returns:
        - DataFrame with OHLCV + taker buy/sell volume
        """
        if start_date is None:
            end_date = end_date or datetime.now()
            start_date = end_date - timedelta(days=days)

        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)

        # Check cache first
        cache_key = f"{symbol}_{interval}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if self.use_cache:
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return cached

        # Fetch from API
        base_url = BINANCE_FUTURES_API_BASE if use_futures else BINANCE_API_KLINES
        endpoint = f"{BINANCE_FUTURES_API_BASE}/fapi/v1/klines" if use_futures else BINANCE_API_KLINES

        df = self._fetch_all_klines(endpoint, symbol, interval, start_ts, end_ts)

        if self.use_cache and df is not None and len(df) > 0:
            self._save_to_cache(cache_key, df)

        return df

    def _fetch_all_klines(
        self,
        endpoint: str,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int
    ) -> Optional[pd.DataFrame]:
        """Fetch all klines with pagination."""
        all_klines = []
        current_start = start_ts

        while current_start < end_ts:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ts,
                "limit": 1000
            }

            try:
                response = requests.get(endpoint, params=params, timeout=10)
                response.raise_for_status()
                klines = response.json()

                if not klines:
                    break

                all_klines.extend(klines)
                current_start = klines[-1][0] + 1

            except Exception as e:
                print(f"Error fetching data: {e}")
                break

        if not all_klines:
            return None

        return self._klines_to_dataframe(all_klines)

    def _klines_to_dataframe(self, klines: list) -> pd.DataFrame:
        """Convert raw klines to DataFrame."""
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')

        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df.sort_index()

    def _load_from_cache(self, key: str) -> Optional[pd.DataFrame]:
        """Load data from cache if available."""
        cache_path = self.cache_dir / f"{key}.csv"
        if cache_path.exists():
            try:
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                print(f"Loaded from cache: {cache_path.name}")
                return df
            except Exception as e:
                print(f"Cache read error: {e}")
        return None

    def _save_to_cache(self, key: str, df: pd.DataFrame):
        """Save data to cache."""
        cache_path = self.cache_dir / f"{key}.csv"
        try:
            df.to_csv(cache_path)
        except Exception as e:
            print(f"Cache write error: {e}")

    def fetch_weeks(self, symbol: str = "BTCUSDT", interval: str = "1h",
                    weeks_back: int = 1) -> pd.DataFrame:
        """Fetch N weeks of data."""
        end_date = datetime.now() - timedelta(weeks=7 * (weeks_back - 1))
        start_date = end_date - timedelta(weeks=7)
        return self.fetch_klines(symbol, interval, start_date=start_date, end_date=end_date)

    def fetch_months(self, symbol: str = "BTCUSDT", interval: str = "1h",
                     months_back: int = 1) -> pd.DataFrame:
        """Fetch N months of data."""
        end_date = datetime.now() - timedelta(days=30 * (months_back - 1))
        start_date = end_date - timedelta(days=30)
        return self.fetch_klines(symbol, interval, start_date=start_date, end_date=end_date)

    def fetch_days(self, symbol: str = "BTCUSDT", interval: str = "1h",
                   days_back: int = 1) -> pd.DataFrame:
        """Fetch N days of data."""
        end_date = datetime.now() - timedelta(days=days_back - 1)
        start_date = end_date - timedelta(days=days_back)
        return self.fetch_klines(symbol, interval, start_date=start_date, end_date=end_date)


# Convenience functions for backward compatibility
def fetch_binance_data(symbol="BTCUSDT", interval="1h", days=180, use_cache=True) -> pd.DataFrame:
    """Fetch historical data from Binance (backward compatible)."""
    fetcher = BinanceFetcher(use_cache=use_cache)
    return fetcher.fetch_klines(symbol=symbol, interval=interval, days=days)


def fetch_binance_data_week(symbol="BTCUSDT", interval="1h", weeks_back=1) -> pd.DataFrame:
    """Fetch one week of data (backward compatible)."""
    fetcher = BinanceFetcher()
    return fetcher.fetch_weeks(symbol=symbol, interval=interval, weeks_back=weeks_back)


def fetch_binance_data_month(symbol="BTCUSDT", interval="1h", months_back=1) -> pd.DataFrame:
    """Fetch one month of data (backward compatible)."""
    fetcher = BinanceFetcher()
    return fetcher.fetch_months(symbol=symbol, interval=interval, months_back=months_back)


def fetch_binance_futures_data(symbol="BTCUSDT", interval="1h", days=30) -> pd.DataFrame:
    """Fetch futures data from Binance (backward compatible)."""
    fetcher = BinanceFetcher()
    return fetcher.fetch_klines(symbol=symbol, interval=interval, days=days, use_futures=True)
