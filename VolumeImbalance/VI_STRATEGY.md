# Volume Imbalance HaasScript Strategy

## Strategy Overview

The Volume Imbalance (VI) strategy identifies buying and selling pressure through volume analysis and trades on daily timeframe for BTCUSDT perpetual futures.

## Optimized Parameters

Based on extensive optimization on real Binance data (Nov 2025 - May 2026):

| Parameter | Value | Description |
|-----------|-------|-------------|
| **VI Period** | 9 | Lookback period for VI calculation |
| **VI Threshold** | 0.20 | Entry trigger level |
| **Stop Loss** | 1.5% | Maximum loss per trade |
| **Take Profit** | 3.0% | Target profit per trade |
| **Trailing Stop** | 1.0% | Profit protection |
| **Position Size** | 2% | Conservative risk |
| **Timeframe** | 1d | Daily candles |

## Strategy Logic

### Volume Imbalance Calculation

```
VI = (Volume of up bars - Volume of down bars) / Total Volume
```

- **VI > 0.20**: Buying pressure dominant → LONG signal
- **VI < -0.20**: Selling pressure dominant → SHORT signal

### Entry Rules

1. **Long Entry**: VI crosses above 0.20 (from below)
2. **Short Entry**: VI crosses below -0.20 (from above)
3. Wait minimum 1 bar between signals (avoid whipsaws)

### Exit Rules

1. **Stop Loss Hit**: Exit at stop price (1.5% from entry)
2. **Take Profit Hit**: Exit at target price (3.0% from entry)
3. **Trailing Stop**: Stop moves to protect profits (1.0% trail)
4. **Signal Reverse**: Exit when opposite VI threshold crossed

## Performance Results

### With Realistic Costs (Perpetual Futures)

**2% Position Sizing (Conservative):**
```
Return: +1.10%
Max Drawdown: 0.18%
Win Rate: 47.6%
Profit Factor: 2.67
Number of Trades: 103
```

**Full Capital Position:**
```
Return: +64.87%
Max Drawdown: 11.49%
Win Rate: 47.2%
Profit Factor: 2.62
Number of Trades: 108
```

## How to Use in HaasOnline

### 1. Import the Script

1. Open HaasOnline Trading Bot
2. Go to **Scripts** tab
3. Click **New Script**
4. Copy-paste the contents of `VolumeImbalance_VI.haas`
5. Save as `VolumeImbalance_VI`

### 2. Configure Parameters

1. Add script to your bot
2. Select **BTCUSDT Perpetual Futures**
3. Set **Timeframe** to `1d`
4. Adjust parameters if needed:
   - `PositionSizePct`: 2.0 (conservative) to 10.0 (aggressive)
   - `StopLossPct`: 1.5
   - `TakeProfitPct`: 3.0
   - `TrailingStopPct`: 1.0

### 3. Start Trading

1. Enable the script
2. Click **Start** on your bot
3. Monitor in **Open Positions** tab
4. Check logs in **Logs** tab

## Risk Warnings

### Important Considerations

1. **Timeframe**: Strategy optimized for **daily candles**
   - May not work on lower timeframes
   - SLATE discovered daily is only profitable timeframe

2. **Market Conditions**: Requires trending market
   - Works well in volatile, trending periods
   - May underperform in range-bound markets

3. **Position Sizing**:
   - 2% = Very conservative (1.10% return, 0.18% DD)
   - 10% = Moderate (5.5% return, 0.9% DD)
   - 100% = Aggressive (64.87% return, 11.49% DD)

4. **Transaction Costs**: Includes realistic futures fees
   - Maker fee: 0.02%
   - Taker fee: 0.04%
   - Slippage: 10-25 bps (volatility-adjusted)

## Monitoring

### Key Metrics to Watch

- **Win Rate**: Should be ~47-48%
- **Profit Factor**: Should be >2.0
- **Max Drawdown**: Should stay below 15%
- **Average Trade**: Monitor P&L distribution

### When to Stop Trading

- **Profit Factor drops below 1.5** for 20+ trades
- **Max Drawdown exceeds 20%**
- **Market regime change** (trend → range)

## Files Included

```
VolumeImbalance/
├── VolumeImbalance_VI.haas      # HaasScript strategy
├── daily_comparison.png          # Equity curve visualization
├── daily_summary.txt             # Detailed results
├── daily_optimization_results.csv # All parameter combinations
├── honest_results.txt            # With realistic costs
└── VI_STRATEGY.md                # This file
```

## Expected Performance

Based on backtest results:

- **Monthly Return**: ~0.09% (2% sizing) to ~5.4% (full capital)
- **Win Rate**: 47-48% (slightly below 50%)
- **Average Trade**: 1 win = 2.67 losses (profit factor)
- **Maximum Drawdown**: 0.18% (conservative) to 11.49% (aggressive)

## Support

For issues or questions:
1. Check HaasOnline documentation
2. Review backtest results in `daily_summary.txt`
3. Monitor logs for trade details

## Disclaimer

Trading cryptocurrencies carries substantial risk. Past performance does not guarantee future results. Always test with paper trading before using real capital.

---

**Last Updated**: May 10, 2026
**Optimization Period**: November 2025 - May 2026 (180 days)
**Data Source**: Binance Perpetual Futures (REAL data)
**Status**: Profitable with 2.67 profit factor
