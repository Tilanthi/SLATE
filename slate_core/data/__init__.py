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

__all__ = [
    "DataNormalizer",
    "SymbolMapper",
    "TimeseriesCache",
    "DatabaseManager",
    "HistoricalDataFetcher",
    "DataQualityChecker",
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
