"""
Historical Data Fetcher

Fetches historical market data from exchanges for backtesting.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from ..connectors.base import ExchangeConnector, Candle
from ..config import get_config

logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """
    Fetches historical market data from exchanges.

    Features:
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Chunked fetching for large date ranges
    - Data validation and cleaning
    """

    def __init__(self):
        """Initialize historical data fetcher."""
        self.config = get_config()
        # Create default connector for simple access
        from ..connectors.binance import BinanceConnector
        self.default_connector = BinanceConnector()

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent candles for a symbol (simple interface for engine).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d, etc.)
            limit: Number of candles to fetch

        Returns:
            List of candles as dictionaries
        """
        try:
            candles = await self.default_connector.get_candles(
                symbol=symbol,
                interval=timeframe,  # BinanceConnector uses 'interval' not 'timeframe'
                limit=limit,
            )

            # Handle both Candle objects and dictionaries
            result = []
            for c in candles:
                if isinstance(c, dict):
                    # Already a dictionary, ensure it has required fields
                    result.append({
                        "timestamp": c.get("timestamp"),
                        "open": c.get("open", 0),
                        "high": c.get("high", 0),
                        "low": c.get("low", 0),
                        "close": c.get("close", 0),
                        "volume": c.get("volume", 0),
                    })
                else:
                    # Candle object
                    result.append({
                        "timestamp": c.timestamp,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume,
                    })
            return result
        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return []

    async def get_ticker(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Get current ticker for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Ticker data dictionary
        """
        try:
            ticker = await self.default_connector.get_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error getting ticker: {e}")
            return {"price": 0, "volume": 0, "symbol": symbol}

    async def get_orderbook(
        self,
        symbol: str,
        depth: int = 20,
    ) -> Dict[str, Any]:
        """
        Get order book for a symbol.

        Args:
            symbol: Trading symbol
            depth: Order book depth

        Returns:
            Order book data dictionary
        """
        try:
            orderbook = await self.default_connector.get_orderbook(symbol, depth)
            return orderbook
        except Exception as e:
            logger.error(f"Error getting orderbook: {e}")
            return {"bids": [], "asks": [], "symbol": symbol}

    async def fetch_historical_candles(
        self,
        connector: ExchangeConnector,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        limit_per_request: int = 1000,
    ) -> List[Candle]:
        """
        Fetch historical candles for a date range.

        Args:
            connector: Exchange connector
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d, etc.)
            start_date: Start date
            end_date: End date
            limit_per_request: Max candles per request

        Returns:
            List of candles
        """
        all_candles = []
        current_start = start_date

        while current_start < end_date:
            # Calculate end of this chunk
            chunk_end = min(current_start + timedelta(days=30), end_date)

            logger.info(
                f"Fetching candles for {symbol} from {current_start} to {chunk_end}"
            )

            try:
                candles = await self._fetch_candles_chunk(
                    connector=connector,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=current_start,
                    end_date=chunk_end,
                    limit=limit_per_request,
                )

                if candles:
                    all_candles.extend(candles)
                    logger.info(f"Fetched {len(candles)} candles")

                    # Move to next chunk
                    current_start = candles[-1].timestamp + timedelta(minutes=1)
                else:
                    logger.warning(f"No candles returned for chunk starting {current_start}")
                    current_start = chunk_end

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching candles chunk: {e}")
                # Retry with backoff
                await asyncio.sleep(2)
                continue

        # Remove duplicates and sort
        all_candles = self._deduplicate_candles(all_candles)
        all_candles.sort(key=lambda x: x.timestamp)

        logger.info(f"Total candles fetched: {len(all_candles)}")
        return all_candles

    async def _fetch_candles_chunk(
        self,
        connector: ExchangeConnector,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        limit: int,
    ) -> List[Candle]:
        """
        Fetch a chunk of candles.

        Args:
            connector: Exchange connector
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date
            limit: Max candles to fetch

        Returns:
            List of candles
        """
        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                candles = await connector.get_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit,
                    start_time=start_date,
                    end_time=end_date,
                )

                # Validate candles
                validated = self._validate_candles(candles)

                return validated

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}"
                )

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        return []

    def _validate_candles(self, candles: List[Candle]) -> List[Candle]:
        """
        Validate and clean candles.

        Args:
            candles: List of candles to validate

        Returns:
            Validated candles
        """
        validated = []

        for candle in candles:
            # Check for required fields
            if not all([
                candle.open > 0,
                candle.high > 0,
                candle.low > 0,
                candle.close > 0,
                candle.volume >= 0,
            ]):
                logger.warning(f"Invalid candle data: {candle}")
                continue

            # Check OHLC consistency
            if not (candle.low <= candle.open <= candle.high and
                    candle.low <= candle.close <= candle.high):
                logger.warning(f"OHLC inconsistency in candle: {candle}")
                continue

            # Check for reasonable values
            if candle.high < candle.low:
                logger.warning(f"High < Low in candle: {candle}")
                continue

            validated.append(candle)

        return validated

    def _deduplicate_candles(self, candles: List[Candle]) -> List[Candle]:
        """
        Remove duplicate candles.

        Args:
            candles: List of candles

        Returns:
            Deduplicated candles
        """
        seen = set()
        deduplicated = []

        for candle in candles:
            # Create unique key
            key = (candle.exchange, candle.symbol, candle.timestamp, candle.timeframe)

            if key not in seen:
                seen.add(key)
                deduplicated.append(candle)

        return deduplicated

    async def fetch_multiple_symbols(
        self,
        connector: ExchangeConnector,
        symbols: List[str],
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, List[Candle]]:
        """
        Fetch historical candles for multiple symbols concurrently.

        Args:
            connector: Exchange connector
            symbols: List of trading symbols
            timeframe: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping symbol to candles
        """
        results = {}

        # Create tasks for all symbols
        tasks = []
        for symbol in symbols:
            task = self.fetch_historical_candles(
                connector=connector,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )
            tasks.append((symbol, task))

        # Execute concurrently with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests

        async def fetch_with_semaphore(symbol: str, task):
            async with semaphore:
                try:
                    candles = await task
                    return symbol, candles
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {e}")
                    return symbol, []

        # Gather results
        gathered = await asyncio.gather(
            *[fetch_with_semaphore(s, t) for s, t in tasks],
            return_exceptions=True,
        )

        for result in gathered:
            if isinstance(result, Exception):
                logger.error(f"Task error: {result}")
            elif result:
                symbol, candles = result
                results[symbol] = candles

        return results

    async def fetch_ohlcv_data(
        self,
        connector: ExchangeConnector,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, List[float]]:
        """
        Fetch OHLCV data as separate arrays.

        Args:
            connector: Exchange connector
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with open, high, low, close, volume arrays
        """
        candles = await self.fetch_historical_candles(
            connector=connector,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "timestamps": [c.timestamp.timestamp() for c in candles],
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
            "volume": [c.volume for c in candles],
        }

    async def backfill_database(
        self,
        connector: ExchangeConnector,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Backfill database with historical candles.

        Args:
            connector: Exchange connector
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date (default: now)

        Returns:
            Number of candles inserted
        """
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        logger.info(f"Backfilling {symbol} {timeframe} from {start_date} to {end_date}")

        # Fetch candles
        candles = await self.fetch_historical_candles(
            connector=connector,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        # Store in database
        # This would use the database manager to store candles
        # For now, just return count
        logger.info(f"Would backfill {len(candles)} candles")

        return len(candles)

    async def get_available_date_range(
        self,
        connector: ExchangeConnector,
        symbol: str,
        timeframe: str,
    ) -> tuple[datetime, datetime]:
        """
        Get available date range for a symbol.

        Args:
            connector: Exchange connector
            symbol: Trading symbol
            timeframe: Timeframe

        Returns:
            Tuple of (earliest_date, latest_date)
        """
        try:
            # Try to fetch recent candles to see what's available
            candles = await connector.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=1,
            )

            if candles:
                latest = candles[0].timestamp
            else:
                latest = datetime.now(timezone.utc)

            # For earliest, we'd need to query the database or make an API call
            # This is implementation-dependent
            earliest = latest - timedelta(days=365)  # Default to 1 year back

            return earliest, latest

        except Exception as e:
            logger.error(f"Error getting date range: {e}")
            return datetime.now(timezone.utc) - timedelta(days=365), datetime.now(timezone.utc)


class DataQualityChecker:
    """
    Checks data quality for historical market data.
    """

    def __init__(self):
        """Initialize data quality checker."""

    def check_missing_data(
        self,
        candles: List[Candle],
        timeframe: str,
    ) -> List[datetime]:
        """
        Check for missing candles.

        Args:
            candles: List of candles
            timeframe: Timeframe

        Returns:
            List of missing timestamps
        """
        if not candles:
            return []

        # Calculate expected interval in minutes
        timeframe_minutes = self._timeframe_to_minutes(timeframe)

        # Generate expected timestamps
        expected = set()
        current = candles[0].timestamp

        for candle in candles:
            expected.add(candle.timestamp)

        # Check for gaps
        missing = []
        expected_timestamps = set()

        ts = candles[0].timestamp
        end_ts = candles[-1].timestamp

        while ts <= end_ts:
            expected_timestamps.add(ts)
            ts += timedelta(minutes=timeframe_minutes)

        # Find missing
        actual_timestamps = {c.timestamp for c in candles}
        missing_timestamps = expected_timestamps - actual_timestamps

        return sorted(list(missing_timestamps))

    def check_outliers(
        self,
        candles: List[Candle],
        std_dev_threshold: float = 3.0,
    ) -> List[Candle]:
        """
        Check for price outliers using z-score.

        Args:
            candles: List of candles
            std_dev_threshold: Standard deviation threshold

        Returns:
            List of outlier candles
        """
        import numpy as np

        outliers = []

        # Calculate returns
        closes = [c.close for c in candles]
        returns = np.diff(np.log(closes))

        # Calculate z-scores
        mean = np.mean(returns)
        std = np.std(returns)

        for i, candle in enumerate(candles[1:], 1):
            ret = returns[i-1]
            z_score = abs((ret - mean) / std) if std > 0 else 0

            if z_score > std_dev_threshold:
                outliers.append(candle)

        return outliers

    def check_ohlcv_consistency(self, candles: List[Candle]) -> List[str]:
        """
        Check OHLCV data consistency.

        Args:
            candles: List of candles

        Returns:
            List of consistency issues
        """
        issues = []

        for i, candle in enumerate(candles):
            # Check high >= low
            if candle.high < candle.low:
                issues.append(
                    f"Candle {i}: High ({candle.high}) < Low ({candle.low})"
                )

            # Check open within [low, high]
            if not (candle.low <= candle.open <= candle.high):
                issues.append(
                    f"Candle {i}: Open ({candle.open}) not in [Low, High]"
                )

            # Check close within [low, high]
            if not (candle.low <= candle.close <= candle.high):
                issues.append(
                    f"Candle {i}: Close ({candle.close}) not in [Low, High]"
                )

            # Check volume non-negative
            if candle.volume < 0:
                issues.append(f"Candle {i}: Negative volume ({candle.volume})")

            # Check for zero prices
            if candle.open == 0 or candle.high == 0 or candle.low == 0 or candle.close == 0:
                issues.append(f"Candle {i}: Zero price detected")

        return issues

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe to minutes."""
        mapping = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "12h": 720,
            "1d": 1440,
            "3d": 4320,
            "1w": 10080,
        }
        return mapping.get(timeframe, 60)
