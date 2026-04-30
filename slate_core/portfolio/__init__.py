#!/usr/bin/env python3
"""
SLATE Portfolio Management Module

Phase 6: PnL Portfolio Management (Weeks 21-24)

Components:
- Portfolio Optimization: Markowitz, CVaR, Black-Litterman
- Position Sizing: Kelly, Risk Parity, Target Volatility, CPPI
- Tail Risk Management: EVT, Stress Testing, Crash Protection

This phase optimizes portfolio-level returns while managing risk.

Author: SLATE Evolution
Date: 2026-04-30
Status: OPERATIONAL
"""

from .portfolio_optimization import (
    OptimizationMethod,
    Portfolio,
    PortfolioOptimizer,
    get_portfolio_optimizer
)

from .position_sizing import (
    SizingMethod,
    PositionSize,
    PositionSizingEngine,
    get_position_sizing_engine
)

from .tail_risk import (
    RiskEvent,
    TailRiskMetrics,
    TailRiskManager,
    get_tail_risk_manager
)

__all__ = [
    'OptimizationMethod',
    'Portfolio',
    'PortfolioOptimizer',
    'get_portfolio_optimizer',

    'SizingMethod',
    'PositionSize',
    'PositionSizingEngine',
    'get_position_sizing_engine',

    'RiskEvent',
    'TailRiskMetrics',
    'TailRiskManager',
    'get_tail_risk_manager'
]
