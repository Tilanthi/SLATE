"""
SLATE Autonomous Market Data Manager

Automatically fetches and manages market data for autonomous operations.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

try:
    from ..connectors.binance_spot import BinanceSpotConnector
    CONNECTOR_AVAILABLE = True
except ImportError:
    CONNECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MarketDataSnapshot:
    """Snapshot of current market data."""
    symbol: str
    timestamp: datetime
    last_price: float
    volume_24h: float
    change_24h: float
    high_24h: float
    low_24h: float

    def to_dict(self):
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'last_price': self.last_price,
            'volume_24h': self.volume_24h,
            'change_24h': self.change_24h,
            'high_24h': self.high_24h,
            'low_24h': self.low_24h
        }


class MarketDataManager:
    """
    Manage automatic market data fetching for autonomous operations.

    Features:
    - Periodic automatic data fetching
    - Data caching to reduce API calls
    - Multi-symbol support
    - Error handling and retries
    """

    def __init__(self, symbols: List[str], update_interval_seconds: int = 60):
        self.symbols = symbols
        self.update_interval = update_interval_seconds

        # Initialize connector
        if CONNECTOR_AVAILABLE:
            self.connector = BinanceSpotConnector()
            logger.info(f"Market connector initialized for {len(symbols)} symbols")
        else:
            self.connector = None
            logger.warning("Binance connector not available - market data limited")

        # Data cache
        self.market_data_cache: Dict[str, MarketDataSnapshot] = {}
        self.last_update_time: Optional[datetime] = None

        # Background task
        self.auto_fetch_active = False
        self.auto_fetch_task: Optional[asyncio.Task] = None

        logger.info(f"Market Data Manager initialized for {len(symbols)} symbols")

    async def start_auto_fetch(self):
        """Start automatic market data fetching in background."""
        if not self.connector:
            logger.warning("Cannot start auto-fetch - connector not available")
            return

        if self.auto_fetch_active:
            logger.warning("Auto-fetch already active")
            return

        self.auto_fetch_active = True
        self.auto_fetch_task = asyncio.create_task(self._auto_fetch_loop())
        logger.info("Automatic market data fetching started")

    async def stop_auto_fetch(self):
        """Stop automatic market data fetching."""
        if not self.auto_fetch_active:
            return

        self.auto_fetch_active = False
        if self.auto_fetch_task:
            self.auto_fetch_task.cancel()
            try:
                await self.auto_fetch_task
            except asyncio.CancelledError:
                pass

        logger.info("Automatic market data fetching stopped")

    async def _auto_fetch_loop(self):
        """Background loop for automatic data fetching."""
        logger.info("Auto-fetch loop started")

        while self.auto_fetch_active:
            try:
                # Fetch data for all symbols
                await self.fetch_all_symbols()

                # Wait for next update
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                logger.info("Auto-fetch loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in auto-fetch loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Wait before retry

        logger.info("Auto-fetch loop ended")

    async def fetch_all_symbols(self) -> Dict[str, MarketDataSnapshot]:
        """Fetch market data for all configured symbols."""
        logger.debug(f"Fetching data for {len(self.symbols)} symbols")

        if not self.connector:
            logger.warning("Cannot fetch symbols - connector not available")
            return {}

        results = {}
        for symbol in self.symbols:
            try:
                snapshot = await self.fetch_symbol(symbol)
                if snapshot:
                    results[symbol] = snapshot
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        self.last_update_time = datetime.now()
        logger.debug(f"Fetched {len(results)} symbols")
        return results

    async def fetch_symbol(self, symbol: str) -> Optional[MarketDataSnapshot]:
        """Fetch market data for a single symbol."""
        if not self.connector:
            logger.warning("Cannot fetch symbol - connector not available")
            return None

        try:
            ticker = await self.connector.get_ticker(symbol)

            if not ticker or ticker.get('last_price', 0) == 0:
                logger.warning(f"No data received for {symbol}")
                return None

            snapshot = MarketDataSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                last_price=ticker['last_price'],
                volume_24h=ticker['volume_24h'],
                change_24h=ticker['change_24h'],
                high_24h=ticker['high_24h'],
                low_24h=ticker['low_24h']
            )

            # Update cache
            self.market_data_cache[symbol] = snapshot

            return snapshot

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None

    def get_cached_data(self, symbol: str) -> Optional[MarketDataSnapshot]:
        """Get cached market data for a symbol."""
        return self.market_data_cache.get(symbol)

    def get_all_cached_data(self) -> Dict[str, MarketDataSnapshot]:
        """Get all cached market data."""
        return self.market_data_cache.copy()

    def is_data_stale(self, max_age_seconds: int = 120) -> bool:
        """Check if cached data is stale."""
        if not self.last_update_time:
            return True

        age = (datetime.now() - self.last_update_time).total_seconds()
        return age > max_age_seconds

    def get_market_intelligence(self) -> Dict[str, Any]:
        """Get market intelligence for decision making."""
        market_data = self.get_all_cached_data()

        if not market_data:
            return {
                'available': False,
                'last_update': None,
                'symbols': {}
            }

        return {
            'available': True,
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'is_stale': self.is_data_stale(),
            'symbols': {
                symbol: {
                    'last_price': data.last_price,
                    'volume_24h': data.volume_24h,
                    'change_24h': data.change_24h,
                    'high_24h': data.high_24h,
                    'low_24h': data.low_24h,
                    'timestamp': data.timestamp.isoformat()
                }
                for symbol, data in market_data.items()
            }
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get market data manager statistics."""
        return {
            'symbols_tracked': len(self.symbols),
            'cached_symbols': len(self.market_data_cache),
            'auto_fetch_active': self.auto_fetch_active,
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'is_stale': self.is_data_stale(),
            'connector_available': CONNECTOR_AVAILABLE,
            'update_interval_seconds': self.update_interval
        }