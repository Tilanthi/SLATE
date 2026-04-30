#!/usr/bin/env python3
"""
Binance USDT-M Perpetual Futures Connector

Real API connectivity for data fetching with paper trading for orders.
Supports all USDT-M perpetual futures on Binance.

NEVER executes real trades - paper trading only.
"""

import asyncio
import logging
import aiohttp
import ssl
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import time
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class BinancePerpetualPosition:
    """Paper trading position for Binance perpetual futures."""
    symbol: str
    side: Literal['long', 'short']
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int = 1
    percentage: float = 0.0


@dataclass
class BinancePerpetualOrder:
    """Paper trading order for Binance perpetual futures."""
    order_id: str
    symbol: str
    side: Literal['BUY', 'SELL']
    order_type: Literal['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT']
    position_side: Literal['BOTH', 'LONG', 'SHORT']
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: Literal['NEW', 'FILLED', 'PARTIALLY_FILLED', 'CANCELED', 'REJECTED'] = 'NEW'
    timestamp: datetime = field(default_factory=datetime.now)
    filled_qty: float = 0.0
    avg_price: float = 0.0


class BinancePerpetualConnector:
    """
    Binance USDT-M Perpetual Futures connector.

    Features:
    - Real-time market data from Binance API
    - Paper trading for orders (NO real execution)
    - Position management and tracking
    - Account information
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = "binance_perpetual"
        self.mode = "paper_trading"

        # API endpoints
        self.base_url = "https://fapi.binance.com"
        self.stream_url = "wss://fstream.binance.com/ws"

        # SSL context (for compatibility)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Paper trading state
        self.balances: Dict[str, float] = {"USDT": 10000.0}
        self.positions: Dict[str, BinancePerpetualPosition] = {}
        self.orders: Dict[str, BinancePerpetualOrder] = {}
        self.order_counter = 0

        # Supported symbols
        self.symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
            "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
            "LINKUSDT", "ATOMUSDT", "LTCUSDT", "UNIUSDT", "APTUSDT"
        ]

        logger.info("Binance USDT-M Perpetual connector initialized in PAPER_TRADING mode")

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Dict = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make HTTP request to Binance API."""
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SLATE/2.0"
        }

        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        # Add signature for signed requests
        if signed and self.api_secret:
            if params is None:
                params = {}
            timestamp = int(time.time() * 1000)
            params["timestamp"] = timestamp

            query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            signature = hashlib.hmac.new(
                self.api_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature

        if method == "GET" and params:
            url += f"?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.request(method, url, headers=headers, json=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Binance API error: {response.status} - {error_text}")
                        return {}

                    return await response.json()
            except asyncio.TimeoutError:
                logger.error("Binance API request timeout")
                return {}
            except Exception as e:
                logger.error(f"Binance API request error: {e}")
                return {}

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker data from Binance API."""
        try:
            data = await self._make_request("/fapi/v1/ticker/24hr", params={"symbol": symbol})

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
                    "timestamp": datetime.now()
                }
        except Exception as e:
            logger.warning(f"Error fetching ticker for {symbol}: {e}")

        # Fallback to simulated data
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
        """Get order book from Binance API."""
        try:
            data = await self._make_request(
                "/fapi/v1/depth",
                params={"symbol": symbol, "limit": min(depth, 1000)}
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
        """Get candlestick data from Binance API."""
        try:
            data = await self._make_request(
                "/fapi/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": min(limit, 1500)}
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

        # Fallback to simulated data
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

    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get current funding rate from Binance API."""
        try:
            data = await self._make_request("/fapi/v1/premiumIndex", params={"symbol": symbol})

            if data:
                return {
                    "symbol": symbol,
                    "mark_price": float(data.get("markPrice", 0)),
                    "index_price": float(data.get("indexPrice", 0)),
                    "estimated_settle_price": float(data.get("estimatedSettlePrice", 0)),
                    "last_funding_rate": float(data.get("lastFundingRate", 0)),
                    "funding_rate": float(data.get("fundingRate", 0)),
                    "next_funding_time": data.get("nextFundingTime"),
                    "timestamp": datetime.now()
                }
        except Exception as e:
            logger.warning(f"Error fetching funding rate for {symbol}: {e}")

        return {
            "symbol": symbol,
            "funding_rate": 0.0001,
            "timestamp": datetime.now()
        }

    async def place_order(
        self,
        symbol: str,
        side: Literal['BUY', 'SELL'],
        order_type: Literal['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT'],
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        position_side: Literal['BOTH', 'LONG', 'SHORT'] = 'BOTH',
        reduce_only: bool = False
    ) -> BinancePerpetualOrder:
        """
        Place a paper trading order (NOT EXECUTED ON BINANCE).

        For paper trading simulation - no real orders placed.
        """
        self.order_counter += 1
        order_id = f"PAPER_BINANCE_{int(time.time() * 1000)}_{self.order_counter}"

        order = BinancePerpetualOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            position_side=position_side,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status="FILLED",  # Simulated instant fill
            filled_qty=quantity,
            avg_price=price or 50000.0
        )

        self.orders[order_id] = order

        # Update paper trading position
        await self._update_paper_position(order)

        logger.info(f"[PAPER TRADING] Binance Perpetual Order: {side} {quantity} {symbol} @ {price}")
        logger.info(f"[PAPER TRADING] Order ID: {order_id} | NOT executed on Binance - simulation only")

        return order

    async def _update_paper_position(self, order: BinancePerpetualOrder) -> None:
        """Update paper trading position based on filled order."""
        symbol = order.symbol

        if symbol not in self.positions:
            # Create new position
            side = 'long' if order.side == 'BUY' else 'short'
            self.positions[symbol] = BinancePerpetualPosition(
                symbol=symbol,
                side=side,
                size=order.filled_qty,
                entry_price=order.avg_price,
                mark_price=order.avg_price,
                unrealized_pnl=0.0
            )
        else:
            # Update existing position
            pos = self.positions[symbol]
            if (order.side == 'BUY' and pos.side == 'long') or \
               (order.side == 'SELL' and pos.side == 'short'):
                pos.size += order.filled_qty
            else:
                pos.size -= order.filled_qty

            # Remove position if size is zero
            if abs(pos.size) < 0.0001:
                del self.positions[symbol]

    async def get_positions(self) -> List[BinancePerpetualPosition]:
        """Get all paper trading positions."""
        return list(self.positions.values())

    async def get_position(self, symbol: str) -> Optional[BinancePerpetualPosition]:
        """Get position for a specific symbol."""
        return self.positions.get(symbol)

    async def get_balance(self) -> Dict[str, float]:
        """Get paper trading balance."""
        return self.balances

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        return {
            "exchange": self.exchange,
            "mode": self.mode,
            "total_balance": self.balances.get("USDT", 0),
            "available_balance": self.balances.get("USDT", 0),
            "positions": len(self.positions),
            "open_orders": len([o for o in self.orders.values() if o.status == 'NEW']),
            "leverage": "1x (paper trading)",
            "margin_mode": "cross",
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

        qty = quantity or abs(pos.size)
        side = 'SELL' if pos.side == 'long' else 'BUY'

        await self.place_order(
            symbol=symbol,
            side=side,
            order_type='MARKET',
            quantity=qty
        )

        return True

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information from Binance API."""
        try:
            data = await self._make_request("/fapi/v1/exchangeInfo")

            if data:
                symbols = []
                for s in data.get("symbols", []):
                    if s.get("status") == "TRADING":
                        symbols.append({
                            "symbol": s["symbol"],
                            "base_asset": s["baseAsset"],
                            "quote_asset": s["quoteAsset"],
                            "status": s["status"],
                            "contract_type": s.get("contractType", "PERPETUAL")
                        })

                return {
                    "exchange": "binance_perpetual",
                    "timezone": data.get("timezone", "UTC"),
                    "server_time": datetime.fromtimestamp(data.get("serverTime", 0) / 1000),
                    "symbols": symbols[:50],  # Limit to first 50
                    "rate_limits": data.get("rateLimits", [])
                }
        except Exception as e:
            logger.warning(f"Error fetching exchange info: {e}")

        return {"exchange": "binance_perpetual", "symbols": self.symbols}
