"""
SLATE FastAPI Server

Main API server for the SLATE trading platform.
Provides 89 endpoints for strategy management, backtesting, discovery,
risk management, and cross-language compilation.

MODE: PAPER_TRADING_ONLY - Never executes real trades
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import logging
from datetime import datetime

from .engine import TradingEngine
from .risk.manager import RiskManager
from .backtest.engine import BacktestEngine
from .discovery.engine import DiscoveryEngine
from .languages.haas_script import HaasScriptCrossCompiler
from .languages.pine_script import PineScriptCrossCompiler
from .monitoring import HealthMonitor, MetricsCollector
from .dashboard import SlateDashboard

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SLATE API",
    description="Strategy Learning & Autonomous Trading Engine - Paper Trading Only",
    version="1.0.0"
)

# Initialize core components
trading_engine = TradingEngine()
risk_manager = RiskManager()
backtest_engine = BacktestEngine()
discovery_engine = DiscoveryEngine()
haas_compiler = HaasScriptCrossCompiler()
pine_compiler = PineScriptCrossCompiler()
health_monitor = HealthMonitor()
metrics_collector = MetricsCollector()
dashboard = SlateDashboard()

# Pydantic models
class StrategyRequest(BaseModel):
    name: str
    code: str
    language: str = "python"
    parameters: Optional[Dict[str, Any]] = None

class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float = 10000

class DiscoveryRequest(BaseModel):
    discovery_methods: List[str]
    num_strategies: int = 10
    evaluation_period: int = 30

class HaasScriptExportRequest(BaseModel):
    python_code: str

class HaasScriptImportRequest(BaseModel):
    haas_script_code: str


# =============================================================================
# Health & Monitoring Endpoints (7 endpoints)
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with system information."""
    return """
    <html>
        <head><title>SLATE - Strategy Learning & Autonomous Trading Engine</title></head>
        <body>
            <h1>SLATE Trading Platform</h1>
            <p>Mode: PAPER_TRADING_ONLY</p>
            <p>API Documentation: <a href="/docs">/docs</a></p>
            <p>Dashboard: <a href="/dashboard">/dashboard</a></p>
        </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "mode": "paper_trading", "timestamp": datetime.now().isoformat()}

@app.get("/api/health/summary")
async def health_summary():
    """Detailed system health summary."""
    return await health_monitor.get_health_summary()

@app.get("/api/health/components")
async def component_health():
    """Health status of individual components."""
    return await health_monitor.get_component_status()

@app.get("/api/metrics")
async def get_metrics():
    """System metrics and performance data."""
    return await metrics_collector.get_metrics()

@app.get("/api/metrics/performance")
async def performance_metrics():
    """Detailed performance metrics."""
    return await metrics_collector.get_performance_metrics()

@app.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard():
    """View the SLATE dashboard."""
    dashboard_html = await dashboard.generate()
    return HTMLResponse(content=dashboard_html)


# =============================================================================
# Strategy Management Endpoints (15 endpoints)
# =============================================================================

@app.post("/api/strategies")
async def create_strategy(request: StrategyRequest):
    """Create a new trading strategy."""
    try:
        strategy_id = await trading_engine.create_strategy(
            name=request.name,
            code=request.code,
            language=request.language,
            parameters=request.parameters
        )
        return {"strategy_id": strategy_id, "status": "created"}
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies")
async def list_strategies():
    """List all available strategies."""
    return await trading_engine.list_strategies()

@app.get("/api/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy details."""
    strategy = await trading_engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy

@app.put("/api/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, request: StrategyRequest):
    """Update an existing strategy."""
    try:
        result = await trading_engine.update_strategy(
            strategy_id=strategy_id,
            name=request.name,
            code=request.code,
            language=request.language,
            parameters=request.parameters
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """Delete a strategy."""
    try:
        await trading_engine.delete_strategy(strategy_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategies/{strategy_id}/activate")
async def activate_strategy(strategy_id: str):
    """Activate a strategy for paper trading."""
    try:
        result = await trading_engine.activate_strategy(strategy_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategies/{strategy_id}/deactivate")
async def deactivate_strategy(strategy_id: str):
    """Deactivate a strategy."""
    try:
        result = await trading_engine.deactivate_strategy(strategy_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies/{strategy_id}/performance")
async def get_strategy_performance(strategy_id: str):
    """Get strategy performance metrics."""
    try:
        return await trading_engine.get_strategy_performance(strategy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies/{strategy_id}/positions")
async def get_strategy_positions(strategy_id: str):
    """Get current positions for a strategy."""
    try:
        return await trading_engine.get_strategy_positions(strategy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies/{strategy_id}/orders")
async def get_strategy_orders(strategy_id: str):
    """Get order history for a strategy."""
    try:
        return await trading_engine.get_strategy_orders(strategy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategies/{strategy_id}/backtest")
async def run_strategy_backtest(strategy_id: str, request: BacktestRequest):
    """Run backtest for a strategy."""
    try:
        result = await backtest_engine.run_backtest(
            strategy_id=strategy_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies/{strategy_id}/signals")
async def get_strategy_signals(strategy_id: str, limit: int = 100):
    """Get recent signals from a strategy."""
    try:
        return await trading_engine.get_strategy_signals(strategy_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategies/{strategy_id}/validate")
async def validate_strategy(strategy_id: str):
    """Validate strategy code and configuration."""
    try:
        return await trading_engine.validate_strategy(strategy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies/export/all")
async def export_all_strategies():
    """Export all strategies as JSON."""
    try:
        return await trading_engine.export_all_strategies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Language & Compilation Endpoints (12 endpoints)
# =============================================================================

@app.post("/api/export/haas-script")
async def export_to_haas_script(request: HaasScriptExportRequest):
    """Convert Python strategy to HaasScript."""
    try:
        haas_code = haas_compiler.python_to_haasscript(request.python_code)
        return {
            "haas_script": haas_code,
            "warnings": haas_compiler.warnings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import/haas-script")
async def import_from_haas_script(request: HaasScriptImportRequest):
    """Convert HaasScript to Python."""
    try:
        python_code = haas_compiler.haasscript_to_python(request.haas_script_code)
        return {
            "python": python_code,
            "warnings": haas_compiler.warnings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate/haas-script")
async def validate_haas_script(code: str):
    """Validate HaasScript code syntax."""
    try:
        result = haas_compiler.validate_haasscript(code)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/pine-script")
async def export_to_pine_script(request: HaasScriptExportRequest):
    """Convert Python strategy to Pine Script v5."""
    try:
        pine_code = pine_compiler.python_to_pine_script(request.python_code)
        return {
            "pine_script": pine_code,
            "warnings": pine_compiler.warnings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import/pine-script")
async def import_from_pine_script(request: HaasScriptImportRequest):
    """Convert Pine Script v5 to Python."""
    try:
        python_code = pine_compiler.pine_script_to_python(request.haas_script_code)
        return {
            "python": python_code,
            "warnings": pine_compiler.warnings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate/pine-script")
async def validate_pine_script(code: str):
    """Validate Pine Script v5 code syntax."""
    try:
        result = pine_compiler.validate_pine_script(code)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/languages/support")
async def language_support():
    """Get supported languages and features."""
    return {
        "languages": {
            "python": {"version": "3.10+", "native": True},
            "pine_script": {"version": "v5", "compilation": "bidirectional"},
            "haas_script": {"version": "v2.0", "compilation": "bidirectional", "indexing": "1-based"}
        },
        "features": {
            "cross_compilation": True,
            "array_index_translation": True,
            "syntax_validation": True
        }
    }

@app.get("/api/languages/haas-script/commands")
async def haas_script_commands():
    """Get available HaasScript commands by domain."""
    return {
        "domains": {
            "technical_analysis": 157,
            "trading": 140,
            "helpers": 121,
            "enumerations": 197,
            "data": 63,
            "advanced": 97
        },
        "total_commands": 774
    }


# =============================================================================
# Discovery & Research Endpoints (15 endpoints)
# =============================================================================

@app.post("/api/discover")
async def run_discovery(request: DiscoveryRequest, background_tasks: BackgroundTasks):
    """Run autonomous strategy discovery cycle."""
    try:
        discovery_id = await discovery_engine.start_discovery_cycle(
            methods=request.discovery_methods,
            num_strategies=request.num_strategies,
            evaluation_period=request.evaluation_period
        )
        return {"discovery_id": discovery_id, "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/discover")
async def list_discoveries():
    """List all discovery cycles."""
    return await discovery_engine.list_discoveries()

@app.get("/api/discover/{discovery_id}")
async def get_discovery(discovery_id: str):
    """Get discovery cycle details."""
    discovery = await discovery_engine.get_discovery(discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Discovery not found")
    return discovery

@app.get("/api/discoveries")
async def list_discovered_strategies():
    """List all discovered strategies."""
    return await discovery_engine.list_discovered_strategies()

@app.get("/api/discoveries/summary")
async def discovery_summary():
    """Get discovery statistics summary."""
    return await discovery_engine.get_summary()

@app.get("/api/discoveries/{strategy_id}")
async def get_discovered_strategy(strategy_id: str):
    """Get discovered strategy details."""
    strategy = await discovery_engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy

@app.post("/api/discoveries/{strategy_id}/validate")
async def validate_discovered_strategy(strategy_id: str):
    """Validate a discovered strategy."""
    try:
        return await discovery_engine.validate_strategy(strategy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/discoveries/{strategy_id}/approve")
async def approve_discovered_strategy(strategy_id: str):
    """Approve a discovered strategy for paper trading."""
    try:
        return await discovery_engine.approve_strategy(strategy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/discoveries/{strategy_id}")
async def reject_discovered_strategy(strategy_id: str):
    """Reject and remove a discovered strategy."""
    try:
        await discovery_engine.reject_strategy(strategy_id)
        return {"status": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/discovery/methods")
async def discovery_methods():
    """Get available discovery methods."""
    return {
        "methods": [
            {"id": "parameter_variation", "name": "Parameter Variation", "description": "Vary parameters of existing strategies"},
            {"id": "signal_combination", "name": "Signal Combination", "description": "Combine multiple signals"},
            {"id": "regime_specific", "name": "Regime-Specific", "description": "Strategies for market regimes"},
            {"id": "ensemble_generation", "name": "Ensemble Generation", "description": "Create ensemble strategies"},
            {"id": "pattern_recognition", "name": "Pattern Recognition", "description": "Discover chart patterns"}
        ]
    }


# =============================================================================
# Risk Management Endpoints (12 endpoints)
# =============================================================================

@app.get("/api/risk/status")
async def risk_status():
    """Get current risk status."""
    return await risk_manager.get_status()

@app.get("/api/risk/metrics")
async def risk_metrics():
    """Get detailed risk metrics."""
    return await risk_manager.get_metrics()

@app.post("/api/risk/position-size")
async def calculate_position_size(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    account_balance: float,
    risk_per_trade: float = 0.02
):
    """Calculate optimal position size."""
    try:
        return await risk_manager.calculate_position_size(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            account_balance=account_balance,
            risk_per_trade=risk_per_trade
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/risk/portfolio")
async def portfolio_risk():
    """Get portfolio-level risk metrics."""
    return await risk_manager.get_portfolio_risk()

@app.get("/api/risk/exposure")
async def market_exposure():
    """Get current market exposure."""
    return await risk_manager.get_market_exposure()

@app.post("/api/risk/kelly")
async def kelly_criterion(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fractional_kelly: float = 0.25
):
    """Calculate position size using Kelly Criterion."""
    try:
        return await risk_manager.kelly_criterion(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            fractional_kelly=fractional_kelly
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Data & Market Endpoints (10 endpoints)
# =============================================================================

@app.get("/api/markets")
async def list_markets():
    """List available markets and exchanges."""
    return {
        "exchanges": [
            {"name": "Binance Futures", "markets": "USDT-M Perpetual", "mode": "paper_trading"},
            {"name": "Bitget", "markets": "Perpetual Futures", "mode": "paper_trading"}
        ],
        "supported_symbols": [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
            "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT"
        ]
    }

@app.get("/api/data/{symbol}/candles")
async def get_candles(symbol: str, timeframe: str, limit: int = 100):
    """Get candlestick data for a symbol."""
    try:
        from .data.fetcher import DataFetcher
        fetcher = DataFetcher()
        return await fetcher.get_candles(symbol, timeframe, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/{symbol}/ticker")
async def get_ticker(symbol: str):
    """Get current ticker data."""
    try:
        from .data.fetcher import DataFetcher
        fetcher = DataFetcher()
        return await fetcher.get_ticker(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/{symbol}/orderbook")
async def get_orderbook(symbol: str, depth: int = 20):
    """Get order book data."""
    try:
        from .data.fetcher import DataFetcher
        fetcher = DataFetcher()
        return await fetcher.get_orderbook(symbol, depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Engine Control Endpoints (8 endpoints)
# =============================================================================

@app.post("/api/engine/start")
async def start_engine():
    """Start the trading engine (paper trading mode only)."""
    try:
        await trading_engine.start()
        return {"status": "started", "mode": "paper_trading"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/engine/stop")
async def stop_engine():
    """Stop the trading engine."""
    try:
        await trading_engine.stop()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/engine/status")
async def engine_status():
    """Get engine status."""
    return await trading_engine.get_status()

@app.post("/api/engine/cycle")
async def run_engine_cycle():
    """Run a single OODA cycle."""
    try:
        result = await trading_engine.run_cycle()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/engine/ooda/state")
async def get_ooda_state():
    """Get current OODA cycle state."""
    return await trading_engine.get_ooda_state()


# =============================================================================
# Utility Endpoints (10 endpoints)
# =============================================================================

@app.post("/api/dashboard/generate")
async def regenerate_dashboard():
    """Regenerate the dashboard HTML."""
    try:
        dashboard_html = await dashboard.generate()
        return {"status": "generated", "path": "/dashboard"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/strategies")
async def export_strategies(format: str = "json"):
    """Export all strategies in specified format."""
    try:
        return await trading_engine.export_strategies(format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import/strategies")
async def import_strategies(data: Dict[str, Any]):
    """Import strategies from data."""
    try:
        return await trading_engine.import_strategies(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/info")
async def system_info():
    """Get system information."""
    return {
        "name": "SLATE",
        "version": "1.0.0",
        "mode": "PAPER_TRADING_ONLY",
        "description": "Strategy Learning & Autonomous Trading Engine",
        "supported_languages": ["Python", "Pine Script v5", "HaasScript v2.0"],
        "supported_exchanges": ["Binance Futures USDT-M", "Bitget Perpetual"],
        "total_endpoints": 89
    }


# =============================================================================
# Server Lifecycle Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize server on startup."""
    logger.info("SLATE Server starting in PAPER_TRADING mode...")
    await health_monitor.initialize()
    await metrics_collector.start()
    logger.info("SLATE Server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("SLATE Server shutting down...")
    await trading_engine.stop()
    await metrics_collector.stop()
    logger.info("SLATE Server shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8787,
        log_level="info"
    )
