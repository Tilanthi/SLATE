#!/usr/bin/env python3
"""
SLATE Regime-Adaptive Discovery System

Phase 1 Integration: Market Intelligence + Edge Discovery

This module integrates market regime detection with the edge discovery engine
to create adaptive strategies that respond to market conditions.

Key Innovation: Strategies are not static - they adapt based on:
- Current market regime (trending, sideways, volatility state)
- Correlation network state
- Liquidity conditions
- Time-of-day patterns

Author: SLATE Evolution
Date: 2025-04-30
Priority: CRITICAL - Foundation for autonomous agent
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

# Import market intelligence
from .market_regime_detector import (
    MarketRegimeDetector,
    MarketRegime,
    RegimeState,
    CorrelationNetwork,
    get_market_intelligence
)

logger = logging.getLogger(__name__)


class RegimeAdaptiveSignal(Enum):
    """Regime-adaptive signal types."""
    # Trending market signals
    TREND_FOLLOW_LONG = "trend_follow_long"
    TREND_FOLLOW_SHORT = "trend_follow_short"
    MOMENTUM_CONTINUATION = "momentum_continuation"

    # Sideways market signals
    MEAN_REVERSION_LONG = "mean_reversion_long"
    MEAN_REVERSION_SHORT = "mean_reversion_short"
    RANGE_TRADE = "range_trade"

    # Volatility-based signals
    VOLATILITY_BREAKOUT = "volatility_breakout"
    VOLATILITY_MEAN_REVERSION = "volatility_mean_reversion"
    VOLATILITY_CRUSH_PROFIT = "volatility_crush_profit"

    # Liquidity-based signals
    LIQUIDITY_PREMIUM_COLLECT = "liquidity_premium_collect"
    LIQUIDITY_CRUSH_EXIT = "liquidity_crush_exit"

    # Correlation-based signals
    CORRELATION_ARBITRAGE = "correlation_arbitrage"
    LEAD_LAG_EXPLOIT = "lead_lag_exploit"


@dataclass
class RegimeAdaptiveStrategy:
    """A regime-adaptive trading strategy."""
    strategy_id: str
    name: str
    description: str
    applicable_regimes: List[MarketRegime]
    signal_type: RegimeAdaptiveSignal
    entry_params: Dict[str, Any]
    exit_params: Dict[str, Any]
    risk_params: Dict[str, Any]
    regime_specific_params: Dict[MarketRegime, Dict[str, Any]] = field(default_factory=dict)

    def is_applicable(self, regime: MarketRegime) -> bool:
        """Check if strategy applies to current regime."""
        return regime in self.applicable_regimes

    def get_params_for_regime(self, regime: MarketRegime) -> Dict[str, Any]:
        """Get strategy parameters adapted for current regime."""
        # Start with base params
        params = {
            'entry': self.entry_params.copy(),
            'exit': self.exit_params.copy(),
            'risk': self.risk_params.copy()
        }

        # Apply regime-specific overrides
        if regime in self.regime_specific_params:
            overrides = self.regime_specific_params[regime]
            for key, value in overrides.items():
                if key in params:
                    params[key].update(value)
                else:
                    params[key] = value

        return params


class RegimeAdaptiveSignalGenerator:
    """
    Generate trading signals adapted to current market regime.

    Philosophy: "One size does NOT fit all. Different regimes require different approaches."

    Signal generation logic:
    - Trending markets: Follow momentum, don't fade
    - Sideways markets: Mean reversion, range trading
    - High volatility: Reduce size, wait for clarity
    - Low volatility: Prepare for breakout
    """

    def __init__(self):
        self.market_intel = get_market_intelligence()
        self.active_strategies: List[RegimeAdaptiveStrategy] = []
        self.signal_history = []

        # Initialize regime-adaptive strategies
        self._initialize_strategies()

        logger.info("RegimeAdaptiveSignalGenerator initialized with regime-aware strategies")

    def _initialize_strategies(self):
        """Initialize the repertoire of regime-adaptive strategies."""

        # ===== TRENDING MARKET STRATEGIES =====

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="trend_follow_ma_crossover",
            name="Moving Average Crossover Trend Following",
            description="Follow trends using MA crossovers, adapted for trend strength",
            applicable_regimes=[MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN],
            signal_type=RegimeAdaptiveSignal.TREND_FOLLOW_LONG,
            entry_params={
                'fast_ma': 20,
                'slow_ma': 50,
                'confirmation_periods': 3
            },
            exit_params={
                'fast_ma': 20,
                'slow_ma': 50,
                'trailing_stop_atr': 2.0
            },
            risk_params={
                'position_size': 0.03,
                'stop_loss_atr': 1.5
            },
            regime_specific_params={
                MarketRegime.TRENDING_UP: {
                    'entry': {'only_long': True}
                },
                MarketRegime.TRENDING_DOWN: {
                    'entry': {'only_short': True}
                }
            }
        ))

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="momentum_breakout",
            name="Momentum Breakout",
            description="Trade momentum breakouts with volume confirmation",
            applicable_regimes=[MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN],
            signal_type=RegimeAdaptiveSignal.MOMENTUM_CONTINUATION,
            entry_params={
                'lookback_period': 20,
                'breakout_threshold': 2.0,  # Standard deviations
                'volume_confirmation': True
            },
            exit_params={
                'profit_target_atr': 3.0,
                'trailing_stop_atr': 1.5
            },
            risk_params={
                'position_size': 0.04,
                'stop_loss_atr': 1.0
            }
        ))

        # ===== SIDEWAYS MARKET STRATEGIES =====

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="mean_reversion_bollinger",
            name="Bollinger Band Mean Reversion",
            description="Fade extreme moves in range-bound markets",
            applicable_regimes=[MarketRegime.SIDEWAYS],
            signal_type=RegimeAdaptiveSignal.MEAN_REVERSION_LONG,
            entry_params={
                'bb_period': 20,
                'bb_std': 2.5,
                'entry_threshold': 2.0,  # Enter at 2 std
                'rsi_filter': True
            },
            exit_params={
                'target_atr': 1.5,
                'stop_loss_atr': 1.0
            },
            risk_params={
                'position_size': 0.025,
                'max_hold_time_bars': 50
            }
        ))

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="range_trade_support_resistance",
            name="Support/Resistance Range Trading",
            description="Trade between established support and resistance",
            applicable_regimes=[MarketRegime.SIDEWAYS],
            signal_type=RegimeAdaptiveSignal.RANGE_TRADE,
            entry_params={
                'lookback_period': 50,
                'touch_tolerance': 0.01,  # 1% tolerance
                'confirmations_needed': 2
            },
            exit_params={
                'target_pct': 0.02,  # 2% target
                'stop_loss_pct': 0.01
            },
            risk_params={
                'position_size': 0.03,
                'max_attempts_per_range': 3
            }
        ))

        # ===== VOLATILITY-BASED STRATEGIES =====

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="volatility_breakout",
            name="Volatility Breakout",
            description="Trade breakouts from low-volatility compression",
            applicable_regimes=[MarketRegime.LOW_VOLATILITY],
            signal_type=RegimeAdaptiveSignal.VOLATILITY_BREAKOUT,
            entry_params={
                'vol_lookback': 20,
                'vol_percentile': 20,  # Enter when vol in bottom 20%
                'breakout_threshold': 1.5
            },
            exit_params={
                'profit_target_atr': 4.0,
                'trailing_stop_atr': 2.0
            },
            risk_params={
                'position_size': 0.04,
                'stop_loss_atr': 1.5
            }
        ))

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="volatility_mean_reversion",
            name="Volatility Mean Reversion",
            description="Fade extreme volatility spikes",
            applicable_regimes=[MarketRegime.HIGH_VOLATILITY],
            signal_type=RegimeAdaptiveSignal.VOLATILITY_MEAN_REVERSION,
            entry_params={
                'vol_lookback': 20,
                'vol_percentile': 80,  # Enter when vol in top 20%
                'entry_delay_bars': 2  # Wait for peak
            },
            exit_params={
                'target_vol_percentile': 50,
                'max_hold_time_bars': 30
            },
            risk_params={
                'position_size': 0.02,  # Smaller in high vol
                'stop_loss_atr': 2.0
            }
        ))

        # ===== LIQUIDITY-BASED STRATEGIES =====

        self.active_strategies.append(RegimeAdaptiveStrategy(
            strategy_id="liquidity_premium_collect",
            name="Liquidity Premium Collection",
            description="Provide liquidity during tight spread periods",
            applicable_regimes=[MarketRegime.LIQUIDITY_ABUNDANT],
            signal_type=RegimeAdaptiveSignal.LIQUIDITY_PREMIUM_COLLECT,
            entry_params={
                'spread_threshold': 0.0005,  # 0.05% spread
                'depth_confirmed': True
            },
            exit_params={
                'target_profit_bps': 10,
                'max_hold_time_minutes': 60
            },
            risk_params={
                'position_size': 0.02,
                'inventory_limit': 0.1
            }
        ))

        logger.info(f"Initialized {len(self.active_strategies)} regime-adaptive strategies")

    async def generate_signals(
        self,
        symbol: str,
        data: pd.DataFrame,
        current_regime: RegimeState
    ) -> List[Dict[str, Any]]:
        """
        Generate trading signals adapted to current market regime.

        Args:
            symbol: Trading symbol
            data: Price data with OHLCV
            current_regime: Current market regime state

        Returns:
            List of applicable trading signals
        """
        signals = []

        # Find strategies applicable to current regime
        applicable_strategies = [
            s for s in self.active_strategies
            if s.is_applicable(current_regime.regime)
        ]

        logger.info(f"Found {len(applicable_strategies)} strategies applicable to {current_regime.regime.value}")

        # Generate signals from each applicable strategy
        for strategy in applicable_strategies:
            try:
                signal = await self._generate_strategy_signal(
                    strategy=strategy,
                    symbol=symbol,
                    data=data,
                    regime=current_regime
                )

                if signal and signal['confidence'] > 0.5:
                    signals.append(signal)
                    logger.info(f"Generated signal: {signal['signal_type']} | "
                               f"Confidence: {signal['confidence']:.2f} | "
                               f"Strategy: {strategy.name}")

            except Exception as e:
                logger.warning(f"Failed to generate signal for {strategy.name}: {e}")
                continue

        # Store signal history
        self.signal_history.append({
            'timestamp': datetime.now(),
            'regime': current_regime.regime.value,
            'signals': signals
        })

        return signals

    async def _generate_strategy_signal(
        self,
        strategy: RegimeAdaptiveStrategy,
        symbol: str,
        data: pd.DataFrame,
        regime: RegimeState
    ) -> Optional[Dict[str, Any]]:
        """Generate signal from a specific strategy."""

        # Get regime-adapted parameters
        params = strategy.get_params_for_regime(regime.regime)

        # Calculate indicators
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data['volume'].values

        # Calculate ATR for risk management
        atr = self._calculate_atr(high, low, close, period=14)
        current_atr = atr[-1]

        # Generate signal based on strategy type
        signal_type = strategy.signal_type
        confidence = 0.0
        action = None
        reason = ""

        # === TREND FOLLOWING STRATEGIES ===

        if signal_type in [RegimeAdaptiveSignal.TREND_FOLLOW_LONG,
                          RegimeAdaptiveSignal.TREND_FOLLOW_SHORT,
                          RegimeAdaptiveSignal.MOMENTUM_CONTINUATION]:

            # Moving average crossover
            fast_ma = np.convolve(close[-params['entry']['fast_ma']:],
                                 np.ones(params['entry']['fast_ma'])/params['entry']['fast_ma'],
                                 mode='valid')
            slow_ma = np.convolve(close[-params['entry']['slow_ma']:],
                                 np.ones(params['entry']['slow_ma'])/params['entry']['slow_ma'],
                                 mode='valid')

            if len(fast_ma) > 0 and len(slow_ma) > 0:
                fast_ma_current = fast_ma[-1]
                slow_ma_current = slow_ma[-1]

                # Determine trend direction
                if regime.regime == MarketRegime.TRENDING_UP:
                    if fast_ma_current > slow_ma_current:
                        action = 1  # LONG
                        confidence = 0.7
                        reason = f"Fast MA ({fast_ma_current:.2f}) > Slow MA ({slow_ma_current:.2f}) in uptrend"
                    else:
                        # Wait for alignment
                        action = 0
                        confidence = 0.3
                        reason = "Waiting for MA alignment"

                elif regime.regime == MarketRegime.TRENDING_DOWN:
                    if fast_ma_current < slow_ma_current:
                        action = -1  # SHORT
                        confidence = 0.7
                        reason = f"Fast MA ({fast_ma_current:.2f}) < Slow MA ({slow_ma_current:.2f}) in downtrend"
                    else:
                        action = 0
                        confidence = 0.3
                        reason = "Waiting for MA alignment"

        # === MEAN REVERSION STRATEGIES ===

        elif signal_type in [RegimeAdaptiveSignal.MEAN_REVERSION_LONG,
                            RegimeAdaptiveSignal.MEAN_REVERSION_SHORT,
                            RegimeAdaptiveSignal.RANGE_TRADE]:

            # Bollinger Bands
            bb_period = params['entry'].get('bb_period', 20)
            bb_std = params['entry'].get('bb_std', 2.0)

            sma = np.convolve(close[-bb_period:], np.ones(bb_period)/bb_period, mode='valid')
            std = np.std(close[-bb_period:])

            if len(sma) > 0:
                upper_band = sma[-1] + bb_std * std
                lower_band = sma[-1] - bb_std * std
                current_price = close[-1]

                # Check for mean reversion setup
                if current_price < lower_band:
                    action = 1  # LONG - fade the move
                    confidence = 0.65
                    reason = f"Price ({current_price:.2f}) below lower BB ({lower_band:.2f}) - mean reversion long"
                elif current_price > upper_band:
                    action = -1  # SHORT - fade the move
                    confidence = 0.65
                    reason = f"Price ({current_price:.2f}) above upper BB ({upper_band:.2f}) - mean reversion short"
                else:
                    action = 0
                    confidence = 0.2
                    reason = "Price within bands - no edge"

        # === VOLATILITY STRATEGIES ===

        elif signal_type in [RegimeAdaptiveSignal.VOLATILITY_BREAKOUT,
                            RegimeAdaptiveSignal.VOLATILITY_MEAN_REVERSION]:

            # Calculate volatility
            returns = pd.Series(close).pct_change().dropna()
            current_vol = returns.tail(20).std()
            historical_vol = returns.tail(100).std()
            vol_ratio = current_vol / historical_vol if historical_vol > 0 else 1

            if signal_type == RegimeAdaptiveSignal.VOLATILITY_BREAKOUT:
                # Low vol compression - look for breakout
                if vol_ratio < 0.5:
                    action = 0  # Wait for breakout
                    confidence = 0.8
                    reason = f"Volatility compressed ({vol_ratio:.2f}) - waiting for breakout direction"
                else:
                    # Breakout happening - trade direction
                    recent_return = returns.iloc[-1]
                    action = 1 if recent_return > 0 else -1
                    confidence = 0.6
                    reason = f"Breakout detected with vol ratio {vol_ratio:.2f}"

            elif signal_type == RegimeAdaptiveSignal.VOLATILITY_MEAN_REVERSION:
                # High vol - expect reversion
                if vol_ratio > 2.0:
                    # Fade the last move
                    recent_return = returns.iloc[-1]
                    action = -1 if recent_return > 0 else 1
                    confidence = 0.55
                    reason = f"High volatility ({vol_ratio:.2f}) - fading extreme move"

        # === LIQUIDITY STRATEGIES ===

        elif signal_type == RegimeAdaptiveSignal.LIQUIDITY_PREMIUM_COLLECT:
            # Provide liquidity - counter-trend entries
            recent_return = (close[-1] - close[-2]) / close[-2]
            action = -1 if recent_return > 0 else 1
            confidence = 0.5
            reason = "Providing liquidity against short-term flow"

        # Build signal object
        if action is not None and action != 0:
            signal = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'strategy_id': strategy.strategy_id,
                'strategy_name': strategy.name,
                'signal_type': signal_type.value,
                'action': action,  # 1 = LONG, -1 = SHORT
                'confidence': confidence,
                'reason': reason,
                'regime': regime.regime.value,
                'entry_params': params.get('entry', {}),
                'exit_params': params.get('exit', {}),
                'risk_params': params.get('risk', {}),
                'atr': current_atr,
                'current_price': close[-1]
            }

            return signal

        return None

    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range."""
        high_low = high - low
        high_close = np.abs(high - np.roll(close, 1))
        low_close = np.abs(low - np.roll(close, 1))

        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = np.zeros_like(tr)
        atr[period-1] = np.mean(tr[:period])

        for i in range(period, len(tr)):
            atr[i] = (atr[i-1] * (period-1) + tr[i]) / period

        return atr

    def get_applicable_strategy_count(self, regime: MarketRegime) -> int:
        """Get number of strategies applicable to a regime."""
        return len([s for s in self.active_strategies if s.is_applicable(regime)])

    def get_strategy_coverage_report(self) -> str:
        """Generate report of strategy coverage across regimes."""
        report = "\n" + "="*60 + "\n"
        report += "REGIME-ADAPTIVE STRATEGY COVERAGE\n"
        report += "="*60 + "\n\n"

        for regime in MarketRegime:
            applicable = [s for s in self.active_strategies if s.is_applicable(regime)]
            report += f"{regime.value.upper()}:\n"
            report += f"  Strategies: {len(applicable)}\n"
            for strategy in applicable:
                report += f"    - {strategy.name}\n"
            report += "\n"

        return report


# Singleton instance
_regime_adaptive_generator = None


def get_regime_adaptive_generator() -> RegimeAdaptiveSignalGenerator:
    """Get or create regime-adaptive signal generator instance."""
    global _regime_adaptive_generator
    if _regime_adaptive_generator is None:
        _regime_adaptive_generator = RegimeAdaptiveSignalGenerator()
    return _regime_adaptive_generator
