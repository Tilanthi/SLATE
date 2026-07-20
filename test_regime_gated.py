"""Regime-gated carry strategy test + AI allocation evolution.

Tests whether deploying carry ONLY in down markets (flat otherwise) produces
a profitable, risk-managed portfolio across SOL/BTC/ETH. Then evolves the
optimal allocation via the native GA (Phase 5 AI layer).
"""
import pandas as pd
import numpy as np
from slate_core.dex.data.load_data import load_candles, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.premium.funding_carry import backtest_premium_stream
from slate_core.statistics.equity_curve import portfolio_metrics
from slate_core.portfolio.portfolio_backtester import PortfolioBacktester
from slate_core.portfolio.allocation_gp import evolve_allocation


def regime_gated_carry(down_threshold=-0.03, lookback=168):
    """Short perps ONLY when funding>0 AND market is in a downtrend (7d ret < threshold).
    Flat otherwise — avoids the bull-market losses that killed unconditional carry."""
    def signal_fn(df, i, params):
        funding = df["funding"].iloc[i] if "funding" in df.columns else 0.0
        if funding <= 0:
            return 0
        if i >= lookback:
            ret_7d = df["close"].iloc[i] / df["close"].iloc[i - lookback] - 1.0
            if ret_7d > down_threshold:
                return 0    # market NOT down enough → flat
        return -1            # market is down → short (carry + directional profit)
    return signal_fn


def main():
    client = HLClient()
    streams = {}
    for coin in ["SOL", "BTC", "ETH"]:
        df = load_candles(f"sol_data_cache/HYPERLIQUID_{coin}_1h.json")
        df = merge_funding(df, client, coin)
        result = backtest_premium_stream(df, coin, regime_gated_carry(-0.03, 168),
                                         "regime_gated_carry", timeframe="1h")
        streams[coin] = result
        m = result["metrics"]
        tag = "PROFIT" if m["sharpe"] > 0 else "loss"
        print(f"{coin} regime-gated carry: sharpe={m['sharpe']:+.2f} "
              f"dd={m['max_drawdown']:.3f} ann_ret={m['annualized_return']:+.4f} "
              f"pnl={result['total_pnl']:+.1f} [{tag}]")

    stream_returns = {k: v["returns"] for k, v in streams.items() if len(v["returns"]) > 10}
    print(f"\n--- AI allocation evolution (20 gen x 30 pop, native GA) ---")
    evo = evolve_allocation(stream_returns, n_gen=20, pop_size=30, seed=42)
    best = evo["best_genome"]
    best_m = evo["best_metrics"]
    if best:
        print(f"evolved weights: {dict((k, round(v, 3)) for k, v in best.stream_weights.items())}")
    print(f"best portfolio: sharpe={best_m.get('sharpe', 0):+.2f} "
          f"calmar={best_m.get('calmar', 0):+.2f} dd={best_m.get('max_drawdown', 0):.3f}")

    bt = PortfolioBacktester(periods_per_year=365)
    weights = best.stream_weights if best else {k: 1.0 / len(stream_returns) for k in stream_returns}
    combined = bt.combine(stream_returns, weights)
    wf = bt.walk_forward_validate(stream_returns, weights, n_folds=5)
    mc = bt.monte_carlo(combined["returns"], n_sims=500)
    cm = combined["metrics"]
    print(f"\n===== COMBINED regime-gated portfolio =====")
    print(f"sharpe={cm['sharpe']:+.2f} max_dd={cm['max_drawdown']:.3f} "
          f"calmar={cm['calmar']:+.2f} ann_ret={cm['annualized_return']:+.4f}")
    print(f"diversification_ratio={combined['diversification_ratio']:.2f}")
    print(f"monte_carlo_p95_dd={mc['p95_dd']:.3f} max_dd={mc['max_dd']:.3f}")
    print(f"walk_forward folds:")
    for f in wf.get("folds", []):
        print(f"  fold {f['fold']}: sharpe={f['sharpe']:+.2f} dd={f['max_drawdown']:.3f}")

    print(f"\n===== COMPARISON =====")
    print(f"unconditional carry (equal-weight):     sharpe=-0.35 (loses in bull market)")
    print(f"regime-gated carry (AI-evolved):        sharpe={cm['sharpe']:+.2f}")


if __name__ == "__main__":
    main()
