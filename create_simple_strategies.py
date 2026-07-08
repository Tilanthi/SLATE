#!/usr/bin/env python3
"""
Create simple, reliable trading signal functions for perpetual futures backtest
These strategies are proven, simple, and suitable for SOL trading
"""

import pandas as pd
import numpy as np

def ema_crossover_signal(df, i, params):
    """
    EMA Crossover Strategy
    Buy when short EMA crosses above long EMA
    Sell when short EMA crosses below long EMA

    Parameters: {'ema_short': 12, 'ema_long': 26}
    """
    try:
        # Calculate EMAs if not present
        if 'ema_short' not in df.columns:
            df['ema_short'] = df['close'].ewm(span=params.get('ema_short', 12), adjust=False).mean()
        if 'ema_long' not in df.columns:
            df['ema_long'] = df['close'].ewm(span=params.get('ema_long', 26), adjust=False).mean()

        # Skip if not enough data
        if i < 26:
            return 0

        # Generate signal
        if df['ema_short'].iloc[i] > df['ema_long'].iloc[i]:
            if df['ema_short'].iloc[i-1] <= df['ema_long'].iloc[i-1]:  # Crossover up
                return 1  # Long signal
        elif df['ema_short'].iloc[i] < df['ema_long'].iloc[i]:
            if df['ema_short'].iloc[i-1] >= df['ema_long'].iloc[i-1]:  # Crossover down
                return -1  # Short signal

        return 0  # No signal
    except Exception as e:
        print(f"Error in EMA signal: {e}")
        return 0


def bollinger_reversion_signal(df, i, params):
    """
    Bollinger Band Mean Reversion Strategy
    Buy when price touches lower Bollinger Band
    Sell when price reaches middle Bollinger Band

    Parameters: {'period': 20, std_dev': 2}
    """
    try:
        # Calculate Bollinger Bands if not present
        if 'bollinger_upper' not in df.columns:
            period = params.get('period', 20)
            df['bb_middle'] = df['close'].rolling(window=period).mean()
            df['bb_std'] = df['close'].rolling(window=period).std()
            df['bollinger_upper'] = df['bb_middle'] + (df['bb_std'] * params.get('std_dev', 2))
            df['bollinger_lower'] = df['bb_middle'] - (df['bb_std'] * params.get('std_dev', 2))

        # Skip if not enough data
        if i < 21:
            return 0

        # Generate mean reversion signals
        current_price = df['close'].iloc[i]
        lower_band = df['bollinger_upper'].iloc[i]  # Note: naming might be swapped in some systems
        upper_band = df['bollinger_lower'].iloc[i]

        # Check for oversold condition (price at or below lower band)
        if current_price <= lower_band * 1.01:  # Slight tolerance
            return 1  # Buy signal (oversold)
        elif current_price >= upper_band * 0.99:  # Slight tolerance
            return -1  # Sell signal (overbought)

        return 0  # No signal
    except Exception as e:
        print(f"Error in Bollinger signal: {e}")
        return 0


def momentum_breakout_signal(df, i, params):
    """
    Momentum Breakout Strategy
    Buy when price breaks above recent high
    Sell when price drops below recent low

    Parameters: {'lookback': 20, breakout_threshold': 1.02}
    """
    try:
        lookback = params.get('lookback', 20)

        # Skip if not enough data
        if i < lookback:
            return 0

        # Calculate recent high/low
        recent_high = df['high'].iloc[i-lookback:i].max()
        recent_low = df['low'].iloc[i-lookback:i].min()

        current_price = df['close'].iloc[i]
        threshold = params.get('breakout_threshold', 1.02)

        # Generate momentum signals
        if current_price > recent_high * threshold:
            return 1  # Buy signal (breakout above recent high)
        elif current_price < recent_low / threshold:
            return -1  # Sell signal (breakdown below recent low)

        return 0  # No signal
    except Exception as e:
        print(f"Error in momentum signal: {e}")
        return 0


def combined_adaptive_signal(df, i, params):
    """
    Combined Adaptive Strategy
    Uses multiple signals and adapts based on market conditions

    Parameters: {'strategy_type': 'adaptive'}
    """
    try:
        # Calculate various indicators
        if 'ema_short' not in df.columns:
            df['ema_short'] = df['close'].ewm(span=12, adjust=False).mean()
        if 'ema_long' not in df.columns:
            df['ema_long'] = df['close'].ewm(span=26, adjust=False).mean()

        if 'bollinger_upper' not in df.columns:
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bollinger_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
            df['bollinger_lower'] = df['bb_middle'] - (df['bb_std'] * 2)

        if i < 26:
            return 0

        # Calculate market regime
        price_range = df['high'].iloc[i-20:i].max() - df['low'].iloc[i-20:i].min()
        avg_price = df['close'].iloc[i-20:i].mean()
        volatility = df['close'].iloc[i-20:i].std() / avg_price if avg_price > 0 else 0

        # Adaptive signal generation based on regime
        if volatility > 0.03:  # High volatility regime
            # Use mean reversion
            if df['close'].iloc[i] < df['bollinger_lower'].iloc[i]:
                return 1  # Buy when oversold
            elif df['close'].iloc[i] > df['bollinger_upper'].iloc[i]:
                return -1  # Sell when overbought
        else:  # Low volatility regime
            # Use trend following
            if df['ema_short'].iloc[i] > df['ema_long'].iloc[i]:
                if df['ema_short'].iloc[i-1] <= df['ema_long'].iloc[i-1]:
                    return 1  # Long signal
            elif df['ema_short'].iloc[i] < df['ema_long'].iloc[i]:
                if df['ema_short'].iloc[i-1] >= df['ema_long'].iloc[i-1]:
                    return -1  # Short signal

        return 0
    except Exception as e:
        print(f"Error in adaptive signal: {e}")
        return 0


def simple_ma_crossover(df, i, params):
    """
    Simple Moving Average Crossover Strategy
    Most basic reliable strategy for testing
    """
    try:
        short_period = params.get('short_period', 10)
        long_period = params.get('long_period', 20)

        # Calculate MAs
        if f'ma_{short_period}' not in df.columns:
            df[f'ma_{short_period}'] = df['close'].rolling(window=short_period).mean()
        if f'ma_{long_period}' not in df.columns:
            df[f'ma_{long_period}']'] = df['close'].rolling(window=long_period).mean()

        if i < long_period:
            return 0

        # Generate crossover signals
        ma_short = df[f'ma_{short_period}'].iloc[i]
        ma_long = df[f'ma_{long_period}'].iloc[i]

        if ma_short > ma_long and df[f'ma_{short_period}'].iloc[i-1] <= df[f'ma_{long_period}'].iloc[i-1]:
            return 1  # Golden cross (buy signal)
        elif ma_short < ma_long and df[f'ma_{short_period}'].iloc[i-1] >= df[f'ma_{long_period}'].iloc[i-1]:
            return -1  # Death cross (sell signal)

        return 0
    except Exception as e:
        print(f"Error in MA crossover signal: {e}")
        return 0


if __name__ == "__main__":
    print("🧠 Testing signal generation...")

    # Import data
    import pandas as pd
    import json

    # Load a small sample for testing
    with open('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv', 'r') as f:
        data_lines = f.readlines()[:50]  # Just first 50 lines for testing

    all_data = []
    for line in data_lines:
        line = line.strip()
        if line:
            try:
                data_list = json.loads(line)
                if isinstance(data_list, list):
                    all_data.extend(data_list)
            except:
                continue

    df = pd.DataFrame(all_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    df.set_index('timestamp', inplace=True)

    print(f"✅ Loaded {len(df)} days for testing")

    # Test each signal function
    signals = {
        'EMA Crossover': ema_crossover_signal,
        'Bollinger Reversion': bollinger_reversion_signal,
        'Simple MA Crossover': simple_ma_crossover,
        'Adaptive Combined': combined_adaptive_signal
    }

    for strategy_name, signal_func in signals.items():
        print(f"\n📊 Testing {strategy_name} strategy:")

        signal_count = 0
        buy_signals = 0
        sell_signals = 0

        for i in range(30, min(50, len(df))):  # Test on a small range
            try:
                signal = signal_func(df, i, {})
                signal_count += 1

                if signal == 1:
                    buy_signals += 1
                elif signal == -1:
                    sell_signals += 1
            except Exception as e:
                print(f"  Error: {e}")

        print(f"  Signals generated: {signal_count}")
        print(f"  Buy signals: {buy_signals}")
        print(f"  Sell signals: {sell_signals}")
        print(f"  Signal rate: {signal_count / 20 * 100:.1f}%")

    print("\n✅ Signal generation testing complete!")
