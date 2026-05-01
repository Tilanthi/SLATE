#!/usr/bin/env python3
"""
SLATE Edge Discovery Engine - Finding Genuine Market Alpha

Focuses on discovering true market edges through:
- Brutal transaction cost realism (fees, slippage, partial fills)
- Multi-path Monte Carlo validation (100+ paths)
- Out-of-sample testing with walk-forward analysis
- Uncapped performance metrics
- Risk-managed position sizing
- Maximum 25% drawdown constraint
- PERSISTENT MEMORY via GraphPalace for cross-cycle learning

Strategies tested:
- Market microstructure edges
- Cross-asset correlations
- Volatility regime exploitation
- Order flow imbalances
- Time-of-day patterns
- Statistical arbitrage opportunities
- Momentum-mean reversion hybrids
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import sqlite3
from collections import defaultdict

# Import persistent memory
try:
    from .discovery_memory import get_discovery_memory
    PERSISTENT_MEMORY_AVAILABLE = True
except ImportError:
    PERSISTENT_MEMORY_AVAILABLE = False
    logger.warning("Persistent memory not available - discoveries will not be stored in knowledge graph")

# Import checkpoint manager
try:
    from .checkpoint_manager import get_checkpoint_manager
    CHECKPOINT_AVAILABLE = True
except ImportError:
    CHECKPOINT_AVAILABLE = False
    logger.warning("Checkpoint manager not available - crash recovery disabled")

# Import reflection memory
try:
    from .reflection_memory import get_reflection_memory
    REFLECTION_MEMORY_AVAILABLE = True
except ImportError:
    REFLECTION_MEMORY_AVAILABLE = False
    logger.warning("Reflection memory not available - cross-cycle learning disabled")

logger = logging.getLogger(__name__)


class EdgeType(Enum):
    """Types of market edges to discover."""
    VOLATILITY_REGIME = "volatility_regime"
    MARKET_MICROSTRUCTURE = "market_microstructure"
    CORRELATION_ARBITRAGE = "correlation_arbitrage"
    ORDER_FLOW_IMBALANCE = "order_flow_imbalance"
    TIME_PATTERN = "time_pattern"
    MOMENTUM_MEAN_REVERSION = "momentum_mean_reversion"
    LIQUIDITY_PREMIUM = "liquidity_premium"
    FUNDAMENTAL_MOMENTUM = "fundamental_momentum"


@dataclass
class EdgeCandidate:
    """A discovered market edge candidate."""
    edge_type: EdgeType
    description: str
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    risk_params: Dict[str, Any]
    confidence: float
    expected_return: float
    expected_drawdown: float


@dataclass
class EdgeBacktestConfig:
    """Brutally realistic backtest configuration."""
    # Transaction costs
    maker_fee: float = 0.0002  # 0.02%
    taker_fee: float = 0.0005  # 0.05%
    base_slippage_bps: int = 10  # Higher base slippage for realism
    volatility_adjusted_slippage: bool = True

    # Fill realism
    base_fill_rate: float = 0.85  # Only 85% fill at best price
    partial_fill_probability: float = 0.15
    partial_fill_min_size: float = 0.3  # 30% of order minimum

    # Risk management
    max_position_size: float = 0.05  # 5% max per position
    max_portfolio_heat: float = 0.15  # 15% total exposure
    stop_loss_atr_multiple: float = 2.0
    take_profit_atr_multiple: float = 3.0

    # Validation
    monte_carlo_paths: int = 100
    walk_forward_windows: int = 5
    out_of_sample_ratio: float = 0.3

    # Constraints
    max_drawdown_limit: float = 0.25  # 25% hard limit
    min_trading_days: int = 60  # Minimum 2 months of data
    initial_capital: float = 10000.0


@dataclass
class EdgeBacktestResult:
    """Results from edge validation with USDT profit as PRIMARY metric."""
    edge_type: str
    edge_description: str

    # PRIMARY METRICS: USDT Profit (not percentages)
    total_profit_usdt: float  # Actual USDT profit/loss
    total_return_pct: float  # Percentage return
    final_capital: float
    initial_capital: float

    # Buy and Hold Baseline (CRITICAL for comparison)
    buy_hold_profit_usdt: float  # What buy-and-hold would have made
    buy_hold_return_pct: float
    vs_buy_hold_usdt: float  # Strategy profit minus buy-hold profit
    beat_market: bool  # Did we beat simply holding?

    # Risk metrics
    max_drawdown_pct: float
    max_drawdown_usdt: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Trading statistics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_pnl_usdt: float

    # Validation metrics (in USDT)
    monte_carlo_mean_profit_usdt: float
    monte_carlo_std_profit_usdt: float
    monte_carlo_5th_percentile_usdt: float
    monte_carlo_win_rate: float  # % of paths profitable

    walk_forward_is_profitable: bool
    walk_forward_avg_profit_usdt: float

    # Realism metrics
    avg_slippage_bps: float
    avg_fill_rate: float
    total_fees_usdt: float

    # Market data
    period_start: str
    period_end: str
    volatility_regime: str
    start_price: float
    end_price: float

    # Status
    passed_validation: bool
    validation_failures: List[str]

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EdgeDiscoveryEngine:
    """
    Discovers and validates genuine market edges with brutal realism.

    Unlike traditional parameter sweeping, this engine:
    1. Focuses on structural market inefficiencies
    2. Applies realistic transaction costs
    3. Validates with multi-path Monte Carlo
    4. Enforces strict risk constraints
    5. Ranks by PnL, not just Sharpe
    """

    def __init__(self, db_path: str = "slate_core/slate_realistic_discoveries.db",
                 checkpoint_enabled: bool = False,
                 reflection_enabled: bool = True):
        self.db_path = db_path
        self.config = EdgeBacktestConfig()
        self.discovered_edges: List[EdgeBacktestResult] = []
        self.checkpoint_enabled = checkpoint_enabled
        self.reflection_enabled = reflection_enabled

        # Initialize persistent memory for cross-cycle learning
        if PERSISTENT_MEMORY_AVAILABLE:
            self.memory = get_discovery_memory()
            logger.info("Persistent memory enabled - discoveries stored in knowledge graph")
        else:
            self.memory = None
            logger.warning("Persistent memory unavailable - using database only")

        # Initialize checkpoint manager for crash recovery
        if CHECKPOINT_AVAILABLE and checkpoint_enabled:
            self.checkpoint_manager = get_checkpoint_manager()
            logger.info("Checkpoint manager enabled - crash recovery available")
        else:
            self.checkpoint_manager = None

        # Initialize reflection memory for cross-cycle learning
        if REFLECTION_MEMORY_AVAILABLE and reflection_enabled:
            self.reflection_memory = get_reflection_memory()
            logger.info("Reflection memory enabled - cross-cycle learning available")
        else:
            self.reflection_memory = None

        # Initialize database
        self._init_db()

        logger.info("EdgeDiscoveryEngine initialized with brutal realism")

    def _init_db(self):
        """Initialize database schema for edge discoveries with USDT profit focus."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edge_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_type TEXT NOT NULL,
                edge_description TEXT NOT NULL,

                -- PRIMARY METRIC: USDT Profit
                total_profit_usdt REAL NOT NULL,
                total_return_pct REAL NOT NULL,
                final_capital REAL NOT NULL,
                initial_capital REAL NOT NULL,

                -- Buy and Hold Baseline
                buy_hold_profit_usdt REAL NOT NULL,
                buy_hold_return_pct REAL NOT NULL,
                vs_buy_hold_usdt REAL NOT NULL,
                beat_market INTEGER NOT NULL,

                -- Risk metrics
                max_drawdown_pct REAL NOT NULL,
                max_drawdown_usdt REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                sortino_ratio REAL,
                calmar_ratio REAL,

                -- Trading statistics
                total_trades INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL,
                avg_trade_pnl_usdt REAL,

                -- Validation metrics
                monte_carlo_mean_profit_usdt REAL,
                monte_carlo_std_profit_usdt REAL,
                monte_carlo_5th_percentile_usdt REAL,
                monte_carlo_win_rate REAL,

                walk_forward_is_profitable INTEGER,
                walk_forward_avg_profit_usdt REAL,

                -- Realism metrics
                avg_slippage_bps REAL,
                avg_fill_rate REAL,
                total_fees_usdt REAL,

                -- Market data
                period_start TEXT,
                period_end TEXT,
                volatility_regime TEXT,
                start_price REAL,
                end_price REAL,

                -- Validation
                passed_validation INTEGER NOT NULL,
                validation_failures TEXT,

                timestamp TEXT NOT NULL,

                -- RANKING: USDT Profit is PRIMARY
                rank_score REAL,

                UNIQUE(edge_type, edge_description, period_start, period_end)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_profit
            ON edge_discoveries(total_profit_usdt DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_validation
            ON edge_discoveries(passed_validation, total_profit_usdt DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_beat_market
            ON edge_discoveries(beat_market, total_profit_usdt DESC)
        """)

        conn.commit()
        conn.close()
        logger.info("Edge discoveries database initialized with USDT profit schema")

    def generate_edge_candidates(self) -> List[EdgeCandidate]:
        """
        Generate diverse edge candidates from a large strategy library.
        Each cycle randomly selects different strategies to test for true exploration.
        """
        import random
        import uuid

        # Large library of diverse strategy templates
        strategy_library = [
            # MOMENTUM STRATEGIES
            {
                "name": "EMA Crossover Momentum",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._ema_crossover_strategy()
            },
            {
                "name": "RSI Momentum Breakout",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._rsi_momentum_strategy()
            },
            {
                "name": "MACD Histogram Momentum",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._macd_momentum_strategy()
            },
            {
                "name": "Breakout Pullback Entry",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._breakout_pullback_strategy()
            },

            # MEAN REVERSION STRATEGIES
            {
                "name": "Bollinger Band Mean Reversion",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._bollinger_reversion_strategy()
            },
            {
                "name": "RSI Extremes Reversal",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._rsi_reversal_strategy()
            },
            {
                "name": "Support Resistance Bounce",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._sr_bounce_strategy()
            },
            {
                "name": "Fibonacci Retracement Fade",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._fib_reversal_strategy()
            },

            # VOLATILITY STRATEGIES
            {
                "name": "ATR Breakout Expansion",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._atr_breakout_strategy()
            },
            {
                "name": "Volatility Squeeze Play",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._vol_squeeze_strategy()
            },
            {
                "name": "VIX Proxy Spike Fade",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._vix_spike_strategy()
            },
            {
                "name": "Gamma Exposure Scalping",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._gamma_scalp_strategy()
            },

            # TIME-BASED STRATEGIES
            {
                "name": "Asian Session Range Fade",
                "edge_type": EdgeType.TIME_PATTERN,
                "template": lambda: self._asian_session_strategy()
            },
            {
                "name": "London Open Breakout",
                "edge_type": EdgeType.TIME_PATTERN,
                "template": lambda: self._london_open_strategy()
            },
            {
                "name": "NY Open Momentum",
                "edge_type": EdgeType.TIME_PATTERN,
                "template": lambda: self._ny_open_strategy()
            },
            {
                "name": "End of Day Reversal",
                "edge_type": EdgeType.TIME_PATTERN,
                "template": lambda: self._eod_reversal_strategy()
            },
            {
                "name": "Weekend Gap Fade",
                "edge_type": EdgeType.TIME_PATTERN,
                "template": lambda: self._weekend_gap_strategy()
            },
            {
                "name": "CPI/Pivot News Play",
                "edge_type": EdgeType.TIME_PATTERN,
                "template": lambda: self._news_play_strategy()
            },

            # MARKET MICROSTRUCTURE
            {
                "name": "Order Flow Imbalance",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._order_flow_strategy()
            },
            {
                "name": "Liquidity Sweep Reversal",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._liquidity_sweep_strategy()
            },
            {
                "name": "Iceberg Order Detection",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._iceberg_strategy()
            },
            {
                "name": "Tick Volume Anomaly",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._tick_volume_strategy()
            },
            {
                "name": "Bid-Ask Spread Dynamics",
                "edge_type": EdgeType.MARKET_MICROSTRUCTURE,
                "template": lambda: self._spread_dynamics_strategy()
            },

            # STATISTICAL ARBITRAGE
            {
                "name": "Pairs Trading Signal",
                "edge_type": EdgeType.CORRELATION_ARBITRAGE,
                "template": lambda: self._pairs_trading_strategy()
            },
            {
                "name": "Statistical Mean Reversion",
                "edge_type": EdgeType.CORRELATION_ARBITRAGE,
                "template": lambda: self._stat_arb_strategy()
            },
            {
                "name": "Cointegration Breakdown",
                "edge_type": EdgeType.CORRELATION_ARBITRAGE,
                "template": lambda: self._cointegration_strategy()
            },
            {
                "name": "Z-Score Extreme Entry",
                "edge_type": EdgeType.CORRELATION_ARBITRAGE,
                "template": lambda: self._zscore_strategy()
            },

            # PATTERN RECOGNITION
            {
                "name": "Double Top/Bottom",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._double_pattern_strategy()
            },
            {
                "name": "Head and Shoulders",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._head_shoulders_strategy()
            },
            {
                "name": "Triangle Breakout",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._triangle_breakout_strategy()
            },
            {
                "name": "Flag Pattern Continuation",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._flag_strategy()
            },
            {
                "name": "Cup and Handle",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._cup_handle_strategy()
            },

            # ADVANCED/ML-INSPIRED
            {
                "name": "Multi-Timeframe Alignment",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._multi_timeframe_strategy()
            },
            {
                "name": "Trend Strength Adaptive",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._trend_strength_strategy()
            },
            {
                "name": "Regime Switching Model",
                "edge_type": EdgeType.VOLATILITY_REGIME,
                "template": lambda: self._regime_switch_strategy()
            },
            {
                "name": "Momentum Decay Model",
                "edge_type": EdgeType.MOMENTUM_MEAN_REVERSION,
                "template": lambda: self._momentum_decay_strategy()
            },
        ]

        # Randomly select strategies to test this cycle (exploration over exploitation)
        num_strategies_to_test = random.randint(3, 8)
        selected_strategies = random.sample(strategy_library, num_strategies_to_test)

        candidates = []
        for strategy in selected_strategies:
            try:
                candidate = strategy["template"]()
                # Add unique identifier for database tracking
                unique_id = str(uuid.uuid4())[:8]
                candidate = EdgeCandidate(
                    edge_type=candidate.edge_type,
                    description=f"{candidate.description} [{unique_id}]",
                    entry_conditions=candidate.entry_conditions,
                    exit_conditions=candidate.exit_conditions,
                    risk_params=candidate.risk_params,
                    confidence=candidate.confidence,
                    expected_return=candidate.expected_return,
                    expected_drawdown=candidate.expected_drawdown
                )
                candidates.append(candidate)
            except Exception as e:
                logger.warning(f"Failed to generate {strategy['name']}: {e}")

        logger.info(f"Generated {len(candidates)} diverse edge candidates from {num_strategies_to_test} unique strategies")
        return candidates
        return candidates

    async def fetch_solusdt_data(self, days: int = 90) -> Optional[pd.DataFrame]:
        """
        Fetch REAL SOLUSDT historical data from Binance.

        NEVER uses synthetic data - only real market data.

        Args:
            days: Number of days of historical data to fetch

        Returns:
            DataFrame with OHLCV data or None if fetch fails

        Raises:
            RuntimeError: If unable to fetch real data
        """
        import json
        import ssl
        import aiohttp

        # First, try to load from cache (cached real data only)
        cache_file = Path(f"./slate_core/palace_data/historical/SOLUSDT_1h.json")
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)

                df = pd.DataFrame(data)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)

                # Ensure required columns
                for col in ["open", "high", "low", "close", "volume"]:
                    if col not in df.columns:
                        return None

                # Calculate indicators if needed
                if "atr" not in df.columns:
                    df = self._calculate_indicators(df)

                logger.info(f"Loaded {len(df)} REAL candles from cache for SOLUSDT")
                return df

            except Exception as e:
                logger.warning(f"Failed to load cached data: {e}")

        # Fetch from Binance API - REAL DATA ONLY
        try:
            symbol = "SOLUSDT"
            interval = "1h"  # 1-hour candles for balance
            limit = min(days * 24, 1000)  # Binance limit

            base_url = "https://api.binance.com/api/v3/klines"

            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

            all_klines = []
            current_start = start_time

            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)

            async with aiohttp.ClientSession(connector=connector) as session:
                while current_start < end_time:
                    params = {
                        "symbol": symbol,
                        "interval": interval,
                        "startTime": current_start,
                        "endTime": end_time,
                        "limit": limit
                    }

                    async with session.get(base_url, params=params) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch real data from Binance: {response.status}")
                            raise RuntimeError(f"Cannot fetch real market data: HTTP {response.status}")

                        klines = await response.json()
                        if not klines:
                            break

                        all_klines.extend(klines)

                        # Update start time for next batch
                        current_start = klines[-1][0] + 1

                        if len(klines) < limit:
                            break

                        await asyncio.sleep(0.1)  # Rate limiting

            # Convert to DataFrame
            df = pd.DataFrame(all_klines, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            # Convert to numeric
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Validate we have real data
            if len(df) < 100:
                raise RuntimeError("Insufficient real data received")

            # Calculate technical indicators
            df = self._calculate_indicators(df)

            # Cache the REAL data
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_data = df.reset_index()[["timestamp", "open", "high", "low", "close", "volume"]].copy()
            cache_data["timestamp"] = cache_data["timestamp"].astype(str)  # Convert timestamps to strings
            with open(cache_file, 'w') as f:
                json.dump(cache_data.to_dict('records'), f)

            logger.info(f"Fetched {len(df)} REAL candles for {symbol} ({days} days)")
            logger.info(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

            return df

        except Exception as e:
            logger.error(f"CRITICAL: Cannot fetch REAL SOLUSDT data: {e}")
            raise RuntimeError(f"FAILED to fetch real market data. Discovery aborted. Error: {e}")

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate comprehensive technical indicators for diverse strategy detection."""

        # ATR (multiple periods)
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        df["atr"] = true_range.rolling(window=14).mean()
        df["atr_ratio"] = df["atr"] / df["atr"].rolling(window=50).mean()

        # Multiple ATR periods for diverse strategies
        for period in [7, 11, 20, 43]:
            df[f"atr_{period}"] = true_range.rolling(window=period).mean()

        # Bollinger Bands
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["std_20"] = df["close"].rolling(window=20).std()
        df["bollinger_upper"] = df["sma_20"] + 2 * df["std_20"]
        df["bollinger_lower"] = df["sma_20"] - 2 * df["std_20"]
        df["bollinger_width"] = (df["bollinger_upper"] - df["bollinger_lower"]) / df["sma_20"]

        # Volume indicators
        df["volume_avg"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_avg"]

        # Multiple EMA periods for diverse strategies
        for period in [7, 10, 14, 17, 20, 33, 36, 50, 68, 72, 200]:
            df[f"ema_{period}"] = df["close"].ewm(span=period).mean()

        # RSI (multiple periods)
        def calculate_rsi(series, period=14):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        df["rsi"] = calculate_rsi(df["close"], 14)
        for period in [10, 17, 38, 41, 43]:
            df[f"rsi_{period}"] = calculate_rsi(df["close"], period)

        # MACD
        ema_12 = df["close"].ewm(span=12).mean()
        ema_26 = df["close"].ewm(span=26).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Returns
        df["returns"] = df["close"].pct_change()

        # Rolling high/low for breakout strategies
        for period in [10, 20, 35, 50, 78, 120]:
            df[f"high_{period}"] = df["high"].rolling(window=period).max()
            df[f"low_{period}"] = df["low"].rolling(window=period).min()

        return df.dropna()

    def simulate_edge_backtest(
        self,
        df: pd.DataFrame,
        candidate: EdgeCandidate,
        config: EdgeBacktestConfig
    ) -> EdgeBacktestResult:
        """
        Simulate edge backtest with brutal realism.

        PRIMARY METRIC: USDT Profit (not percentage)
        BASELINE: Buy-and-hold comparison

        Applies:
        - Realistic fees (maker/taker)
        - Slippage based on volatility
        - Partial fills
        - Risk-managed position sizing
        """
        initial_capital = config.initial_capital
        capital = initial_capital
        position = None
        trades = []
        equity_curve = [capital]

        total_fees_usdt = 0
        total_slippage_bps = 0
        filled_signals = 0
        total_signals = 0

        # Price data for buy-and-hold calculation
        start_price = df.iloc[50]["close"]
        end_price = df.iloc[-1]["close"]

        for i in range(50, len(df) - 1):  # Skip warmup period
            current_price = df.iloc[i]["close"]
            atr = df.iloc[i]["atr"]

            # Check entry conditions based on edge type
            signal = self._check_entry_signal(df, i, candidate)
            total_signals += 1

            if signal and position is None:
                # Apply fill rate
                if np.random.random() > config.base_fill_rate:
                    continue  # Signal not filled

                filled_signals += 1

                # Calculate position size with risk management
                risk_amount = capital * config.max_position_size
                stop_distance = atr * config.stop_loss_atr_multiple

                if stop_distance > 0:
                    shares = min(
                        risk_amount / stop_distance,
                        capital * config.max_position_size / current_price
                    )
                else:
                    shares = capital * config.max_position_size / current_price

                # Apply partial fill
                if np.random.random() < config.partial_fill_probability:
                    fill_fraction = np.random.uniform(
                        config.partial_fill_min_size, 0.9
                    )
                    shares *= fill_fraction

                # Calculate entry with slippage
                slippage_bps = self._calculate_slippage(df, i, config)
                entry_price = current_price * (1 + slippage_bps / 10000 * signal)

                position = {
                    "entry_price": entry_price,
                    "shares": shares,
                    "entry_time": df.index[i],
                    "stop_loss": entry_price * (1 - 2 * stop_distance / entry_price * signal),
                    "take_profit": entry_price * (1 + 3 * stop_distance / entry_price * signal)
                }

            # Check exit conditions if in position
            elif position:
                exit_signal = False
                exit_reason = None

                # Check stop loss
                if signal > 0 and df.iloc[i]["low"] <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_signal = True
                    exit_reason = "stop_loss"
                elif signal < 0 and df.iloc[i]["high"] >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_signal = True
                    exit_reason = "stop_loss"

                # Check take profit
                elif signal > 0 and df.iloc[i]["high"] >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_signal = True
                    exit_reason = "take_profit"
                elif signal < 0 and df.iloc[i]["low"] <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_signal = True
                    exit_reason = "take_profit"

                # Check time-based exit
                elif (df.index[i] - position["entry_time"]).total_seconds() > 14400:  # 4 hours
                    exit_price = df.iloc[i]["close"]
                    exit_signal = True
                    exit_reason = "time_exit"

                # Apply exit
                if exit_signal:
                    # Apply exit slippage and fees
                    exit_slippage = self._calculate_slippage(df, i, config)
                    final_exit_price = exit_price * (1 - exit_slippage / 10000 * signal)

                    # Calculate PnL in USDT
                    if signal > 0:
                        pnl_usdt = (final_exit_price - position["entry_price"]) * position["shares"]
                    else:
                        pnl_usdt = (position["entry_price"] - final_exit_price) * position["shares"]

                    # Apply fees in USDT
                    entry_fee_usdt = position["entry_price"] * position["shares"] * config.taker_fee
                    exit_fee_usdt = final_exit_price * position["shares"] * config.taker_fee
                    total_fees_usdt += entry_fee_usdt + exit_fee_usdt
                    pnl_usdt -= entry_fee_usdt + exit_fee_usdt

                    capital += pnl_usdt
                    trades.append({
                        "pnl_usdt": pnl_usdt,
                        "return_pct": pnl_usdt / initial_capital,
                        "reason": exit_reason,
                        "entry": position["entry_price"],
                        "exit": final_exit_price,
                        "shares": position["shares"]
                    })

                    position = None
                    equity_curve.append(capital)

        # Calculate buy-and-hold baseline
        buy_hold_return_pct = (end_price - start_price) / start_price
        buy_hold_profit_usdt = initial_capital * buy_hold_return_pct

        # Calculate metrics
        if not trades:
            return self._create_failed_result(candidate, start_price, end_price, buy_hold_profit_usdt, buy_hold_return_pct)

        total_profit_usdt = capital - initial_capital
        total_return_pct = total_profit_usdt / initial_capital
        vs_buy_hold_usdt = total_profit_usdt - buy_hold_profit_usdt
        beat_market = total_profit_usdt > buy_hold_profit_usdt

        win_rate = sum(1 for t in trades if t["pnl_usdt"] > 0) / len(trades)

        # Calculate drawdown
        equity = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown_usdt = running_max - equity
        drawdown_pct = drawdown_usdt / running_max
        max_drawdown_usdt = drawdown_usdt.max()
        max_drawdown_pct = drawdown_pct.max()

        # Sharpe ratio (UNCAPPED)
        returns_pct = [t["return_pct"] for t in trades]
        if len(returns_pct) > 1 and np.std(returns_pct) > 0:
            sharpe = np.mean(returns_pct) / np.std(returns_pct) * np.sqrt(252)
        else:
            sharpe = 0

        # Profit factor
        gross_profit = sum(t["pnl_usdt"] for t in trades if t["pnl_usdt"] > 0)
        gross_loss = abs(sum(t["pnl_usdt"] for t in trades if t["pnl_usdt"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Validation failures
        failures = []
        if max_drawdown_pct > config.max_drawdown_limit:
            failures.append(f"Drawdown {max_drawdown_pct:.2%} exceeds {config.max_drawdown_limit:.2%}")

        if total_profit_usdt <= 0:
            failures.append(f"Negative profit ${total_profit_usdt:.2f}")

        passed = len(failures) == 0

        return EdgeBacktestResult(
            edge_type=candidate.edge_type.value,
            edge_description=candidate.description,
            total_profit_usdt=total_profit_usdt,
            total_return_pct=total_return_pct,
            final_capital=capital,
            initial_capital=initial_capital,
            buy_hold_profit_usdt=buy_hold_profit_usdt,
            buy_hold_return_pct=buy_hold_return_pct,
            vs_buy_hold_usdt=vs_buy_hold_usdt,
            beat_market=beat_market,
            max_drawdown_pct=max_drawdown_pct,
            max_drawdown_usdt=max_drawdown_usdt,
            sharpe_ratio=sharpe,
            sortino_ratio=0,
            calmar_ratio=0,
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_pnl_usdt=np.mean([t["pnl_usdt"] for t in trades]),
            monte_carlo_mean_profit_usdt=0,
            monte_carlo_std_profit_usdt=0,
            monte_carlo_5th_percentile_usdt=0,
            monte_carlo_win_rate=0,
            walk_forward_is_profitable=False,
            walk_forward_avg_profit_usdt=0,
            avg_slippage_bps=total_slippage_bps / len(trades) if trades else 0,
            avg_fill_rate=filled_signals / total_signals if total_signals > 0 else 0,
            total_fees_usdt=total_fees_usdt,
            period_start=df.index[0].isoformat(),
            period_end=df.index[-1].isoformat(),
            volatility_regime="unknown",
            start_price=start_price,
            end_price=end_price,
            passed_validation=passed,
            validation_failures=failures
        )

    def _check_entry_signal(self, df: pd.DataFrame, i: int, candidate: EdgeCandidate) -> int:
        """
        Check if entry conditions are met for diverse strategy types.

        Comprehensive signal generation for 35+ strategy templates.
        Returns: 1 (LONG), -1 (SHORT), 0 (no signal)
        """
        row = df.iloc[i]
        desc = candidate.description.lower()

        # Extract parameters from description when available
        import re

        # MOMENTUM STRATEGIES
        if "ema crossover" in desc:
            # EMA[period]/EMA[period*2] crossover
            ema_match = re.search(r'ema(\d+)', desc)
            if ema_match:
                period = int(ema_match.group(1))
                fast_col = f"ema_{period}"
                slow_col = f"ema_{period*2}"
                if fast_col in row.columns and slow_col in row.columns:
                    if row[fast_col] > row[slow_col] and row["close"] > row["sma_20"]:
                        return 1  # Golden cross - uptrend
                    elif row[fast_col] < row[slow_col] and row["close"] < row["sma_20"]:
                        return -1  # Death cross - downtrend

        elif "rsi momentum" in desc:
            # RI breakout strategy
            rsi_match = re.search(r'rsi(\d+)', desc)
            thresh_match = re.search(r'treshold=(\d+\.?\d*)', desc)
            if rsi_match and thresh_match:
                period = int(rsi_match.group(1))
                threshold = float(thresh_match.group(1))
                rsi_col = f"rsi_{period}" if period != 14 else "rsi"
                if rsi_col in row.columns:
                    if row[rsi_col] > (50 + threshold * 10) and row["volume_ratio"] > 1.0:
                        return 1  # Strong momentum up
                    elif row[rsi_col] < (50 - threshold * 10) and row["volume_ratio"] > 1.0:
                        return -1  # Strong momentum down

        elif "macd" in desc:
            # MACD histogram momentum
            if "macd_hist" in row.columns and row["macd_hist"] > 0:
                return 1  # Bullish momentum
            elif "macd_hist" in row.columns and row["macd_hist"] < 0:
                return -1  # Bearish momentum

        elif "breakout pullback" in desc:
            # Pullback to key level after breakout
            period_match = re.search(r'(\d+)-period', desc)
            if period_match:
                period = int(period_match.group(1))
                high_col = f"high_{period}"
                low_col = f"low_{period}"
                if high_col in row.columns and low_col in row.columns:
                    if row["close"] > row[high_col].shift(1) and row["close"] < row["close"].shift(1):
                        return 1  # Pullback after upside breakout
                    elif row["close"] < row[low_col].shift(1) and row["close"] > row["close"].shift(1):
                        return -1  # Pullback after downside breakout

        elif "trend strength" in desc or "adx" in desc.lower():
            # Adaptive based on trend strength
            if row["ema_50"] > row["ema_200"] and 30 < row["rsi"] < 70:
                return 1  # Pullback in uptrend
            elif row["ema_50"] < row["ema_200"] and 30 < row["rsi"] < 70:
                return -1  # Rally in downtrend

        # MEAN REVERSION STRATEGIES
        elif "bollinger" in desc and "reversion" in desc:
            # Bollinger band reversion
            bb_match = re.search(r'(\d+)-period', desc)
            std_match = re.search(r'([\d.]+) std', desc)
            if bb_match and std_match:
                period = int(bb_match.group(1))
                std_mult = float(std_match.group(1))
                if row["close"] > row["sma_20"] + std_mult * row["std_20"]:
                    return -1  # Short upper band
                elif row["close"] < row["sma_20"] - std_mult * row["std_20"]:
                    return 1  # Long lower band

        elif "rsi extremes" in desc or "rsi.*reversal" in desc:
            # RSI overbought/oversold reversal
            rsi_match = re.search(r'rsi(\d+)', desc)
            if rsi_match:
                period = int(rsi_match.group(1))
                rsi_col = f"rsi_{period}" if period != 14 else "rsi"
                if rsi_col in row.columns:
                    if row[rsi_col] > 70:  # Overbought
                        return -1  # Short reversal
                    elif row[rsi_col] < 30:  # Oversold
                        return 1  # Long reversal

        elif "support" in desc or "resistance" in desc or "sr" in desc:
            # Support/resistance bounce
            period_match = re.search(r'(\d+)-period', desc)
            if period_match:
                period = int(period_match.group(1))
                # Check if price is near recent high/low
                recent_high = row["close"].rolling(period).max().iloc[-1]
                recent_low = row["close"].rolling(period).min().iloc[-1]
                if abs(row["close"] - recent_low) / row["close"] < 0.01:
                    return 1  # Bounce off support
                elif abs(row["close"] - recent_high) / row["close"] < 0.01:
                    return -1  # Bounce off resistance

        elif "fibonacci" in desc or "fib" in desc:
            # Fibonacci retracement
            if row["close"] < row["sma_20"] and row["returns"] < -0.02:
                return 1  # Long at Fib support
            elif row["close"] > row["sma_20"] and row["returns"] > 0.02:
                return -1  # Short at Fib resistance

        # VOLATILITY STRATEGIES
        elif "atr breakout" in desc or "atr.*expansion" in desc:
            # ATR breakout strategy
            atr_match = re.search(r'atr(\d+)', desc)
            mult_match = re.search(r'>([\d.]+)x', desc)
            if atr_match and mult_match:
                period = int(atr_match.group(1))
                atr_col = f"atr_{period}" if period != 14 else "atr"
                if atr_col in row.columns:
                    atr_ratio = row[atr_col] / row[atr_col].rolling(50).mean().iloc[-1]
                    if atr_ratio > float(mult_match.group(1)):
                        if row["close"] > row["sma_20"]:
                            return 1  # Breakout up
                        else:
                            return -1  # Breakout down

        elif "volatility squeeze" in desc or "squeeze" in desc:
            # Volatility squeeze breakout
            if row["bollinger_width"] < row["bollinger_width"].rolling(50).quantile(0.1).iloc[-1]:
                # In squeeze - wait for breakout
                if abs(row["returns"]) > 0.01 and row["volume_ratio"] > 1.5:
                    if row["returns"] > 0:
                        return 1  # Upside breakout
                    else:
                        return -1  # Downside breakout

        elif "vix" in desc or "volatility.*spike" in desc:
            # Volatility spike fade
            if row["atr_ratio"] > 2.0 and abs(row["returns"]) > 0.02:
                if row["returns"] > 0:
                    return -1  # Fade up spike
                else:
                    return 1  # Fade down spike

        elif "gamma" in desc:
            # Gamma exposure scalping
            if row["volume_ratio"] > 2.0 and abs(row["returns"]) > 0.015:
                return 1 if row["returns"] > 0 else -1  # Ride momentum

        # TIME-BASED STRATEGIES
        elif "asian" in desc:
            # Asian session range fade
            hour = df.index[i].hour
            if 20 <= hour or hour <= 2:
                if row["volume_ratio"] < 0.8:
                    if row["close"] > row["sma_20"]:
                        return -1  # Short rise in quiet session
                    else:
                        return 1  # Long drop in quiet session

        elif "london" in desc:
            # London open breakout
            hour = df.index[i].hour
            if 7 <= hour <= 8:
                if abs(row["returns"]) > 0.001:
                    return 1 if row["returns"] > 0 else -1  # Follow breakout

        elif "ny" in desc or "new york" in desc or "13:00" in desc:
            # NY open momentum
            hour = df.index[i].hour
            if 13 <= hour <= 14:
                if row["ema_20"] > row["ema_50"]:
                    return 1  # Follow uptrend
                elif row["ema_20"] < row["ema_50"]:
                    return -1  # Follow downtrend

        elif "eod" in desc or "end of day" in desc:
            # End-of-day reversal
            hour = df.index[i].hour
            if 22 <= hour or hour <= 0:
                if abs(row["returns"][:5].sum()) > 0.02:  # Strong daily move
                    return -1 if row["returns"].iloc[-1] > 0 else 1  # Fade daily trend

        elif "weekend" in desc or "gap" in desc:
            # Weekend gap fade (check for large opening move)
            if i > 0 and abs(row["open"] - df.iloc[i-1]["close"]) / df.iloc[i-1]["close"] > 0.01:
                return -1 if row["open"] > df.iloc[i-1]["close"] else 1  # Fade gap

        elif "news" in desc or "cpi" in desc or "fomc" in desc:
            # News event volatility
            if row["volume_ratio"] > 1.5 and abs(row["returns"]) > 0.005:
                return 1 if row["returns"] > 0 else -1  # Follow news move

        # MARKET MICROSTRUCTURE
        elif "order flow" in desc or "tick" in desc:
            # Order flow / tick volume
            if row["volume_ratio"] > 1.5:
                if row["close"] > row["sma_20"] and row["volume_ratio"] > 2.0:
                    return 1  # Strong flow up
                elif row["close"] < row["sma_20"] and row["volume_ratio"] > 2.0:
                    return -1  # Strong flow down

        elif "sweep" in desc or "liquidity" in desc:
            # Liquidity sweep
            if row["volume_ratio"] > 2.0:
                candle_range = row["high"] - row["low"]
                if candle_range > 0:
                    wick_ratio = (row["high"] - row["close"]) / candle_range
                    if wick_ratio > 0.4 and row["close"] < row["open"]:
                        return 1  # Reject upside - go long
                    wick_ratio_lower = (row["close"] - row["low"]) / candle_range
                    if wick_ratio_lower > 0.4 and row["close"] > row["open"]:
                        return -1  # Reject downside - go short

        elif "iceberg" in desc or "absorption" in desc:
            # Iceberg / absorption
            if row["volume_ratio"] > 1.5 and abs(row["returns"]) < 0.005:
                return -1 if row["close"] > row["sma_20"] else 1  # Fade stalled move

        elif "spread" in desc:
            # Bid-ask spread dynamics
            if row["bollinger_width"] > 0.02:
                return -1 if row["close"] > row["sma_20"] + row["std_20"] else 1

        # STATISTICAL ARBITRAGE
        elif "pairs" in desc:
            # Pairs trading (use BTC correlation proxy)
            if abs(row["close"] - row["sma_20"]) > 2 * row["std_20"]:
                return -1 if row["close"] > row["sma_20"] else 1  # Mean reversion

        elif "statistical" in desc or "stat arb" in desc:
            # Statistical mean reversion
            dev_match = re.search(r'[-+]?([\d.]+)std', desc)
            if dev_match:
                threshold = float(dev_match.group(1))
                deviation = (row["close"] - row["sma_20"]) / row["std_20"]
                if abs(deviation) > threshold:
                    return -1 if deviation > 0 else 1  # Fade deviation

        elif "cointegration" in desc:
            # Cointegration breakdown
            if abs(row["close"] - row["sma_20"]) / row["close"] > 0.02:
                return -1 if row["close"] > row["sma_20"] else 1

        elif "z-score" in desc or "zscore" in desc:
            # Z-score extreme
            z_score = (row["close"] - row["sma_20"]) / row["std_20"]
            mult_match = re.search(r'z>([-+]?[\d.]+)', desc)
            if mult_match:
                threshold = float(mult_match.group(1))
                if abs(z_score) > threshold:
                    return -1 if z_score > 0 else 1  # Fade extreme z-score

        # PATTERN RECOGNITION
        elif "double" in desc:
            # Double top/bottom (simplified)
            if row["close"] > row["sma_20"] + 2 * row["std_20"] and row["rsi"] > 70:
                return -1  # Double top
            elif row["close"] < row["sma_20"] - 2 * row["std_20"] and row["rsi"] < 30:
                return 1  # Double bottom

        elif "head" in desc or "h&s" in desc:
            # Head and shoulders (simplified)
            if row["close"] > row["sma_20"] + 1.5 * row["std_20"] and row["volume_ratio"] < 0.8:
                return -1  # Potential top
            elif row["close"] < row["sma_20"] - 1.5 * row["std_20"] and row["volume_ratio"] < 0.8:
                return 1  # Potential bottom

        elif "triangle" in desc:
            # Triangle consolidation breakout
            if row["bollinger_width"] < row["bollinger_width"].rolling(20).mean().iloc[-1] * 0.7:
                if abs(row["returns"]) > 0.01:
                    return 1 if row["returns"] > 0 else -1  # Breakout direction

        elif "flag" in desc:
            # Flag pattern continuation
            if row["ema_20"] > row["ema_50"] and row["close"] > row["sma_20"]:
                return 1  # Bullish flag continuation
            elif row["ema_20"] < row["ema_50"] and row["close"] < row["sma_20"]:
                return -1  # Bearish flag continuation

        elif "cup" in desc:
            # Cup and handle
            if row["close"] > row["sma_20"] and row["volume_ratio"] > 1.2:
                return 1  # Cup completion

        # ADVANCED / ML-INSPIRED
        elif "multi-timeframe" in desc or "multi timeframe" in desc:
            # Multi-timeframe alignment
            if row["ema_20"] > row["ema_50"] > row["ema_200"]:
                return 1  # All timeframes bullish
            elif row["ema_20"] < row["ema_50"] < row["ema_200"]:
                return -1  # All timeframes bearish

        elif "regime" in desc:
            # Regime switching
            if row["atr_ratio"] < 1.0:  # Low vol regime
                if row["close"] > row["sma_20"]:
                    return 1  # Range trade - buy low
            else:  # High vol regime
                if row["returns"] > 0.01:
                    return 1  # Momentum trade
                elif row["returns"] < -0.01:
                    return -1  # Momentum trade short

        elif "momentum.*decay" in desc or "decay" in desc:
            # Momentum decay
            if abs(row["returns"]) > 0.015:
                # Check if momentum is slowing
                recent_returns = row["returns"].rolling(5).sum()
                earlier_returns = row["returns"].shift(5).rolling(5).sum()
                if abs(recent_returns) < abs(earlier_returns):
                    return -1 if row["returns"] > 0 else 1  # Fade slowing momentum

        # GENERIC FALLBACK for strategies not matched above
        # Use trend + RSI as default
        if row["ema_20"] > row["ema_50"] and 30 < row["rsi"] < 70:
            return 1  # Default long in uptrend
        elif row["ema_20"] < row["ema_50"] and 30 < row["rsi"] < 70:
            return -1  # Default short in downtrend

        return 0  # No signal

    def _calculate_slippage(self, df: pd.DataFrame, i: int, config: EdgeBacktestConfig) -> int:
        """Calculate slippage based on volatility."""
        base_slippage = config.base_slippage_bps
        if config.volatility_adjusted_slippage:
            vol_multiplier = min(df.iloc[i]["atr_ratio"], 3.0)
            return int(base_slippage * vol_multiplier)
        return base_slippage

    def _create_failed_result(
        self,
        candidate: EdgeCandidate,
        start_price: float = 0,
        end_price: float = 0,
        buy_hold_profit_usdt: float = 0,
        buy_hold_return_pct: float = 0
    ) -> EdgeBacktestResult:
        """Create a failed result for edges that don't generate trades."""
        return EdgeBacktestResult(
            edge_type=candidate.edge_type.value,
            edge_description=candidate.description,
            total_profit_usdt=0,
            total_return_pct=0,
            final_capital=10000,
            initial_capital=10000,
            buy_hold_profit_usdt=buy_hold_profit_usdt,
            buy_hold_return_pct=buy_hold_return_pct,
            vs_buy_hold_usdt=-buy_hold_profit_usdt,
            beat_market=False,
            max_drawdown_pct=0,
            max_drawdown_usdt=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            total_trades=0,
            win_rate=0,
            profit_factor=0,
            avg_trade_pnl_usdt=0,
            monte_carlo_mean_profit_usdt=0,
            monte_carlo_std_profit_usdt=0,
            monte_carlo_5th_percentile_usdt=0,
            monte_carlo_win_rate=0,
            walk_forward_is_profitable=False,
            walk_forward_avg_profit_usdt=0,
            avg_slippage_bps=0,
            avg_fill_rate=0,
            total_fees_usdt=0,
            period_start="",
            period_end="",
            volatility_regime="",
            start_price=start_price,
            end_price=end_price,
            passed_validation=False,
            validation_failures=["No trades generated"]
        )

    def run_monte_carlo_validation(
        self,
        df: pd.DataFrame,
        candidate: EdgeCandidate,
        config: EdgeBacktestConfig
    ) -> Tuple[float, float, float, float]:
        """
        Run Monte Carlo validation with 100+ paths.

        Returns:
            (mean_profit_usdt, std_profit_usdt, 5th_percentile_usdt, win_rate)
        """
        profits_usdt = []

        for _ in range(config.monte_carlo_paths):
            # Bootstrap resample the data
            sampled_indices = np.random.choice(len(df), size=len(df), replace=True)
            sampled_df = df.iloc[sampled_indices].copy()

            result = self.simulate_edge_backtest(sampled_df, candidate, config)
            profits_usdt.append(result.total_profit_usdt)

        return (
            np.mean(profits_usdt),
            np.std(profits_usdt),
            np.percentile(profits_usdt, 5),
            sum(1 for p in profits_usdt if p > 0) / len(profits_usdt)
        )

    def save_discovery(self, result: EdgeBacktestResult) -> bool:
        """Save discovery to database AND persistent memory (mempalace)."""
        try:
            # 1. Save to SQLite database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate rank score (USDT PROFIT is PRIMARY)
            rank_score = (
                result.total_profit_usdt * 1.0 -  # USDT profit is #1 priority
                result.max_drawdown_usdt * 0.5 +  # Penalize drawdown in USDT
                (result.vs_buy_hold_usdt if result.beat_market else 0) * 0.3  # Bonus for beating market
            )

            cursor.execute("""
                INSERT OR REPLACE INTO edge_discoveries (
                    edge_type, edge_description,
                    total_profit_usdt, total_return_pct, final_capital, initial_capital,
                    buy_hold_profit_usdt, buy_hold_return_pct, vs_buy_hold_usdt, beat_market,
                    max_drawdown_pct, max_drawdown_usdt, sharpe_ratio, sortino_ratio, calmar_ratio,
                    total_trades, win_rate, profit_factor, avg_trade_pnl_usdt,
                    monte_carlo_mean_profit_usdt, monte_carlo_std_profit_usdt,
                    monte_carlo_5th_percentile_usdt, monte_carlo_win_rate,
                    walk_forward_is_profitable, walk_forward_avg_profit_usdt,
                    avg_slippage_bps, avg_fill_rate, total_fees_usdt,
                    period_start, period_end, volatility_regime, start_price, end_price,
                    passed_validation, validation_failures, timestamp, rank_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.edge_type, result.edge_description,
                result.total_profit_usdt, result.total_return_pct, result.final_capital, result.initial_capital,
                result.buy_hold_profit_usdt, result.buy_hold_return_pct, result.vs_buy_hold_usdt, int(result.beat_market),
                result.max_drawdown_pct, result.max_drawdown_usdt, result.sharpe_ratio, result.sortino_ratio, result.calmar_ratio,
                result.total_trades, result.win_rate, result.profit_factor, result.avg_trade_pnl_usdt,
                result.monte_carlo_mean_profit_usdt, result.monte_carlo_std_profit_usdt,
                result.monte_carlo_5th_percentile_usdt, result.monte_carlo_win_rate,
                int(result.walk_forward_is_profitable), result.walk_forward_avg_profit_usdt,
                result.avg_slippage_bps, result.avg_fill_rate, result.total_fees_usdt,
                result.period_start, result.period_end, result.volatility_regime, result.start_price, result.end_price,
                int(result.passed_validation), json.dumps(result.validation_failures),
                result.timestamp, rank_score
            ))

            conn.commit()
            conn.close()

            # 2. Store in PERSISTENT MEMORY (GraphPalace/mempalace) for cross-cycle learning
            if self.memory and result.passed_validation:
                try:
                    memory_data = {
                        "edge_type": result.edge_type,
                        "edge_description": result.edge_description,
                        "total_profit_usdt": result.total_profit_usdt,
                        "total_return_pct": result.total_return_pct,
                        "max_drawdown_pct": result.max_drawdown_pct,
                        "sharpe_ratio": result.sharpe_ratio,
                        "beat_market": result.beat_market,
                        "vs_buy_hold_usdt": result.vs_buy_hold_usdt,
                        "monte_carlo_win_rate": result.monte_carlo_win_rate,
                        "passed_validation": result.passed_validation,
                        "period_start": result.period_start,
                        "period_end": result.period_end,
                        "start_price": result.start_price,
                        "end_price": result.end_price,
                        "volatility_regime": result.volatility_regime
                    }
                    memory_id = self.memory.store_discovery(memory_data)
                    logger.info(f"✓ Stored in persistent memory: {memory_id}")
                except Exception as e:
                    logger.warning(f"Failed to store in persistent memory: {e}")

            logger.info(f"Saved: {result.edge_description} | Profit: ${result.total_profit_usdt:.2f} | vs Buy-Hold: ${result.vs_buy_hold_usdt:.2f}")
            return True

        except Exception as e:
            logger.error(f"Error saving discovery: {e}")
            return False

    # ============================================================================
    # DIVERSE STRATEGY TEMPLATE METHODS
    # Each generates unique strategy variations with randomized parameters
    # ============================================================================

    def _random_params(self):
        """Generate random parameters for strategy variations."""
        import random
        return {
            'pos_size': round(random.uniform(0.01, 0.06), 3),
            'stop_atr': round(random.uniform(0.5, 2.5), 1),
            'take_profit': round(random.uniform(1.5, 4.0), 1),
            'period': random.randint(5, 50),
            'multiplier': round(random.uniform(0.5, 3.0), 1),
            'threshold': round(random.uniform(0.1, 2.0), 1)
        }

    # MOMENTUM STRATEGIES
    def _ema_crossover_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"EMA Crossover Momentum (EMA{p['period']}/EMA{p['period']*2})",
            entry_conditions={
                "fast_ema": f"EMA{p['period']}",
                "slow_ema": f"EMA{p['period']*2}",
                "signal": f"crossover with {p['threshold']} std confirmation"
            },
            exit_conditions={
                "take_profit": f"{p['take_profit']} * ATR",
                "stop_loss": f"{p['stop_atr']} * ATR",
                "time_stop": f"{p['period']} hours"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2, 2),
            expected_return=round(p['threshold'] * 0.01, 3),
            expected_drawdown=round(p['pos_size'] * 2, 2)
        )

    def _rsi_momentum_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"RSI Momentum Breakout (RSI{p['period']}, threshold={p['threshold']})",
            entry_conditions={
                "rsi_period": p['period'],
                "entry": f"RSI breaks {50 + p['threshold']*10}",
                "confirmation": "volume above average"
            },
            exit_conditions={
                "exit": f"RSI reaches {70 + p['threshold']*5}",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/3, 2),
            expected_return=round(p['threshold'] * 0.008, 3),
            expected_drawdown=round(p['pos_size'] * 1.8, 2)
        )

    def _macd_momentum_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"MACD Histogram Momentum (12,{p['period']},{p['period']*2})",
            entry_conditions={
                "macd_fast": "12",
                "macd_slow": str(p['period']),
                "macd_signal": str(p['period']*2),
                "signal": f"histogram turns positive with {p['threshold']*0.5} threshold"
            },
            exit_conditions={
                "exit": "histogram turns negative",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2.5, 2),
            expected_return=round(p['threshold'] * 0.007, 3),
            expected_drawdown=round(p['pos_size'] * 1.5, 2)
        )

    def _breakout_pullback_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Breakout Pullback Entry ({p['period']}-period high/low)",
            entry_conditions={
                "breakout": f"price breaks {p['period']}-period high/low",
                "pullback": f"retraces to {p['threshold']*0.3} of breakout",
                "entry": "on pullback completion"
            },
            exit_conditions={
                "target": f"{p['take_profit']} * risk",
                "stop": f"beyond pullback extreme by {p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2.2, 2),
            expected_return=round(p['threshold'] * 0.009, 3),
            expected_drawdown=round(p['pos_size'] * 1.6, 2)
        )

    # MEAN REVERSION STRATEGIES
    def _bollinger_reversion_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"Bollinger Band Mean Reversion ({p['period']}-period, {p['multiplier']} std)",
            entry_conditions={
                "bb_period": p['period'],
                "bb_std": p['multiplier'],
                "entry": f"price touches ±{p['multiplier']} std band",
                "confirmation": "RSI shows overbought/oversold"
            },
            exit_conditions={
                "target": "middle band (SMA)",
                "stop": f"{p['stop_atr']} ATR from entry"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.8, 2),
            expected_return=round(p['threshold'] * 0.006, 3),
            expected_drawdown=round(p['pos_size'] * 1.2, 2)
        )

    def _rsi_reversal_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"RSI Extremes Reversal (RSI{p['period']}, extreme={30-p['threshold']*5})",
            entry_conditions={
                "rsi_period": p['period'],
                "oversold": 30 - p['threshold']*5,
                "overbought": 70 + p['threshold']*5,
                "signal": "RSI shows extreme reading"
            },
            exit_conditions={
                "target": f"RSI returns to 50",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2, 2),
            expected_return=round(p['threshold'] * 0.007, 3),
            expected_drawdown=round(p['pos_size'] * 1.4, 2)
        )

    def _sr_bounce_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Support/Resistance Bounce ({p['period']}-period S/R levels)",
            entry_conditions={
                "sr_period": p['period'],
                "entry": f"price approaches {p['period']}-period S/R with {p['threshold']*0.5}% tolerance",
                "confirmation": "volume spike or rejection wick"
            },
            exit_conditions={
                "target": f"{p['take_profit']} * risk",
                "stop": f"{p['stop_atr']} ATR beyond S/R"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.5, 2),
            expected_return=round(p['threshold'] * 0.008, 3),
            expected_drawdown=round(p['pos_size'] * 1.3, 2)
        )

    def _fib_reversal_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"Fibonacci Retracement Fade ({p['threshold']}.0% retracement level)",
            entry_conditions={
                "fib_level": f"{p['threshold']}.0% retracement",
                "trend": f"{p['period']}-period trend identified",
                "entry": f"price retraces to {p['threshold']}.0% Fib level"
            },
            exit_conditions={
                "target": f"trend continuation to {p['take_profit']*0.3}%",
                "stop": f"next Fib level ±{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.6, 2),
            expected_return=round(p['threshold'] * 0.007, 3),
            expected_drawdown=round(p['pos_size'] * 1.5, 2)
        )

    # VOLATILITY STRATEGIES
    def _atr_breakout_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"ATR Breakout Expansion (ATR{p['period']}>{p['multiplier']}x average)",
            entry_conditions={
                "atr_period": p['period'],
                "expansion": f"ATR expands {p['multiplier']}x above average",
                "confirmation": "price breaks recent range"
            },
            exit_conditions={
                "target": f"{p['take_profit']} * initial ATR",
                "stop": f"{p['stop_atr']} * current ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.4, 2),
            expected_return=round(p['threshold'] * 0.01, 3),
            expected_drawdown=round(p['pos_size'] * 1.7, 2)
        )

    def _vol_squeeze_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"Volatility Squeeze Play (Bollinger width<{p['threshold']*0.1}%)",
            entry_conditions={
                "squeeze": f"Bollinger width in lowest {p['threshold']*10}% percentile",
                "breakout": "price breaks squeeze range with volume",
                "direction": "trade breakout direction"
            },
            exit_conditions={
                "target": f"{p['take_profit']} * ATR at breakout",
                "stop": f"opposite side of squeeze ±{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.3, 2),
            expected_return=round(p['threshold'] * 0.012, 3),
            expected_drawdown=round(p['pos_size'] * 1.4, 2)
        )

    def _vix_spike_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"VIX Proxy Spike Fade (vol>{p['multiplier']}x ATR, fade move)",
            entry_conditions={
                "vol_spike": f"volatility exceeds {p['multiplier']}x ATR",
                "price_move": f"price moves >{p['threshold']}% in {p['period']} bars",
                "direction": "fade the extreme move"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.5}% reversion",
                "stop": f"{p['stop_atr']} ATR extension"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.7, 2),
            expected_return=round(p['threshold'] * 0.006, 3),
            expected_drawdown=round(p['pos_size'] * 1.2, 2)
        )

    def _gamma_scalp_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Gamma Exposure Scalping (rapid moves, {p['period']}-bar hold)",
            entry_conditions={
                "gamma": f"price acceleration >{p['multiplier']} std",
                "volume": "above average",
                "entry": "ride gamma expansion"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.3}% move",
                "stop": f"{p['stop_atr']} ATR",
                "time_stop": f"{p['period']*5} minutes"
            },
            risk_params={"position_size": str(p['pos_size']*0.5)},
            confidence=round(p['threshold']/2.5, 2),
            expected_return=round(p['threshold'] * 0.004, 3),
            expected_drawdown=round(p['pos_size'], 2)
        )

    # TIME-BASED STRATEGIES
    def _asian_session_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.TIME_PATTERN,
            description=f"Asian Session Range Fade (UTC 20:00-02:00, vol adj={p['threshold']})",
            entry_conditions={
                "session": "Asian (UTC 20:00-02:00)",
                "range": f"price moves >{p['threshold']*0.5}% from session open",
                "entry": "fade the move at session extremes"
            },
            exit_conditions={
                "target": "return to session VWAP",
                "stop": f"{p['stop_atr']} ATR",
                "time_exit": "session end"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2, 2),
            expected_return=round(p['threshold'] * 0.007, 3),
            expected_drawdown=round(p['pos_size'] * 1.3, 2)
        )

    def _london_open_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.TIME_PATTERN,
            description=f"London Open Breakout (UTC 07:00-08:00, thresh={p['threshold']}%)",
            entry_conditions={
                "session": "London open (UTC 07:00-08:00)",
                "breakout": f"price breaks {p['period']}-period Asian range by {p['threshold']*0.3}%",
                "confirmation": "volume above Asian average"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.5}% of daily ATR",
                "stop": f"{p['stop_atr']} ATR",
                "time_exit": "12:00 UTC"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.5, 2),
            expected_return=round(p['threshold'] * 0.011, 3),
            expected_drawdown=round(p['pos_size'] * 1.5, 2)
        )

    def _ny_open_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.TIME_PATTERN,
            description=f"NY Open Momentum (UTC 13:00-14:00, trend={p['period']}h)",
            entry_conditions={
                "session": "NY open (UTC 13:00-14:00)",
                "trend": f"{p['period']}h trend direction pre-open",
                "entry": "continue trend direction on open"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.4}% move",
                "stop": f"{p['stop_atr']} ATR",
                "time_exit": "17:00 UTC"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.6, 2),
            expected_return=round(p['threshold'] * 0.009, 3),
            expected_drawdown=round(p['pos_size'] * 1.4, 2)
        )

    def _eod_reversal_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.TIME_PATTERN,
            description=f"End-of-Day Reversal (UTC 22:00-00:00, profit taking)",
            entry_conditions={
                "session": "EOD (UTC 22:00-00:00)",
                "signal": f"daily move >{p['threshold']}%, likely profit-taking",
                "entry": "fade the daily trend"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.3}% reversion",
                "stop": f"{p['stop_atr']} ATR",
                "time_exit": "midnight UTC"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2.2, 2),
            expected_return=round(p['threshold'] * 0.005, 3),
            expected_drawdown=round(p['pos_size'] * 1.1, 2)
        )

    def _weekend_gap_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.TIME_PATTERN,
            description=f"Weekend Gap Fade (gap>{p['threshold']}%, fade direction)",
            entry_conditions={
                "signal": f"weekend gap >{p['threshold']}%",
                "entry": "fade the gap direction",
                "confirmation": "first 1h candle shows rejection"
            },
            exit_conditions={
                "target": "gap fill (Friday close)",
                "stop": f"{p['stop_atr']} ATR beyond gap extreme"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.8, 2),
            expected_return=round(p['threshold'] * 0.006, 3),
            expected_drawdown=round(p['pos_size'] * 1.2, 2)
        )

    def _news_play_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.TIME_PATTERN,
            description=f"CPI/Pivot News Play (scheduled news, vol={p['multiplier']}x)",
            entry_conditions={
                "event": "CPI/FOMC/PPI releases",
                "pre_vol": f"volatility <{p['threshold']*0.5}% for 1h pre-event",
                "entry": "trade breakout direction post-event"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.6}% of pre-event range",
                "stop": f"{p['stop_atr']} ATR",
                "time_exit": "2h post-event"
            },
            risk_params={"position_size": str(p['pos_size']*0.8)},
            confidence=round(p['threshold']/2.5, 2),
            expected_return=round(p['threshold'] * 0.008, 3),
            expected_drawdown=round(p['pos_size'] * 1.6, 2)
        )

    # MARKET MICROSTRUCTURE
    def _order_flow_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Order Flow Imbalance (tick delta>{p['multiplier']}std, ride flow)",
            entry_conditions={
                "imbalance": f"tick delta >{p['multiplier']} std from mean",
                "confirmation": "price follows imbalance",
                "entry": "ride order flow direction"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.4}% move",
                "stop": f"flow reverses ±{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size']*0.7)},
            confidence=round(p['threshold']/3, 2),
            expected_return=round(p['threshold'] * 0.004, 3),
            expected_drawdown=round(p['pos_size'], 2)
        )

    def _liquidity_sweep_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Liquidity Sweep Reversal (wicks>{p['threshold']*20}%, reverse at sweep)",
            entry_conditions={
                "sweep": f"wick >{p['threshold']*20}% of candle, volume spike",
                "entry": "reverse after sweep completes",
                "confirmation": "quick rejection"
            },
            exit_conditions={
                "target": "return to sweep origin",
                "stop": f"{p['stop_atr']} ATR beyond sweep"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.6, 2),
            expected_return=round(p['threshold'] * 0.008, 3),
            expected_drawdown=round(p['pos_size'] * 1.3, 2)
        )

    def _iceberg_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Iceberg Order Detection (absorption at level, fade it)",
            entry_conditions={
                "absorption": f"large volume absorbed at price for >{p['period']*5} bars",
                "signal": "price fails to break through",
                "entry": "fade the breakout attempt"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.3}% against absorbed level",
                "stop": f"{p['stop_atr']} ATR beyond level"
            },
            risk_params={"position_size": str(p['pos_size']*0.6)},
            confidence=round(p['threshold']/2.8, 2),
            expected_return=round(p['threshold'] * 0.005, 3),
            expected_drawdown=round(p['pos_size'] * 1.1, 2)
        )

    def _tick_volume_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Tick Volume Anomaly (vol>{p['multiplier']}x avg, fade extreme)",
            entry_conditions={
                "anomaly": f"tick volume >{p['multiplier']}x average",
                "price": "price at extreme of recent range",
                "entry": "fade the volume spike direction"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.2}% reversion",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size']*0.5)},
            confidence=round(p['threshold']/3.5, 2),
            expected_return=round(p['threshold'] * 0.003, 3),
            expected_drawdown=round(p['pos_size'] * 0.8, 2)
        )

    def _spread_dynamics_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MARKET_MICROSTRUCTURE,
            description=f"Bid-Ask Spread Dynamics (spread>{p['multiplier']}x avg, mean revert)",
            entry_conditions={
                "spread": f"bid-ask spread >{p['multiplier']}x average",
                "signal": "widening spread indicates stress",
                "entry": "fade the move that caused widening"
            },
            exit_conditions={
                "target": "spread normalizes",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size']*0.4)},
            confidence=round(p['threshold']/4, 2),
            expected_return=round(p['threshold'] * 0.002, 3),
            expected_drawdown=round(p['pos_size'] * 0.6, 2)
        )

    # STATISTICAL ARBITRAGE
    def _pairs_trading_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.CORRELATION_ARBITRAGE,
            description=f"Pairs Trading Signal (SOL-BTC, z>{p['threshold']} std)",
            entry_conditions={
                "pair": "SOLUSDT vs BTCUSDT",
                "signal": f"ratio deviates >{p['threshold']} std from mean",
                "entry": "long underperformer, short outperformer"
            },
            exit_conditions={
                "target": "ratio returns to mean",
                "stop": f"{p['stop_atr']} std expansion"
            },
            risk_params={"position_size": str(p['pos_size']*0.5)},
            confidence=round(p['threshold']/2.2, 2),
            expected_return=round(p['threshold'] * 0.004, 3),
            expected_drawdown=round(p['pos_size'], 2)
        )

    def _stat_arb_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.CORRELATION_ARBITRAGE,
            description=f"Statistical Mean Reversion (dev>{p['threshold']}std, {p['period']}-bar mean)",
            entry_conditions={
                "deviation": f"price >{p['threshold']} std from {p['period']}-bar mean",
                "entry": "fade the deviation",
                "confirmation": "volume not confirming move"
            },
            exit_conditions={
                "target": "return to mean",
                "stop": f"{p['stop_atr']} std from entry"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2, 2),
            expected_return=round(p['threshold'] * 0.005, 3),
            expected_drawdown=round(p['pos_size'] * 1.2, 2)
        )

    def _cointegration_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.CORRELATION_ARBITRAGE,
            description=f"Cointegration Breakdown (residual>{p['threshold']}std, reversion)",
            entry_conditions={
                "coint": f"SOL-BTC cointegration residual >{p['threshold']} std",
                "entry": "trade convergence",
                "hedge": "delta-neutral approach"
            },
            exit_conditions={
                "target": "residual returns to zero",
                "stop": f"{p['stop_atr']} std residual expansion"
            },
            risk_params={"position_size": str(p['pos_size']*0.6)},
            confidence=round(p['threshold']/2.5, 2),
            expected_return=round(p['threshold'] * 0.003, 3),
            expected_drawdown=round(p['pos_size'] * 0.9, 2)
        )

    def _zscore_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.CORRELATION_ARBITRAGE,
            description=f"Z-Score Extreme Entry (z>{p['multiplier']}, fade signal)",
            entry_conditions={
                "zscore": f"price z-score >{p['multiplier']} or <{-p['multiplier']}",
                "entry": "fade the extreme z-score",
                "lookback": p['period']
            },
            exit_conditions={
                "target": "z-score returns to 0",
                "stop": f"z-score expands to ±{p['multiplier']*1.5}"
            },
            risk_params={"position_size": str(p['pos_size']*0.7)},
            confidence=round(p['threshold']/2.8, 2),
            expected_return=round(p['threshold'] * 0.004, 3),
            expected_drawdown=round(p['pos_size'] * 1.1, 2)
        )

    # PATTERN RECOGNITION
    def _double_pattern_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Double Top/Bottom ({p['period']}-bar pattern, confirm on break)",
            entry_conditions={
                "pattern": f"double top/bottom over {p['period']} bars",
                "neckline": f"{p['threshold']*0.5}% price level",
                "confirmation": "break of neckline with volume"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.4}% pattern height",
                "stop": f"beyond opposite peak by {p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.8, 2),
            expected_return=round(p['threshold'] * 0.009, 3),
            expected_drawdown=round(p['pos_size'] * 1.4, 2)
        )

    def _head_shoulders_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Head and Shoulders ({p['period']*2}-bar pattern, neckline break)",
            entry_conditions={
                "pattern": f"H&S over {p['period']*2} bars",
                "neckline": f"{p['threshold']*0.4}% level",
                "confirmation": "break with declining volume"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.5}% pattern height",
                "stop": f"beyond head by {p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.6, 2),
            expected_return=round(p['threshold'] * 0.01, 3),
            expected_drawdown=round(p['pos_size'] * 1.5, 2)
        )

    def _triangle_breakout_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"Triangle Breakout ({p['period']*3}-bar consolidation, directional break)",
            entry_conditions={
                "pattern": f"triangle over {p['period']*3} bars, narrowing range",
                "breakout": f"price breaks with >{p['threshold']*0.3}% move",
                "confirmation": "volume expansion"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.6}% of triangle base",
                "stop": f"opposite side ±{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.4, 2),
            expected_return=round(p['threshold'] * 0.011, 3),
            expected_drawdown=round(p['pos_size'] * 1.3, 2)
        )

    def _flag_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Flag Pattern Continuation ({p['period']}-bar flag, ride trend)",
            entry_conditions={
                "pattern": f"bull/bear flag over {p['period']} bars",
                "pole": f"strong prior move >{p['threshold']*0.5}%",
                "entry": "breakout of flag in pole direction"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.7}% of pole length",
                "stop": f"{p['stop_atr']} ATR beyond flag"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.5, 2),
            expected_return=round(p['threshold'] * 0.01, 3),
            expected_drawdown=round(p['pos_size'] * 1.4, 2)
        )

    def _cup_handle_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Cup and Handle ({p['period']*4}-bar pattern, breakout confirmation)",
            entry_conditions={
                "pattern": f"cup and handle over {p['period']*4} bars",
                "cup_depth": f"U-shape >{p['threshold']*0.4}% depth",
                "entry": "breakout from handle with volume"
            },
            exit_conditions={
                "target": f"return to cup rim +{p['take_profit']*0.3}%",
                "stop": f"bottom of cup ±{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.7, 2),
            expected_return=round(p['threshold'] * 0.012, 3),
            expected_drawdown=round(p['pos_size'] * 1.6, 2)
        )

    # ADVANCED/ML-INSPIRED
    def _multi_timeframe_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Multi-Timeframe Alignment ({p['period']}m/{p['period']*4}m/{p['period']*8}m aligned)",
            entry_conditions={
                "timeframes": f"{p['period']}m, {p['period']*4}m, {p['period']*8}m",
                "signal": "all timeframes show same direction",
                "entry": "enter when lower timeframe aligns"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.5}% of higher TF ATR",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.3, 2),
            expected_return=round(p['threshold'] * 0.011, 3),
            expected_drawdown=round(p['pos_size'] * 1.4, 2)
        )

    def _trend_strength_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Trend Strength Adaptive (ADX>{p['threshold']*10}, adapt position)",
            entry_conditions={
                "adx": f"ADX >{p['threshold']*10} (strong trend)",
                "entry": "pullback to key level in trend direction",
                "adapt": f"position size scaled by ADX/{p['threshold']*10}"
            },
            exit_conditions={
                "target": f"next support/resistance ({p['take_profit']*0.4}% ATR)",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.4, 2),
            expected_return=round(p['threshold'] * 0.01, 3),
            expected_drawdown=round(p['pos_size'] * 1.3, 2)
        )

    def _regime_switch_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.VOLATILITY_REGIME,
            description=f"Regime Switching Model (detect trend/range, switch strategy)",
            entry_conditions={
                "regime": f"detect market regime (trend/range) using {p['period']}-bar ATR",
                "trend_strategy": "momentum if trending",
                "range_strategy": "mean reversion if ranging"
            },
            exit_conditions={
                "target": f"{p['take_profit']*0.5}% of regime-specific target",
                "stop": f"{p['stop_atr']} ATR or regime change"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/1.6, 2),
            expected_return=round(p['threshold'] * 0.009, 3),
            expected_drawdown=round(p['pos_size'] * 1.2, 2)
        )

    def _momentum_decay_strategy(self):
        p = self._random_params()
        return EdgeCandidate(
            edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
            description=f"Momentum Decay Model (rate of change slowing, fade)",
            entry_conditions={
                "momentum": f"{p['period']}-bar ROC shows strong move",
                "decay": f"rate of change declining over {p['period']//2} bars",
                "entry": "fade as momentum decays"
            },
            exit_conditions={
                "target": f"{p['threshold']*0.3}% reversal",
                "stop": f"{p['stop_atr']} ATR"
            },
            risk_params={"position_size": str(p['pos_size'])},
            confidence=round(p['threshold']/2, 2),
            expected_return=round(p['threshold'] * 0.006, 3),
            expected_drawdown=round(p['pos_size'] * 1.1, 2)
        )

    def generate_nl_strategy(self, description: str, provider: str = "mock", api_key: Optional[str] = None) -> Optional[EdgeCandidate]:
        """
        Generate an EdgeCandidate from natural language description.

        Args:
            description: Natural language strategy description (e.g., "Test a mean reversion strategy when RSI is below 30")
            provider: LLM provider ("openai", "anthropic", "ollama", "mock")
            api_key: API key for the provider (if required)

        Returns:
            EdgeCandidate or None if generation fails

        Example:
            >>> candidate = engine.generate_nl_strategy("Test a breakout strategy when volume is high")
            >>> result = engine.simulate_edge_backtest(df, candidate, config)
        """
        try:
            from .nl_strategy_generator import create_nl_generator, NLStrategyRequest

            # Create generator
            generator = create_nl_generator(provider=provider, api_key=api_key)

            # Create request
            request = NLStrategyRequest(description=description)

            # Generate strategy
            result = generator.generate_strategy(request)

            if not result.success:
                logger.error(f"Failed to generate strategy from description: {result.error}")
                return None

            # Convert to EdgeCandidate
            try:
                edge_type = EdgeType(result.edge_type.lower())
            except ValueError:
                # Default to momentum if unknown type
                edge_type = EdgeType.MOMENTUM_MEAN_REVERSION

            candidate = EdgeCandidate(
                edge_type=edge_type,
                description=result.description,
                entry_conditions=result.entry_conditions,
                exit_conditions=result.exit_conditions,
                risk_params=result.risk_params,
                confidence=result.confidence,
                expected_return=result.expected_return,
                expected_drawdown=result.expected_drawdown
            )

            logger.info(f"Generated NL strategy: {result.description}")
            logger.info(f"  Type: {result.edge_type}")
            logger.info(f"  Explanation: {result.explanation}")

            return candidate

        except ImportError as e:
            logger.error(f"Natural language generator not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating NL strategy: {e}")
            return None

    async def run_discovery_cycle_with_checkpoint(
        self,
        resume_cycle_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run discovery cycle with checkpoint support for crash recovery.

        Inspired by TradingAgents' checkpoint resume system, this method:
        - Saves state after each candidate tested
        - Can resume from last checkpoint if interrupted
        - Provides progress tracking and error recovery

        Args:
            resume_cycle_id: Optional cycle ID to resume from

        Returns:
            Discovery results with cycle information
        """
        if not self.checkpoint_manager:
            logger.warning("Checkpoint manager not enabled - using standard discovery cycle")
            return await self.run_discovery_cycle()

        # Handle resume or start new cycle
        if resume_cycle_id:
            if not self.checkpoint_manager.can_resume(resume_cycle_id):
                logger.error(f"Cannot resume cycle {resume_cycle_id} - not found or already complete")
                return {"status": "failed", "reason": "cannot_resume"}

            resume_state = self.checkpoint_manager.get_resume_state(resume_cycle_id)
            logger.info(f"Resuming from step {resume_state['resume_from_index']} for cycle {resume_cycle_id}")

            cycle_id = resume_cycle_id
            start_index = resume_state['resume_from_index']
            completed_results = resume_state['completed_results']
        else:
            # Start new cycle
            candidates = self.generate_edge_candidates()
            cycle_id = self.checkpoint_manager.start_cycle(len(candidates))
            start_index = 0
            completed_results = []
            logger.info(f"Starting new discovery cycle {cycle_id} with {len(candidates)} candidates")

        try:
            # Fetch data
            try:
                df = await self.fetch_solusdt_data(days=90)
            except RuntimeError as e:
                logger.error(f"Cannot fetch real data: {e}")
                return {"status": "failed", "reason": "cannot_fetch_real_data", "error": str(e)}

            if df is None or len(df) < 1000:
                logger.error("Insufficient real data for discovery")
                return {"status": "failed", "reason": "insufficient_real_data"}

            logger.info(f"Loaded {len(df)} REAL candles for backtesting")
            logger.info(f"Period: {df.index[0]} to {df.index[-1]}")

            # Get candidates (new or resume)
            if resume_cycle_id:
                candidates = self.generate_edge_candidates()
            else:
                candidates = self.generate_edge_candidates()

            # Test candidates starting from checkpoint
            results = []
            for i in range(start_index, len(candidates)):
                candidate = candidates[i]
                logger.info(f"Testing edge {i+1}/{len(candidates)}: {candidate.description}")

                try:
                    # Single path backtest
                    result = self.simulate_edge_backtest(df, candidate, self.config)

                    # Monte Carlo validation if base result is promising
                    if result.total_profit_usdt > 0 and result.max_drawdown_pct < 0.25:
                        mc_mean, mc_std, mc_5th, mc_win = self.run_monte_carlo_validation(
                            df, candidate, self.config
                        )
                        result.monte_carlo_mean_profit_usdt = mc_mean
                        result.monte_carlo_std_profit_usdt = mc_std
                        result.monte_carlo_5th_percentile_usdt = mc_5th
                        result.monte_carlo_win_rate = mc_win

                    # Save result to database
                    self.save_discovery(result)

                    # Save checkpoint
                    result_data = {
                        "description": result.edge_description,
                        "profit_usdt": result.total_profit_usdt,
                        "return_pct": result.total_return_pct,
                        "beat_market": result.beat_market
                    }

                    self.checkpoint_manager.save_candidate_result(
                        candidate_index=i,
                        edge_type=candidate.edge_type.value,
                        description=candidate.description,
                        status='success',
                        result_data=result_data
                    )

                    self.checkpoint_manager.save_checkpoint(
                        stage='backtesting',
                        tested_index=i,
                        result=result_data
                    )

                    results.append(result)

                except Exception as e:
                    logger.error(f"Error testing edge {candidate.description}: {e}")

                    # Save error checkpoint
                    self.checkpoint_manager.save_candidate_result(
                        candidate_index=i,
                        edge_type=candidate.edge_type.value,
                        description=candidate.description,
                        status='error',
                        error_message=str(e)
                    )

                    self.checkpoint_manager.save_checkpoint(
                        stage='backtesting',
                        tested_index=i,
                        error=str(e)
                    )

            # Combine completed and new results
            all_results = completed_results + results

            # Convert EdgeBacktestResult objects to dicts for sorting and filtering
            formatted_results = []
            for r in all_results:
                if isinstance(r, dict):
                    formatted_results.append(r)
                else:
                    # EdgeBacktestResult object
                    formatted_results.append({
                        'total_profit_usdt': float(r.total_profit_usdt),
                        'total_return_pct': float(r.total_return_pct),
                        'beat_market': bool(r.beat_market),
                        'sharpe_ratio': float(r.sharpe_ratio),
                        'max_drawdown_pct': float(r.max_drawdown_pct),
                        'win_rate': float(r.win_rate),
                        'description': r.edge_description,
                        'passed_validation': bool(r.passed_validation)
                    })

            # Rank results by USDT profit
            passed = [r for r in formatted_results if r.get('passed_validation', True)]
            passed.sort(key=lambda x: x.get('total_profit_usdt', 0), reverse=True)

            # Mark cycle as complete
            self.checkpoint_manager.mark_complete(cycle_id)

            # Log to reflection memory if enabled
            if self.reflection_memory:
                try:
                    market_conditions = {
                        'regime': 'unknown',
                        'volatility': 'unknown'
                    }

                    self.reflection_memory.log_discovery_cycle(
                        cycle_id=cycle_id,
                        results=formatted_results,
                        top_performers=passed[:5],
                        market_conditions=market_conditions
                    )

                    logger.info("Discovery cycle logged to reflection memory")
                except Exception as e:
                    logger.warning(f"Failed to log to reflection memory: {e}")

            logger.info(f"Discovery cycle {cycle_id} complete: {len(passed)}/{len(all_results)} edges passed")

            return {
                "status": "success",
                "cycle_id": cycle_id,
                "total_candidates": len(candidates),
                "passed_validation": len(passed),
                "resumed": resume_cycle_id is not None,
                "top_edges": [
                    {
                        "description": r.get("edge_description", r.get("description", "")),
                        "profit_usdt": r.get("total_profit_usdt", 0),
                        "return_pct": r.get("total_return_pct", 0),
                        "drawdown_pct": r.get("max_drawdown_pct", 0),
                        "beat_market": r.get("beat_market", False),
                        "vs_buy_hold_usdt": r.get("vs_buy_hold_usdt", 0),
                        "sharpe": r.get("sharpe_ratio", 0),
                        "mc_win_rate": r.get("monte_carlo_win_rate", 0)
                    }
                    for r in passed[:5]
                ]
            }

        except Exception as e:
            logger.error(f"Discovery cycle failed: {e}")
            return {"status": "failed", "reason": "cycle_error", "error": str(e)}

    async def run_discovery_cycle(self) -> Dict[str, Any]:
        """
        Run a complete discovery cycle with REAL data only.

        1. Generate edge candidates
        2. Fetch REAL SOLUSDT data (NEVER synthetic)
        3. Backtest each edge with brutal realism
        4. Run Monte Carlo validation (100+ paths)
        5. Save and rank by USDT profit
        """
        logger.info("Starting edge discovery cycle with REAL data only...")

        # Generate candidates
        candidates = self.generate_edge_candidates()
        logger.info(f"Generated {len(candidates)} edge candidates")

        # Fetch REAL data (will raise error if unable to get real data)
        try:
            df = await self.fetch_solusdt_data(days=90)
        except RuntimeError as e:
            logger.error(f"Cannot fetch real data: {e}")
            return {"status": "failed", "reason": "cannot_fetch_real_data", "error": str(e)}

        if df is None or len(df) < 1000:
            logger.error("Insufficient real data for discovery")
            return {"status": "failed", "reason": "insufficient_real_data"}

        logger.info(f"Loaded {len(df)} REAL candles for backtesting")
        logger.info(f"Period: {df.index[0]} to {df.index[-1]}")
        logger.info(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

        # Test each edge
        results = []
        for candidate in candidates:
            logger.info(f"Testing edge: {candidate.description}")

            try:
                # Single path backtest
                result = self.simulate_edge_backtest(df, candidate, self.config)

                # Monte Carlo validation if base result is promising
                if result.total_profit_usdt > 0 and result.max_drawdown_pct < 0.25:
                    mc_mean, mc_std, mc_5th, mc_win = self.run_monte_carlo_validation(
                        df, candidate, self.config
                    )
                    result.monte_carlo_mean_profit_usdt = mc_mean
                    result.monte_carlo_std_profit_usdt = mc_std
                    result.monte_carlo_5th_percentile_usdt = mc_5th
                    result.monte_carlo_win_rate = mc_win

                # Save result
                self.save_discovery(result)
                results.append(result)

            except Exception as e:
                logger.error(f"Error testing edge {candidate.description}: {e}")

        # Rank results by USDT profit
        passed = [r for r in results if r.passed_validation]
        passed.sort(key=lambda x: x.total_profit_usdt, reverse=True)

        # Log to reflection memory if enabled
        if self.reflection_memory:
            try:
                import uuid
                cycle_id = str(uuid.uuid4())
                market_conditions = {
                    'regime': 'unknown',
                    'volatility': 'unknown'
                }

                # Convert results to format expected by reflection memory
                formatted_results = []
                for r in results:
                    formatted_results.append({
                        'total_profit_usdt': float(r.total_profit_usdt),
                        'total_return_pct': float(r.total_return_pct),
                        'beat_market': bool(r.beat_market),
                        'sharpe_ratio': float(r.sharpe_ratio),
                        'max_drawdown_pct': float(r.max_drawdown_pct),
                        'win_rate': float(r.win_rate),
                        'description': r.edge_description,
                        'passed_validation': bool(r.passed_validation)
                    })

                self.reflection_memory.log_discovery_cycle(
                    cycle_id=cycle_id,
                    results=formatted_results,
                    top_performers=passed[:5],
                    market_conditions=market_conditions
                )

                logger.info("Discovery cycle logged to reflection memory")
            except Exception as e:
                logger.warning(f"Failed to log to reflection memory: {e}")

        logger.info(f"Discovery cycle complete: {len(passed)}/{len(results)} edges passed validation")

        return {
            "status": "success",
            "total_candidates": len(candidates),
            "passed_validation": len(passed),
            "top_edges": [
                {
                    "description": r.edge_description,
                    "profit_usdt": r.total_profit_usdt,
                    "return_pct": r.total_return_pct,
                    "drawdown_pct": r.max_drawdown_pct,
                    "beat_market": r.beat_market,
                    "vs_buy_hold_usdt": r.vs_buy_hold_usdt,
                    "sharpe": r.sharpe_ratio,
                    "mc_win_rate": r.monte_carlo_win_rate
                }
                for r in passed[:5]
            ]
        }


async def run_edge_discovery():
    """Run edge discovery with REAL data and print USDT profit results."""
    engine = EdgeDiscoveryEngine()
    results = await engine.run_discovery_cycle()

    print("\n" + "="*80)
    print("EDGE DISCOVERY RESULTS - USDT PROFIT FOCUS")
    print("="*80)

    if results["status"] == "success":
        print(f"\nTested {results['total_candidates']} edge candidates on REAL SOLUSDT data")
        print(f"Passed validation: {results['passed_validation']}")

        if results["top_edges"]:
            print("\n" + "-"*80)
            print("TOP PERFORMING EDGES (Ranked by USDT Profit)")
            print("-"*80)
            for i, edge in enumerate(results["top_edges"], 1):
                print(f"\n{i}. {edge['description']}")
                print(f"   PROFIT: ${edge['profit_usdt']:.2f} ({edge['return_pct']:.2%})")
                print(f"   vs Buy-Hold: ${edge['vs_buy_hold_usdt']:+.2f} {'✓' if edge['beat_market'] else '✗'}")
                print(f"   Drawdown: {edge['drawdown_pct']:.2%} (${edge.get('drawdown_usdt', 0):.2f})")
                print(f"   Sharpe: {edge['sharpe']:.2f}")
                print(f"   MC Win Rate: {edge['mc_win_rate']:.1%}")
            print("-"*80)
    else:
        reason = results.get('reason', 'unknown')
        print(f"\n❌ Discovery failed: {reason}")
        if reason == "cannot_fetch_real_data":
            print("   CRITICAL: Only REAL market data is acceptable.")
            print("   The system will NOT use synthetic data.")

    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_edge_discovery())
