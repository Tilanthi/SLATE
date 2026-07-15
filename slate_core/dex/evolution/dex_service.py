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
from slate_core.dex.data.load_data import REAL_DATA_DEFAULT, load_candles, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.dex.evolution.dex_controller import (
    DexMMPromptSampler, DexPairsPromptSampler, DexPromptSampler, _run_steps_parallel,
    dex_failure_summary, dex_mm_evolution_step, dex_pairs_evolution_step,
    run_dex_evolution, run_dex_evolution_parallel,
)

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
                 coin_b: str = "BTC"):
        self.data_path = data_path
        self.gate_preset = gate_preset
        self.interval_s = interval_s
        self.steps_per_cycle = steps_per_cycle
        self.target = target                  # "directional" | "market_maker"
        self.concurrency = concurrency        # P1: candidate evals run concurrently
        self.coin = coin                      # P2: perp symbol for funding-data merge
        self.coin_b = coin_b                  # P4: second leg of the pairs target
        self._hl = HLClient()
        self._dfA = None
        self._dfB = None
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

    def _load_pair(self):
        """Load two aligned markets (coin, coin_b) for the pairs target."""
        if self._dfA is None:
            dfA = load_candles(self.data_path)
            dfB = load_candles(f"sol_data_cache/HYPERLIQUID_{self.coin_b}_1h.json")
            common = dfA.index.intersection(dfB.index)
            self._dfA = dfA.loc[common]
            self._dfB = dfB.loc[common]
            self._df = self._dfA                  # so status() reports row count
        return self._dfA, self._dfB

    def status(self) -> dict:
        best = self.db.best()
        return {
            "pipeline": "dex",
            "running": self._running,
            "venue": "hyperliquid",
            "gate_preset": self.gate_preset,
            "llm_backend": self.llm.name,
            "interval_s": self.interval_s,
            "steps_per_cycle": self.steps_per_cycle,
            "niches": len(self.db.occupied_niches()),
            "pool_size": len(self.db.island_pool()),
            "best_fitness": (best.fitness_score if best else None),
            "best_id": (best.candidate_id if best else None),
            "data_rows": (len(self._df) if self._df is not None else None),
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
                if self.target == "pairs":
                    dfA, dfB = self._load_pair()
                else:
                    df = self._load_df()
                try:                                   # P5: inject recent failure feedback
                    self.sampler.failure_summary = dex_failure_summary()
                except Exception:
                    pass
                if self.target == "pairs":
                    produced = await _run_steps_parallel(
                        lambda: dex_pairs_evolution_step(
                            self.db, self.sampler, self.pool, dfA, dfB,
                            config=self.evolution_config, fitness_config=self.fitness_config),
                        self.steps_per_cycle, self.concurrency)
                elif self.target == "market_maker":
                    produced = await _run_steps_parallel(
                        lambda: dex_mm_evolution_step(
                            self.db, self.sampler, self.pool, df,
                            config=self.evolution_config, fitness_config=self.fitness_config),
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
