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
- Reactive priority (user queries pause operations)
- Resource management (CPU/memory constraints)
- Market intelligence integration

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

---

## Analytics and Validation Architecture

### Analytics Components

**Profitability Reporter**
- **File:** `slate_core/analytics/profitability_reporter.py`
- **Purpose:** Comprehensive profitability analysis and reporting
- **Key Features:**
  - Database growth tracking (93,763 total discoveries)
  - Discovery throughput monitoring (2,478 strategies/hour)
  - Validation analysis (success rates, win rates)
  - Market regime detection
  - Performance baseline calculation

**Enhanced Discovery Endpoints**
- **File:** `slate_core/discovery/enhanced_endpoints.py`
- **Purpose:** Enhanced discovery API endpoints with advanced filtering
- **Key Features:**
  - Phase 1 enhanced discovery
  - Advanced filtering capabilities
  - Performance comparison endpoints
  - Real-time statistics

**Enhanced Server**
- **File:** `slate_core/server_enhanced.py`
- **Purpose:** Enhanced server with monitoring capabilities
- **Key Features:**
  - Real-time monitoring
  - Enhanced validation features
  - Performance tracking
  - Health check endpoints

**Strategy Validator**
- **File:** `slate_core/autonomous/strategy_validator.py`
- **Purpose:** Updated validation with data-driven thresholds
- **Key Features:**
  - Minimum win rate thresholds (48%)
  - Statistical validation with bootstrap
  - Performance degradation detection
  - Data-driven thresholds from 93,763 strategy analysis

---

## Integration Architecture

### Core Integration Files

**Autonomous Orchestrator**
- **File:** `slate_core/autonomous/orchestrator.py`
- **Purpose:** Updated with intelligence integration
- **Key Features:**
  - Intelligence layer integration
  - Reactive priority system
  - Resource management
  - Error handling and recovery

**Main Server**
- **File:** `slate_core/server.py`
- **Purpose:** Main server with intelligence API endpoints
- **Key Features:**
  - 3 new intelligence API endpoints
  - Existing discovery endpoints
  - Health check endpoints
  - Status monitoring

---

## API Endpoints Architecture

### Trading Intelligence Endpoints

**1. Intelligence Status**
- **Endpoint:** `GET /api/intelligence/status`
- **Purpose:** Comprehensive intelligence system status
- **Returns:**
  - Orchestrator status
  - Component availability
  - Cycle statistics
  - Portfolio status
  - Health monitoring status
  - Risk control status

**2. Components Status**
- **Endpoint:** `GET /api/intelligence/components`
- **Purpose:** Component availability status
- **Returns:**
  - Strategy selector status
  - Portfolio manager status
  - Health monitor status
  - Risk controller status
  - Lifecycle manager status

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
- **Purpose:** Direct database access
- **Usage:** `sqlite3 slate_core/slate_realistic_discoveries.db`

---

## Database Architecture

### Database File
- **Location:** `slate_core/slate_realistic_discoveries.db`
- **Type:** SQLite database
- **Scale:** 93,763 total discoveries, 1,859 profitable

### Database Contents
- **Total Discoveries:** 93,763 strategies
- **Profitable Strategies:** 1,859 strategies (1.98% success rate)
- **Unprofitable Strategies:** 91,904 strategies
- **Growth Rate:** ~65,000+ strategies from baseline

---

## Server Architecture

### Server Configuration
- **Port:** 8788
- **Mode:** Paper trading only
- **Status:** Running with full trading intelligence active
- **Uptime:** ~22 hours continuous operation

### Server Components
- **Main Server:** `slate_core/server.py`
- **Enhanced Server:** `slate_core/server_enhanced.py`
- **Intelligence Orchestrator:** `slate_core/intelligence/trading_intelligence_orchestrator.py`
- **Autonomous Orchestrator:** `slate_core/autonomous/orchestrator.py`

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
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: Strategy Discovery (Phase 1)                      │
│ - Enhanced Discovery Engine                                  │
│ - Daily Timeframe Focus                                      │
│ - Smart Pre-Filters                                          │
│ - Realistic Transaction Costs                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ DATA LAYER                                                   │
│ - SQLite Database (93,763 strategies)                       │
│ - Binance Exchange Data                                     │
│ - Analytics Module                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure Overview

```
slate_core/
├── intelligence/
│   ├── strategy_selector.py
│   ├── portfolio_manager.py
│   ├── health_monitor.py
│   ├── risk_controller.py
│   ├── lifecycle_manager.py
│   └── trading_intelligence_orchestrator.py
├── analytics/
│   └── profitability_reporter.py
├── discovery/
│   └── enhanced_endpoints.py
├── autonomous/
│   ├── orchestrator.py
│   └── strategy_validator.py
├── server.py
├── server_enhanced.py
└── slate_realistic_discoveries.db
```

---

## API Usage Examples

### Check System Status
```bash
curl http://127.0.0.1:8788/health
```

### Check Intelligence Status
```bash
curl http://127.0.0.1:8788/api/intelligence/status | jq '.'
```

### Check Component Status
```bash
curl http://127.0.0.1:8788/api/intelligence/components | jq '.'
```

### Start Enhanced Discovery
```bash
curl -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=100"
```

### Get Enhanced Stats
```bash
curl http://127.0.0.1:8788/api/discovery/enhanced/stats | jq '.'
```

### Performance Comparison
```bash
curl http://127.0.0.1:8788/api/discovery/performance | jq '.'
```

---

## Integration Points

### Intelligence Layer Integration
- **Autonomous Orchestrator:** Coordinates with intelligence layer
- **Main Server:** Provides API endpoints for intelligence control
- **Strategy Validator:** Works with intelligence for validation

### Analytics Integration
- **Profitability Reporter:** Provides data-driven thresholds
- **Enhanced Endpoints:** Advanced filtering and monitoring
- **Health Monitor:** Real-time performance validation

### Discovery Integration
- **Enhanced Discovery:** Feeds strategies to intelligence layer
- **Phase 1 Quick Wins:** Daily timeframe exclusive focus
- **Smart Pre-Filters:** Eliminate unprofitable strategies early

---

*Last Updated: 2026-06-30*
*Complete system architecture for SLATE Autonomous Quantitative Trading System*