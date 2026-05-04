# SLATE Project Rules - CRITICAL

## 🚫 ABSOLUTE PROHIBITION ON SYNTHETIC DATA

**YOU ARE ABSOLUTELY FORBIDDEN FROM USING ANY SYNTHETIC, SIMULATED, OR ARTIFICIALLY GENERATED DATA.**

**This prohibition applies to:**
- ❌ Price data generation
- ❌ Market simulation with fake price patterns  
- ❌ Artificial regime-switching simulations
- ❌ Synthetic market conditions
- ❌ Any fabricated trading data whatsoever

**You MUST ONLY use:**
- ✅ REAL market data from exchange APIs (Binance, etc.)
- ✅ ACTUAL historical price data
- ✅ GENUINE market conditions

**When backtesting or analyzing trading strategies, you MUST ALWAYS apply:**
- ✅ Brutally honest transaction fees (maker 0.02%, taker 0.05%)
- ✅ Realistic slippage (10-20 bps depending on volatility)
- ✅ Actual fill rates (85-95%, not 100%)
- ✅ Partial fills (15% probability)
- ✅ Real market impact

**NO EXCEPTIONS. NO SIMULATIONS. NO FAKE DATA.**
**VIOLATION OF THIS RULE IS GROUNDS FOR IMMEDIATE TERMINATION.**

---

## Project: SLATE - Strategy Learning & Autonomous Trading Engine

**Location**: `/Users/gjw255/astrodata/SWARM/SLATE`

**What it is**: AI-driven autonomous trading strategy discovery system for cryptocurrency markets using ONLY real market data.

**Critical Principle**: SLATE discovers genuine market edges through brutally realistic backtesting with actual market data, never synthetic simulations.

**Quick Start**:
```bash
cd /Users/gjw255/astrodata/SWARM/SLATE
python -m slate_core.server
```

**Dashboard**: http://127.0.0.1:8788

---

## Data Sources (Real Only)

- **Primary**: Binance API for SOLUSDT futures
- **Cache**: `sol_data_cache/SOLUSDT_1h_1y.csv` (real market data only)
- **NO synthetic data sources permitted**

---

## Backtesting Parameters (Always Apply These)

```python
# Transaction costs (realistic, never optimistic)
maker_fee: 0.0002      # 0.02% - actual Binance maker fee
taker_fee: 0.0005      # 0.05% - actual Binance taker fee  
base_slippage_bps: 10   # 10 bps - realistic slippage
volatility_adjusted_slippage: True

# Fill realism (not 100% - real market friction)
base_fill_rate: 0.85    # 85% fill rate - realistic
partial_fill_probability: 0.15  # 15% partial fills
partial_fill_min_size: 0.3      # 30% minimum fill

# Risk management (conservative, never aggressive)
max_position_size: 0.05  # 5% max per position
max_portfolio_heat: 0.15  # 15% total exposure
stop_loss_atr_multiple: 2.0
take_profit_atr_multiple: 3.0
```

---

## Verification Commands

**Always verify data is real:**
```bash
# Check data source
head -5 sol_data_cache/SOLUSDT_1h_1y.csv

# Verify realistic ranges
python -c "import pandas as pd; df = pd.read_csv('sol_data_cache/SOLUSDT_1h_1y.csv'); print(f'Real price range: ${df[\"close\"].min():.2f} - ${df[\"close\"].max():.2f}')"
```

---

## Database Reset Protocol

If synthetic data is ever used or discovered:
```bash
# Stop server
pkill -f slate_core.server

# Clear all discoveries
rm -f slate_core/slate_realistic_discoveries.db

# Clear knowledge graph  
rm -f slate_core/palace_data/discoveries/*.json

# Clear reflection memory
rm -f ~/.slate/memory/discovery_memory.md

# Restart fresh
python -m slate_core.server
```

---

**Remember**: SLATE's value proposition is discovering GENUINE market edges using REAL data. Synthetic data defeats the entire purpose and produces misleading results. ALWAYS use real market data with realistic transaction costs.
