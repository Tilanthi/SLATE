# CLAUDE_TRADING_FULL.md - Complete Trading Rules and Research Findings

**Purpose:** Comprehensive trading rules, research findings, and critical constraints for SLATE system

---

## Critical Trading Rules (MUST FOLLOW)

### Data Rules
- ❌ **NO SYNTHETIC DATA** - Only use real market data from exchange APIs
- ❌ **NO SIMULATIONS** - No fake price patterns or generated data
- ✅ **Real Market Data Only** - Binance exchange data for all analysis

### Cost Rules (ALWAYS Apply)
- ✅ **Maker Fee**: 0.02% 
- ✅ **Taker Fee**: 0.05%
- ✅ **Slippage**: 10-20 basis points (0.10-0.20%)
- ✅ **Fill Rates**: 85-95% (not all orders fill)
- ⚠️ **BRUTAL REALITY**: These costs eliminate many false positive strategies

### Timeframe Rules
- ✅ **Daily+ timeframes**: 97.5% of all profitable strategies exist here
- ❌ **Sub-daily technical indicators**: NOT profitable on efficient exchanges
- ❌ **1m-1h timeframes**: 0% profitability (dominated by HFTs and market makers)
- ✅ **Focus**: Daily timeframe for discovery and analysis

### Mode Rules
- ❌ **NO REAL MONEY** - Paper trading only
- ✅ **Paper Trading Mode** - All operations in simulation
- ✅ **Safety-First Design** - All intelligence operations protect capital

---

## Key Research Findings (From 93,763 Strategy Analysis)

### Timeframe Analysis
- **Daily timeframes**: 97.5% of all profitable strategies
- **Sub-daily timeframes**: 0% profitability (1m-1h timeframes)
- **Conclusion**: Market efficiency dominates at shorter timeframes

### Trading Frequency Analysis
- **Profitable strategies**: Trade 23x less frequently than unprofitable ones
- **Typical profitable frequency**: ~15 trades/year (daily timeframe)
- **Unprofitable frequency**: ~350+ trades/year (overtrading)
- **Conclusion**: Less frequent trading = more sustainable edge

### Win Rate Analysis
- **Profitable strategies**: Average 51.0% win rate
- **Unprofitable strategies**: Average 39.7% win rate
- **Threshold**: Minimum 48% win rate for validation
- **Conclusion**: Win rate is key discriminator, but not sufficient alone

### Validation Effectiveness
- **Historical success rate**: 1.98% (1,859 profitable out of 93,763 total)
- **Current success rate**: 0% (market regime dependent)
- **System protection**: Validation correctly preventing deployment of unprofitable strategies
- **Conclusion**: Validation is working - protecting capital during unfavorable regimes

### Market Regime Sensitivity
- **Current discovery rate**: 2,478 strategies/hour (extremely high)
- **Current validation success**: 0% (all discoveries unprofitable)
- **Typical losses**: -15% to -16% returns on discovered strategies
- **Conclusion**: Edge types are regime-dependent - need regime-aware discovery

### Transaction Cost Impact
- **Without costs**: Many strategies appear profitable
- **With realistic costs**: Most strategies become unprofitable
- **Conclusion**: Realistic costs are essential for valid backtesting

---

## Critical System Behaviors

### Discovery System
- **Baseline rate**: 0.2 strategies/second (basic discovery)
- **Enhanced rate**: 0.8 strategies/second (4x speedup)
- **Current throughput**: 2,478 strategies/hour
- **Focus**: Daily timeframe exclusive (Phase 1 Quick Wins)

### Validation System
- **Minimum win rate**: 48%
- **Statistical validation**: Bootstrap confidence intervals
- **Historical baseline**: 1.98% success rate
- **Current status**: 0% (market regime protection)

### Trading Intelligence System
- **Autonomy level**: ~85% operational automation
- **Strategy deployment**: 2,244 strategies across 748 cycles
- **Current active**: 0 strategies (validation protection)
- **Technical success**: 100% (748 consecutive successful cycles)

---

## Performance Metrics

### Discovery Performance
- **Phase 1 baseline**: 0.2 strategies/second
- **Phase 1 enhanced**: 0.8 strategies/second (4x speedup)
- **Phase 1 mature**: 10-20 strategies/second (50-100x speedup projected)
- **BIODISC improvements**: 4-50x total speedup through parallelization

### Intelligence Performance
- **Selection engine**: 5-factor optimization (return, Sharpe, regime, correlation, trend)
- **Portfolio methods**: 6 allocation methods (Kelly, Risk Parity, CVaR, etc.)
- **Health monitoring**: Real-time bootstrap validation
- **Risk controls**: Portfolio VaR, drawdown circuit breakers, correlation limits

---

## Safety Mechanisms

### Risk Controls
- **Portfolio VaR**: 2% daily VaR limit
- **Drawdown limits**: 10% warning, 20% stop
- **Correlation limits**: Max 0.7 portfolio correlation
- **Concentration limits**: Max 30% single strategy, 50% single symbol

### Validation Protection
- **Minimum win rate**: 48% threshold
- **Statistical validation**: Bootstrap confidence intervals
- **Performance degradation**: Automatic detection
- **Capital protection**: 0 strategies deployed during validation crisis

---

## System Architecture Overview

### Autonomous Capability Layers

**Layer 1: Strategy Discovery** (Phase 1)
- Enhanced discovery with 4-50x speedup
- Daily timeframe exclusive focus
- Smart pre-filters and realistic costs

**Layer 2: Trading Intelligence** (Phase 2)
- Strategy selection and portfolio management
- Health monitoring and risk controls
- Lifecycle automation

**Layer 3: Autonomous Coordination**
- Reactive priority (user queries pause operations)
- Resource management (CPU/memory constraints)
- Market intelligence integration

---

*Last Updated: 2026-06-30*
*Based on analysis of 93,763 strategies with 1,859 profitable strategies*