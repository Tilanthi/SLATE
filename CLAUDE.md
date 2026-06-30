# SLATE PROJECT CONTEXT - Quick Reference

**Current Identity:** Autonomous Quantitative Trading System 🧠

---

## 🎯 Critical Instructions

**GitHub Repository Target:** 
- **SLATE Repository**: https://github.com/Tilanthi/SLATE
- **Push Instructions**: When asked to push to GitHub from this SLATE project, **ALWAYS** push **ONLY** to the SLATE repository at `https://github.com/Tilanthi/SLATE`
- **Do NOT** push to any other repositories (ASTRA, personal projects, etc.)
- **Current Directory**: `/Users/gjw255/astrodata/SWARM/SLATE/`

**Command Verification:**
```bash
# Always confirm you're in SLATE before pushing
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/
git remote -v  # Should show: https://github.com/Tilanthi/SLATE.git
```

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
- **Phase 1 Discovery**: `curl -X POST "http://127.0.0.1:8788/api/discovery/phase1/start?num_strategies=25"`
- **Enhanced Discovery**: `curl -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=100"`
- **Enhanced Stats**: `curl http://127.0.0.1:8788/api/discovery/enhanced/stats | jq '.'`

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

## 🔴 Current Operational Status

**System Status:** 🟡 **DISCOVERY CRISIS**

**Quick Summary:**
- **Trading Intelligence:** ✅ ACTIVE (748 cycles, 2,244 strategies deployed historically)
- **Autonomous Discovery:** ✅ RUNNING (2,478 strategies/hour throughput)
- **Portfolio Management:** ⚠️ IDLE (0 strategies currently passing validation)
- **Risk Monitoring:** ✅ ACTIVE (0 risk alerts, all systems normal)
- **Health Monitoring:** ✅ ACTIVE (validation working correctly)

**Current Challenge:**
- **Discovery Rate:** 2,478 strategies/hour (extremely high)
- **Validation Success:** 0% (all recent discoveries unprofitable)
- **Market Regime:** Current conditions unfavorable for current edge types
- **System Protection:** Validation correctly preventing deployment (capital protected)

*For detailed live status, see: [CLAUDE_OPERATIONAL_STATUS.md](CLAUDE_OPERATIONAL_STATUS.md)*

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
**"Autonomous Quantitative Trading System"** 🧠
- **Autonomy Level:** ~85% operational automation (up from ~40%)
- **Server:** Running on port 8788 with full trading intelligence active
- **Portfolio:** $10,000 paper trading capital, Kelly Criterion allocation
- **Database:** 93,763 total discoveries, 1,859 profitable (1.98% baseline)

### Phase 2 Transformation
**Before:** Manual strategy selection and deployment
**After:** Autonomous strategy discovery, selection, deployment, and portfolio management

### 5 Core Intelligence Components
1. **Strategy Selection Engine** 🎯 - Multi-criteria optimization
2. **Portfolio Manager** 💼 - 6 allocation methods (Kelly, Risk Parity, CVaR, etc.)
3. **Strategy Health Monitor** 🏥 - Statistical degradation detection
4. **Real-Time Risk Controller** 🛡️ - Portfolio-level circuit breakers
5. **Strategy Lifecycle Manager** 🔄 - Autonomous deployment and retirement

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

### Key Architecture Files
- **Intelligence Components:** `slate_core/intelligence/*.py` (5 core components)
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
- **Current Identity:** "Autonomous Quantitative Trading System" 🧠
- **Autonomy Level:** ~85% operational automation (up from ~40%)
- **Decision Making:** Multi-objective optimization with statistical validation
- **Portfolio Management:** 6 allocation methods with risk controls
- **Lifecycle Automation:** Deployment → Monitoring → Retirement → Replacement

---

*Last Updated: 2026-06-30*  
*This file is automatically read when working in the SLATE directory*  
*For detailed information, refer to specialized documentation files listed above*