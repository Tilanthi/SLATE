#!/usr/bin/env python3
"""
SLATE Advanced Position Sizing System

Phase 6: PnL Portfolio Management (Weeks 21-24)

Implements sophisticated position sizing strategies:
- Fractional Kelly Criterion
- Risk Parity
- Target Volatility
- CPPI (Constant Proportion Portfolio Insurance)

Critical for optimal capital allocation and risk management.

Author: SLATE Evolution
Date: 2026-04-30
Priority: MEDIUM - Advanced position sizing
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

logger = logging.getLogger(__name__)


class SizingMethod(Enum):
    """Position sizing methods."""
    KELLY = "kelly"  # Kelly Criterion
    FRACTIONAL_KELLY = "fractional_kelly"  # Fractional Kelly
    RISK_PARITY = "risk_parity"  # Equal risk contribution
    TARGET_VOLATILITY = "target_volatility"  # Target portfolio vol
    CPPI = "cppi"  # Constant Proportion Portfolio Insurance
    FIXED_FRACTION = "fixed_fraction"  # Fixed % of capital
    VOLATILITY_TARGET = "volatility_target"  # Vol-adjusted sizing


@dataclass
class PositionSize:
    """Position size recommendation."""
    asset: str
    strategy: str

    # Sizing
    units: float  # Number of units/contracts
    notional_value: float  # Notional value
    capital_allocation: float  # % of total capital

    # Risk metrics
    position_risk: float  # $ risk
    portfolio_risk_contribution: float  # % of portfolio risk
    max_loss: float  # Maximum expected loss

    # Confidence
    confidence: float
    method: SizingMethod


class KellyCriterion:
    """
    Kelly Criterion position sizing.

    Maximizes long-term growth rate.
    f* = μ/σ² for single asset
    """

    def __init__(self, max_leverage: float = 1.5):
        self.max_leverage = max_leverage
        logger.info(f"KellyCriterion initialized (max_leverage={max_leverage})")

    def calculate_kelly(
        self,
        expected_return: float,
        variance: float,
        capital: float,
        asset_price: float
    ) -> PositionSize:
        """
        Calculate Kelly position size.

        Args:
            expected_return: Expected return (per period)
            variance: Return variance
            capital: Available capital
            asset_price: Current asset price

        Returns:
            Position size recommendation
        """

        # Kelly fraction
        if variance > 0:
            kelly_fraction = expected_return / variance
        else:
            kelly_fraction = 0.0

        # Cap at max leverage
        kelly_fraction = min(kelly_fraction, self.max_leverage)
        kelly_fraction = max(kelly_fraction, 0.0)  # No short selling

        # Position size
        capital_allocation = kelly_fraction
        notional_value = capital * capital_allocation
        units = notional_value / asset_price if asset_price > 0 else 0

        return PositionSize(
            asset="ASSET",
            strategy="Kelly",
            units=units,
            notional_value=notional_value,
            capital_allocation=capital_allocation,
            position_risk=notional_value * np.sqrt(variance),
            portfolio_risk_contribution=capital_allocation,
            max_loss=notional_value * 0.5,  # Rough estimate
            confidence=0.7,
            method=SizingMethod.KELLY
        )

    def calculate_fractional_kelly(
        self,
        expected_return: float,
        variance: float,
        capital: float,
        asset_price: float,
        fraction: float = 0.25
    ) -> PositionSize:
        """
        Calculate fractional Kelly position size.

        Uses fraction of full Kelly for more conservative sizing.
        Commonly uses 1/4 Kelly or half Kelly.

        Args:
            expected_return: Expected return
            variance: Return variance
            capital: Available capital
            asset_price: Current asset price
            fraction: Kelly fraction (0.25 = quarter Kelly)

        Returns:
            Position size recommendation
        """

        position = self.calculate_kelly(expected_return, variance, capital, asset_price)
        position.capital_allocation *= fraction
        position.notional_value *= fraction
        position.units *= fraction
        position.position_risk *= fraction
        position.portfolio_risk_contribution *= fraction
        position.max_loss *= fraction
        position.method = SizingMethod.FRACTIONAL_KELLY
        position.strategy = f"Fractional Kelly ({fraction:.0%})"

        return position


class RiskParity:
    """
    Risk Parity position sizing.

    Equalizes risk contribution across assets.
    Each asset contributes same amount to portfolio risk.
    """

    def __init__(self):
        logger.info("RiskParity initialized")

    def calculate_risk_parity_weights(
        self,
        cov_matrix: pd.DataFrame
    ) -> np.ndarray:
        """
        Calculate risk parity weights.

        Args:
            cov_matrix: Covariance matrix

        Returns:
            Risk parity weights
        """

        n_assets = len(cov_matrix)

        # Risk parity: equalize marginal risk contribution
        # Solve: w_i * (Σw)_i = w_j * (Σw)_j for all i, j

        def risk_budget_objective(w):
            """Objective: minimize deviation from equal risk contribution."""
            portfolio_risk = np.sqrt(np.dot(w.T, np.dot(cov_matrix.values, w)))
            marginal_risk = np.dot(cov_matrix.values, w) / portfolio_risk
            risk_contribution = w * marginal_risk

            # Target: equal risk contribution
            target_risk = 1.0 / n_assets
            return np.sum((risk_contribution - target_risk) ** 2)

        # Constraints
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = [(0, 1) for _ in range(n_assets)]

        # Initial guess
        w0 = np.ones(n_assets) / n_assets

        # Optimize
        result = optimize.minimize(
            risk_budget_objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        weights = result.x if result.success else w0
        return weights

    def size_positions_risk_parity(
        self,
        returns: pd.DataFrame,
        capital: float,
        asset_prices: pd.Series
    ) -> List[PositionSize]:
        """
        Size positions using risk parity.

        Args:
            returns: Historical returns
            capital: Total capital
            asset_prices: Current asset prices

        Returns:
            List of position sizes
        """

        # Calculate covariance matrix
        cov_matrix = returns.cov() * 252  # Annualized

        # Calculate risk parity weights
        weights = self.calculate_risk_parity_weights(cov_matrix)

        # Create position sizes
        positions = []
        for i, asset in enumerate(returns.columns):
            capital_allocation = weights[i]
            notional_value = capital * capital_allocation
            units = notional_value / asset_prices[asset] if asset_prices[asset] > 0 else 0

            # Risk contribution
            asset_risk = np.sqrt(cov_matrix.iloc[i, i])
            position_risk = notional_value * asset_risk

            position = PositionSize(
                asset=asset,
                strategy="Risk Parity",
                units=units,
                notional_value=notional_value,
                capital_allocation=capital_allocation,
                position_risk=position_risk,
                portfolio_risk_contribution=1.0 / len(returns.columns),
                max_loss=notional_value * 0.5,
                confidence=0.8,
                method=SizingMethod.RISK_PARITY
            )
            positions.append(position)

        return positions


class TargetVolatility:
    """
    Target Volatility position sizing.

    Scales positions to achieve target portfolio volatility.
    """

    def __init__(self, target_volatility: float = 0.15):
        self.target_volatility = target_volatility  # 15% annual vol
        logger.info(f"TargetVolatility initialized (target={target_volatility:.2%})")

    def scale_to_target_volatility(
        self,
        returns: pd.DataFrame,
        base_weights: np.ndarray,
        capital: float,
        asset_prices: pd.Series
    ) -> List[PositionSize]:
        """
        Scale positions to achieve target volatility.

        Args:
            returns: Historical returns
            base_weights: Base portfolio weights
            capital: Total capital
            asset_prices: Current asset prices

        Returns:
            List of scaled position sizes
        """

        # Calculate current portfolio volatility
        cov_matrix = returns.cov() * 252
        current_vol = np.sqrt(np.dot(base_weights.T, np.dot(cov_matrix.values, base_weights)))

        # Scale factor
        if current_vol > 0:
            scale_factor = self.target_volatility / current_vol
        else:
            scale_factor = 1.0

        # Cap scale factor (0.5x to 2x)
        scale_factor = max(0.5, min(2.0, scale_factor))

        # Scale weights
        scaled_weights = base_weights * scale_factor
        scaled_weights = scaled_weights / scaled_weights.sum()  # Re-normalize

        # Create position sizes
        positions = []
        for i, asset in enumerate(returns.columns):
            capital_allocation = scaled_weights[i]
            notional_value = capital * capital_allocation
            units = notional_value / asset_prices[asset] if asset_prices[asset] > 0 else 0

            position = PositionSize(
                asset=asset,
                strategy=f"Target Volatility ({self.target_volatility:.2%})",
                units=units,
                notional_value=notional_value,
                capital_allocation=capital_allocation,
                position_risk=notional_value * np.sqrt(cov_matrix.iloc[i, i]),
                portfolio_risk_contribution=capital_allocation,
                max_loss=notional_value * 0.5,
                confidence=0.75,
                method=SizingMethod.TARGET_VOLATILITY
            )
            positions.append(position)

        return positions


class CPPI:
    """
    Constant Proportion Portfolio Insurance (CPPI).

    Protects downside while maintaining upside potential.
    """

    def __init__(self, cushion_multiplier: float = 3.0):
        self.cushion_multiplier = cushion_multiplier
        logger.info(f"CPPI initialized (multiplier={cushion_multiplier})")

    def calculate_cppi_allocation(
        self,
        capital: float,
        floor_value: float,
        risky_asset_price: float,
        risky_asset_volatility: float
    ) -> PositionSize:
        """
        Calculate CPPI allocation to risky asset.

        Args:
            capital: Current portfolio value
            floor_value: Floor value (minimum acceptable)
            risky_asset_price: Price of risky asset
            risky_asset_volatility: Volatility of risky asset

        Returns:
            Position size for risky asset
        """

        # Calculate cushion
        cushion = (capital - floor_value) / capital if capital > 0 else 0

        # Calculate risky asset allocation
        risky_allocation = min(1.0, cushion * self.cushion_multiplier)
        risky_allocation = max(0.0, risky_allocation)

        # Safe asset allocation
        safe_allocation = 1.0 - risky_allocation

        # Position size
        notional_value = capital * risky_allocation
        units = notional_value / risky_asset_price if risky_asset_price > 0 else 0

        return PositionSize(
            asset="RISKY_ASSET",
            strategy=f"CPPI (m={self.cushion_multiplier})",
            units=units,
            notional_value=notional_value,
            capital_allocation=risky_allocation,
            position_risk=notional_value * risky_asset_volatility,
            portfolio_risk_contribution=risky_allocation,
            max_loss=capital - floor_value,  # Maximum loss is cushion
            confidence=0.85,
            method=SizingMethod.CPPI
        )


class VolatilityTarget:
    """
    Volatility-targeted position sizing.

    Sizes positions inversely proportional to volatility.
    Higher volatility → smaller position.
    """

    def __init__(self, target_volatility: float = 0.10):
        self.target_volatility = target_volatility
        logger.info(f"VolatilityTarget initialized (target={target_volatility:.2%})")

    def size_by_volatility(
        self,
        returns: pd.Series,
        capital: float,
        asset_price: float,
        base_allocation: float = 0.20
    ) -> PositionSize:
        """
        Size position based on volatility.

        Args:
            returns: Historical returns
            capital: Available capital
            asset_price: Current asset price
            base_allocation: Base allocation percentage

        Returns:
            Volatility-adjusted position size
        """

        # Calculate realized volatility
        realized_vol = returns.std() * np.sqrt(252)

        # Volatility scaling factor
        if realized_vol > 0:
            vol_scale = self.target_volatility / realized_vol
        else:
            vol_scale = 1.0

        # Cap scale factor
        vol_scale = max(0.25, min(4.0, vol_scale))

        # Adjusted allocation
        capital_allocation = base_allocation * vol_scale
        capital_allocation = min(1.0, capital_allocation)  # Cap at 100%

        # Position size
        notional_value = capital * capital_allocation
        units = notional_value / asset_price if asset_price > 0 else 0

        return PositionSize(
            asset="ASSET",
            strategy=f"Volatility Target ({self.target_volatility:.2%})",
            units=units,
            notional_value=notional_value,
            capital_allocation=capital_allocation,
            position_risk=notional_value * realized_vol,
            portfolio_risk_contribution=capital_allocation,
            max_loss=notional_value * 0.5,
            confidence=0.8,
            method=SizingMethod.VOLATILITY_TARGET
        )


class PositionSizingEngine:
    """
    Unified position sizing engine.

    Combines all sizing methods for optimal capital allocation.
    """

    def __init__(self):
        self.kelly = KellyCriterion()
        self.risk_parity = RiskParity()
        self.target_vol = TargetVolatility()
        self.cppi = CPPI()
        self.vol_target = VolatilityTarget()

        logger.info("PositionSizingEngine initialized")

    async def calculate_position_size(
        self,
        method: SizingMethod,
        returns: pd.DataFrame,
        capital: float,
        asset_prices: pd.Series,
        **kwargs
    ) -> List[PositionSize]:
        """
        Calculate position sizes using specified method.

        Args:
            method: Sizing method
            returns: Historical returns
            capital: Available capital
            asset_prices: Current asset prices
            **kwargs: Method-specific parameters

        Returns:
            List of position sizes
        """

        if method == SizingMethod.KELLY:
            # Single asset Kelly
            asset = kwargs.get('asset', returns.columns[0])
            asset_returns = returns[asset]
            expected_return = asset_returns.mean() * 252
            variance = asset_returns.var() * 252

            position = self.kelly.calculate_kelly(
                expected_return,
                variance,
                capital,
                asset_prices[asset]
            )
            return [position]

        elif method == SizingMethod.FRACTIONAL_KELLY:
            asset = kwargs.get('asset', returns.columns[0])
            fraction = kwargs.get('fraction', 0.25)
            asset_returns = returns[asset]
            expected_return = asset_returns.mean() * 252
            variance = asset_returns.var() * 252

            position = self.kelly.calculate_fractional_kelly(
                expected_return,
                variance,
                capital,
                asset_prices[asset],
                fraction
            )
            return [position]

        elif method == SizingMethod.RISK_PARITY:
            return self.risk_parity.size_positions_risk_parity(
                returns, capital, asset_prices
            )

        elif method == SizingMethod.TARGET_VOLATILITY:
            base_weights = kwargs.get('base_weights', np.ones(len(returns.columns)) / len(returns.columns))
            return self.target_vol.scale_to_target_volatility(
                returns, base_weights, capital, asset_prices
            )

        elif method == SizingMethod.CPPI:
            floor_value = kwargs.get('floor_value', capital * 0.8)
            risky_asset = kwargs.get('risky_asset', returns.columns[0])
            risky_vol = returns[risky_asset].std() * np.sqrt(252)

            position = self.cppi.calculate_cppi_allocation(
                capital,
                floor_value,
                asset_prices[risky_asset],
                risky_vol
            )
            return [position]

        elif method == SizingMethod.VOLATILITY_TARGET:
            asset = kwargs.get('asset', returns.columns[0])
            base_allocation = kwargs.get('base_allocation', 0.20)

            position = self.vol_target.size_by_volatility(
                returns[asset],
                capital,
                asset_prices[asset],
                base_allocation
            )
            return [position]

        elif method == SizingMethod.FIXED_FRACTION:
            # Simple fixed fraction
            fraction = kwargs.get('fraction', 0.10)
            positions = []
            for asset in returns.columns:
                capital_allocation = fraction
                notional_value = capital * capital_allocation
                units = notional_value / asset_prices[asset] if asset_prices[asset] > 0 else 0

                position = PositionSize(
                    asset=asset,
                    strategy=f"Fixed Fraction ({fraction:.2%})",
                    units=units,
                    notional_value=notional_value,
                    capital_allocation=capital_allocation,
                    position_risk=notional_value * returns[asset].std(),
                    portfolio_risk_contribution=capital_allocation,
                    max_loss=notional_value * 0.5,
                    confidence=0.5,
                    method=SizingMethod.FIXED_FRACTION
                )
                positions.append(position)
            return positions

        else:
            logger.warning(f"Unknown method: {method}, using fixed fraction")
            return await self.calculate_position_size(
                SizingMethod.FIXED_FRACTION,
                returns, capital, asset_prices
            )

    def generate_sizing_report(
        self,
        positions: List[PositionSize],
        capital: float
    ) -> str:
        """Generate position sizing report."""

        report = f"""
{'='*60}
POSITION SIZING REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

TOTAL CAPITAL: ${capital:,.2f}
TOTAL POSITIONS: {len(positions)}

POSITION BREAKDOWN:
"""

        total_allocation = 0
        total_risk = 0

        for position in sorted(positions, key=lambda p: p.capital_allocation, reverse=True):
            report += f"""
{position.asset}:
  Strategy: {position.strategy}
  Units: {position.units:.4f}
  Notional: ${position.notional_value:,.2f}
  Allocation: {position.capital_allocation:.2%}
  Risk: ${position.position_risk:,.2f}
  Max Loss: ${position.max_loss:,.2f}
  Confidence: {position.confidence:.1%}
"""

            total_allocation += position.capital_allocation
            total_risk += position.position_risk

        report += f"""
SUMMARY:
  Total Allocation: {total_allocation:.2%}
  Total Risk: ${total_risk:,.2f}
  Cash: {(1 - total_allocation):.2%} of capital
"""

        return report


# Singleton instance
_position_sizing_engine = None


def get_position_sizing_engine() -> PositionSizingEngine:
    """Get or create position sizing engine instance."""
    global _position_sizing_engine
    if _position_sizing_engine is None:
        _position_sizing_engine = PositionSizingEngine()
    return _position_sizing_engine
