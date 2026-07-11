"""Tests for the Phase 0 fitness evaluator (slate_core.discovery.evolution.fitness_evaluator)."""
import math

from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig,
    check_signal_correctness,
    split_is_oos,
    run_backtest,
    evaluate_fitness,
    FitnessResult,
)


# ---------------------------------------------------------------------------
# Task 0.2: correctness-by-construction gate
# ---------------------------------------------------------------------------

def test_correctness_accepts_valid_signals(sol_slice):
    def good_signal(df, i, params):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1
    ok, reason = check_signal_correctness(good_signal, sol_slice, {})
    assert ok is True
    assert reason == ""


def test_correctness_rejects_unbounded_output(sol_slice):
    def bad_signal(df, i, params):
        return 999.0  # not in {-1, 0, 1}
    ok, reason = check_signal_correctness(bad_signal, sol_slice, {})
    assert ok is False
    assert "bounded" in reason.lower() or "invalid" in reason.lower()


def test_correctness_rejects_nan(sol_slice):
    def nan_signal(df, i, params):
        return float("nan")
    ok, reason = check_signal_correctness(nan_signal, sol_slice, {})
    assert ok is False


def test_correctness_rejects_exceptions(sol_slice):
    def crash_signal(df, i, params):
        raise RuntimeError("boom")
    ok, reason = check_signal_correctness(crash_signal, sol_slice, {})
    assert ok is False
    assert "exception" in reason.lower()


# ---------------------------------------------------------------------------
# Task 0.3: chronological IS/OOS split + seeded backtest runner
# ---------------------------------------------------------------------------

def test_split_is_chronological_and_disjoint(sol_slice):
    is_df, oos_df = split_is_oos(sol_slice, is_fraction=0.6)
    assert len(is_df) + len(oos_df) == len(sol_slice)
    assert is_df.index[-1] <= oos_df.index[0]   # IS ends before OOS starts
    assert len(oos_df) > 20                       # enough bars to trade


def test_run_backtest_returns_metrics_dict(sol_slice):
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1
    res = run_backtest(mom, {}, sol_slice, edge_type="momentum", seed=42)
    assert isinstance(res, dict)
    for k in ("total_profit_usdt", "vs_buy_hold_usdt", "sharpe_ratio",
              "total_trades", "beat_market", "max_drawdown_pct"):
        assert k in res, f"missing metric {k}"
    assert res["total_trades"] >= 0


def test_run_backtest_is_deterministic_under_seed(sol_slice):
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1
    a = run_backtest(mom, {}, sol_slice, "momentum", seed=7)
    b = run_backtest(mom, {}, sol_slice, "momentum", seed=7)
    assert a["total_profit_usdt"] == b["total_profit_usdt"]


# ---------------------------------------------------------------------------
# Task 0.4: overfit penalty + evaluate_fitness
# ---------------------------------------------------------------------------

def test_evaluate_fitness_rejects_bad_signal(sol_slice):
    def bad(df, i, p):
        return 42  # fails correctness gate
    res = evaluate_fitness(bad, {}, sol_slice, edge_type="momentum", candidate_id="bad")
    assert isinstance(res, FitnessResult)
    assert res.evaluated is False
    assert res.fitness_score == float("-inf")
    assert res.rejection_reason


def test_evaluate_fitness_happy_path(monkeypatch, sol_slice):
    """Deterministic happy path via a stubbed backtest (IS slightly > OOS)."""
    from slate_core.discovery.evolution import fitness_evaluator as fe

    def fake_run(signal_fn, parameters, df, edge_type, seed):
        is_run = df.index[0] == sol_slice.index[0]
        base = {"total_profit_usdt": 100.0, "vs_buy_hold_usdt": 0.0,
                "sharpe_ratio": 1.5, "total_trades": 20, "beat_market": True,
                "max_drawdown_pct": 0.1, "total_transaction_costs_usdt": 0.0,
                "win_rate": 0.6, "profit_factor": 1.5}
        base["vs_buy_hold_usdt"] = 50.0 if is_run else 30.0
        return base
    monkeypatch.setattr(fe, "run_backtest", fake_run)

    def sig(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1
    res = evaluate_fitness(sig, {}, sol_slice, edge_type="momentum", candidate_id="happy")
    assert res.evaluated is True
    assert math.isfinite(res.fitness_score)
    assert res.oos_vs_buyhold == 30.0
    assert res.overfit_gap == 20.0          # 50 - 30
    assert res.overfit_penalty == 20.0      # weight 1.0
    assert res.fitness_score == 10.0        # 30 - 20


def test_overfit_penalty_when_is_far_exceeds_oos(monkeypatch, sol_slice):
    """A huge IS/OOS gap must produce a large penalty that drags fitness down."""
    from slate_core.discovery.evolution import fitness_evaluator as fe

    def fake_run(signal_fn, parameters, df, edge_type, seed):
        is_run = df.index[0] == sol_slice.index[0]
        base = {"total_profit_usdt": 100.0, "vs_buy_hold_usdt": 0.0,
                "sharpe_ratio": 1.0, "total_trades": 20, "beat_market": True,
                "max_drawdown_pct": 0.1, "total_transaction_costs_usdt": 0.0,
                "win_rate": 0.5, "profit_factor": 1.0}
        base["vs_buy_hold_usdt"] = 500.0 if is_run else 10.0
        return base
    monkeypatch.setattr(fe, "run_backtest", fake_run)

    def flat(df, i, p):
        return 0
    res = evaluate_fitness(flat, {}, sol_slice, edge_type="momentum", candidate_id="gap")
    assert res.overfit_gap == 490.0
    assert res.overfit_penalty == 490.0
    assert res.fitness_score == 10.0 - 490.0


def test_require_absolute_oos_profit_gate(monkeypatch, sol_slice):
    """A strategy that loses money OOS (but happens to beat a worse buy-hold)
    must be rejected by the absolute-profit gate, not rewarded."""
    from slate_core.discovery.evolution import fitness_evaluator as fe

    def fake_run(signal_fn, parameters, df, edge_type, seed):
        base = {"total_profit_usdt": -50.0, "vs_buy_hold_usdt": 30.0,
                "sharpe_ratio": 0.5, "total_trades": 20, "beat_market": True,
                "max_drawdown_pct": 0.1, "total_transaction_costs_usdt": 0.0,
                "win_rate": 0.4, "profit_factor": 0.9}
        return base
    monkeypatch.setattr(fe, "run_backtest", fake_run)

    def flat(df, i, p):
        return 0
    res = evaluate_fitness(flat, {}, sol_slice, edge_type="momentum", candidate_id="neg")
    assert res.evaluated is False
    assert "profit" in res.rejection_reason.lower()
    assert res.fitness_score == float("-inf")


def test_evaluate_fitness_runs_on_real_data(sol_slice):
    """Real backtest integration: must run without crashing and be well-formed
    (does NOT assert evaluated=True — that depends on real performance)."""
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1
    res = evaluate_fitness(mom, {}, sol_slice, edge_type="momentum", candidate_id="real")
    assert isinstance(res, FitnessResult)
    assert res.n_trades_oos >= 0
    assert isinstance(res.overfit_gap, float)
    assert not math.isnan(res.fitness_score)


# ---------------------------------------------------------------------------
# Task 4.3: two-window overfit gate (for evolved-code programs)
# ---------------------------------------------------------------------------

from slate_core.discovery.evolution.fitness_evaluator import evaluate_fitness_two_window


def _two_window_run_factory(oos2_profit, oos2_edge):
    """Stub run_backtest distinguishing IS / OOS1 / OOS2 by row count."""
    def fake_run(signal_fn, parameters, df, edge_type, seed):
        ln = len(df)
        if ln > 50:                                  # IS (~60 rows)
            return {"total_profit_usdt": 100.0, "vs_buy_hold_usdt": 80.0,
                    "sharpe_ratio": 1.5, "total_trades": 50, "beat_market": True,
                    "max_drawdown_pct": 0.1, "total_transaction_costs_usdt": 0.0,
                    "win_rate": 0.6, "profit_factor": 1.5}
        if ln > 30:                                  # OOS1 (~36 rows)
            return {"total_profit_usdt": 50.0, "vs_buy_hold_usdt": 30.0,
                    "sharpe_ratio": 1.2, "total_trades": 30, "beat_market": True,
                    "max_drawdown_pct": 0.1, "total_transaction_costs_usdt": 0.0,
                    "win_rate": 0.55, "profit_factor": 1.3}
        return {"total_profit_usdt": oos2_profit, "vs_buy_hold_usdt": oos2_edge,
                "sharpe_ratio": 0.8, "total_trades": 20, "beat_market": oos2_profit > 0,
                "max_drawdown_pct": 0.15, "total_transaction_costs_usdt": 0.0,
                "win_rate": 0.45, "profit_factor": 1.0}
    return fake_run


def test_two_window_passes_when_both_windows_profitable(monkeypatch, sol_slice):
    from slate_core.discovery.evolution import fitness_evaluator as fe
    monkeypatch.setattr(fe, "run_backtest", _two_window_run_factory(45.0, 28.0))
    res = evaluate_fitness_two_window(lambda df, i, p: 0, {}, sol_slice,
                                      edge_type="momentum", candidate_id="ok")
    assert res.evaluated is True
    assert res.fitness_score == 28.0 - 51.0     # min OOS edge(28) - overfit penalty(80-29=51)


def test_two_window_rejects_when_one_window_loses(monkeypatch, sol_slice):
    """The overfit control: a strategy that loses on the 2nd OOS window is rejected."""
    from slate_core.discovery.evolution import fitness_evaluator as fe
    monkeypatch.setattr(fe, "run_backtest", _two_window_run_factory(-20.0, -40.0))
    res = evaluate_fitness_two_window(lambda df, i, p: 0, {}, sol_slice,
                                      edge_type="momentum", candidate_id="overfit")
    assert res.evaluated is False
    assert "profit" in res.rejection_reason.lower()
    assert res.fitness_score == float("-inf")


def test_two_window_rejects_bad_signal(sol_slice):
    res = evaluate_fitness_two_window(lambda df, i, p: 42, {}, sol_slice,
                                      edge_type="momentum", candidate_id="bad")
    assert res.evaluated is False
    assert res.fitness_score == float("-inf")


# ---------------------------------------------------------------------------
# Task D2: gate presets (strict / exploration)
# ---------------------------------------------------------------------------

def test_strict_preset_is_default():
    c = FitnessConfig.strict()
    assert c.min_trades == 10
    assert c.overfit_penalty_weight == 1.0
    assert c.require_absolute_oos_profit is True


def test_exploration_preset_is_looser_but_keeps_core_defenses():
    c = FitnessConfig.exploration()
    assert c.min_trades < 10
    assert c.overfit_penalty_weight < 1.0
    # Core overfit defenses must remain on even in exploration mode.
    assert c.require_absolute_oos_profit is True
    assert c.require_beat_buyhold_oos is True
