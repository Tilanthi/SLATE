"""Regression tests for the validation gate (Fix 5).

A money-losing strategy must be REJECTED, not sail through as CONDITIONAL via
auto-passing validators + a 33% consensus floor.
"""
import pytest

from slate_core.discovery.rigorous_validation import get_rigorous_validation_system


def _metrics(**overrides):
    base = {
        "total_profit": 0.0,
        "total_return": 0.0,
        "sharpe_ratio": 0.0,
        "total_trades": 0,
        "win_rate": 0.0,
        "max_drawdown": 0.0,
        "initial_capital": 10000.0,
        "final_capital": 10000.0,
    }
    base.update(overrides)
    return base


def test_validation_rejects_money_losing_strategy():
    """Fix 5: negative-profit strategy -> REJECT (was CONDITIONAL)."""
    system = get_rigorous_validation_system()
    losing = _metrics(total_profit=-150.0, total_return=-0.015, sharpe_ratio=-0.9,
                      total_trades=80, win_rate=0.45, max_drawdown=0.05,
                      final_capital=9850.0)
    report = system.validate_strategy("loser", losing)
    assert report.deployment_recommendation == "REJECT", (
        f"losing strategy got {report.deployment_recommendation}, expected REJECT"
    )
    assert report.consensus_result is False


def test_validation_rejects_zero_profit_strategy():
    """Zero profit (break-even before costs) is not a passable edge either."""
    system = get_rigorous_validation_system()
    flat = _metrics(total_profit=0.0, total_return=0.0, total_trades=50)
    report = system.validate_strategy("flat", flat)
    assert report.deployment_recommendation == "REJECT"


def test_profitable_strategy_is_not_rejected_by_floor():
    """Sanity: a clearly profitable strategy must clear the profitability floor
    (it proceeds to normal scoring; we only assert the floor didn't veto it)."""
    system = get_rigorous_validation_system()
    winning = _metrics(total_profit=500.0, total_return=0.05, sharpe_ratio=1.2,
                       total_trades=60, win_rate=0.55, max_drawdown=0.08,
                       final_capital=10500.0)
    report = system.validate_strategy("winner", winning)
    # The profitability floor must not mark a profitable strategy as REJECT-via-floor.
    # (It may still be REJECT/CONDITIONAL/DEPLOY from the other validators, but the
    # floor itself passed -> overall score > 0 and not the zeroed floor report.)
    assert report.overall_validation_score > 0.0 or report.deployment_recommendation != "REJECT" \
        or "profitability_floor" not in report.individual_validations


def test_gate1_is_successful_rejects_money_losing_hypothesis():
    """Fix 5 (gate 1): a money-losing strategy must not pass HypothesisValidation
    even when trades/win_rate/sharpe/drawdown push the component score to 0.8."""
    from slate_core.discovery.closed_loop_discovery import HypothesisTestResult

    res = HypothesisTestResult(
        hypothesis=None,
        backtest_result={"total_profit": -15.75, "total_return": -0.001},
        validation_score=0.8, statistical_tests={}, surprises=[],
        failure_reasons=[], success_factors=[], regime_performance={}, cost_impact={},
    )
    assert res.is_successful() is False, (
        "money-losing hypothesis passed gate 1 (component score 0.8 >= 0.3)"
    )


def _valid_result(**overrides):
    """A complete, valid strategy_data dict for the persistence layer."""
    base = {
        "strategy_name": "t", "strategy_description": "d", "edge_type": "momentum",
        "total_profit_usdt": 100.0, "total_return_pct": 0.01,
        "final_capital": 10100.0, "initial_capital": 10000.0,
        "buy_hold_profit_usdt": -5000.0, "buy_hold_return_pct": -0.5,
        "vs_buy_hold_usdt": 5100.0, "beat_market": True,
        "max_drawdown_pct": 0.05, "max_drawdown_usdt": 500.0, "sharpe_ratio": 1.2,
        "total_trades": 50, "winning_trades": 28, "losing_trades": 22,
        "win_rate": 56.0, "total_funding_paid_usdt": 5.0, "total_funding_received_usdt": 2.0,
        "net_funding_usdt": -3.0, "avg_funding_daily_usdt": -0.1,
        "total_fees_usdt": 20.0, "total_slippage_usdt": 30.0, "total_transaction_costs_usdt": 53.0,
        "total_signals": 50, "filled_signals": 40, "partial_fills": 5,
        "period_start": "2026-01-01T00:00:00", "period_end": "2026-07-01T00:00:00",
        "start_price": 134.0, "end_price": 74.0, "timeframe": "1d",
        "passed_validation": 1, "timestamp": "2026-07-12T00:00:00",
    }
    base.update(overrides)
    return base


def test_save_discovery_refuses_money_loser(tmp_path):
    """Fix (a): the persistence choke point must refuse a money-losing result no
    matter which engine produced it (closes the swarm-path bypass that let a
    -$15.75 momentum_mean_reversion row be saved)."""
    import sqlite3
    from slate_core.discovery.perpetual_database import PerpetualDatabaseManager

    db = str(tmp_path / "t.db")
    mgr = PerpetualDatabaseManager(db)
    losing = _valid_result(strategy_name="swarm_loser", total_profit_usdt=-15.75,
                            vs_buy_hold_usdt=5123.69, beat_market=True)  # the mirage case
    saved = mgr.save_discovery(losing)
    assert saved is False, "money-losing discovery was persisted"
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM perpetual_discoveries").fetchone()[0]
    assert n == 0, f"{n} money-losing row(s) persisted"


def test_save_discovery_persists_profitable_result(tmp_path):
    """Sanity: the floor must not block a genuinely profitable result."""
    import sqlite3
    from slate_core.discovery.perpetual_database import PerpetualDatabaseManager

    db = str(tmp_path / "t.db")
    mgr = PerpetualDatabaseManager(db)
    saved = mgr.save_discovery(_valid_result(strategy_name="winner", total_profit_usdt=100.0))
    assert saved is True
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM perpetual_discoveries").fetchone()[0]
    assert n == 1
