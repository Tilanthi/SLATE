#!/usr/bin/env python3
"""
SLATE Continuous Monitoring System

Phase 5: Autonomous Research Agenda

Implements continuous market monitoring:
- Opportunity scanning
- Anomaly detection
- Correlation breakdown warnings
- Regime change alerts

Critical for autonomous opportunity detection.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Enables proactive research
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
from scipy import stats
from collections import deque

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OpportunityType(Enum):
    """Types of opportunities."""
    ARBITRAGE = "arbitrage"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    REGIME_CHANGE = "regime_change"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_CRUNCH = "liquidity_crunch"


@dataclass
class Alert:
    """A monitoring alert."""
    id: str
    type: OpportunityType
    severity: AlertSeverity
    title: str
    description: str

    # Context
    affected_markets: List[str]
    timestamp: datetime
    expiry: Optional[datetime]

    # Data
    current_value: float
    threshold_value: float
    deviation: float

    # Actionability
    confidence: float
    expected_duration: Optional[float]  # In hours
    suggested_actions: List[str]

    # Status
    acknowledged: bool = False
    action_taken: bool = False


class OpportunityScanner:
    """
    Scan for trading opportunities.

    Identifies patterns that may represent profitable opportunities.
    """

    def __init__(self, lookback_period: int = 100):
        self.lookback_period = lookback_period
        self.historical_data: Dict[str, deque] = {}

        logger.info(f"OpportunityScanner initialized with {lookback_period} period lookback")

    async def scan_opportunities(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """
        Scan for opportunities.

        Args:
            market_data: Current market data
            current_time: Current timestamp

        Returns:
            List of opportunity alerts
        """

        alerts = []

        # Update historical data
        for symbol in market_data.columns:
            if symbol not in self.historical_data:
                self.historical_data[symbol] = deque(maxlen=self.lookback_period)

            if len(market_data) > 0:
                self.historical_data[symbol].append(market_data[symbol].iloc[-1])

        # Scan for opportunities
        alerts.extend(await self._scan_arbitrage(market_data, current_time))
        alerts.extend(await self._scan_momentum(market_data, current_time))
        alerts.extend(await self._scan_mean_reversion(market_data, current_time))
        alerts.extend(await self._scan_volatility_spikes(market_data, current_time))

        return alerts

    async def _scan_arbitrage(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """Scan for arbitrage opportunities."""

        alerts = []

        # Look for price discrepancies (would need multi-exchange data)
        # For now, simulate with synthetic spreads
        if len(market_data.columns) >= 2:
            symbol1, symbol2 = market_data.columns[:2]
            spread = market_data[symbol1].iloc[-1] - market_data[symbol2].iloc[-1]
            spread_pct = spread / market_data[symbol2].iloc[-1]

            if abs(spread_pct) > 0.005:  # 0.5% threshold
                alert = Alert(
                    id=f"arb_{current_time.strftime('%Y%m%d%H%M')}",
                    type=OpportunityType.ARBITRAGE,
                    severity=AlertSeverity.MEDIUM,
                    title=f"Price Discrepancy: {symbol1} vs {symbol2}",
                    description=f"Spread of {spread_pct:.2%} detected",
                    affected_markets=[symbol1, symbol2],
                    timestamp=current_time,
                    expiry=current_time + timedelta(hours=1),
                    current_value=spread_pct,
                    threshold_value=0.005,
                    deviation=spread_pct / 0.005,
                    confidence=0.7,
                    expected_duration=0.5,
                    suggested_actions=[
                        "Investigate arbitrage execution",
                        "Check execution costs",
                        "Verify funding rates"
                    ]
                )
                alerts.append(alert)

        return alerts

    async def _scan_momentum(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """Scan for momentum opportunities."""

        alerts = []

        for symbol in market_data.columns:
            if len(self.historical_data[symbol]) < 20:
                continue

            # Calculate momentum
            recent = list(self.historical_data[symbol])[-20:]
            momentum = (recent[-1] - recent[0]) / recent[0]

            # Strong momentum threshold
            if abs(momentum) > 0.05:  # 5% move
                direction = "upward" if momentum > 0 else "downward"
                alert = Alert(
                    id=f"mom_{symbol}_{current_time.strftime('%Y%m%d%H%M')}",
                    type=OpportunityType.MOMENTUM,
                    severity=AlertSeverity.HIGH if abs(momentum) > 0.1 else AlertSeverity.MEDIUM,
                    title=f"Strong {direction.capitalize()} Momentum: {symbol}",
                    description=f"{symbol} showing {abs(momentum):.2%} {direction} momentum",
                    affected_markets=[symbol],
                    timestamp=current_time,
                    expiry=current_time + timedelta(hours=4),
                    current_value=momentum,
                    threshold_value=0.05,
                    deviation=abs(momentum) / 0.05,
                    confidence=0.8,
                    expected_duration=4.0,
                    suggested_actions=[
                        "Test trend-following strategy",
                        "Check for volume confirmation",
                        "Assess sustainability"
                    ]
                )
                alerts.append(alert)

        return alerts

    async def _scan_mean_reversion(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """Scan for mean reversion opportunities."""

        alerts = []

        for symbol in market_data.columns:
            if len(self.historical_data[symbol]) < 50:
                continue

            # Calculate z-score
            recent = list(self.historical_data[symbol])[-50:]
            mean = np.mean(recent)
            std = np.std(recent)
            current = recent[-1]
            z_score = (current - mean) / std if std > 0 else 0

            # Extreme z-score threshold
            if abs(z_score) > 2.5:
                direction = "oversold" if z_score < 0 else "overbought"
                alert = Alert(
                    id=f"mr_{symbol}_{current_time.strftime('%Y%m%d%H%M')}",
                    type=OpportunityType.MEAN_REVERSION,
                    severity=AlertSeverity.HIGH if abs(z_score) > 3 else AlertSeverity.MEDIUM,
                    title=f"Mean Reversion Signal: {symbol}",
                    description=f"{symbol} is {direction} (Z-score: {z_score:.2f})",
                    affected_markets=[symbol],
                    timestamp=current_time,
                    expiry=current_time + timedelta(hours=6),
                    current_value=z_score,
                    threshold_value=2.5,
                    deviation=abs(z_score) / 2.5,
                    confidence=0.75,
                    expected_duration=6.0,
                    suggested_actions=[
                        "Test mean reversion strategy",
                        "Check for regime change",
                        "Assess reversal probability"
                    ]
                )
                alerts.append(alert)

        return alerts

    async def _scan_volatility_spikes(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """Scan for volatility spikes."""

        alerts = []

        for symbol in market_data.columns:
            if len(self.historical_data[symbol]) < 30:
                continue

            # Calculate rolling volatility
            recent = list(self.historical_data[symbol])[-30:]
            returns = pd.Series(recent).pct_change().dropna()

            if len(returns) < 10:
                continue

            current_vol = returns.std() * np.sqrt(252)
            historical_vol = returns.iloc[:-10].std() * np.sqrt(252) if len(returns) > 10 else current_vol

            if historical_vol > 0:
                vol_ratio = current_vol / historical_vol
                if vol_ratio > 2.0:  # Volatility doubled
                    alert = Alert(
                        id=f"vol_{symbol}_{current_time.strftime('%Y%m%d%H%M')}",
                        type=OpportunityType.VOLATILITY_SPIKE,
                        severity=AlertSeverity.HIGH,
                        title=f"Volatility Spike: {symbol}",
                        description=f"Volatility increased by {vol_ratio:.1f}x",
                        affected_markets=[symbol],
                        timestamp=current_time,
                        expiry=current_time + timedelta(hours=2),
                        current_value=vol_ratio,
                        threshold_value=2.0,
                        deviation=vol_ratio / 2.0,
                        confidence=0.85,
                        expected_duration=2.0,
                        suggested_actions=[
                            "Reduce position sizes",
                            "Check stop-loss levels",
                            "Consider volatility strategies"
                        ]
                    )
                    alerts.append(alert)

        return alerts


class AnomalyDetector:
    """
    Detect anomalies in market data.

    Uses statistical methods to identify unusual behavior.
    """

    def __init__(self, sensitivity: float = 3.0):
        self.sensitivity = sensitivity  # Standard deviations
        self.baseline_stats: Dict[str, Dict[str, float]] = {}

        logger.info(f"AnomalyDetector initialized with {sensitivity}σ sensitivity")

    async def detect_anomalies(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """
        Detect anomalies in market data.

        Args:
            market_data: Current market data
            current_time: Current timestamp

        Returns:
            List of anomaly alerts
        """

        alerts = []

        for symbol in market_data.columns:
            # Update baseline statistics
            if symbol not in self.baseline_stats:
                self.baseline_stats[symbol] = {
                    'mean': market_data[symbol].iloc[-1],
                    'std': 0.01,
                    'count': 1
                }
                continue

            # Calculate returns
            if len(market_data[symbol]) > 1:
                returns = market_data[symbol].pct_change().dropna()
                if len(returns) > 0:
                    latest_return = returns.iloc[-1]
                    baseline = self.baseline_stats[symbol]

                    # Z-score anomaly detection
                    if baseline['std'] > 0:
                        z_score = abs(latest_return - baseline['mean']) / baseline['std']

                        if z_score > self.sensitivity:
                            alert = Alert(
                                id=f"anom_{symbol}_{current_time.strftime('%Y%m%d%H%M')}",
                                type=OpportunityType.VOLATILITY_SPIKE,
                                severity=AlertSeverity.HIGH if z_score > 5 else AlertSeverity.MEDIUM,
                                title=f"Statistical Anomaly: {symbol}",
                                description=f"{symbol} return {z_score:.1f}σ from baseline",
                                affected_markets=[symbol],
                                timestamp=current_time,
                                expiry=current_time + timedelta(hours=1),
                                current_value=z_score,
                                threshold_value=self.sensitivity,
                                deviation=z_score / self.sensitivity,
                                confidence=min(0.95, z_score / 10),
                                expected_duration=1.0,
                                suggested_actions=[
                                    "Investigate cause of anomaly",
                                    "Check for news events",
                                    "Verify data quality"
                                ]
                            )
                            alerts.append(alert)

                    # Update baseline
                    baseline['mean'] = baseline['mean'] * 0.95 + latest_return * 0.05
                    baseline['std'] = baseline['std'] * 0.95 + abs(latest_return - baseline['mean']) * 0.05

        return alerts


class CorrelationMonitor:
    """
    Monitor correlation breakdowns.

    Correlations can break down in stress, creating opportunities.
    """

    def __init__(self, window: int = 60, threshold: float = 0.3):
        self.window = window
        self.threshold = threshold
        self.historical_correlations: Dict[Tuple[str, str], float] = {}

        logger.info(f"CorrelationMonitor initialized (window={window}, threshold={threshold})")

    async def monitor_correlations(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """
        Monitor for correlation breakdowns.

        Args:
            market_data: Current market data
            current_time: Current timestamp

        Returns:
            List of correlation breakdown alerts
        """

        alerts = []

        if len(market_data.columns) < 2:
            return alerts

        # Calculate current correlations
        returns = market_data.pct_change().dropna()

        for i, symbol1 in enumerate(market_data.columns):
            for symbol2 in market_data.columns[i + 1:]:
                pair = (symbol1, symbol2)

                # Calculate current correlation
                if len(returns) >= self.window:
                    current_corr = returns[symbol1].tail(self.window).corr(returns[symbol2].tail(self.window))

                    # Check for breakdown
                    if pair in self.historical_correlations:
                        historical_corr = self.historical_correlations[pair]
                        correlation_change = abs(current_corr - historical_corr)

                        if correlation_change > self.threshold:
                            alert = Alert(
                                id=f"corr_breakdown_{symbol1}_{symbol2}_{current_time.strftime('%Y%m%d%H%M')}",
                                type=OpportunityType.CORRELATION_BREAKDOWN,
                                severity=AlertSeverity.HIGH if correlation_change > 0.5 else AlertSeverity.MEDIUM,
                                title=f"Correlation Breakdown: {symbol1}-{symbol2}",
                                description=f"Correlation changed from {historical_corr:.2f} to {current_corr:.2f}",
                                affected_markets=[symbol1, symbol2],
                                timestamp=current_time,
                                expiry=current_time + timedelta(hours=12),
                                current_value=current_corr,
                                threshold_value=historical_corr,
                                deviation=correlation_change / self.threshold,
                                confidence=0.7,
                                expected_duration=12.0,
                                suggested_actions=[
                                    "Investigate cause of breakdown",
                                    "Test pair trading strategies",
                                    "Update correlation models"
                                ]
                            )
                            alerts.append(alert)

                    # Update historical correlation
                    self.historical_correlations[pair] = current_corr

        return alerts


class RegimeChangeDetector:
    """
    Detect market regime changes.

    Regime changes signal major shifts in market behavior.
    """

    def __init__(self, window: int = 252):
        self.window = window
        self.current_regime = "UNKNOWN"
        self.regime_history: List[Tuple[datetime, str]] = []

        logger.info(f"RegimeChangeDetector initialized (window={window})")

    async def detect_regime_change(
        self,
        market_data: pd.DataFrame,
        current_time: datetime
    ) -> List[Alert]:
        """
        Detect regime changes.

        Args:
            market_data: Current market data
            current_time: Current timestamp

        Returns:
            List of regime change alerts
        """

        alerts = []

        if len(market_data) < self.window:
            return alerts

        # Use BTC as market proxy
        if 'BTC' not in market_data.columns and len(market_data.columns) > 0:
            market_symbol = market_data.columns[0]
        else:
            market_symbol = 'BTC'

        if market_symbol not in market_data.columns:
            return alerts

        # Calculate returns
        returns = market_data[market_symbol].pct_change().dropna()

        if len(returns) < self.window:
            return alerts

        # Calculate regime indicators
        recent_returns = returns.tail(self.window)
        volatility = recent_returns.std() * np.sqrt(252)
        trend = recent_returns.sum()
        max_drawdown = self._calculate_max_drawdown(recent_returns)

        # Classify regime
        new_regime = self._classify_regime(volatility, trend, max_drawdown)

        # Check for regime change
        if new_regime != self.current_regime and self.current_regime != "UNKNOWN":
            alert = Alert(
                id=f"regime_change_{current_time.strftime('%Y%m%d%H%M')}",
                type=OpportunityType.REGIME_CHANGE,
                severity=AlertSeverity.CRITICAL,
                title=f"Regime Change: {self.current_regime} → {new_regime}",
                description=f"Market regime changed from {self.current_regime} to {new_regime}",
                affected_markets=[market_symbol],
                timestamp=current_time,
                expiry=current_time + timedelta(days=7),
                current_value=0.0,
                threshold_value=0.0,
                deviation=1.0,
                confidence=0.8,
                expected_duration=168.0,  # 1 week
                suggested_actions=[
                    "Review all active strategies",
                    "Adjust risk parameters",
                    "Update regime-dependent models",
                    "Consider regime-specific strategies"
                ]
            )
            alerts.append(alert)

        self.current_regime = new_regime
        self.regime_history.append((current_time, new_regime))

        return alerts

    def _classify_regime(
        self,
        volatility: float,
        trend: float,
        max_drawdown: float
    ) -> str:
        """Classify market regime."""

        if volatility > 1.0:
            return "HIGH_VOLATILITY"
        elif max_drawdown < -0.2:
            return "BEAR_MARKET"
        elif trend > 0.2:
            return "BULL_MARKET"
        elif abs(trend) < 0.05:
            return "SIDEWAYS"
        else:
            return "TRANSITION"


class ContinuousMonitor:
    """
    Unified continuous monitoring system.

    Coordinates all monitoring components.
    """

    def __init__(self):
        self.opportunity_scanner = OpportunityScanner()
        self.anomaly_detector = AnomalyDetector()
        self.correlation_monitor = CorrelationMonitor()
        self.regime_detector = RegimeChangeDetector()

        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []

        logger.info("ContinuousMonitor initialized")

    async def monitor(
        self,
        market_data: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> List[Alert]:
        """
        Perform comprehensive monitoring.

        Args:
            market_data: Current market data
            current_time: Current timestamp

        Returns:
            List of new alerts
        """

        if current_time is None:
            current_time = datetime.now()

        all_alerts = []

        # Run all monitors
        all_alerts.extend(await self.opportunity_scanner.scan_opportunities(market_data, current_time))
        all_alerts.extend(await self.anomaly_detector.detect_anomalies(market_data, current_time))
        all_alerts.extend(await self.correlation_monitor.monitor_correlations(market_data, current_time))
        all_alerts.extend(await self.regime_detector.detect_regime_change(market_data, current_time))

        # Filter duplicates
        seen_ids = {alert.id for alert in self.active_alerts}
        new_alerts = [alert for alert in all_alerts if alert.id not in seen_ids]

        # Add to active alerts
        self.active_alerts.extend(new_alerts)

        # Clean up expired alerts
        self.active_alerts = [
            alert for alert in self.active_alerts
            if alert.expiry is None or alert.expiry > current_time
        ]

        # Move resolved alerts to history
        for alert in all_alerts:
            if alert.action_taken or (alert.expiry and alert.expiry <= current_time):
                self.alert_history.append(alert)
                if alert in self.active_alerts:
                    self.active_alerts.remove(alert)

        logger.info(f"Monitoring complete: {len(new_alerts)} new alerts")

        return new_alerts

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        type: Optional[OpportunityType] = None
    ) -> List[Alert]:
        """Get active alerts, optionally filtered."""

        alerts = self.active_alerts

        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]

        if type is not None:
            alerts = [a for a in alerts if a.type == type]

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def generate_monitoring_report(self) -> str:
        """Generate monitoring report."""

        report = f"""
{'='*60}
CONTINUOUS MONITORING REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ACTIVE ALERTS: {len(self.active_alerts)}
ALERT HISTORY: {len(self.alert_history)}

ACTIVE BY SEVERITY:
"""

        severity_counts = {}
        for alert in self.active_alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        for severity, count in sorted(severity_counts.items(), key=lambda x: x[0].value, reverse=True):
            report += f"  {severity.value.upper()}: {count}\n"

        report += f"\nACTIVE BY TYPE:\n"

        type_counts = {}
        for alert in self.active_alerts:
            type_counts[alert.type] = type_counts.get(alert.type, 0) + 1

        for opp_type, count in sorted(type_counts.items(), key=lambda x: x[0].value):
            report += f"  {opp_type.value.replace('_', ' ').title()}: {count}\n"

        report += f"\nRECENT ALERTS:\n"

        for alert in sorted(self.active_alerts, key=lambda a: a.timestamp, reverse=True)[:10]:
            report += f"""
[{alert.severity.value.upper()}] {alert.title}
  Type: {alert.type.value}
  Markets: {', '.join(alert.affected_markets)}
  Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
  Description: {alert.description}
"""

        return report


# Singleton instance
_continuous_monitor = None


def get_continuous_monitor() -> ContinuousMonitor:
    """Get or create continuous monitor instance."""
    global _continuous_monitor
    if _continuous_monitor is None:
        _continuous_monitor = ContinuousMonitor()
    return _continuous_monitor
