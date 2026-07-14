"""Tests for the Phase 0 fitness evaluator (slate_core.discovery.evolution.fitness_evaluator)."""
import math

import numpy as np
import pandas as pd

from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig,
    check_signal_correctness,
    split_is_oos,
    run_backtest,
    evaluate_fitness,
    classify_signal_family,
    classify_active_regime,
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
    # The huge IS/OOS gap drags overfit-adjusted fitness to -480, which the
    # min_fitness gate now rejects (previously this was stored with fitness -480).
    assert res.evaluated is False
    assert "fitness" in res.rejection_reason.lower()


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


def _two_window_run_factory(oos2_profit, oos2_edge, is_edge=40.0):
    """Stub run_backtest distinguishing IS / OOS1 / OOS2 by row count.
    is_edge defaults low so the happy path has positive overfit-adjusted fitness."""
    def fake_run(signal_fn, parameters, df, edge_type, seed):
        ln = len(df)
        if ln > 50:                                  # IS (~60 rows)
            return {"total_profit_usdt": 100.0, "vs_buy_hold_usdt": is_edge,
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
    assert res.fitness_score == 17.0     # min OOS edge(28) - overfit penalty(40-29=11)


def test_two_window_rejects_when_one_window_loses(monkeypatch, sol_slice):
    """The overfit control: a strategy that loses on the 2nd OOS window is rejected."""
    from slate_core.discovery.evolution import fitness_evaluator as fe
    monkeypatch.setattr(fe, "run_backtest", _two_window_run_factory(-20.0, -40.0))
    res = evaluate_fitness_two_window(lambda df, i, p: 0, {}, sol_slice,
                                      edge_type="momentum", candidate_id="overfit")
    assert res.evaluated is False
    assert "profit" in res.rejection_reason.lower()
    assert res.fitness_score == float("-inf")


def test_two_window_rejects_negative_overfit_adjusted_fitness(monkeypatch, sol_slice):
    """Tightened gate: profitable on BOTH OOS windows (so it passes the
    absolute-profit and beat-buyhold gates) but overfit-adjusted fitness is
    negative -> REJECTED. Stops overfit survivors (e.g. the live -1826s) being
    stored as niche elites. min_fitness default = 0."""
    from slate_core.discovery.evolution import fitness_evaluator as fe
    # IS edge 500 vs avg OOS ~29 -> penalty ~471 -> fitness min(30,28)-471 = -443
    monkeypatch.setattr(fe, "run_backtest", _two_window_run_factory(45.0, 28.0, is_edge=500.0))
    res = evaluate_fitness_two_window(lambda df, i, p: 0, {}, sol_slice,
                                      edge_type="momentum", candidate_id="overfit_neg")
    assert res.evaluated is False
    assert res.fitness_score == float("-inf")
    assert "fitness" in res.rejection_reason.lower()


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


# ---------------------------------------------------------------------------
# Behavioral niche labels: family + regime derived from the candidate's OWN
# behaviour (not inherited). Lets MAP-Elites diversify across >1 cell.
# ---------------------------------------------------------------------------

def test_classify_signal_family_momentum(sol_slice):
    """A signal that goes long after up moves aligns with recent returns."""
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1
    assert classify_signal_family(mom, sol_slice, {}) == "momentum"


def test_classify_signal_family_mean_reversion(sol_slice):
    """A signal that goes long after down moves opposes recent returns."""
    def mr(df, i, p):
        return -1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else 1
    assert classify_signal_family(mr, sol_slice, {}) == "mean_reversion"


def test_classify_signal_family_flat_is_other(sol_slice):
    """A signal that never trades has no directional timing bias."""
    def flat(df, i, p):
        return 0
    assert classify_signal_family(flat, sol_slice, {}) == "other"


def test_classifiers_handle_backtester_injected_columns(sol_slice):
    """Real evolved signals read columns the backtester INJECTS (e.g. ema_20),
    which are absent from the raw df. The classifiers must probe on the same
    enriched frame the backtester trades on — otherwise every such signal
    KeyErrors bar-by-bar and mislabels as other/unknown, collapsing MAP-Elites
    back to one cell. (This is the bug the live monitor surfaced: the first
    real survivors were all labelled other/unknown despite using ema_20.)"""
    def ema_trend(df, i, p):                       # mirrors a real evolved signal
        close = df["close"].iloc[i]
        ema = df["ema_20"].iloc[i]                 # NOT in the raw df
        roc = (close - df["close"].iloc[i - 3]) / df["close"].iloc[i - 3]
        if close > ema and roc > 0:
            return 1
        if close < ema and roc < 0:
            return -1
        return 0
    fam = classify_signal_family(ema_trend, sol_slice, {})
    reg = classify_active_regime(ema_trend, sol_slice, {})
    assert fam != "other", f"family fell back to 'other' (raw df lacks ema_20): {fam}"
    assert reg != "unknown", f"regime fell back to 'unknown': {reg}"


def _vol_regime_df(n_each=60):
    """Synthetic close path for the vol-bucketing UNIT TEST only: first half
    calm, second half wild. NOT market data (no trading uses this) — it exists
    so the regime classifier can be exercised deterministically, which real
    sol_slice (one fixed vol profile) does not allow."""
    rng = np.random.RandomState(0)
    calm = 100.0 + np.cumsum(rng.normal(0, 0.05, n_each))        # low vol
    wild = calm[-1] + np.cumsum(rng.normal(0, 3.0, n_each))      # high vol
    return pd.DataFrame({"close": np.concatenate([calm, wild])})


def test_classify_active_regime_trades_in_wild_half():
    df = _vol_regime_df()
    def wild_only(d, i, p):
        return 1 if 70 <= i < 110 else 0      # deep in the high-vol region
    assert classify_active_regime(wild_only, df, {}) == "high_vol"


def test_classify_active_regime_trades_in_calm_half():
    df = _vol_regime_df()
    def calm_only(d, i, p):
        return 1 if 20 <= i < 50 else 0       # deep in the low-vol region
    assert classify_active_regime(calm_only, df, {}) == "low_vol"


def test_classify_active_regime_never_trades_is_unknown():
    df = _vol_regime_df()
    def flat(d, i, p):
        return 0
    assert classify_active_regime(flat, df, {}) == "unknown"


def test_two_window_result_carries_behavioral_labels(monkeypatch, sol_slice):
    """An evaluated candidate must carry family/regime labels so the controller
    can place it in a behavioural niche instead of inheriting the parent's."""
    from slate_core.discovery.evolution import fitness_evaluator as fe
    monkeypatch.setattr(fe, "run_backtest", _two_window_run_factory(45.0, 28.0))
    res = evaluate_fitness_two_window(
        lambda df, i, p: (1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1),
        {}, sol_slice, edge_type="momentum", candidate_id="labelled",
    )
    assert res.evaluated is True
    assert res.family_label == "momentum"
    assert res.regime_label in {"low_vol", "med_vol", "high_vol"}


def test_two_window_rejected_candidate_still_carries_labels(monkeypatch, sol_slice):
    """(a2) A REJECTED candidate must still carry family/regime labels, so the
    funnel can show WHAT kind of signal is failing - not just that it failed.
    (Labels used to be set only on the pass-branch, so every reject showed as
    (none)/(none) in the funnel.)"""
    from slate_core.discovery.evolution import fitness_evaluator as fe
    # OOS2 loses -> rejected at the profit gate, but correctness passes.
    monkeypatch.setattr(fe, "run_backtest", _two_window_run_factory(-20.0, -40.0))

    def mr(df, i, p):                       # mean-reversion: long after down moves
        return -1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else 1
    res = evaluate_fitness_two_window(mr, {}, sol_slice, edge_type="momentum",
                                      candidate_id="rejected_mr")
    assert res.evaluated is False                       # rejected ...
    assert res.family_label == "mean_reversion"          # ... but still labelled
    assert res.regime_label in {"low_vol", "med_vol", "high_vol"}
