"""
SLATE Strategy Implementations

Concrete trading strategy implementations for the SLATE discovery system.
Each strategy follows the AdaptiveRegimeSwitchingStrategy pattern and implements
the generate_signal(df, i, params) -> int interface.

Available Strategies:
- MomentumStrategy: EMA crossover momentum strategy for trending markets
- MeanReversionStrategy: Bollinger Bands + RSI for ranging markets
- BreakoutStrategy: Volatility breakout strategy
- FundingArbitrageStrategy: Perpetual futures funding rate arbitrage
"""

from slate_core.discovery.strategies.momentum_strategy import MomentumStrategy
from slate_core.discovery.strategies.mean_reversion_strategy import MeanReversionStrategy
from slate_core.discovery.strategies.breakout_strategy import BreakoutStrategy
from slate_core.discovery.strategies.funding_arbitrage_strategy import FundingArbitrageStrategy
from slate_core.discovery.strategies.strategy_factory import StrategyFactory

__all__ = [
    'MomentumStrategy',
    'MeanReversionStrategy',
    'BreakoutStrategy',
    'FundingArbitrageStrategy',
    'StrategyFactory',
]
