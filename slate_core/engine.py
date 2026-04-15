"""
SLATE Trading Engine

Implements the OODA (Observe-Orient-Decide-Act) cycle for autonomous trading.

OODA Cycle for Trading:
- Observe: Collect market data, price action, indicators
- Orient: Analyze signals, regime detection, literature/strategy comparison
- Decide: Strategy selection, position sizing, risk assessment
- Act: Execute trades (paper trading only), monitor positions
- Learn: Update strategy performance, adapt parameters

NEVER executes live trades - paper trading and simulation only.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OODAPhase(Enum):
    """OODA Cycle phases."""
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"
    LEARN = "learn"


class MarketRegime(Enum):
    """Market regime types."""
    BULL_VOLATILE = "bull_volatile"
    BULL_STABLE = "bull_stable"
    BEAR_VOLATILE = "bear_volatile"
    BEAR_STABLE = "bear_stable"
    RANGING = "ranging"
    TRANSITION = "transition"


class Signal(Enum):
    """Trading signals."""
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"
    HOLD = "hold"
    NONE = "none"


@dataclass
class MarketObservation:
    """Data collected during Observe phase."""
    timestamp: datetime
    symbol: str
    price: float
    volume: float
    high: float
    low: float
    indicators: Dict[str, float] = field(default_factory=dict)
    orderbook: Optional[Dict] = None
    market_events: List[str] = field(default_factory=list)


@dataclass
class SituationAwareness:
    """Analysis from Orient phase."""
    regime: MarketRegime
    confidence: float
    signals: Dict[str, Signal]
    strategy_rankings: List[Tuple[str, float]]  # (strategy_id, score)
    risk_assessment: Dict[str, Any]
    context: str = ""


@dataclass
class TradingDecision:
    """Decision from Decide phase."""
    action: str
    strategy_id: str
    symbol: str
    side: str
    size: float
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reasoning: str
    confidence: float


@dataclass
class ActionResult:
    """Result from Act phase."""
    success: bool
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    executed_price: Optional[float] = None
    error: Optional[str] = None


class TradingEngine:
    """
    Main trading engine implementing OODA cycle.

    Coordinates data collection, analysis, decision making, and
    execution (paper trading only).
    """

    def __init__(self):
        self.running = False
        self.current_phase = OODAPhase.OBSERVE
        self.strategies: Dict[str, Dict] = {}
        self.active_positions: Dict[str, Dict] = {}
        self.ooda_state: Dict[str, Any] = {}
        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime] = None

        # Import sub-modules
        from .data.fetcher import HistoricalDataFetcher
        from .risk.manager import RiskManager
        from .statistics.regime import RegimeDetector

        self.data_fetcher = HistoricalDataFetcher()
        self.risk_manager = RiskManager()
        self.regime_detector = RegimeDetector()

    async def start(self):
        """Start the trading engine."""
        if self.running:
            logger.warning("Engine already running")
            return

        self.running = True
        logger.info("Trading Engine started in PAPER_TRADING mode")
        logger.info("NEVER executes live trades - paper trading only")

    async def stop(self):
        """Stop the trading engine."""
        self.running = False
        logger.info("Trading Engine stopped")

    async def run_cycle(self) -> Dict[str, Any]:
        """
        Run a complete OODA cycle.

        Returns:
            Dict with cycle results and state updates
        """
        if not self.running:
            self.running = True

        cycle_start = datetime.now()
        self.cycle_count += 1

        logger.info(f"Starting OODA cycle #{self.cycle_count}")

        try:
            # Observe: Collect market data
            observation = await self._observe()
            self.ooda_state['observation'] = observation

            # Orient: Analyze and assess
            awareness = await self._orient(observation)
            self.ooda_state['awareness'] = awareness

            # Decide: Make trading decision
            decision = await self._decide(observation, awareness)
            self.ooda_state['decision'] = decision

            # Act: Execute (paper trading)
            action_result = await self._act(decision)
            self.ooda_state['action_result'] = action_result

            # Learn: Update and adapt
            learning = await self._learn(observation, awareness, decision, action_result)
            self.ooda_state['learning'] = learning

            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            self.last_cycle_time = datetime.now()

            result = {
                'cycle_number': self.cycle_count,
                'duration_seconds': cycle_duration,
                'timestamp': datetime.now().isoformat(),
                'observation': {
                    'symbol': observation.symbol,
                    'price': observation.price
                },
                'awareness': {
                    'regime': awareness.regime.value,
                    'confidence': awareness.confidence
                },
                'decision': {
                    'action': decision.action,
                    'confidence': decision.confidence
                },
                'action_result': {
                    'success': action_result.success
                }
            }

            logger.info(f"OODA cycle #{self.cycle_count} completed in {cycle_duration:.2f}s")

            return result

        except Exception as e:
            logger.error(f"Error in OODA cycle: {e}", exc_info=True)
            return {
                'cycle_number': self.cycle_count,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def _observe(self) -> MarketObservation:
        """
        Observe phase: Collect market data.

        Gathers price data, indicators, orderbook, and market events.
        """
        self.current_phase = OODAPhase.OBSERVE
        logger.debug("Observe phase: Collecting market data")

        # Get active symbols from strategies
        symbols = self._get_active_symbols()
        primary_symbol = symbols[0] if symbols else "BTCUSDT"

        # Fetch market data
        candles = await self.data_fetcher.get_candles(primary_symbol, "1h", 100)
        ticker = await self.data_fetcher.get_ticker(primary_symbol)
        orderbook = await self.data_fetcher.get_orderbook(primary_symbol, 20)

        # Calculate technical indicators
        indicators = await self._calculate_indicators(candles)

        # Create observation
        observation = MarketObservation(
            timestamp=datetime.now(),
            symbol=primary_symbol,
            price=float(ticker.get('price', candles[-1]['close'] if candles else 0)),
            volume=float(ticker.get('volume', candles[-1]['volume'] if candles else 0)),
            high=float(candles[-1]['high'] if candles else 0),
            low=float(candles[-1]['low'] if candles else 0),
            indicators=indicators,
            orderbook=orderbook
        )

        logger.debug(f"Observed {primary_symbol} @ {observation.price}")
        return observation

    async def _orient(self, observation: MarketObservation) -> SituationAwareness:
        """
        Orient phase: Analyze market state.

        Detect regime, rank strategies, assess risk.
        """
        self.current_phase = OODAPhase.ORIENT
        logger.debug("Orient phase: Analyzing market state")

        # Detect market regime
        regime = await self.regime_detector.detect_regime(observation)
        regime_confidence = await self.regime_detector.get_confidence()

        # Generate and rank signals
        signals = {}
        strategy_rankings = []

        for strategy_id, strategy in self.strategies.items():
            if strategy.get('active', False):
                signal = await self._generate_signal(strategy, observation)
                signals[strategy_id] = signal

                score = await self._score_strategy(
                    strategy, signal, regime, observation
                )
                strategy_rankings.append((strategy_id, score))

        # Sort by score (descending)
        strategy_rankings.sort(key=lambda x: x[1], reverse=True)

        # Risk assessment
        risk_assessment = await self.risk_manager.assess_risk(
            observation, regime, signals
        )

        # Build context description
        context = self._build_context(regime, observation, signals)

        awareness = SituationAwareness(
            regime=regime,
            confidence=regime_confidence,
            signals=signals,
            strategy_rankings=strategy_rankings,
            risk_assessment=risk_assessment,
            context=context
        )

        logger.debug(f"Oriented: Regime={regime.value}, Top strategy={strategy_rankings[0][0] if strategy_rankings else None}")
        return awareness

    async def _decide(
        self,
        observation: MarketObservation,
        awareness: SituationAwareness
    ) -> TradingDecision:
        """
        Decide phase: Make trading decision.

        Select best strategy, determine position size, check risk limits.
        """
        self.current_phase = OODAPhase.DECIDE
        logger.debug("Decide phase: Making trading decision")

        # Check if we should trade
        risk_check = await self._check_risk_limits(awareness)

        if not risk_check['approved']:
            return TradingDecision(
                action="hold",
                strategy_id="",
                symbol=observation.symbol,
                side="none",
                size=0.0,
                entry_price=observation.price,
                stop_loss=None,
                take_profit=None,
                reasoning=f"Risk check failed: {risk_check['reason']}",
                confidence=0.0
            )

        # Get top strategy
        if not awareness.strategy_rankings:
            return TradingDecision(
                action="hold",
                strategy_id="",
                symbol=observation.symbol,
                side="none",
                size=0.0,
                entry_price=observation.price,
                stop_loss=None,
                take_profit=None,
                reasoning="No strategies available",
                confidence=0.0
            )

        top_strategy_id, top_score = awareness.strategy_rankings[0]
        top_strategy = self.strategies[top_strategy_id]
        signal = awareness.signals[top_strategy_id]

        # Determine action
        if signal == Signal.HOLD or signal == Signal.NONE:
            action = "hold"
            side = "none"
        elif signal == Signal.CLOSE:
            action = "close"
            side = "close"
        elif signal == Signal.LONG:
            action = "open"
            side = "long"
        elif signal == Signal.SHORT:
            action = "open"
            side = "short"
        else:
            action = "hold"
            side = "none"

        # Calculate position size
        if action == "open":
            position_size = await self._calculate_position_size(
                observation, awareness, top_strategy, side
            )
        else:
            position_size = 0.0

        # Calculate stop loss and take profit
        stop_loss, take_profit = await self._calculate_exit_levels(
            observation, top_strategy, side
        )

        decision = TradingDecision(
            action=action,
            strategy_id=top_strategy_id,
            symbol=observation.symbol,
            side=side,
            size=position_size,
            entry_price=observation.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=f"Strategy {top_strategy_id} (score: {top_score:.2f}), Regime: {awareness.regime.value}",
            confidence=min(top_score, 1.0)
        )

        logger.debug(f"Decided: {action} {side} {position_size} @ {observation.price}")
        return decision

    async def _act(self, decision: TradingDecision) -> ActionResult:
        """
        Act phase: Execute trading decision (PAPER TRADING ONLY).

        Simulates order execution without real trades.
        """
        self.current_phase = OODAPhase.ACT
        logger.debug("Act phase: Executing decision (PAPER TRADING)")

        if decision.action == "hold":
            return ActionResult(success=True, reasoning="No action taken")

        # PAPER TRADING ONLY - Never execute real trades
        logger.info(f"[PAPER TRADING] Would {decision.action} {decision.side} {decision.size} {decision.symbol}")
        logger.info(f"[PAPER TRADING] Entry: {decision.entry_price}, SL: {decision.stop_loss}, TP: {decision.take_profit}")
        logger.info(f"[PAPER TRADING] Reasoning: {decision.reasoning}")

        # Simulate execution
        if decision.action == "open":
            position_id = f"pos_{decision.symbol}_{decision.side}_{datetime.now().timestamp()}"

            self.active_positions[position_id] = {
                'id': position_id,
                'strategy_id': decision.strategy_id,
                'symbol': decision.symbol,
                'side': decision.side,
                'size': decision.size,
                'entry_price': decision.entry_price,
                'stop_loss': decision.stop_loss,
                'take_profit': decision.take_profit,
                'timestamp': datetime.now().isoformat(),
                'mode': 'paper_trading'
            }

            return ActionResult(
                success=True,
                order_id=f"paper_{position_id}",
                position_id=position_id,
                executed_price=decision.entry_price
            )

        elif decision.action == "close":
            # Find and close position
            for pos_id, pos in self.active_positions.items():
                if pos['symbol'] == decision.symbol:
                    del self.active_positions[pos_id]
                    return ActionResult(
                        success=True,
                        position_id=pos_id,
                        executed_price=decision.entry_price
                    )

            return ActionResult(success=True, reasoning="No position to close")

        return ActionResult(success=True, reasoning="Paper trading simulation")

    async def _learn(
        self,
        observation: MarketObservation,
        awareness: SituationAwareness,
        decision: TradingDecision,
        action_result: ActionResult
    ) -> Dict[str, Any]:
        """
        Learn phase: Update and adapt.

        Track performance, update strategy scores, adapt parameters.
        """
        self.current_phase = OODAPhase.LEARN
        logger.debug("Learn phase: Updating and adapting")

        learning_updates = {
            'timestamp': datetime.now().isoformat(),
            'strategy_updates': [],
            'regime_transition': False
        }

        # Update strategy performance if trade was made
        if decision.action in ["open", "close"] and action_result.success:
            strategy_id = decision.strategy_id

            if strategy_id in self.strategies:
                strategy = self.strategies[strategy_id]
                performance = strategy.get('performance', {})

                # Track trade
                trade = {
                    'timestamp': datetime.now().isoformat(),
                    'action': decision.action,
                    'side': decision.side,
                    'size': decision.size,
                    'price': decision.entry_price,
                    'reasoning': decision.reasoning
                }

                if 'trades' not in performance:
                    performance['trades'] = []
                performance['trades'].append(trade)

                strategy['performance'] = performance
                learning_updates['strategy_updates'].append(strategy_id)

        # Check for regime transition
        current_regime = awareness.regime
        previous_regime = self.ooda_state.get('awareness', SituationAwareness).regime if self.ooda_state.get('awareness') else None

        if previous_regime and current_regime != previous_regime:
            learning_updates['regime_transition'] = True
            learning_updates['previous_regime'] = previous_regime.value
            learning_updates['new_regime'] = current_regime.value
            logger.info(f"Regime transition: {previous_regime.value} → {current_regime.value}")

        return learning_updates

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _calculate_indicators(self, candles: List[Dict]) -> Dict[str, float]:
        """Calculate technical indicators from candle data."""
        indicators = {}

        if not candles or len(candles) < 20:
            return indicators

        closes = [c['close'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]

        # Simple Moving Averages
        if len(closes) >= 20:
            indicators['sma20'] = sum(closes[-20:]) / 20
        if len(closes) >= 50:
            indicators['sma50'] = sum(closes[-50:]) / 50

        # RSI (simplified)
        if len(closes) >= 15:
            gains = []
            losses = []
            for i in range(1, 15):
                change = closes[-i] - closes[-i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14

            if avg_loss > 0:
                rs = avg_gain / avg_loss
                indicators['rsi'] = 100 - (100 / (1 + rs))
            else:
                indicators['rsi'] = 100

        # Bollinger Bands (simplified)
        if len(closes) >= 20:
            sma20 = indicators['sma20']
            squared_diffs = [(c - sma20) ** 2 for c in closes[-20:]]
            std = (sum(squared_diffs) / 20) ** 0.5
            indicators['bb_upper'] = sma20 + (2 * std)
            indicators['bb_lower'] = sma20 - (2 * std)
            indicators['bb_middle'] = sma20

        return indicators

    async def _generate_signal(
        self,
        strategy: Dict,
        observation: MarketObservation
    ) -> Signal:
        """Generate trading signal from strategy."""
        # Simplified signal generation based on indicators
        indicators = observation.indicators

        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30:
                return Signal.LONG
            elif rsi > 70:
                return Signal.SHORT

        if 'sma20' in indicators and 'sma50' in indicators:
            if indicators['sma20'] > indicators['sma50']:
                return Signal.LONG
            else:
                return Signal.SHORT

        return Signal.HOLD

    async def _score_strategy(
        self,
        strategy: Dict,
        signal: Signal,
        regime: MarketRegime,
        observation: MarketObservation
    ) -> float:
        """Score a strategy based on multiple factors."""
        score = 0.5  # Base score

        # Historical performance
        performance = strategy.get('performance', {})
        if performance:
            win_rate = performance.get('win_rate', 0.5)
            score += (win_rate - 0.5) * 0.3

        # Regime alignment
        strategy_regimes = strategy.get('regimes', [])
        if regime.value in strategy_regimes or not strategy_regimes:
            score += 0.1

        # Signal strength
        if signal != Signal.HOLD and signal != Signal.NONE:
            score += 0.1

        return min(max(score, 0.0), 1.0)

    async def _calculate_position_size(
        self,
        observation: MarketObservation,
        awareness: SituationAwareness,
        strategy: Dict,
        side: str
    ) -> float:
        """Calculate position size based on risk management."""
        # Default position size (paper trading)
        return 0.01  # 1% of capital

    async def _calculate_exit_levels(
        self,
        observation: MarketObservation,
        strategy: Dict,
        side: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate stop loss and take profit levels."""
        if side == "long":
            sl = observation.price * 0.98  # 2% stop loss
            tp = observation.price * 1.04  # 4% take profit
        else:  # short
            sl = observation.price * 1.02
            tp = observation.price * 0.96

        return sl, tp

    async def _check_risk_limits(self, awareness: SituationAwareness) -> Dict:
        """Check if trading is within risk limits."""
        risk_assessment = awareness.risk_assessment

        if risk_assessment.get('risk_level') == 'critical':
            return {'approved': False, 'reason': 'Risk level critical'}

        if risk_assessment.get('exposure', 0) > 0.95:
            return {'approved': False, 'reason': 'Max exposure reached'}

        return {'approved': True}

    def _get_active_symbols(self) -> List[str]:
        """Get list of active symbols from strategies."""
        symbols = set()
        for strategy in self.strategies.values():
            if strategy.get('active', False):
                symbols.add(strategy.get('symbol', 'BTCUSDT'))
        return list(symbols)

    def _build_context(
        self,
        regime: MarketRegime,
        observation: MarketObservation,
        signals: Dict[str, Signal]
    ) -> str:
        """Build context description for decision making."""
        signal_summary = ", ".join([f"{sid}: {sig.value}" for sid, sig in signals.items()])

        return (
            f"Market Regime: {regime.value}, "
            f"Price: {observation.price}, "
            f"Signals: [{signal_summary}], "
            f"Active Positions: {len(self.active_positions)}"
        )

    # =========================================================================
    # Strategy Management Methods
    # =========================================================================

    async def create_strategy(
        self,
        name: str,
        code: str,
        language: str = "python",
        parameters: Optional[Dict] = None
    ) -> str:
        """Create a new trading strategy."""
        strategy_id = f"strategy_{datetime.now().timestamp()}"

        self.strategies[strategy_id] = {
            'id': strategy_id,
            'name': name,
            'code': code,
            'language': language,
            'parameters': parameters or {},
            'active': False,
            'created_at': datetime.now().isoformat(),
            'performance': {}
        }

        logger.info(f"Created strategy {strategy_id}: {name}")
        return strategy_id

    async def list_strategies(self) -> List[Dict]:
        """List all strategies."""
        return list(self.strategies.values())

    async def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """Get strategy by ID."""
        return self.strategies.get(strategy_id)

    async def update_strategy(
        self,
        strategy_id: str,
        name: str,
        code: str,
        language: str = "python",
        parameters: Optional[Dict] = None
    ) -> Dict:
        """Update an existing strategy."""
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        self.strategies[strategy_id].update({
            'name': name,
            'code': code,
            'language': language,
            'parameters': parameters or {},
            'updated_at': datetime.now().isoformat()
        })

        logger.info(f"Updated strategy {strategy_id}")
        return self.strategies[strategy_id]

    async def delete_strategy(self, strategy_id: str):
        """Delete a strategy."""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            logger.info(f"Deleted strategy {strategy_id}")

    async def activate_strategy(self, strategy_id: str) -> Dict:
        """Activate a strategy for paper trading."""
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        self.strategies[strategy_id]['active'] = True
        self.strategies[strategy_id]['activated_at'] = datetime.now().isoformat()

        logger.info(f"Activated strategy {strategy_id}")
        return self.strategies[strategy_id]

    async def deactivate_strategy(self, strategy_id: str) -> Dict:
        """Deactivate a strategy."""
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        self.strategies[strategy_id]['active'] = False

        logger.info(f"Deactivated strategy {strategy_id}")
        return self.strategies[strategy_id]

    async def get_strategy_performance(self, strategy_id: str) -> Dict:
        """Get strategy performance metrics."""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        return strategy.get('performance', {})

    async def get_strategy_positions(self, strategy_id: str) -> List[Dict]:
        """Get positions for a strategy."""
        return [
            pos for pos in self.active_positions.values()
            if pos.get('strategy_id') == strategy_id
        ]

    async def get_strategy_orders(self, strategy_id: str) -> List[Dict]:
        """Get order history for a strategy."""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        return strategy.get('performance', {}).get('trades', [])

    async def get_strategy_signals(
        self, strategy_id: str, limit: int = 100
    ) -> List[Dict]:
        """Get recent signals from a strategy."""
        # Simplified - return recent trades as signals
        trades = await self.get_strategy_orders(strategy_id)
        return trades[-limit:]

    async def validate_strategy(self, strategy_id: str) -> Dict:
        """Validate strategy code and configuration."""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return {'valid': False, 'error': 'Strategy not found'}

        # Basic validation
        if not strategy.get('code'):
            return {'valid': False, 'error': 'No code provided'}

        if strategy.get('language') not in ['python', 'pine_script', 'haas_script']:
            return {'valid': False, 'error': 'Unsupported language'}

        return {'valid': True, 'language': strategy['language']}

    async def export_all_strategies(self) -> Dict:
        """Export all strategies as JSON."""
        return {
            'strategies': self.strategies,
            'positions': self.active_positions,
            'exported_at': datetime.now().isoformat()
        }

    async def export_strategies(self, format: str = "json") -> Any:
        """Export strategies in specified format."""
        if format == "json":
            return await self.export_all_strategies()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def import_strategies(self, data: Dict) -> Dict:
        """Import strategies from data."""
        imported = []

        for strategy_id, strategy in data.get('strategies', {}).items():
            if strategy_id not in self.strategies:
                self.strategies[strategy_id] = strategy
                imported.append(strategy_id)

        return {'imported': imported, 'count': len(imported)}

    # =========================================================================
    # Engine Status Methods
    # =========================================================================

    async def get_status(self) -> Dict:
        """Get engine status."""
        return {
            'running': self.running,
            'current_phase': self.current_phase.value,
            'cycle_count': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            'active_strategies': sum(1 for s in self.strategies.values() if s.get('active', False)),
            'active_positions': len(self.active_positions),
            'mode': 'paper_trading'
        }

    async def get_ooda_state(self) -> Dict:
        """Get current OODA cycle state."""
        return {
            'phase': self.current_phase.value,
            'observation': self.ooda_state.get('observation', {}).get('symbol') if self.ooda_state.get('observation') else None,
            'awareness': {
                'regime': self.ooda_state.get('awareness', {}).regime.value if isinstance(self.ooda_state.get('awareness'), SituationAwareness) else None
            } if self.ooda_state.get('awareness') else None,
            'decision': {
                'action': self.ooda_state.get('decision', {}).action if isinstance(self.ooda_state.get('decision'), TradingDecision) else None
            } if self.ooda_state.get('decision') else None,
            'cycle_count': self.cycle_count
        }
