# CLAUDE_ARCHITECTURE.md - System Architecture and Components

**Purpose:** Complete system architecture, file locations, and API endpoint documentation

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
- Reactive priority (user queries pause operations ONLY during execution)
- CONTINUOUS discovery (resumes immediately after request completion)
- Resource management (CPU/memory constraints)
- Market intelligence integration
- 24/7 operation with minimal interruption
- **REGIME-AWARE DISCOVERY:** Detects market transitions, filters incompatible strategies

---

## Phase 2 Intelligence Architecture Files

### Core Intelligence Components

**1. Strategy Selection Engine**
- **File:** `slate_core/intelligence/strategy_selector.py`
- **Purpose:** Multi-criteria optimization for strategy selection
- **Key Features:**
  - 5-factor scoring (return 30%, Sharpe 25%, regime 20%, correlation 15%, trend 10%)
  - Regime-aware filtering
  - Correlation-based diversification
  - Statistical validation with bootstrap

**2. Portfolio Manager**
- **File:** `slate_core/intelligence/portfolio_manager.py`
- **Purpose:** Multi-strategy portfolio coordination and allocation
- **Key Features:**
  - 6 allocation methods (Kelly, Risk Parity, Target Volatility, CVaR, Regime-Adaptive, Equal Weight)
  - Real-time portfolio performance tracking
  - Automatic rebalancing on regime changes
  - Multi-strategy correlation monitoring

**3. Health Monitor**
- **File:** `slate_core/intelligence/health_monitor.py`
- **Purpose:** Real-time strategy health monitoring
- **Key Features:**
  - Statistical validation with bootstrap analysis
  - Degradation detection
  - Early warning system
  - Multi-level health scoring (HEALTHY/DEGRADING/UNHEALTHY/CRITICAL)

**4. Risk Controller**
- **File:** `slate_core/intelligence/risk_controller.py`
- **Purpose:** Portfolio-level risk controls
- **Key Features:**
  - Portfolio VaR monitoring (2% daily VaR limit)
  - Drawdown circuit breakers (10% warning, 20% stop)
  - Correlation monitoring (max 0.7)
  - Concentration limits (30% single strategy, 50% single symbol)
  - Volatility scaling and stress testing

**5. Lifecycle Manager**
- **File:** `slate_core/intelligence/lifecycle_manager.py`
- **Purpose:** Strategy lifecycle automation
- **Key Features:**
  - Autonomous deployment with gradual rollout
  - Production management with health monitoring
  - Watchlist management for concerning strategies
  - Retirement decisions based on statistical significance
  - Automatic replacement strategy discovery

**6. Intelligence Orchestrator**
- **File:** `slate_core/intelligence/trading_intelligence_orchestrator.py`
- **Purpose:** Central coordination of intelligence components
- **Key Features:**
  - 60-second intelligence cycles
  - Reactive priority (user queries pause operations)
  - Resource management (CPU/memory constraints)
  - Error handling and recovery
  - Cycle reliability tracking

**7. Regime-Aware Discovery Manager** (NEW - Critical Architecture Fix)
- **File:** `slate_core/intelligence/regime_aware_discovery.py`
- **Purpose:** Prevents testing May-optimized strategies in July conditions
- **Key Features:**
  - Market regime transition detection
  - Strategy compatibility filtering by regime
  - Historical performance tracking by regime
  - Adaptive strategy guidance for current conditions
  - Prevents 2-month discovery crises through regime intelligence

---

## Regime-Aware Discovery Architecture (NEW)

### Core Innovation
**Problem Solved:** System was stuck testing May-optimized strategies for 2 months with 0% success because market conditions fundamentally changed.

**Solution:** Regime-aware discovery that detects market regime transitions and prevents testing strategies from incompatible market regimes.

### Key Components

**RegimeAwareDiscoveryManager:**
- **Purpose:** Central coordination of regime-aware discovery
- **Key Methods:**
  - `detect_regime_transition()` - Identifies fundamental market regime changes
  - `should_test_strategy()` - Prevents testing incompatible strategies
  - `record_strategy_performance()` - Tracks performance by regime
  - `get_adaptive_strategy_guidance()` - Provides regime-specific recommendations

**RegimeType Classification:**
```python
TRENDING_UP = "trending_up"
TRENDING_DOWN = "trending_down"
RANGE_BOUND = "range_bound"
HIGH_VOLATILITY = "high_volatility"
LOW_VOLATILITY = "low_volatility"
```

**RegimeTransition Detection:**
```python
TREND_TO_RANGE = "trend_to_range"           # Trend becomes range-bound
RANGE_TO_TREND = "range_to_trend"           # Range becomes trending
VOLATILITY_SPIKE = "volatility_spike"       # Sudden volatility increase
VOLATILITY_CRUSH = "volatility_crush"       # Sudden volatility decrease
FUNDAMENTAL_SHIFT = "fundamental_shift"     # Major market structure change
```

### Integration Points

**Swarm Integration Enhancement:**
- File: `slate_core/swarm/swarm_integration.py`
- Enhanced with `regime_aware_manager` integration
- New filtering: `_filter_strategies_by_regime()`
- New parameter adjustment: `_apply_regime_adjustments()`

**Key Statistics Added:**
```python
'strategies_skipped_regime_mismatch': 0,  # Tracks filtered strategies
'regime_aware_blocks': 0,                  # Tracks regime-based blocks
'regime_transitions': 2                      # Tracks regime changes
```

---

## Analytics and Validation Architecture

### Analytics Components

**Profitability Reporter**
- **File:** `slate_core/analytics/profitability_reporter.py`
- **Purpose:** Comprehensive profitability analysis and reporting
- **Key Features:**
  - Database growth tracking (119,416 total discoveries)
  - Discovery throughput monitoring (~2,500 strategies/hour)
  - Historical performance analysis by timeframe
  - Validation effectiveness tracking

---

## API Architecture

### Swarm Intelligence Endpoints

**1. Start Swarm Discovery**
- **Endpoint:** `POST /api/swarm/start`
- **Purpose:** Start regime-aware swarm discovery
- **Parameters:** `num_agents=63`
- **Returns:** 
  ```json
  {
    "status": "success",
    "cycle_results": {
      "regime_info": {
        "current_regime": "range_bound",
        "trend_direction": "sideways",
        "volatility_level": "low",
        "transition_detected": "fundamental_shift"
      }
    },
    "integration_stats": {
      "regime_transitions": 2,
      "strategies_skipped_regime_mismatch": 0
    }
  }
  ```

**2. Swarm Status**
- **Endpoint:** `GET /api/swarm/status`
- **Purpose:** Check swarm discovery status
- **Returns:** 
  ```json
  {
    "discovery_running": true,
    "integration_stats": {
      "swarm_cycles_completed": 3,
      "total_strategies_discovered": 189,
      "regime_transitions": 2
    }
  }
  ```

**3. Swarm Intelligence**
- **Endpoint:** `GET /api/swarm/intelligence`
- **Purpose:** Get collective intelligence and pheromone data
- **Returns:** Current regime, active pheromones, discovery hotspots

### Intelligence System Endpoints

**1. Intelligence Status**
- **Endpoint:** `GET /api/intelligence/status`
- **Purpose:** Check intelligence system status
- **Returns:** 
  - Intelligence cycle status
  - Strategy selector status
  - Portfolio manager status
  - Health monitor status
  - Risk controller status
  - Lifecycle manager status

**2. Components Status**
- **Endpoint:** `GET /api/intelligence/components`
- **Purpose:** Check availability of intelligence components
- **Returns:** Component availability and health status

**3. Toggle Intelligence**
- **Endpoint:** `POST /api/intelligence/toggle`
- **Purpose:** Enable/disable intelligence layer
- **Parameters:** `enabled=true/false`
- **Returns:** Confirmation of toggle operation

### Enhanced Discovery Endpoints

**1. Phase 1 Start**
- **Endpoint:** `POST /api/discovery/phase1/start`
- **Purpose:** Start Phase 1 enhanced discovery
- **Parameters:** `num_strategies=25`
- **Returns:** Discovery job status

**2. Phase 1 Stats**
- **Endpoint:** `GET /api/discovery/phase1/stats`
- **Purpose:** Phase 1 component statistics
- **Returns:** Phase 1 performance metrics

**3. Enhanced Start**
- **Endpoint:** `POST /api/discovery/enhanced/start`
- **Purpose:** Start full enhanced discovery
- **Parameters:** `num_strategies=100`
- **Returns:** Enhanced discovery job status

**4. Enhanced Stats**
- **Endpoint:** `GET /api/discovery/enhanced/stats`
- **Purpose:** Enhanced system statistics
- **Returns:** Enhanced discovery performance metrics

**5. Performance Comparison**
- **Endpoint:** `GET /api/discovery/performance`
- **Purpose:** Performance comparison between systems
- **Returns:** Baseline vs enhanced performance

### Basic System Endpoints

**1. Health Check**
- **Endpoint:** `GET /health`
- **Purpose:** Basic system health check
- **Returns:** System status and uptime

**2. Database Access**
- **File:** `sqlite3 slate_core/slate_realistic_discoveries.db`
- **Usage:** Direct database access for analysis

---

## Database Architecture

### Database File
- **Location:** `slate_core/slate_realistic_discoveries.db`
- **Type:** SQLite database
- **Scale:** 119,416 total discoveries, 1,859 profitable

### Database Contents
- **Total Discoveries:** 119,416 strategies
- **Profitable Strategies:** 1,859 strategies (1.56% success rate)
- **Timeframe Distribution:** 97.5% profitable strategies are daily timeframe
- **Recent Crisis:** 0 profitable strategies June-July (regime mismatch issue resolved)

---

## Server Architecture

### Server Configuration
- **Port:** 8788
- **Mode:** Paper trading only
- **Status:** Running with full trading intelligence active
- **Uptime:** Continuous operation with regime-aware discovery

### Server Components
- **Main Server:** `slate_core/server.py`
- **Enhanced Server:** `slate_core/server_enhanced.py`
- **Intelligence Orchestrator:** `slate_core/intelligence/trading_intelligence_orchestrator.py`
- **Autonomous Orchestrator:** `slate_core/autonomous/orchestrator.py`
- **Regime-Aware Manager:** `slate_core/intelligence/regime_aware_discovery.py` (NEW)
- **Swarm Integration:** `slate_core/swarm/swarm_integration.py` (Enhanced with regime awareness)

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SLATE ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: Autonomous Coordination                             │
│ - Reactive Priority System                                   │
│ - Resource Management (CPU/Memory)                          │
│ - Market Intelligence Integration                            │
│ - REGIME-AWARE DISCOVERY (NEW)                               │
│ - Market Regime Transition Detection                         │
│ - Strategy Compatibility Filtering                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: Trading Intelligence (Phase 2)                     │
│ - Strategy Selection Engine                                   │
│ - Portfolio Manager                                          │
│ - Health Monitor                                             │
│ - Risk Controller                                            │
│ - Lifecycle Manager                                          │
│ - Intelligence Orchestrator                                 │
│ - Regime-Aware Manager (NEW)                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: Strategy Discovery (Phase 1)                      │
│ - Enhanced Discovery Engine                                  │
│ - Daily Timeframe Focus                                      │
│ - Smart Pre-Filters                                          │
│ - Realistic Transaction Costs                               │
│ - Regime-Aware Filtering (NEW)                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ DATA LAYER                                                   │
│ - SQLite Database (119,416 strategies)                      │
│ - Binance Exchange Data                                      │
│ - Analytics Module                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Architecture Files

### Core Intelligence
- **Regime-Aware Manager:** `slate_core/intelligence/regime_aware_discovery.py` (NEW)
- **Strategy Selector:** `slate_core/intelligence/strategy_selector.py`
- **Portfolio Manager:** `slate_core/intelligence/portfolio_manager.py`
- **Health Monitor:** `slate_core/intelligence/health_monitor.py`
- **Risk Controller:** `slate_core/intelligence/risk_controller.py`
- **Lifecycle Manager:** `slate_core/intelligence/lifecycle_manager.py`

### Discovery System
- **Swarm Integration:** `slate_core/swarm/swarm_integration.py` (Enhanced)
- **Swarm Coordinator:** `slate_core/swarm/swarm_discovery.py`
- **Startup Coordinator:** `slate_core/startup_coordinator.py` (Continuous operation)
- **Enhanced Discovery:** `slate_core/discovery/enhanced_endpoints.py`

### Analytics
- **Profitability Reporter:** `slate_core/analytics/profitability_reporter.py`

### Server
- **Main Server:** `slate_core/server.py`
- **Intelligence Orchestrator:** `slate_core/intelligence/trading_intelligence_orchestrator.py`
- **Autonomous Orchestrator:** `slate_core/autonomous/orchestrator.py`

---

## Testing and Verification

### Regime-Aware Discovery Test
```bash
# Test regime-aware implementation
python test_regime_aware.py

# Expected output:
# ✅ REGIME-AWARE DISCOVERY TEST PASSED
# ✅ Regime-aware manager initialized
# ✅ Swarm integration with regime awareness operational
```

### Live System Verification
```bash
# Check regime-aware discovery status
curl -X POST "http://127.0.0.1:8788/api/swarm/start?num_agents=63" | jq '.integration_stats'

# Expected output:
# {
#   "regime_transitions": 2,              # 🎯 Detecting regime changes
#   "strategies_skipped_regime_mismatch": 0  # 🎯 Filtering active
# }
```

---

*Last Updated: 2026-07-01 (Regime-Aware Discovery Architecture)*  
*For detailed information on regime-aware discovery, see: REGIME_AWARE_FIX_SUMMARY.md*