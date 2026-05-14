"""
Unified Backtest Engine
Consolidates duplicated backtest logic across multiple files
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass
from datetime import datetime

from ..config.constants import (
    DEFAULT_INITIAL_CAPITAL_USDT,
    DEFAULT_LOT_SIZE_BTC,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    DEFAULT_TRAILING_STOP_PCT,
    VI_PERIOD_DEFAULT,
    VI_THRESHOLD_DEFAULT,
    MAKER_FEE,
    TAKER_FEE
)
from ..indicators.volume_imbalance import VolumeImbalance


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: datetime
    exit_time: Optional[datetime]
    type: Literal['LONG', 'SHORT']
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    reason: Optional[str]
    vi_at_entry: float = 0.0


@dataclass
class BacktestConfig:
    """Configuration for backtest parameters."""
    vi_period: int = VI_PERIOD_DEFAULT
    vi_threshold: float = VI_THRESHOLD_DEFAULT
    initial_capital: float = DEFAULT_INITIAL_CAPITAL_USDT
    lot_size: float = DEFAULT_LOT_SIZE_BTC
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT
    take_profit_pct: float = DEFAULT_TAKE_PROFIT_PCT
    trailing_stop_pct: float = DEFAULT_TRAILING_STOP_PCT
    maker_fee: float = MAKER_FEE
    taker_fee: float = TAKER_FEE


@dataclass
class BacktestResults:
    """Results from a backtest run."""
    equity_curve: pd.DataFrame
    trades: List[Trade]
    final_capital: float
    total_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int


class BacktestEngine:
    """
    Unified backtest engine for strategy testing.

    Supports Volume Imbalance strategy with configurable parameters.
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Initialize backtest engine.

        Parameters:
        - config: BacktestConfig with parameters (uses defaults if None)
        """
        self.config = config or BacktestConfig()
        self.vi_calculator = VolumeImbalance(period=self.config.vi_period)

    def run(self, df: pd.DataFrame, verbose: bool = True) -> BacktestResults:
        """
        Run backtest on price data.

        Parameters:
        - df: DataFrame with OHLCV data
        - verbose: Print trade details

        Returns:
        - BacktestResults with performance metrics
        """
        df = df.copy()
        df['vi'] = self.vi_calculator.calculate(df)

        capital = self.config.initial_capital
        position: Optional[Literal['long', 'short']] = None
        entry_price: Optional[float] = None
        entry_time: Optional[datetime] = None
        stop_loss: Optional[float] = None
        take_profit: Optional[float] = None
        highest_since_entry: Optional[float] = None
        lowest_since_entry: Optional[float] = None

        trades: List[Trade] = []
        equity_curve = []

        if verbose:
            self._print_header()

        for i in range(self.config.vi_period, len(df)):
            current_time = df.index[i]
            close = df['close'].iloc[i]
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            vi = df['vi'].iloc[i]

            if pd.isna(vi):
                continue

            # Entry logic
            if position is None:
                position, entry_price, entry_time, stop_loss, take_profit, highest_since_entry, lowest_since_entry = \
                    self._check_entry(df, i, position, entry_price, entry_time, stop_loss, take_profit,
                                    highest_since_entry, lowest_since_entry, verbose, trades, vi)

            # Exit logic
            elif position == 'long':
                position, entry_price, entry_time, stop_loss, take_profit = \
                    self._check_long_exit(current_time, close, high, low, vi, entry_price, entry_time,
                                        stop_loss, take_profit, highest_since_entry, capital,
                                        verbose, trades)

            elif position == 'short':
                position, entry_price, entry_time, stop_loss, take_profit = \
                    self._check_short_exit(current_time, close, high, low, vi, entry_price, entry_time,
                                         stop_loss, take_profit, lowest_since_entry, capital,
                                         verbose, trades)

            # Calculate equity
            equity = capital
            if position == 'long' and entry_price:
                equity += (close - entry_price) * self.config.lot_size
            elif position == 'short' and entry_price:
                equity += (entry_price - close) * self.config.lot_size

            equity_curve.append({'time': current_time, 'equity': equity})

        equity_df = pd.DataFrame(equity_curve).set_index('time')
        return self._calculate_results(equity_df, trades, capital)

    def _check_entry(self, df, i, position, entry_price, entry_time, stop_loss, take_profit,
                     highest_since_entry, lowest_since_entry, verbose, trades, vi):
        """Check for entry signals."""
        current_time = df.index[i]
        close = df['close'].iloc[i]

        if vi > self.config.vi_threshold:
            position = 'long'
            entry_price = close
            entry_time = current_time
            highest_since_entry = close
            stop_loss = entry_price * (1 - self.config.stop_loss_pct)
            take_profit = entry_price * (1 + self.config.take_profit_pct)
            trades.append(Trade(
                entry_time=current_time,
                exit_time=None,
                type='LONG',
                entry_price=close,
                exit_price=None,
                pnl=None,
                reason=None,
                vi_at_entry=vi
            ))
            if verbose:
                print(f"LONG  | {current_time.strftime('%m/%d %H:%M')} | ${close:,.2f} | VI: {vi:+.2f}")

        elif vi < -self.config.vi_threshold:
            position = 'short'
            entry_price = close
            entry_time = current_time
            lowest_since_entry = close
            stop_loss = entry_price * (1 + self.config.stop_loss_pct)
            take_profit = entry_price * (1 - self.config.take_profit_pct)
            trades.append(Trade(
                entry_time=current_time,
                exit_time=None,
                type='SHORT',
                entry_price=close,
                exit_price=None,
                pnl=None,
                reason=None,
                vi_at_entry=vi
            ))
            if verbose:
                print(f"SHORT | {current_time.strftime('%m/%d %H:%M')} | ${close:,.2f} | VI: {vi:+.2f}")

        return position, entry_price, entry_time, stop_loss, take_profit, highest_since_entry, lowest_since_entry

    def _check_long_exit(self, current_time, close, high, low, vi, entry_price, entry_time,
                         stop_loss, take_profit, highest_since_entry, capital, verbose, trades):
        """Check exit conditions for long positions."""
        highest_since_entry = max(highest_since_entry, high)
        trailing_stop = highest_since_entry * (1 - self.config.trailing_stop_pct)
        stop_loss = max(stop_loss, trailing_stop)

        exit_triggered = False
        exit_price = None
        exit_reason = None

        if low <= stop_loss:
            exit_price = stop_loss
            exit_reason = 'SL'
            exit_triggered = True
        elif high >= take_profit:
            exit_price = take_profit
            exit_reason = 'TP'
            exit_triggered = True
        elif vi < -self.config.vi_threshold:
            exit_price = close
            exit_reason = 'REV'
            exit_triggered = True

        if exit_triggered:
            pnl = (exit_price - entry_price) * self.config.lot_size
            capital += pnl
            trades[-1].exit_time = current_time
            trades[-1].exit_price = exit_price
            trades[-1].pnl = pnl
            trades[-1].reason = exit_reason
            if verbose:
                print(f"EXIT LONG | {current_time.strftime('%m/%d %H:%M')} | ${exit_price:,.2f} | {exit_reason} | PnL: ${pnl:+.2f}")
            return None, None, None, None, None

        return 'long', entry_price, entry_time, stop_loss, take_profit

    def _check_short_exit(self, current_time, close, high, low, vi, entry_price, entry_time,
                          stop_loss, take_profit, lowest_since_entry, capital, verbose, trades):
        """Check exit conditions for short positions."""
        lowest_since_entry = min(lowest_since_entry, low)
        trailing_stop = lowest_since_entry * (1 + self.config.trailing_stop_pct)
        stop_loss = min(stop_loss, trailing_stop)

        exit_triggered = False
        exit_price = None
        exit_reason = None

        if high >= stop_loss:
            exit_price = stop_loss
            exit_reason = 'SL'
            exit_triggered = True
        elif low <= take_profit:
            exit_price = take_profit
            exit_reason = 'TP'
            exit_triggered = True
        elif vi > self.config.vi_threshold:
            exit_price = close
            exit_reason = 'REV'
            exit_triggered = True

        if exit_triggered:
            pnl = (entry_price - exit_price) * self.config.lot_size
            capital += pnl
            trades[-1].exit_time = current_time
            trades[-1].exit_price = exit_price
            trades[-1].pnl = pnl
            trades[-1].reason = exit_reason
            if verbose:
                print(f"EXIT SHORT| {current_time.strftime('%m/%d %H:%M')} | ${exit_price:,.2f} | {exit_reason} | PnL: ${pnl:+.2f}")
            return None, None, None, None, None

        return 'short', entry_price, entry_time, stop_loss, take_profit

    def _calculate_results(self, equity_df: pd.DataFrame, trades: List[Trade], final_capital: float) -> BacktestResults:
        """Calculate backtest performance metrics."""
        total_return = (final_capital - self.config.initial_capital) / self.config.initial_capital
        max_drawdown = (equity_df['equity'].min() - equity_df['equity'].max()) / equity_df['equity'].max()

        closed_trades = [t for t in trades if t.exit_time is not None]
        total_trades = len(closed_trades)

        if total_trades > 0:
            winning_trades = sum(1 for t in closed_trades if t.pnl > 0)
            win_rate = winning_trades / total_trades

            gross_profit = sum(t.pnl for t in closed_trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in closed_trades if t.pnl < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        else:
            win_rate = 0
            profit_factor = 0

        return BacktestResults(
            equity_curve=equity_df,
            trades=trades,
            final_capital=final_capital,
            total_return=total_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades
        )

    def _print_header(self):
        """Print backtest header."""
        print(f"\n{'='*60}")
        print(f"BACKTEST: Volume Imbalance Strategy")
        print(f"{'='*60}")
        print(f"VI Period: {self.config.vi_period}, Threshold: ±{self.config.vi_threshold:.2f}")
        print(f"Initial Capital: ${self.config.initial_capital:,.0f}")
        print(f"Stop Loss: {self.config.stop_loss_pct*100:.1f}%, Take Profit: {self.config.take_profit_pct*100:.1f}%")
        print(f"Trailing Stop: {self.config.trailing_stop_pct*100:.1f}%")
        print(f"{'='*60}\n")


# Convenience function for quick backtests
def run_backtest(df: pd.DataFrame,
                 vi_period: int = VI_PERIOD_DEFAULT,
                 vi_threshold: float = VI_THRESHOLD_DEFAULT,
                 initial_capital: float = DEFAULT_INITIAL_CAPITAL_USDT,
                 verbose: bool = True) -> BacktestResults:
    """
    Quick backtest function (backward compatible).

    Parameters:
    - df: DataFrame with OHLCV data
    - vi_period: VI calculation period
    - vi_threshold: VI signal threshold
    - initial_capital: Starting capital
    - verbose: Print trade details

    Returns:
    - BacktestResults
    """
    config = BacktestConfig(
        vi_period=vi_period,
        vi_threshold=vi_threshold,
        initial_capital=initial_capital
    )
    engine = BacktestEngine(config)
    return engine.run(df, verbose=verbose)
