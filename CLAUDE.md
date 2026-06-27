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

**Architecture Overview**:
- **Automatic Discovery**: SLATE ALWAYS starts with automatic discovery enabled
- **Continuous Operation**: Discovery runs continuously unless user requests specific tasks
- **Smart Pause/Resume**: User activity automatically pauses discovery; resumes after 5 minutes idle
- **Startup Coordinator**: Ensures discovery starts immediately on server startup
- **Autonomous System**: Advanced AI for self-directed market exploration
- **Paper Trading Only**: All operations are paper trading - never real money

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

---

## 🚀 AUTOMATIC DISCOVERY SYSTEM

**Core Architecture Principle**: SLATE ALWAYS starts with automatic discovery enabled and running continuously.

### How Automatic Discovery Works

1. **Startup Behavior**:
   - Discovery starts IMMEDIATELY when SLATE launches
   - No manual intervention required
   - System is "always on" by default

2. **Continuous Operation**:
   - Discovery runs in continuous cycles (5-second intervals)
   - Tests diverse strategies across all timeframes (1m to daily)
   - Stores results in persistent database
   - Learns from previous discoveries

3. **Smart Pause/Resume**:
   - User activity automatically pauses discovery
   - API calls, queries, and tasks trigger pause
   - Resumes after 5 minutes of user inactivity
   - Ensures user requests get priority

4. **Multi-Timeframe Exploration**:
   - Tests across: 1m, 5m, 15m, 30m, 1h, 4h, 8h, 12h, 1d
   - Ensures comprehensive temporal coverage
   - Discovers edges across different market rhythms

### Startup Coordinator

The `StartupCoordinator` class manages automatic discovery:

```python
from slate_core.startup_coordinator import get_startup_coordinator

# Get coordinator (auto-starts discovery)
coordinator = get_startup_coordinator()

# Check status
status = coordinator.get_status()
# Returns: state, idle time, resume countdown, etc.

# Record user activity (auto-pauses)
coordinator.record_user_activity()
```

### System States

- `AUTO_DISCOVERY`: Running continuous discovery (default)
- `USER_TASK`: Executing specific user request
- `PAUSED`: Temporarily paused
- `IDLE`: Waiting to resume

### Integration Points

**In Server** (`slate_core/server.py`):
```python
# Startup event initializes coordinator
startup_coordinator = get_startup_coordinator()

# All API endpoints track user activity
@app.post("/api/discovery/start")
async def start_discovery():
    track_user_activity()  # Pauses discovery
    # ... user request handling
```

**In Direct Usage**:
```python
from slate_core.startup_coordinator import execute_with_discovery_paused

# Execute task with discovery paused
result = await execute_with_discovery_paused(
    my_function, arg1, arg2
)
```

---

## 🤖 AUTONOMOUS SYSTEM

**Advanced AI Capabilities** for self-directed market exploration.

### Autonomous Orchestrator

Manages independent market analysis operations:

```python
from slate_core.autonomous import AutonomousOrchestrator

orchestrator = AutonomousOrchestrator(config)
orchestrator.start()  # Starts autonomous loop
```

**Features**:
- Idle detection (activates after 5 minutes user inactivity)
- Trading decision-making coordination
- Strategy discovery and validation
- Resource management and safety constraints
- Reactive priority (user requests interrupt)

**Safety Constraints**:
- Only operates during idle periods
- User queries immediately pause operations
- All strategies validated with realistic costs
- Resource constraints enforced (CPU, memory, time)
- Only modifies files within `slate_core/` directory

### Autonomous Components

1. **ResourceManager**: Monitors CPU, memory, time usage
2. **TradingDecisionMaker**: Generates trading goals
3. **StrategyValidator**: Validates with realistic costs
4. **DiscoveryReporter**: Reports discoveries
5. **MarketSubAgentSpawner**: Spawns specialized agents

---

## 🧠 MEMORY SYSTEMS

### Persistent Memory (GraphPalace)

Stores discoveries in knowledge graph for cross-cycle learning:

```python
from slate_core.discovery.discovery_memory import get_discovery_memory

memory = get_discovery_memory()
memory.store_discovery(result)
```

**Location**: `slate_core/palace_data/discoveries/`

### Reflection Memory

Cross-cycle learning and experience tracking:

```python
from slate_core.discovery.reflection_memory import get_reflection_memory

memory = get_reflection_memory()
lessons = memory.get_recent_lessons(limit=10)
context = memory.get_context_for_new_cycle()
```

**Location**: `~/.slate/memory/discovery_memory.md`

### Checkpoint Manager

Crash recovery for incomplete discovery cycles:

```python
from slate_core.discovery.checkpoint_manager import get_checkpoint_manager

mgr = get_checkpoint_manager()
incomplete = mgr.get_incomplete_cycles()
```

---

## 📊 DISCOVERY ENGINE

**Core Engine**: `EdgeDiscoveryEngine` in `slate_core/discovery/edge_discovery_engine.py`

### Strategy Types Tested

- **Momentum**: EMA crossovers, RSI breakouts, MACD momentum
- **Mean Reversion**: Bollinger Bands, RSI reversals, support/resistance
- **Volatility**: ATR breakouts, volatility squeezes, VIX proxies
- **Time-Based**: Session patterns, time-of-day effects
- **Market Microstructure**: Order flow imbalances, gamma exposure
- **Correlation**: Cross-asset arbitrage opportunities
- **Fundamental**: Momentum based on fundamental factors

### Validation Methods

1. **Brutal Transaction Costs**:
   - Maker fee: 0.02%
   - Taker fee: 0.05%
   - Base slippage: 10 bps (volatility-adjusted)
   - Fill rate: 85% (realistic, not 100%)

2. **Monte Carlo Validation**:
   - 100+ paths per strategy
   - 5th percentile risk assessment
   - Path profitability rate

3. **Walk-Forward Analysis**:
   - 5 rolling windows
   - 30% out-of-sample
   - Temporal robustness testing

4. **Risk Constraints**:
   - Maximum 25% drawdown
   - 5% max position size
   - 15% total portfolio heat

### Performance Metrics

**Primary Metric**: USDT Profit (actual dollar profit)

**Supporting Metrics**:
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Win Rate, Profit Factor
- Maximum Drawdown
- Monte Carlo confidence intervals
- Walk-forward stability

---

## 🔌 API ENDPOINTS

### Health & Status

- `GET /health` - System health check
- `GET /api/metrics` - System metrics
- `GET /api/health/summary` - Complete health summary

### Discovery Control

- `POST /api/discovery/start` - Start discovery cycle
- `POST /api/discovery/stop` - Stop discovery
- `GET /api/discovery/status` - Current status
- `GET /api/discovery/top` - Top strategies
- `GET /api/discovery/statistics` - Overall statistics
- `GET /api/discovery/benchmark` - Benchmark comparison
- `GET /api/discovery/correlation` - Strategy correlation
- `GET /api/discovery/portfolio/optimize` - Portfolio optimization

### Natural Language Strategy Generation

- `POST /api/discovery/nl/generate` - Generate strategy from description
- `POST /api/discovery/nl/test` - Generate and test strategy

### Checkpoint & Recovery

- `GET /api/discovery/checkpoint/status` - Checkpoint status
- `POST /api/discovery/checkpoint/resume` - Resume from checkpoint
- `POST /api/discovery/checkpoint/clear` - Clear checkpoints

### Memory Systems

- `GET /api/memory/reflection` - Get reflection memory
- `GET /api/memory/lessons` - Get recent lessons
- `GET /api/memory/context` - Get discovery context
- `POST /api/memory/clear` - Clear reflection memory

### YouTube Integration

- `POST /api/youtube/transcribe` - Transcribe YouTube video
- `POST /api/youtube/search` - Search transcript
- `GET /api/youtube/status` - YouTube capabilities status
- `POST /api/youtube/cache/clear` - Clear transcript cache

### Autonomous System

- `GET /api/autonomous/status` - Autonomous system status
- `GET /api/autonomous/discoveries` - Autonomous discoveries
- `POST /api/autonomous/start` - Start autonomous operations
- `POST /api/autonomous/stop` - Stop autonomous operations
- `GET /api/autonomous/report` - Generate autonomous report

---

## 📁 DIRECTORY STRUCTURE

```
slate_core/
├── __init__.py                          # Core module initialization
├── server.py                            # Main server with auto-discovery
├── startup_coordinator.py              # Automatic discovery management
├── autonomous/                          # Autonomous system
│   ├── __init__.py
│   ├── orchestrator.py                 # Main coordinator
│   ├── config.py                       # Configuration
│   ├── resource_manager.py             # Resource monitoring
│   ├── decision_maker.py               # Trading decisions
│   ├── strategy_validator.py          # Strategy validation
│   ├── sub_agent_spawner.py            # Agent spawning
│   └── discovery_reporter.py           # Discovery reporting
├── discovery/                          # Discovery engine
│   ├── edge_discovery_engine.py       # Main discovery engine
│   ├── discovery_memory.py            # Persistent memory
│   ├── reflection_memory.py           # Cross-cycle learning
│   └── checkpoint_manager.py          # Crash recovery
├── intelligence/                        # Advanced AI modules
│   ├── autonomous_discovery_engine.py
│   ├── market_regime_detector.py
│   ├── ensemble_discovery.py
│   └── genetic_optimizer.py
├── connectors/                         # Exchange connectors
│   ├── binance_spot.py
│   └── binance_usdt_perpetual.py
├── statistics/                         # Statistical validation
│   ├── statistical_validator.py
│   ├── bootstrap_validation.py
│   ├── multiple_testing_correction.py
│   └── walk_forward_validation.py
└── external_data/                      # External data sources
    ├── youtube_transcriber.py
    └── video_insight_extractor.py
```

---

## 🎯 RECENT ARCHITECTURE CHANGES

### Version 2.0.0 - Automatic Discovery Architecture

**Major Changes**:

1. **Startup Coordinator** (`startup_coordinator.py`):
   - Ensures discovery ALWAYS starts on server startup
   - Manages pause/resume based on user activity
   - Provides system status and monitoring
   - Coordinates between autonomous and manual operations

2. **Core Module** (`__init__.py`):
   - Unified entry point for SLATE system
   - `create_slate_system()` for easy initialization
   - `auto_start_discovery()` for background operation

3. **Enhanced Server Integration**:
   - Startup coordinator integrated into server startup
   - All API endpoints track user activity
   - Health endpoint includes coordinator status
   - Automatic pause/resume functionality

4. **Improved State Management**:
   - Clear system states (AUTO_DISCOVERY, USER_TASK, PAUSED, IDLE)
   - Activity tracking with timestamps
   - Idle timeout management (5 minutes)
   - Priority system for user vs. autonomous operations

5. **Safety Constraints**:
   - All operations maintain paper-trading mode
   - Realistic transaction costs always enforced
   - Resource limits (CPU, memory, time)
   - File system safety (only modifies `slate_core/`)

**Benefits**:
- SLATE is now "always on" and discovering continuously
- User requests get automatic priority
- Better resource utilization
- Improved crash recovery
- Clearer operational semantics
