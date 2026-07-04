#!/usr/bin/env python3
"""
Regime-Aware Agent Strategy Mapping

Maps existing swarm agents to regime-aware strategies based on market conditions.
This allows the swarm to automatically use appropriate strategies for current regime.

Author: SLATE Architecture Enhancement
Date: 2026-07-03
"""

from slate_core.discovery.regime_aware_strategies import STRATEGY_REGISTRY


# Map agent types to appropriate strategies based on regime
AGENT_STRATEGY_MAPPING = {
    'regime_detector': {
        'sideways': ['bollinger_mean_reversion', 'rsi_extremes', 'support_resistance'],
        'trending': ['enhanced_ema', 'volatility_breakout'],
        'volatile': ['volatility_breakout', 'statistical_arbitrage'],
        'default': ['statistical_arbitrage']
    },
    'pattern_discoverer': {
        'sideways': ['bollinger_mean_reversion', 'support_resistance'],
        'trending': ['enhanced_ema'],
        'volatile': ['volatility_breakout'],
        'default': ['bollinger_mean_reversion']
    },
    'parameter_explorer': {
        'sideways': ['enhanced_ema', 'bollinger_mean_reversion'],
        'trending': ['enhanced_ema'],
        'volatile': ['volatility_breakout', 'enhanced_ema'],
        'default': ['enhanced_ema']
    },
    'cross_timeframe_analyst': {
        'sideways': ['support_resistance', 'statistical_arbitrage'],
        'trending': ['enhanced_ema'],
        'volatile': ['volatility_breakout'],
        'default': ['statistical_arbitrage']
    },
    'experimental_strategist': {
        'sideways': ['bollinger_mean_reversion', 'rsi_extremes', 'statistical_arbitrage'],
        'trending': ['enhanced_ema', 'volatility_breakout'],
        'volatile': ['volatility_breakout', 'statistical_arbitrage'],
        'default': ['statistical_arbitrage']
    }
}


def get_strategies_for_agent(agent_type: str, current_regime: str = 'sideways') -> list:
    """
    Get appropriate strategies for a given agent type and market regime.

    Args:
        agent_type: Type of swarm agent
        current_regime: Current market regime (sideways, trending, volatile)

    Returns:
        List of strategy names to use
    """
    if agent_type not in AGENT_STRATEGY_MAPPING:
        # Default to statistical arbitrage for unknown agents
        return ['statistical_arbitrage']

    regime_strategies = AGENT_STRATEGY_MAPPING[agent_type]

    # Use regime-specific strategies if available
    if current_regime in regime_strategies:
        return regime_strategies[current_regime]

    # Fall back to default
    return regime_strategies.get('default', ['statistical_arbitrage'])


def transform_agent_parameters(agent_params: dict, current_regime: str = 'sideways') -> dict:
    """
    Transform agent parameters to use regime-appropriate strategies.

    This modifies the agent_params to replace edge_type with appropriate
    regime-aware strategy types.

    Args:
        agent_params: Original agent parameters
        current_regime: Current market regime

    Returns:
        Modified parameters with regime-aware strategy types
    """
    agent_type = agent_params.get('agent_type', 'parameter_explorer')
    original_edge_type = agent_params.get('edge_type', 'momentum_mean_reversion')

    # Get appropriate strategies for this agent and regime
    strategies = get_strategies_for_agent(agent_type, current_regime)

    # Use the first appropriate strategy (could rotate through them)
    new_edge_type = strategies[0]

    # Create modified parameters
    modified_params = agent_params.copy()
    modified_params['edge_type'] = new_edge_type
    modified_params['original_edge_type'] = original_edge_type  # Keep for reference

    return modified_params


if __name__ == "__main__":
    # Test the mapping
    print("Regime-Aware Agent Strategy Mapping")
    print("\nRegime Detector strategies:")
    print(f"  Sideways: {get_strategies_for_agent('regime_detector', 'sideways')}")
    print(f"  Trending: {get_strategies_for_agent('regime_detector', 'trending')}")
    print(f"  Volatile: {get_strategies_for_agent('regime_detector', 'volatile')}")

    print("\nParameter transformation test:")
    test_params = {'agent_type': 'pattern_discoverer', 'edge_type': 'momentum_mean_reversion', 'fast_period': 10}
    transformed = transform_agent_parameters(test_params, 'sideways')
    print(f"  Original: {test_params['edge_type']}")
    print(f"  Transformed: {transformed['edge_type']}")
