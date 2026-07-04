#!/usr/bin/env python3
"""
World-Class Strategy Discovery Engine

Rebuilt from scratch with proper quantitative finance principles:
- Market regime awareness and adaptation
- Proper risk management and position sizing
- Multiple strategy classes with proven edge
- Realistic signal generation and execution
- Robust validation and backtesting
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import sqlite3
import logging
from datetime import datetime
import json

from slate_core.discovery.world_class_strategies import (
    WorldClassQuantStrategies,
    MarketRegime,
    StrategyClass,
    StrategySignal,
    StrategyResult
)

logger = logging.getLogger(__name__)


class WorldClassDiscoveryEngine:
    """
    World-class strategy discovery engine.

    Built on principles from successful crypto trading firms:
    - Market regime awareness
    - Proper risk management
    - Multiple strategy classes
    - Proven edge in crypto markets
    """

    def __init__(self):
        self.quant_strategies = WorldClassQuantStrategies()
        self.db_path = 'slate_core/slate_realistic_discoveries.db'
        self.max_strategies_per_cycle = 50
        self.min_trades_required = 10
        self.min_win_rate = 0.45
        self.min_sharpe_ratio = 0.5
        self.max_drawdown_tolerance = 0.15

    def load_market_data(self) -> pd.DataFrame:
        """Load and prepare market data for strategy discovery"""
        try:
            with open('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv', 'r') as f:
                content = f.read()

            all_data = []
            for line in content.strip().split('\n'):
                if line.strip():
                    try:
                        data_list = json.loads(line.strip())
                        if isinstance(data_list, list):
                            all_data.extend(data_list)
                    except Exception:
                        continue

            df = pd.DataFrame(all_data)

            if 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp'])
            else:
                df['date'] = pd.to_datetime(df.iloc[:, 0])

            # Ensure we have OHLC data
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            if 'high' in df.columns:
                df['high'] = pd.to_numeric(df['high'], errors='coerce')
            else:
                df['high'] = df['close']  # Fallback to close

            if 'low' in df.columns:
                df['low'] = pd.to_numeric(df['low'], errors='coerce')
            else:
                df['low'] = df['close']  # Fallback to close

            if 'volume' in df.columns:
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

            df = df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)

            logger.info(f"Loaded {len(df)} data points for strategy discovery")
            return df

        except Exception as e:
            logger.error(f"Failed to load market data: {e}")
            return None

    def discover_regime_aware_strategies(self) -> Dict[str, StrategyResult]:
        """
        Discover regime-aware strategies with proper validation.
        """
        logger.info("Starting world-class strategy discovery...")

        df = self.load_market_data()
        if df is None or len(df) < 100:
            logger.error("Insufficient data for strategy discovery")
            return {}

        # Detect current market regime
        current_regime = self.quant_strategies.detect_market_regime(df)
        logger.info(f"Current market regime: {current_regime.value}")

        # Generate strategies for current regime
        discovered_strategies = {}

        # 1. Trend Following Strategies (only in trending markets)
        if current_regime in [MarketRegime.STRONG_BULL, MarketRegime.STRONG_BEAR]:
            logger.info("Generating trend-following strategies...")
            trend_signals = self.quant_strategies.generate_trend_following_signals(df, current_regime)
            if trend_signals:
                trend_result = self.quant_strategies.backtest_strategy_signals(df, trend_signals)
                discovered_strategies['trend_following'] = trend_result

        # 2. Mean Reversion Strategies (only in sideways markets)
        elif current_regime == MarketRegime.SIDEWAYS:
            logger.info("Generating mean reversion strategies...")
            mr_signals = self.quant_strategies.generate_mean_reversion_signals(df, current_regime)
            if mr_signals:
                mr_result = self.quant_strategies.backtest_strategy_signals(df, mr_signals)
                discovered_strategies['mean_reversion'] = mr_result

        # 3. Validate strategies before saving
        validated_strategies = {}
        for strategy_name, result in discovered_strategies.items():
            if self.validate_strategy(result):
                validated_strategies[strategy_name] = result
                logger.info(f"✅ {strategy_name} passed validation")
            else:
                logger.info(f"❌ {strategy_name} failed validation")

        return validated_strategies

    def validate_strategy(self, result: StrategyResult) -> bool:
        """
        Validate strategy meets world-class standards.

        Requirements:
        - Minimum trades: 10+ (statistical significance)
        - Win rate: 45%+ (reasonable success rate)
        - Sharpe ratio: 0.5+ (positive risk-adjusted returns)
        - Max drawdown: <15% (controlled risk)
        - Total return: Positive (actually profitable)
        """
        validation_checks = []

        # Trade frequency check
        has_enough_trades = result.total_trades >= self.min_trades_required
        validation_checks.append(('Trade Frequency', has_enough_trades, f"{result.total_trades} >= {self.min_trades_required}"))

        # Win rate check
        good_win_rate = result.win_rate >= self.min_win_rate
        validation_checks.append(('Win Rate', good_win_rate, f"{result.win_rate:.2f} >= {self.min_win_rate}"))

        # Risk-adjusted returns check
        good_sharpe = result.sharpe_ratio >= self.min_sharpe_ratio
        validation_checks.append(('Sharpe Ratio', good_sharpe, f"{result.sharpe_ratio:.2f} >= {self.min_sharpe_ratio}"))

        # Risk management check
        controlled_risk = result.max_drawdown <= self.max_drawdown_tolerance
        validation_checks.append(('Max Drawdown', controlled_risk, f"{result.max_drawdown:.2f} <= {self.max_drawdown_tolerance}"))

        # Profitability check
        is_profitable = result.total_return > 0
        validation_checks.append(('Profitability', is_profitable, f"{result.total_return:.4f} > 0"))

        # Log validation results
        for check_name, passed, details in validation_checks:
            status = "✅" if passed else "❌"
            logger.info(f"{status} {check_name}: {details}")

        # Strategy passes if all checks pass
        all_passed = all(check[1] for check in validation_checks)

        return all_passed

    def save_discovered_strategies(self, strategies: Dict[str, StrategyResult]) -> int:
        """
        Save validated strategies to database.
        """
        saved_count = 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for strategy_name, result in strategies.items():
                # Create strategy description
                strategy_desc = f"World-class {strategy_name} strategy"

                # Calculate metrics
                final_capital = self.quant_strategies.capital_base * (1 + result.total_return)
                total_return_pct = result.total_return

                # Determine beat_market (load fresh market data)
                try:
                    market_df = self.load_market_data()
                    if market_df is not None and len(market_df) > 1:
                        buy_hold_return = (market_df['close'].iloc[-1] / market_df['close'].iloc[0] - 1)
                    else:
                        buy_hold_return = 0
                except:
                    buy_hold_return = 0

                beat_market = 1 if total_return_pct > buy_hold_return else 0

                # Insert into database
                cursor.execute("""
                    INSERT INTO perpetual_discoveries (
                        strategy_name, strategy_description, edge_type, total_return_pct,
                        sharpe_ratio, win_rate, total_trades, max_drawdown_pct,
                        initial_capital, final_capital, beat_market,
                        passed_validation, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"world_class_{strategy_name}",
                    strategy_desc,
                    strategy_name,
                    total_return_pct,
                    result.sharpe_ratio,
                    result.win_rate,
                    result.total_trades,
                    result.max_drawdown,
                    self.quant_strategies.capital_base,
                    final_capital,
                    beat_market,
                    1,  # passed_validation
                    datetime.now().isoformat()
                ))

                saved_count += 1

            conn.commit()
            conn.close()

            logger.info(f"✅ Saved {saved_count} validated strategies to database")
            return saved_count

        except Exception as e:
            logger.error(f"Failed to save strategies: {e}")
            return 0

    def run_discovery_cycle(self) -> Dict[str, any]:
        """
        Run a complete discovery cycle with validation.
        """
        logger.info("🚀 Starting world-class discovery cycle")

        # Discover strategies
        strategies = self.discover_regime_aware_strategies()

        if not strategies:
            logger.warning("No strategies discovered or validated")
            return {
                'status': 'no_strategies',
                'strategies_discovered': 0,
                'strategies_validated': 0
            }

        # Save to database
        saved_count = self.save_discovered_strategies(strategies)

        result = {
            'status': 'success',
            'strategies_discovered': len(strategies),
            'strategies_validated': saved_count,
            'strategies': {name: {
                'total_trades': s.total_trades,
                'win_rate': s.win_rate,
                'sharpe_ratio': s.sharpe_ratio,
                'total_return': s.total_return
            } for name, s in strategies.items()}
        }

        logger.info(f"🎯 Discovery cycle complete: {saved_count} strategies validated and saved")
        return result


# Global instance
_discovery_engine: Optional[WorldClassDiscoveryEngine] = None


def get_world_class_discovery_engine() -> WorldClassDiscoveryEngine:
    """Get the global world-class discovery engine instance."""
    global _discovery_engine
    if _discovery_engine is None:
        _discovery_engine = WorldClassDiscoveryEngine()
    return _discovery_engine