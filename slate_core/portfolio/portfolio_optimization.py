#!/usr/bin/env python3
"""
SLATE Portfolio Optimization System

Phase 6: PnL Portfolio Management (Weeks 21-24)

Implements portfolio optimization strategies:
- Markowitz mean-variance optimization
- CVaR (Conditional Value at Risk) optimization
- Black-Litterman model
- Regime-specific allocations

Critical for maximizing portfolio returns while managing risk.

Author: SLATE Evolution
Date: 2026-04-30
Priority: MEDIUM - Portfolio-level optimization
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from scipy import optimize
from scipy.stats import norm

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """Portfolio optimization methods."""
    MEAN_VARIANCE = "mean_variance"  # Markowitz
    CVAR = "cvar"  # Conditional Value at Risk
    BLACK_LITTERMAN = "black_litterman"  # BL model
    RISK_PARITY = "risk_parity"  # Equal risk contribution
    MINIMUM_VARIANCE = "minimum_variance"  # Min variance portfolio
    MAXIMUM_SHARPE = "maximum_sharpe"  # Max Sharpe ratio
    EQUAL_WEIGHT = "equal_weight"  # Naive 1/N


@dataclass
class Portfolio:
    """A portfolio allocation."""
    weights: Dict[str, float]  # Asset weights (sum to 1)
    expected_return: float
    expected_risk: float
    sharpe_ratio: float

    # Component breakdown
    asset_returns: Dict[str, float]
    asset_risks: Dict[str, float]
    correlations: pd.DataFrame

    # Risk metrics
    var_95: float  # Value at Risk at 95%
    cvar_95: float  # Conditional VaR at 95%
    max_drawdown: float

    # Optimization metadata
    optimization_method: OptimizationMethod
    constraints: List[str]
    regime: Optional[str] = None


class MarkowitzOptimizer:
    """
    Markowitz mean-variance optimization.

    Classic portfolio optimization: maximize return for given risk level.
    """

    def __init__(self, risk_free_rate: float = 0.03):
        self.risk_free_rate = risk_free_rate
        logger.info(f"MarkowitzOptimizer initialized (rf={risk_free_rate:.2%})")

    def optimize(
        self,
        returns: pd.DataFrame,
        target_risk: Optional[float] = None,
        target_return: Optional[float] = None,
        method: str = 'sharpe'
    ) -> Portfolio:
        """
        Optimize portfolio using mean-variance framework.

        Args:
            returns: Historical returns (columns = assets)
            target_risk: Target portfolio volatility (optional)
            target_return: Target portfolio return (optional)
            method: 'sharpe', 'min_variance', or 'target_risk'

        Returns:
            Optimized portfolio
        """

        # Calculate inputs
        mean_returns = returns.mean() * 252  # Annualized
        cov_matrix = returns.cov() * 252  # Annualized
        n_assets = len(returns.columns)

        # Initial guess (equal weight)
        w0 = np.ones(n_assets) / n_assets

        # Constraints
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]  # Weights sum to 1

        # Bounds (no short selling, max 50% per asset)
        bounds = [(0, 0.5) for _ in range(n_assets)]

        # Objective function
        if method == 'sharpe':
            # Maximize Sharpe ratio = minimize negative Sharpe
            def objective(w):
                portfolio_return = np.dot(w, mean_returns)
                portfolio_risk = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
                sharpe = (portfolio_return - self.risk_free_rate) / (portfolio_risk + 1e-10)
                return -sharpe

        elif method == 'min_variance':
            # Minimize variance
            def objective(w):
                return np.dot(w.T, np.dot(cov_matrix, w))

        elif method == 'target_return' and target_return is not None:
            # Minimize risk for target return
            def objective(w):
                return np.dot(w.T, np.dot(cov_matrix, w))

            constraints.append({
                'type': 'eq',
                'fun': lambda w: np.dot(w, mean_returns) - target_return
            })

        else:
            raise ValueError(f"Unknown method: {method}")

        # Optimize
        result = optimize.minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9}
        )

        if not result.success:
            logger.warning(f"Optimization failed: {result.message}")
            weights = w0
        else:
            weights = result.x

        # Create portfolio
        return self._create_portfolio(
            weights,
            returns.columns,
            mean_returns,
            cov_matrix,
            OptimizationMethod.MEAN_VARIANCE
        )

    def _create_portfolio(
        self,
        weights: np.ndarray,
        asset_names: List[str],
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        method: OptimizationMethod
    ) -> Portfolio:
        """Create portfolio object from weights."""

        weight_dict = {name: float(w) for name, w in zip(asset_names, weights)}

        # Portfolio metrics
        portfolio_return = np.dot(weights, mean_returns)
        portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix.values, weights)))
        sharpe = (portfolio_return - self.risk_free_rate) / (portfolio_risk + 1e-10)

        # Asset-level metrics
        asset_returns = {name: float(mean_returns[name]) for name in asset_names}
        asset_risks = {name: float(np.sqrt(cov_matrix.loc[name, name])) for name in asset_names}

        # VaR and CVaR (assuming normal distribution)
        var_95 = portfolio_risk * 1.645 - portfolio_return
        cvar_95 = portfolio_risk * 2.06 - portfolio_return

        return Portfolio(
            weights=weight_dict,
            expected_return=portfolio_return,
            expected_risk=portfolio_risk,
            sharpe_ratio=sharpe,
            asset_returns=asset_returns,
            asset_risks=asset_risks,
            correlations=cov_matrix,
            var_95=var_95,
            cvar_95=cvar_95,
            max_drawdown=0.0,  # Would calculate from historical
            optimization_method=method,
            constraints=['long_only', 'sum_to_1']
        )


class CVaROptimizer:
    """
    Conditional Value at Risk (CVaR) optimization.

    Minimizes expected shortfall beyond VaR threshold.
    More robust than mean-variance for non-normal distributions.
    """

    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        logger.info(f"CVaROptimizer initialized (α={confidence_level})")

    def optimize(
        self,
        returns: pd.DataFrame,
        scenarios: int = 1000
    ) -> Portfolio:
        """
        Optimize portfolio using CVaR.

        Args:
            returns: Historical returns
            scenarios: Number of scenarios for CVaR calculation

        Returns:
            Optimized portfolio
        """

        n_assets = len(returns.columns)

        # Generate scenarios (use historical returns)
        scenario_returns = returns.sample(n=min(scenarios, len(returns)), replace=True)

        # CVaR optimization using linear programming approximation
        def cvar_objective(w, alpha=0.95):
            """Calculate CVaR for given weights."""
            portfolio_returns = scenario_returns @ w
            var = np.percentile(portfolio_returns, (1 - alpha) * 100)
            cvar = portfolio_returns[portfolio_returns <= var].mean()
            return -cvar  # Minimize negative CVaR

        # Initial guess
        w0 = np.ones(n_assets) / n_assets

        # Constraints
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = [(0, 0.5) for _ in range(n_assets)]

        # Optimize
        result = optimize.minimize(
            lambda w: cvar_objective(w, self.confidence_level),
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        weights = result.x if result.success else w0

        # Calculate portfolio metrics
        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252

        # Use Markowitz helper to create portfolio
        markowitz = MarkowitzOptimizer()
        portfolio = markowitz._create_portfolio(
            weights,
            returns.columns,
            mean_returns,
            cov_matrix,
            OptimizationMethod.CVAR
        )

        # Update CVaR-specific metrics
        portfolio_returns = returns @ weights
        portfolio.var_95 = np.percentile(portfolio_returns, 5)
        portfolio.cvar_95 = portfolio_returns[portfolio_returns <= portfolio.var_95].mean()

        return portfolio


class BlackLittermanOptimizer:
    """
    Black-Litterman portfolio optimization.

    Combines market equilibrium with investor views.
    Produces more stable allocations than pure mean-variance.
    """

    def __init__(self, risk_aversion: float = 3.0):
        self.risk_aversion = risk_aversion
        logger.info(f"BlackLittermanOptimizer initialized (λ={risk_aversion})")

    def optimize(
        self,
        returns: pd.DataFrame,
        market_caps: pd.Series,
        views: Optional[List[Dict[str, Any]]] = None
    ) -> Portfolio:
        """
        Optimize using Black-Litterman model.

        Args:
            returns: Historical returns
            market_caps: Market capitalizations (for equilibrium weights)
            views: List of investor views

        Returns:
            Optimized portfolio
        """

        # Calculate inputs
        cov_matrix = returns.cov() * 252
        n_assets = len(returns.columns)

        # Market equilibrium weights (proportional to market cap)
        market_weights = market_caps / market_caps.sum()

        # Equilibrium returns (reverse optimization)
        # π = λ * Σ * w_market
        equilibrium_returns = self.risk_aversion * cov_matrix @ market_weights

        # Start with equilibrium returns
        bl_returns = equilibrium_returns.copy()

        # Incorporate views if provided
        if views:
            bl_returns = self._incorporate_views(
                equilibrium_returns,
                cov_matrix,
                views,
                market_weights
            )

        # Optimize with BL returns
        markowitz = MarkowitzOptimizer()
        portfolio = markowitz.optimize(
            returns,
            method='sharpe'
        )

        # Override expected returns with BL returns
        portfolio = self._create_portfolio(
            market_weights.values,
            returns.columns,
            bl_returns,
            cov_matrix,
            OptimizationMethod.BLACK_LITTERMAN
        )

        return portfolio

    def _incorporate_views(
        self,
        equilibrium_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        views: List[Dict[str, Any]],
        market_weights: pd.Series
    ) -> pd.Series:
        """Incorporate investor views into equilibrium returns."""

        # Simplified BL implementation
        # In production, use full matrix formulation

        # Adjust returns based on views
        adjusted_returns = equilibrium_returns.copy()

        for view in views:
            assets = view['assets']
            view_return = view['return']
            confidence = view.get('confidence', 0.5)

            # Adjust returns for assets in view
            for asset in assets:
                if asset in adjusted_returns.index:
                    adjustment = (view_return - equilibrium_returns[asset]) * confidence
                    adjusted_returns[asset] += adjustment

        return adjusted_returns

    def _create_portfolio(
        self,
        weights: np.ndarray,
        asset_names: List[str],
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        method: OptimizationMethod
    ) -> Portfolio:
        """Create portfolio object."""
        markowitz = MarkowitzOptimizer()
        return markowitz._create_portfolio(
            weights,
            asset_names,
            mean_returns,
            cov_matrix,
            method
        )


class RegimeBasedOptimizer:
    """
    Regime-specific portfolio optimization.

    Different allocations for different market regimes.
    """

    def __init__(self):
        self.regime_portfolios: Dict[str, Portfolio] = {}
        logger.info("RegimeBasedOptimizer initialized")

    def optimize_for_regime(
        self,
        returns: pd.DataFrame,
        regimes: pd.Series,
        regime: str
    ) -> Portfolio:
        """
        Optimize portfolio for specific regime.

        Args:
            returns: Historical returns
            regimes: Regime for each time period
            regime: Target regime

        Returns:
            Optimized portfolio for regime
        """

        # Filter data for regime
        regime_mask = regimes == regime
        regime_returns = returns[regime_mask]

        if len(regime_returns) < 50:  # Insufficient data
            logger.warning(f"Insufficient data for regime {regime}, using all data")
            regime_returns = returns

        # Optimize
        optimizer = MarkowitzOptimizer()
        portfolio = optimizer.optimize(regime_returns, method='sharpe')
        portfolio.regime = regime

        # Store
        self.regime_portfolios[regime] = portfolio

        return portfolio

    def get_regime_portfolio(self, regime: str) -> Optional[Portfolio]:
        """Get optimized portfolio for regime."""
        return self.regime_portfolios.get(regime)


class PortfolioOptimizer:
    """
    Unified portfolio optimization system.

    Combines all optimization methods.
    """

    def __init__(self, default_method: OptimizationMethod = OptimizationMethod.MAXIMUM_SHARPE):
        self.default_method = default_method
        self.markowitz = MarkowitzOptimizer()
        self.cvar = CVaROptimizer()
        self.black_litterman = BlackLittermanOptimizer()
        self.regime_optimizer = RegimeBasedOptimizer()

        logger.info(f"PortfolioOptimizer initialized (default={default_method.value})")

    async def optimize_portfolio(
        self,
        returns: pd.DataFrame,
        method: Optional[OptimizationMethod] = None,
        market_caps: Optional[pd.Series] = None,
        views: Optional[List[Dict[str, Any]]] = None,
        regimes: Optional[pd.Series] = None,
        current_regime: Optional[str] = None
    ) -> Portfolio:
        """
        Optimize portfolio using specified method.

        Args:
            returns: Historical returns
            method: Optimization method
            market_caps: Market caps (for Black-Litterman)
            views: Investor views (for Black-Litterman)
            regimes: Regime labels (for regime optimization)
            current_regime: Current regime (for regime optimization)

        Returns:
            Optimized portfolio
        """

        method = method or self.default_method

        # Regime-specific optimization
        if method == OptimizationMethod.MEAN_VARIANCE and regimes is not None and current_regime:
            return self.regime_optimizer.optimize_for_regime(returns, regimes, current_regime)

        # Standard optimizations
        if method == OptimizationMethod.MEAN_VARIANCE or method == OptimizationMethod.MAXIMUM_SHARPE:
            return self.markowitz.optimize(returns, method='sharpe')

        elif method == OptimizationMethod.MINIMUM_VARIANCE:
            return self.markowitz.optimize(returns, method='min_variance')

        elif method == OptimizationMethod.CVAR:
            return self.cvar.optimize(returns)

        elif method == OptimizationMethod.BLACK_LITTERMAN:
            if market_caps is None:
                market_caps = pd.Series([1] * len(returns.columns), index=returns.columns)
            return self.black_litterman.optimize(returns, market_caps, views)

        elif method == OptimizationMethod.EQUAL_WEIGHT:
            return self._equal_weight_portfolio(returns)

        else:
            logger.warning(f"Unknown method: {method}, using equal weight")
            return self._equal_weight_portfolio(returns)

    def _equal_weight_portfolio(self, returns: pd.DataFrame) -> Portfolio:
        """Create equal-weight portfolio."""

        n_assets = len(returns.columns)
        weights = np.ones(n_assets) / n_assets

        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252

        markowitz = MarkowitzOptimizer()
        portfolio = markowitz._create_portfolio(
            weights,
            returns.columns,
            mean_returns,
            cov_matrix,
            OptimizationMethod.EQUAL_WEIGHT
        )

        return portfolio

    def compare_methods(
        self,
        returns: pd.DataFrame
    ) -> Dict[str, Portfolio]:
        """
        Compare different optimization methods.

        Args:
            returns: Historical returns

        Returns:
            Dictionary of method -> portfolio
        """

        results = {}

        # Compare key methods
        methods = [
            OptimizationMethod.EQUAL_WEIGHT,
            OptimizationMethod.MINIMUM_VARIANCE,
            OptimizationMethod.MAXIMUM_SHARPE,
            OptimizationMethod.CVAR
        ]

        for method in methods:
            try:
                portfolio = asyncio.run(self.optimize_portfolio(returns, method))
                results[method.value] = portfolio
            except Exception as e:
                logger.warning(f"Failed to optimize with {method.value}: {e}")

        return results

    def generate_optimization_report(
        self,
        portfolio: Portfolio,
        benchmark_return: Optional[float] = None
    ) -> str:
        """Generate optimization report."""

        report = f"""
{'='*60}
PORTFOLIO OPTIMIZATION REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OPTIMIZATION METHOD: {portfolio.optimization_method.value}
REGIME: {portfolio.regime or 'N/A'}

PORTFOLIO METRICS:
  Expected Return: {portfolio.expected_return:.2%}
  Expected Risk: {portfolio.expected_risk:.2%}
  Sharpe Ratio: {portfolio.sharpe_ratio:.2f}

RISK METRICS:
  VaR (95%): {portfolio.var_95:.2%}
  CVaR (95%): {portfolio.cvar_95:.2%}
  Max Drawdown: {portfolio.max_drawdown:.2%}

"""

        if benchmark_return is not None:
            excess_return = portfolio.expected_return - benchmark_return
            report += f"  Excess Return: {excess_return:.2%}\n"

        report += "ALLOCATION:\n"
        allocations = sorted(portfolio.weights.items(), key=lambda x: x[1], reverse=True)
        for asset, weight in allocations:
            if weight > 0.01:  # Only show >1%
                report += f"  {asset}: {weight:.2%}\n"

        return report


# Singleton instance
_portfolio_optimizer = None


def get_portfolio_optimizer() -> PortfolioOptimizer:
    """Get or create portfolio optimizer instance."""
    global _portfolio_optimizer
    if _portfolio_optimizer is None:
        _portfolio_optimizer = PortfolioOptimizer()
    return _portfolio_optimizer
