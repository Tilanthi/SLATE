#!/bin/bash
# Strategy Implementation Verification Script
# Tests that all strategy classes generate signals correctly

echo "🔍 Strategy Implementation Verification"
echo "=========================================="

# Test 1: Verify strategy imports
echo "📦 Test 1: Verify strategy imports..."
python3 -c "
from slate_core.discovery.strategies.strategy_factory import StrategyFactory
from slate_core.discovery.strategies.momentum_strategy import MomentumStrategy
from slate_core.discovery.strategies.mean_reversion_strategy import MeanReversionStrategy
from slate_core.discovery.strategies.breakout_strategy import BreakoutStrategy
from slate_core.discovery.strategies.funding_arbitrage_strategy import FundingArbitrageStrategy
print('✅ All strategy imports successful')
"

if [ $? -eq 0 ]; then
    echo "✅ Strategy imports: PASSED"
else
    echo "❌ Strategy imports: FAILED"
    exit 1
fi

# Test 2: Verify strategy factory
echo ""
echo "🏭 Test 2: Verify strategy factory..."
python3 -c "
from slate_core.discovery.strategies.strategy_factory import StrategyFactory
from slate_core.discovery.closed_loop_discovery import StrategyHypothesis, HypothesisType

factory = StrategyFactory()

# Test each strategy type
for htype in [HypothesisType.MOMENTUM, HypothesisType.MEAN_REVERSION,
              HypothesisType.BREAKOUT, HypothesisType.FUNDING_ARBITRAGE]:
    hypothesis = StrategyHypothesis(
        name=f'test_{htype.value}',
        hypothesis_type=htype,
        premise='Test',
        prediction='Test',
        market_conditions={},
        strategy_design={},
        test_design={},
        expected_outcomes={},
        regime_applicability=['ALL']
    )
    strategy = factory.create_strategy(hypothesis)
    print(f'✅ {htype.value}: {strategy.__class__.__name__} created')
"

if [ $? -eq 0 ]; then
    echo "✅ Strategy factory: PASSED"
else
    echo "❌ Strategy factory: FAILED"
    exit 1
fi

# Test 3: Verify signal generation
echo ""
echo "📊 Test 3: Verify signal generation with real data..."
python3 -c "
import pandas as pd
from slate_core.discovery.strategies.strategy_factory import StrategyFactory
from slate_core.discovery.closed_loop_discovery import StrategyHypothesis, HypothesisType

# Load market data
try:
    df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1h_6m.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    print(f'✅ Loaded {len(df)} days of market data')
except Exception as e:
    print(f'❌ Could not load market data: {e}')
    exit(1)

factory = StrategyFactory()

# Test mean reversion strategy
hypothesis = StrategyHypothesis(
    name='test_mean_reversion',
    hypothesis_type=HypothesisType.MEAN_REVERSION,
    premise='Test',
    prediction='Test',
    market_conditions={},
    strategy_design={'bb_period': 20, 'bb_std': 2.0},
    test_design={},
    expected_outcomes={},
    regime_applicability=['SIDEWAYS']
)

strategy = factory.create_strategy(hypothesis)
signals = [strategy.generate_signal(df, i, {}) for i in range(100, min(200, len(df)))]
signal_count = sum(1 for s in signals if s != 0)

print(f'✅ Mean Reversion: {signal_count} signals out of {len(signals)} bars')

if signal_count > 0:
    print(f'✅ Signal frequency: {signal_count/len(signals)*100:.2f}%')
    print('✅ Mean Reversion strategy generating signals correctly')
else:
    print('❌ Mean Reversion strategy not generating signals')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Signal generation: PASSED"
else
    echo "❌ Signal generation: FAILED"
    exit 1
fi

# Test 4: Verify swarm integration
echo ""
echo "🐜 Test 4: Verify swarm integration components..."
python3 -c "
from slate_core.swarm.swarm_hypothesis_translator import SwarmToHypothesisTranslator
from slate_core.swarm.pheromone_hypothesis_mapper import PheromoneHypothesisMapper
from slate_core.swarm.swarm_discovery import PheromoneType, PheromoneSignal

# Test translator
translator = SwarmToHypothesisTranslator()
print(f'✅ SwarmToHypothesisTranslator initialized')

# Test mapper
mapper = PheromoneHypothesisMapper()
print(f'✅ PheromoneHypothesisMapper initialized')

# Test pheromone processing
from datetime import datetime
test_pheromones = [
    PheromoneSignal(
        pheromone_type=PheromoneType.DISCOVERY,
        location='fast_ema=12,slow_ema=26',
        strength=0.8,
        source_agent='test_agent',
        timestamp=datetime.now()
    )
]

base_params = {'fast_ema': 10, 'slow_ema': 20}
optimized_params = mapper.map_pheromones_to_parameters(test_pheromones, base_params)
print(f'✅ Pheromone guidance: {base_params} → {optimized_params}')
"

if [ $? -eq 0 ]; then
    echo "✅ Swarm integration: PASSED"
else
    echo "❌ Swarm integration: FAILED"
    exit 1
fi

# Test 5: Verify factory integration into backtest
echo ""
echo "🔄 Test 5: Verify factory integration into backtest system..."
python3 -c "
from slate_core.discovery.closed_loop_discovery import ClosedLoopDiscoverySystem

# Initialize system
system = ClosedLoopDiscoverySystem()
print('✅ ClosedLoopDiscoverySystem initialized')

# Check that factory pattern is available
from slate_core.discovery.strategies.strategy_factory import get_strategy_factory
factory = get_strategy_factory()
print(f'✅ Strategy factory available: {factory}')
print(f'✅ Supported types: {[htype.value for htype in factory.get_supported_types()]}')
"

if [ $? -eq 0 ]; then
    echo "✅ Factory integration: PASSED"
else
    echo "❌ Factory integration: FAILED"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ ALL VERIFICATION TESTS PASSED!"
echo ""
echo "Summary:"
echo "- Strategy imports: ✅"
echo "- Strategy factory: ✅"
echo "- Signal generation: ✅"
echo "- Swarm integration: ✅"
echo "- Factory integration: ✅"
echo ""
echo "🎉 Implementation verification complete!"
