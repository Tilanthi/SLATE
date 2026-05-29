# Backward compatibility - export all constants
from .constants import *

# New unified configuration management system
from .manager import (
    Environment,
    TradingConfig,
    TransactionCostConfig,
    ApiConfig,
    DataConfig,
    BacktestConfig,
    LoggingConfig,
    OrchestrationConfig,
    SystemConfig,
    ConfigManager,
    get_config_manager,
    get_config
)

__all__ = [
    # Constants (backward compatible)
    'DEFAULT_SYMBOL',
    'DEFAULT_QUOTE',
    'DEFAULT_INTERVAL',
    'VI_PERIOD_DEFAULT',
    'VI_THRESHOLD_DEFAULT',
    'DEFAULT_INITIAL_CAPITAL_USDT',
    'DEFAULT_INITIAL_CAPITAL_BTC',
    'DEFAULT_LOT_SIZE_BTC',
    'MAKER_FEE',
    'TAKER_FEE',
    'BASE_SLIPPAGE_BPS',
    'VOLATILITY_ADJUSTED_SLIPPAGE',
    'BASE_FILL_RATE',
    'PARTIAL_FILL_PROBABILITY',
    'PARTIAL_FILL_MIN_SIZE',
    'MAX_POSITION_SIZE',
    'MAX_PORTFOLIO_HEAT',
    'STOP_LOSS_ATR_MULTIPLE',
    'TAKE_PROFIT_ATR_MULTIPLE',
    'DEFAULT_STOP_LOSS_PCT',
    'DEFAULT_TAKE_PROFIT_PCT',
    'DEFAULT_TRAILING_STOP_PCT',
    'BINANCE_API_BASE',
    'BINANCE_API_KLINES',
    'BINANCE_FUTURES_API_BASE',
    'DEFAULT_CACHE_DIR',
    'DEFAULT_CACHE_FILE_PATTERN',
    'DEFAULT_OUTPUT_DIR',
    'DEFAULT_CHART_FORMAT',
    'DEFAULT_CHART_DPI',
    # New configuration management
    'Environment',
    'TradingConfig',
    'TransactionCostConfig',
    'ApiConfig',
    'DataConfig',
    'BacktestConfig',
    'LoggingConfig',
    'OrchestrationConfig',
    'SystemConfig',
    'ConfigManager',
    'get_config_manager',
    'get_config'
]

