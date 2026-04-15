#!/usr/bin/env python3
"""
SLATE Realistic Strategy Discovery System

Continuously discovers, backtests, and evolves trading strategies using:
- Realistic fee/slippage/fill assumptions
- Historical data archive for consistent testing
- Multiple strategy types beyond simple indicators
- Performance tracking and evolution
- Timeframe exploration (5s to hours)
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from collections import defaultdict
import numpy as np

# Import multi-path testing for robustness evaluation
try:
    from .multipath_backtester import MultiPathBacktester, MultiPathResult
    MULTIPATH_AVAILABLE = True
except ImportError:
    MULTIPATH_AVAILABLE = False
    # Define a dummy class for type annotations when import fails
    class MultiPathResult:
        pass

# Import persistence layer
try:
    from .realistic_memory import get_realistic_discovery_memory
    PERSISTENCE_AVAILABLE = True
except ImportError:
    PERSISTENCE_AVAILABLE = False

# Import stigmergic coordinator
try:
    from .stigmergic_coordinator import get_stigmergic_coordinator
    STIGMERGIC_AVAILABLE = True
except ImportError:
    STIGMERGIC_AVAILABLE = False
    logger.warning("Stigmergic coordinator not available")

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Realistic backtest configuration."""
    # Fees (Paradex-style: maker 0.02%, taker 0.05%)
    maker_fee: float = 0.0002
    taker_fee: float = 0.0005
    # Slippage (basis points)
    slippage_bps: int = 5
    # Fill rate (probability of order filling)
    fill_rate: float = 0.95
    # Position sizing
    max_position_size: float = 0.1  # 10% of capital
    # Test period
    test_period_days: int = 30
    # Starting capital
    initial_capital: float = 10000.0


@dataclass
class BacktestResult:
    """Results from a backtest."""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    timeframe: str
    period_start: str
    period_end: str

    # Performance metrics
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    equity_curve_smoothness: float  # Lower is better
    calmar_ratio: float

    # Trading stats
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_trade: float

    # Risk metrics
    volatility: float
    var_95: float  # Value at risk 95%
    cvar_95: float  # Conditional VaR

    # Strategy parameters (for evolution)
    parameters: Dict

    # Detailed data
    equity_curve: List[float]
    trades: List[Dict]

    # Timestamp
    timestamp: str


class HistoricalDataArchive:
    """Archive of historical price data for consistent 30-day backtesting."""

    def __init__(self, archive_dir: str = "./palace_data/historical"):
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.cache = {}
        self.symbols = ['BTCUSDT', 'ETHUSDT']
        self.timeframes = ['5s', '1m', '5m', '15m', '1h', '4h']

        # Real 30-day requirements
        self.candles_needed = {
            '1m': 43200,  # 30 days × 24 hours × 60 minutes
            '5m': 8640,   # 30 days × 24 hours × 12 (5-min candles per hour)
            '15m': 2880,  # 30 days × 24 hours × 4 (15-min candles per hour)
            '1h': 720,    # 30 days × 24 hours
            '4h': 180     # 30 days × 6 (4-hour candles per day)
        }

        logger.info("HistoricalDataArchive initialized with 30-day requirements")

    async def get_test_data(self, symbol: str = 'BTCUSDT',
                            timeframe: str = '1m') -> Optional[List[Dict]]:
        """Get 30 days of historical data for backtesting."""
        cache_key = f"{symbol}_{timeframe}"

        # Check memory cache
        if cache_key in self.cache:
            data = self.cache[cache_key]
            # Validate it's actually 30 days of data
            required = self.candles_needed.get(timeframe, 1000)
            if len(data) < required * 0.9:  # Need 90% of required candles
                logger.warning(f"Cached data has only {len(data)} candles, need {required} for 30-day test")
                return None
            return data

        # Check file cache
        cache_file = self.archive_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Validate it's actually 30 days of data
            required = self.candles_needed.get(timeframe, 1000)
            if len(data) < required * 0.9:
                logger.warning(f"Cached data has only {len(data)} candles, need {required} for 30-day test")
                return None

            self.cache[cache_key] = data

            # Calculate actual days covered
            days_covered = len(data) / self.candles_needed.get(timeframe, 1) * 30
            logger.info(f"Loaded {len(data)} candles from cache for {cache_key} ({days_covered:.1f} days)")

            return data

        # Need to fetch real 30-day data - return None for now
        logger.warning(f"No 30-day cached data found for {cache_key}")
        return None

    def save_data(self, symbol: str, timeframe: str, data: List[Dict]):
        """Save data to cache."""
        cache_key = f"{symbol}_{timeframe}"
        cache_file = self.archive_dir / f"{cache_key}.json"

        with open(cache_file, 'w') as f:
            json.dump(data, f)

        self.cache[cache_key] = data
        logger.info(f"Saved {len(data)} candles to cache for {cache_key}")


class RealisticBacktester:
    """Run realistic backtests with proper fees, slippage, and fills."""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.archive = HistoricalDataArchive()

    async def run_backtest(self, strategy: Dict, symbol: str = 'BTCUSDT',
                          timeframe: str = '1m') -> Optional[BacktestResult]:
        """Run a single backtest with realistic assumptions."""
        # Get historical data
        data = await self.archive.get_test_data(symbol, timeframe)
        if not data or len(data) < 100:
            logger.warning(f"Insufficient data for {symbol} {timeframe}")
            return None

        # Initialize backtest state
        capital = self.config.initial_capital
        position = 0.0
        entry_price = 0.0  # Track entry price for unrealized P&L
        entry_cost = 0.0  # Track entry cost for P&L calculation
        equity_curve = [capital]
        trades = []

        # Generate signals from strategy
        signals = self._generate_signals(strategy, data)

        # Run backtest with improved position management
        stop_loss_pct = strategy.get('stop_loss', 0.05)  # 5% stop loss default
        take_profit_pct = strategy.get('take_profit', 0.10)  # 10% take profit default

        for i in range(1, len(data)):
            current_price = data[i]['close']
            signal = signals[i]

            # Check stop-loss / take-profit if in position
            if position != 0:
                if position > 0:
                    # Long position
                    pnl_pct = (current_price - entry_price) / entry_price
                    if pnl_pct <= -stop_loss_pct:
                        # Stop loss hit - exit immediately
                        signal = 0  # Force exit
                    elif pnl_pct >= take_profit_pct:
                        # Take profit hit - exit immediately
                        signal = 0  # Force exit
                else:
                    # Short position
                    pnl_pct = (entry_price - current_price) / entry_price
                    if pnl_pct <= -stop_loss_pct:
                        # Stop loss hit - exit immediately
                        signal = 0  # Force exit
                    elif pnl_pct >= take_profit_pct:
                        # Take profit hit - exit immediately
                        signal = 0  # Force exit

            # Handle signal reversals (long→short or short→long)
            if position != 0 and signal != 0 and ((position > 0 and signal < 0) or (position < 0 and signal > 0)):
                # Close existing position first, then open new one
                if position > 0:
                    # Close long position
                    execution_price = current_price * (1 - self.config.slippage_bps / 10000)
                    proceeds = position * execution_price
                    exit_fee = proceeds * self.config.maker_fee
                    capital += proceeds - exit_fee
                    trade_pnl = (proceeds - exit_fee) - entry_cost
                    trades.append({
                        'entry_bar': entry_bar,
                        'exit_bar': i,
                        'pnl': trade_pnl,
                        'type': 'long'
                    })
                else:
                    # Close short position
                    execution_price = current_price * (1 + self.config.slippage_bps / 10000)
                    proceeds = abs(position) * execution_price
                    exit_fee = proceeds * self.config.maker_fee
                    capital += proceeds - exit_fee
                    trade_pnl = (proceeds - exit_fee) - entry_cost
                    trades.append({
                        'entry_bar': entry_bar,
                        'exit_bar': i,
                        'pnl': trade_pnl,
                        'type': 'short'
                    })

                position = 0
                entry_price = 0.0
                entry_cost = 0.0
                # Fall through to open new position below

            # Apply signal
            if signal != 0 and position == 0:
                # Entry signal
                position_size = capital * self.config.max_position_size

                if signal > 0:
                    # Long entry
                    execution_price = current_price * (1 + self.config.slippage_bps / 10000)
                    entry_fee = position_size * self.config.taker_fee
                    position = (position_size - entry_fee) / execution_price
                    entry_price = execution_price
                    entry_cost = position_size  # Track full cost basis
                    capital -= position_size
                    entry_bar = i  # Track entry bar for trade recording

                elif signal < 0:
                    # Short entry
                    execution_price = current_price * (1 - self.config.slippage_bps / 10000)
                    entry_fee = position_size * self.config.taker_fee
                    position = -(position_size - entry_fee) / execution_price
                    entry_price = execution_price
                    entry_cost = position_size  # Track full cost basis
                    capital -= position_size
                    entry_bar = i  # Track entry bar for trade recording

            elif signal == 0 and position != 0:
                # Exit signal
                if position > 0:
                    # Exit long
                    execution_price = current_price * (1 - self.config.slippage_bps / 10000)
                    proceeds = position * execution_price
                    exit_fee = proceeds * self.config.maker_fee
                    capital += proceeds - exit_fee
                    trade_pnl = (proceeds - exit_fee) - entry_cost
                    trades.append({
                        'entry_bar': entry_bar,
                        'exit_bar': i,
                        'pnl': trade_pnl,
                        'type': 'long'
                    })
                else:
                    # Exit short
                    execution_price = current_price * (1 + self.config.slippage_bps / 10000)
                    proceeds = abs(position) * execution_price
                    exit_fee = proceeds * self.config.maker_fee
                    capital += proceeds - exit_fee
                    trade_pnl = (proceeds - exit_fee) - entry_cost
                    trades.append({
                        'entry_bar': entry_bar,
                        'exit_bar': i,
                        'pnl': trade_pnl,
                        'type': 'short'
                    })
                position = 0
                entry_price = 0.0
                entry_cost = 0.0

            # Calculate current equity
            if position != 0:
                if position > 0:
                    unrealized_pnl = position * (data[i]['close'] - entry_price)
                else:
                    unrealized_pnl = abs(position) * (entry_price - data[i]['close'])
                current_equity = capital + unrealized_pnl
            else:
                current_equity = capital
            equity_curve.append(current_equity)

        # Calculate metrics
        result = self._calculate_metrics(
            strategy, symbol, timeframe, data,
            equity_curve, trades
        )

        return result

    def _generate_signals(self, strategy: Dict, data: List[Dict]) -> List[int]:
        """Generate trading signals from strategy definition."""
        signals = [0] * len(data)
        strategy_type = strategy.get('type', 'unknown')

        if strategy_type == 'momentum':
            signals = self._momentum_signals(data, strategy)
        elif strategy_type == 'mean_reversion':
            signals = self._mean_reversion_signals(data, strategy)
        elif strategy_type == 'breakout':
            signals = self._breakout_signals(data, strategy)
        elif strategy_type == 'trend_following':
            signals = self._trend_signals(data, strategy)
        elif strategy_type == 'statistical_arb':
            signals = self._stat_arb_signals(data, strategy)
        else:
            # Default random signals for exploration
            signals = [random.choice([-1, 0, 1]) if random.random() < 0.1 else 0 for _ in data]

        return signals

    def _momentum_signals(self, data: List[Dict], params: Dict) -> List[int]:
        """Momentum strategy signals."""
        period = params.get('period', 20)
        # Use lower default threshold for 30-day tests (0.5% instead of 2%)
        threshold = params.get('threshold', 0.005)
        signals = [0] * len(data)

        for i in range(period, len(data)):
            momentum = (data[i]['close'] * 100 / data[i - period]['close']) - 100
            if momentum > threshold:
                signals[i] = 1
            elif momentum < -threshold:
                signals[i] = -1

        return signals

    def _mean_reversion_signals(self, data: List[Dict], params: Dict) -> List[int]:
        """Mean reversion signals using Bollinger Bands."""
        period = params.get('period', 20)
        # Use lower std_dev for 30-day tests (1.5 instead of 2.0)
        std_dev = params.get('std_dev', 1.5)
        signals = [0] * len(data)

        for i in range(period, len(data)):
            closes = [d['close'] for d in data[i-period:i]]
            mean = np.mean(closes)
            std = np.std(closes)
            upper_band = mean + std_dev * std
            lower_band = mean - std_dev * std

            if data[i]['close'] < lower_band:
                signals[i] = 1
            elif data[i]['close'] > upper_band:
                signals[i] = -1

        return signals

    def _breakout_signals(self, data: List[Dict], params: Dict) -> List[int]:
        """Breakout strategy signals."""
        period = params.get('period', 20)
        signals = [0] * len(data)

        for i in range(period, len(data)):
            high = max(d['high'] for d in data[i-period:i])
            low = min(d['low'] for d in data[i-period:i])

            if data[i]['close'] > high:
                signals[i] = 1
            elif data[i]['close'] < low:
                signals[i] = -1

        return signals

    def _trend_signals(self, data: List[Dict], params: Dict) -> List[int]:
        """Trend following with moving average crossover."""
        fast = params.get('fast_period', 10)
        slow = params.get('slow_period', 20)
        signals = [0] * len(data)

        for i in range(slow, len(data)):
            fast_ma = np.mean([d['close'] for d in data[i-fast:i]])
            slow_ma = np.mean([d['close'] for d in data[i-slow:i]])

            if fast_ma > slow_ma:
                signals[i] = 1
            elif fast_ma < slow_ma:
                signals[i] = -1

        return signals

    def _stat_arb_signals(self, data: List[Dict], params: Dict) -> List[int]:
        """Statistical arbitrage using z-score."""
        period = params.get('period', 20)
        threshold = params.get('threshold', 2.0)
        signals = [0] * len(data)

        for i in range(period, len(data)):
            closes = np.array([d['close'] for d in data[i-period:i]])
            z_score = (data[i]['close'] - np.mean(closes)) / np.std(closes)

            if z_score < -threshold:
                signals[i] = 1
            elif z_score > threshold:
                signals[i] = -1

        return signals

    def _calculate_metrics(self, strategy: Dict, symbol: str, timeframe: str,
                          data: List[Dict], equity_curve: List[float],
                          trades: List[Dict]) -> BacktestResult:
        """Calculate comprehensive performance metrics."""
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]

        # Calculate returns based on trades, not every bar
        # This avoids the issue of mostly-zero returns when not in position
        if len(trades) > 0:
            trade_returns = [t.get('pnl', 0) / self.config.initial_capital for t in trades if t.get('pnl', 0) != 0]
        else:
            # If no trades, use the overall return
            trade_returns = [total_return]

        # Sharpe ratio (annualized) - use trade returns
        if len(trade_returns) > 0 and np.std(trade_returns) > 0:
            # Annualization depends on timeframe
            # For 30-day test period with N trades, we annualize by sqrt(252 * 30 / days_in_test)
            # But more accurately: if we have N trades over 30 days, that's N/30 trades per day
            # Annualized Sharpe = (mean_return / std_return) * sqrt(trades_per_day * 252)

            # For simplicity, use the test period length (30 days)
            test_period_days = self.config.test_period_days
            trades_per_day = len(trade_returns) / test_period_days if test_period_days > 0 else 1

            # Risk-free rate assumption (0 for crypto)
            risk_free_rate = 0.0

            sharpe = (np.mean(trade_returns) - risk_free_rate) / np.std(trade_returns) * np.sqrt(trades_per_day * 252)
        else:
            sharpe = 0.0

        # Sortino ratio (using trade returns)
        downside_returns = [r for r in trade_returns if r < 0]
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            test_period_days = self.config.test_period_days
            trades_per_day = len(trade_returns) / test_period_days if test_period_days > 0 else 1
            sortino = (np.mean(trade_returns)) / np.std(downside_returns) * np.sqrt(trades_per_day * 252)
        else:
            sortino = 0.0

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd

        # Equity curve smoothness (standard deviation of trade returns)
        smoothness = np.std(trade_returns) if len(trade_returns) > 0 else 0

        # Calmar ratio
        if max_dd > 0:
            calmar = total_return / max_dd
        else:
            calmar = 0

        # Trading stats
        total_trades = len(trades)
        if total_trades > 0:
            win_rate = len([t for t in trades if t.get('pnl', 0) > 0]) / total_trades
            avg_trade = np.mean([t.get('pnl', 0) for t in trades])
        else:
            win_rate = 0
            avg_trade = 0

        # Profit factor
        gross_profit = sum([t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0])
        gross_loss = abs(sum([t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Risk metrics (using trade returns)
        volatility = np.std(trade_returns) if len(trade_returns) > 0 else 0
        var_95 = np.percentile(trade_returns, 5) if len(trade_returns) > 0 else 0
        cvar_95 = np.mean([r for r in trade_returns if r <= var_95]) if len(trade_returns) > 0 else 0

        return BacktestResult(
            strategy_id=strategy.get('id', 'unknown'),
            strategy_name=strategy.get('name', 'Unknown'),
            strategy_type=strategy.get('type', 'unknown'),
            timeframe=timeframe,
            period_start=data[0]['timestamp'] if data else '',
            period_end=data[-1]['timestamp'] if data else '',
            total_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            equity_curve_smoothness=smoothness,
            calmar_ratio=calmar,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade=avg_trade,
            volatility=volatility,
            var_95=var_95,
            cvar_95=cvar_95,
            parameters=strategy.get('parameters', {}),
            equity_curve=[float(x) for x in equity_curve[-100:]],  # Last 100 points
            trades=trades[-500:],  # Last 500 trades for analysis
            timestamp=datetime.now().isoformat()
        )


class StrategyGenerator:
    """Generate diverse strategies for testing with systematic type exploration."""

    def __init__(self):
        self.strategy_types = [
            'momentum',
            'mean_reversion',
            'breakout',
            'trend_following',
            'statistical_arb',
            'machine_learning',
            'regime_switching',
            'order_flow',
            'microstructure',
            'multi_timeframe'
        ]
        self.timeframes = ['5s', '1m', '5m', '15m', '1h', '4h']

        # Diversity tracking - ensure we test all types systematically
        self.type_rotation_index = 0
        self.timeframe_rotation_index = 0
        self.generation_count = 0

        # Track recent types tested to avoid repetition
        self.recent_types = []  # Last 20 types tested
        self.type_counts = {stype: 0 for stype in self.strategy_types}

        logger.info("StrategyGenerator initialized with systematic type exploration")

    def generate_strategy(self, parent_strategy: Dict = None) -> Dict:
        """Generate a new strategy with systematic type diversity."""
        if parent_strategy:
            return self._evolve_strategy(parent_strategy)

        # Use systematic rotation to ensure all types are explored
        strategy_type = self._get_next_strategy_type()
        timeframe = self._get_next_timeframe()

        strategy = {
            'id': f"str_{random.randint(10000, 99999)}",
            'name': f"{strategy_type}_{timeframe}_{random.randint(1, 100)}",
            'type': strategy_type,
            'timeframe': timeframe,
            'parameters': self._generate_parameters(strategy_type)
        }

        # Track diversity
        self._track_diversity(strategy_type)

        logger.debug(f"Generated {strategy_type} strategy (type count: {self.type_counts[strategy_type]})")

        return strategy

    def _get_next_strategy_type(self) -> str:
        """Get next strategy type using forced round-robin to ensure all types are tested."""
        # Force round-robin through strategy types
        strategy_type = self.strategy_types[self.type_rotation_index % len(self.strategy_types)]

        # Always advance the counter - don't get stuck
        self.type_rotation_index += 1

        # Log rotation progress periodically
        if self.type_rotation_index % len(self.strategy_types) == 0:
            logger.info(f"Completed full rotation through {len(self.strategy_types)} strategy types")
            logger.info(f"Type distribution so far: {self.type_counts}")

        return strategy_type

    def _get_next_timeframe(self) -> str:
        """Get next timeframe - all tests use same 4-week period for comparability."""
        return '1m'  # All strategies use same timeframe for comparable results

    def _track_diversity(self, strategy_type: str):
        """Track diversity of strategy types tested."""
        self.type_counts[strategy_type] += 1
        self.recent_types.append(strategy_type)

        # Keep only recent history (last 20)
        if len(self.recent_types) > 20:
            self.recent_types = self.recent_types[-20:]

        self.generation_count += 1

        # Log diversity metrics periodically
        if self.generation_count % 100 == 0:
            logger.info(f"Diversity metrics: {self.type_counts}")

    def get_diversity_metrics(self) -> Dict:
        """Get current diversity metrics."""
        total = sum(self.type_counts.values())
        if total == 0:
            return {stype: 0 for stype in self.strategy_types}

        return {
            'total_generated': total,
            'type_distribution': {k: v for k, v in self.type_counts.items()},
            'type_percentages': {k: round(v/total * 100, 1) for k, v in self.type_counts.items()},
            'recent_diversity': len(set(self.recent_types)),
            'balancedness': self._calculate_balancedness()
        }

    def _calculate_balancedness(self) -> float:
        """Calculate how balanced the type distribution is (0-1, higher is better)."""
        total = sum(self.type_counts.values())
        if total == 0:
            return 0.0

        # Calculate coefficient of variation (lower is more balanced)
        counts = list(self.type_counts.values())
        mean = np.mean(counts)
        std = np.std(counts)

        if mean == 0:
            return 0.0

        cv = std / mean
        # Convert to 0-1 scale (lower cv = higher balancedness)
        balancedness = max(0, 1 - cv/2)
        return round(balancedness, 3)

    def generate_diverse_strategies(self, count: int = 3, coordinator=None) -> List[Dict]:
        """Generate multiple strategies with guaranteed type diversity.

        Args:
            count: Number of strategies to generate
            coordinator: Optional stigmergic coordinator for dynamic prioritization

        Returns:
            List of strategies with different types
        """
        strategies = []

        # Get dynamic priorities from coordinator if available
        priorities = {}
        if coordinator:
            for stype in self.strategy_types:
                priorities[stype] = coordinator.get_strategy_priority(stype)
            logger.debug(f"Using stigmergic priorities: {priorities}")

        # Calculate type allocation based on priorities
        if priorities:
            # Use weighted allocation based on priorities
            total_priority = sum(priorities.values()) or 1.0
            type_allocation = {}
            remaining = count

            for i, stype in enumerate(self.strategy_types):
                if i == len(self.strategy_types) - 1:
                    # Last type gets remainder
                    type_allocation[stype] = remaining
                else:
                    # Allocate based on priority proportion
                    allocation = max(1, int(count * priorities[stype] / total_priority))
                    allocation = min(allocation, remaining)  # Don't exceed count
                    type_allocation[stype] = allocation
                    remaining -= allocation

            logger.debug(f"Type allocation based on priorities: {type_allocation}")
        else:
            # Default: equal allocation
            type_allocation = {}

        for i in range(count):
            # Use priority-based allocation or round-robin fallback
            if priorities and type_allocation:
                # Select type based on allocation
                for stype, alloc in type_allocation.items():
                    if alloc > 0:
                        strategy_type = stype
                        type_allocation[stype] -= 1
                        break
                else:
                    # Fallback to round-robin if allocation exhausted
                    strategy_type = self._get_next_strategy_type()
            else:
                # Default round-robin
                strategy_type = self._get_next_strategy_type()

            timeframe = self._get_next_timeframe()

            strategy = {
                'id': f"str_{random.randint(10000, 99999)}",
                'name': f"{strategy_type}_{timeframe}_{random.randint(1, 100)}",
                'type': strategy_type,
                'timeframe': timeframe,
                'parameters': self._generate_parameters(strategy_type),
                'priority': priorities.get(strategy_type, 1.0) if priorities else 1.0
            }

            strategies.append(strategy)
            self._track_diversity(strategy_type)

        # Build priority strings separately
        priority_strings = [f"{s['type']}={s.get('priority', 1.0):.2f}" for s in strategies]
        logger.info(f"Generated {count} diverse strategies: {[s['type'] for s in strategies]} "
                   f"(priorities: {priority_strings})")
        return strategies

    def _generate_parameters(self, strategy_type: str) -> Dict:
        """Generate parameters for a strategy type."""
        params = {}

        if strategy_type == 'momentum':
            params = {
                'period': random.randint(5, 100),
                'threshold': random.uniform(0.01, 0.10)
            }
        elif strategy_type == 'mean_reversion':
            params = {
                'period': random.randint(10, 50),
                'std_dev': random.uniform(1.0, 3.0)
            }
        elif strategy_type == 'breakout':
            params = {
                'period': random.randint(10, 50),
                'confirmation': random.choice([True, False])
            }
        elif strategy_type == 'trend_following':
            params = {
                'fast_period': random.randint(5, 20),
                'slow_period': random.randint(20, 50)
            }
        else:
            params = {
                'param1': random.uniform(0, 100),
                'param2': random.uniform(0, 100)
            }

        return params

    def _evolve_strategy(self, parent: Dict) -> Dict:
        """Evolve a strategy by mutating parameters."""
        child = parent.copy()
        child['id'] = f"str_{random.randint(10000, 99999)}"
        child['generation'] = child.get('generation', 0) + 1

        # Mutate parameters
        if 'parameters' in child:
            for key in child['parameters']:
                if isinstance(child['parameters'][key], (int, float)):
                    # Mutate by ±10%
                    mutation = random.uniform(0.9, 1.1)
                    child['parameters'][key] *= mutation

        return child


class EvolutionEngine:
    """Track results and evolve strategies based on performance.

    Now integrated with multi-path testing for robustness evaluation:
    - Uses robustness_score when available (penalizes variance, rewards consistency)
    - Falls back to sharpe_ratio for single-path results
    - Tracks consistency_ratio and confidence intervals
    """

    def __init__(self, use_multipath: bool = True, num_paths: int = 50):
        """Initialize evolution engine.

        Args:
            use_multipath: Whether to use multi-path testing for robustness
            num_paths: Number of paths to test (default 50 for balance)
        """
        self.results_history = []
        self.multipath_results = []  # Multi-path results
        self.best_strategies = defaultdict(list)
        self.performance_tracker = {}
        self.use_multipath = use_multipath and MULTIPATH_AVAILABLE
        self.num_paths = num_paths

        # Initialize multi-path backtester if available
        self.multipath_backtester = None
        if self.use_multipath:
            try:
                self.multipath_backtester = MultiPathBacktester()
                logger.info(f"Multi-path testing enabled with {num_paths} paths")
            except Exception as e:
                logger.warning(f"Failed to initialize multi-path backtester: {e}")
                self.use_multipath = False

        # Initialize database persistence
        self.db_memory = None
        if PERSISTENCE_AVAILABLE:
            try:
                self.db_memory = get_realistic_discovery_memory()
                logger.info("Realistic discovery persistence enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize persistence: {e}")

    def record_result(self, result: Union[BacktestResult, MultiPathResult],
                     discovery_cycle: Optional[int] = None):
        """Record a backtest result or multi-path result."""
        if isinstance(result, MultiPathResult):
            self.multipath_results.append(result)
            self._record_multipath_result(result)

            # Persist to database
            if self.db_memory:
                try:
                    import asyncio
                    # Convert to dict and add evaluation_type
                    result_dict = asdict(result)
                    result_dict['evaluation_type'] = 'multipath'
                    result_dict['discovery_cycle'] = discovery_cycle

                    # Save in background (don't block)
                    asyncio.create_task(self.db_memory.save_result(result_dict, discovery_cycle))

                    logger.debug(f"Saved multi-path result {result.strategy_name} to database")
                except Exception as e:
                    logger.warning(f"Failed to save multi-path result to database: {e}")

        else:
            self.results_history.append(result)

            # Track by strategy type
            self.best_strategies[result.strategy_type].append(result)

            # Sort by sharpe_ratio for single-path
            self.best_strategies[result.strategy_type].sort(
                key=lambda x: x.sharpe_ratio, reverse=True
            )
            self.best_strategies[result.strategy_type] = \
                self.best_strategies[result.strategy_type][:10]  # Keep top 10

            # Update performance tracker
            key = f"{result.strategy_type}_{result.timeframe}"
            if key not in self.performance_tracker:
                self.performance_tracker[key] = []
            self.performance_tracker[key].append(self._extract_metrics(result))

            # Persist to database
            if self.db_memory:
                try:
                    import asyncio
                    # Convert to dict and add evaluation_type
                    result_dict = asdict(result)
                    result_dict['evaluation_type'] = 'singlepath'
                    result_dict['num_paths'] = 1
                    result_dict['discovery_cycle'] = discovery_cycle

                    # Save in background (don't block)
                    asyncio.create_task(self.db_memory.save_result(result_dict, discovery_cycle))

                    logger.debug(f"Saved single-path result {result.strategy_name} to database")
                except Exception as e:
                    logger.warning(f"Failed to save single-path result to database: {e}")

    async def evaluate_with_multipath(self, strategy: Dict, historical_candles: List[Dict]) -> Optional[MultiPathResult]:
        """Evaluate a strategy using multi-path testing.

        Args:
            strategy: Strategy definition to evaluate
            historical_candles: Historical candles for bootstrap sampling

        Returns:
            MultiPathResult if successful, None otherwise
        """
        if not self.use_multipath or not self.multipath_backtester:
            return None

        try:
            logger.info(f"Running multi-path evaluation for {strategy.get('name', 'unknown')}...")
            multipath_result = await self.multipath_backtester.test_strategy_multipath(
                strategy, self.num_paths, historical_candles
            )

            # Record the multi-path result
            self.record_result(multipath_result)

            logger.info(
                f"Multi-path result: mean_return={multipath_result.mean_return:.2%}, "
                f"robustness={multipath_result.robustness_score:.3f}, "
                f"consistency={multipath_result.consistency_ratio:.1%}"
            )

            return multipath_result

        except Exception as e:
            logger.warning(f"Multi-path evaluation failed: {e}")
            return None

        # Track by strategy type
        self.best_strategies[result.strategy_type].append(result)

        # Sort by robustness_score if MultiPathResult, else sharpe_ratio
        if isinstance(result, MultiPathResult):
            self.best_strategies[result.strategy_type].sort(
                key=lambda x: x.robustness_score, reverse=True
            )
        else:
            self.best_strategies[result.strategy_type].sort(
                key=lambda x: x.sharpe_ratio, reverse=True
            )

        self.best_strategies[result.strategy_type] = \
            self.best_strategies[result.strategy_type][:10]  # Keep top 10

        # Update performance tracker
        key = f"{result.strategy_type}_{result.timeframe}"
        if key not in self.performance_tracker:
            self.performance_tracker[key] = []
        self.performance_tracker[key].append(self._extract_metrics(result))

    def _record_multipath_result(self, result: MultiPathResult):
        """Record a multi-path result in history."""
        self.multipath_results.append(result)

        # Also add to best_strategies with proper sorting
        self.best_strategies[result.strategy_type].append(result)
        self.best_strategies[result.strategy_type].sort(
            key=lambda x: x.robustness_score, reverse=True
        )
        self.best_strategies[result.strategy_type] = \
            self.best_strategies[result.strategy_type][:10]

        # Update performance tracker with multi-path metrics
        key = f"{result.strategy_type}_{result.timeframe}"
        if key not in self.performance_tracker:
            self.performance_tracker[key] = []
        self.performance_tracker[key].append({
            'timestamp': result.timestamp,
            'sharpe': result.mean_sharpe,
            'return': result.mean_return,
            'robustness_score': result.robustness_score,
            'consistency_ratio': result.consistency_ratio,
            'return_ci_lower': result.return_ci_lower,
            'return_ci_upper': result.return_ci_upper,
            'num_paths': result.num_paths,
            'is_multipath': True
        })

    def _extract_metrics(self, result: Union[BacktestResult, MultiPathResult]) -> Dict:
        """Extract metrics from result for performance tracking."""
        if isinstance(result, MultiPathResult):
            return {
                'timestamp': result.timestamp,
                'sharpe': result.mean_sharpe,
                'return': result.mean_return,
                'robustness_score': result.robustness_score,
                'consistency_ratio': result.consistency_ratio,
                'return_ci_lower': result.return_ci_lower,
                'return_ci_upper': result.return_ci_upper,
                'num_paths': result.num_paths,
                'is_multipath': True
            }
        else:
            return {
                'timestamp': result.timestamp,
                'sharpe': result.sharpe_ratio,
                'return': result.total_return,
                'max_dd': result.max_drawdown,
                'is_multipath': False
            }

    def get_best_parameters(self, strategy_type: str) -> Dict:
        """Get best parameters for a strategy type."""
        if strategy_type not in self.best_strategies:
            return {}

        best = self.best_strategies[strategy_type][0]
        base = {
            'type': strategy_type,
            'sample_count': len(self.best_strategies[strategy_type])
        }

        if isinstance(best, MultiPathResult):
            base.update({
                'best_sharpe': best.mean_sharpe,
                'best_return': best.mean_return,
                'best_timeframe': best.timeframe,
                'robustness_score': best.robustness_score,
                'consistency_ratio': best.consistency_ratio,
                'return_ci_lower': best.return_ci_lower,
                'return_ci_upper': best.return_ci_upper,
                'num_paths': best.num_paths,
                'evaluation_type': 'multipath'
            })
        else:
            base.update({
                'best_sharpe': best.sharpe_ratio,
                'best_return': best.total_return,
                'best_timeframe': best.timeframe,
                'evaluation_type': 'singlepath'
            })

        return base

    def get_insights(self) -> Dict:
        """Get insights from evolution, including robustness metrics."""
        insights = {
            'total_tests': len(self.results_history) + len(self.multipath_results),
            'multipath_tests': len(self.multipath_results),
            'singlepath_tests': len(self.results_history),
            'best_overall': None,
            'best_by_type': {},
            'trends': {},
            'robustness_summary': {}
        }

        # Combine all results for sorting
        all_results = []
        for r in self.results_history:
            all_results.append(('single', r))
        for r in self.multipath_results:
            all_results.append(('multi', r))

        # Find best overall (prefer multi-path results)
        if all_results:
            # Sort multi-path by robustness_score, single-path by sharpe
            def sort_key(item):
                result_type, result = item
                if result_type == 'multi':
                    return (1, result.robustness_score)  # Prefer multi-path
                else:
                    return (0, result.sharpe_ratio)

            sorted_results = sorted(all_results, key=sort_key, reverse=True)
            best_type, best = sorted_results[0]

            if best_type == 'multi':
                insights['best_overall'] = {
                    'name': best.strategy_name,
                    'type': best.strategy_type,
                    'sharpe': best.mean_sharpe,
                    'return': best.mean_return,
                    'robustness_score': best.robustness_score,
                    'consistency': best.consistency_ratio,
                    'evaluation': 'multipath'
                }
            else:
                insights['best_overall'] = {
                    'name': best.strategy_name,
                    'type': best.strategy_type,
                    'sharpe': best.sharpe_ratio,
                    'return': best.total_return,
                    'evaluation': 'singlepath'
                }

        # Best by type (prefer multi-path results)
        for stype, results in self.best_strategies.items():
            if results:
                best = results[0]
                if isinstance(best, MultiPathResult):
                    insights['best_by_type'][stype] = {
                        'sharpe': best.mean_sharpe,
                        'return': best.mean_return,
                        'timeframe': best.timeframe,
                        'robustness_score': best.robustness_score,
                        'consistency': best.consistency_ratio,
                        'evaluation': 'multipath'
                    }
                else:
                    insights['best_by_type'][stype] = {
                        'sharpe': best.sharpe_ratio,
                        'return': best.total_return,
                        'timeframe': best.timeframe,
                        'evaluation': 'singlepath'
                    }

        # Robustness summary (from multi-path results)
        if self.multipath_results:
            robustness_scores = [r.robustness_score for r in self.multipath_results]
            consistencies = [r.consistency_ratio for r in self.multipath_results]

            insights['robustness_summary'] = {
                'avg_robustness': np.mean(robustness_scores),
                'best_robustness': max(robustness_scores),
                'avg_consistency': np.mean(consistencies),
                'high_consistency_count': len([c for c in consistencies if c > 0.7])
            }

        return insights


class ContinuousDiscoverySystem:
    """Main discovery system that runs continuous backtests.

    Now integrated with multi-path testing for robust strategy evaluation:
    - Single-path backtests for quick screening
    - Multi-path evaluation for promising strategies (robustness scoring)
    - Evolution based on robustness metrics when available
    """

    def __init__(self, use_multipath: bool = True, num_paths: int = 50,
                 multipath_sample_rate: float = 0.2):
        """Initialize continuous discovery system.

        Args:
            use_multipath: Whether to enable multi-path testing
            num_paths: Number of paths for multi-path evaluation
            multipath_sample_rate: Fraction of strategies to evaluate with multi-path
        """
        self.backtester = RealisticBacktester()
        self.generator = StrategyGenerator()
        self.evolution = EvolutionEngine(use_multipath=use_multipath, num_paths=num_paths)
        self.running = False
        # Scale workers based on CPU count for better parallel processing
        import os
        cpu_count = os.cpu_count() or 4
        self.workers = min(20, cpu_count * 2)  # Use up to 20 workers or 2x CPU cores
        self.multipath_sample_rate = multipath_sample_rate
        self.historical_archive = HistoricalDataArchive()
        self.current_cycle = 0  # Track discovery cycle number

        # Initialize stigmergic coordinator
        self.stigmergic_coordinator = None
        if STIGMERGIC_AVAILABLE:
            self.stigmergic_coordinator = get_stigmergic_coordinator()
            logger.info("Stigmergic coordinator initialized for real-time coordination")

        logger.info(f"Continuous discovery initialized: multipath={use_multipath}, "
                   f"num_paths={num_paths}, sample_rate={multipath_sample_rate}")

    async def start_discovery(self, cycles: int = 100):
        """Start continuous discovery with stigmergic coordination."""
        self.running = True
        logger.info(f"Starting continuous discovery: {cycles} cycles")

        # Update dynamic priorities at start
        if self.stigmergic_coordinator:
            self.stigmergic_coordinator.update_dynamic_priorities()

        for cycle in range(cycles):
            if not self.running:
                break

            self.current_cycle = cycle + 1  # Track cycle number for database

            if not self.running:
                break

            # Check for external candidates from self-evolving system
            from .candidate_queue import get_candidate_queue
            candidate_queue = get_candidate_queue()

            external_candidates = await candidate_queue.get_candidates(count=self.workers)

            if external_candidates:
                # Test external candidates (self-evolved strategies)
                logger.info(f"Testing {len(external_candidates)} external candidates from self-evolving system")
                strategies = []
                for candidate in external_candidates:
                    strategy = {
                        'id': candidate.id,
                        'name': candidate.name,
                        'type': candidate.type,
                        'timeframe': candidate.timeframe,
                        'parameters': candidate.parameters,
                        'source': 'self_evolving',
                        'confidence': candidate.confidence
                    }
                    strategies.append(strategy)
            else:
                # Generate diverse strategies with guaranteed type spread
                # Use stigmergic priorities to influence generation
                strategies = self.generator.generate_diverse_strategies(
                    self.workers,
                    coordinator=self.stigmergic_coordinator
                )

            # Filter strategies through stigmergic redundancy checks
            filtered_strategies = []
            for strategy in strategies:
                can_test = True
                reason = "OK"

                if self.stigmergic_coordinator:
                    can_test, reason = await self.stigmergic_coordinator.can_test_strategy(
                        strategy_id=strategy['id'],
                        strategy_type=strategy['type'],
                        parameters=strategy.get('parameters', {})
                    )

                if can_test:
                    filtered_strategies.append(strategy)
                else:
                    logger.debug(f"Filtered {strategy['id']}: {reason}")

            if len(filtered_strategies) == 0:
                logger.warning("All strategies filtered by stigmergic coordinator, generating fallback strategies")
                filtered_strategies = strategies[:1]  # Always test at least one

            logger.info(f"Testing {len(filtered_strategies)} strategies (filtered from {len(strategies)})")

            # Create backtest tasks and register with coordinator
            tasks = []
            strategy_map = {}  # Map task index to strategy
            for i, strategy in enumerate(filtered_strategies):
                # Register testing start with coordinator
                if self.stigmergic_coordinator:
                    await self.stigmergic_coordinator.register_testing_start(
                        strategy_id=strategy['id'],
                        strategy_type=strategy['type'],
                        parameters=strategy.get('parameters', {}),
                        priority=self.stigmergic_coordinator.get_strategy_priority(strategy['type'])
                    )

                task = self.backtester.run_backtest(
                    strategy,
                    symbol=strategy.get('symbol', 'BTCUSDT'),
                    timeframe='1m'  # Use same 4-week period for all tests
                )
                tasks.append(task)
                strategy_map[i] = strategy

            # Run backtests in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and register completion with coordinator
            for i, result in enumerate(results):
                strategy = strategy_map.get(i)
                if not strategy:
                    continue

                if isinstance(result, BacktestResult):
                    # Register completion with coordinator (deposit pheromone)
                    if self.stigmergic_coordinator:
                        await self.stigmergic_coordinator.register_testing_complete(
                            strategy_id=strategy['id'],
                            result={
                                'sharpe_ratio': result.sharpe_ratio,
                                'total_return': result.total_return,
                                'max_drawdown': result.max_drawdown
                            }
                        )

                    logger.info(
                        f"Strategy {result.strategy_name}: "
                        f"Sharpe={result.sharpe_ratio:.2f}, "
                        f"Return={result.total_return:.2%} "
                        f"[priority={self.stigmergic_coordinator.get_strategy_priority(result.strategy_type):.2f}]"
                        if self.stigmergic_coordinator else
                        f"Strategy {result.strategy_name}: "
                        f"Sharpe={result.sharpe_ratio:.2f}, "
                        f"Return={result.total_return:.2%}"
                    )

            # Mark external candidates as completed
            if external_candidates:
                candidate_queue = get_candidate_queue()

                for i, result in enumerate(results):
                    if isinstance(result, BacktestResult) and i < len(external_candidates):
                        candidate_id = external_candidates[i].id
                        success = result.sharpe_ratio > -100  # Basic success check
                        await candidate_queue.mark_completed(candidate_id, success)

                        logger.info(
                            f"External candidate {candidate_id}: "
                            f"Sharpe={result.sharpe_ratio:.2f}, Return={result.total_return:.2%} "
                            f"[from {external_candidates[i].source}]"
                        )

            # Record results with multi-path evaluation for sampled strategies
            multipath_tasks = []
            for i, result in enumerate(results):
                if isinstance(result, BacktestResult):
                    strategy = strategies[i]

                    # Decide whether to run multi-path evaluation
                    use_multipath = (random.random() < self.multipath_sample_rate
                                   and self.evolution.use_multipath)

                    if use_multipath:
                        # Load historical data for multi-path evaluation
                        symbol = strategy.get('symbol', 'BTCUSDT')
                        timeframe = strategy.get('timeframe', '1m')
                        candles = await self.historical_archive.load_data(symbol, timeframe)

                        if candles:
                            # Schedule multi-path evaluation
                            mp_task = self.evolution.evaluate_with_multipath(strategy, candles)
                            multipath_tasks.append(mp_task)
                        else:
                            # No historical data available, use single-path
                            self.evolution.record_result(result, self.current_cycle)
                            logger.info(
                                f"Strategy {result.strategy_name}: "
                                f"Sharpe={result.sharpe_ratio:.2f}, "
                                f"Return={result.total_return:.2%} [SINGLE-PATH]"
                            )
                    else:
                        # Single-path evaluation only
                        self.evolution.record_result(result, self.current_cycle)
                        logger.info(
                            f"Strategy {result.strategy_name}: "
                            f"Sharpe={result.sharpe_ratio:.2f}, "
                            f"Return={result.total_return:.2%}"
                        )

            # Run multi-path evaluations in parallel
            if multipath_tasks:
                await asyncio.gather(*multipath_tasks, return_exceptions=True)

            # Evolve strategies based on best performers
            await self._evolve_strategies()

            # Periodic database archiving (every 50 cycles, reduced from 100)
            if (cycle + 1) % 50 == 0 and self.db_memory:
                try:
                    # Archive old results instead of deleting them
                    from slate_core.discovery.tiered_storage import get_tiered_storage

                    tiered_storage = get_tiered_storage()
                    archive_result = tiered_storage.archive_old_results(
                        keep_recent=100,    # Keep full detail for most recent 100
                        keep_best=100,      # Keep full detail for best 100 by Sharpe
                        max_age_days=7      # Archive records older than 7 days
                    )

                    logger.info(
                        f"Database archive: {archive_result['archived_count']} records archived, "
                        f"{archive_result['full_records']} full detail, "
                        f"{archive_result['archived_records']} archived, "
                        f"saved ~{archive_result['space_saved_mb']:.1f} MB"
                    )
                except Exception as e:
                    logger.warning(f"Database archiving failed: {e}")

            logger.info(f"Completed discovery cycle {cycle + 1}/{cycles}")

    async def _evolve_strategies(self):
        """Generate new strategies based on best performers."""
        # Get insights
        insights = self.evolution.get_insights()

        # Evolve from best strategies
        for stype, info in insights.get('best_by_type', {}).items():
            # Create evolved versions
            for _ in range(2):
                parent = {
                    'type': stype,
                    'timeframe': info['timeframe'],
                    'generation': 0
                }
                child = self.generator._evolve_strategy(parent)
                # Will be tested in next cycle

    def stop_discovery(self):
        """Stop continuous discovery."""
        self.running = False
        logger.info("Stopping continuous discovery")

    def get_status(self) -> Dict:
        """Get discovery system status including robustness metrics."""
        insights = self.evolution.get_insights()
        return {
            'running': self.running,
            'total_tests': insights['total_tests'],
            'multipath_tests': insights.get('multipath_tests', 0),
            'singlepath_tests': insights.get('singlepath_tests', 0),
            'workers': self.workers,
            'multipath_enabled': self.evolution.use_multipath,
            'num_paths': self.evolution.num_paths if self.evolution.use_multipath else 0,
            'insights': insights
        }

    def get_recent_results(self, limit: int = 50) -> List[Dict]:
        """Get recent backtest results including multi-path results."""
        # Combine both types of results
        recent_single = self.evolution.results_history[-limit:]
        recent_multi = self.evolution.multipath_results[-limit:]

        # Combine and sort by timestamp
        all_results = []
        for r in recent_single:
            d = asdict(r)
            d['evaluation_type'] = 'singlepath'
            all_results.append((d['timestamp'], d))
        for r in recent_multi:
            d = asdict(r)
            d['evaluation_type'] = 'multipath'
            all_results.append((d['timestamp'], d))

        # Sort by timestamp and return most recent
        all_results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in all_results[:limit]]


# Global instance
_discovery_system = None


def get_discovery_system() -> ContinuousDiscoverySystem:
    """Get the global discovery system instance."""
    global _discovery_system
    if _discovery_system is None:
        _discovery_system = ContinuousDiscoverySystem()
    return _discovery_system
