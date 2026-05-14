"""
SLATE Configuration Constants
Centralized configuration to eliminate hardcoded values across the codebase
"""

# Default trading symbols
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_QUOTE = "USDT"

# Default timeframe
DEFAULT_INTERVAL = "1h"

# Volume Imbalance defaults
VI_PERIOD_DEFAULT = 12
VI_THRESHOLD_DEFAULT = 0.30

# Capital and position sizing
DEFAULT_INITIAL_CAPITAL_USDT = 10000
DEFAULT_INITIAL_CAPITAL_BTC = 0.5
DEFAULT_LOT_SIZE_BTC = 0.01

# Transaction costs (realistic Binance futures fees)
MAKER_FEE = 0.0002  # 0.02%
TAKER_FEE = 0.0005  # 0.05%

# Slippage (realistic market impact)
BASE_SLIPPAGE_BPS = 10  # 10 basis points
VOLATILITY_ADJUSTED_SLIPPAGE = True

# Fill realism (not 100% - real market friction)
BASE_FILL_RATE = 0.85  # 85% fill rate
PARTIAL_FILL_PROBABILITY = 0.15  # 15% partial fills
PARTIAL_FILL_MIN_SIZE = 0.3  # 30% minimum fill

# Risk management
MAX_POSITION_SIZE = 0.05  # 5% max per position
MAX_PORTFOLIO_HEAT = 0.15  # 15% total exposure
STOP_LOSS_ATR_MULTIPLE = 2.0
TAKE_PROFIT_ATR_MULTIPLE = 3.0

# Default stop loss and take profit percentages
DEFAULT_STOP_LOSS_PCT = 0.02  # 2%
DEFAULT_TAKE_PROFIT_PCT = 0.04  # 4%
DEFAULT_TRAILING_STOP_PCT = 0.015  # 1.5%

# API endpoints
BINANCE_API_BASE = "https://api.binance.com"
BINANCE_API_KLINES = f"{BINANCE_API_BASE}/api/v3/klines"
BINANCE_FUTURES_API_BASE = "https://fapi.binance.com"

# Data cache paths
DEFAULT_CACHE_DIR = "sol_data_cache"
DEFAULT_CACHE_FILE_PATTERN = "{symbol}_{interval}_{period}.csv"

# Backtest output paths
DEFAULT_OUTPUT_DIR = "backtest_results"
DEFAULT_CHART_FORMAT = "png"
DEFAULT_CHART_DPI = 150
