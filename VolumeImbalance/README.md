# Volume Imbalance Strategy Simulator

## Overview

This Python implementation reproduces the Volume Imbalance (VI) trading strategy described in "Medium_Volume_Imbalancee.pdf". The strategy uses buying and selling pressure measured through volume analysis to generate trading signals.

## Strategy Principle

**Volume Imbalance (VI) Indicator:**
```
VI = (Volume of up bars - Volume of down bars) / Total Volume
```

- **VI > +threshold**: Strong buying pressure → LONG signal
- **VI < -threshold**: Strong selling pressure → SHORT signal
- **VI around 0**: Balanced market → No signal

## Implementation Details

### Parameters (No Optimization - Default Values)

| Parameter | Value | Description |
|-----------|-------|-------------|
| VI Period | 12 | Lookback period for VI calculation |
| VI Threshold | ±0.30 | Threshold for entry signals |
| Initial Capital | $10,000 | Starting capital |
| Lot Size | 0.01 BTC | Fixed position size |
| Stop Loss | 2.0% | Maximum loss per trade |
| Take Profit | 4.0% | Target profit per trade |
| Trailing Stop | 1.5% | Trailing stop for profit protection |

### Entry & Exit Rules

**Long Entry:**
- VI > 0.30 (buying pressure dominant)
- Enter at current close price

**Short Entry:**
- VI < -0.30 (selling pressure dominant)
- Enter at current close price

**Exit Conditions (for both Long and Short):**
1. Stop Loss hit (2% from entry)
2. Take Profit hit (4% from entry)
3. Trailing Stop activated (1.5% from favorable extreme)
4. Reverse signal (opposite VI threshold crossed)

### Money Management

- **Fixed lot size**: 0.01 BTC per trade
- **No pyramiding**: One position at a time
- **Risk per trade**: Maximum 2% of entry price
- **Reward ratio**: 2:1 (4% TP vs 2% SL)

## Backtest Results

### Data Source
- **Exchange**: Binance
- **Symbol**: BTCUSDT (Spot)
- **Timeframe**: 1-hour candles
- **Period**: November 11, 2025 to May 10, 2026 (~180 days)
- **Candles**: 4,319

### Performance Summary

| Metric | Value |
|--------|-------|
| Initial Capital | $10,000.00 |
| Final Equity | $9,406.33 |
| **Total Return** | **-5.94%** |
| Max Drawdown | -6.05% |
| Total Trades | 342 |
| Win Rate | 33.63% |
| Profit Factor | 0.58 |

### Trade Breakdown

| Category | Count | Win Rate |
|----------|-------|----------|
| Long Trades | 145 | 33.10% |
| Short Trades | 197 | 34.01% |
| **Total** | **342** | **33.63%** |

### Exit Reason Analysis

| Reason | Count | Percentage |
|--------|-------|------------|
| Stop Loss | 301 | 88.0% |
| Signal Reverse | 40 | 11.7% |
| Take Profit | 1 | 0.3% |

## Analysis

### Key Observations

1. **High Loss Rate**: 88% of trades hit stop loss, indicating the VI threshold of ±0.30 may be too sensitive or the stop loss too tight.

2. **Poor Win Rate**: 33.63% win rate with a profit factor of 0.58 means losses consistently outweigh gains.

3. **Payoff Ratio**: 1.14 (average win $6.97 / average loss $6.14) shows wins are slightly larger than losses, but not enough to overcome the low win rate.

4. **Long vs Short**: Similar performance on both sides (33.10% vs 34.01% win rate), suggesting the strategy is directionally balanced.

### Comparison with Figure 4

The paper's Figure 4 shows a steadily growing equity curve. Our results differ significantly:

**Possible Reasons:**
1. **Different Market Conditions**: The paper may have tested on different historical data
2. **Transaction Costs**: Our implementation uses realistic stop losses; the paper may not have
3. **Data Quality**: Spot vs Futures data differences
4. **Parameter Optimization**: Figure 4 may use optimized parameters, not defaults

### Recommendations for Improvement

1. **Optimize Parameters**:
   - Test VI periods: 6, 9, 12, 18, 24
   - Test VI thresholds: 0.15, 0.20, 0.25, 0.30, 0.35, 0.40
   - Test stop loss: 1.5%, 2%, 2.5%, 3%
   - Test take profit: 3%, 4%, 5%, 6%

2. **Add Filters**:
   - Trend filter (only trade with trend)
   - Volatility filter (avoid low volatility periods)
   - Time-of-day filter (avoid specific hours)

3. **Improve Money Management**:
   - Dynamic lot sizing based on volatility
   - Position sizing based on VI strength
   - Maximum daily loss limit

## Files Generated

```
VolumeImbalance/
├── volume_imbalance_simulator.py     # Main simulator script
├── volume_imbalance_equity_curve.png # Visualization (3-panel plot)
├── volume_imbalance_statistics.txt   # Detailed statistics
└── README.md                         # This file
```

## Usage

```bash
# Run the simulator
python volume_imbalance_simulator.py

# Results will be saved in VolumeImbalance/ folder
```

## Customization

To test different parameters, modify these lines in the script:

```python
equity_curve, trades = run_volume_imbalance_backtest(
    df,
    vi_period=12,           # Change VI period
    vi_threshold=0.30,       # Change VI threshold
    initial_capital=10000,
    lot_size=0.01,
    stop_loss_pct=0.02,      # Change stop loss
    take_profit_pct=0.04,    # Change take profit
    trailing_stop_pct=0.015  # Change trailing stop
)
```

## Conclusion

The Volume Imbalance strategy with default parameters is **not profitable** on the tested BTCUSDT data (Nov 2025 - May 2026), losing 5.94% with a maximum drawdown of 6.05%.

The strategy requires optimization and additional filters to become viable for live trading. The high stop loss rate (88%) suggests the basic VI signal alone is insufficient for consistent profitability in current market conditions.

---

**Implementation Date**: May 10, 2026
**Data Source**: Binance API (REAL data, not simulated)
**Status**: Unoptimized version matching Figure 4 parameters from paper
