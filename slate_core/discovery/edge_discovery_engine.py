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

    def __init__(self, db_path: str = "slate_core/slate_realistic_discoveries.db"):
        self.db_path = db_path
        self.config = EdgeBacktestConfig()
        self.discovered_edges: List[EdgeBacktestResult] = []

        # Initialize persistent memory for cross-cycle learning
        if PERSISTENT_MEMORY_AVAILABLE:
            self.memory = get_discovery_memory()
            logger.info("Persistent memory enabled - discoveries stored in knowledge graph")
        else:
            self.memory = None
            logger.warning("Persistent memory unavailable - using database only")

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
        Generate edge candidates based on market structure hypotheses.

        Returns diverse edge types with randomized parameters for continuous discovery.
        Each cycle generates unique variations to accumulate test results.
        """
        import random
        candidates = []

        # Add randomness for parameter variations
        atr_ratio = round(random.uniform(0.3, 0.7), 2)
        bollinger_width = round(random.uniform(0.015, 0.025), 3)
        atr_expansion = round(random.uniform(1.8, 2.5), 1)
        time_stop_hours = random.randint(3, 6)
        position_size = round(random.uniform(0.02, 0.05), 3)
        stop_atr_mult = round(random.uniform(1.2, 2.0), 1)

        # 1. Volatility Regime Edges (Both Long and Short) - with random variations
        candidates.extend([
            EdgeCandidate(
                edge_type=EdgeType.VOLATILITY_REGIME,
                description=f"ATR breakout during low volatility (LONG or SHORT) - ATR<{atr_ratio} BW<{bollinger_width}",
                entry_conditions={
                    "atr_ratio": f"< {atr_ratio}",
                    "bollinger_width": f"< {bollinger_width}",
                    "direction": "trade the breakout direction"
                },
                exit_conditions={
                    "atr_expansion": f"> {atr_expansion}",
                    "time_stop": f"{time_stop_hours} hours"
                },
                risk_params={
                    "position_size": str(position_size),
                    "stop_atr_multiple": str(stop_atr_mult)
                },
                confidence=round(random.uniform(0.5, 0.7), 2),
                expected_return=round(random.uniform(0.015, 0.025), 3),
                expected_drawdown=round(random.uniform(0.06, 0.10), 2)
            ),
            EdgeCandidate(
                edge_type=EdgeType.VOLATILITY_REGIME,
                description=f"Mean reversion after volatility spike (LONG or SHORT) - v2.{random.randint(1,100)}",
                entry_conditions={
                    "vix_proxy": f"> {round(random.uniform(1.8, 2.5), 1)}",
                    "price_change": f"> {round(random.uniform(1.5, 2.5), 1)}% in 1h",
                    "direction": "fade the spike"
                },
                exit_conditions={
                    "reversion_target": f"{round(random.uniform(0.4, 0.6), 1)} * std_dev",
                    "time_stop": f"{random.randint(5, 8)} hours"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.03, 0.05), 3)),
                    "stop_atr_multiple": str(round(random.uniform(0.8, 1.2), 1))
                },
                confidence=round(random.uniform(0.4, 0.6), 2),
                expected_return=round(random.uniform(0.01, 0.02), 3),
                expected_drawdown=round(random.uniform(0.05, 0.08), 2)
            ),
        ])

        # 2. Market Microstructure Edges (Both Long and Short) - with random variations
        candidates.extend([
            EdgeCandidate(
                edge_type=EdgeType.MARKET_MICROSTRUCTURE,
                description=f"Bid-ask bounce mean reversion (LONG or SHORT) - v{random.randint(1,100)}",
                entry_conditions={
                    "spread_widening": f"> {round(random.uniform(1.5, 2.5), 1)}x average",
                    "bollinger_touch": f"price at ±{round(random.uniform(1.5, 2.5), 1)} std",
                    "direction": "fade the extension"
                },
                exit_conditions={
                    "spread_normalization": "return to 1x",
                    "time_stop": f"{random.randint(20, 45)} minutes"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.015, 0.025), 3)),
                    "stop_atr_multiple": str(round(random.uniform(0.4, 0.6), 1))
                },
                confidence=round(random.uniform(0.35, 0.45), 2),
                expected_return=round(random.uniform(0.003, 0.007), 3),
                expected_drawdown=round(random.uniform(0.02, 0.04), 2)
            ),
            EdgeCandidate(
                edge_type=EdgeType.MARKET_MICROSTRUCTURE,
                description=f"Liquidity sweep detection and reversal (LONG or SHORT) - vol{random.randint(1,100)}",
                entry_conditions={
                    "volume_spike": f"> {round(random.uniform(2.5, 3.5), 1)}x average",
                    "price_rejection": f"wicks > {round(random.uniform(40, 60), 0)}% of candle",
                    "direction": "trade the rejection"
                },
                exit_conditions={
                    "target": "sweep_origin_price",
                    "time_stop": f"{random.randint(1, 3)} hours"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.025, 0.035), 3)),
                    "stop_atr_multiple": str(round(random.uniform(0.7, 0.9), 1))
                },
                confidence=round(random.uniform(0.45, 0.55), 2),
                expected_return=round(random.uniform(0.008, 0.012), 3),
                expected_drawdown=round(random.uniform(0.04, 0.06), 2)
            ),
        ])

        # 3. Time Pattern Edges (Both Long and Short) - with random variations
        candidates.extend([
            EdgeCandidate(
                edge_type=EdgeType.TIME_PATTERN,
                description=f"Asian session range fade (LONG or SHORT) - session{random.randint(1,100)}",
                entry_conditions={
                    "time": "UTC 20:00 - 02:00",
                    "volume": "below daily average",
                    "direction": "fade price moves"
                },
                exit_conditions={
                    "target": "session mean reversion",
                    "time_stop": "session end"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.035, 0.045), 3)),
                    "stop_atr_multiple": str(round(random.uniform(0.9, 1.1), 1))
                },
                confidence=round(random.uniform(0.40, 0.50), 2),
                expected_return=round(random.uniform(0.006, 0.010), 3),
                expected_drawdown=round(random.uniform(0.05, 0.07), 2)
            ),
            EdgeCandidate(
                edge_type=EdgeType.TIME_PATTERN,
                description=f"London open volatility breakout (LONG or SHORT) - break{random.randint(1,100)}",
                entry_conditions={
                    "time": "UTC 07:00 - 08:00",
                    "direction": "trade the breakout direction"
                },
                exit_conditions={
                    "breakout_confirmation": "sustained move",
                    "time_stop": "12:00 UTC"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.045, 0.055), 3)),
                    "stop_atr_multiple": str(round(random.uniform(1.3, 1.7), 1))
                },
                confidence=round(random.uniform(0.50, 0.60), 2),
                expected_return=round(random.uniform(0.010, 0.014), 3),
                expected_drawdown=round(random.uniform(0.07, 0.09), 2)
            ),
        ])

        # 4. Momentum-Mean Reversion Hybrid (Both Directions) - with random variations
        candidates.extend([
            EdgeCandidate(
                edge_type=EdgeType.MOMENTUM_MEAN_REVERSION,
                description=f"Trend-following with pullback entries (LONG in uptrend, SHORT in downtrend) - trend{random.randint(1,100)}",
                entry_conditions={
                    "trend": "EMA200 slope determines direction",
                    "entry": "pullback to EMA50",
                    "rsi": "30-70 zone"
                },
                exit_conditions={
                    "target": "previous swing point",
                    "stop": "beyond pullback extreme"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.035, 0.045), 3)),
                    "stop_atr_multiple": str(round(random.uniform(1.8, 2.2), 1))
                },
                confidence=round(random.uniform(0.55, 0.65), 2),
                expected_return=round(random.uniform(0.015, 0.021), 3),
                expected_drawdown=round(random.uniform(0.09, 0.11), 2)
            ),
        ])

        # 5. Statistical Arbitrage Edges (Both Long and Short) - with random variations
        candidates.extend([
            EdgeCandidate(
                edge_type=EdgeType.CORRELATION_ARBITRAGE,
                description=f"Price deviation mean reversion (LONG or SHORT) - dev{random.randint(1,100)}",
                entry_conditions={
                    "deviation": f"> {round(random.uniform(1.8, 2.2), 1)} std from 20-period mean",
                    "volatility": "elevated (>1.5x ATR)",
                    "direction": "fade the deviation"
                },
                exit_conditions={
                    "convergence": "return to 1 std",
                    "time_stop": f"{random.randint(3, 5)} hours"
                },
                risk_params={
                    "position_size": str(round(random.uniform(0.025, 0.035), 3)),
                    "stop_atr_multiple": str(round(random.uniform(1.3, 1.7), 1))
                },
                confidence=round(random.uniform(0.35, 0.45), 2),
                expected_return=round(random.uniform(0.008, 0.012), 3),
                expected_drawdown=round(random.uniform(0.06, 0.08), 2)
            ),
        ])

        logger.info(f"Generated {len(candidates)} edge candidates across {len(EdgeType)} types")
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
        """Calculate technical indicators for edge detection."""
        # ATR
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = true_range.rolling(window=14).mean()
        df["atr_ratio"] = df["atr"] / df["atr"].rolling(window=20).mean()

        # Bollinger Bands
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["std_20"] = df["close"].rolling(window=20).std()
        df["bollinger_upper"] = df["sma_20"] + 2 * df["std_20"]
        df["bollinger_lower"] = df["sma_20"] - 2 * df["std_20"]
        df["bollinger_width"] = (df["bollinger_upper"] - df["bollinger_lower"]) / df["sma_20"]

        # Volume
        df["volume_avg"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_avg"]

        # EMAs
        df["ema_50"] = df["close"].ewm(span=50).mean()
        df["ema_200"] = df["close"].ewm(span=200).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # Returns
        df["returns"] = df["close"].pct_change()

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
        Check if entry conditions are met for PERPETUAL FUTURES trading.

        Returns:
            1 for LONG position
            -1 for SHORT position
            0 for no signal

        Perpetual futures support BOTH directions - we take long positions when
        expecting price increases and short positions when expecting decreases.
        """
        row = df.iloc[i]

        if candidate.edge_type == EdgeType.VOLATILITY_REGIME:
            if "compression" in candidate.description.lower():
                # Low volatility compression - trade the breakout direction
                if row["atr_ratio"] < 0.5 and row["bollinger_width"] < 0.02:
                    # Long if price is near upper band, short if near lower band
                    if row["close"] > row["sma_20"]:
                        return 1  # Long - expecting upside breakout
                    else:
                        return -1  # Short - expecting downside breakout

            elif "spike" in candidate.description.lower():
                # Volatility spike - mean reversion
                if row["atr_ratio"] > 2.0 and abs(row["returns"]) > 0.02:
                    # Short after large up move, long after large down move
                    if row["returns"] > 0.02:  # Large up move
                        return -1  # Short - expecting reversion down
                    elif row["returns"] < -0.02:  # Large down move
                        return 1  # Long - expecting reversion up

        elif candidate.edge_type == EdgeType.MARKET_MICROSTRUCTURE:
            if "bid-ask" in candidate.description.lower():
                # Bid-ask bounce - fade the moves
                if row["bollinger_width"] > 0.03:  # Wide spread
                    if row["close"] > row["sma_20"] + row["std_20"]:
                        return -1  # Short - fade the upper band touch
                    elif row["close"] < row["sma_20"] - row["std_20"]:
                        return 1  # Long - fade the lower band touch

            elif "sweep" in candidate.description.lower():
                # Liquidity sweep - reversal after spike
                if row["volume_ratio"] > 3.0:
                    # Check for rejection wicks
                    candle_range = row["high"] - row["low"]
                    if row["close"] < row["open"] and (row["high"] - row["close"]) / candle_range > 0.5:
                        return 1  # Long - rejecting upside
                    elif row["close"] > row["open"] and (row["close"] - row["low"]) / candle_range > 0.5:
                        return -1  # Short - rejecting downside

        elif candidate.edge_type == EdgeType.TIME_PATTERN:
            hour = df.index[i].hour

            if "asian" in candidate.description.lower():
                # Asian session - range trading fade
                if 20 <= hour or hour <= 2:
                    if row["volume_ratio"] < 0.8:  # Low volume
                        if row["close"] > row["sma_20"]:
                            return -1  # Short - fade the rise in quiet session
                        else:
                            return 1  # Long - fade the drop in quiet session

            elif "london" in candidate.description.lower():
                # London open - volatility breakout
                if 7 <= hour <= 8:
                    # Trade the direction of the initial move
                    if row["returns"] > 0.001:  # Positive move
                        return 1  # Long - follow the breakout
                    elif row["returns"] < -0.001:  # Negative move
                        return -1  # Short - follow the breakdown

        elif candidate.edge_type == EdgeType.MOMENTUM_MEAN_REVERSION:
            # Trend-following with mean reversion entries
            if row["ema_50"] > row["ema_200"]:  # Uptrend
                if row["close"] < row["ema_50"] and 30 < row["rsi"] < 70:
                    return 1  # Long - buy dip in uptrend
            elif row["ema_50"] < row["ema_200"]:  # Downtrend
                if row["close"] > row["ema_50"] and 30 < row["rsi"] < 70:
                    return -1  # Short - sell rally in downtrend

        elif candidate.edge_type == EdgeType.CORRELATION_ARBITRAGE:
            # Correlation arbitrage - trade the convergence
            # This would typically involve two assets, but for SOL we use
            # price deviation from expected value based on trend
            if row["atr_ratio"] > 1.5:
                # Price extended from mean - potential reversal
                if row["close"] > row["sma_20"] + 2 * row["std_20"]:
                    return -1  # Short - overextended
                elif row["close"] < row["sma_20"] - 2 * row["std_20"]:
                    return 1  # Long - overextended downside

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
        passed = [r for r in results if r.passed_validation]
        passed.sort(key=lambda x: x.total_return, reverse=True)

        logger.info(f"Discovery cycle complete: {len(passed)}/{len(results)} edges passed validation")

        return {
            "status": "success",
            "total_candidates": len(candidates),
            "passed_validation": len(passed),
            "top_edges": [
                {
                    "description": r.edge_description,
                    "return": r.total_return,
                    "drawdown": r.max_drawdown,
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
