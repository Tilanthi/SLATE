"""PortfolioService: a long-running diversified-premium portfolio manager.

Assembles funding-carry premium streams across N coins, computes risk-managed
allocation weights via the PortfolioRiskController (drawdown throttle + regime
de-risk + vol-target), runs the portfolio backtester for combined metrics, and
reports per-stream + portfolio-level risk/return. Selected via SLATE_PIPELINE=portfolio.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

import numpy as np

from slate_core.portfolio.portfolio_backtester import PortfolioBacktester
from slate_core.risk.risk_manager import PortfolioRiskController, RiskConfig
from slate_core.statistics.equity_curve import portfolio_metrics

logger = logging.getLogger(__name__)


class PortfolioService:
    """Manages a diversified book of risk-premium streams under risk control."""

    def __init__(self, coins: Optional[List[str]] = None,
                 funding_threshold_pct: float = 0.0,
                 interval_s: float = 300.0):
        self.coins = coins or ["SOL", "BTC", "ETH"]
        self.threshold = funding_threshold_pct
        self.interval_s = interval_s
        self.risk = PortfolioRiskController(RiskConfig())
        self.backtester = PortfolioBacktester(periods_per_year=365)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._streams: Dict[str, dict] = {}   # coin -> {returns, metrics, ...}
        self._weights: Dict[str, float] = {}
        self._portfolio_result: Dict = {}
        self.stats = {"cycles": 0, "last_error": "", "last_rebalance": ""}

    def _load_streams(self):
        """Load + backtest ALL premium variants per coin (carry, regime-aware, reversal)."""
        from slate_core.premium.funding_carry import backtest_all_premiums
        from slate_core.dex.data.load_data import load_candles, merge_funding
        from slate_core.dex.data.hyperliquid_client import HLClient

        client = HLClient()
        for coin in self.coins:
            try:
                path = f"sol_data_cache/HYPERLIQUID_{coin}_1h.json"
                df = load_candles(path)
                try:
                    df = merge_funding(df, client, coin)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("funding merge failed for %s: %s", coin, str(exc)[:80])
                variants = backtest_all_premiums(df, coin=coin, timeframe="1h")
                for vname, result in variants.items():
                    key = f"{coin}_{vname}"
                    self._streams[key] = result
                    logger.info("loaded %s: sharpe=%.2f pnl=%.1f",
                                key, result["metrics"].get("sharpe", 0),
                                result["total_pnl"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("stream load failed for %s: %s", coin, str(exc)[:120])
                self.stats["last_error"] = str(exc)[:200]

    def _rebalance(self):
        """Run the AI allocation evolution + risk-managed portfolio metrics."""
        from slate_core.portfolio.allocation_gp import evolve_allocation

        if not self._streams:
            return
        stream_returns = {k: v["returns"] for k, v in self._streams.items()
                          if len(v["returns"]) > 10}
        if len(stream_returns) < self.risk.config.min_streams:
            logger.warning("need >= %d streams, have %d",
                           self.risk.config.min_streams, len(stream_returns))
            return

        # Phase 5: AI allocation — evolve the best risk-managed weights (native GA, no LLM)
        evo = evolve_allocation(stream_returns, n_gen=20, pop_size=30, seed=42)
        best = evo.get("best_genome")
        best_metrics = evo.get("best_metrics", {})

        if best:
            self._weights = {k: round(v, 3) for k, v in best.stream_weights.items()}
        else:
            n = len(stream_returns)
            self._weights = {k: 1.0 / n for k in stream_returns}

        combined = self.backtester.combine(stream_returns, self._weights)
        wf = self.backtester.walk_forward_validate(stream_returns, self._weights, n_folds=5)
        mc = self.backtester.monte_carlo(combined["returns"], n_sims=500)
        corr = self.backtester.correlation_report(stream_returns)

        self._portfolio_result = {
            "combined": combined,
            "walk_forward": wf,
            "monte_carlo": mc,
            "correlation": corr,
            "evolution_history": evo.get("history", []),
            "evolved_metrics": best_metrics,
        }
        self.stats["cycles"] += 1
        self.stats["last_rebalance"] = "done"

    def status(self) -> dict:
        """Report per-stream + portfolio-level risk/return."""
        per_stream = {}
        for coin, s in self._streams.items():
            m = s.get("metrics", {})
            per_stream[coin] = {
                "sharpe": round(m.get("sharpe", 0), 3),
                "max_drawdown": round(m.get("max_drawdown", 0), 4),
                "annualized_return": round(m.get("annualized_return", 0), 4),
                "total_pnl": round(s.get("total_pnl", 0), 2),
            }
        combined_metrics = {}
        if self._portfolio_result and "combined" in self._portfolio_result:
            cm = self._portfolio_result["combined"].get("metrics", {})
            combined_metrics = {
                "sharpe": round(cm.get("sharpe", 0), 3),
                "max_drawdown": round(cm.get("max_drawdown", 0), 4),
                "calmar": round(cm.get("calmar", 0), 3),
                "annualized_return": round(cm.get("annualized_return", 0), 4),
                "diversification_ratio": round(
                    self._portfolio_result["combined"].get("diversification_ratio", 1), 3),
            }
        mc = self._portfolio_result.get("monte_carlo", {}) if self._portfolio_result else {}
        return {
            "pipeline": "portfolio",
            "running": self._running,
            "coins": self.coins,
            "streams_loaded": len(self._streams),
            "per_stream": per_stream,
            "weights": {k: round(v, 3) for k, v in self._weights.items()},
            "combined_metrics": combined_metrics,
            "monte_carlo_p95_dd": round(mc.get("p95_dd", 0), 4) if mc else None,
            "correlation_max": round(
                self._portfolio_result.get("correlation", {}).get("max_correlation", 0), 3)
                if self._portfolio_result else None,
            "risk_state": self.risk.status(),
            "stats": dict(self.stats),
        }

    async def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("PortfolioService started (coins=%s)", self.coins)
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("PortfolioService stopped")
        return True

    async def _loop(self):
        """Periodic: load streams (if needed) → rebalance → report."""
        while self._running:
            try:
                if not self._streams:
                    self._load_streams()
                self._rebalance()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.stats["last_error"] = str(exc)[:200]
                logger.warning("portfolio cycle error: %s", str(exc)[:200])
            await asyncio.sleep(self.interval_s)


__all__ = ["PortfolioService"]
