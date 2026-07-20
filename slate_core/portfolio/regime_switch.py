"""Regime-switching portfolio: deploy the best strategy per market regime.

Combines the per-regime winners from the sweep into a single signal stream:
for each bar, detect the regime and use that regime's designated strategy.
Goes flat in regimes where no strategy has positive edge.

This is the practical implementation of the regime-switching concept: different
strategies work in different conditions, and a regime-aware portfolio that
deploys the RIGHT strategy at the RIGHT time can be positive overall even when
no single strategy is positive across ALL conditions.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from slate_core.discovery.regime_detector import (
    ALL_REGIMES, BEAR, BULL, HIGH_VOL, LOW_VOL, SIDEWAYS, RegimeDetector,
)
from slate_core.discovery.mega_sweep import _precompute, fast_backtest, gen_signals
from slate_core.statistics.equity_curve import portfolio_metrics


class RegimeSwitchPortfolio:
    """A portfolio that switches between strategies based on detected regime.

    Each regime maps to a (strategy_type, params) pair. Bars in regimes with
    no mapping are flat (no position).
    """

    def __init__(self, regime_map: Optional[Dict[str, tuple]] = None,
                 detector: Optional[RegimeDetector] = None):
        """
        Args:
            regime_map: {regime_label: (strategy_type, params_dict)}.
                Omit a regime → flat in that regime.
            detector: RegimeDetector instance.
        """
        self.detector = detector or RegimeDetector()
        self.regime_map = regime_map or {}

    def generate_combined_signal(self, df: pd.DataFrame) -> np.ndarray:
        """Generate the regime-switched signal array for a df."""
        ind = _precompute(df)
        regime = self.detector.detect(df)
        regime_arr = regime.values
        n = len(df)
        combined = np.zeros(n, dtype=int)

        for regime_label, (strat_type, params) in self.regime_map.items():
            mask = regime_arr == regime_label
            if mask.sum() < 10:
                continue
            # Generate signal only for this regime's bars
            sub_sig = gen_signals(ind, strat_type, **params)
            combined[mask] = sub_sig[mask]

        return combined

    def backtest(self, df: pd.DataFrame, coin: str = "") -> Dict:
        """Backtest the regime-switched strategy on a single coin's data."""
        signals = self.generate_combined_signal(df)
        closes = df["close"].astype(float).values
        rets = fast_backtest(signals, closes)
        m = portfolio_metrics(rets, periods_per_year=8760)

        # Per-regime breakdown
        regime = self.detector.detect(df)
        regime_arr = regime.values
        per_regime = {}
        for r in ALL_REGIMES:
            mask = regime_arr == r
            if mask.sum() > 50:
                rm = portfolio_metrics(rets[mask], periods_per_year=8760)
                per_regime[r] = {"sharpe": rm["sharpe"], "pnl_pct": float(np.sum(rets[mask]))}
            else:
                per_regime[r] = None

        return {
            "coin": coin,
            "signals": signals,
            "returns": rets,
            "overall_sharpe": m["sharpe"],
            "overall_dd": m["max_drawdown"],
            "overall_ann_ret": m["annualized_return"],
            "per_regime": per_regime,
            "regime_map": {k: v[0] for k, v in self.regime_map.items()},
        }

    def backtest_multi(self, coins_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """Backtest the regime-switched strategy across multiple coins."""
        return {coin: self.backtest(df, coin=coin) for coin, df in coins_data.items()}


# Default regime map based on the mega-sweep findings (trend-following dominates)
DEFAULT_REGIME_MAP = {
    BEAR: ("carry_regime", {"ut": 0.01, "lb": 24, "thr": 0.0}),
    BULL: ("trend_follow", {"lb": 168, "thr": 0.05}),
    LOW_VOL: ("ema_cross", {"fast": 12, "slow": 48}),
    # SIDEWAYS: flat (no edge found)
    # HIGH_VOL: flat (no edge found)
}


def run_regime_switch_backtest(coins_data: Dict[str, pd.DataFrame],
                               regime_map: Optional[Dict] = None) -> Dict:
    """Run the regime-switching portfolio and report combined metrics."""
    from slate_core.portfolio.portfolio_backtester import PortfolioBacktester

    rmap = regime_map or DEFAULT_REGIME_MAP
    rsp = RegimeSwitchPortfolio(rmap)

    # Backtest per coin
    per_coin = rsp.backtest_multi(coins_data)

    # Combine into a portfolio (equal-weight across coins)
    stream_returns = {coin: r["returns"] for coin, r in per_coin.items()}
    bt = PortfolioBacktester(periods_per_year=8760)
    weights = {k: 1.0 / len(stream_returns) for k in stream_returns}
    combined = bt.combine(stream_returns, weights)
    wf = bt.walk_forward_validate(stream_returns, weights, n_folds=5)
    mc = bt.monte_carlo(combined["returns"], n_sims=500)

    print("\n" + "=" * 70)
    print("REGIME-SWITCHING PORTFOLIO RESULTS")
    print("=" * 70)
    print(f"\nRegime map: {dict((k, v[0]) for k, v in rmap.items())}")

    print(f"\n--- Per-coin results ---")
    for coin, r in per_coin.items():
        print(f"  {coin}: sharpe={r['overall_sharpe']:+.2f} "
              f"dd={r['overall_dd']:.3f} ann_ret={r['overall_ann_ret']:+.4f}")
        for regime_label, pr in r["per_regime"].items():
            if pr and pr["sharpe"] != 0:
                print(f"    {regime_label:10s}: sharpe={pr['sharpe']:+.2f} pnl={pr['pnl_pct']:+.4f}")

    cm = combined["metrics"]
    print(f"\n--- Combined portfolio (equal-weight across coins) ---")
    print(f"  sharpe={cm['sharpe']:+.2f} max_dd={cm['max_drawdown']:.3f} "
          f"calmar={cm['calmar']:+.2f} ann_ret={cm['annualized_return']:+.4f}")
    print(f"  diversification_ratio={combined['diversification_ratio']:.2f}")
    print(f"  monte_carlo_p95_dd={mc['p95_dd']:.3f}")

    print(f"\n--- Walk-forward validation ---")
    for f in wf.get("folds", []):
        print(f"  fold {f['fold']}: sharpe={f['sharpe']:+.2f} dd={f['max_drawdown']:.3f}")

    # Comparison
    print(f"\n--- COMPARISON ---")
    print(f"  unconditional carry (equal-weight):     sharpe=-0.35")
    print(f"  regime-gated carry (AI-evolved):        sharpe=+0.06")
    print(f"  regime-switching portfolio:             sharpe={cm['sharpe']:+.2f}")

    return {
        "per_coin": per_coin,
        "combined": combined,
        "walk_forward": wf,
        "monte_carlo": mc,
    }


__all__ = ["RegimeSwitchPortfolio", "DEFAULT_REGIME_MAP", "run_regime_switch_backtest"]
