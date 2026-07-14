"""Tests for the per-candidate verdict (funnel) logger (ASTRA §4 / §7.2).

The funnel diagnostic: every evaluated candidate's outcome + death-stage is
persisted to a JSONL log, independent of stdout, so we can SEE where candidates
die (correctness? profit? overfit? two-window?) instead of only observing that
nothing gets stored.
"""
import json

from slate_core.discovery.evolution.verdict_log import (
    CandidateVerdict,
    VerdictLogger,
    death_stage_from_reason,
    failed_gates_from_reason,
    verdict_from_fitness_result,
    log_candidate_verdict,
    set_verdict_logger,
)
from slate_core.discovery.evolution.fitness_evaluator import FitnessResult


def _v(**over):
    base = dict(candidate_id="c", death_stage="unknown", evaluated=False,
                fitness_score=float("-inf"), rejection_reason="", family="",
                regime="", parent_id="", program_hash="", is_edge=0.0,
                oos_edge=0.0, n_trades_oos=0, overfit_gap=0.0, timestamp="t")
    base.update(over)
    return CandidateVerdict(**base)


# ---------------------------------------------------------------------------
# death-stage mapping (the heart of the funnel: bucket WHERE candidates die)
# ---------------------------------------------------------------------------

def test_death_stage_maps_correctness():
    assert death_stage_from_reason("correctness: NaN/None signal at bar 5") == "correctness"


def test_death_stage_maps_not_profitable():
    assert death_stage_from_reason("oos_total_profit=-50.00<=0 (not profitable)") == "not_profitable"
    assert death_stage_from_reason("oos2_total_profit=-20.00<=0") == "not_profitable"


def test_death_stage_maps_no_oos_edge():
    assert death_stage_from_reason("oos_does_not_beat_buyhold") == "no_oos_edge"
    assert death_stage_from_reason("oos_edge_not_positive_on_both_windows") == "no_oos_edge"


def test_death_stage_maps_too_few_trades():
    assert death_stage_from_reason("oos_trades=3<10") == "too_few_trades"
    assert death_stage_from_reason("oos2_trades=2<5") == "too_few_trades"


def test_death_stage_maps_overfit_fitness():
    assert death_stage_from_reason(
        "fitness=-443.0<0.0 (overfit-adjusted edge not positive; IS>>OOS)"
    ) == "overfit_fitness"


def test_death_stage_maps_eval_crash():
    assert death_stage_from_reason("eval timeout (>30s / >10s CPU)") == "eval_crash"
    assert death_stage_from_reason("eval: no result (child crashed)") == "eval_crash"


def test_death_stage_unknown_for_empty_or_unrecognized():
    assert death_stage_from_reason("") == "unknown"
    assert death_stage_from_reason("something unprecedented") == "unknown"


# ---------------------------------------------------------------------------
# (a1) multi-gate reasons: primary stage = FIRST failing gate; failed_gates
# preserves the co-failures. Stops the over-labeling where every multi-gate
# reject was bucketed as "overfit_fitness" because the fitness reason appeared
# last but the min_fitness gate always fires when the overfit penalty is huge.
# ---------------------------------------------------------------------------

def test_death_stage_uses_first_failing_gate_for_multi_gate_reason():
    reason = ("oos2_total_profit=0.00<=0; oos1_trades=1<5; oos2_trades=0<5; "
              "fitness=-3858.0<0.0 (overfit-adjusted edge not positive; IS>>OOS)")
    assert death_stage_from_reason(reason) == "not_profitable"


def test_failed_gates_lists_all_distinct_stages_in_order():
    reason = ("oos2_total_profit=0.00<=0; oos1_trades=1<5; oos2_trades=0<5; "
              "fitness=-3858.0<0.0 (overfit-adjusted edge not positive; IS>>OOS)")
    assert failed_gates_from_reason(reason) == [
        "not_profitable", "too_few_trades", "overfit_fitness",
    ]


def test_failed_gates_empty_when_no_reason():
    assert failed_gates_from_reason("") == []
    assert failed_gates_from_reason(None) == []


def test_verdict_carries_primary_stage_and_failed_gates():
    res = FitnessResult(evaluated=False, fitness_score=float("-inf"),
                        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
                        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
                        validation_score=0.0,
                        rejection_reason="oos2_total_profit=0.00<=0; oos1_trades=1<5; "
                                         "fitness=-5.0<0.0 (overfit-adjusted edge not positive; IS>>OOS)",
                        candidate_id="r")
    v = verdict_from_fitness_result(res, candidate_id="r")
    assert v.death_stage == "not_profitable"            # primary = first gate
    assert v.failed_gates == ["not_profitable", "too_few_trades", "overfit_fitness"]


def test_passed_verdict_has_empty_failed_gates():
    res = FitnessResult(evaluated=True, fitness_score=12.0, oos_vs_buyhold=12.0,
                        is_vs_buyhold=20.0, overfit_gap=8.0, overfit_penalty=4.0,
                        n_trades_is=30, n_trades_oos=15, validation_score=1.0,
                        candidate_id="ok")
    v = verdict_from_fitness_result(res, candidate_id="ok")
    assert v.death_stage == "passed"
    assert v.failed_gates == []


# ---------------------------------------------------------------------------
# VerdictLogger: JSONL append, independent of stdout
# ---------------------------------------------------------------------------

def test_verdict_logger_appends_jsonl_line(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    lg = VerdictLogger(str(path))
    lg.log(_v(candidate_id="c1", death_stage="not_profitable", oos_edge=-1.0))
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["candidate_id"] == "c1"
    assert rec["death_stage"] == "not_profitable"
    assert rec["oos_edge"] == -1.0


def test_verdict_logger_appends_many_lines(tmp_path):
    path = tmp_path / "v.jsonl"
    lg = VerdictLogger(str(path))
    for i in range(3):
        lg.log(_v(candidate_id=f"c{i}", death_stage="passed", evaluated=True,
                  fitness_score=float(i)))
    assert len(path.read_text().splitlines()) == 3


def test_verdict_logger_emits_portable_json(tmp_path):
    """-inf fitness must not leak as the non-standard token -Infinity (which
    breaks jq / pandas strict parsers). Coerced to null for portable JSON."""
    path = tmp_path / "v.jsonl"
    VerdictLogger(str(path)).log(_v(fitness_score=float("-inf")))
    raw = path.read_text().strip()
    assert "Infinity" not in raw          # portable JSON only
    rec = json.loads(raw)
    assert rec["fitness_score"] is None   # -inf -> null


def test_verdict_logger_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "dir" / "v.jsonl"
    VerdictLogger(str(path)).log(_v())
    assert path.exists()


# ---------------------------------------------------------------------------
# verdict_from_fitness_result
# ---------------------------------------------------------------------------

def test_verdict_from_passed_result():
    res = FitnessResult(evaluated=True, fitness_score=12.0, oos_vs_buyhold=12.0,
                        is_vs_buyhold=20.0, overfit_gap=8.0, overfit_penalty=4.0,
                        n_trades_is=30, n_trades_oos=15, validation_score=1.0,
                        candidate_id="x", family_label="momentum",
                        regime_label="high_vol")
    v = verdict_from_fitness_result(res, candidate_id="x", parent_id="p",
                                    program_hash="deadbeef")
    assert v.death_stage == "passed"
    assert v.evaluated is True
    assert v.fitness_score == 12.0
    assert v.family == "momentum" and v.regime == "high_vol"
    assert v.parent_id == "p" and v.program_hash == "deadbeef"
    assert v.oos_edge == 12.0 and v.n_trades_oos == 15


def test_verdict_from_rejected_result_uses_death_stage():
    res = FitnessResult(evaluated=False, fitness_score=float("-inf"),
                        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
                        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
                        validation_score=0.0,
                        rejection_reason="oos_total_profit=-5.00<=0 (not profitable)",
                        candidate_id="bad")
    v = verdict_from_fitness_result(res, candidate_id="bad")
    assert v.death_stage == "not_profitable"
    assert v.evaluated is False


# ---------------------------------------------------------------------------
# module-level singleton (the controller calls log_candidate_verdict directly)
# ---------------------------------------------------------------------------

def test_log_candidate_verdict_writes_to_singleton(tmp_path):
    lg = VerdictLogger(str(tmp_path / "sing.jsonl"))
    set_verdict_logger(lg)
    try:
        log_candidate_verdict(_v(candidate_id="z", death_stage="compile"))
        lines = (tmp_path / "sing.jsonl").read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["death_stage"] == "compile"
    finally:
        set_verdict_logger(None)   # reset so other tests rebuild the default


def test_log_candidate_verdict_never_raises_on_bad_path():
    """Logging must not crash the search loop even if the path is unwritable."""
    set_verdict_logger(VerdictLogger("/no/such/dir/!/v.jsonl"))
    try:
        log_candidate_verdict(_v())     # must swallow the OSError, not raise
    finally:
        set_verdict_logger(None)
