"""
Tests for exchange connectors.
"""

import pytest
from slate_core.connectors.binance import BinanceConnector
from slate_core.connectors.bitget import BitgetConnector


class TestBinanceConnector:
    """Tests for Binance connector."""

    def setup_method(self):
        self.connector = BinanceConnector()

    @pytest.mark.asyncio
    async def test_get_ticker(self):
        """Test getting ticker data."""
        ticker = await self.connector.get_ticker("BTCUSDT")
        assert "price" in ticker
        assert "symbol" in ticker
        assert ticker["symbol"] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_get_candles(self):
        """Test getting candlestick data."""
        candles = await self.connector.get_candles("BTCUSDT", "1h", 10)
        assert len(candles) == 10
        assert "close" in candles[0]

    @pytest.mark.asyncio
    async def test_paper_trading_only(self):
        """Test that orders are not executed on exchange."""
        # This should be a paper trading order only
        order = await self.connector.place_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=50000
        )

        assert order.order_id.startswith("paper_")
        assert order.status == "filled"


class TestBitgetConnector:
    """Tests for Bitget connector."""

    def setup_method(self):
        self.connector = BitgetConnector()

    @pytest.mark.asyncio
    async def test_get_ticker(self):
        """Test getting ticker data."""
        ticker = await self.connector.get_ticker("BTCUSDT")
        assert "price" in ticker

    @pytest.mark.asyncio
    async def test_paper_trading_only(self):
        """Test that orders are simulated only."""
        order = await self.connector.place_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=50000
        )

        assert order.order_id.startswith("bitget_paper_")
