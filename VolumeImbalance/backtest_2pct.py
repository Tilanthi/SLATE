#!/usr/bin/env python3
"""
Volume Imbalance Strategy - 2% Position Sizing

Uses only 2% of capital per trade for conservative risk management.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

def fetch_binance_futures_daily_data(days=365):
    """Fetch REAL perpetual futures data from Binance."""
    base_url = "https://fapi.binance.com/fapi/v1/klines"
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    all_klines = []
    current_start = start_time

    print(f"Fetching {days} days of PERPETUAL FUTURES data from Binance...")

    while current_start < end_time:
        params = {"symbol": "BTCUSDT", "interval": "1d",
                   "startTime": current_start, "endTime": end_time, "limit": 1000}
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            if not klines:
                break
            all_klines.extend(klines)
            current_start = klines[-1][0] + 1
        except Exception as e:
            print(f"Error: {e}")
            break

    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['volatility'] = df['atr'] / df['close']
    df = df.sort_index()
    print(f"✓ Loaded {len(df)} daily candles from {df.index[0]} to {df.index[-1]}")
    return df

def calculate_vi(df, period):
    """Calculate Volume Imbalance."""
    df_temp = df.copy()
    df_temp['is_up'] = df_temp['close'] > df_temp['open']
    df_temp['up_volume'] = df_temp['volume'] * df_temp['is_up']
    df_temp['down_volume'] = df_temp['volume'] * (~df_temp['is_up'])
    up_vol_sum = df_temp['up_volume'].rolling(window=period).sum()
    down_vol_sum = df_temp['down_volume'].rolling(window=period).sum()
    total_vol = df_temp['volume'].rolling(window=period).sum()
    vi = (up_vol_sum - down_vol_sum) / total_vol
    return vi

def run_backtest_2pct(df, vi_period=9, vi_threshold=0.20,
                       sl_pct=0.015, tp_pct=0.03, trail_pct=0.01,
                       initial_capital=10000):
    """
    Run backtest with 2% position sizing and honest costs.

    Position sizing: 2% of capital per trade
    """

    df_temp = df.copy()
    df_temp['vi'] = calculate_vi(df_temp, vi_period)

    # Transaction costs
    maker_fee = 0.0002
    taker_fee = 0.0004
    base_slippage_bps = 10

    capital = initial_capital
    position_size_pct = 0.02  # 2% of capital per trade
    position = None
    entry_price = None
    entry_btc_price = None
    sl_price = None
    tp_price = None
    highest = None
    lowest = None
    position_btc = None

    trades = []
    equity = []

    for i in range(vi_period, len(df_temp)):
        close = df_temp['close'].iloc[i]
        high = df_temp['high'].iloc[i]
        low = df_temp['low'].iloc[i]
        vi = df_temp['vi'].iloc[i]
        volatility = df_temp['volatility'].iloc[i]

        if pd.isna(vi) or pd.isna(volatility):
            equity.append(capital)
            continue

        slippage_bps = base_slippage_bps * (1 + volatility * 5)
        slippage_bps = max(5, min(slippage_bps, 25))
        fill_rate = max(0.80, min(0.98, 0.90 - (volatility * 0.5)))

        # Entry logic
        if position is None:
            if vi > vi_threshold:
                if np.random.random() > fill_rate:
                    equity.append(capital)
                    continue

                entry_price = close * (1 + slippage_bps / 10000)
                entry_btc_price = entry_price

                # 2% of capital as position size
                position_value_usdt = capital * position_size_pct
                position_btc = (position_value_usdt / entry_btc_price)

                if np.random.random() < 0.15:
                    fill_pct = np.random.uniform(0.30, 0.70)
                    position_btc *= fill_pct

                position = 'long'
                highest = close
                sl_price = entry_price * (1 - sl_pct)
                tp_price = entry_price * (1 + tp_pct)

            elif vi < -vi_threshold:
                if np.random.random() > fill_rate:
                    equity.append(capital)
                    continue

                entry_price = close * (1 - slippage_bps / 10000)
                entry_btc_price = entry_price

                position_value_usdt = capital * position_size_pct
                position_btc = (position_value_usdt / entry_btc_price)

                if np.random.random() < 0.15:
                    fill_pct = np.random.uniform(0.30, 0.70)
                    position_btc *= fill_pct

                position = 'short'
                lowest = close
                sl_price = entry_price * (1 + sl_pct)
                tp_price = entry_price * (1 - tp_pct)

        # Exit logic
        elif position == 'long':
            highest = max(highest, high)
            trail = highest * (1 - trail_pct)
            sl_price = max(sl_price, trail)

            if low <= sl_price:
                exit_price = sl_price * (1 - slippage_bps / 10000)
                pnl = position_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl
                trades.append({'type': 'LONG', 'pnl': pnl, 'exit': 'sl'})
                position = None
                position_btc = None

            elif high >= tp_price:
                exit_price = tp_price * (1 - slippage_bps / 10000)
                pnl = position_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl
                trades.append({'type': 'LONG', 'pnl': pnl, 'exit': 'tp'})
                position = None
                position_btc = None

            elif vi < -vi_threshold:
                exit_price = close * (1 - slippage_bps / 10000)
                pnl = position_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl
                trades.append({'type': 'LONG', 'pnl': pnl, 'exit': 'signal'})
                position = None
                position_btc = None

        elif position == 'short':
            lowest = min(lowest, low)
            trail = lowest * (1 + trail_pct)
            sl_price = min(sl_price, trail)

            if high >= sl_price:
                exit_price = sl_price * (1 + slippage_bps / 10000)
                pnl = position_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl
                trades.append({'type': 'SHORT', 'pnl': pnl, 'exit': 'sl'})
                position = None
                position_btc = None

            elif low <= tp_price:
                exit_price = tp_price * (1 + slippage_bps / 10000)
                pnl = position_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl
                trades.append({'type': 'SHORT', 'pnl': pnl, 'exit': 'tp'})
                position = None
                position_btc = None

            elif vi > vi_threshold:
                exit_price = close * (1 - slippage_bps / 10000)
                pnl = position_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl
                trades.append({'type': 'SHORT', 'pnl': pnl, 'exit': 'signal'})
                position = None
                position_btc = None

        equity.append(capital)

    return capital, trades, equity

# Main
if __name__ == "__main__":
    print("="*70)
    print("VOLUME IMBALANCE - 2% POSITION SIZING")
    print("Perpetual Futures with Honest Costs")
    print("="*70)

    df = fetch_binance_futures_daily_data(days=365)

    if df is None or len(df) < 100:
        print("Error: Could not fetch data")
        sys.exit(1)

    print("\nPosition Sizing: 2% of capital per trade")
    print("This means with $10,000 capital, each trade is ~$200 notional value\n")

    final_cap, trades, equity = run_backtest_2pct(df)

    total_return = (final_cap - 10000) / 10000
    max_dd = (pd.Series(equity).cummax() - pd.Series(equity)).max() / pd.Series(equity).cummax().max()

    if len(trades) > 0:
        win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades)
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else 0
    else:
        win_rate = 0
        pf = 0

    print("="*70)
    print("RESULTS WITH 2% POSITION SIZING")
    print("="*70)
    print(f"Initial Capital: $10,000")
    print(f"Final Capital: ${final_cap:,.2f}")
    print(f"Total Return: {total_return*100:+.2f}%")
    print(f"Max Drawdown: {max_dd*100:.2f}%")
    print(f"Win Rate: {win_rate*100:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Number of Trades: {len(trades)}")
    print("="*70)

    # Calculate average position size
    if df['close'].mean() > 0:
        avg_btc_price = df['close'].mean()
        avg_position_value = 10000 * 0.02
        avg_btc_position = avg_position_value / avg_btc_price
        print(f"\nPosition Size Details:")
        print(f"  2% of $10,000 = ${avg_position_value:,.0f} per trade")
        print(f"  At avg BTC price ${avg_btc_price:,.0f}")
        print(f"  Position size: ~{avg_btc_position:.4f} BTC per trade")
