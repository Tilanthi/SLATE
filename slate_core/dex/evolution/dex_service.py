"""DexEvolutionService: a long-running DEX evolution loop hosted by the server.

Mirrors EvolutionService (CEX) but runs the DEX controller on Hyperliquid candle
data, with a separate population DB (slate_core/dex_evolution.db) and verdict log
(slate_core/dex_verdicts.jsonl). Selected by SLATE_PIPELINE=dex; otherwise the CEX
evolution runs. Paper/discovery only — never places live HL orders.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from slate_core.discovery.evolution.controller import EvolutionConfig
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.llm_client import LLMClient, LLMConfig, get_llm_client
from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig
from slate_core.discovery.evolution.program_database import ProgramDBConfig, ProgramDatabase
from slate_core.dex.data.load_data import REAL_DATA_DEFAULT, load_candles, load_markets, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.dex.backtester.l2_tick_backtester import load_l2_snapshots
from slate_core.dex.backtester.economics import hl_perp_fee_schedule
from slate_core.dex.evolution.dex_controller import (
    DexMMPromptSampler, DexPairsPromptSampler, DexPromptSampler, _run_steps_parallel,
    dex_cross_market_evolution_step, dex_failure_summary, dex_mm_evolution_step,
    dex_pairs_evolution_step, run_dex_evolution, run_dex_evolution_parallel,
)
from slate_core.dex.evolution.param_optimizer import mm_param_step
from slate_core.dex.evolution.gp.controller import gp_evolution_step
from slate_core.dex.evolution.gp.fitness import textbook_archetype_curves

logger = logging.getLogger(__name__)

DEX_EVOLUTION_DB_DEFAULT = "slate_core/dex_evolution.db"


class DexEvolutionService:
    def __init__(self, data_path: str = REAL_DATA_DEFAULT,
                 persist_path: str = DEX_EVOLUTION_DB_DEFAULT,
                 llm_client: Optional[LLMClient] = None,
                 gate_preset: str = "exploration",
                 interval_s: float = 60.0, steps_per_cycle: int = 2,
                 target: str = "directional",
                 max_signal_complexity: int = 350,
                 concurrency: int = 4,
                 coin: str = "SOL",
                 coin_b: str = "BTC",
                 markets=None,
                 l2_data_path: Optional[str] = None,
                 l2_stride: int = 3):
        self.data_path = data_path
        self.gate_preset = gate_preset
        self.interval_s = interval_s
        self.steps_per_cycle = steps_per_cycle
        self.target = target                  # "directional" | "market_maker"
        self.concurrency = concurrency        # P1: candidate evals run concurrently
        self.coin = coin                      # P2: perp symbol for funding-data merge
        self.coin_b = coin_b                  # P4: second leg of the pairs target
        # Native (non-LLM) market-making path: tick/L2 snapshots + GA parameter
        # optimizer. The MM target no longer calls the LLM at all.
        self.l2_data_path = l2_data_path or f"sol_data_cache/L2_{coin}.jsonl"
        self.l2_stride = l2_stride            # subsample factor for search-pace
        self._snaps = None
        self._archetype_curves = None         # GP novelty reference (textbook MM curves)
        self._gp_schedule = None              # GP search fee schedule (maker=0% tier)
        self._hl = HLClient()
        self._dfA = None
        self._dfB = None
        self.markets = markets or ["SOL", "BTC", "ETH"]   # P3: cross-market target
        self._markets_df = None
        self.fitness_config = (FitnessConfig.exploration() if gate_preset == "exploration"
                               else FitnessConfig.strict())
        # DEX complexity cap is LOOSER than CEX (200): measured DEX signals cluster
        # at 201-350 AST nodes (p50=277, p90=341), so 200 rejected 68% pre-eval and
        # starved the funnel. 350 lets candidates reach evaluation where the overfit
        # gate (the primary defense) decides, while still blocking the baroque tail.
        self.evolution_config = EvolutionConfig(max_signal_complexity=max_signal_complexity,
                                                validation="walkforward")
        self.db = ProgramDatabase(ProgramDBConfig(persist_path=persist_path))
        self.db.load()
        if target == "market_maker":
            self.sampler = DexMMPromptSampler()
        elif target == "pairs":
            self.sampler = DexPairsPromptSampler()
        elif target == "cross_market":
            self.sampler = DexPromptSampler()        # evolves a directional signal
        else:
            self.sampler = DexPromptSampler()
        self.llm = llm_client or get_llm_client(LLMConfig())
        self.pool = LLMPool(self.llm, self.llm, LLMPoolConfig())
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._df = None
        self.stats = {"cycles": 0, "produced": 0, "rejected": 0, "last_error": ""}

    def _load_df(self):
        if self._df is None:
            df = load_candles(self.data_path)
            try:                                   # P2: real per-bar funding for carry
                df = merge_funding(df, self._hl, self.coin)
            except Exception as exc:  # noqa: BLE001
                logger.warning("funding merge failed: %s", str(exc)[:120])
            self._df = df
        return self._df

    def _load_snaps(self):
        """Load + subsample the accumulated L2 snapshots for the native MM path."""
        if self._snaps is None:
            snaps = load_l2_snapshots(self.l2_data_path)
            if self.l2_stride and self.l2_stride > 1:
                snaps = snaps[::self.l2_stride]
            self._snaps = snaps
            self._df = self._df or snaps  # so status() reports a row count
        return self._snaps

    def _load_pair(self):
        """Load two aligned markets (coin, coin_b) for the pairs target."""
        if self._dfA is None:
            dfA = load_candles(f"sol_data_cache/HYPERLIQUID_{self.coin}_1h.json")
            dfB = load_candles(f"sol_data_cache/HYPERLIQUID_{self.coin_b}_1h.json")
            common = dfA.index.intersection(dfB.index)
            self._dfA = dfA.loc[common]
            self._dfB = dfB.loc[common]
            self._df = self._dfA                  # so status() reports row count
        return self._dfA, self._dfB

    def _load_markets(self):
        """Load N markets for the cross-market directional target."""
        if self._markets_df is None:
            self._markets_df = load_markets(self.markets)
            if self._markets_df:
                self._df = next(iter(self._markets_df.values()))
        return self._markets_df

    def status(self) -> dict:
        best = self.db.best()
        return {
            "pipeline": "dex",
            "running": self._running,
            "venue": "hyperliquid",
            "target": self.target,
            "native": self.target in ("market_maker", "market_maker_gp"),   # no LLM
            "gate_preset": self.gate_preset,
            "llm_backend": self.llm.name,
            "interval_s": self.interval_s,
            "steps_per_cycle": self.steps_per_cycle,
            "niches": len(self.db.occupied_niches()),
            "pool_size": len(self.db.island_pool()),
            "best_fitness": (best.fitness_score if best else None),
            "best_id": (best.candidate_id if best else None),
            "data_rows": (len(self._df) if self._df is not None else None),
            "l2_snapshots": (len(self._snaps) if self._snaps is not None else None),
            "stats": dict(self.stats),
        }

    async def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("DexEvolutionService started (preset=%s, llm=%s, venue=hyperliquid)",
                    self.gate_preset, self.llm.name)
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("DexEvolutionService stopped")
        return True

    async def _loop(self):
        while self._running:
            try:
                snaps = None
                if self.target == "pairs":
                    dfA, dfB = self._load_pair()
                elif self.target == "cross_market":
                    markets_df = self._load_markets()
                elif self.target == "market_maker":
                    snaps = self._load_snaps()      # native MM path uses L2, not bars
                elif self.target == "market_maker_gp":
                    snaps = self._load_snaps()      # native GP path also uses L2
                else:
                    df = self._load_df()
                try:                                   # P5: inject recent failure feedback
                    self.sampler.failure_summary = dex_failure_summary()
                except Exception:
                    pass
                if self.target == "cross_market":
                    produced = await _run_steps_parallel(
                        lambda: dex_cross_market_evolution_step(
                            self.db, self.sampler, self.pool, markets_df,
                            config=self.evolution_config, fitness_config=self.fitness_config),
                        self.steps_per_cycle, self.concurrency)
                elif self.target == "pairs":
                    produced = await _run_steps_parallel(
                        lambda: dex_pairs_evolution_step(
                            self.db, self.sampler, self.pool, dfA, dfB,
                            config=self.evolution_config, fitness_config=self.fitness_config),
                        self.steps_per_cycle, self.concurrency)
                elif self.target == "market_maker":
                    # NATIVE path (no LLM): GA + MAP-Elites over (spread, skew, size)
                    # evaluated by the tick/L2 backtester. The pool/sampler are unused.
                    produced = await _run_steps_parallel(
                        lambda: mm_param_step(
                            self.db, snaps,
                            config=self.evolution_config, fitness_config=self.fitness_config),
                        self.steps_per_cycle, self.concurrency)
                elif self.target == "market_maker_gp":
                    # NATIVE structure-level GP (no LLM): evolve the quoting policy's
                    # FORM, not just 3 params, with novelty pressure vs textbook MMs.
                    if self._archetype_curves is None:
                        self._archetype_curves = textbook_archetype_curves(snaps)
                    if self._gp_schedule is None:
                        # Search at the maker=0% tier (>$500M vol) — the regime where
                        # active MM can be profitable. At retail fees (+0.015%) every
                        # active strategy loses, so the search would degenerate to
                        # abstention; maker=0% is the meaningful MM search regime.
                        # Caveat: structure must profit net of adverse selection AND
                        # the strategy must qualify for the volume tier in production.
                        self._gp_schedule = hl_perp_fee_schedule(volume_14d_usd=600_000_000)
                    produced = await _run_steps_parallel(
                        lambda: gp_evolution_step(
                            self.db, snaps, archetype_curves=self._archetype_curves,
                            fitness_config=self.fitness_config, schedule=self._gp_schedule),
                        self.steps_per_cycle, self.concurrency)
                else:
                    produced = await run_dex_evolution_parallel(
                        self.db, self.sampler, self.pool, df,
                        n_steps=self.steps_per_cycle, concurrency=self.concurrency,
                        config=self.evolution_config, fitness_config=self.fitness_config,
                    )
                self.stats["cycles"] += 1
                self.stats["produced"] += len(produced)
                self.stats["rejected"] += max(0, self.steps_per_cycle - len(produced))
                self.db.save()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.stats["last_error"] = str(exc)[:200]
                logger.warning("dex evolution cycle error: %s", str(exc)[:200])
            await asyncio.sleep(self.interval_s)
