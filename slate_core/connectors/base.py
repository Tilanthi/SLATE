"""
Base Connector Module

Defines common data types and interfaces for exchange connectors.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


@dataclass
class Ticker:
    """Ticker information."""

    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    volume_24h: float
    timestamp: datetime


@dataclass
class OrderBookLevel:
    """Single level in order book."""

    price: float
    size: float


@dataclass
class OrderBook:
    """Order book data."""

    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime


@dataclass
class Trade:
    """Trade data."""

    symbol: str
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    timestamp: datetime
    trade_id: Optional[str] = None


@dataclass
class Candle:
    """OHLCV candle data."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    """Position data."""

    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float


@dataclass
class Balance:
    """Account balance."""

    asset: str
    free: float
    locked: float


class ExchangeConnector:
    """Base class for exchange connectors."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """Initialize connector."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for symbol."""
        raise NotImplementedError

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book."""
        raise NotImplementedError

    async def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        raise NotImplementedError

    async def get_candles(
        self, symbol: str, interval: str, limit: int = 100
    ) -> List[Candle]:
        """Get candle data."""
        raise NotImplementedError

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        raise NotImplementedError

    async def get_balance(self) -> List[Balance]:
        """Get account balance."""
        raise NotImplementedError
