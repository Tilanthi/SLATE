"""Per-candidate verdict (funnel) logging for SLATE evolution (ASTRA §4 / §7.2).

THE PROBLEM THIS SOLVES
-----------------------
SLATE's honest state was "saves nothing because every strategy loses money
after brutal costs." That is an OUTCOME, not a DIAGNOSIS. Without a record of
*where* each candidate died (correctness gate? too few trades? not profitable
OOS? overfit-adjusted fitness negative? two-window failure? eval crash?), we
cannot tell "no daily edge exists" from "candidates die at a fixable stage we
haven't isolated" — exactly the assumption-vs-measure trap ASTRA fell into
when it built a data lake to fix a bottleneck that turned out to be elsewhere.

THE FIX
-------
Every evaluated candidate emits ONE structured JSONL line carrying its
death-stage, so the failure distribution can be read directly:

    correctness -> too_few_trades -> not_profitable -> no_oos_edge
                -> overfit_fitness -> validation_failed -> eval_crash -> passed

Where the pile is largest is the bottleneck, and each bucket points to a
different fix (§4). Written INSIDE the search process to a file, independent of
stdout — the evolution controller runs LLM calls + subprocess evals whose
stdout may be discarded, so an explicit file write is the only reliable record
(§7.2).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_PATH = "slate_core/evolution_verdicts.jsonl"


@dataclass
class CandidateVerdict:
    """One candidate's outcome, for the funnel. fitness_score is -inf when the
    candidate was rejected by a gate (serialized to null for portable JSON)."""
    candidate_id: str
    death_stage: str            # see _STAGE_ORDER / death_stage_from_reason
    evaluated: bool             # passed the gate and produced a real score
    fitness_score: float
    rejection_reason: str
    family: str
    regime: str
    parent_id: str
    program_hash: str
    is_edge: float              # in-sample edge vs buy-hold (USDT)
    oos_edge: float             # out-of-sample edge vs buy-hold (USDT)
    n_trades_oos: int
    overfit_gap: float
    timestamp: str              # ISO-8601 UTC
    failed_gates: List[str] = field(default_factory=list)
    # Every distinct death-stage this candidate failed (multi-gate rejects fail
    # several at once). Empty for passes. Use this for the full co-failure
    # picture; death_stage is just the primary (first) one.


def _classify_subreason(text: str) -> str:
    """Map ONE semicolon-delimited sub-reason to a death-stage."""
    low = text.lower()
    if low.startswith("correctness"):
        return "correctness"
    if "total_profit" in low:                 # absolute-profit gate (1- or 2-window)
        return "not_profitable"
    if "does_not_beat_buyhold" in low or "edge_not_positive" in low:
        return "no_oos_edge"
    if "trades=" in low and "<" in low:        # min-trades gate
        return "too_few_trades"
    if "fitness=" in low:                      # the min_fitness (overfit) gate
        return "overfit_fitness"
    if "validation_score" in low:              # pluralistic validation floor
        return "validation_failed"
    if low.startswith("eval ") or low.startswith("eval:"):
        return "eval_crash"
    return "unknown"


def death_stage_from_reason(reason: str) -> str:
    """PRIMARY death-stage = the causally-earliest failing gate (the FIRST
    semicolon-delimited sub-reason), not a priority scan of the whole string.

    A reject often fails several gates at once; the evaluator checks them in
    order, so the first sub-reason is the most informative primary cause.
    Previously every multi-gate reject was over-labeled 'overfit_fitness'
    because the fitness reason always fires (a huge overfit penalty drags the
    adjusted fitness negative) and was scanned first. Use
    failed_gates_from_reason() for the full co-failure set.
    """
    r = (reason or "").strip()
    if not r:
        return "unknown"
    return _classify_subreason(r.split("; ")[0])


def failed_gates_from_reason(reason: str) -> List[str]:
    """Every distinct death-stage mentioned in a (possibly multi-gate) rejection
    reason, in first-appearance order. Empty for passes / unknown reasons."""
    r = (reason or "").strip()
    if not r:
        return []
    seen: List[str] = []
    for sub in r.split("; "):
        stage = _classify_subreason(sub)
        if stage != "unknown" and stage not in seen:
            seen.append(stage)
    return seen


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def verdict_from_fitness_result(result, *, candidate_id: str = "",
                                parent_id: str = "",
                                program_hash: str = "") -> CandidateVerdict:
    """Build a verdict from a FitnessResult. death_stage is 'passed' when the
    candidate cleared the gate, else mapped from its rejection_reason."""
    stage = "passed" if result.evaluated else death_stage_from_reason(result.rejection_reason)
    return CandidateVerdict(
        candidate_id=candidate_id or getattr(result, "candidate_id", ""),
        death_stage=stage,
        evaluated=bool(result.evaluated),
        fitness_score=float(result.fitness_score),
        rejection_reason=result.rejection_reason or "",
        family=getattr(result, "family_label", "") or "",
        regime=getattr(result, "regime_label", "") or "",
        parent_id=parent_id,
        program_hash=program_hash,
        is_edge=float(result.is_vs_buyhold),
        oos_edge=float(result.oos_vs_buyhold),
        n_trades_oos=int(result.n_trades_oos),
        overfit_gap=float(result.overfit_gap),
        timestamp=_now_iso(),
        failed_gates=[] if result.evaluated else failed_gates_from_reason(result.rejection_reason),
    )


def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce non-finite floats (inf/-inf/nan, e.g. a rejected -inf fitness) to
    None so the JSONL is portable (jq, strict pandas) rather than emitting the
    non-standard -Infinity token."""
    for k, v in rec.items():
        if isinstance(v, float) and not math.isfinite(v):
            rec[k] = None
    return rec


class VerdictLogger:
    """Appends one JSONL line per candidate to a file. Independent of stdout."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("SLATE_VERDICT_LOG", DEFAULT_PATH)

    def log(self, verdict: CandidateVerdict) -> None:
        rec = _sanitize(dataclasses.asdict(verdict))
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Module-level singleton: the controller calls log_candidate_verdict(verdict)
# without holding a logger reference. Tests inject one via set_verdict_logger.
# ---------------------------------------------------------------------------

_LOGGER: Optional[VerdictLogger] = None


def get_verdict_logger() -> VerdictLogger:
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = VerdictLogger()
    return _LOGGER


def set_verdict_logger(logger: Optional[VerdictLogger]) -> None:
    """Inject (or clear with None) the singleton logger — used by tests."""
    global _LOGGER
    _LOGGER = logger


def log_candidate_verdict(verdict: CandidateVerdict) -> None:
    """Persist one candidate verdict to the funnel log. NEVER raises — a logging
    failure must not crash the search loop (the verdict is diagnostic, not on
    the critical correctness path)."""
    try:
        get_verdict_logger().log(verdict)
    except Exception as exc:  # noqa: BLE001 - logging is best-effort
        logger.warning("verdict log write failed: %s", exc)
