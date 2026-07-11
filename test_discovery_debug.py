#!/usr/bin/env python3
"""
Debug test of closed-loop discovery system with detailed error reporting
"""
import pandas as pd
import traceback
from slate_core.discovery.closed_loop_integration import get_enhanced_discovery_system

# Load market data properly
print("Loading market data...")
df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)
print(f"✅ Loaded {len(df)} days of real market data")

# Get closed-loop discovery system
print("Initializing closed-loop discovery system...")
system = get_enhanced_discovery_system()

# Run one discovery cycle with detailed error handling
print("Running discovery cycle...")
print("=" * 60)

try:
    results = system.run_enhanced_discovery_cycle(df)

    print("\n" + "=" * 60)
    print("DISCOVERY RESULTS:")
    print("=" * 60)

    if results.get('status') == 'success':
        print(f"✅ Discovery cycle completed successfully")

        discovery = results.get('discovery', {})
        validation = results.get('validation', {})
        database = results.get('database_saved', 0)

        print(f"\n🔬 Hypotheses Generated: {discovery.get('hypotheses_generated', 0)}")
        print(f"🧪 Strategies Validated: {discovery.get('strategies_validated', 0)}")
        print(f"💾 Database Saved: {database} strategies")

        validation_status = validation.get('status', 'unknown')
        print(f"📊 Validation Status: {validation_status}")

        if validation_status == 'success':
            reports = validation.get('validation_reports', [])
            print(f"📋 Validation Reports: {len(reports)}")

            for i, report in enumerate(reports[:3]):  # Show first 3
                print(f"\n  Strategy {i+1}:")
                print(f"    Name: {report.get('strategy_name', 'unknown')}")
                print(f"    Recommendation: {report.get('deployment_recommendation', 'UNKNOWN')}")
                print(f"    Win Rate: {report.get('win_rate', 0):.1%}")
                print(f"    Return: {report.get('total_return_pct', 0):.2%}")
                print(f"    Trades: {report.get('total_trades', 0)}")
    else:
        print(f"❌ Discovery cycle failed")
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Message: {results.get('message', 'No message provided')}")

        # Print any error details
        if 'discovery' in results:
            discovery = results['discovery']
            print(f"\nDiscovery details:")
            print(f"  Status: {discovery.get('status', 'unknown')}")
            if 'error' in discovery:
                print(f"  Error: {discovery['error']}")

except Exception as e:
    print(f"\n❌ EXCEPTION during discovery cycle:")
    print(f"Error: {e}")
    print(f"\nFull traceback:")
    traceback.print_exc()

print("\n" + "=" * 60)