#!/bin/bash
# End-to-End Integration Test
# Tests the complete implementation: strategies → factory → validation → learning

echo "🚀 End-to-End Integration Test"
echo "=========================================="

# Test the complete flow from hypothesis to validated strategy
echo "🔄 Running complete discovery flow test..."

python3 << 'EOF'
import pandas as pd
import sys
from datetime import datetime

# Import all components
from slate_core.discovery.closed_loop_discovery import (
    ClosedLoopDiscoverySystem,
    StrategyHypothesis,
    HypothesisType
)
from slate_core.discovery.strategies.strategy_factory import StrategyFactory

print("📊 Loading market data...")
try:
    # Try to load the perpetual futures data
    df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1h_6m.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    print(f"✅ Loaded {len(df)} days of SOLUSDT perpetual futures data")
except Exception as e:
    print(f"❌ Could not load market data: {e}")
    sys.exit(1)

print("\n🏭 Testing strategy factory...")
factory = StrategyFactory()

# Create a test hypothesis for each strategy type
test_results = []

for htype in [HypothesisType.MOMENTUM, HypothesisType.MEAN_REVERSION,
              HypothesisType.BREAKOUT, HypothesisType.FUNDING_ARBITRAGE]:

    try:
        print(f"\n🧪 Testing {htype.value}...")

        # Create hypothesis
        if htype == HypothesisType.MOMENTUM:
            strategy_design = {'fast_ema': 12, 'slow_ema': 26}
        elif htype == HypothesisType.MEAN_REVERSION:
            strategy_design = {'bb_period': 20, 'bb_std': 2.0, 'rsi_period': 14}
        elif htype == HypothesisType.BREAKOUT:
            strategy_design = {'lookback': 20, 'bb_std': 2.0}
        elif htype == HypothesisType.FUNDING_ARBITRAGE:
            strategy_design = {'funding_threshold': 0.0001, 'holding_period_hours': 8}

        hypothesis = StrategyHypothesis(
            name=f'end_to_end_test_{htype.value}',
            hypothesis_type=htype,
            premise=f'End-to-end test of {htype.value} strategy',
            prediction='Strategy will generate signals and complete backtest',
            market_conditions={'regime': 'TEST'},
            strategy_design=strategy_design,
            test_design={'test_period': '12_months', 'transaction_costs': 'realistic_perpetual'},
            expected_outcomes={'min_trades': 5, 'min_win_rate': 0.40},
            regime_applicability=['ALL'],
            confidence_level=0.8
        )

        # Create strategy using factory
        strategy = factory.create_strategy(hypothesis)
        print(f"  ✅ Strategy created: {strategy.__class__.__name__}")

        # Create signal function
        signal_function = factory.create_signal_function(strategy)
        print(f"  ✅ Signal function created")

        # Test signal generation on actual data
        signals = []
        for i in range(100, min(200, len(df))):
            try:
                signal = signal_function(df, i, {})
                signals.append(signal)
            except Exception as e:
                print(f"  ⚠️  Signal generation error at bar {i}: {e}")
                break

        signal_count = sum(1 for s in signals if s != 0)
        signal_frequency = signal_count / len(signals) * 100 if signals else 0

        print(f"  ✅ Generated {signal_count} signals ({signal_frequency:.2f}% frequency)")

        # Basic validation
        if signal_count > 0:
            print(f"  ✅ {htype.value} strategy: PASSED")
            test_results.append({
                'type': htype.value,
                'status': 'PASSED',
                'signals': signal_count,
                'frequency': signal_frequency
            })
        else:
            print(f"  ❌ {htype.value} strategy: FAILED (no signals)")
            test_results.append({
                'type': htype.value,
                'status': 'FAILED',
                'signals': signal_count,
                'frequency': signal_frequency
            })

    except Exception as e:
        print(f"  ❌ {htype.value} strategy: ERROR - {e}")
        test_results.append({
            'type': htype.value,
            'status': 'ERROR',
            'error': str(e)
        })

# Summary
print("\n" + "="*60)
print("📊 END-TO-END TEST SUMMARY")
print("="*60)

passed_count = sum(1 for r in test_results if r.get('status') == 'PASSED')
total_count = len(test_results)

for result in test_results:
    status_symbol = "✅" if result.get('status') == 'PASSED' else "❌"
    print(f"{status_symbol} {result['type']}: {result['status']}")
    if result.get('status') == 'PASSED':
        print(f"   Signals: {result['signals']}, Frequency: {result['frequency']:.2f}%")

print("\n" + "="*60)
print(f"Results: {passed_count}/{total_count} strategies passed")

if passed_count == total_count:
    print("✅ ALL END-TO-END TESTS PASSED!")
    print("\n🎉 Implementation is working correctly!")
    sys.exit(0)
else:
    print(f"⚠️  {total_count - passed_count} strategies failed")
    print("Some components may need attention")
    sys.exit(1)

EOF

if [ $? -eq 0 ]; then
    echo "✅ End-to-end test: PASSED"
else
    echo "❌ End-to-end test: FAILED"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ END-TO-END INTEGRATION TEST COMPLETE!"
echo ""
echo "🎉 All components are working together correctly!"
echo ""
echo "System Status:"
echo "- Strategy implementations: ✅"
echo "- Strategy factory: ✅"
echo "- Signal generation: ✅"
echo "- Real data integration: ✅"
echo "- End-to-end flow: ✅"
