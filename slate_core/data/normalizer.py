"""
Data Normalization Module

Normalizes data from different exchanges into a unified format.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from ..connectors.base import (
    Ticker,
    OrderBook,
    OrderBookLevel,
    Trade,
    Candle,
    Position,
    Balance,
)

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Normalizes data from multiple exchanges into unified format.

    Handles:
    - Symbol normalization
    - Price precision
    - Volume normalization
    - Timestamp alignment
    """

    def __init__(self):
        """Initialize data normalizer."""
        self._symbol_map: Dict[str, str] = {}
        self._price_precision: Dict[str, int] = {}
        self._volume_precision: Dict[str, int] = {}

    def normalize_symbol(self, symbol: str, exchange: str) -> str:
        """
        Normalize symbol to unified format.

        Args:
            symbol: Original symbol
            exchange: Exchange ID

        Returns:
            Normalized symbol (e.g., 'BTC/USDT')
        """
        # Remove separators and convert to uppercase
        clean = symbol.upper().replace("/", "").replace("-", "")

        # Add separator if not present
        if "/" not in clean:
            # Detect quote currency
            if clean.endswith("USDT"):
                base = clean[:-4]
                quote = "USDT"
            elif clean.endswith("USD"):
                base = clean[:-3]
                quote = "USD"
            elif clean.endswith("BTC") and len(clean) > 3:
                base = clean[:-3]
                quote = "BTC"
            elif clean.endswith("ETH") and len(clean) > 3:
                base = clean[:-3]
                quote = "ETH"
            else:
                # Fallback: assume last 3-4 chars are quote
                if len(clean) > 6:
                    base = clean[:-4]
                    quote = clean[-4:]
                else:
                    base = clean[:-3]
                    quote = clean[-3:]

            clean = f"{base}/{quote}"

        # Cache mapping
        key = f"{exchange}:{symbol}"
        self._symbol_map[key] = clean

        return clean

    def denormalize_symbol(self, symbol: str, exchange: str) -> str:
        """
        Convert unified symbol back to exchange format.

        Args:
            symbol: Unified symbol (e.g., 'BTC/USDT')
            exchange: Exchange ID

        Returns:
            Exchange-specific symbol format
        """
        # Remove separator
        clean = symbol.replace("/", "").replace("-", "")

        # Exchange-specific formatting
        if exchange == "binance_futures":
            # Binance uses all caps, no separator
            return clean
        elif exchange == "bitget":
            # Bitget uses all caps, no separator
            return clean
        else:
            # Default: all caps, no separator
            return clean

    def normalize_ticker(self, ticker: Ticker) -> Ticker:
        """
        Normalize ticker data.

        Args:
            ticker: Original ticker

        Returns:
            Normalized ticker
        """
        # Normalize symbol
        normalized_symbol = self.normalize_symbol(ticker.symbol, ticker.exchange)

        # Ensure timestamp has timezone
        if ticker.timestamp.tzinfo is None:
            ticker.timestamp = ticker.timestamp.replace(tzinfo=timezone.utc)

        # Round prices to reasonable precision
        ticker.last_price = round(ticker.last_price, 8)
        ticker.bid_price = round(ticker.bid_price, 8)
        ticker.ask_price = round(ticker.ask_price, 8)

        return ticker

    def normalize_orderbook(self, orderbook: OrderBook) -> OrderBook:
        """
        Normalize orderbook data.

        Args:
            orderbook: Original orderbook

        Returns:
            Normalized orderbook
        """
        # Normalize symbol
        orderbook.symbol = self.normalize_symbol(orderbook.symbol, orderbook.exchange)

        # Normalize timestamps
        if orderbook.timestamp.tzinfo is None:
            orderbook.timestamp = orderbook.timestamp.replace(tzinfo=timezone.utc)

        # Round prices and sizes
        for level in orderbook.bids:
            level.price = round(level.price, 8)
            level.size = round(level.size, 8)

        for level in orderbook.asks:
            level.price = round(level.price, 8)
            level.size = round(level.size, 8)

        # Sort bids descending, asks ascending
        orderbook.bids.sort(key=lambda x: x.price, reverse=True)
        orderbook.asks.sort(key=lambda x: x.price)

        return orderbook

    def normalize_trade(self, trade: Trade) -> Trade:
        """
        Normalize trade data.

        Args:
            trade: Original trade

        Returns:
            Normalized trade
        """
        # Normalize symbol
        trade.symbol = self.normalize_symbol(trade.symbol, trade.exchange)

        # Normalize timestamp
        if trade.timestamp.tzinfo is None:
            trade.timestamp = trade.timestamp.replace(tzinfo=timezone.utc)

        # Round price and size
        trade.price = round(trade.price, 8)
        trade.size = round(trade.size, 8)

        return trade

    def normalize_candle(self, candle: Candle) -> Candle:
        """
        Normalize candle data.

        Args:
            candle: Original candle

        Returns:
            Normalized candle
        """
        # Normalize symbol
        candle.symbol = self.normalize_symbol(candle.symbol, candle.exchange)

        # Normalize timestamp
        if candle.timestamp.tzinfo is None:
            candle.timestamp = candle.timestamp.replace(tzinfo=timezone.utc)

        # Round prices
        candle.open = round(candle.open, 8)
        candle.high = round(candle.high, 8)
        candle.low = round(candle.low, 8)
        candle.close = round(candle.close, 8)
        candle.volume = round(candle.volume, 8)

        return candle

    def normalize_position(self, position: Position) -> Position:
        """
        Normalize position data.

        Args:
            position: Original position

        Returns:
            Normalized position
        """
        # Normalize symbol
        position.symbol = self.normalize_symbol(position.symbol, position.exchange)

        # Normalize timestamp
        if position.timestamp.tzinfo is None:
            position.timestamp = position.timestamp.replace(tzinfo=timezone.utc)

        # Round values
        position.entry_price = round(position.entry_price, 8)
        position.mark_price = round(position.mark_price, 8)
        position.size = round(position.size, 8)

        return position

    def normalize_balance(self, balance: Balance) -> Balance:
        """
        Normalize balance data.

        Args:
            balance: Original balance

        Returns:
            Normalized balance
        """
        # Round values
        balance.total_balance = round(balance.total_balance, 8)
        balance.available_balance = round(balance.available_balance, 8)
        balance.used_balance = round(balance.used_balance, 8)
        balance.unrealized_pnl = round(balance.unrealized_pnl, 8)

        return balance

    def aggregate_orderbooks(
        self, orderbooks: List[OrderBook], max_depth: int = 100
    ) -> OrderBook:
        """
        Aggregate orderbooks from multiple exchanges.

        Args:
            orderbooks: List of orderbooks to aggregate
            max_depth: Maximum depth of aggregated orderbook

        Returns:
            Aggregated orderbook
        """
        if not orderbooks:
            raise ValueError("No orderbooks to aggregate")

        # Use first orderbook as template
        first_ob = orderbooks[0]
        symbol = first_ob.symbol
        exchange = "aggregated"
        timestamp = datetime.now(timezone.utc)

        # Aggregate bids
        aggregated_bids: List[OrderBookLevel] = []
        for price_level in range(max_depth):
            total_size = 0.0
            price = None

            for ob in orderbooks:
                if price_level < len(ob.bids):
                    bid = ob.bids[price_level]
                    if price is None:
                        price = bid.price
                    total_size += bid.size

            if price is not None and total_size > 0:
                aggregated_bids.append(OrderBookLevel(price=price, size=total_size))

        # Aggregate asks
        aggregated_asks: List[OrderBookLevel] = []
        for price_level in range(max_depth):
            total_size = 0.0
            price = None

            for ob in orderbooks:
                if price_level < len(ob.asks):
                    ask = ob.asks[price_level]
                    if price is None:
                        price = ask.price
                    total_size += ask.size

            if price is not None and total_size > 0:
                aggregated_asks.append(OrderBookLevel(price=price, size=total_size))

        return OrderBook(
            exchange=exchange,
            symbol=symbol,
            timestamp=timestamp,
            bids=aggregated_bids,
            asks=aggregated_asks,
        )

    def calculate_aggregated_ticker(self, tickers: List[Ticker]) -> Ticker:
        """
        Calculate aggregated ticker from multiple exchanges.

        Args:
            tickers: List of tickers to aggregate

        Returns:
            Aggregated ticker
        """
        if not tickers:
            raise ValueError("No tickers to aggregate")

        symbol = tickers[0].symbol
        exchange = "aggregated"
        timestamp = datetime.now(timezone.utc)

        # Use best bid and ask across exchanges
        best_bid = max(t.bid_price for t in tickers)
        best_ask = min(t.ask_price for t in tickers)

        # Aggregate other fields
        total_volume = sum(t.volume_24h for t in tickers)

        # Weighted average price
        total_value = sum(t.last_price * t.volume_24h for t in tickers)
        weighted_price = total_value / total_volume if total_volume > 0 else tickers[0].last_price

        return Ticker(
            exchange=exchange,
            symbol=symbol,
            timestamp=timestamp,
            last_price=weighted_price,
            bid_price=best_bid,
            ask_price=best_ask,
            bid_size=sum(t.bid_size for t in tickers),
            ask_size=sum(t.ask_size for t in tickers),
            volume_24h=total_volume,
            change_24h=tickers[0].change_24h,
            change_pct_24h=tickers[0].change_pct_24h,
            high_24h=max(t.high_24h for t in tickers),
            low_24h=min(t.low_24h for t in tickers),
            open_interest=sum(t.open_interest or 0 for t in tickers),
        )

    def align_timestamps(self, data_points: List[Any], interval_seconds: int) -> List[Any]:
        """
        Align timestamps to fixed intervals.

        Args:
            data_points: List of data points with timestamps
            interval_seconds: Interval in seconds

        Returns:
            List with aligned timestamps
        """
        aligned = []

        for point in data_points:
            if hasattr(point, 'timestamp'):
                ts = point.timestamp
                # Calculate aligned timestamp
                aligned_ts = int(ts.timestamp() / interval_seconds) * interval_seconds
                point.timestamp = datetime.fromtimestamp(aligned_ts, tz=timezone.utc)
                aligned.append(point)

        return aligned


class SymbolMapper:
    """
    Maps symbols between different exchanges.
    """

    def __init__(self):
        """Initialize symbol mapper."""
        self._mappings: Dict[str, Dict[str, str]] = {}

    def add_mapping(self, unified_symbol: str, exchange: str, exchange_symbol: str) -> None:
        """
        Add symbol mapping.

        Args:
            unified_symbol: Unified symbol (e.g., 'BTC/USDT')
            exchange: Exchange ID
            exchange_symbol: Exchange-specific symbol
        """
        if unified_symbol not in self._mappings:
            self._mappings[unified_symbol] = {}
        self._mappings[unified_symbol][exchange] = exchange_symbol

    def get_exchange_symbol(self, unified_symbol: str, exchange: str) -> Optional[str]:
        """
        Get exchange-specific symbol.

        Args:
            unified_symbol: Unified symbol
            exchange: Exchange ID

        Returns:
            Exchange-specific symbol or None
        """
        return self._mappings.get(unified_symbol, {}).get(exchange)

    def get_unified_symbol(self, exchange_symbol: str, exchange: str) -> Optional[str]:
        """
        Get unified symbol from exchange symbol.

        Args:
            exchange_symbol: Exchange-specific symbol
            exchange: Exchange ID

        Returns:
            Unified symbol or None
        """
        for unified_symbol, mappings in self._mappings.items():
            if mappings.get(exchange) == exchange_symbol:
                return unified_symbol
        return None

    def load_common_mappings(self) -> None:
        """
        Load common symbol mappings.
        """
        common_pairs = [
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "BNB/USDT",
            "XRP/USDT",
            "ADA/USDT",
            "DOGE/USDT",
            "MATIC/USDT",
            "DOT/USDT",
            "AVAX/USDT",
        ]

        for pair in common_pairs:
            clean = pair.replace("/", "")
            self.add_mapping(pair, "binance_futures", clean)
            self.add_mapping(pair, "bitget", clean)
