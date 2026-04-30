#!/usr/bin/env python3
"""
SLATE Partial Fill and Slippage Model

Phase 3: Brutally Realistic Execution Modeling

Models realistic execution frictions:
- Order book depth-dependent fills
- Volatility-adjusted slippage
- Time-of-day fill rates
- Iceberg order simulation
- Partial execution handling

This ensures backtesting reflects real-world execution challenges.

Author: SLATE Evolution
Date: 2026-04-30
Priority: CRITICAL - Partial fills significantly affect PnL
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

logger = logging.getLogger(__name__)


class FillQuality(Enum):
    """Quality of order fill."""
    EXCELLENT = "excellent"  # Filled at limit or better
    GOOD = "good"  # Filled near limit with minor slippage
    POOR = "poor"  # Significant slippage
    PARTIAL = "partial"  # Only partially filled


@dataclass
class FillResult:
    """Result of order execution attempt."""
    order_id: str
    requested_size: float
    filled_size: float
    fill_price: float
    limit_price: Optional[float]
    slippage_bps: float
    fill_quality: FillQuality
    fill_time_seconds: int
    remaining_size: float
    execution_cost_usdt: float


class OrderBookSimulator:
    """
    Simulate realistic order book behavior.

    Models:
    - Depth-dependent fills
    - Shape of order book
    - Time-varying liquidity
    """

    def __init__(self):
        # Order book shape parameters
        self.book_depth_impact = 0.001  # Price impact per depth percentile
        self.max_depth_bps = 50.0  # Maximum slippage at full depth

        # Liquidity parameters
        self.base_liquidity_usdt = 100000.0  # Base liquidity at top of book
        self.depth_decay = 0.7  # How fast liquidity decays with depth

        logger.info("OrderBookSimulator initialized")

    def get_available_liquidity(
        self,
        symbol: str,
        side: str,
        depth_bps: float = 5.0
    ) -> float:
        """
        Get available liquidity at specified depth.

        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            depth_bps: Depth in basis points from mid

        Returns:
            Available liquidity in USDT
        """

        # Liquidity decays exponentially with depth
        depth_factor = np.exp(-depth_bps / 10.0)  # Decay parameter
        available = self.base_liquidity_usdt * depth_factor

        return max(available, 1000.0)  # Minimum liquidity

    def simulate_fill(
        self,
        order_size: float,
        side: str,
        limit_price: Optional[float] = None,
        market_price: float = 100.0,
        volatility: float = 0.02
    ) -> FillResult:
        """
        Simulate order fill with realistic book dynamics.

        Args:
            order_size: Order size in USDT
            side: 'buy' or 'sell'
            limit_price: Limit price (None for market order)
            market_price: Current market price
            volatility: Current volatility

        Returns:
            FillResult with execution details
        """

        order_id = f"order_{datetime.now().timestamp()}"

        # Check available liquidity at limit price
        if limit_price is not None:
            depth_bps = abs(limit_price - market_price) / market_price * 10000
            available_liquidity = self.get_available_liquidity("BTCUSDT", side, depth_bps)
        else:
            # Market order - use wider depth
            available_liquidity = self.get_available_liquidity("BTCUSDT", side, 10.0)

        # Determine fill size
        if order_size <= available_liquidity:
            # Full fill likely
            fill_probability = 0.95
        else:
            # Partial fill likely
            fill_probability = 0.7 * (available_liquidity / order_size)

        # Apply volatility adjustment (high vol = worse fills)
        vol_adjustment = 1.0 / (1.0 + volatility * 10)
        fill_probability *= vol_adjustment

        # Simulate fill
        filled_size = order_size * fill_probability

        # Calculate slippage
        if limit_price is None:
            # Market order slippage
            depth_impact = self._calculate_depth_impact(filled_size, side)
            slippage_bps = depth_impact * 10000
        else:
            # Limit order slippage (minimal if filled)
            slippage_bps = 1.0  # Small slippage even for limit orders

        # Calculate fill price
        if side.lower() == 'buy':
            fill_price = market_price * (1 + slippage_bps / 10000)
        else:
            fill_price = market_price * (1 - slippage_bps / 10000)

        # Respect limit price
        if limit_price is not None:
            if side.lower() == 'buy' and fill_price > limit_price:
                fill_price = limit_price
                filled_size = min(filled_size, available_liquidity)
            elif side.lower() == 'sell' and fill_price < limit_price:
                fill_price = limit_price
                filled_size = min(filled_size, available_liquidity)

        # Determine fill quality
        if filled_size >= order_size * 0.95:
            if slippage_bps < 2:
                fill_quality = FillQuality.EXCELLENT
            elif slippage_bps < 5:
                fill_quality = FillQuality.GOOD
            else:
                fill_quality = FillQuality.POOR
        else:
            fill_quality = FillQuality.PARTIAL

        # Calculate execution cost
        execution_cost_usdt = abs(fill_price - market_price) / market_price * filled_size

        return FillResult(
            order_id=order_id,
            requested_size=order_size,
            filled_size=filled_size,
            fill_price=fill_price,
            limit_price=limit_price,
            slippage_bps=slippage_bps,
            fill_quality=fill_quality,
            fill_time_seconds=int(np.random.exponential(30)),  # Average 30 seconds
            remaining_size=max(0, order_size - filled_size),
            execution_cost_usdt=execution_cost_usdt
        )

    def _calculate_depth_impact(self, size: float, side: str) -> float:
        """Calculate price impact based on order size."""

        # Square-root impact model
        participation_rate = size / self.base_liquidity_usdt
        impact = self.book_depth_impact * np.sqrt(participation_rate)

        return impact


class VolatilityAdjustedSlippageModel:
    """
    Volatility-adjusted slippage model.

    Higher volatility = higher slippage
    Volatility clustering effects
    """

    def __init__(self):
        self.base_slippage_bps = 2.0  # Base slippage for normal volatility
        self.volatility_multiplier = 50.0  # How much vol affects slippage

        logger.info("VolatilityAdjustedSlippageModel initialized")

    def calculate_slippage(
        self,
        order_size: float,
        avg_daily_volume: float,
        volatility: float,
        time_of_day: Optional[datetime] = None
    ) -> float:
        """
        Calculate volatility-adjusted slippage.

        Args:
            order_size: Order size in USDT
            avg_daily_volume: Average daily volume
            volatility: Current volatility (std dev of returns)
            time_of_day: Execution time (affects slippage)

        Returns:
            Slippage in basis points
        """

        # Participation rate
        participation = order_size / avg_daily_volume

        # Base slippage (square-root law)
        base_slippage = self.base_slippage_bps * np.sqrt(participation * 100)

        # Volatility adjustment
        vol_adjustment = 1.0 + (volatility * self.volatility_multiplier)

        # Time-of-day adjustment (worse during volatile times)
        if time_of_day:
            hour = time_of_day.hour
            # Higher slippage during market open/close
            if hour in [8, 9, 16, 17, 18]:  # Open/close times
                vol_adjustment *= 1.5

        total_slippage_bps = base_slippage * vol_adjustment

        return min(total_slippage_bps, 100.0)  # Cap at 100 bps


class PartialFillSimulator:
    """
    Simulate partial fill scenarios.

    Models:
    - Time-dependent fill rates
    - Iceberg orders
    - Multi-part execution
    """

    def __init__(self):
        self.fill_rate_decay = 0.8  # Fill rate decay per retry
        self.max_retries = 3

        # Time-of-day fill rates (relative to baseline)
        self.hourly_fill_rates = {
            # Asian session (lower fills)
            0: 0.8, 1: 0.7, 2: 0.6, 3: 0.5, 4: 0.5, 5: 0.6, 6: 0.8, 7: 0.9,
            # European session (better fills)
            8: 1.0, 9: 1.1, 10: 1.2, 11: 1.2, 12: 1.1, 13: 1.0,
            14: 1.0, 15: 1.1, 16: 1.2,
            # US session (best fills)
            17: 1.3, 18: 1.4, 19: 1.3, 20: 1.2, 21: 1.0, 22: 0.9, 23: 0.8
        }

        logger.info("PartialFillSimulator initialized")

    def get_fill_probability(
        self,
        order_size: float,
        liquidity: float,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Get probability of order being filled.

        Args:
            order_size: Order size
            liquidity: Available liquidity
            timestamp: Order timestamp

        Returns:
            Fill probability (0-1)
        """

        # Base fill probability
        if order_size <= liquidity:
            base_prob = 0.95
        else:
            base_prob = 0.5 * (liquidity / order_size)

        # Time-of-day adjustment
        if timestamp:
            hour = timestamp.hour
            time_multiplier = self.hourly_fill_rates.get(hour, 1.0)
            base_prob *= time_multiplier

        return max(0.1, min(base_prob, 0.99))  # Clamp between 10% and 99%

    def simulate_iceberg_execution(
        self,
        total_size: float,
        slice_size: float,
        num_slices: int,
        market_price: float = 100.0
    ) -> List[FillResult]:
        """
        Simulate iceberg order execution.

        Args:
            total_size: Total order size
            slice_size: Size of each visible slice
            num_slices: Number of slices to attempt
            market_price: Current market price

        Returns:
            List of FillResult for each slice
        """

        results = []
        remaining_size = total_size

        for i in range(num_slices):
            if remaining_size <= 0:
                break

            current_slice = min(slice_size, remaining_size)

            # Simulate fill for this slice
            # Later slices have worse fill rates
            fill_prob = 0.9 * (self.fill_rate_decay ** i)

            if np.random.random() < fill_prob:
                filled = current_slice
            else:
                filled = current_slice * 0.5  # Partial fill

            # Calculate slippage (worse for later slices)
            slippage_bps = 1.0 + i * 2.0  # Increasing slippage

            results.append(FillResult(
                order_id=f"iceberg_slice_{i}",
                requested_size=current_slice,
                filled_size=filled,
                fill_price=market_price * (1 + slippage_bps / 10000),
                limit_price=None,
                slippage_bps=slippage_bps,
                fill_quality=FillQuality.GOOD if filled >= current_slice * 0.9 else FillQuality.PARTIAL,
                fill_time_seconds=30 * (i + 1),
                remaining_size=max(0, remaining_size - filled),
                execution_cost_usdt=(slippage_bps / 10000) * filled
            ))

            remaining_size -= filled

        return results


class RealisticExecutionModel:
    """
    Unified realistic execution model.

    Combines all execution frictions:
    - Transaction costs
    - Market impact
    - Partial fills
    - Slippage
    - Timing effects

    This is the primary interface for realistic backtesting.
    """

    def __init__(self):
        self.order_book = OrderBookSimulator()
        self.slippage_model = VolatilityAdjustedSlippageModel()
        self.partial_fill = PartialFillSimulator()

        logger.info("RealisticExecutionModel initialized")

    async def simulate_order_execution(
        self,
        order_size: float,
        side: str,
        limit_price: Optional[float] = None,
        market_price: float = 100.0,
        volatility: float = 0.02,
        avg_daily_volume: float = 1000000.0,
        timestamp: Optional[datetime] = None
    ) -> Tuple[FillResult, float]:
        """
        Simulate realistic order execution.

        Args:
            order_size: Order size in USDT
            side: 'buy' or 'sell'
            limit_price: Limit price (None for market)
            market_price: Current market price
            volatility: Current volatility
            avg_daily_volume: Average daily volume
            timestamp: Execution timestamp

        Returns:
            (FillResult, total_cost_bps)
        """

        # Step 1: Calculate slippage
        slippage_bps = self.slippage_model.calculate_slippage(
            order_size, avg_daily_volume, volatility, timestamp
        )

        # Step 2: Simulate fill with order book
        fill_result = self.order_book.simulate_fill(
            order_size, side, limit_price, market_price, volatility
        )

        # Step 3: Adjust for partial fills
        fill_prob = self.partial_fill.get_fill_probability(
            order_size, avg_daily_volume * 0.01, timestamp
        )

        # Apply partial fill probability
        if np.random.random() > fill_prob:
            # Partial fill
            fill_result.filled_size *= 0.7
            fill_result.fill_quality = FillQuality.PARTIAL
            fill_result.remaining_size = order_size - fill_result.filled_size

        # Step 4: Calculate total cost
        # Cost = slippage + opportunity cost of unfilled portion
        slippage_cost = slippage_bps * fill_result.filled_size / order_size
        opportunity_cost = (order_size - fill_result.filled_size) / order_size * 10.0  # 10 bps opportunity cost

        total_cost_bps = slippage_cost + opportunity_cost

        return fill_result, total_cost_bps

    def generate_execution_report(self, fill_result: FillResult, total_cost_bps: float) -> str:
        """Generate detailed execution report."""

        report = f"""
REALISTIC EXECUTION REPORT
{'='*40}
Order ID: {fill_result.order_id}
Side: {'BUY' if fill_result.limit_price is None or fill_result.fill_price <= fill_result.limit_price else 'SELL'}

EXECUTION RESULTS:
  Requested: ${fill_result.requested_size:,.2f}
  Filled: ${fill_result.filled_size:,.2f}
  Fill Rate: {(fill_result.filled_size / fill_result.requested_size) * 100:.1f}%
  Remaining: ${fill_result.remaining_size:,.2f}

PRICE DETAILS:
  Market Price: ${fill_result.limit_price or 'N/A'} (limit)
  Fill Price: ${fill_result.fill_price:.2f}
  Slippage: {fill_result.slippage_bps:.2f} bps
  Execution Cost: ${fill_result.execution_cost:.4f}

FILL QUALITY: {fill_result.fill_quality.value.upper()}
Fill Time: {fill_result.fill_time_seconds} seconds

TOTAL COST: {total_cost_bps:.2f} bps
"""
        return report


# Singleton instance
_realistic_execution_model = None


def get_realistic_execution_model() -> RealisticExecutionModel:
    """Get or create realistic execution model instance."""
    global _realistic_execution_model
    if _realistic_execution_model is None:
        _realistic_execution_model = RealisticExecutionModel()
    return _realistic_execution_model
