# SLATE HaasScript Strategies

Mean reversion and other trading strategies for HaasScript v2.0.

## Mean Reversion Strategy (BTCUSDT Binance Futures)

### Strategy Overview
- **Type**: Mean Reversion
- **Market**: BTCUSDT Perpetual Futures (Binance)
- **Timeframe**: 1 Hour (recommended)
- **Indicators**: Bollinger Bands (20, 2.0), RSI (14)

### Entry Logic

**Long Entry**:
- Price closes below Bollinger Lower Band
- RSI < 30 (oversold)
- Only enter when no position exists

**Short Entry**:
- Price closes above Bollinger Upper Band
- RSI > 70 (overbought)
- Only enter when no position exists

### Exit Logic

**Exit Long**:
- Price crosses back above BB Middle OR
- RSI becomes overbought (> 70)

**Exit Short**:
- Price crosses back below BB Middle OR
- RSI becomes oversold (< 30)

### Risk Management

- **Risk Per Trade**: 2% of account balance
- **Stop Loss**: 3%
- **Take Profit**: 6% (2:1 reward:risk ratio)

### HaasScript Notes

⚠️ **CRITICAL**: HaasScript uses **1-based array indexing**:
- `IndexArray(array, 1)` gets the **first (most recent)** element
- `IndexArray(array, 2)` gets the **second** element
- This is different from Python's 0-based indexing!

### Usage

1. Copy the strategy code to HaasOnline Trade Server
2. Configure for Binance Futures (paper trading mode first!)
3. Set timeframe to 1 Hour
4. Backtest thoroughly before any real use
5. Start with minimum position sizes

### Paper Trading Only

⚠️ **WARNING**: This strategy is for paper trading and simulation only.
Never execute live trades without:
- Extensive backtesting
- Forward testing on paper trading
- Understanding the risks
- Having proper risk management in place

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| BB Period | 20 | Bollinger Bands period |
| BB Std Dev | 2.0 | Standard deviation multiplier |
| RSI Period | 14 | RSI calculation period |
| RSI Oversold | 30 | RSI oversold threshold |
| RSI Overbought | 70 | RSI overbought threshold |
| Risk Per Trade | 2.0% | Percentage of balance to risk |
| Stop Loss | 3.0% | Stop loss percentage |
| Take Profit | 6.0% | Take profit percentage |

### License

MIT License - Use at your own risk
