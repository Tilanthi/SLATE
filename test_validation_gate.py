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
