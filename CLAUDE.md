# SLATE PROJECT CONTEXT - Quick Reference

**Current Identity:** Autonomous Perpetual Futures Trading System 🔄⚡

---

## 🎯 Critical Trading Architecture (UPDATED 2026-07-02)

### **Perpetual Futures Backtesting - 12 Month Specific**
- **Market**: SOLUSDT Perpetual Futures (Binance)
- **Position Types**: Long + Short (perpetual contracts enable both)
- **Backtest Period**: 12 months (full year - Nov 2025 to Jul 2026)
- **Data Source**: Real Binance futures data (downloaded & reused)
- **Brutally Honest Costs**:
  - Maker Fee: 0.02% | Taker Fee: 0.05%
  - Slippage: 15 bps base (volatility-adjusted up to 3x)
  - Fill Rate: 80% (worse than spot due to perps complexity)
  - Partial Fills: 20% probability
- **Funding Rates**: Applied every 8 hours (±0.02% realistic range)
- **Risk Management**: 3x max leverage, 3% max position size
- **Data Files**: `sol_data_cache/SOLUSDT_perpetual_1d_12m.csv` (241 days)

### **Key Differences from Spot Trading**
1. **Funding Costs**: Long/short positions pay/receive funding every 8 hours
2. **Higher Slippage**: 15 bps vs 10 bps for spot (perps more volatile)
3. **Worse Fills**: 80% vs 85% (perps less liquid than spot)
4. **Both Directions**: Can profit from shorts (spot only longs)
5. **Specific Period**: 6-month test vs arbitrary historical period

---

**GitHub Repository Target:** 
- **SLATE Repository**: https://github.com/Tilanthi/SLATE
- **Push Instructions**: When asked to push to GitHub from this SLATE project, **ALWAYS** push **ONLY** to the **main branch** of the SLATE repository at `https://github.com/Tilanthi/SLATE`
- **Do NOT** push to any other repositories (ASTRA, personal projects, etc.)
- **Do NOT** push to any other branches (always use main branch)
- **Current Directory**: `/Users/gjw255/astrodata/SWARM/SLATE/`

**Command Verification:**
```bash
# Always confirm you're in SLATE before pushing
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/
git remote -v  # Should show: https://github.com/Tilanthi/SLATE.git
git branch --show-current  # Should show: main
```

---

## 🎯 Regime-Aware Strategy System (UPDATED 2026-07-03)

### **Critical Enhancement: Regime-Specific Strategies**

**Problem Solved:** Previous system used trend-following strategies (EMA crossover) in ranging markets, resulting in 0.15% validation success despite 36,101+ strategies tested.

**Solution:** Implemented regime-aware strategy system with 6 specialized strategy types:

### **Available Strategy Types**

#### **1. Mean Reversion Strategies (For Sideways/Ranging Markets)**
- **Bollinger Band Mean Reversion**: Buy at lower band, sell at upper band
- **RSI Extremes**: Buy when RSI < 30 (oversold), sell when RSI > 70 (overbought)
- **Support/Resistance Trading**: Trade at key support/resistance levels

#### **2. Enhanced Trend Following (Range-Friendly)**
- **Enhanced EMA**: Faster EMAs (8/17) with range filters and volatility checks
- **Range Filter**: Avoids whipsaws in tight ranges
- **Multi-Timeframe Confirmation**: Reduces false signals

#### **3. Statistical Arbitrage (Market-Neutral)**
- **Z-Score Trading**: Buy/sell when price deviates statistically from mean
- **Volatility Breakout**: Trade volatility expansions after squeeze
- **Pairs Trading**: Exploit pricing inefficiencies

### **Regime Detection & Strategy Selection**

| Market Regime | Characteristics | Optimal Strategies |
|---------------|----------------|-------------------|
| **Sideways/Ranging** | -46% bear market, tight ranges | Mean reversion, S/R trading |
| **Trending** | Sustained directional moves | Enhanced EMA, breakout |
| **Volatile** | High volatility, spikes | Volatility breakout, stat arb |
| **Any** | Mixed conditions | Statistical arbitrage |

### **Strategy Performance**

**Before (EMA only in ranging market):**
- Signals: 10 crossovers in 175 days (1 every 17.5 days)
- Success rate: 0.15% (54/36,101 strategies)
- Problem: Wrong strategy type for market regime

**After (Regime-aware strategies):**
- Expected signals: 50-100+ signals in 175 days (mean reversion)
- Expected success rate: 1.5-3% (10-20x improvement)
- Solution: Right strategies for current regime

### **Implementation Files**
- **Strategy Library**: `slate_core/discovery/regime_aware_strategies.py`
- **Agent Mapping**: `slate_core/discovery/regime_aware_agent_mapping.py`
- **Integration**: Updated in `perpetual_discovery_integration.py` and `perpetual_swarm_bridge.py`

### **Agent Strategy Assignment**

- **Regime Detector (5 agents)**: Statistical arbitrage, regime-specific strategies
- **Pattern Discoverer (10 agents)**: Bollinger mean reversion, S/R trading
- **Parameter Explorer (30 agents)**: Enhanced EMA, volatility breakout
- **Cross-Timeframe Analyst (8 agents)**: S/R trading, statistical arbitrage
- **Experimental Strategist (10 agents)**: All regime-aware strategies

**Key Insight:** System now automatically uses appropriate strategies for current market regime, eliminating the regime-strategy mismatch that caused the discovery crisis.

---

## 🚀 Quick Commands

### System Operations
- **Start SLATE**: `python -m slate_core.server`
- **Check Status**: `curl http://127.0.0.1:8788/health`
- **Database Access**: `sqlite3 slate_core/slate_realistic_discoveries.db`

### Intelligence System
- **Intelligence Status**: `curl http://127.0.0.1:8788/api/intelligence/status | jq '.'`
- **Components Status**: `curl http://127.0.0.1:8788/api/intelligence/components | jq '.'`
- **Toggle Intelligence**: `curl -X POST "http://127.0.0.1:8788/api/intelligence/toggle?enabled=true"`

### Discovery Operations
- **Swarm Discovery**: `curl -X POST "http://127.0.0.1:8788/api/swarm/start?num_agents=63"`
- **Swarm Status**: `curl http://127.0.0.1:8788/api/swarm/status | jq '.'`
- **Swarm Intelligence**: `curl http://127.0.0.1:8788/api/swarm/intelligence | jq '.'`
- **Stop Swarm**: `curl -X POST "http://127.0.0.1:8788/api/swarm/stop"`
- **Phase 1 Discovery**: `curl -X POST "http://127.0.0.1:8788/api/discovery/phase1/start?num_strategies=25"`
- **Enhanced Discovery**: `curl -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=100"`
- **Enhanced Stats**: `curl http://127.0.0.1:8788/api/discovery/enhanced/stats | jq '.'`

### Perpetual Futures Backtesting (UPDATED 2026-07-02)
- **Market**: SOLUSDT Perpetual Futures (Binance)
- **Backtest Period**: 12 months (full year, specific period)
- **Data Source**: Real Binance futures data (downloaded once, reused)
- **Position Types**: Long and Short (perpetual contracts enable both)
- **Transaction Costs**: Brutally realistic
  - Maker Fee: 0.02% | Taker Fee: 0.05%
  - Slippage: 15 bps (volatility-adjusted)
  - Fill Rate: 80% (worse than spot)
  - Partial Fills: 20% probability
- **Funding Rates**: Applied every 8 hours (±0.02% range)
- **Risk Management**: 3x max leverage, 3% max position size
- **Data Files**: `sol_data_cache/SOLUSDT_perpetual_1d_12m.csv`

---

## 📚 Modular Documentation (Specialized Files)

### Core Documentation
- **[CLAUDE_TRADING_FULL.md](CLAUDE_TRADING_FULL.md)** - Complete trading rules, research findings, critical constraints
- **[CLAUDE_PHASE2_INTELLIGENCE.md](CLAUDE_PHASE2_INTELLIGENCE.md)** - Trading Intelligence Layer details (5 core components)
- **[CLAUDE_ANALYTICS.md](CLAUDE_ANALYTICS.md)** - Performance metrics, analytics capabilities, data analysis findings
- **[CLAUDE_ARCHITECTURE.md](CLAUDE_ARCHITECTURE.md)** - System architecture, file locations, API endpoints
- **[CLAUDE_OPERATIONAL_STATUS.md](CLAUDE_OPERATIONAL_STATUS.md)** - Current live operational status and system state
- **[CLAUDE_COMMANDS.md](CLAUDE_COMMANDS.md)** - Complete command reference for all operations

---

## 🔴 Current Operational Status (UPDATED 2026-07-03)

**System Status:** 🟢 **REGIME-AWARE PERPETUAL FUTURES DISCOVERY - FULLY OPERATIONAL**

**Quick Summary:**
- **Swarm Discovery:** ✅ ACTIVE (63 agents, 24/7 operation)
- **Market:** SOLUSDT Perpetual Futures (Binance)
- **Backtest Period:** 12 months (Nov 2025 - Jul 2026)
- **Position Types:** Long + Short (perpetual contracts)
- **Funding Rates:** ✅ Applied every 8 hours
- **Transaction Costs:** ✅ Brutally realistic (fees, slippage, fill rates)
- **Database:** ✅ FULLY OPERATIONAL (79+ strategies saved, swarm integration working)
- **Discovery Architecture:** 12-month specific perpetual futures backtesting
- **Recent Fixes:** Database persistence fixed (2026-07-03), swarm deployment automation improved

**Current Solution:**
- **Regime-Aware Discovery:** Prevents testing May-optimized strategies in July conditions (FIXES 2-month crisis)
- **Swarm Intelligence:** Multi-agent collective discovery for current market regime
- **Regime Detection:** Sophisticated market regime transition detection and filtering
- **Pattern Discovery:** 10 agents exploring diverse pattern categories
- **Parameter Exploration:** 30 agents optimizing strategy parameters
- **Cross-Timeframe Analysis:** 8 agents analyzing multi-timeframe correlations
- **Experimental Strategies:** 10 agents testing novel combinations

*For detailed live status, see: [CLAUDE_OPERATIONAL_STATUS.md](CLAUDE_OPERATIONAL_STATUS.md)*

---

## 🔄 Auto-Restart Mechanism (UPDATED 2026-07-04)

### **Problem Solved: Discovery Pipeline Stopping**
**Issue:** Discovery pipeline would stop unexpectedly due to unhandled errors or task completion, requiring manual restart.

**Solution:** Implemented comprehensive auto-restart mechanism with multiple layers of protection:

### **Auto-Restart Features**
- **Watchdog Monitoring:** Background task checks discovery health every 30-60 seconds
- **Error Recovery:** Exponential backoff on consecutive errors (max 60s wait)
- **State Synchronization:** Maintains global `discovery_running` flag across health endpoints
- **Smart Restart:** Only restarts when appropriate (not during user tasks)
- **Consecutive Error Detection:** Pauses briefly after 5 consecutive errors, then retries

### **Implementation Components**
1. **Startup Coordinator Enhancements** (`startup_coordinator.py`):
   - Enhanced `_discovery_loop()` with error counting and recovery
   - Added `watchdog_check_discovery()` for continuous monitoring
   - Global state synchronization with server endpoints

2. **Server Integration** (`server.py`):
   - Added `periodic_discovery_health_check()` for server-level monitoring
   - Integrated watchdog startup in server initialization
   - Health endpoint improvements for accurate status reporting

### **Auto-Restart Behavior**
- **Normal Operation:** Discovery runs continuously, checked every 60 seconds
- **Error Handling:** Up to 5 consecutive errors trigger 30s wait, then retry
- **Crash Recovery:** Automatic detection and restart of stopped discovery tasks
- **User Task Awareness:** Won't interrupt during active user requests
- **Status Accuracy:** Health endpoints reflect true discovery state

### **Monitoring & Verification**
```bash
# Check discovery status
curl http://127.0.0.1:8788/health | jq '.discovery_running'

# Check coordinator status
curl http://127.0.0.1:8788/health | jq '.startup_coordinator.discovery_running'

# Verify swarm status
curl http://127.0.0.1:8788/api/swarm/status | jq '.initialized'
```

---

## 🎯 Critical Constraints

### Data & Mode Rules
- ❌ **NO SYNTHETIC DATA** - Only real market data from Binance
- ❌ **NO SIMULATIONS** - No fake price patterns
- ❌ **NO REAL MONEY** - Paper trading only
- ✅ **Brutal Transaction Costs** - Maker 0.02%, Taker 0.05%, 10-20 bps slippage
- ✅ **Daily Timeframe Exclusive** - 97.5% of profitable strategies exist here
- ✅ **Safety-First Design** - All intelligence operations in paper trading mode

*For complete trading rules and research findings, see: [CLAUDE_TRADING_FULL.md](CLAUDE_TRADING_FULL.md)*

---

## 🚀 System Overview

### Current Identity
**"Adaptive Perpetual Futures Discovery System with Profit-Driven Learning"** 🧠💰⚡
- **Autonomy Level:** ~99. operational automation with adaptive learning
- **Discovery Method:** CONTINUOUS swarm intelligence (63 specialized agents, 24/7)
- **Market Focus:** Perpetual futures (12-month backtest, SOLUSDT)
- **Database Persistence:** ✅ FULLY OPERATIONAL (auto-saves all backtests)
- **Learning System:** 🆕 PROFIT-DRIVEN (guides agents toward profitable parameter spaces)
- **Recent Improvements:** Fixed database persistence, implemented adaptive learning from backtest results
- **Server:** Running on port 8788 with full trading intelligence active
- **Portfolio:** $10,000 paper trading capital, Kelly Criterion allocation
- **Database:** 79+ perpetual futures strategies (2026-07-03), continuous accumulation

### Phase 3 Transformation: Swarm Intelligence
**Before (Phase 2):** Autonomous testing of historical edge types
**After (Phase 3):** Swarm discovery of regime-specific strategies

**Swarm Components:**
- **Regime Detection Agents** (5): Analyze current market conditions
- **Pattern Discovery Agents** (10): Explore diverse strategy patterns
- **Parameter Space Explorers** (30): Optimize strategy parameters
- **Cross-Timeframe Analysts** (8): Analyze multi-timeframe correlations
- **Experimental Strategists** (10): Test novel strategy combinations

**Stigmergic Communication:**
- **Discovery Pheromones**: Guide agents toward promising areas
- **Avoidance Pheromones**: Warn away from unprofitable parameters
- **Regime Pheromones**: Share market regime intelligence
- **Innovation Pheromones**: Encourage creative exploration

### Phase 2 Transformation
**Before:** Manual strategy selection and deployment
**After:** Autonomous strategy discovery, selection, deployment, and portfolio management

### 5 Core Intelligence Components
1. **Strategy Selection Engine** 🎯 - Multi-criteria optimization
2. **Portfolio Manager** 💼 - 6 allocation methods (Kelly, Risk Parity, CVaR, etc.)
3. **Strategy Health Monitor** 🏥 - Statistical degradation detection
4. **Real-Time Risk Controller** 🛡️ - Portfolio-level circuit breakers
5. **Strategy Lifecycle Manager** 🔄 - Autonomous deployment and retirement

### Continuous Discovery Architecture ⚡
- **Operation Mode:** 24/7 continuous regime-aware swarm discovery (63 specialized agents)
- **Regime Intelligence:** Detects market regime transitions, filters incompatible strategies
- **Pause Behavior:** ONLY pauses during active user request execution
- **Resume Behavior:** Resumes IMMEDIATELY after request completion
- **No Waiting Period:** Runs continuously when no user tasks active
- **Auto-Restart Mechanism:** 🆕 **Automatically restarts if discovery stops (watchdog monitoring every 30-60 seconds)**
- **Error Recovery:** 🆕 **Exponential backoff on consecutive errors, maximum 60s wait time**
- **Global State Sync:** 🆕 **Maintains discovery_running flag across server health endpoints**
- **Startup Coordinator:** `slate_core/startup_coordinator.py` (manages continuous operation)
- **Regime-Aware Manager:** `slate_core/intelligence/regime_aware_discovery.py` (prevents regime mismatch)
- **Server Integration:** `slate_core/server.py` (periodic health checks and auto-restart)

*For complete Phase 2 details, see: [CLAUDE_PHASE2_INTELLIGENCE.md](CLAUDE_PHASE2_INTELLIGENCE.md)*

---

## 📊 Key Performance Metrics

### Discovery Performance
- **Current Throughput:** 2,478 strategies/hour
- **Enhanced Speedup:** 4x faster than baseline (0.8 vs 0.2 strategies/second)
- **Database Growth:** 93,763 total discoveries (up from 28,401 baseline)
- **Timeframe Focus:** Daily timeframe exclusive (97.5% of profitable strategies)

### Intelligence Performance
- **Autonomous Selection:** 2,244 strategies deployed across 748 cycles
- **Technical Success:** 100% (748 consecutive successful cycles, 0 errors)
- **Current Active:** 0 strategies (validation protecting capital during unfavorable regime)
- **Cycle Reliability:** 100% success rate, 0 errors

### Key Research Findings
- **Timeframe Dominance:** Daily timeframes represent 97.5% of profitable strategies
- **Sub-Daily Failure:** 0% profitability (1m-1h timeframes dominated by HFTs)
- **Trading Frequency:** Profitable strategies trade 23x less frequently
- **Win Rates:** Profitable 51.0% vs Unprofitable 39.7%
- **Validation Effectiveness:** 1.98% historical success rate protecting capital

*For complete analytics and findings, see: [CLAUDE_ANALYTICS.md](CLAUDE_ANALYTICS.md)*

---

## 🏗️ System Architecture

### Autonomous Capability Layers
**Layer 1: Strategy Discovery** (Phase 1)
- CONTINUOUS swarm discovery (63 specialized agents, 24/7 operation)
- Enhanced discovery with 4-50x speedup
- Daily timeframe exclusive focus
- Smart pre-filters and realistic costs
- Minimal interruption (only pauses during active user requests)

**Layer 2: Trading Intelligence** (Phase 2)
- Strategy selection and portfolio management
- Health monitoring and risk controls
- Lifecycle automation

**Layer 3: Autonomous Coordination**
- Reactive priority (user queries pause operations ONLY during execution)
- CONTINUOUS discovery resumption (immediate resume after request completion)
- Resource management (CPU/memory constraints)
- Market intelligence integration
- 24/7 autonomous operation

### Key Architecture Files
- **Startup Coordinator:** `slate_core/startup_coordinator.py` (continuous discovery orchestration)
- **Regime-Aware Manager:** `slate_core/intelligence/regime_aware_discovery.py` (regime transition detection)
- **Intelligence Components:** `slate_core/intelligence/*.py` (5 core components)
- **Swarm Integration:** `slate_core/swarm/swarm_integration.py` (63-agent regime-aware discovery)
- **Analytics:** `slate_core/analytics/profitability_reporter.py`
- **Discovery:** `slate_core/discovery/enhanced_endpoints.py`
- **Server:** `slate_core/server.py` with intelligence API endpoints

*For complete architecture details, see: [CLAUDE_ARCHITECTURE.md](CLAUDE_ARCHITECTURE.md)*

---

## 🔍 Quick Status Checks

### System Health
```bash
# Overall system health
curl http://127.0.0.1:8788/health

# Intelligence system status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.'

# Component availability
curl http://127.0.0.1:8788/api/intelligence/components | jq '.'
```

### Database Status
```bash
# Total discoveries
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM discoveries;"

# Profitable strategies
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM discoveries WHERE total_return > 0;"
```

### GitHub Verification
```bash
# Confirm SLATE directory
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/

# Verify git remote
git remote -v  # Should show: https://github.com/Tilanthi/SLATE.git
```

---

## 🎯 Usage Guidelines

### When Working with SLATE
1. **Always verify directory** before any operations (`pwd`)
2. **Check git remote** before pushing (`git remote -v`)
3. **Use modular documentation** - read specialized .md files for detailed information
4. **Monitor operational status** - system protection may limit deployments during unfavorable regimes
5. **Follow trading constraints** - NO synthetic data, NO real money, realistic costs only

### Reading Specialized Documentation
- **For trading rules and research:** Read `CLAUDE_TRADING_FULL.md`
- **For Phase 2 intelligence details:** Read `CLAUDE_PHASE2_INTELLIGENCE.md`
- **For performance analytics:** Read `CLAUDE_ANALYTICS.md`
- **For system architecture:** Read `CLAUDE_ARCHITECTURE.md`
- **For current live status:** Read `CLAUDE_OPERATIONAL_STATUS.md`
- **For complete command reference:** Read `CLAUDE_COMMANDS.md`

---

## 📈 Expected Outcomes

### Operational Transformation
- **Before:** SLATE discovers strategies but requires manual selection and deployment
- **After:** SLATE autonomously discovers, selects, deploys, and manages strategy portfolios

### Performance Improvements
- **Strategy Selection:** Mathematical optimization replacing manual selection
- **Portfolio Performance:** Multi-strategy diversification improving risk-adjusted returns
- **Risk Management:** Real-time monitoring preventing catastrophic losses
- **Adaptability:** Automatic strategy replacement as market conditions change

### System Evolution
- **Current Identity:** "Autonomous Regime-Aware Continuous-Discovery Trading System" 🧠⚡🔄
- **Autonomy Level:** ~99% operational automation (regime-aware discovery, intelligent filtering)
- **Decision Making:** Multi-objective optimization with statistical validation + regime compatibility
- **Portfolio Management:** 6 allocation methods with risk controls
- **Lifecycle Automation:** Deployment → Monitoring → Retirement → Replacement
- **Discovery Architecture:** 24/7 regime-aware operation with intelligent pause/resume
- **Regime Intelligence:** Prevents testing May-optimized strategies in July conditions

---

*Last Updated: 2026-07-01 (Regime-Aware Discovery Architecture)*  
*This file is automatically read when working in the SLATE directory*  
*For detailed information, refer to specialized documentation files listed above*