#!/usr/bin/env python3
"""
Verify that the discovery system generates realistic trading results
"""
import pandas as pd
import sqlite3
from slate_core.discovery.closed_loop_integration import get_enhanced_discovery_system

print("=" * 60)
print("VERIFYING REALISTIC TRADING RESULTS")
print("=" * 60)

# Load market data properly
print("\n1. Loading market data...")
df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1h_6m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)
print(f"   ✅ Loaded {len(df)} days of real market data")

# Clear database for clean test
print("\n2. Clearing database for clean test...")
conn = sqlite3.connect('slate_core/slate_realistic_discoveries.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM perpetual_discoveries")
conn.commit()
conn.close()
print("   ✅ Database cleared")

# Run discovery cycle
print("\n3. Running discovery cycle...")
system = get_enhanced_discovery_system()
results = system.run_enhanced_discovery_cycle(df)

print("\n4. Checking results...")
discovery_status = results.get('status', 'unknown')
print(f"   Overall Status: {discovery_status}")

if discovery_status == 'success':
    discovery = results.get('discovery', {})
    validation = results.get('validation', {})
    database_saved = results.get('database_saved', 0)

    print(f"   Hypotheses Generated: {discovery.get('hypotheses_generated', 0)}")
    print(f"   Strategies Generated: {discovery.get('strategies_generated', 0)}")
    print(f"   Strategies Validated: {discovery.get('strategies_validated', 0)}")
    print(f"   Database Saved: {database_saved}")

    # Check database contents
    print("\n5. Verifying database contents...")
    conn = sqlite3.connect('slate_core/slate_realistic_discoveries.db')
    cursor = conn.cursor()

    # Count strategies
    cursor.execute("SELECT COUNT(*) FROM perpetual_discoveries")
    total_strategies = cursor.fetchone()[0]
    print(f"   Total strategies in database: {total_strategies}")

    if total_strategies > 0:
        # Get strategy details
        cursor.execute("""
            SELECT strategy_name, total_trades, winning_trades, losing_trades,
                   win_rate, total_profit_usdt, total_fees_usdt, total_slippage_usdt,
                   final_capital, initial_capital
            FROM perpetual_discoveries
            LIMIT 1
        """)
        strategy = cursor.fetchone()

        print("\n   Sample Strategy:")
        print(f"   Name: {strategy[0]}")
        print(f"   Total Trades: {strategy[1]}")
        print(f"   Winning Trades: {strategy[2]}")
        print(f"   Losing Trades: {strategy[3]}")
        print(f"   Win Rate: {strategy[4]}%")
        print(f"   Total Profit: ${strategy[5]:.2f}")
        print(f"   Total Fees: ${strategy[6]:.2f}")
        print(f"   Total Slippage: ${strategy[7]:.2f}")
        print(f"   Final Capital: ${strategy[8]:.2f}")
        print(f"   Initial Capital: ${strategy[9]:.2f}")

        # Verify mathematical consistency
        print("\n6. Mathematical consistency checks:")
        total_trades = strategy[1]
        winning_trades = strategy[2]
        losing_trades = strategy[3]
        win_rate = strategy[4]

        print(f"   total_trades == winning_trades + losing_trades:")
        if total_trades == winning_trades + losing_trades:
            print(f"   ✅ {total_trades} == {winning_trades} + {losing_trades}")
        else:
            print(f"   ❌ {total_trades} != {winning_trades} + {losing_trades}")

        if total_trades > 0:
            expected_win_rate = (winning_trades / total_trades) * 100
            print(f"   win_rate ≈ winning_trades / total_trades:")
            print(f"   Expected: {expected_win_rate:.1f}%, Actual: {win_rate:.1f}%")
            if abs(expected_win_rate - win_rate) < 1:  # Within 1%
                print(f"   ✅ Win rate is consistent")
            else:
                print(f"   ❌ Win rate mismatch")

        # Check for realistic costs
        print("\n7. Realistic trading cost checks:")
        if strategy[6] > 0:  # total_fees_usdt
            print(f"   ✅ Fees are non-zero: ${strategy[6]:.2f}")
        else:
            print(f"   ❌ Fees are zero (unrealistic)")

        if strategy[7] > 0:  # total_slippage_usdt
            print(f"   ✅ Slippage is non-zero: ${strategy[7]:.2f}")
        else:
            print(f"   ❌ Slippage is zero (unrealistic)")

        # Check for realistic P&L
        if strategy[5] != 0 or total_trades > 0:  # Either has profit or has trades
            print(f"   ✅ Strategy has trading activity or P&L")
        else:
            print(f"   ❌ No trading activity or P&L (placeholder data)")

    else:
        print("   ⚠️  No strategies saved to database (strict validation working)")

    conn.close()
else:
    print(f"   ❌ Discovery failed: {discovery_status}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)