# SLATE - Strategy Learning & Autonomous Trading Engine

**AI-driven autonomous trading strategy discovery system for cryptocurrency markets**

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)
![Paper Trading](https://img.shields.io/badge/trading-paper_only-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🧪 What is SLATE?

SLATE (Strategy Learning & Autonomous Trading Engine) is an intelligent system that automatically discovers, tests, and validates cryptocurrency trading strategies using machine learning and statistical analysis. It continuously explores diverse strategy templates to find profitable edges in market data.

**⚠️ IMPORTANT:** SLATE runs in **PAPER TRADING MODE ONLY**. No real money is ever risked.

## ✨ Key Features

- **🤖 Autonomous Discovery**: Continuously tests 35+ diverse strategy templates
- **📊 Modern Dashboard**: Real-time web interface with charts and analytics
- **💰 Brutal Realism**: Honest backtesting with realistic fees, slippage, and fill rates
- **🎯 Diverse Strategies**: Momentum, mean reversion, time patterns, microstructure, statistical arbitrage, and more
- **🧠 Monte Carlo Validation**: 100+ path validation for robustness
- **📈 Performance Metrics**: Sharpe ratio, drawdown, win rate, profit factor analysis
- **🔄 Continuous Learning**: Auto-runs discovery cycles every 5 seconds
- **🗄️ Persistent Memory**: Knowledge graph storage of discovered edges

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Dependencies: `pip install -e ".[dev]`

### Installation

```bash
git clone https://github.com/Tilanthi/SLATE.git
cd SLATE
pip install -e .
```

### Start the Server

```bash
python -m slate_core.server
```

The dashboard will be available at: **http://127.0.0.1:8788**

## 📱 Dashboard Features

### Main Dashboard (http://127.0.0.1:8788)

- **Real-time Statistics**: Live discovery metrics and performance
- **Strategy Performance**: Top strategies with detailed metrics
- **Interactive Charts**: Return distribution, win rates, performance over time
- **Discovery Control**: Start/stop discovery, manual refresh
- **Strategy Filtering**: Sort by return, profit, Sharpe ratio, win rate
- **CSV Export**: Export strategy data for further analysis
- **Auto-refresh**: Updates every 5 seconds

### Natural Language Strategy Generation

SLATE now includes a powerful natural language to strategy conversion feature inspired by Vibe-Trading. Simply describe a trading strategy in plain English, and SLATE will automatically convert it to a testable strategy template.

**How it works:**
1. Enter a strategy description in the dashboard (e.g., "Test a mean reversion strategy when RSI is below 30")
2. SLATE parses your description using rule-based patterns or LLM integration
3. Click "Generate Strategy" to preview the strategy parameters
4. Click "Generate & Test" to immediately backtest the strategy
5. Results are automatically saved to the database

### Benchmark Comparison Panel

SLATE automatically compares all strategies against a buy-and-hold baseline to provide meaningful performance context.

**Features:**
- **Beat Market Rate**: Percentage of strategies that outperform buy-and-hold
- **Cumulative Excess Return**: Total profit over buy-and-hold baseline
- **Information Ratio**: Risk-adjusted excess return (excess return / tracking error)
- **Strategy vs Buy & Hold Chart**: Visual comparison of top and worst performers

**API Endpoint:**
```bash
GET /api/discovery/benchmark
```

### Strategy Correlation Analysis

Advanced correlation analysis helps identify diversification opportunities and redundant strategies.

**Features:**
- **Correlation Matrix**: Heatmap showing correlations between strategy types
- **Redundancy Detection**: Identifies highly correlated strategies (>0.8) that may be redundant
- **Diversification Opportunities**: Highlights low-correlation pairs (<0.3) for optimal diversification
- **Multi-Metric Correlation**: Uses returns, Sharpe ratio, and win rate for comprehensive analysis

**API Endpoint:**
```bash
GET /api/discovery/correlation
```

### Portfolio Optimization Engine

Combine multiple strategies optimally using modern portfolio theory.

**Optimization Methods:**
- **Mean-Variance (Markowitz)**: Traditional mean-variance optimization
- **Risk Parity**: Equal risk contribution across strategies
- **Maximize Sharpe Ratio**: Weight strategies by their Sharpe ratios
- **Equal Weight**: Simple equal-weighted portfolio

**Features:**
- **Optimal Allocations**: Calculates optimal weight distribution across strategies
- **Portfolio Metrics**: Expected return, profit, Sharpe ratio, drawdown
- **Diversification Ratio**: Measures effective diversification benefit
- **Visual Allocation Chart**: Pie chart showing portfolio composition

**API Endpoint:**
```bash
GET /api/discovery/portfolio/optimize?method=mean_variance
```

**Example descriptions:**
- "Test a mean reversion strategy when RSI is below 30"
- "Create a momentum strategy with EMA 12/26 crossover"
- "Test a breakout strategy when volume is high"
- "Create a volatility squeeze play strategy"
- "Test a support bounce strategy with 20-period lookback"

**Supported LLM providers:**
- **OpenAI**: GPT-4o-mini for advanced strategy generation
- **Anthropic**: Claude 3.5 Haiku for fast, accurate conversion
- **Google**: Gemini 2.0 Flash Exp for multimodal understanding
- **xAI**: Grok Beta for alternative perspectives
- **DeepSeek**: DeepSeek Chat for cost-effective generation
- **Qwen**: Alibaba Qwen Turbo for Chinese language optimization
- **GLM**: Zhipu GLM-4 Flash for enterprise solutions
- **OpenRouter**: Access to 100+ models via single API
- **Ollama**: Local models for privacy-conscious users
- **Azure OpenAI**: Enterprise-grade OpenAI deployment
- **Mock**: Rule-based fallback (default, no API key required)

**API Endpoints:**
```bash
# Generate strategy from description
POST /api/discovery/nl/generate
{
  "description": "Test a mean reversion strategy when RSI is below 30",
  "provider": "openai"  # or "anthropic", "google", "xai", "deepseek", etc.
}

# Generate and immediately test strategy
POST /api/discovery/nl/test
{
  "description": "Test a breakout strategy when volume is high"
}
```

### Checkpoint & Recovery System

SLATE now includes a robust checkpoint/recovery system inspired by TradingAgents:

**Features:**
- **Automatic State Saving**: Saves progress after each strategy tested
- **Crash Recovery**: Resume from last checkpoint if interrupted
- **SQLite Storage**: Per-cycle checkpoint databases at `~/.slate/cache/checkpoints/`
- **Progress Tracking**: Monitor incomplete cycles and resume points

**API Endpoints:**
```bash
# Get checkpoint status
GET /api/discovery/checkpoint/status

# Resume from specific checkpoint
POST /api/discovery/checkpoint/resume
{
  "cycle_id": "uuid-of-cycle-to-resume"
}

# Clear specific checkpoint or all
POST /api/discovery/checkpoint/clear
{
  "cycle_id": "optional-uuid-or-omit-for-all"
}
```

**Usage:**
```python
from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

# Enable checkpointing
engine = EdgeDiscoveryEngine(checkpoint_enabled=True)

# Run with checkpoint support
result = await engine.run_discovery_cycle_with_checkpoint()

# Resume from crashed cycle
result = await engine.run_discovery_cycle_with_checkpoint(
    resume_cycle_id="previous-cycle-id"
)
```

### Reflection Memory System

SLATE learns from past discoveries using a markdown-based reflection memory:

**Features:**
- **Persistent Logging**: Each cycle logged to `~/.slate/memory/discovery_memory.md`
- **Automatic Reflection**: Generates lessons learned from performance
- **Cross-Cycle Learning**: Past insights inform future cycles
- **Pattern Recognition**: Identifies what works/doesn't work

**API Endpoints:**
```bash
# Get full reflection memory
GET /api/memory/reflection

# Get recent lessons
GET /api/memory/lessons?limit=10

# Get context for new cycle
GET /api/memory/context

# Clear reflection memory
POST /api/memory/clear
```

**Usage:**
```python
from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

# Enable reflection memory (default: enabled)
engine = EdgeDiscoveryEngine(reflection_enabled=True)

# Run discovery - automatically logs to memory
result = await engine.run_discovery_cycle()

# Get context for next cycle
from slate_core.discovery.reflection_memory import get_reflection_memory
memory = get_reflection_memory()
context = memory.get_context_for_new_cycle()
```

### API Documentation

- **Swagger UI**: http://127.0.0.1:8788/docs
- **ReDoc**: http://127.0.0.1:8788/redoc
- **Statistics API**: `/api/discovery/statistics`
- **Top Strategies**: `/api/discovery/top?limit=10&sort_by=total_profit_usdt`
- **NL Strategy Generate**: `/api/discovery/nl/generate`
- **NL Strategy Test**: `/api/discovery/nl/test`
- **Benchmark Comparison**: `/api/discovery/benchmark`
- **Strategy Correlation**: `/api/discovery/correlation`
- **Portfolio Optimization**: `/api/discovery/portfolio/optimize?method=mean_variance`
- **Checkpoint Status**: `/api/discovery/checkpoint/status`
- **Checkpoint Resume**: `/api/discovery/checkpoint/resume`
- **Reflection Memory**: `/api/memory/reflection`

## 🧩 Strategy Types

SLATE tests **35+ diverse strategy templates** across 8 categories:

### Momentum Strategies
- EMA Crossover Momentum
- RSI Momentum Breakout
- MACD Histogram Momentum
- Breakout Pullback Entry

### Mean Reversion Strategies
- Bollinger Band Mean Reversion
- RSI Extremes Reversal
- Support/Resistance Bounce
- Fibonacci Retracement Fade

### Volatility Strategies
- ATR Breakout Expansion
- Volatility Squeeze Play
- VIX Proxy Spike Fade
- Gamma Exposure Scalping

### Time-Based Strategies
- Asian Session Range Fade
- London Open Volatility Breakout
- NY Open Momentum
- End-of-Day Reversal
- Weekend Gap Fade
- CPI/Pivot News Play

### Market Microstructure
- Order Flow Imbalance
- Liquidity Sweep Reversal
- Iceberg Order Detection
- Tick Volume Anomaly
- Bid-Ask Spread Dynamics

### Statistical Arbitrage
- Pairs Trading Signal
- Statistical Mean Reversion
- Cointegration Breakdown
- Z-Score Extreme Entry

### Pattern Recognition
- Double Top/Bottom
- Head and Shoulders
- Triangle Breakout
- Flag Pattern Continuation
- Cup and Handle

### Advanced/ML-Inspired
- Multi-Timeframe Alignment
- Trend Strength Adaptive
- Regime Switching Model
- Momentum Decay Model

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# API Keys (if using external data sources)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Server Configuration
HOST=0.0.0.0
PORT=8788
```

### Backtest Configuration

Located in `slate_core/discovery/edge_discovery_engine.py`:

```python
@dataclass
class EdgeBacktestConfig:
    # Transaction costs
    maker_fee: float = 0.0002      # 0.02%
    taker_fee: float = 0.0005      # 0.05%
    base_slippage_bps: int = 10     # 10 bps
    
    # Fill realism
    base_fill_rate: float = 0.85    # 85% fill rate
    partial_fill_probability: float = 0.15
    partial_fill_min_size: float = 0.3  # 30% minimum fill
    
    # Risk management
    max_position_size: float = 0.05  # 5% max per position
    stop_loss_atr_multiple: float = 2.0
    take_profit_atr_multiple: float = 3.0
    
    # Validation
    monte_carlo_paths: int = 100     # 100 Monte Carlo paths
    walk_forward_windows: int = 5
```

## 📊 Performance Metrics

Each strategy is evaluated using:

- **USDT Profit**: Primary metric (actual profit in USDT)
- **Return Percentage**: ROI on initial capital
- **Sharpe Ratio**: Risk-adjusted returns
- **Sortino Ratio**: Downside risk-adjusted returns
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss
- **Beat Market**: Performance vs buy-and-hold

## 🛠️ Development

### Project Structure

```
SLATE/
├── slate_core/
│   ├── server.py                 # FastAPI server & dashboard
│   ├── static/                    # Web dashboard assets
│   │   ├── index.html            # Main dashboard
│   │   ├── css/
│   │   │   └── dashboard.css     # Dashboard styling
│   │   └── js/
│   │       ├── api.js             # API client with retry logic
│   │       ├── app.js             # Dashboard application logic
│   │       ├── charts.js          # Chart.js visualizations
│   │       └── utils.js           # Utility functions
│   ├── discovery/
│   │   ├── edge_discovery_engine.py  # Main discovery engine
│   │   ├── discovery_memory.py       # Persistent memory system
│   │   └── nl_strategy_generator.py  # Natural language to strategy conversion
│   └── palace_data/               # Knowledge graph storage
├── tests/                         # Test suite
└── requirements.txt               # Python dependencies
```

### Adding New Strategies

**Method 1: Using Natural Language (Recommended for quick testing)**

Simply use the dashboard's Natural Language Strategy Generator:
1. Enter a description like "Test a mean reversion strategy when RSI is below 30"
2. Click "Generate & Test" to immediately backtest
3. Results are saved automatically to the database

**Method 2: Programming New Templates**

To add a new strategy template programmatically:

1. Add a new template method in `edge_discovery_engine.py`
2. Implement the `_check_entry_signal()` logic for your strategy
3. Add any required technical indicators to `_calculate_indicators()`
4. The system will automatically test it with random variations

### Running Tests

```bash
pytest tests/ -v
```

## 📈 API Endpoints

### Statistics
```bash
GET /api/discovery/statistics
```

### Top Strategies
```bash
GET /api/discovery/top?limit=10&sort_by=total_profit_usdt
```

### Discovery Control
```bash
POST /api/discovery/start
POST /api/discovery/stop
GET /api/discovery/status
```

### Health Check
```bash
GET /health
```

## ⚠️ Disclaimer

**THIS IS PAPER TRADING ONLY**

- No real money is ever risked
- All results are simulated
- Past performance does not guarantee future results
- Always do your own research before trading

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with FastAPI, Python, and JavaScript
- Uses Chart.js for visualizations
- Market data from Binance public API
- Inspired by quantitative trading research

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the API documentation at `/docs`
- Review the test files for examples

---

**Note**: SLATE is actively developed. Features and APIs may change as the system evolves.

**Status**: ✅ Active Development | 🧪 Paper Trading Only
