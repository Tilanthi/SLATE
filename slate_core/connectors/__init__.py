"""
SLATE Exchange Connectors

Unified interface for Binance Futures USDT-M and Bitget Perpetual.
Paper trading mode only - NO LIVE TRADING.
"""

from .binance import BinanceConnector
from .bitget import BitgetConnector

__all__ = ['BinanceConnector', 'BitgetConnector']
