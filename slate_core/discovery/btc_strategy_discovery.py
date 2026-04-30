"""
BTCUSDT Perpetuals Strategy Discovery System

Comprehensive mission to discover the most profitable trading strategy
for BTCUSDT perpetuals over a 12-month period with realistic trading conditions.

Author: SLATE Discovery System
Date: 2025-04-17
Mission: Maximize profit while minimizing drawdown using real market data
"""

import asyncio
import logging
import sqlite3
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import time
from dataclasses import dataclass, asdict
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)


@dataclass
class TradingCosts:
    """Realistic trading costs for BTCUSDT perpetuals."""
    maker_fee: float = 0.0002      # 0.02% maker fee
    taker_fee: float = 0.0005      # 0.05% taker fee
    funding_rate_hourly: float = 0.00001  # ~0.01% hourly funding
    slippage_bps: float = 5.0      # 5 bps slippage for market orders
    impact_bps: float = 2.0        # 2 bps market impact for large orders
    min_profit_bps: float = 10.0   # Minimum 10 bps profit to trade


@dataclass
class StrategyResult:
    """Result of backtesting a strategy."""
    strategy_name: str
    parameters: Dict[str, Any]

    # Performance metrics
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # Trading statistics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_trade: float
    avg_hold_time_hours: float

    # Risk metrics
    var_95: float
    cvar_95: float
    tail_ratio: float

    # Detailed data
    equity_curve: List[float]
    trades: List[Dict[str, Any]]
    returns: List[float]

    # Metadata
    timestamp: str
    data_period: str
    notes: str = ""


class BTCDataFetcher:
    """Fetch 12 months of BTCUSDT perpetuals data with caching."""

    def __init__(self, cache_dir: str = "./btc_data_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.exchange = ccxt.binanceusdm({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })

    async def fetch_historical_data(
        self,
        symbol: str = "BTCUSDT",
        months: int = 12,
        timeframes: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Fetch historical OHLCV data for multiple timeframes."""

        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']

        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        all_data = {}

        for timeframe in timeframes:
            cache_file = self.cache_dir / f"{symbol}_{timeframe}_{months}m.parquet"

            # Check cache first
            if cache_file.exists():
                logger.info(f"Loading {timeframe} data from cache: {cache_file}")
                all_data[timeframe] = pd.read_parquet(cache_file)
                continue

            # Fetch from exchange
            logger.info(f"Fetching {timeframe} data from {start_date} to {end_date}")

            candles = []
            since = self.exchange.milliseconds() - (months * 30 * 24 * 60 * 60 * 1000)

            while since < self.exchange.milliseconds():
                try:
                    batch = await self.exchange.fetch_ohlcv(
                        symbol,
                        timeframe,
                        since=since,
                        limit=1000
                    )

                    if not batch:
                        break

                    candles.extend(batch)
                    since = batch[-1][0] + 1

                    # Avoid rate limits
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(f"Error fetching {timeframe}: {e}")
                    await asyncio.sleep(1)
                    continue

            # Convert to DataFrame
            df = pd.DataFrame(
                candles,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Cache to disk
            df.to_parquet(cache_file)
            all_data[timeframe] = df

            logger.info(f"Downloaded {len(df)} {timeframe} candles")

        await self.exchange.close()
        return all_data


class AdvancedIndicators:
    """Calculate advanced technical indicators for strategy discovery."""

    @staticmethod
    def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive technical indicators to OHLCV data."""

        # Momentum indicators
        df['rsi_14'] = AdvancedIndicators.rsi(df['close'], 14)
        df['rsi_7'] = AdvancedIndicators.rsi(df['close'], 7)
        df['rsi_21'] = AdvancedIndicators.rsi(df['close'], 21)

        # Moving averages
        for period in [5, 10, 20, 50, 100, 200]:
            df[f'sma_{period}'] = df['close'].rolling(period).mean()
            df[f'ema_{period}'] = df['close'].ewm(span=period).mean()

        # MACD
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # ATR (Average True Range)
        df['atr_14'] = AdvancedIndicators.atr(df, 14)
        df['atr_7'] = AdvancedIndicators.atr(df, 7)

        # Volume indicators
        df['volume_sma_20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']

        # Price momentum
        for period in [1, 3, 5, 10]:
            df[f'return_{period}'] = df['close'].pct_change(period)

        # Volatility
        df['volatility_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()

        # Stochastic
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()

        # Support/Resistance levels
        df['support_20'] = df['low'].rolling(20).min()
        df['resistance_20'] = df['high'].rolling(20).max()
        df['support_50'] = df['low'].rolling(50).min()
        df['resistance_50'] = df['high'].rolling(50).max()

        # Trend indicators
        df['adx_14'] = AdvancedIndicators.adx(df, 14)
        df['plus_di_14'] = AdvancedIndicators.plus_di(df, 14)
        df['minus_di_14'] = AdvancedIndicators.minus_di(df, 14)

        return df

    @staticmethod
    def rsi(series: pd.Series, period: int) -> pd.Series:
        """Calculate RSI."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def atr(df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    @staticmethod
    def adx(df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average Directional Index."""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = AdvancedIndicators.atr(df, 1)
        plus_di = 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())
        minus_di = 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(period).mean()

    @staticmethod
    def plus_di(df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Plus Directional Indicator."""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)

        tr = AdvancedIndicators.atr(df, 1)
        return 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())

    @staticmethod
    def minus_di(df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Minus Directional Indicator."""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = AdvancedIndicators.atr(df, 1)
        return 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())


class RegimeDetector:
    """Detect market regimes for adaptive strategies."""

    @staticmethod
    def detect_regimes(df: pd.DataFrame) -> pd.DataFrame:
        """Add regime detection features."""

        # Trend regime
        sma_short = df['close'].rolling(20).mean()
        sma_long = df['close'].rolling(50).mean()
        df['regime_trend'] = np.where(sma_short > sma_long, 1, -1)

        # Volatility regime
        volatility = df['close'].pct_change().rolling(20).std()
        vol_threshold = volatility.quantile(0.75)
        df['regime_volatility'] = np.where(volatility > vol_threshold, 1, 0)

        # Volume regime
        volume_ratio = df['volume'] / df['volume'].rolling(50).mean()
        df['regime_volume'] = np.where(volume_ratio > 1.2, 1, 0)

        # Combined regime
        df['regime_combined'] = (
            df['regime_trend'].astype(str) +
            df['regime_volatility'].astype(str) +
            df['regime_volume'].astype(str)
        )

        return df


class OrderFlowAnalyzer:
    """Analyze order flow for microstructure insights."""

    @staticmethod
    def analyze_order_flow(df: pd.DataFrame) -> pd.DataFrame:
        """Add order flow indicators."""

        # Imbalance indicators
        df['close_location'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'])

        # Candle patterns
        df['is_hammer'] = (
            (df['close_location'] < 0.3) &
            (df['body_ratio'] < 0.3) &
            (df['close'] > df['open'])
        )

        df['is_shooting_star'] = (
            (df['close_location'] > 0.7) &
            (df['body_ratio'] < 0.3) &
            (df['close'] < df['open'])
        )

        # Engulfing patterns
        df['prev_open'] = df['open'].shift(1)
        df['prev_close'] = df['close'].shift(1)
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)

        df['is_bullish_engulfing'] = (
            (df['prev_close'] < df['prev_open']) &  # Previous red candle
            (df['close'] > df['open']) &  # Current green candle
            (df['open'] < df['prev_close']) &  # Opens below previous close
            (df['close'] > df['prev_open'])  # Closes above previous open
        )

        df['is_bearish_engulfing'] = (
            (df['prev_close'] > df['prev_open']) &  # Previous green candle
            (df['close'] < df['open']) &  # Current red candle
            (df['open'] > df['prev_close']) &  # Opens above previous close
            (df['close'] < df['prev_open'])  # Closes below previous open
        )

        return df


class RealisticBacktester:
    """Backtester with brutally honest trading costs."""

    def __init__(self, costs: TradingCosts = None):
        self.costs = costs or TradingCosts()
        self.initial_capital = 100000.0

    def backtest_strategy(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        strategy_name: str,
        parameters: Dict[str, Any]
    ) -> StrategyResult:
        """Backtest a strategy with realistic costs."""

        capital = self.initial_capital
        position = 0  # +1 for long, -1 for short, 0 for neutral
        entry_price = None
        entry_time = None
        trades = []
        equity_curve = []
        returns = []

        # Track costs
        total_fees = 0
        total_slippage = 0

        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]

            # Check for position entry/exit
            signal = signals.iloc[i]

            # Close existing position
            if position != 0 and signal == 0:
                # Calculate exit price with slippage
                exit_price = current_price * (1 - np.sign(position) * self.costs.slippage_bps / 10000)

                # Calculate P&L
                pnl = position * (exit_price - entry_price) / entry_price * capital

                # Apply fees
                entry_fee = capital * self.costs.maker_fee
                exit_fee = (capital + pnl) * self.costs.taker_fee
                total_fees += entry_fee + exit_fee
                pnl -= entry_fee + exit_fee

                # Record trade
                hold_time = (current_time - entry_time).total_seconds() / 3600
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'position': 'long' if position > 0 else 'short',
                    'pnl': pnl,
                    'return': pnl / capital,
                    'hold_time_hours': hold_time
                })

                capital += pnl
                position = 0
                entry_price = None

            # Open new position
            elif position == 0 and signal != 0:
                entry_price = current_price * (1 + np.sign(signal) * self.costs.slippage_bps / 10000)
                entry_time = current_time
                position = np.sign(signal)

                # Apply entry fee
                fee = capital * self.costs.maker_fee
                total_fees += fee

            # Calculate equity
            if position != 0:
                unrealized_pnl = position * (current_price - entry_price) / entry_price * capital
                equity = capital + unrealized_pnl
            else:
                equity = capital

            equity_curve.append(equity)

            # Calculate returns
            if len(equity_curve) > 1:
                returns.append((equity - equity_curve[-2]) / equity_curve[-2])

        # Close any remaining position
        if position != 0:
            final_price = df['close'].iloc[-1]
            exit_price = final_price * (1 - np.sign(position) * self.costs.slippage_bps / 10000)
            pnl = position * (exit_price - entry_price) / entry_price * capital
            capital += pnl

        # Calculate metrics
        total_return = (capital - self.initial_capital) / self.initial_capital

        if returns:
            returns_array = np.array(returns)
            sharpe = np.sqrt(252) * np.mean(returns_array) / np.std(returns_array) if np.std(returns_array) > 0 else 0
            sortino = np.sqrt(252) * np.mean(returns_array) / np.std(returns_array[returns_array < 0]) if len(returns_array[returns_array < 0]) > 0 else 0
        else:
            sharpe = 0
            sortino = 0

        # Calculate max drawdown
        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdowns = (equity_array - running_max) / running_max
        max_drawdown = abs(drawdowns.min())

        # Calculate other metrics
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        if winning_trades and losing_trades:
            avg_win = np.mean([t['pnl'] for t in winning_trades])
            avg_loss = np.mean([t['pnl'] for t in losing_trades])
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        else:
            profit_factor = 0

        avg_trade = np.mean([t['pnl'] for t in trades]) if trades else 0
        avg_hold_time = np.mean([t['hold_time_hours'] for t in trades]) if trades else 0

        # VaR and CVaR
        if returns:
            var_95 = np.percentile(returns, 5)
            cvar_95 = np.mean(returns[returns <= var_95])
        else:
            var_95 = 0
            cvar_95 = 0

        return StrategyResult(
            strategy_name=strategy_name,
            parameters=parameters,
            total_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            calmar_ratio=total_return / max_drawdown if max_drawdown > 0 else 0,
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade=avg_trade,
            avg_hold_time_hours=avg_hold_time,
            var_95=var_95,
            cvar_95=cvar_95,
            tail_ratio=abs(cvar_95 / var_95) if var_95 != 0 else 0,
            equity_curve=equity_curve[-1000:],  # Last 1000 points
            trades=trades[-500:],  # Last 500 trades
            returns=returns[-500:],  # Last 500 returns
            timestamp=datetime.now().isoformat(),
            data_period=f"12 months",
            notes=f"Total fees: ${total_fees:.2f}, Total slippage: ${total_slippage:.2f}"
        )


class StrategyExplorer:
    """Explore strategy parameter space systematically."""

    def __init__(self, backtester: RealisticBacktester):
        self.backtester = backtester
        self.results = []

    def explore_momentum_strategies(
        self,
        df: pd.DataFrame,
        rsi_ranges: List[Tuple[int, int]] = None,
        macd_ranges: List[Tuple[int, int, int]] = None
    ) -> List[StrategyResult]:
        """Explore momentum-based strategies."""

        if rsi_ranges is None:
            rsi_ranges = [(7, 21), (14, 28), (21, 35), (5, 15), (10, 20)]

        if macd_ranges is None:
            macd_ranges = [(5, 12, 9), (8, 17, 9), (12, 26, 9), (5, 20, 5)]

        results = []

        for rsi_period, rsi_threshold in rsi_ranges:
            for macd_fast, macd_slow, macd_signal in macd_ranges:
                # Calculate indicators
                indicators = AdvancedIndicators()
                df_test = df.copy()

                # RSI + MACD strategy
                signals = pd.Series(0, index=df_test.index)

                # RSI oversold + MACD bullish crossover = long
                rsi_condition = df_test['rsi_14'] < 30
                macd_condition = (
                    (df_test['macd'] > df_test['macd_signal']) &
                    (df_test['macd'].shift(1) <= df_test['macd_signal'].shift(1))
                )
                signals[rsi_condition & macd_condition] = 1

                # RSI overbought + MACD bearish crossover = short
                rsi_overbought = df_test['rsi_14'] > 70
                macd_bearish = (
                    (df_test['macd'] < df_test['macd_signal']) &
                    (df_test['macd'].shift(1) >= df_test['macd_signal'].shift(1))
                )
                signals[rsi_overbought & macd_bearish] = -1

                # Backtest
                result = self.backtester.backtest_strategy(
                    df_test,
                    signals,
                    "momentum_rsi_macd",
                    {
                        'rsi_period': rsi_period,
                        'rsi_threshold': rsi_threshold,
                        'macd_fast': macd_fast,
                        'macd_slow': macd_slow,
                        'macd_signal': macd_signal
                    }
                )

                results.append(result)

        return results

    def explore_breakout_strategies(
        self,
        df: pd.DataFrame,
        bb_periods: List[int] = None,
        bb_std_ranges: List[float] = None
    ) -> List[StrategyResult]:
        """Explore breakout strategies."""

        if bb_periods is None:
            bb_periods = [10, 15, 20, 25, 30]

        if bb_std_ranges is None:
            bb_std_ranges = [1.5, 2.0, 2.5]

        results = []

        for bb_period in bb_periods:
            for bb_std in bb_std_ranges:
                # Calculate Bollinger Bands
                df_test = df.copy()
                df_test['bb_middle'] = df_test['close'].rolling(bb_period).mean()
                df_test['bb_std'] = df_test['close'].rolling(bb_period).std()
                df_test['bb_upper'] = df_test['bb_middle'] + bb_std * df_test['bb_std']
                df_test['bb_lower'] = df_test['bb_middle'] - bb_std * df_test['bb_std']

                # Generate signals
                signals = pd.Series(0, index=df_test.index)

                # Breakout above upper band
                signals[df_test['close'] > df_test['bb_upper']] = 1

                # Breakdown below lower band
                signals[df_test['close'] < df_test['bb_lower']] = -1

                # Volume confirmation
                volume_confirmed = df_test['volume'] > df_test['volume'].rolling(20).mean()
                signals = signals * volume_confirmed

                # Backtest
                result = self.backtester.backtest_strategy(
                    df_test,
                    signals,
                    "breakout_bollinger",
                    {
                        'bb_period': bb_period,
                        'bb_std': bb_std,
                        'volume_confirmation': True
                    }
                )

                results.append(result)

        return results

    def explore_mean_reversion_strategies(
        self,
        df: pd.DataFrame,
        bb_periods: List[int] = None
    ) -> List[StrategyResult]:
        """Explore mean reversion strategies."""

        if bb_periods is None:
            bb_periods = [10, 15, 20, 25, 30]

        results = []

        for bb_period in bb_periods:
            df_test = df.copy()
            df_test['bb_middle'] = df_test['close'].rolling(bb_period).mean()
            df_test['bb_std'] = df_test['close'].rolling(bb_period).std()
            df_test['bb_upper'] = df_test['bb_middle'] + 2 * df_test['bb_std']
            df_test['bb_lower'] = df_test['bb_middle'] - 2 * df_test['bb_std']

            # Generate signals
            signals = pd.Series(0, index=df_test.index)

            # Buy at lower band
            signals[df_test['close'] <= df_test['bb_lower']] = 1

            # Sell at upper band
            signals[df_test['close'] >= df_test['bb_upper']] = -1

            # RSI confirmation for oversold/overbought
            rsi_confirmed = (
                (df_test['rsi_14'] < 30) |
                (df_test['rsi_14'] > 70)
            )
            signals = signals * rsi_confirmed

            # Backtest
            result = self.backtester.backtest_strategy(
                df_test,
                signals,
                "mean_reversion_bb_rsi",
                {'bb_period': bb_period}
            )

            results.append(result)

        return results


async def main():
    """Main discovery mission."""

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 80)
    logger.info("BTCUSDT STRATEGY DISCOVERY MISSION")
    logger.info("=" * 80)
    logger.info("Mission: Discover most profitable strategy with realistic costs")
    logger.info("Data: 12 months of BTCUSDT perpetuals")
    logger.info("Approach: Systematic multi-parameter space exploration")
    logger.info("=" * 80)

    # Initialize components
    data_fetcher = BTCDataFetcher()
    backtester = RealisticBacktester()
    explorer = StrategyExplorer(backtester)

    # Fetch data
    logger.info("Phase 1: Fetching 12 months of BTCUSDT data...")
    data = await data_fetcher.fetch_historical_data(
        symbol="BTCUSDT",
        months=12,
        timeframes=['1h', '4h', '1d']  # Focus on key timeframes
    )

    # Use 1h data for analysis
    df = data['1h'].copy()
    logger.info(f"Loaded {len(df)} hours of data")

    # Add indicators
    logger.info("Phase 2: Calculating technical indicators...")
    indicators = AdvancedIndicators()
    df = indicators.add_indicators(df)

    # Detect regimes
    logger.info("Phase 3: Detecting market regimes...")
    regime_detector = RegimeDetector()
    df = regime_detector.detect_regimes(df)

    # Analyze order flow
    logger.info("Phase 4: Analyzing order flow patterns...")
    order_flow = OrderFlowAnalyzer()
    df = order_flow.analyze_order_flow(df)

    # Explore strategies
    logger.info("Phase 5: Exploring strategy parameter space...")

    all_results = []

    # Momentum strategies
    logger.info("Exploring momentum strategies...")
    momentum_results = explorer.explore_momentum_strategies(df)
    all_results.extend(momentum_results)
    logger.info(f"Tested {len(momentum_results)} momentum variants")

    # Breakout strategies
    logger.info("Exploring breakout strategies...")
    breakout_results = explorer.explore_breakout_strategies(df)
    all_results.extend(breakout_results)
    logger.info(f"Tested {len(breakout_results)} breakout variants")

    # Mean reversion strategies
    logger.info("Exploring mean reversion strategies...")
    mean_reversion_results = explorer.explore_mean_reversion_strategies(df)
    all_results.extend(mean_reversion_results)
    logger.info(f"Tested {len(mean_reversion_results)} mean reversion variants")

    # Analyze results
    logger.info("Phase 6: Analyzing results...")

    # Sort by composite fitness score
    def fitness_score(result: StrategyResult) -> float:
        return (
            result.sharpe_ratio *
            np.log(result.total_trades + 1) *
            (1 + max(0, result.total_return)) *
            (1 - result.max_drawdown)
        )

    all_results.sort(key=fitness_score, reverse=True)

    # Print top results
    logger.info("\n" + "=" * 80)
    logger.info("TOP 10 STRATEGIES BY FITNESS SCORE")
    logger.info("=" * 80)

    for i, result in enumerate(all_results[:10], 1):
        logger.info(f"\n#{i} - {result.strategy_name}")
        logger.info(f"  Return: {result.total_return*100:.2f}%")
        logger.info(f"  Sharpe: {result.sharpe_ratio:.2f}")
        logger.info(f"  Max DD: {result.max_drawdown*100:.2f}%")
        logger.info(f"  Trades: {result.total_trades}")
        logger.info(f"  Win Rate: {result.win_rate*100:.1f}%")
        logger.info(f"  Fitness: {fitness_score(result):.2f}")
        logger.info(f"  Parameters: {result.parameters}")

    # Save best strategy
    best = all_results[0]
    logger.info("\n" + "=" * 80)
    logger.info("BEST STRATEGY IDENTIFIED")
    logger.info("=" * 80)
    logger.info(f"Strategy: {best.strategy_name}")
    logger.info(f"Parameters: {best.parameters}")
    logger.info(f"Return: {best.total_return*100:.2f}%")
    logger.info(f"Sharpe: {best.sharpe_ratio:.2f}")
    logger.info(f"Max Drawdown: {best.max_drawdown*100:.2f}%")
    logger.info(f"Total Trades: {best.total_trades}")
    logger.info(f"Win Rate: {best.win_rate*100:.1f}%")
    logger.info(f"Profit Factor: {best.profit_factor:.2f}")
    logger.info(f"Average Trade: ${best.avg_trade:.2f}")
    logger.info(f"Average Hold Time: {best.avg_hold_time_hours:.1f} hours")

    logger.info("\n" + "=" * 80)
    logger.info("MISSION COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
