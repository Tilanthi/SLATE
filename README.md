# SLATE - Strategy Learning & Autonomous Trading Engine

A unified autonomous trading platform for cryptocurrency markets. **Paper trading and simulation only - NO LIVE TRADING.**

## Features

- **Multi-Language Support**: Python (native), Pine Script v5, HaasScript v2.0
- **Bidirectional Cross-Compilation**: Seamlessly convert between Python, Pine Script, and HaasScript
- **Autonomous Strategy Discovery**: 5 discovery methods for generating new strategies
- **Paper Trading**: Simulated trading environment (never executes real trades)
- **Risk Management**: 5-state risk FSM with Kelly Criterion and volatility targeting
- **Backtesting Engine**: Validate strategies on historical data
- **Real-time Dashboard**: Monitor system performance and discoveries

## Supported Exchanges

- Binance Futures USDT-M (paper trading)
- Bitget Perpetual (paper trading)

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Start the server
python3 -m slate_core.server

# Access dashboard
# http://localhost:8787/dashboard
```

## OODA Trading Cycle

SLATE uses an OODA cycle for autonomous trading:

1. **Observe**: Collect market data, price action, indicators
2. **Orient**: Analyze signals, detect regime, assess risk
3. **Decide**: Strategy selection, position sizing, risk assessment
4. **Act**: Execute paper trades, monitor positions
5. **Learn**: Update performance, adapt parameters

## Language Support

### HaasScript Cross-Compiler

**CRITICAL**: HaasScript uses 1-based array indexing (first element at index 1).

Python to HaasScript translation:
```python
# Python (0-based)
price = prices[0]

# HaasScript (1-based)
local price = IndexArray(prices, 1)
```

HaasScript to Python translation:
```lua
-- HaasScript (1-based)
local price = IndexArray(prices, 1)

-- Python (0-based)
price = prices[0]
```

### Pine Script Cross-Compiler

Pine Script uses 0-based indexing (same as Python), so no index translation needed.

## API Endpoints

The server provides 89 endpoints across:

- Health & Monitoring (7 endpoints)
- Strategy Management (15 endpoints)
- Language & Compilation (12 endpoints)
- Discovery & Research (15 endpoints)
- Risk Management (12 endpoints)
- Data & Markets (10 endpoints)
- Engine Control (8 endpoints)
- Utilities (10 endpoints)

See `/docs` for full API documentation.

## Safety

- **NO LIVE TRADING**: SLATE only operates in paper trading mode
- All trades are simulated
- No real money is ever at risk
- Use for research and backtesting only

## License

MIT License - See LICENSE file for details
