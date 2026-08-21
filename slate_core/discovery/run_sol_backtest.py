"""
Run rigorous walk-forward backtest on SOLUSDT perpetuals
"""

import sys
from pathlib import Path

# Make the repo root importable regardless of CWD: this file lives at
# <repo>/slate_core/discovery/run_sol_backtest.py
sys.path.append(str(Path(__file__).resolve().parents[2]))

from slate_core.discovery.ml_500_5h_rigorous_backtester import RigorousWalkForwardBacktester
import json
from slate_core.config.paths import DATA_CACHE_DIR

def main():
    """Run rigorous backtest on SOLUSDT data."""

    print("\n" + "=" * 80)
    print("ML-500-5h RIGOROUS WALK-FORWARD BACKTEST - SOLUSDT PERPETUALS")
    print("=" * 80)
    print("\nTesting on SOLUSDT perpetual futures (1 year)")
    print("  • No look-ahead bias")
    print("  • No data leakage")
    print("  • Realistic trading costs")
    print("  • Proper walk-forward validation")

    # Initialize backtester for SOLUSDT
    backtester = RigorousWalkForwardBacktester(
        data_path=f"{DATA_CACHE_DIR}/SOLUSDT_1h_1y.csv",
        initial_capital=100000,
        position_size=0.30,
        stop_loss=0.05,
        take_profit=0.08,
        max_drawdown_limit=0.15
    )

    # Load and prepare data
    backtester.load_and_prepare_data()

    # Run rigorous walk-forward backtest
    results = backtester.run_walk_forward_backtest()

    # Print results
    backtester.print_results(results)

    # Save results
    backtester.save_results(results, "solusdt_ml_500_5h_rigorous_backtest_results.json")

    print("\n✓ SOLUSDT backtest complete!")
    print("  Results saved to solusdt_ml_500_5h_rigorous_backtest_results.json")

    return results, backtester

if __name__ == "__main__":
    results, backtester = main()
