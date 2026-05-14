"""
Data Module

Handles all market data operations including normalization, caching,
and database storage.
"""

from .normalizer import DataNormalizer, SymbolMapper
from .cache import TimeseriesCache
from .database import (
    DatabaseManager,
    Ticker,
    Candle,
    Trade,
    PaperOrder,
    PaperPosition,
    PaperBalance,
    Strategy,
    BacktestResult,
    RiskState,
    CircuitBreakerEvent,
    PortfolioSnapshot,
    SignalEvent,
)
from .fetcher import HistoricalDataFetcher, DataQualityChecker
from .binance_fetcher import (
    BinanceFetcher,
    fetch_binance_data,
    fetch_binance_data_week,
    fetch_binance_data_month,
    fetch_binance_futures_data
)

__all__ = [
    "DataNormalizer",
    "SymbolMapper",
    "TimeseriesCache",
    "DatabaseManager",
    "HistoricalDataFetcher",
    "DataQualityChecker",
    # Binance fetcher (consolidated)
    "BinanceFetcher",
    "fetch_binance_data",
    "fetch_binance_data_week",
    "fetch_binance_data_month",
    "fetch_binance_futures_data",
    # Database models
    "Ticker",
    "Candle",
    "Trade",
    "PaperOrder",
    "PaperPosition",
    "PaperBalance",
    "Strategy",
    "BacktestResult",
    "RiskState",
    "CircuitBreakerEvent",
    "PortfolioSnapshot",
    "SignalEvent",
]
