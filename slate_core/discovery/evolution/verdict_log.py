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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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


def death_stage_from_reason(reason: str) -> str:
    """Bucket a FitnessResult.rejection_reason into a funnel death-stage.

    Reasons are produced by fitness_evaluator.py (the gate messages) and
    subprocess_eval.py (eval timeouts/crashes). Order matters: check the
    specific gate signatures before the generic fallback.
    """
    r = (reason or "").lower()
    if not r:
        return "unknown"
    if r.startswith("correctness"):
        return "correctness"
    if "fitness=" in r:                       # the min_fitness (overfit) gate
        return "overfit_fitness"
    if "does_not_beat_buyhold" in r or "edge_not_positive" in r:
        return "no_oos_edge"
    if "total_profit" in r:                   # absolute-profit gate (1- or 2-window)
        return "not_profitable"
    if "trades=" in r and "<" in r:           # min-trades gate
        return "too_few_trades"
    if "validation_score" in r:               # pluralistic validation floor
        return "validation_failed"
    if r.startswith("eval ") or r.startswith("eval:"):
        return "eval_crash"
    return "unknown"


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
