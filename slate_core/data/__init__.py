"""
Data Module

Handles all market data operations including normalization, caching,
and database storage, plus the regime-led discovery data layer.

Legacy submodules (normalizer, cache, database, fetcher, binance_fetcher) are
imported defensively: a broken legacy import must not break the whole package
(or block the regime data layer). Import them directly when needed.
"""

__all__ = []

# Legacy eager imports - guarded so one broken module doesn't break the package.
try:  # pragma: no cover - legacy
    from .normalizer import DataNormalizer, SymbolMapper
    __all__ += ["DataNormalizer", "SymbolMapper"]
except Exception:  # noqa: BLE001 - legacy module optional
    pass

try:  # pragma: no cover - legacy
    from .cache import TimeseriesCache
    __all__ += ["TimeseriesCache"]
except Exception:  # noqa: BLE001
    pass

try:  # pragma: no cover - legacy
    from .database import (
        DatabaseManager, Ticker, Candle, Trade, PaperOrder, PaperPosition,
        PaperBalance, Strategy, BacktestResult, RiskState, CircuitBreakerEvent,
        PortfolioSnapshot, SignalEvent,
    )
    __all__ += ["DatabaseManager", "Ticker", "Candle", "Trade", "PaperOrder",
                "PaperPosition", "PaperBalance", "Strategy", "BacktestResult",
                "RiskState", "CircuitBreakerEvent", "PortfolioSnapshot", "SignalEvent"]
except Exception:  # noqa: BLE001
    pass

try:  # pragma: no cover - legacy
    from .fetcher import HistoricalDataFetcher, DataQualityChecker
    __all__ += ["HistoricalDataFetcher", "DataQualityChecker"]
except Exception:  # noqa: BLE001
    pass

try:  # pragma: no cover - legacy
    from .binance_fetcher import (
        BinanceFetcher, fetch_binance_data, fetch_binance_data_week,
        fetch_binance_data_month, fetch_binance_futures_data,
    )
    __all__ += ["BinanceFetcher", "fetch_binance_data", "fetch_binance_data_week",
                "fetch_binance_data_month", "fetch_binance_futures_data"]
except Exception:  # noqa: BLE001
    pass
