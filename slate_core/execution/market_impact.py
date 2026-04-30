#!/usr/bin/env python3
"""
SLATE Market Impact Model

Phase 3: Brutally Realistic Execution Modeling

Implements institutional-grade market impact modeling:
- Almgren-Chriss model
- Square-root price impact
- Temporary vs permanent impact
- Participation rate optimization
- Order book depth effects

This ensures backtesting accounts for how our orders move prices.

Author: SLATE Evolution
Date: 2026-04-30
Priority: CRITICAL - Market impact erodes alpha
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from scipy.optimize import minimize_scalar

logger = logging.getLogger(__name__)


class ImpactModel(Enum):
    """Types of market impact models."""
    ALMGREN_CHRISS = "almgren_chriss"
    SQUARE_ROOT = "square_root"
    LINEAR = "linear"
    POWER_LAW = "power_law"


@dataclass
class MarketImpact:
    """Market impact calculation result."""
    order_size: float
    avg_daily_volume: float
    participation_rate: float
    permanent_impact_bps: float
    temporary_impact_bps: float
    total_impact_bps: float
    total_impact_usdt: float
    execution_price: float
    arrival_price: float
    price_displacement: float


@dataclass
class OptimalExecution:
    """Optimal execution parameters."""
    optimal_participation_rate: float
    expected_impact_bps: float
    expected_timing_seconds: int
    trade_schedule: List[Tuple[float, float]]  # (time, size)
    cost_benefit_analysis: Dict[str, float]


class AlmgrenChrissModel:
    """
    Almgren-Chriss market impact model.

    The standard model for institutional trading execution.

    Key assumptions:
    - Permanent impact: Linear in trade size
    - Temporary impact: Decay over time
    - Risk-averse optimization

    References:
    - Almgren & Chriss (2000): "Optimal Execution of Portfolio Transactions"
    """

    def __init__(self):
        # Model parameters (typical values for crypto)
        self.permanent_impact_lambda = 0.001  # Permanent impact coefficient
        self.temporary_impact_eta = 0.0001     # Temporary impact coefficient
        self.risk_aversion_gamma = 0.001       # Risk aversion parameter
        self.volatility_sigma = 0.02           # Daily volatility

        logger.info("AlmgrenChrissModel initialized")

    def calculate_impact(
        self,
        order_size: float,
        avg_daily_volume: float,
        arrival_price: float,
        participation_rate: float = 0.10,
        time_horizon_seconds: int = 3600
    ) -> MarketImpact:
        """
        Calculate market impact using Almgren-Chriss model.

        Args:
            order_size: Order size in USDT
            avg_daily_volume: Average daily volume in USDT
            arrival_price: Price at order arrival
            participation_rate: Fraction of ADV we trade (0-1)
            time_horizon_seconds: Execution time horizon

        Returns:
            MarketImpact with complete breakdown
        """

        # Calculate participation rate if not provided
        if participation_rate is None:
            participation_rate = min(order_size / avg_daily_volume, 0.5)

        # Normalized trade size
        normalized_size = order_size / avg_daily_volume

        # Permanent impact (linear in trade size)
        # Permanent impact persists throughout execution
        permanent_impact_bps = self.permanent_impact_lambda * normalized_size * 10000

        # Temporary impact (decays during execution)
        # Temporary impact depends on participation rate
        temporary_impact_bps = (self.temporary_impact_eta *
                               participation_rate *
                               10000)

        # Total impact
        total_impact_bps = permanent_impact_bps + temporary_impact_bps

        # Convert to USDT
        total_impact_usdt = (total_impact_bps / 10000) * order_size

        # Calculate execution price
        price_displacement = (total_impact_bps / 10000) * arrival_price
        execution_price = arrival_price + price_displacement

        return MarketImpact(
            order_size=order_size,
            avg_daily_volume=avg_daily_volume,
            participation_rate=participation_rate,
            permanent_impact_bps=permanent_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            total_impact_bps=total_impact_bps,
            total_impact_usdt=total_impact_usdt,
            execution_price=execution_price,
            arrival_price=arrival_price,
            price_displacement=price_displacement
        )

    def optimize_execution(
        self,
        order_size: float,
        avg_daily_volume: float,
        arrival_price: float,
        urgency: float = 0.5,
        max_participation: float = 0.20
    ) -> OptimalExecution:
        """
        Optimize execution parameters.

        Minimizes total cost: market impact + risk

        Args:
            order_size: Order size in USDT
            avg_daily_volume: Average daily volume
            arrival_price: Arrival price
            urgency: 0-1 (higher = faster execution)
            max_participation: Maximum participation rate

        Returns:
            OptimalExecution with optimal parameters
        """

        def total_cost(participation_rate):
            """Total cost function: impact + risk."""

            # Market impact cost
            impact = self.calculate_impact(
                order_size, avg_daily_volume, arrival_price, participation_rate
            )

            # Risk cost (variance from holding position)
            execution_time = order_size / (avg_daily_volume * participation_rate)
            risk_cost = self.risk_aversion_gamma * (self.volatility_sigma ** 2) * execution_time

            # Total cost (bps)
            return impact.total_impact_bps + risk_cost * 10000

        # Optimize participation rate
        result = minimize_scalar(
            total_cost,
            bounds=(0.01, max_participation),
            method='bounded'
        )

        optimal_participation = result.x
        expected_impact = self.calculate_impact(
            order_size, avg_daily_volume, arrival_price, optimal_participation
        )

        # Calculate execution timing
        execution_seconds = int(order_size / (avg_daily_volume * optimal_participation / 86400))

        # Generate trade schedule (simplified)
        num_slices = max(1, int(execution_seconds / 300))  # 5-minute intervals
        slice_size = order_size / num_slices
        trade_schedule = [(i * 300, slice_size) for i in range(num_slices)]

        # Cost-benefit analysis
        fast_impact = self.calculate_impact(
            order_size, avg_daily_volume, arrival_price, max_participation
        )

        slow_impact = self.calculate_impact(
            order_size, avg_daily_volume, arrival_price, 0.01
        )

        cost_benefit = {
            'optimal_cost_bps': result.fun,
            'fast_execution_cost_bps': fast_impact.total_impact_bps,
            'slow_execution_cost_bps': slow_impact.total_impact_bps,
            'savings_vs_fast': fast_impact.total_impact_bps - result.fun,
            'time_penalty_seconds': execution_seconds
        }

        return OptimalExecution(
            optimal_participation_rate=optimal_participation,
            expected_impact_bps=expected_impact.total_impact_bps,
            expected_timing_seconds=execution_seconds,
            trade_schedule=trade_schedule,
            cost_benefit_analysis=cost_benefit
        )


class SquareRootImpactModel:
    """
    Square-root impact model.

    Alternative to Almgren-Chriss, commonly used for:
    - Large institutional orders
    - Illiquid assets
    - High participation rates

    Formula: Impact = α * sqrt(Participation Rate)
    """

    def __init__(self):
        self.alpha = 5.0  # Impact coefficient (typical: 1-10)

        logger.info("SquareRootImpactModel initialized")

    def calculate_impact(
        self,
        order_size: float,
        avg_daily_volume: float,
        arrival_price: float
    ) -> MarketImpact:
        """Calculate impact using square-root model."""

        participation_rate = min(order_size / avg_daily_volume, 1.0)

        # Square-root impact
        impact_bps = self.alpha * np.sqrt(participation_rate) * 1.0  # 1 bps base

        # Convert to USDT
        impact_usdt = (impact_bps / 10000) * order_size

        # Calculate execution price
        price_displacement = (impact_bps / 10000) * arrival_price
        execution_price = arrival_price + price_displacement

        return MarketImpact(
            order_size=order_size,
            avg_daily_volume=avg_daily_volume,
            participation_rate=participation_rate,
            permanent_impact_bps=impact_bps * 0.7,  # Assume 70% permanent
            temporary_impact_bps=impact_bps * 0.3,  # 30% temporary
            total_impact_bps=impact_bps,
            total_impact_usdt=impact_usdt,
            execution_price=execution_price,
            arrival_price=arrival_price,
            price_displacement=price_displacement
        )


class OrderBookImpactModel:
    """
    Order book depth-based impact model.

    Uses order book shape to estimate price impact:
    - Gaussian mixture model for book shape
    - Depth-dependent impact
    - Non-linear impact for large orders

    More accurate than simple models but requires order book data.
    """

    def __init__(self):
        # Typical order book shape parameters
        self.bid_slope = 0.001  # Price impact per unit volume (bids)
        self.ask_slope = 0.001  # Price impact per unit volume (asks)
        self.book_depth = 100000  # Effective book depth in USDT

        logger.info("OrderBookImpactModel initialized")

    def calculate_impact_from_book(
        self,
        order_size: float,
        side: str,  # 'buy' or 'sell'
        order_book: Optional[Dict] = None
    ) -> MarketImpact:
        """
        Calculate impact from order book data.

        Args:
            order_size: Order size in USDT
            side: 'buy' or 'sell'
            order_book: Optional order book data
                     {bids: [(price, size), ...], asks: [(price, size), ...]}
        """

        if order_book and 'bids' in order_book and 'asks' in order_book:
            # Use actual order book data
            return self._calculate_from_real_book(order_size, side, order_book)
        else:
            # Use synthetic book model
            return self._calculate_from_synthetic_book(order_size, side)

    def _calculate_from_real_book(
        self,
        order_size: float,
        side: str,
        order_book: Dict
    ) -> MarketImpact:
        """Calculate impact using real order book data."""

        if side.lower() == 'buy':
            levels = order_book['asks']
            slope = self.ask_slope
        else:
            levels = order_book['bids']
            slope = self.bid_slope

        # Walk through the book
        remaining_size = order_size
        total_cost = 0.0
        weighted_price = 0.0

        for price, size in levels:
            if remaining_size <= 0:
                break

            # Take from this level
            take_size = min(remaining_size, size)
            total_cost += take_size * price
            weighted_price += take_size * price

            remaining_size -= take_size

        if remaining_size > 0:
            # Order too large for book
            logger.warning(f"Order size {order_size} exceeds available liquidity")
            # Assume linear extrapolation
            weighted_price += remaining_size * (levels[-1][0] * (1 + slope))

        avg_price = total_cost / order_size
        mid_price = (order_book['bids'][0][0] + order_book['asks'][0][0]) / 2

        impact_bps = abs(avg_price - mid_price) / mid_price * 10000

        return MarketImpact(
            order_size=order_size,
            avg_daily_volume=self.book_depth * 10,  # Estimate
            participation_rate=order_size / (self.book_depth * 10),
            permanent_impact_bps=impact_bps * 0.5,
            temporary_impact_bps=impact_bps * 0.5,
            total_impact_bps=impact_bps,
            total_impact_usdt=(impact_bps / 10000) * order_size,
            execution_price=avg_price,
            arrival_price=mid_price,
            price_displacement=avg_price - mid_price
        )

    def _calculate_from_synthetic_book(
        self,
        order_size: float,
        side: str
    ) -> MarketImpact:
        """Calculate impact using synthetic book model."""

        participation_rate = order_size / self.book_depth

        # Impact grows non-linearly with participation
        if side.lower() == 'buy':
            slope = self.ask_slope
        else:
            slope = self.bid_slope

        # Non-linear impact function
        impact_bps = slope * (participation_rate ** 0.75) * 10000

        # Assume arrival price of $100 (for calculation)
        arrival_price = 100.0
        price_displacement = (impact_bps / 10000) * arrival_price

        return MarketImpact(
            order_size=order_size,
            avg_daily_volume=self.book_depth * 10,
            participation_rate=participation_rate,
            permanent_impact_bps=impact_bps * 0.6,
            temporary_impact_bps=impact_bps * 0.4,
            total_impact_bps=impact_bps,
            total_impact_usdt=(impact_bps / 10000) * order_size,
            execution_price=arrival_price + price_displacement,
            arrival_price=arrival_price,
            price_displacement=price_displacement
        )


class MarketImpactModel:
    """
    Unified market impact model.

    Combines all impact models and provides intelligent model selection.
    """

    def __init__(self):
        self.almgren_chriss = AlmgrenChrissModel()
        self.square_root = SquareRootImpactModel()
        self.order_book = OrderBookImpactModel()

        self.default_model = ImpactModel.ALMGREN_CHRISS

        logger.info("MarketImpactModel initialized")

    async def calculate_impact(
        self,
        order_size: float,
        avg_daily_volume: float,
        arrival_price: float,
        model: ImpactModel = None,
        **kwargs
    ) -> MarketImpact:
        """
        Calculate market impact using specified model.

        Args:
            order_size: Order size in USDT
            avg_daily_volume: Average daily volume
            arrival_price: Arrival price
            model: Impact model to use
            **kwargs: Model-specific parameters

        Returns:
            MarketImpact with complete breakdown
        """

        if model is None:
            model = self.default_model

        # Select model based on order characteristics
        if model == ImpactModel.ALMGREN_CHRISS:
            return self.almgren_chriss.calculate_impact(
                order_size, avg_daily_volume, arrival_price,
                kwargs.get('participation_rate'),
                kwargs.get('time_horizon_seconds', 3600)
            )

        elif model == ImpactModel.SQUARE_ROOT:
            return self.square_root.calculate_impact(
                order_size, avg_daily_volume, arrival_price
            )

        else:
            # Default to Almgren-Chriss
            return self.almgren_chriss.calculate_impact(
                order_size, avg_daily_volume, arrival_price
            )

    async def optimize_execution(
        self,
        order_size: float,
        avg_daily_volume: float,
        arrival_price: float,
        urgency: float = 0.5
    ) -> OptimalExecution:
        """
        Optimize execution parameters.

        Returns optimal participation rate and timing.
        """

        return self.almgren_chriss.optimize_execution(
            order_size, avg_daily_volume, arrival_price, urgency
        )

    def generate_impact_report(self, impact: MarketImpact) -> str:
        """Generate detailed impact report."""

        report = f"""
MARKET IMPACT REPORT
{'='*40}
Order Size: ${impact.order_size:,.2f}
ADV: ${impact.avg_daily_volume:,.2f}
Participation Rate: {impact.participation_rate:.2%}

IMPACT BREAKDOWN:
  Permanent Impact: {impact.permanent_impact_bps:.2f} bps
  Temporary Impact: {impact.temporary_impact_bps:.2f} bps
  Total Impact: {impact.total_impact_bps:.2f} bps

PRICE EFFECTS:
  Arrival Price: ${impact.arrival_price:.2f}
  Execution Price: ${impact.execution_price:.2f}
  Price Displacement: {impact.price_displacement:.4f} ({impact.total_impact_bps:.2f} bps)

COST:
  Total Impact Cost: ${impact.total_impact_usdt:.2f}
  Cost as % of Order: {(impact.total_impact_usdt / impact.order_size) * 100:.4f}%
"""
        return report


# Singleton instance
_market_impact_model = None


def get_market_impact_model() -> MarketImpactModel:
    """Get or create market impact model instance."""
    global _market_impact_model
    if _market_impact_model is None:
        _market_impact_model = MarketImpactModel()
    return _market_impact_model
