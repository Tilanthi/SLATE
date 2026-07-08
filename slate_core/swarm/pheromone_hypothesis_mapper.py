#!/usr/bin/env python3
"""
Pheromone Hypothesis Mapper Implementation

Maps pheromone signals to hypothesis parameters for guided discovery.
This enables stigmergic communication to improve strategy quality through collective learning.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from slate_core.swarm.swarm_discovery import PheromoneType, PheromoneSignal

logger = logging.getLogger(__name__)


class PheromoneHypothesisMapper:
    """
    Maps pheromone signals to hypothesis parameters for guided discovery.

    This class translates stigmergic signals from the swarm intelligence system
    into parameter adjustments that improve hypothesis quality. It implements
    collective learning by using pheromone signals to guide parameter selection
    toward successful regions and away from failed approaches.

    Pheromone Types:
    - DISCOVERY: Positive signals that guide toward successful parameter regions
    - AVOIDANCE: Negative signals that warn away from failed parameter combinations
    - REGIME: Context signals that share regime-specific intelligence
    - INNOVATION: Creative signals that encourage novel parameter exploration

    Usage:
        mapper = PheromoneHypothesisMapper()
        optimized_params = mapper.map_pheromones_to_parameters(pheromones, base_params)
    """

    def __init__(self, decay_rate: float = 0.05, guidance_strength: float = 0.3):
        """
        Initialize PheromoneHypothesisMapper.

        Args:
            decay_rate: Rate at which pheromone signals decay (default 0.05 per hour)
            guidance_strength: Strength of pheromone guidance on parameters (0.0-1.0)
        """
        self.decay_rate = decay_rate
        self.guidance_strength = guidance_strength

        # Pheromone processing statistics
        self.pheromones_processed = 0
        self.guidance_events = 0
        self.processing_history = []

        logger.info(f"PheromoneHypothesisMapper initialized: decay_rate={decay_rate}, "
                   f"guidance_strength={guidance_strength}")

    def map_pheromones_to_parameters(self, pheromones: List[PheromoneSignal],
                                     base_params: Dict[str, Any],
                                     hypothesis_type: str = 'momentum') -> Dict[str, Any]:
        """
        Use pheromone signals to guide parameter selection.

        This method processes active pheromone signals and adjusts base parameters
        to align with collective intelligence discoveries.

        Args:
            pheromones: List of active pheromone signals
            base_params: Base parameter dictionary to optimize
            hypothesis_type: Strategy type for parameter-specific adjustments

        Returns:
            Optimized parameter dictionary influenced by pheromone signals
        """
        optimized_params = base_params.copy()

        if not pheromones:
            return optimized_params

        try:
            # Filter relevant pheromones (not decayed, recent)
            active_pheromones = self._filter_active_pheromones(pheromones)

            if not active_pheromones:
                return optimized_params

            # Process each pheromone type
            for pheromone in active_pheromones:
                try:
                    if pheromone.pheromone_type == PheromoneType.DISCOVERY:
                        # Adjust parameters toward successful regions
                        optimized_params.update(self._adjust_toward_discovery(pheromone, optimized_params, hypothesis_type))
                        self.guidance_events += 1

                    elif pheromone.pheromone_type == PheromoneType.AVOIDANCE:
                        # Adjust parameters away from failure regions
                        optimized_params.update(self._adjust_away_from_avoidance(pheromone, optimized_params, hypothesis_type))
                        self.guidance_events += 1

                    elif pheromone.pheromone_type == PheromoneType.REGIME:
                        # Use regime intelligence for parameter adaptation
                        optimized_params.update(self._adapt_to_regime(pheromone, optimized_params, hypothesis_type))
                        self.guidance_events += 1

                    elif pheromone.pheromone_type == PheromoneType.INNOVATION:
                        # Add creative parameter exploration
                        optimized_params.update(self._explore_innovatively(pheromone, optimized_params, hypothesis_type))
                        self.guidance_events += 1

                except Exception as e:
                    logger.warning(f"Error processing pheromone signal: {e}")

            self.pheromones_processed += len(active_pheromones)

            # Track processing
            self.processing_history.append({
                'timestamp': datetime.now(),
                'pheromones_count': len(active_pheromones),
                'guidance_events': self.guidance_events,
                'hypothesis_type': hypothesis_type
            })

            return optimized_params

        except Exception as e:
            logger.error(f"Error mapping pheromones to parameters: {e}")
            return base_params

    def _filter_active_pheromones(self, pheromones: List[PheromoneSignal]) -> List[PheromoneSignal]:
        """Filter active pheromones (not decayed, recent enough)."""
        now = datetime.now()
        active_pheromones = []

        for pheromone in pheromones:
            # Calculate decay
            time_diff = (now - pheromone.timestamp).total_seconds() / 3600  # hours
            decay_factor = np.exp(-self.decay_rate * time_diff)

            # Check if pheromone is still strong enough
            if pheromone.strength * decay_factor > 0.1:  # 10% threshold
                active_pheromones.append(pheromone)

        return active_pheromones

    def _adjust_toward_discovery(self, pheromone: PheromoneSignal, params: Dict[str, Any],
                               hypothesis_type: str) -> Dict[str, Any]:
        """Adjust parameters toward successful discovery regions."""
        adjustments = {}

        try:
            # Extract location information (parameter space coordinates)
            location = pheromone.location
            strength = pheromone.strength

            # Parse location (format: "param1=value1,param2=value2")
            if isinstance(location, str) and '=' in location:
                param_pairs = location.split(',')
                for pair in param_pairs:
                    if '=' in pair:
                        param_name, param_value = pair.split('=', 1)

                        try:
                            # Convert parameter value to appropriate type
                            if '.' in param_value:
                                param_value = float(param_value)
                            else:
                                param_value = int(param_value)

                            # Apply guidance strength (blend current value with suggested value)
                            current_value = params.get(param_name, param_value)
                            blended_value = current_value + (param_value - current_value) * self.guidance_strength * strength

                            adjustments[param_name] = blended_value

                        except ValueError:
                            logger.debug(f"Could not convert parameter value: {param_value}")

        except Exception as e:
            logger.warning(f"Error adjusting toward discovery: {e}")

        return adjustments

    def _adjust_away_from_avoidance(self, pheromone: PheromoneSignal, params: Dict[str, Any],
                                  hypothesis_type: str) -> Dict[str, Any]:
        """Adjust parameters away from avoidance regions."""
        adjustments = {}

        try:
            # Extract location information
            location = pheromone.location
            strength = pheromone.strength

            # Parse location and move away from those values
            if isinstance(location, str) and '=' in location:
                param_pairs = location.split(',')
                for pair in param_pairs:
                    if '=' in pair:
                        param_name, param_value = pair.split('=', 1)

                        try:
                            # Convert parameter value
                            if '.' in param_value:
                                param_value = float(param_value)
                            else:
                                param_value = int(param_value)

                            # Move away from suggested value (invert guidance)
                            current_value = params.get(param_name, param_value)
                            distance = param_value - current_value

                            # Move in opposite direction
                            if abs(distance) > 0:
                                adjusted_value = current_value - distance * self.guidance_strength * strength * 0.5
                                adjustments[param_name] = adjusted_value

                        except ValueError:
                            logger.debug(f"Could not convert parameter value: {param_value}")

        except Exception as e:
            logger.warning(f"Error adjusting away from avoidance: {e}")

        return adjustments

    def _adapt_to_regime(self, pheromone: PheromoneSignal, params: Dict[str, Any],
                        hypothesis_type: str) -> Dict[str, Any]:
        """Adapt parameters based on regime intelligence."""
        adjustments = {}

        try:
            # Extract regime information from metadata
            regime = pheromone.metadata.get('regime', 'UNKNOWN')
            volatility = pheromone.metadata.get('volatility', 'NORMAL')

            # Regime-specific parameter adjustments
            if hypothesis_type == 'momentum':
                if regime == 'TRENDING_UP':
                    adjustments['fast_ema'] = params.get('fast_ema', 12) * 0.9  # Faster signals
                elif regime == 'SIDEWAYS':
                    adjustments['fast_ema'] = params.get('fast_ema', 12) * 1.1  # Slower signals

            elif hypothesis_type == 'mean_reversion':
                if volatility == 'HIGH':
                    adjustments['bb_std'] = params.get('bb_std', 2.0) * 1.2  # Wider bands
                elif volatility == 'LOW':
                    adjustments['bb_std'] = params.get('bb_std', 2.0) * 0.9  # Tighter bands

        except Exception as e:
            logger.warning(f"Error adapting to regime: {e}")

        return adjustments

    def _explore_innovatively(self, pheromone: PheromoneSignal, params: Dict[str, Any],
                            hypothesis_type: str) -> Dict[str, Any]:
        """Add creative parameter exploration."""
        adjustments = {}

        try:
            # Extract innovation suggestion
            innovation = pheromone.metadata.get('innovation_type', 'random')

            if innovation == 'parameter_perturbation':
                # Small random adjustments to explore nearby parameter space
                for param_name, param_value in params.items():
                    if isinstance(param_value, (int, float)):
                        # Add small random perturbation
                        perturbation = np.random.normal(0, 0.05 * abs(param_value))
                        adjustments[param_name] = param_value + perturbation

            elif innovation == 'novel_combination':
                # Suggest novel parameter combinations
                if hypothesis_type == 'momentum':
                    # Try EMA combinations not commonly tested
                    if params.get('fast_ema', 12) == 12:
                        adjustments['fast_ema'] = 8  # Try faster EMA

        except Exception as e:
            logger.warning(f"Error exploring innovatively: {e}")

        return adjustments

    def get_mapper_summary(self) -> Dict[str, Any]:
        """Get summary of mapper activity."""
        return {
            'pheromones_processed': self.pheromones_processed,
            'guidance_events': self.guidance_events,
            'decay_rate': self.decay_rate,
            'guidance_strength': self.guidance_strength,
            'recent_processing': self.processing_history[-10:] if self.processing_history else []
        }

    def reset_statistics(self):
        """Reset mapper statistics."""
        self.pheromones_processed = 0
        self.guidance_events = 0
        self.processing_history = []


def get_pheromone_hypothesis_mapper() -> PheromoneHypothesisMapper:
    """Get global pheromone hypothesis mapper instance."""
    # For now, create new instance each time
    # Could be converted to singleton pattern if needed
    return PheromoneHypothesisMapper()
