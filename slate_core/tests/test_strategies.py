"""
Tests for strategy management.
"""

import pytest
from slate_core.engine import TradingEngine, Signal


class TestTradingEngine:
    """Tests for trading engine."""

    def setup_method(self):
        self.engine = TradingEngine()

    @pytest.mark.asyncio
    async def test_create_strategy(self):
        """Test creating a new strategy."""
        strategy_id = await self.engine.create_strategy(
            name="Test Strategy",
            code="def run(): return 'long'",
            language="python"
        )

        assert strategy_id in self.engine.strategies
        assert self.engine.strategies[strategy_id]['name'] == "Test Strategy"

    @pytest.mark.asyncio
    async def test_activate_strategy(self):
        """Test activating a strategy."""
        strategy_id = await self.engine.create_strategy(
            name="Test Strategy",
            code="def run(): return 'long'",
            language="python"
        )

        await self.engine.activate_strategy(strategy_id)
        assert self.engine.strategies[strategy_id]['active'] is True

    @pytest.mark.asyncio
    async def test_run_ooda_cycle(self):
        """Test running a complete OODA cycle."""
        await self.engine.start()
        result = await self.engine.run_cycle()

        assert 'cycle_number' in result
        assert 'duration_seconds' in result
        assert result['cycle_number'] == 1

    @pytest.mark.asyncio
    async def test_paper_trading_only(self):
        """Test that engine never executes live trades."""
        await self.engine.start()

        # Run a cycle and verify it's paper trading
        result = await self.engine.run_cycle()

        # Check that any actions are marked as paper trading
        if result.get('action_result', {}).get('success'):
            assert 'paper' in str(result).lower()
