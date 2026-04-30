#!/usr/bin/env python3
"""
SLATE Integration Tests

Comprehensive tests that verify all SLATE components work together.
These tests ensure the system can operate autonomously when needed.

Run with: python3 -m pytest slate_core/test_integration.py -v
Or: python3 slate_core/test_integration.py
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSLATEIntegration:
    """Integration tests for complete SLATE system."""

    def test_slate_module_imports(self):
        """Test that all SLATE modules can be imported."""
        from slate_core import __version__, __mode__
        assert __version__ == "1.0.0"
        assert __mode__ == "PAPER_TRADING_ONLY"

    def test_config_system(self):
        """Test configuration system works correctly."""
        from slate_core.config import get_config

        config = get_config()

        # Verify paper trading mode
        assert config.trading_mode == "paper"
        assert config.port == 8788

        # Verify paths are correct
        assert "slate_core/palace_data" in config.graphpalace_path

    def test_language_compilers(self):
        """Test that language compilers work bidirectionally."""
        from slate_core.languages.haas_script import HaasScriptCrossCompiler
        from slate_core.languages.pine_script import PineScriptCrossCompiler

        # Test HaasScript compiler
        haas_compiler = HaasScriptCrossCompiler()

        # Python to HaasScript
        python_code = "price = prices[0]"
        haas_code = haas_compiler.python_to_haasscript(python_code)
        assert "IndexArray" in haas_code

        # HaasScript to Python
        haas_input = "price = IndexArray(prices, 1)"
        python_output = haas_compiler.haasscript_to_python(haas_input)
        assert "prices[0]" in python_output

        # Test Pine Script compiler
        pine_compiler = PineScriptCrossCompiler()

        # Python to Pine Script
        pine_code = pine_compiler.python_to_pine_script(python_code)
        assert "pine" in pine_code.lower()

    def test_connectors_paper_trading(self):
        """Test that all connectors enforce paper trading mode."""
        from slate_core.connectors.binance import BinanceConnector
        from slate_core.connectors.bitget import BitgetConnector

        # Test Binance connector
        binance = BinanceConnector()
        assert binance.mode == "paper_trading"

        # Test Bitget connector
        bitget = BitgetConnector()
        assert bitget.mode == "paper_trading"

    def test_discovery_components(self):
        """Test that discovery system components work."""
        from slate_core.discovery.realistic_backtester import (
            BacktestConfig,
            BacktestResult,
            HistoricalDataArchive
        )

        # Test backtest configuration
        config = BacktestConfig(
            initial_capital=10000.0,
            maker_fee=0.0002,
            taker_fee=0.0005,
            slippage_bps=5,
            fill_rate=0.95
        )

        assert config.initial_capital == 10000.0
        assert config.maker_fee == 0.0002

        # Test historical data archive
        archive = HistoricalDataArchive()
        assert archive.archive_dir is not None

    def test_risk_management(self):
        """Test that risk management system works."""
        from slate_core.risk.manager import RiskManager

        risk_mgr = RiskManager()

        # Test that risk manager is initialized
        assert risk_mgr is not None

        # Test Kelly Criterion calculation (async method)
        # We'll just verify the method exists
        assert hasattr(risk_mgr, 'kelly_criterion')

    @pytest.mark.asyncio
    async def test_data_fetcher(self):
        """Test that data fetcher works correctly."""
        from slate_core.data.fetcher import HistoricalDataFetcher

        fetcher = HistoricalDataFetcher()

        # Test get_candles method
        candles = await fetcher.get_candles("BTCUSDT", "1h", 10)

        assert isinstance(candles, list)
        assert len(candles) > 0

        # Check candle structure
        candle = candles[0]
        assert "timestamp" in candle or "close" in candle

    @pytest.mark.asyncio
    async def test_trading_engine_cycle(self):
        """Test that trading engine can complete OODA cycle."""
        from slate_core.engine import TradingEngine

        engine = TradingEngine()

        # Start engine
        await engine.start()

        # Run one cycle
        result = await engine.run_cycle()

        # Verify result structure
        assert "cycle_number" in result
        assert "duration_seconds" in result
        assert "observation" in result
        assert "decision" in result
        assert "action_result" in result

        # Verify paper trading mode
        assert result["action_result"].get("paper_trading") is True

        # Stop engine
        await engine.stop()

    def test_database_paths(self):
        """Test that database paths are correctly configured."""
        from pathlib import Path
        import slate_core.discovery.realistic_backtester as rb
        import slate_core.discovery.realistic_memory as rm
        import slate_core.discovery.tiered_storage as ts

        # Check that archive path points to slate_core directory
        archive = rb.HistoricalDataArchive()
        assert "slate_core" in str(archive.archive_dir)

        # Check that memory path points to slate_core directory
        memory = rm.RealisticDiscoveryMemory()
        assert "slate_core" in memory.db_path

        # Check that storage path points to slate_core directory
        storage = ts.TieredDiscoveryStorage()
        assert "slate_core" in storage.db_path


class TestSLATEAutonomy:
    """Tests for autonomous operation capabilities."""

    def test_self_evolution_setup(self):
        """Test that self-evolution components are available."""
        from slate_core.discovery.self_evolving import SelfEvolvingDiscoveryEngine
        from slate_core.discovery.stigmergic_coordinator import StigmergicCoordinator

        # These should be importable and ready to use
        assert SelfEvolvingDiscoveryEngine is not None
        assert StigmergicCoordinator is not None

    def test_continuous_discovery_setup(self):
        """Test that continuous discovery is configured."""
        from slate_core.discovery.continuous_discovery import ContinuousDiscoveryScheduler

        # Should be able to create instance
        discovery = ContinuousDiscoveryScheduler()
        assert discovery is not None

    def test_multi_objective_optimization(self):
        """Test that multi-objective optimization works."""
        from slate_core.discovery.multi_objective import MultiObjectiveOptimizer

        optimizer = MultiObjectiveOptimizer()

        # Test optimization
        strategies = [
            {"id": "s1", "sharpe": 1.5, "drawdown": 0.1, "return": 0.2},
            {"id": "s2", "sharpe": 2.0, "drawdown": 0.15, "return": 0.25},
            {"id": "s3", "sharpe": 1.2, "drawdown": 0.05, "return": 0.15},
        ]

        result = optimizer.optimize(strategies)
        assert len(result) > 0


def run_standalone_tests():
    """Run tests when script is executed directly."""
    print("\n" + "="*60)
    print("SLATE Integration Tests")
    print("="*60 + "\n")

    # Run basic tests
    test = TestSLATEIntegration()

    tests = [
        ("Module Imports", test.test_slate_module_imports),
        ("Config System", test.test_config_system),
        ("Language Compilers", test.test_language_compilers),
        ("Connectors Paper Trading", test.test_connectors_paper_trading),
        ("Discovery Components", test.test_discovery_components),
        ("Risk Management", test.test_risk_management),
        ("Database Paths", test.test_database_paths),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1

    # Run async tests
    async_tests = [
        ("Data Fetcher", test.test_data_fetcher),
        ("Trading Engine Cycle", test.test_trading_engine_cycle),
    ]

    async def run_async_tests():
        nonlocal passed, failed
        for name, test_func in async_tests:
            try:
                await test_func()
                print(f"✓ {name}")
                passed += 1
            except Exception as e:
                print(f"✗ {name}: {e}")
                failed += 1

    # Run async tests
    asyncio.run(run_async_tests())

    # Run autonomy tests
    autonomy = TestSLATEAutonomy()

    autonomy_tests = [
        ("Self-Evolution Setup", autonomy.test_self_evolution_setup),
        ("Continuous Discovery Setup", autonomy.test_continuous_discovery_setup),
        ("Multi-Objective Optimization", autonomy.test_multi_objective_optimization),
    ]

    for name, test_func in autonomy_tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_standalone_tests()
    sys.exit(0 if success else 1)
