#!/usr/bin/env python3
"""
One Week Volume Imbalance Backtest
Run a focused 1-week backtest on recent historical data

Refactored to use consolidated SLATE modules - eliminates code duplication
"""

import matplotlib.pyplot as plt
import pandas as pd

# Use consolidated modules instead of duplicated code
import sys
sys.path.insert(0, '/Users/gjw255/astrodata/SWARM/SLATE')

from slate_core.data.binance_fetcher import BinanceFetcher
from slate_core.indicators.volume_imbalance import VolumeImbalance
from slate_core.config.constants import (
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    VI_PERIOD_DEFAULT,
    VI_THRESHOLD_DEFAULT,
    DEFAULT_INITIAL_CAPITAL_USDT,
    DEFAULT_LOT_SIZE_BTC,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    DEFAULT_TRAILING_STOP_PCT
)

if __name__ == "__main__":
    # Fetch data using consolidated module
    fetcher = BinanceFetcher()
    df = fetcher.fetch_weeks(symbol=DEFAULT_SYMBOL, interval=DEFAULT_INTERVAL, weeks_back=1)

    if len(df) > 100:
        # Calculate VI using consolidated module
        vi_calc = VolumeImbalance(period=VI_PERIOD_DEFAULT)
        df['vi'] = vi_calc.calculate(df)

        capital = DEFAULT_INITIAL_CAPITAL_USDT
        position = None
        entry_price = None
        entry_time = None
        stop_loss = None
        take_profit = None
        highest_since_entry = None
        lowest_since_entry = None

        trades = []
        equity_curve = []

        print(f"\n{'='*50}")
        print(f"BACKTEST: 1 Week Volume Imbalance")
        print(f"{'='*50}")
        print(f"VI Period: {VI_PERIOD_DEFAULT}, Threshold: {VI_THRESHOLD_DEFAULT:.2f}")
        print(f"Capital: ${capital:,.0f}")
        print(f"{'='*50}\n")

        for i in range(VI_PERIOD_DEFAULT, len(df)):
            current_time = df.index[i]
            close = df['close'].iloc[i]
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            vi = df['vi'].iloc[i]

            if pd.isna(vi):
                continue

            if position is None:
                if vi > VI_THRESHOLD_DEFAULT:
                    position = 'long'
                    entry_price = close
                    entry_time = current_time
                    highest_since_entry = close
                    stop_loss = entry_price * (1 - DEFAULT_STOP_LOSS_PCT)
                    take_profit = entry_price * (1 + DEFAULT_TAKE_PROFIT_PCT)
                    print(f"LONG entry at ${close:,.2f} (VI: {vi:.2f})")

                elif vi < -VI_THRESHOLD_DEFAULT:
                    position = 'short'
                    entry_price = close
                    entry_time = current_time
                    lowest_since_entry = close
                    stop_loss = entry_price * (1 + DEFAULT_STOP_LOSS_PCT)
                    take_profit = entry_price * (1 - DEFAULT_TAKE_PROFIT_PCT)
                    print(f"SHORT entry at ${close:,.2f} (VI: {vi:.2f})")

            elif position == 'long':
                highest_since_entry = max(highest_since_entry, high)
                trailing_stop = highest_since_entry * (1 - DEFAULT_TRAILING_STOP_PCT)
                stop_loss = max(stop_loss, trailing_stop)

                if low <= stop_loss:
                    exit_price = stop_loss
                    pnl = (exit_price - entry_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades.append({'time': current_time, 'type': 'LONG', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'reason': 'SL'})
                    print(f"LONG exit at ${exit_price:,.2f} (SL) PnL: ${pnl:+.2f}")
                    position = None

                elif high >= take_profit:
                    exit_price = take_profit
                    pnl = (exit_price - entry_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades.append({'time': current_time, 'type': 'LONG', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'reason': 'TP'})
                    print(f"LONG exit at ${exit_price:,.2f} (TP) PnL: ${pnl:+.2f}")
                    position = None

                elif vi < -VI_THRESHOLD_DEFAULT:
                    exit_price = close
                    pnl = (exit_price - entry_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades.append({'time': current_time, 'type': 'LONG', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'reason': 'REV'})
                    print(f"LONG exit at ${exit_price:,.2f} (Rev) PnL: ${pnl:+.2f}")
                    position = None

            elif position == 'short':
                lowest_since_entry = min(lowest_since_entry, low)
                trailing_stop = lowest_since_entry * (1 + DEFAULT_TRAILING_STOP_PCT)
                stop_loss = min(stop_loss, trailing_stop)

                if high >= stop_loss:
                    exit_price = stop_loss
                    pnl = (entry_price - exit_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades.append({'time': current_time, 'type': 'SHORT', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'reason': 'SL'})
                    print(f"SHORT exit at ${exit_price:,.2f} (SL) PnL: ${pnl:+.2f}")
                    position = None

                elif low <= take_profit:
                    exit_price = take_profit
                    pnl = (entry_price - exit_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades.append({'time': current_time, 'type': 'SHORT', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'reason': 'TP'})
                    print(f"SHORT exit at ${exit_price:,.2f} (TP) PnL: ${pnl:+.2f}")
                    position = None

                elif vi > VI_THRESHOLD_DEFAULT:
                    exit_price = close
                    pnl = (entry_price - exit_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades.append({'time': current_time, 'type': 'SHORT', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'reason': 'REV'})
                    print(f"SHORT exit at ${exit_price:,.2f} (Rev) PnL: ${pnl:+.2f}")
                    position = None

            equity = capital
            if position == 'long' and entry_price:
                equity += (close - entry_price) * DEFAULT_LOT_SIZE_BTC
            elif position == 'short' and entry_price:
                equity += (entry_price - close) * DEFAULT_LOT_SIZE_BTC

            equity_curve.append({'time': current_time, 'equity': equity})

        equity = pd.DataFrame(equity_curve).set_index('time')

        print(f"\n{'='*50}")
        print(f"RESULTS")
        print(f"{'='*50}")
        print(f"Trades: {len(trades)}")
        print(f"Final Capital: ${capital:,.2f}")
        print(f"Return: {(capital - DEFAULT_INITIAL_CAPITAL_USDT) / DEFAULT_INITIAL_CAPITAL_USDT * 100:+.2f}%")

        if trades:
            wins = sum(1 for t in trades if t['pnl'] > 0)
            print(f"Win Rate: {wins / len(trades) * 100:.1f}%")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

        ax1.plot(df.index, df['close'], color='#2c3e50', linewidth=1)
        ax1.set_ylabel('Price ($)')
        ax1.set_title('BTCUSDT Price')
        ax1.grid(True, alpha=0.3)

        ax2.plot(df.index, df['vi'], color='#3498db', linewidth=1.5)
        ax2.axhline(VI_THRESHOLD_DEFAULT, color='g', linestyle='--', alpha=0.5)
        ax2.axhline(-VI_THRESHOLD_DEFAULT, color='r', linestyle='--', alpha=0.5)
        ax2.set_ylabel('Volume Imbalance')
        ax2.set_title(f'VI Indicator (Period: {VI_PERIOD_DEFAULT})')
        ax2.grid(True, alpha=0.3)

        ax3.plot(equity.index, equity['equity'], color='#f39c12', linewidth=2)
        ax3.axhline(DEFAULT_INITIAL_CAPITAL_USDT, color='gray', linestyle='--', alpha=0.5)
        ax3.set_ylabel('Equity ($)')
        ax3.set_xlabel('Time')
        ax3.set_title(f'Equity Curve - Final: ${capital:,.2f}')
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('one_week_backtest.png', dpi=150)
        print(f"\nChart saved: one_week_backtest.png")
