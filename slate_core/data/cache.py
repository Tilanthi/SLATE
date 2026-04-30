"""
Timeseries Cache Module

Redis-based caching for market data with TimescaleDB integration.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from ..connectors.base import (
    Ticker,
    OrderBook,
    Trade,
    Candle,
)
from .normalizer import DataNormalizer

logger = logging.getLogger(__name__)


class TimeseriesCache:
    """
    Redis-based timeseries cache for market data.

    Features:
    - High-performance caching
    - Automatic expiration
    - Aggregation support
    - Pub/Sub for real-time updates
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        default_ttl: int = 3600,
    ):
        """
        Initialize timeseries cache.

        Args:
            host: Redis host
            port: Redis port
            password: Redis password
            db: Redis database number
            default_ttl: Default TTL in seconds
        """
        self.default_ttl = default_ttl
        self.normalizer = DataNormalizer()

        # Create connection pool
        self.pool = ConnectionPool(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True,
        )

        self._client: Optional[redis.Redis] = None
        self._pubsub = None

    async def connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            True if successful
        """
        try:
            self._client = redis.Redis(connection_pool=self.pool)
            await self._client.ping()
            logger.info("Connected to Redis timeseries cache")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
        if self._pubsub:
            await self._pubsub.close()

    async def store_ticker(self, ticker: Ticker, ttl: Optional[int] = None) -> bool:
        """
        Store ticker in cache.

        Args:
            ticker: Ticker to store
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        if not self._client:
            return False

        try:
            key = self._ticker_key(ticker.symbol, ticker.exchange)
            data = self._serialize_ticker(ticker)

            await self._client.setex(
                key,
                ttl or self.default_ttl,
                data
            )

            # Publish update
            await self._publish(f"ticker:{ticker.symbol}", data)

            return True
        except Exception as e:
            logger.error(f"Failed to store ticker: {e}")
            return False

    async def get_ticker(self, symbol: str, exchange: str) -> Optional[Ticker]:
        """
        Get ticker from cache.

        Args:
            symbol: Trading symbol
            exchange: Exchange ID

        Returns:
            Cached ticker or None
        """
        if not self._client:
            return None

        try:
            key = self._ticker_key(symbol, exchange)
            data = await self._client.get(key)

            if data:
                return self._deserialize_ticker(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get ticker: {e}")
            return None

    async def store_orderbook(self, orderbook: OrderBook, ttl: Optional[int] = None) -> bool:
        """
        Store orderbook in cache.

        Args:
            orderbook: Orderbook to store
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        if not self._client:
            return False

        try:
            key = self._orderbook_key(orderbook.symbol, orderbook.exchange)
            data = self._serialize_orderbook(orderbook)

            # Store with short TTL (orderbooks change frequently)
            await self._client.setex(
                key,
                ttl or 5,  # 5 second default for orderbooks
                data
            )

            return True
        except Exception as e:
            logger.error(f"Failed to store orderbook: {e}")
            return False

    async def get_orderbook(self, symbol: str, exchange: str) -> Optional[OrderBook]:
        """
        Get orderbook from cache.

        Args:
            symbol: Trading symbol
            exchange: Exchange ID

        Returns:
            Cached orderbook or None
        """
        if not self._client:
            return None

        try:
            key = self._orderbook_key(symbol, exchange)
            data = await self._client.get(key)

            if data:
                return self._deserialize_orderbook(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            return None

    async def store_trade(self, trade: Trade) -> bool:
        """
        Store trade in cache.

        Args:
            trade: Trade to store

        Returns:
            True if successful
        """
        if not self._client:
            return False

        try:
            # Store in timeseries
            key = f"trade:{trade.exchange}:{trade.symbol}"

            # Use Redis sorted set for timeseries
            score = trade.timestamp.timestamp()
            data = self._serialize_trade(trade)

            await self._client.zadd(key, {data: score})

            # Clean old trades (keep last 1000)
            await self._client.zremrangebyrank(key, 0, -1001)

            # Publish update
            await self._publish(f"trade:{trade.symbol}", data)

            return True
        except Exception as e:
            logger.error(f"Failed to store trade: {e}")
            return False

    async def get_recent_trades(
        self, symbol: str, exchange: str, limit: int = 100
    ) -> List[Trade]:
        """
        Get recent trades from cache.

        Args:
            symbol: Trading symbol
            exchange: Exchange ID
            limit: Number of trades to return

        Returns:
            List of recent trades
        """
        if not self._client:
            return []

        try:
            key = f"trade:{exchange}:{symbol}"

            # Get recent trades (highest scores first)
            data_list = await self._client.zrevrange(key, 0, limit - 1)

            trades = []
            for data in data_list:
                trade = self._deserialize_trade(data)
                if trade:
                    trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []

    async def store_candle(self, candle: Candle) -> bool:
        """
        Store candle in cache.

        Args:
            candle: Candle to store

        Returns:
            True if successful
        """
        if not self._client:
            return False

        try:
            key = f"candle:{candle.exchange}:{candle.symbol}:{candle.timeframe}"

            # Use sorted set for timeseries
            score = candle.timestamp.timestamp()
            data = self._serialize_candle(candle)

            await self._client.zadd(key, {data: score})

            # Clean old candles (keep based on timeframe)
            max_candles = self._get_max_candles(candle.timeframe)
            await self._client.zremrangebyrank(key, 0, -max_candles - 1)

            return True
        except Exception as e:
            logger.error(f"Failed to store candle: {e}")
            return False

    async def get_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Candle]:
        """
        Get candles from cache.

        Args:
            symbol: Trading symbol
            exchange: Exchange ID
            timeframe: Timeframe
            limit: Number of candles
            start_time: Start time
            end_time: End time

        Returns:
            List of candles
        """
        if not self._client:
            return []

        try:
            key = f"candle:{exchange}:{symbol}:{timeframe}"

            if start_time and end_time:
                # Get range
                min_score = start_time.timestamp()
                max_score = end_time.timestamp()
                data_list = await self._client.zrangebyscore(
                    key, min_score, max_score, start=0, num=limit
                )
            else:
                # Get recent candles
                data_list = await self._client.zrevrange(key, 0, limit - 1)

            candles = []
            for data in data_list:
                candle = self._deserialize_candle(data)
                if candle:
                    candles.append(candle)

            return candles
        except Exception as e:
            logger.error(f"Failed to get candles: {e}")
            return []

    async def store_ohlcv_aggregate(
        self, symbol: str, timeframe: str, ohlcv: Dict[str, float]
    ) -> bool:
        """
        Store OHLCV aggregate for a symbol.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            ohlcv: Dictionary with open, high, low, close, volume

        Returns:
            True if successful
        """
        if not self._client:
            return False

        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            await self._client.hmset(key, ohlcv)
            await self._client.expire(key, self.default_ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to store OHLCV aggregate: {e}")
            return False

    async def get_ohlcv_aggregate(
        self, symbol: str, timeframe: str
    ) -> Optional[Dict[str, float]]:
        """
        Get OHLCV aggregate for a symbol.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe

        Returns:
            OHLCV dictionary or None
        """
        if not self._client:
            return None

        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            data = await self._client.hgetall(key)

            if data:
                return {k: float(v) for k, v in data.items()}
            return None
        except Exception as e:
            logger.error(f"Failed to get OHLCV aggregate: {e}")
            return None

    async def subscribe_to_updates(
        self, pattern: str, callback
    ) -> None:
        """
        Subscribe to real-time updates.

        Args:
            pattern: Pattern to subscribe to (e.g., "ticker:*")
            callback: Async callback function
        """
        if not self._client:
            return

        try:
            self._pubsub = self._client.pubsub()
            await self._pubsub.subscribe(pattern)

            async for message in self._pubsub.listen():
                if message['type'] == 'message':
                    await callback(message['data'])
        except Exception as e:
            logger.error(f"Subscription error: {e}")

    # ========================================================================
    # SERIALIZATION
    # ========================================================================

    def _serialize_ticker(self, ticker: Ticker) -> str:
        """Serialize ticker to JSON."""
        return json.dumps({
            "exchange": ticker.exchange,
            "symbol": ticker.symbol,
            "timestamp": ticker.timestamp.isoformat(),
            "last_price": str(ticker.last_price),
            "bid_price": str(ticker.bid_price),
            "ask_price": str(ticker.ask_price),
            "bid_size": str(ticker.bid_size),
            "ask_size": str(ticker.ask_size),
            "volume_24h": str(ticker.volume_24h),
            "change_24h": str(ticker.change_24h),
            "change_pct_24h": str(ticker.change_pct_24h),
            "high_24h": str(ticker.high_24h),
            "low_24h": str(ticker.low_24h),
            "open_interest": str(ticker.open_interest) if ticker.open_interest else None,
            "funding_rate": str(ticker.funding_rate) if ticker.funding_rate else None,
        })

    def _deserialize_ticker(self, data: str) -> Optional[Ticker]:
        """Deserialize ticker from JSON."""
        try:
            obj = json.loads(data)
            return Ticker(
                exchange=obj["exchange"],
                symbol=obj["symbol"],
                timestamp=datetime.fromisoformat(obj["timestamp"]),
                last_price=float(obj["last_price"]),
                bid_price=float(obj["bid_price"]),
                ask_price=float(obj["ask_price"]),
                bid_size=float(obj["bid_size"]),
                ask_size=float(obj["ask_size"]),
                volume_24h=float(obj["volume_24h"]),
                change_24h=float(obj["change_24h"]),
                change_pct_24h=float(obj["change_pct_24h"]),
                high_24h=float(obj["high_24h"]),
                low_24h=float(obj["low_24h"]),
                open_interest=float(obj["open_interest"]) if obj.get("open_interest") else None,
                funding_rate=float(obj["funding_rate"]) if obj.get("funding_rate") else None,
            )
        except Exception as e:
            logger.error(f"Failed to deserialize ticker: {e}")
            return None

    def _serialize_orderbook(self, orderbook: OrderBook) -> str:
        """Serialize orderbook to JSON."""
        return json.dumps({
            "exchange": orderbook.exchange,
            "symbol": orderbook.symbol,
            "timestamp": orderbook.timestamp.isoformat(),
            "bids": [[str(l.price), str(l.size)] for l in orderbook.bids],
            "asks": [[str(l.price), str(l.size)] for l in orderbook.asks],
        })

    def _deserialize_orderbook(self, data: str) -> Optional[OrderBook]:
        """Deserialize orderbook from JSON."""
        try:
            obj = json.loads(data)
            from ..connectors.base import OrderBookLevel

            return OrderBook(
                exchange=obj["exchange"],
                symbol=obj["symbol"],
                timestamp=datetime.fromisoformat(obj["timestamp"]),
                bids=[OrderBookLevel(price=float(p[0]), size=float(p[1])) for p in obj["bids"]],
                asks=[OrderBookLevel(price=float(p[0]), size=float(p[1])) for p in obj["asks"]],
            )
        except Exception as e:
            logger.error(f"Failed to deserialize orderbook: {e}")
            return None

    def _serialize_trade(self, trade: Trade) -> str:
        """Serialize trade to JSON."""
        return json.dumps({
            "exchange": trade.exchange,
            "symbol": trade.symbol,
            "trade_id": trade.trade_id,
            "timestamp": trade.timestamp.isoformat(),
            "price": str(trade.price),
            "size": str(trade.size),
            "side": trade.side.value,
        })

    def _deserialize_trade(self, data: str) -> Optional[Trade]:
        """Deserialize trade from JSON."""
        try:
            obj = json.loads(data)
            from ..connectors.base import Side

            return Trade(
                exchange=obj["exchange"],
                symbol=obj["symbol"],
                trade_id=obj["trade_id"],
                timestamp=datetime.fromisoformat(obj["timestamp"]),
                price=float(obj["price"]),
                size=float(obj["size"]),
                side=Side(obj["side"]),
            )
        except Exception as e:
            logger.error(f"Failed to deserialize trade: {e}")
            return None

    def _serialize_candle(self, candle: Candle) -> str:
        """Serialize candle to JSON."""
        return json.dumps({
            "exchange": candle.exchange,
            "symbol": candle.symbol,
            "timestamp": candle.timestamp.isoformat(),
            "open": str(candle.open),
            "high": str(candle.high),
            "low": str(candle.low),
            "close": str(candle.close),
            "volume": str(candle.volume),
            "timeframe": candle.timeframe,
        })

    def _deserialize_candle(self, data: str) -> Optional[Candle]:
        """Deserialize candle from JSON."""
        try:
            obj = json.loads(data)
            return Candle(
                exchange=obj["exchange"],
                symbol=obj["symbol"],
                timestamp=datetime.fromisoformat(obj["timestamp"]),
                open=float(obj["open"]),
                high=float(obj["high"]),
                low=float(obj["low"]),
                close=float(obj["close"]),
                volume=float(obj["volume"]),
                timeframe=obj["timeframe"],
            )
        except Exception as e:
            logger.error(f"Failed to deserialize candle: {e}")
            return None

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _ticker_key(self, symbol: str, exchange: str) -> str:
        """Generate ticker cache key."""
        return f"ticker:{exchange}:{symbol}"

    def _orderbook_key(self, symbol: str, exchange: str) -> str:
        """Generate orderbook cache key."""
        return f"orderbook:{exchange}:{symbol}"

    def _get_max_candles(self, timeframe: str) -> int:
        """Get max candles to keep based on timeframe."""
        # Keep different amounts based on timeframe
        timeframe_map = {
            "1m": 1440,  # 1 day
            "5m": 288,   # 1 day
            "15m": 96,   # 1 day
            "1h": 168,   # 1 week
            "4h": 42,    # 1 week
            "1d": 365,   # 1 year
        }
        return timeframe_map.get(timeframe, 1000)

    async def _publish(self, channel: str, data: str) -> None:
        """Publish data to channel."""
        if self._client:
            try:
                await self._client.publish(channel, data)
            except Exception as e:
                logger.error(f"Failed to publish to {channel}: {e}")

    async def clear_symbol_data(self, symbol: str) -> int:
        """
        Clear all cached data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Number of keys cleared
        """
        if not self._client:
            return 0

        try:
            # Find all keys for this symbol
            pattern = f"*:{symbol}"
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self._client.delete(*keys)

            return len(keys)
        except Exception as e:
            logger.error(f"Failed to clear symbol data: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics
        """
        if not self._client:
            return {}

        try:
            info = await self._client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human"),
                "total_keys": info.get("db0", {}).get("keys"),
                "uptime_days": info.get("uptime_in_days"),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
