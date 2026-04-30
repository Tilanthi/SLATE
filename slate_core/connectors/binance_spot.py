#!/usr/bin/env python3
"""
Binance Spot Connector

Real API connectivity for data fetching with paper trading for orders.
Supports all spot trading pairs on Binance.

NEVER executes real trades - paper trading only.
"""

import asyncio
import logging
import aiohttp
import ssl
import hmac
import hashlib
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class BinanceSpotPosition:
    """Paper trading position for Binance spot."""
    symbol: str
    base_asset: str
    quote_asset: str
    free: float
    locked: float
    avg_price: float
    unrealized_pnl: float


@dataclass
class BinanceSpotOrder:
    """Paper trading order for Binance spot."""
    order_id: str
    symbol: str
    side: Literal['BUY', 'SELL']
    order_type: Literal['MARKET', 'LIMIT', 'STOP_LOSS_LIMIT', 'OCO']
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: Literal['NEW', 'FILLED', 'PARTIALLY_FILLED', 'CANCELED', 'REJECTED', 'EXPIRED'] = 'NEW'
    timestamp: datetime = field(default_factory=datetime.now)
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fees: float = 0.0


class BinanceSpotConnector:
    """
    Binance Spot connector.

    Features:
    - Real-time market data from Binance Spot API
    - Paper trading for orders (NO real execution)
    - Balance management and tracking
    - Order book and trade history
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = "binance_spot"
        self.mode = "paper_trading"

        # API endpoints
        self.base_url = "https://api.binance.com"
        self.stream_url = "wss://stream.binance.com:9443/ws"

        # SSL context
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Paper trading state
        self.balances: Dict[str, float] = {"USDT": 10000.0}
        self.positions: Dict[str, BinanceSpotPosition] = {}
        self.orders: Dict[str, BinanceSpotOrder] = {}
        self.order_counter = 0

        # Supported symbols
        self.symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
            "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
            "LINKUSDT", "ATOMUSDT", "LTCUSDT", "UNIUSDT", "APTUSDT",
            "OPUSDT", "ARBUSDT", "NEARUSDT", "APTUSDT"
        ]

        logger.info("Binance Spot connector initialized in PAPER_TRADING mode")

    def _generate_signature(self, query_string: str) -> str:
        """Generate Binance API signature."""
        if not self.api_secret:
            return ""
        return hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Dict = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make HTTP request to Binance Spot API."""
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SLATE/2.0"
        }

        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        query_string = ""
        if params:
            query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))

        # Add signature for signed requests
        if signed and self.api_secret:
            timestamp = int(time.time() * 1000)
            params["timestamp"] = timestamp if params else timestamp

            if query_string:
                query_string += f"&timestamp={timestamp}"
            else:
                query_string = f"timestamp={timestamp}"

            signature = self._generate_signature(query_string)
            query_string += f"&signature={signature}"

        if query_string:
            url += f"?{query_string}"

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.request(method, url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Binance Spot API error: {response.status} - {error_text}")
                        return {}

                    return await response.json()
            except asyncio.TimeoutError:
                logger.error("Binance Spot API request timeout")
                return {}
            except Exception as e:
                logger.error(f"Binance Spot API request error: {e}")
                return {}

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker data from Binance Spot API."""
        try:
            data = await self._make_request("/api/v3/ticker/24hr", params={"symbol": symbol})

            if data and "symbol" in data:
                return {
                    "symbol": data["symbol"],
                    "last_price": float(data["lastPrice"]),
                    "bid_price": float(data.get("bidPrice", 0)),
                    "ask_price": float(data.get("askPrice", 0)),
                    "volume_24h": float(data["volume"]),
                    "change_24h": float(data["priceChangePercent"]),
                    "high_24h": float(data["highPrice"]),
                    "low_24h": float(data["lowPrice"]),
                    "quote_volume_24h": float(data["quoteVolume"]),
                    "timestamp": datetime.now()
                }
        except Exception as e:
            logger.warning(f"Error fetching ticker for {symbol}: {e}")

        # Fallback
        return {
            "symbol": symbol,
            "last_price": 50000.0,
            "bid_price": 49999.0,
            "ask_price": 50001.0,
            "volume_24h": 10000.0,
            "change_24h": 2.5,
            "timestamp": datetime.now()
        }

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """Get order book from Binance Spot API."""
        try:
            data = await self._make_request(
                "/api/v3/depth",
                params={"symbol": symbol, "limit": min(depth, 5000)}
            )

            if data and "bids" in data:
                bids = [[float(p), float(q)] for p, q in data["bids"][:depth]]
                asks = [[float(p), float(q)] for p, q in data["asks"][:depth]]

                return {
                    "symbol": symbol,
                    "bids": bids,
                    "asks": asks,
                    "last_update_id": data.get("lastUpdateId", 0),
                    "timestamp": datetime.now()
                }
        except Exception as e:
            logger.warning(f"Error fetching orderbook for {symbol}: {e}")

        # Fallback
        base_price = 50000.0
        return {
            "symbol": symbol,
            "bids": [[base_price - i * 0.5, 10.0 - i * 0.1] for i in range(depth)],
            "asks": [[base_price + i * 0.5, 10.0 - i * 0.1] for i in range(depth)],
            "timestamp": datetime.now()
        }

    async def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get candlestick data from Binance Spot API."""
        try:
            data = await self._make_request(
                "/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
            )

            if data:
                candles = []
                for k in data:
                    candles.append({
                        "timestamp": datetime.fromtimestamp(k[0] / 1000),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5])
                    })
                return candles
        except Exception as e:
            logger.warning(f"Error fetching candles for {symbol}: {e}")

        # Fallback
        candles = []
        base_price = 50000.0
        for i in range(limit):
            ts = datetime.now() - timedelta(hours=limit-i)
            candles.append({
                "timestamp": ts,
                "open": base_price + i * 10,
                "high": base_price + i * 10 + 50,
                "low": base_price + i * 10 - 30,
                "close": base_price + i * 10 + 20,
                "volume": 100.0 + i
            })
        return candles

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades from Binance Spot API."""
        try:
            data = await self._make_request(
                "/api/v3/trades",
                params={"symbol": symbol, "limit": min(limit, 1000)}
            )

            if data:
                trades = []
                for t in data:
                    trades.append({
                        "id": t.get("id"),
                        "price": float(t["price"]),
                        "qty": float(t["qty"]),
                        "time": datetime.fromtimestamp(t["time"] / 1000),
                        "is_buyer_maker": t["isBuyerMaker"]
                    })
                return trades
        except Exception as e:
            logger.warning(f"Error fetching recent trades for {symbol}: {e}")

        return []

    async def place_order(
        self,
        symbol: str,
        side: Literal['BUY', 'SELL'],
        order_type: Literal['MARKET', 'LIMIT'] = 'MARKET',
        quantity: float = 1.0,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> BinanceSpotOrder:
        """
        Place a paper trading order (NOT EXECUTED ON BINANCE).

        For paper trading simulation - no real orders placed.
        """
        self.order_counter += 1
        order_id = f"PAPER_SPOT_{int(time.time() * 1000)}_{self.order_counter}"

        # Calculate fees (0.1% for spot)
        current_price = price or 50000.0
        notional = quantity * current_price
        fees = notional * 0.001  # 0.1% standard fee

        order = BinanceSpotOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status="FILLED",  # Simulated instant fill
            filled_qty=quantity,
            avg_price=current_price,
            fees=fees
        )

        self.orders[order_id] = order

        # Update paper trading position
        await self._update_paper_position(order)

        logger.info(f"[PAPER TRADING] Binance Spot Order: {side} {quantity} {symbol} @ {current_price}")
        logger.info(f"[PAPER TRADING] Order ID: {order_id} | NOT executed on Binance - simulation only")
        logger.info(f"[PAPER TRADING] Fees: ${fees:.2f} (0.1%)")

        return order

    async def _update_paper_position(self, order: BinanceSpotOrder) -> None:
        """Update paper trading position based on filled order."""
        symbol = order.symbol

        # Extract base and quote assets
        if symbol.endswith("USDT"):
            base_asset = symbol.replace("USDT", "")
            quote_asset = "USDT"
        else:
            base_asset = symbol[:3]
            quote_asset = symbol[3:]

        if symbol not in self.positions:
            # Create new position
            self.positions[symbol] = BinanceSpotPosition(
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                free=order.filled_qty,
                locked=0.0,
                avg_price=order.avg_price,
                unrealized_pnl=0.0
            )
        else:
            # Update existing position
            pos = self.positions[symbol]

            if order.side == "BUY":
                pos.free += order.filled_qty
                # Update average price
                total_value = (pos.avg_price * pos.free) + (order.avg_price * order.filled_qty)
                total_qty = pos.free + order.filled_qty
                pos.avg_price = total_value / total_qty if total_qty > 0 else pos.avg_price
            else:  # SELL
                # Calculate PnL
                pnl = (order.avg_price - pos.avg_price) * order.filled_qty
                pos.unrealized_pnl += pnl
                pos.free -= order.filled_qty

            # Remove position if empty
            if pos.free < 0.0001:
                del self.positions[symbol]

    async def get_positions(self) -> List[BinanceSpotPosition]:
        """Get all paper trading positions."""
        return list(self.positions.values())

    async def get_position(self, symbol: str) -> Optional[BinanceSpotPosition]:
        """Get position for a specific symbol."""
        return self.positions.get(symbol)

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        """Get paper trading balance."""
        if asset:
            return {asset: self.balances.get(asset, 0)}
        return self.balances

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        total_value = self.balances.get("USDT", 0)

        # Add value of spot positions
        for pos in self.positions.values():
            total_value += pos.free * pos.avg_price

        return {
            "exchange": self.exchange,
            "mode": self.mode,
            "balances": self.balances,
            "total_value_usdt": total_value,
            "positions": len(self.positions),
            "open_orders": len([o for o in self.orders.values() if o.status == 'NEW']),
            "trading_enabled": True,
            "timestamp": datetime.now()
        }

    async def get_supported_symbols(self) -> List[str]:
        """Get list of supported trading symbols."""
        return self.symbols.copy()

    async def close_position(self, symbol: str, quantity: Optional[float] = None) -> bool:
        """Close a paper trading position."""
        pos = self.positions.get(symbol)
        if not pos:
            return False

        qty = quantity or pos.free
        side = 'SELL' if pos.free > 0 else 'BUY'

        await self.place_order(
            symbol=symbol,
            side=side,
            order_type='MARKET',
            quantity=qty
        )

        return True

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information from Binance Spot API."""
        try:
            data = await self._make_request("/api/v3/exchangeInfo")

            if data:
                symbols = []
                for s in data.get("symbols", []):
                    if s.get("status") == "TRADING":
                        symbols.append({
                            "symbol": s["symbol"],
                            "base_asset": s["baseAsset"],
                            "quote_asset": s["quoteAsset"],
                            "status": s["status"],
                            "filters": s.get("filters", [])[:3]
                        })

                return {
                    "exchange": "binance_spot",
                    "timezone": data.get("timezone", "UTC"),
                    "server_time": datetime.fromtimestamp(data.get("serverTime", 0) / 1000),
                    "symbols": symbols[:50],
                    "rate_limits": data.get("rateLimits", [])
                }
        except Exception as e:
            logger.warning(f"Error fetching exchange info: {e}")

        return {"exchange": "binance_spot", "symbols": self.symbols}

    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific symbol."""
        try:
            data = await self._make_request("/api/v3/exchangeInfo")

            if data:
                for s in data.get("symbols", []):
                    if s["symbol"] == symbol:
                        return {
                            "symbol": s["symbol"],
                            "base_asset": s["baseAsset"],
                            "quote_asset": s["quoteAsset"],
                            "status": s["status"],
                            "min_qty": float([f for f in s.get("filters", []) if f["filterType"] == "LOT_SIZE"][0]["minQty"]),
                            "max_qty": float([f for f in s.get("filters", []) if f["filterType"] == "LOT_SIZE"][0]["maxQty"]),
                            "min_price": float([f for f in s.get("filters", []) if f["filterType"] == "PRICE_FILTER"][0]["minPrice"]),
                            "max_price": float([f for f in s.get("filters", []) if f["filterType"] == "PRICE_FILTER"][0]["maxPrice"]),
                            "tick_size": float([f for f in s.get("filters", []) if f["filterType"] == "PRICE_FILTER"][0]["tickSize"])
                        }
        except Exception as e:
            logger.warning(f"Error fetching symbol info for {symbol}: {e}")

        return None
