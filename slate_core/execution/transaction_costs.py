#!/usr/bin/env python3
"""
SLATE Advanced Transaction Cost Model

Phase 3: Brutally Realistic Execution Modeling

Implements institutional-grade transaction cost modeling for:
- Exchange-specific fee schedules
- VIP tier structures
- Time-of-day fee variations
- Funding rates (perpetual futures)
- Short borrowing costs
- Maker vs taker fees

This ensures backtesting results reflect real-world trading costs.

Author: SLATE Evolution
Date: 2026-04-30
Priority: CRITICAL - Realism prevents surprises
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class Exchange(Enum):
    """Supported exchanges."""
    BINANCE_PERPETUAL = "binance_perpetual"
    BITGET_PERPETUAL = "bitget_perpetual"
    BINANCE_SPOT = "binance_spot"


class OrderType(Enum):
    """Order types for fee calculation."""
    MAKER = "maker"  # Limit order resting on book
    TAKER = "taker"  # Market or marketable limit


class VIPTier(Enum):
    """VIP tiers for fee discounts."""
    REGULAR = 0
    VIP_1 = 1
    VIP_2 = 2
    VIP_3 = 3
    VIP_4 = 4
    VIP_5 = 5
    VIP_6 = 6
    VIP_7 = 7
    VIP_8 = 8
    VIP_9 = 9


@dataclass
class FeeSchedule:
    """Exchange fee schedule."""
    exchange: Exchange
    maker_fee_bps: float  # Basis points
    taker_fee_bps: float
    vip_discounts: Dict[VIPTier, float]  # Discount percentages
    min_notional: float  # Minimum order size
    max_order_size: float  # Maximum order size
    fee_currency: str = "USDT"


@dataclass
class TransactionCost:
    """Transaction cost breakdown."""
    exchange: Exchange
    order_type: OrderType
    notional_value: float
    base_fee: float
    vip_discount: float
    final_fee: float
    fee_percentage: float
    funding_cost: float = 0.0
    borrowing_cost: float = 0.0
    total_cost: float = 0.0


class ExchangeFeeManager:
    """
    Manage exchange-specific fee schedules.

    Real fees as of 2026-04-30.
    """

    def __init__(self):
        self.fee_schedules: Dict[Exchange, FeeSchedule] = {}
        self._initialize_fee_schedules()

        logger.info("ExchangeFeeManager initialized with real fee schedules")

    def _initialize_fee_schedules(self):
        """Initialize fee schedules for all supported exchanges."""

        # Binance USDT-M Perpetual Futures
        self.fee_schedules[Exchange.BINANCE_PERPETUAL] = FeeSchedule(
            exchange=Exchange.BINANCE_PERPETUAL,
            maker_fee_bps=0.02,  # 0.02% maker fee
            taker_fee_bps=0.05,  # 0.05% taker fee
            vip_discounts={
                VIPTier.REGULAR: 0.00,
                VIPTier.VIP_1: 0.10,   # 10% discount
                VIPTier.VIP_2: 0.15,
                VIPTier.VIP_3: 0.20,
                VIPTier.VIP_4: 0.25,
                VIPTier.VIP_5: 0.30,
                VIPTier.VIP_6: 0.35,
                VIPTier.VIP_7: 0.40,
                VIPTier.VIP_8: 0.45,
                VIPTier.VIP_9: 0.50,   # 50% discount
            },
            min_notional=5.0,  # $5 minimum
            max_order_size=1000000.0,  # $1M max
            fee_currency="USDT"
        )

        # Bitget Perpetual Futures
        self.fee_schedules[Exchange.BITGET_PERPETUAL] = FeeSchedule(
            exchange=Exchange.BITGET_PERPETUAL,
            maker_fee_bps=0.02,  # 0.02% maker fee
            taker_fee_bps=0.06,  # 0.06% taker fee (slightly higher)
            vip_discounts={
                VIPTier.REGULAR: 0.00,
                VIPTier.VIP_1: 0.05,
                VIPTier.VIP_2: 0.10,
                VIPTier.VIP_3: 0.15,
                VIPTier.VIP_4: 0.20,
                VIPTier.VIP_5: 0.25,
            },
            min_notional=5.0,
            max_order_size=500000.0,
            fee_currency="USDT"
        )

        # Binance Spot
        self.fee_schedules[Exchange.BINANCE_SPOT] = FeeSchedule(
            exchange=Exchange.BINANCE_SPOT,
            maker_fee_bps=0.10,  # 0.10% maker fee (spot is higher)
            taker_fee_bps=0.10,  # 0.10% taker fee
            vip_discounts={
                VIPTier.REGULAR: 0.00,
                VIPTier.VIP_1: 0.20,   # 20% discount
                VIPTier.VIP_2: 0.40,
                VIPTier.VIP_3: 0.60,
                VIPTier.VIP_4: 0.70,
                VIPTier.VIP_5: 0.80,
            },
            min_notional=10.0,
            max_order_size=50000.0,
            fee_currency="USDT"
        )

    def get_fee_schedule(self, exchange: Exchange) -> FeeSchedule:
        """Get fee schedule for an exchange."""
        return self.fee_schedules.get(exchange)


class PerpetualFundingCalculator:
    """
    Calculate funding rates for perpetual futures.

    Funding rates are periodic payments between longs and shorts
    to anchor perpetual prices to spot prices.
    """

    def __init__(self):
        self.funding_history = {}

        # Typical funding rates (can be overridden with real data)
        self.typical_funding_rates = {
            'BTCUSDT': 0.0001,   # 0.01% per 8 hours
            'ETHUSDT': 0.00012,
            'SOLUSDT': 0.00015,
            'BNBUSDT': 0.0001,
            'default': 0.0001
        }

        logger.info("PerpetualFundingCalculator initialized")

    def calculate_funding_cost(
        self,
        symbol: str,
        position_size: float,
        position_side: str,  # 'long' or 'short'
        hours_held: float,
        funding_rate: Optional[float] = None
    ) -> float:
        """
        Calculate funding cost for holding a perpetual position.

        Args:
            symbol: Trading pair
            position_size: Position size in USDT
            position_side: 'long' or 'short'
            hours_held: Hours position held
            funding_rate: Annualized funding rate (if None, uses typical)

        Returns:
            Funding cost (positive = cost, negative = earned)
        """

        # Get funding rate
        if funding_rate is None:
            funding_rate = self.typical_funding_rates.get(
                symbol,
                self.typical_funding_rates['default']
            )

        # Funding is typically every 8 hours
        funding_periods = hours_held / 8.0

        # Calculate funding
        funding_payment = position_size * funding_rate * funding_periods

        # Longs pay if funding is positive, shorts receive
        # Shorts pay if funding is negative, longs receive
        if position_side.lower() == 'long':
            return funding_payment  # Positive = cost
        else:
            return -funding_payment  # Negative = cost (positive funding = shorts earn)

    def get_funding_rate_impact(
        self,
        symbol: str,
        position_value: float,
        holding_period_hours: float = 24.0
    ) -> Dict[str, float]:
        """Get funding rate impact for both long and short positions."""

        long_cost = self.calculate_funding_cost(
            symbol, position_value, 'long', holding_period_hours
        )

        short_cost = self.calculate_funding_cost(
            symbol, position_value, 'short', holding_period_hours
        )

        return {
            'long_cost_bps': (long_cost / position_value) * 10000,
            'short_cost_bps': (short_cost / position_value) * 10000,
            'long_cost_usdt': long_cost,
            'short_cost_usdt': short_cost,
            'funding_rate': self.typical_funding_rates.get(symbol, 0.0001)
        }


class ShortBorrowingCostCalculator:
    """
    Calculate short borrowing costs for perpetual futures.

    Shorting perpetuals doesn't require borrowing, but there's
    still a cost associated with the short position via funding.
    """

    def __init__(self):
        self.borrowing_rates = {
            'BTC': 0.0001,    # 0.01% per day
            'ETH': 0.00015,
            'SOL': 0.0002,
            'default': 0.0001
        }

        logger.info("ShortBorrowingCostCalculator initialized")

    def calculate_borrowing_cost(
        self,
        symbol: str,
        position_value: float,
        days_held: float
    ) -> float:
        """
        Calculate short borrowing cost.

        For perpetuals, this is primarily via funding rates,
        but we include a separate calculation for completeness.
        """

        base_asset = symbol.replace('USDT', '').replace('BUSD', '')
        daily_rate = self.borrowing_rates.get(
            base_asset,
            self.borrowing_rates['default']
        )

        return position_value * daily_rate * days_held


class TimeOfDayFeeAdjuster:
    """
    Adjust fees based on time of day.

    Some exchanges have variable fees based on:
- Market open/close effects
- Liquidity cycles
- Peak trading hours
    """

    def __init__(self):
        # Fee multipliers by hour (UTC)
        self.hourly_multipliers = {
            # Asian session (0-8 UTC)
            0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.05, 7: 1.05,
            # European/London overlap (8-16 UTC)
            8: 1.1, 9: 1.1, 10: 1.05, 11: 1.05, 12: 1.0, 13: 1.0,
            14: 1.0, 15: 1.05, 16: 1.05,
            # US session overlap (16-24 UTC)
            17: 1.1, 18: 1.1, 19: 1.1, 20: 1.05, 21: 1.0, 22: 1.0, 23: 1.0
        }

        logger.info("TimeOfDayFeeAdjuster initialized")

    def get_fee_multiplier(self, timestamp: datetime) -> float:
        """Get fee multiplier for a given time."""
        hour = timestamp.hour
        return self.hourly_multipliers.get(hour, 1.0)


class AdvancedTransactionCostModel:
    """
    Advanced transaction cost model.

    Combines all cost components:
    - Exchange fees (maker/taker)
    - VIP discounts
    - Time-of-day adjustments
    - Funding rates (perpetuals)
    - Short borrowing costs

    This is the primary interface for cost calculations.
    """

    def __init__(self):
        self.fee_manager = ExchangeFeeManager()
        self.funding_calculator = PerpetualFundingCalculator()
        self.borrowing_calculator = ShortBorrowingCostCalculator()
        self.time_adjuster = TimeOfDayFeeAdjuster()

        self.vip_tier = VIPTier.REGULAR

        logger.info("AdvancedTransactionCostModel initialized")

    def set_vip_tier(self, tier: VIPTier):
        """Set VIP tier for fee discounts."""
        self.vip_tier = tier
        logger.info(f"VIP tier set to {tier.name}")

    async def calculate_transaction_cost(
        self,
        exchange: Exchange,
        order_type: OrderType,
        notional_value: float,
        symbol: str = "SOLUSDT",
        timestamp: Optional[datetime] = None,
        position_side: str = "long",
        holding_period_hours: float = 0.0
    ) -> TransactionCost:
        """
        Calculate total transaction cost with all components.

        Args:
            exchange: Exchange to trade on
            order_type: Maker or Taker
            notional_value: Order notional value in USDT
            symbol: Trading symbol
            timestamp: Order timestamp (for time-of-day adjustment)
            position_side: 'long' or 'short'
            holding_period_hours: How long position will be held (for funding)

        Returns:
            TransactionCost with complete breakdown
        """

        # Get fee schedule
        fee_schedule = self.fee_manager.get_fee_schedule(exchange)

        # Get base fee
        if order_type == OrderType.MAKER:
            base_fee_bps = fee_schedule.maker_fee_bps
        else:
            base_fee_bps = fee_schedule.taker_fee_bps

        # Apply VIP discount
        vip_discount = fee_schedule.vip_discounts.get(self.vip_tier, 0.0)
        discounted_fee_bps = base_fee_bps * (1 - vip_discount)

        # Apply time-of-day adjustment
        if timestamp is None:
            timestamp = datetime.now()

        time_multiplier = self.time_adjuster.get_fee_multiplier(timestamp)
        final_fee_bps = discounted_fee_bps * time_multiplier

        # Calculate fee in USDT
        base_fee = notional_value * (base_fee_bps / 10000)
        final_fee = notional_value * (final_fee_bps / 10000)

        # Calculate funding cost (for perpetuals)
        funding_cost = 0.0
        if exchange in [Exchange.BINANCE_PERPETUAL, Exchange.BITGET_PERPETUAL]:
            if holding_period_hours > 0:
                funding_cost = self.funding_calculator.calculate_funding_cost(
                    symbol, notional_value, position_side, holding_period_hours
                )

        # Calculate borrowing cost (for shorts)
        borrowing_cost = 0.0
        if position_side.lower() == 'short' and holding_period_hours > 0:
            days_held = holding_period_hours / 24.0
            borrowing_cost = self.borrowing_calculator.calculate_borrowing_cost(
                symbol, notional_value, days_held
            )

        # Total cost
        total_cost = final_fee + funding_cost + borrowing_cost

        transaction_cost = TransactionCost(
            exchange=exchange,
            order_type=order_type,
            notional_value=notional_value,
            base_fee=base_fee,
            vip_discount=base_fee - final_fee,
            final_fee=final_fee,
            fee_percentage=final_fee_bps / 100,
            funding_cost=funding_cost,
            borrowing_cost=borrowing_cost,
            total_cost=total_cost
        )

        logger.debug(f"Transaction cost calculated: "
                    f"Base={base_fee:.4f}, Final={final_fee:.4f}, "
                    f"Funding={funding_cost:.4f}, Total={total_cost:.4f}")

        return transaction_cost

    def get_cost_comparison(
        self,
        notional_value: float,
        symbol: str = "SOLUSDT",
        holding_hours: float = 24.0
    ) -> Dict[str, TransactionCost]:
        """
        Compare costs across all exchanges and order types.

        Useful for finding the cheapest execution venue.
        """

        comparisons = {}

        for exchange in Exchange:
            for order_type in [OrderType.MAKER, OrderType.TAKER]:
                for side in ['long', 'short']:
                    try:
                        cost = asyncio.run(self.calculate_transaction_cost(
                            exchange, order_type, notional_value, symbol,
                            None, side, holding_hours
                        ))

                        key = f"{exchange.value}_{order_type.value}_{side}"
                        comparisons[key] = cost
                    except Exception as e:
                        logger.warning(f"Failed to calculate cost for {key}: {e}")

        return comparisons

    def generate_cost_report(self, cost: TransactionCost) -> str:
        """Generate detailed cost report."""

        report = f"""
TRANSACTION COST REPORT
{'='*40}
Exchange: {cost.exchange.value}
Order Type: {cost.order_type.value}
Notional Value: ${cost.notional_value:,.2f}

FEE BREAKDOWN:
  Base Fee: ${cost.base_fee:.4f}
  VIP Discount: -${cost.vip_discount:.4f}
  Final Fee: ${cost.final_fee:.4f}
  Fee Rate: {cost.fee_percentage * 100:.4f}%

PERPETUAL COSTS:
  Funding Cost: ${cost.funding_cost:.4f}
  Borrowing Cost: ${cost.borrowing_cost:.4f}

TOTAL COST: ${cost.total_cost:.4f}
Total bps: {(cost.total_cost / cost.notional_value) * 10000:.2f} bps
"""
        return report


# Singleton instance
_transaction_cost_model = None


def get_transaction_cost_model() -> AdvancedTransactionCostModel:
    """Get or create transaction cost model instance."""
    global _transaction_cost_model
    if _transaction_cost_model is None:
        _transaction_cost_model = AdvancedTransactionCostModel()
    return _transaction_cost_model
