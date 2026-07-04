#!/usr/bin/env python3
"""
Perpetual Futures Discovery Integration for SLATE

Connects the perpetual futures backtesting engine to the swarm discovery system.
This replaces the old spot-based discovery with perpetual futures-specific logic.
"""

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from .perpetual_futures_backtest import (
    PerpetualFuturesBacktester,
    PerpetualBacktestConfig,
    PerpetualBacktestResult,
    example_ema_crossover_signal
)
from .perpetual_database import PerpetualDatabaseManager

logger = logging.getLogger(__name__)


class PerpetualDiscoveryIntegration:
    """
    Integration layer for perpetual futures discovery.

    This class bridges the gap between:
    1. Swarm intelligence agents (generating strategy candidates)
    2. Perpetual futures backtesting (realistic validation)
    3. Database storage (persistent results)
    """

    def __init__(self):
        self.backtester = PerpetualFuturesBacktester()
        self.db_manager = PerpetualDatabaseManager()
        self.data_cache = {}

        logger.info("Perpetual Discovery Integration initialized")

    async def load_12m_data(self) -> Optional[pd.DataFrame]:
        """Load 6 months of perpetual futures data (4,182 data points)."""
        cache_file = Path("sol_data_cache/SOLUSDT_perpetual_1d_6m_full.csv")

        if not cache_file.exists():
            logger.error("12-month data file not found. Run fetch_binance_futures.py first")
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

            # Convert numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'atr',
                          'atr_ratio', 'rsi', 'macd', 'macd_signal', 'macd_hist',
                          'bollinger_upper', 'bollinger_lower', 'bollinger_width',
                          'sma_20', 'std_20', 'funding_rate', 'volume_ratio']

            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # CRITICAL FIX: Resample hourly data to daily timeframe
            # The data file contains hourly data, but our strategies require daily timeframe
            # (where 97.5% of profitable strategies exist)
            logger.info(f"🔄 Resampling {len(df)} hourly data points to daily timeframe...")

            # OHLC resampling for price data
            ohlc_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }

            # For indicators, take the last value of the day
            indicator_cols = ['atr', 'atr_ratio', 'rsi', 'macd', 'macd_signal', 'macd_hist',
                            'bollinger_upper', 'bollinger_lower', 'bollinger_width',
                            'sma_20', 'std_20', 'funding_rate', 'volume_ratio',
                            'ema_7', 'ema_10', 'ema_14', 'ema_17', 'ema_20',
                            'ema_33', 'ema_36', 'ema_50', 'ema_68', 'ema_72', 'ema_200']

            for col in indicator_cols:
                if col in df.columns:
                    ohlc_dict[col] = 'last'

            # Resample to daily
            df_daily = df.resample('1D').agg(ohlc_dict).dropna()

            logger.info(f"✓ Loaded {len(df_daily)} daily candles from 6-month perpetual futures data")
            logger.info(f"Period: {df_daily.index[0]} to {df_daily.index[-1]}")
            logger.info(f"Price range: ${df_daily['close'].iloc[0]:.2f} -> ${df_daily['close'].iloc[-1]:.2f}")

            return df_daily

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return None

    def generate_strategy_from_agent(self, agent_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert swarm agent parameters into a strategy for backtesting.

        Args:
            agent_params: Parameters from swarm agent (fast_period, slow_period, etc.)

        Returns:
            Strategy configuration for backtesting
        """
        strategy_type = agent_params.get('edge_type', 'momentum_mean_reversion')

        # Generate strategy description
        fast_period = agent_params.get('fast_period', 10)
        slow_period = agent_params.get('slow_period', 20)
        signal_threshold = agent_params.get('signal_threshold', 0.5)
        position_size = agent_params.get('position_size', 0.03)

        strategy_name = f"{strategy_type}_ema_{fast_period}_{slow_period}"
        strategy_description = (
            f"EMA Crossover ({strategy_type}): Fast={fast_period}, Slow={slow_period}, "
            f"Threshold={signal_threshold:.2f}, Size={position_size:.1%}"
        )

        return {
            'strategy_name': strategy_name,
            'strategy_description': strategy_description,
            'edge_type': strategy_type,
            'parameters': agent_params,
            'signal_function': self._create_signal_function(strategy_type, agent_params)
        }

    def _create_signal_function(self, strategy_type: str, params: Dict[str, Any]):
        """Create a signal function based on strategy type with regime-aware strategies."""

        def signal_function(df: pd.DataFrame, i: int, parameters: Dict[str, Any]) -> int:
            """Generate trading signals for perpetual futures with regime awareness."""

            # Import regime-aware strategies
            try:
                from slate_core.discovery.regime_aware_strategies import (
                    bollinger_mean_reversion_signal,
                    rsi_extremes_signal,
                    support_resistance_signal,
                    enhanced_ema_signal,
                    statistical_arbitrage_signal,
                    volatility_breakout_signal
                )

                # Map strategy types to signal functions
                strategy_mapping = {
                    # NEW: Regime-aware strategies
                    'bollinger_mean_reversion': bollinger_mean_reversion_signal,
                    'rsi_extremes': rsi_extremes_signal,
                    'support_resistance': support_resistance_signal,
                    'enhanced_ema': enhanced_ema_signal,
                    'statistical_arbitrage': statistical_arbitrage_signal,
                    'volatility_breakout': volatility_breakout_signal,

                    # EXISTING: Legacy strategies (kept for compatibility)
                    'momentum_mean_reversion': self._ema_crossover_signal,
                    'volatility_regime': self._bollinger_signal,
                    'market_microstructure': self._rsi_signal,
                }

                if strategy_type in strategy_mapping:
                    return strategy_mapping[strategy_type](df, i, parameters)
                else:
                    # Default to enhanced EMA for unknown types
                    return enhanced_ema_signal(df, i, parameters)

            except Exception as e:
                logger.error(f"Error in signal function: {e}")
                return self._default_signal(df, i, parameters)

        return signal_function

    def _ema_crossover_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
        """EMA crossover signal for perpetual futures."""
        fast_period = int(params.get('fast_period', 10))
        slow_period = int(params.get('slow_period', 20))

        fast_col = f"ema_{fast_period}"
        slow_col = f"ema_{slow_period}"

        if fast_col not in df.columns or slow_col not in df.columns:
            return 0

        if i < 1:
            return 0

        # Golden cross (long signal)
        if df.iloc[i][fast_col] > df.iloc[i][slow_col]:
            if df.iloc[i-1][fast_col] <= df.iloc[i-1][slow_col]:
                return 1  # LONG

        # Death cross (short signal)
        elif df.iloc[i][fast_col] < df.iloc[i][slow_col]:
            if df.iloc[i-1][fast_col] >= df.iloc[i-1][slow_col]:
                return -1  # SHORT

        return 0

    def _bollinger_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
        """Bollinger band mean reversion signal."""
        if i < 1:
            return 0

        current_close = df.iloc[i]['close']
        upper_band = df.iloc[i]['bollinger_upper']
        lower_band = df.iloc[i]['bollinger_lower']
        rsi = df.iloc[i]['rsi']

        # Short at upper band (overbought)
        if current_close >= upper_band * 0.98 and rsi > 70:
            return -1  # SHORT

        # Long at lower band (oversold)
        elif current_close <= lower_band * 1.02 and rsi < 30:
            return 1  # LONG

        return 0

    def _rsi_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
        """RSI extremities signal."""
        if i < 1:
            return 0

        rsi = df.iloc[i]['rsi']

        # Overbought - short
        if rsi > 70:
            return -1  # SHORT

        # Oversold - long
        elif rsi < 30:
            return 1  # LONG

        return 0

    def _default_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
        """Default trend-following signal."""
        if i < 1:
            return 0

        ema_20 = df.iloc[i]['ema_20']
        ema_50 = df.iloc[i]['ema_50']
        rsi = df.iloc[i]['rsi']

        # Uptrend with pullback - long
        if ema_20 > ema_50 and 30 < rsi < 70:
            return 1  # LONG

        # Downtrend with rally - short
        elif ema_20 < ema_50 and 30 < rsi < 70:
            return -1  # SHORT

        return 0

    async def backtest_strategy(
        self,
        df: pd.DataFrame,
        strategy_config: Dict[str, Any]
    ) -> Optional[PerpetualBacktestResult]:
        """
        Run perpetual futures backtest on a strategy.

        Args:
            df: 12-month price data
            strategy_config: Strategy configuration

        Returns:
            Backtest result or None if failed
        """
        try:
            result = self.backtester.backtest_strategy(
                df=df,
                strategy_name=strategy_config['strategy_name'],
                strategy_description=strategy_config['strategy_description'],
                edge_type=strategy_config['edge_type'],
                signal_function=strategy_config['signal_function'],
                parameters=strategy_config['parameters']
            )

            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return None

    def save_result(self, result: PerpetualBacktestResult) -> bool:
        """
        Save backtest result to database.

        CRITICAL FIX: Map all 47 PerpetualBacktestResult fields to database columns correctly.
        """
        try:
            logger.debug(f"💾 Saving result: {result.strategy_name}")

            # Map all fields correctly to match database schema (48 columns excluding id)
            result_dict = {
                # Strategy identification (3)
                'strategy_name': result.strategy_name,
                'strategy_description': result.strategy_description,
                'edge_type': result.edge_type,

                # PRIMARY METRICS (4)
                'total_profit_usdt': result.total_profit_usdt,
                'total_return_pct': result.total_return_pct,
                'final_capital': result.final_capital,
                'initial_capital': result.initial_capital,

                # Baseline comparison (4)
                'buy_hold_profit_usdt': result.buy_hold_profit_usdt,
                'buy_hold_return_pct': result.buy_hold_return_pct,
                'vs_buy_hold_usdt': result.vs_buy_hold_usdt,
                'beat_market': result.beat_market,

                # Risk metrics (5)
                'max_drawdown_pct': result.max_drawdown_pct,
                'max_drawdown_usdt': result.max_drawdown_usdt,
                'sharpe_ratio': result.sharpe_ratio,
                'sortino_ratio': result.sortino_ratio if hasattr(result, 'sortino_ratio') else 0,
                'calmar_ratio': result.calmar_ratio if hasattr(result, 'calmar_ratio') else 0,

                # Trading statistics (10)
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor if hasattr(result, 'profit_factor') else 0,
                'avg_trade_pnl_usdt': result.avg_trade_pnl_usdt if hasattr(result, 'avg_trade_pnl_usdt') else 0,
                'avg_win_usdt': result.avg_win_usdt if hasattr(result, 'avg_win_usdt') else 0,
                'avg_loss_usdt': result.avg_loss_usdt if hasattr(result, 'avg_loss_usdt') else 0,
                'largest_win_usdt': result.largest_win_usdt if hasattr(result, 'largest_win_usdt') else 0,
                'largest_loss_usdt': result.largest_loss_usdt if hasattr(result, 'largest_loss_usdt') else 0,

                # Perpetual-specific metrics (4)
                'total_funding_paid_usdt': result.total_funding_paid_usdt,
                'total_funding_received_usdt': result.total_funding_received_usdt,
                'net_funding_usdt': result.net_funding_usdt,
                'avg_funding_daily_usdt': result.avg_funding_daily_usdt,

                # Cost breakdown (3)
                'total_fees_usdt': result.total_fees_usdt,
                'total_slippage_usdt': result.total_slippage_usdt,
                'total_transaction_costs_usdt': result.total_transaction_costs_usdt,

                # Realism metrics (4)
                'avg_slippage_bps': result.avg_slippage_bps if hasattr(result, 'avg_slippage_bps') else 0,
                'avg_fill_rate': result.avg_fill_rate if hasattr(result, 'avg_fill_rate') else 0,
                'total_signals': result.total_signals,
                'filled_signals': result.filled_signals,
                'partial_fills': result.partial_fills,

                # Market data (6)
                'period_start': result.period_start,
                'period_end': result.period_end,
                'start_price': result.start_price,
                'end_price': result.end_price,
                'volatility_regime': result.volatility_regime if hasattr(result, 'volatility_regime') else 'unknown',
                'timeframe': result.timeframe,

                # Validation (2)
                'passed_validation': result.passed_validation,
                'validation_failures': result.validation_failures,

                # Metadata (2) - timestamp is required
                'timestamp': result.timestamp,
            }

            # Calculate rank score (CRITICAL: USDT profit is PRIMARY, accounting for all costs)
            rank_score = (
                result_dict['total_profit_usdt'] * 1.0 -  # Actual USDT profit after ALL costs
                result_dict['max_drawdown_usdt'] * 0.5 +   # Penalize drawdown
                (result_dict['vs_buy_hold_usdt'] if result_dict['beat_market'] else 0) * 0.3  # Bonus for beating market
            )
            result_dict['rank_score'] = rank_score

            success = self.db_manager.save_discovery(result_dict)

            if success:
                logger.info(f"✅ Saved: {result.strategy_name} | Profit: ${result.total_profit_usdt:.2f} | Validated: {result.passed_validation} | Costs: ${result.total_transaction_costs_usdt:.2f}")
            else:
                logger.error(f"❌ Failed to save: {result.strategy_name}")

            return success

        except Exception as e:
            logger.error(f"❌ Exception in save_result: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def process_agent_batch(
        self,
        agent_params_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process a batch of agent parameters through perpetual futures backtesting.

        CRITICAL FIX: Save ALL results to database, including failures.
        This ensures we can track what's being tested and why things fail.

        Args:
            agent_params_list: List of agent parameter dictionaries

        Returns:
            Summary of results
        """
        # Load data once
        df = await self.load_12m_data()
        if df is None:
            logger.error("❌ Failed to load 12-month data")
            return {'status': 'error', 'message': 'Failed to load data'}

        logger.info(f"🔄 Processing {len(agent_params_list)} agent parameters")

        results = []
        passed_validation = 0
        failed_validation = 0
        total_profit = 0
        save_errors = 0

        for i, agent_params in enumerate(agent_params_list):
            try:
                # Generate strategy
                strategy_config = self.generate_strategy_from_agent(agent_params)

                # Run backtest
                result = await self.backtest_strategy(df, strategy_config)

                if result is None:
                    logger.warning(f"⚠️ Strategy {i+1}/{len(agent_params_list)} returned None result")
                    failed_validation += 1
                    continue

                # CRITICAL FIX: Save ALL results to database, not just passed ones
                save_success = self.save_result(result)
                if not save_success:
                    save_errors += 1
                    logger.error(f"❌ Failed to save strategy: {result.strategy_name}")

                # Track statistics regardless of validation outcome
                if result.passed_validation:
                    passed_validation += 1
                    total_profit += result.total_profit_usdt
                    results.append({
                        'strategy_name': result.strategy_name,
                        'profit_usdt': result.total_profit_usdt,
                        'return_pct': result.total_return_pct,
                        'beat_market': result.beat_market,
                        'total_costs_usdt': result.total_transaction_costs_usdt,
                        'net_funding_usdt': result.net_funding_usdt
                    })
                else:
                    failed_validation += 1
                    # Log why it failed
                    if result.validation_failures:
                        logger.debug(f"Strategy failed validation: {result.validation_failures}")

            except Exception as e:
                logger.error(f"❌ Failed to process agent {i+1}/{len(agent_params_list)}: {e}")
                failed_validation += 1
                continue

        logger.info(f"✅ Batch processing complete:")
        logger.info(f"  Total Tested: {len(agent_params_list)}")
        logger.info(f"  Passed: {passed_validation}")
        logger.info(f"  Failed: {failed_validation}")
        logger.info(f"  Save Errors: {save_errors}")
        logger.info(f"  Total Profit: ${total_profit:.2f}")

        return {
            'status': 'success',
            'total_tested': len(agent_params_list),
            'passed_validation': passed_validation,
            'failed_validation': failed_validation,
            'save_errors': save_errors,
            'total_profit_usdt': total_profit,
            'results': results
        }


# Singleton instance
_perpetual_integration = None

def get_perpetual_integration() -> PerpetualDiscoveryIntegration:
    """Get the singleton perpetual discovery integration instance."""
    global _perpetual_integration
    if _perpetual_integration is None:
        _perpetual_integration = PerpetualDiscoveryIntegration()
    return _perpetual_integration


if __name__ == "__main__":
    # Test the integration
    print("Testing Perpetual Discovery Integration...")

    async def test():
        integration = get_perpetual_integration()

        # Test parameters (simulating swarm agent output)
        test_params = [
            {
                'edge_type': 'momentum_mean_reversion',
                'fast_period': 10,
                'slow_period': 20,
                'signal_threshold': 0.5,
                'position_size': 0.03
            },
            {
                'edge_type': 'volatility_regime',
                'fast_period': 14,
                'slow_period': 28,
                'signal_threshold': 0.6,
                'position_size': 0.025
            }
        ]

        results = await integration.process_agent_batch(test_params)
        print(f"\n✓ Integration test complete:")
        print(f"  Status: {results['status']}")
        print(f"  Tested: {results['total_tested']}")
        print(f"  Passed: {results['passed_validation']}")
        print(f"  Total Profit: ${results.get('total_profit_usdt', 0):.2f}")

    asyncio.run(test())