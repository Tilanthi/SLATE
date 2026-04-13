"""
SLATE Strategy Generator

Generates new trading strategies using 5 discovery methods.
"""

import logging
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import copy

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """
    Generate new trading strategies using various discovery methods.

    Methods:
    1. Parameter Variation - Vary parameters of existing strategies
    2. Signal Combination - Combine multiple signals
    3. Regime-Specific - Strategies for different market regimes
    4. Ensemble Generation - Create ensemble strategies
    5. Pattern Recognition - Discover chart patterns
    """

    # Base strategy templates
    BASE_STRATEGIES = {
        "rsi_reversal": {
            "name": "RSI Reversal",
            "type": "mean_reversion",
            "parameters": {
                "rsi_period": 14,
                "oversold": 30,
                "overbought": 70
            },
            "code_template": "rsi_reversal"
        },
        "macd_trend": {
            "name": "MACD Trend",
            "type": "trend_following",
            "parameters": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            },
            "code_template": "macd_trend"
        },
        "bollinger_breakout": {
            "name": "Bollinger Breakout",
            "type": "breakout",
            "parameters": {
                "period": 20,
                "std_dev": 2.0
            },
            "code_template": "bollinger_breakout"
        }
    }

    def __init__(self):
        self.generation_counter = 0

    async def generate_strategies(
        self,
        methods: List[str],
        count: int = 10
    ) -> List[Dict]:
        """Generate strategies using specified methods."""
        generated = []

        for method in methods:
            method_count = count // len(methods)

            if method == "parameter_variation":
                generated.extend(await self._parameter_variation(method_count))
            elif method == "signal_combination":
                generated.extend(await self._signal_combination(method_count))
            elif method == "regime_specific":
                generated.extend(await self._regime_specific(method_count))
            elif method == "ensemble_generation":
                generated.extend(await self._ensemble_generation(method_count))
            elif method == "pattern_recognition":
                generated.extend(await self._pattern_recognition(method_count))

        return generated[:count]

    async def _parameter_variation(self, count: int) -> List[Dict]:
        """Vary parameters of existing strategies."""
        strategies = []

        for _ in range(count):
            # Select random base strategy
            base_name = random.choice(list(self.BASE_STRATEGIES.keys()))
            base = copy.deepcopy(self.BASE_STRATEGIES[base_name])

            # Vary parameters
            for param, value in base["parameters"].items():
                if isinstance(value, int):
                    # Vary by ±30%
                    variation = random.uniform(0.7, 1.3)
                    base["parameters"][param] = int(value * variation)
                elif isinstance(value, float):
                    variation = random.uniform(0.8, 1.2)
                    base["parameters"][param] = round(value * variation, 2)

            strategies.append({
                "id": f"param_var_{self.generation_counter}",
                "name": f"{base['name']} (Var)",
                "discovery_method": "parameter_variation",
                "base_strategy": base_name,
                "parameters": base["parameters"],
                "type": base["type"],
                "generated_at": datetime.now().isoformat()
            })

            self.generation_counter += 1

        logger.info(f"Generated {len(strategies)} parameter variation strategies")
        return strategies

    async def _signal_combination(self, count: int) -> List[Dict]:
        """Combine multiple signals."""
        strategies = []

        signal_types = ["RSI", "MACD", "BB", "EMA", "ADX"]

        for _ in range(count):
            # Select 2-3 random signals
            num_signals = random.choice([2, 3])
            signals = random.sample(signal_types, num_signals)

            strategies.append({
                "id": f"signal_comb_{self.generation_counter}",
                "name": f"{'-'.join(signals)} Combo",
                "discovery_method": "signal_combination",
                "signals": signals,
                "logic": "all" if random.random() > 0.5 else "majority",
                "type": "multi_signal",
                "parameters": {
                    "require_all": True,
                    "min_signals": num_signals
                },
                "generated_at": datetime.now().isoformat()
            })

            self.generation_counter += 1

        logger.info(f"Generated {len(strategies)} signal combination strategies")
        return strategies

    async def _regime_specific(self, count: int) -> List[Dict]:
        """Create strategies for specific market regimes."""
        strategies = []

        regimes = ["bull_volatile", "bull_stable", "bear_volatile", "bear_stable", "ranging"]

        for _ in range(count):
            regime = random.choice(regimes)

            # Adapt strategy to regime
            if "bull" in regime:
                strategy_type = "trend_following"
            elif "bear" in regime:
                strategy_type = "mean_reversion"
            else:
                strategy_type = "range_trading"

            strategies.append({
                "id": f"regime_{self.generation_counter}",
                "name": f"{regime.replace('_', ' ').title()} Strategy",
                "discovery_method": "regime_specific",
                "target_regime": regime,
                "type": strategy_type,
                "parameters": self._get_regime_parameters(regime),
                "generated_at": datetime.now().isoformat()
            })

            self.generation_counter += 1

        logger.info(f"Generated {len(strategies)} regime-specific strategies")
        return strategies

    async def _ensemble_generation(self, count: int) -> List[Dict]:
        """Create ensemble strategies."""
        strategies = []

        base_names = list(self.BASE_STRATEGIES.keys())

        for _ in range(count):
            # Select 2-4 base strategies
            num_strategies = random.choice([2, 3, 4])
            components = random.sample(base_names, num_strategies)

            strategies.append({
                "id": f"ensemble_{self.generation_counter}",
                "name": f"{num_strategies}-Strategy Ensemble",
                "discovery_method": "ensemble_generation",
                "components": components,
                "aggregation": random.choice(["weighted_vote", "unanimous", "consensus"]),
                "type": "ensemble",
                "parameters": {
                    "weights": [random.uniform(0.2, 0.5) for _ in components]
                },
                "generated_at": datetime.now().isoformat()
            })

            self.generation_counter += 1

        logger.info(f"Generated {len(strategies)} ensemble strategies")
        return strategies

    async def _pattern_recognition(self, count: int) -> List[Dict]:
        """Discover chart pattern strategies."""
        strategies = []

        patterns = [
            "double_bottom", "double_top",
            "head_and_shoulders", "inverse_head_and_shoulders",
            "triangle", "wedge", "flag"
        ]

        for _ in range(count):
            pattern = random.choice(patterns)

            strategies.append({
                "id": f"pattern_{self.generation_counter}",
                "name": f"{pattern.replace('_', ' ').title()}",
                "discovery_method": "pattern_recognition",
                "pattern": pattern,
                "type": "pattern",
                "parameters": {
                    "lookback_periods": random.randint(20, 50),
                    "confirmation_required": True
                },
                "generated_at": datetime.now().isoformat()
            })

            self.generation_counter += 1

        logger.info(f"Generated {len(strategies)} pattern recognition strategies")
        return strategies

    def _get_regime_parameters(self, regime: str) -> Dict:
        """Get parameters optimized for a specific regime."""
        if regime == "bull_volatile":
            return {
                "risk_per_trade": 0.03,
                "use_trailing_stop": True,
                "trailing_stop_pct": 0.02
            }
        elif regime == "bull_stable":
            return {
                "risk_per_trade": 0.02,
                "use_trailing_stop": False,
                "take_profit_pct": 0.05
            }
        elif regime == "bear_volatile":
            return {
                "risk_per_trade": 0.015,
                "use_shorts": True,
                "stop_loss_pct": 0.02
            }
        elif regime == "bear_stable":
            return {
                "risk_per_trade": 0.02,
                "use_shorts": True,
                "take_profit_pct": 0.04
            }
        else:  # ranging
            return {
                "risk_per_trade": 0.01,
                "mean_reversion": True,
                "range_entry_pct": 0.02
            }
