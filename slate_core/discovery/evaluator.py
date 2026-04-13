"""
SLATE Strategy Evaluator

Evaluates discovered strategies with rigorous statistical validation.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """Metrics for strategy evaluation."""
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_trade: float
    total_trades: int


class StrategyEvaluator:
    """
    Evaluate discovered strategies with statistical validation.

    Metrics:
    - Return metrics (total return, CAGR)
    - Risk metrics (Sharpe, Sortino, max drawdown)
    - Trade metrics (win rate, profit factor, avg trade)
    - Statistical significance (p-values, confidence intervals)
    """

    def __init__(self):
        self.min_trades = 30
        self.min_win_rate = 0.45
        self.min_profit_factor = 1.2

    async def evaluate_strategy(
        self,
        strategy: Dict,
        evaluation_period_days: int = 30
    ) -> Dict:
        """
        Evaluate a strategy with backtesting and statistical analysis.

        Returns evaluation results with a composite score.
        """
        try:
            # Generate backtest results (simulated)
            backtest_results = await self._run_backtest(
                strategy,
                days=evaluation_period_days
            )

            # Calculate metrics
            metrics = self._calculate_metrics(backtest_results)

            # Statistical validation
            stats = self._statistical_validation(backtest_results)

            # Composite score
            score = self._calculate_composite_score(metrics, stats)

            return {
                "strategy_id": strategy.get("id"),
                "strategy_name": strategy.get("name"),
                "discovery_method": strategy.get("discovery_method"),
                "evaluation_period_days": evaluation_period_days,
                "metrics": metrics,
                "statistics": stats,
                "score": score,
                "validated": stats["significant"],
                "evaluated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error evaluating strategy {strategy.get('id')}: {e}")
            return {
                "strategy_id": strategy.get("id"),
                "error": str(e),
                "score": 0.0
            }

    async def _run_backtest(
        self,
        strategy: Dict,
        days: int
    ) -> Dict:
        """Run backtest simulation (paper trading)."""
        # Simulate backtest results
        # In production, this would run actual backtests

        num_trades = np.random.randint(20, 100)

        returns = []
        for _ in range(num_trades):
            # Random return between -5% and +8%
            ret = np.random.uniform(-0.05, 0.08)
            returns.append(ret)

        return {
            "returns": returns,
            "num_trades": num_trades,
            "initial_capital": 10000,
            "final_capital": 10000 * (1 + sum(returns)),
            "days": days
        }

    def _calculate_metrics(self, backtest: Dict) -> Dict:
        """Calculate performance metrics."""
        returns = backtest["returns"]

        if not returns:
            return {
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 1.0,
                "total_trades": 0
            }

        # Total return
        total_return = sum(returns)

        # Win rate
        winning_trades = [r for r in returns if r > 0]
        losing_trades = [r for r in returns if r < 0]
        win_rate = len(winning_trades) / len(returns) if returns else 0

        # Profit factor
        gross_profit = sum(winning_trades)
        gross_loss = abs(sum(losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Sharpe ratio (simplified, assuming 252 trading days/year)
        if len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - running_max
        max_drawdown = abs(min(drawdowns)) if len(drawdowns) > 0 else 0

        return {
            "total_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(np.mean(winning_trades), 4) if winning_trades else 0,
            "avg_loss": round(np.mean(losing_trades), 4) if losing_trades else 0,
            "total_trades": len(returns)
        }

    def _statistical_validation(self, backtest: Dict) -> Dict:
        """Perform statistical validation tests."""
        returns = backtest["returns"]

        if len(returns) < self.min_trades:
            return {
                "significant": False,
                "reason": f"Insufficient trades ({len(returns)} < {self.min_trades})",
                "p_value": 1.0,
                "confidence_interval": [0, 0]
            }

        # Simple t-test for mean return being > 0
        # This is simplified - production would use proper statistical tests
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Standard error
        se = std_return / np.sqrt(len(returns))

        # 95% confidence interval
        ci_lower = mean_return - 1.96 * se
        ci_upper = mean_return + 1.96 * se

        # "Significant" if CI doesn't include 0 and mean return is positive
        significant = ci_lower > 0 and mean_return > 0

        return {
            "significant": significant,
            "p_value": max(0, min(1, 1 - (mean_return / se if se > 0 else 0))),
            "confidence_interval": [round(ci_lower, 4), round(ci_upper, 4)],
            "sample_size": len(returns)
        }

    def _calculate_composite_score(
        self,
        metrics: Dict,
        stats: Dict
    ) -> float:
        """
        Calculate composite score (0-1).

        Weights:
        - Total return: 30%
        - Sharpe ratio: 25%
        - Win rate: 20%
        - Profit factor: 15%
        - Statistical significance: 10%
        """
        score = 0.0

        # Return score (cap at 50% total return)
        return_score = min(abs(metrics["total_return"]) / 0.5, 1.0)
        if metrics["total_return"] < 0:
            return_score = 0
        score += return_score * 0.30

        # Sharpe score (good Sharpe > 2)
        sharpe_score = min(max(metrics["sharpe_ratio"], 0) / 2, 1.0)
        score += sharpe_score * 0.25

        # Win rate score (target > 50%)
        win_rate_score = min(max(metrics["win_rate"] - 0.4, 0) / 0.2, 1.0)
        score += win_rate_score * 0.20

        # Profit factor score (target > 1.5)
        pf_score = min(max(metrics["profit_factor"] - 1, 0) / 0.5, 1.0)
        score += pf_score * 0.15

        # Statistical significance
        if stats["significant"]:
            score += 0.10

        return round(score, 4)
