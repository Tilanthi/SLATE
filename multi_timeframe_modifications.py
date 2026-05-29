#!/usr/bin/env python3
"""
Create a new multi-timeframe discovery cycle that tests across ALL timeframes uniformly.
This will replace the single-timeframe discovery cycle.
"""

# This script shows the modifications needed to slate_core/discovery/edge_discovery_engine.py

MODIFICATIONS = """
# 1. Add timeframe to EdgeBacktestResult class (around line 100)
@dataclass
class EdgeBacktestResult:
    # ... existing fields ...
    timeframe: str = "1h"  # Add this field

# 2. Modify save_discovery method to include timeframe (line 1423-1436)
cursor.execute(\"\"\"
    INSERT OR REPLACE INTO edge_discoveries (
        edge_type, edge_description,
        total_profit_usdt, total_return_pct, final_capital, initial_capital,
        buy_hold_profit_usdt, buy_hold_return_pct, vs_buy_hold_usdt, beat_market,
        max_drawdown_pct, max_drawdown_usdt, sharpe_ratio, sortino_ratio, calmar_ratio,
        total_trades, win_rate, profit_factor, avg_trade_pnl_usdt,
        monte_carlo_mean_profit_usdt, monte_carlo_std_profit_usdt,
        monte_carlo_5th_percentile_usdt, monte_carlo_win_rate,
        walk_forward_is_profitable, walk_forward_avg_profit_usdt,
        avg_slippage_bps, avg_fill_rate, total_fees_usdt,
        period_start, period_end, volatility_regime, start_price, end_price,
        passed_validation, validation_failures, timestamp, rank_score,
        timeframe  # ADD THIS
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
\"\"", (
    # ... existing values ...
    result.timeframe,  # ADD THIS
))

# 3. Create new multi-timeframe discovery cycle method
async def run_multi_timeframe_discovery_cycle(self) -> Dict[str, Any]:
    \"\"\"
    Run discovery cycle across ALL timeframes uniformly.

    Timeframes: 1m, 5m, 10m, 15m, 30m, 1h, 4h, 8h, 12h, 1d
    \"\"\"
    timeframes = ['1m', '5m', '10m', '15m', '30m', '1h', '4h', '8h', '12h', '1d']

    logger.info(f"Starting MULTI-TIMEFRAME discovery across {len(timeframes)} timeframes...")

    all_results = []

    for timeframe in timeframes:
        logger.info(f"\\n{'='*60}")
        logger.info(f"Testing timeframe: {timeframe}")
        logger.info(f"{'='*60}")

        # Load data for this timeframe
        try:
            df = await self.fetch_solusdt_data(days=365, timeframe=timeframe)
        except RuntimeError as e:
            logger.warning(f"Skipping {timeframe}: {e}")
            continue

        if df is None or len(df) < 100:
            logger.warning(f"Insufficient data for {timeframe}, skipping")
            continue

        # Generate candidates for this timeframe
        candidates = self.generate_edge_candidates()
        logger.info(f"Testing {len(candidates)} strategies on {timeframe}")

        # Test each strategy on this timeframe
        for candidate in candidates:
            # Update description to include timeframe
            candidate.description = f"[{timeframe}] {candidate.description}"

            logger.info(f"Testing: {candidate.description}")

            try:
                result = self.simulate_edge_backtest(df, candidate, self.config)
                result.timeframe = timeframe  # Set timeframe

                # Monte Carlo validation if promising
                if result.total_profit_usdt > 0 and result.max_drawdown_pct < 0.25:
                    mc_mean, mc_std, mc_5th, mc_win = self.run_monte_carlo_validation(
                        df, candidate, self.config
                    )
                    result.monte_carlo_mean_profit_usdt = mc_mean
                    result.monte_carlo_std_profit_usdt = mc_std
                    result.monte_carlo_5th_percentile_usdt = mc_5th
                    result.monte_carlo_win_rate = mc_win

                self.save_discovery(result)
                all_results.append(result)

            except Exception as e:
                logger.error(f"Error testing {candidate.description}: {e}")

        logger.info(f"Completed {timeframe}: {len([r for r in all_results if r.timeframe == timeframe])} results")

    # Summary
    logger.info(f"\\n{'='*60}")
    logger.info("MULTI-TIMEFRAME DISCOVERY COMPLETE")
    logger.info(f"{'='*60}")
    for tf in timeframes:
        tf_results = [r for r in all_results if r.timeframe == tf]
        if tf_results:
            best = max(tf_results, key=lambda x: x.total_profit_usdt)
            logger.info(f"{tf:4s}: {len(tf_results):4d} strategies, best return: {best.total_return_pct:>7.2%}")

    passed = [r for r in all_results if r.passed_validation]
    passed.sort(key=lambda x: x.total_profit_usdt, reverse=True)

    return {
        "status": "success",
        "total_candidates": len(all_results),
        "passed_validation": len(passed),
        "top_edges": [
            {
                "description": r.edge_description,
                "profit_usdt": r.total_profit_usdt,
                "return_pct": r.total_return_pct,
                "drawdown_pct": r.max_drawdown_pct,
                "beat_market": r.vs_buy_hold_usdt,
                "sharpe": r.sharpe_ratio,
                "mc_win_rate": r.monte_carlo_win_rate
            }
            for r in passed[:5]
        ],
        "timeframes_tested": timeframes,
        "results_by_timeframe": {
            tf: len([r for r in all_results if r.timeframe == tf])
            for tf in timeframes
        }
    }
"""

print(__doc__)
print(MODIFICATIONS)
