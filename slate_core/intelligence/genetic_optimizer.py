#!/usr/bin/env python3
"""
SLATE Genetic Algorithm Strategy Optimizer

Phase 2: Genetic Algorithm Optimization for Strategy Parameters

Uses evolutionary algorithms to optimize trading strategy parameters
through survival of the fittest strategies.

Key Capabilities:
- Population-based parameter search
- Multi-objective optimization (PnL vs Drawdown)
- Fitness function focused on USDT profit
- Mutation and crossover for diversity
- Elitism to preserve best strategies
- Regime-aware optimization

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Critical for finding profitable strategies
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import random
import json
from pathlib import Path

# Optimization library
import optuna

# Import ML discovery
from .ml_strategy_discovery import get_ml_discovery, MLModelType

logger = logging.getLogger(__name__)


class OptimizationObjective(Enum):
    """Optimization objectives."""
    MAXIMIZE_PROFIT = "maximize_profit"
    MINIMIZE_DRAWDOWN = "minimize_drawdown"
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MAXIMIZE_WIN_RATE = "maximize_win_rate"
    MULTI_OBJECTIVE = "multi_objectective"


@dataclass
class StrategyGenome:
    """A strategy's genetic parameters."""
    genome_id: str
    parameters: Dict[str, Any]
    fitness_score: float
    profit_usdt: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    generation: int
    parent_ids: List[str] = field(default_factory=list)

    def dominates(self, other: 'StrategyGenome') -> bool:
        """Check if this genome dominates another (Pareto)."""
        return (self.profit_usdt >= other.profit_usdt and
                self.max_drawdown_pct <= other.max_drawdown_pct and
                (self.profit_usdt > other.profit_usdt or
                 self.max_drawdown_pct < other.max_drawdown_pct))


class GeneticAlgorithmOptimizer:
    """
    Genetic algorithm optimizer for trading strategies.

    Evolution process:
    1. Initialize random population
    2. Evaluate fitness of each individual
    3. Select best performers (selection)
    4. Create new generation (crossover + mutation)
    5. Repeat for specified generations
    """

    def __init__(self,
                 population_size: int = 50,
                 generations: int = 100,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.7,
                 elitism_count: int = 5):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_count = elitism_count

        self.population: List[StrategyGenome] = []
        self.generation_history = []
        self.best_genome: Optional[StrategyGenome] = None

        # Parameter search space
        self.parameter_space = self._initialize_parameter_space()

        logger.info(f"GeneticAlgorithmOptimizer initialized: "
                   f"pop_size={population_size}, generations={generations}")

    def _initialize_parameter_space(self) -> Dict[str, Dict[str, Any]]:
        """Initialize parameter search space for strategy optimization."""

        return {
            # Moving average parameters
            'fast_ma_period': {'type': 'int', 'min': 5, 'max': 50},
            'slow_ma_period': {'type': 'int', 'min': 20, 'max': 200},

            # RSI parameters
            'rsi_period': {'type': 'int', 'min': 10, 'max': 30},
            'rsi_overbought': {'type': 'int', 'min': 65, 'max': 80},
            'rsi_oversold': {'type': 'int', 'min': 20, 'max': 35},

            # Volatility parameters
            'volatility_window': {'type': 'int', 'min': 10, 'max': 50},
            'volatility_threshold': {'type': 'float', 'min': 0.5, 'max': 3.0},

            # Bollinger Band parameters
            'bb_period': {'type': 'int', 'min': 10, 'max': 30},
            'bb_std': {'type': 'float', 'min': 1.0, 'max': 3.0},

            # Position sizing
            'position_size': {'type': 'float', 'min': 0.01, 'max': 0.10},
            'max_position_heat': {'type': 'float', 'min': 0.10, 'max': 0.30},

            # Risk management
            'stop_loss_atr': {'type': 'float', 'min': 0.5, 'max': 3.0},
            'take_profit_atr': {'type': 'float', 'min': 1.0, 'max': 5.0},

            # ML model parameters
            'ml_n_estimators': {'type': 'int', 'min': 50, 'max': 300},
            'ml_max_depth': {'type': 'int', 'min': 3, 'max': 15},
            'ml_learning_rate': {'type': 'float', 'min': 0.01, 'max': 0.3},
        }

    def generate_random_genome(self, generation: int = 0) -> StrategyGenome:
        """Generate a random strategy genome."""

        parameters = {}
        for param_name, param_space in self.parameter_space.items():
            if param_space['type'] == 'int':
                parameters[param_name] = random.randint(param_space['min'], param_space['max'])
            elif param_space['type'] == 'float':
                parameters[param_name] = random.uniform(param_space['min'], param_space['max'])

        genome_id = f"gen{generation}_{random.randint(1000, 9999)}"

        return StrategyGenome(
            genome_id=genome_id,
            parameters=parameters,
            fitness_score=0.0,
            profit_usdt=0.0,
            max_drawdown_pct=100.0,
            sharpe_ratio=-999.0,
            win_rate=0.0,
            generation=generation
        )

    async def evaluate_genome_fitness(
        self,
        genome: StrategyGenome,
        data: pd.DataFrame,
        symbol: str = "SOLUSDT"
    ) -> StrategyGenome:
        """
        Evaluate the fitness of a strategy genome.

        Fitness function = USDT Profit - Drawdown Penalty
        """

        params = genome.parameters

        # Generate signals based on parameters
        signals = self._generate_signals_from_params(data, params)

        if signals is None or len(signals) == 0:
            # Invalid parameters
            genome.fitness_score = -999999.0
            return genome

        # Simulate trading
        performance = self._simulate_trading(data, signals, params)

        # Calculate fitness (multi-objective)
        # Primary: Maximize profit
        # Secondary: Minimize drawdown
        # Tertiary: Maximize Sharpe

        profit = performance['total_profit']
        drawdown = performance['max_drawdown']
        sharpe = performance['sharpe']
        win_rate = performance['win_rate']

        # Fitness score (weighted multi-objective)
        fitness = profit * 1.0  # Profit is primary
        fitness -= drawdown * 10000.0  # Penalize drawdown heavily
        fitness += sharpe * 100.0  # Bonus for Sharpe

        # Hard constraint: max drawdown 25%
        if drawdown > 0.25:
            fitness -= 100000.0  # Severe penalty

        genome.profit_usdt = profit
        genome.max_drawdown_pct = drawdown
        genome.sharpe_ratio = sharpe
        genome.win_rate = win_rate
        genome.fitness_score = fitness

        return genome

    def _generate_signals_from_params(
        self,
        data: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Optional[pd.Series]:
        """Generate trading signals from parameters."""

        try:
            # Calculate indicators based on parameters
            fast_ma = data['close'].rolling(params['fast_ma_period']).mean()
            slow_ma = data['close'].rolling(params['slow_ma_period']).mean()

            rsi = self._calculate_rsi(data['close'], params['rsi_period'])

            bb_middle = data['close'].rolling(params['bb_period']).mean()
            bb_std = data['close'].rolling(params['bb_period']).std()
            bb_upper = bb_middle + params['bb_std'] * bb_std
            bb_lower = bb_middle - params['bb_std'] * bb_std

            # Generate signals
            signals = pd.Series(0, index=data.index)

            # Trend following signal
            trend_signal = np.where(fast_ma > slow_ma, 1, -1)

            # RSI signal
            rsi_signal = np.where(rsi > params['rsi_overbought'], -1,
                                 np.where(rsi < params['rsi_oversold'], 1, 0))

            # Bollinger Band signal
            bb_signal = np.where(data['close'] < bb_lower, 1,
                                np.where(data['close'] > bb_upper, -1, 0))

            # Combine signals
            signals = pd.Series(trend_signal, index=data.index)

            # Only take signals when confirmed by multiple indicators
            confirmed = (rsi_signal == trend_signal) | (bb_signal == trend_signal)
            signals = signals * confirmed

            return signals.dropna()

        except Exception as e:
            logger.warning(f"Failed to generate signals: {e}")
            return None

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _simulate_trading(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
        params: Dict[str, Any]
    ) -> Dict[str, float]:
        """Simulate trading with given signals."""

        capital = 10000.0
        position = 0.0
        trades = []

        for i in range(len(signals)):
            if i == 0:
                continue

            signal = signals.iloc[i]
            price = data['close'].iloc[i]

            if signal != 0 and position == 0:
                # Enter position
                position_size = capital * params['position_size']
                position = position_size / price
                entry_price = price

            elif signal == 0 and position != 0:
                # Exit position
                exit_price = price
                pnl = (exit_price - entry_price) / entry_price * position

                # Apply costs
                pnl -= 0.0005  # Taker fee

                capital += pnl
                trades.append(pnl)
                position = 0.0

            # Check stop loss / take profit
            if position != 0:
                atr = self._calculate_atr(data, i, params.get('stop_loss_atr', 2.0))
                if price < entry_price - atr:
                    # Stop loss hit
                    exit_price = price
                    pnl = (exit_price - entry_price) / entry_price * position - 0.0005
                    capital += pnl
                    trades.append(pnl)
                    position = 0.0

        # Calculate metrics
        total_profit = capital - 10000.0

        if trades:
            # Drawdown
            cumulative = np.cumsum(trades)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = np.min(cumulative - running_max)
            max_drawdown = abs(drawdown) / 10000.0

            # Sharpe
            sharpe = np.mean(trades) / np.std(trades) * np.sqrt(252) if np.std(trades) > 0 else 0

            # Win rate
            win_rate = np.sum([t > 0 for t in trades]) / len(trades)
        else:
            max_drawdown = 0.0
            sharpe = 0.0
            win_rate = 0.0

        return {
            'total_profit': total_profit,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe,
            'win_rate': win_rate
        }

    def _calculate_atr(self, data: pd.DataFrame, idx: int, multiplier: float = 2.0) -> float:
        """Calculate ATR-based stop loss."""
        if idx < 14:
            return data['close'].iloc[idx] * 0.02  # Default 2%

        high_low = data['high'].iloc[idx-14:idx] - data['low'].iloc[idx-14:idx]
        tr = high_low.max()
        return tr * multiplier

    def tournament_selection(self, tournament_size: int = 3) -> StrategyGenome:
        """Select parent using tournament selection."""

        tournament = random.sample(self.population, min(tournament_size, len(self.population)))
        return max(tournament, key=lambda g: g.fitness_score)

    def crossover(self, parent1: StrategyGenome, parent2: StrategyGenome, generation: int) -> StrategyGenome:
        """Create offspring through crossover."""

        child_params = {}

        for param_name in self.parameter_space.keys():
            # Uniform crossover
            if random.random() < 0.5:
                child_params[param_name] = parent1.parameters[param_name]
            else:
                child_params[param_name] = parent2.parameters[param_name]

        child_id = f"gen{generation}_{random.randint(1000, 9999)}"

        return StrategyGenome(
            genome_id=child_id,
            parameters=child_params,
            fitness_score=0.0,
            profit_usdt=0.0,
            max_drawdown_pct=100.0,
            sharpe_ratio=-999.0,
            win_rate=0.0,
            generation=generation,
            parent_ids=[parent1.genome_id, parent2.genome_id]
        )

    def mutate(self, genome: StrategyGenome) -> StrategyGenome:
        """Mutate a genome's parameters."""

        for param_name, param_space in self.parameter_space.items():
            if random.random() < self.mutation_rate:
                # Apply mutation
                if param_space['type'] == 'int':
                    current = genome.parameters[param_name]
                    mutation = random.randint(-5, 5)
                    genome.parameters[param_name] = np.clip(
                        current + mutation,
                        param_space['min'],
                        param_space['max']
                    )
                elif param_space['type'] == 'float':
                    current = genome.parameters[param_name]
                    mutation = random.gauss(0, 0.1)
                    genome.parameters[param_name] = np.clip(
                        current + mutation,
                        param_space['min'],
                        param_space['max']
                    )

        return genome

    async def optimize(
        self,
        data: pd.DataFrame,
        symbol: str = "SOLUSDT"
    ) -> List[StrategyGenome]:
        """
        Run genetic algorithm optimization.

        Returns the best strategies found.
        """

        logger.info(f"Starting genetic optimization for {symbol}")
        logger.info(f"Population: {self.population_size}, Generations: {self.generations}")

        # Initialize population
        logger.info("Initializing population...")
        for i in range(self.population_size):
            genome = self.generate_random_genome(generation=0)
            genome = await self.evaluate_genome_fitness(genome, data, symbol)
            self.population.append(genome)

        # Sort by fitness
        self.population.sort(key=lambda g: g.fitness_score, reverse=True)
        self.best_genome = self.population[0]

        logger.info(f"Generation 0 - Best Fitness: {self.best_genome.fitness_score:.2f}, "
                   f"Profit: ${self.best_genome.profit_usdt:.2f}")

        # Evolve
        for gen in range(1, self.generations):
            new_population = []

            # Elitism: keep best performers
            new_population.extend(self.population[:self.elitism_count])

            # Create offspring
            while len(new_population) < self.population_size:
                # Selection
                parent1 = self.tournament_selection()
                parent2 = self.tournament_selection()

                # Crossover
                if random.random() < self.crossover_rate:
                    child = self.crossover(parent1, parent2, gen)
                else:
                    child = self.generate_random_genome(gen)

                # Mutation
                child = self.mutate(child)

                # Evaluate
                child = await self.evaluate_genome_fitness(child, data, symbol)

                new_population.append(child)

            # Replace population
            self.population = sorted(new_population, key=lambda g: g.fitness_score, reverse=True)

            # Update best
            if self.population[0].fitness_score > self.best_genome.fitness_score:
                self.best_genome = self.population[0]

            # Log progress
            if gen % 10 == 0:
                logger.info(f"Generation {gen} - Best Fitness: {self.best_genome.fitness_score:.2f}, "
                           f"Profit: ${self.best_genome.profit_usdt:.2f}, "
                           f"Drawdown: {self.best_genome.max_drawdown_pct:.2%}")

            # Store generation history
            self.generation_history.append({
                'generation': gen,
                'best_fitness': self.population[0].fitness_score,
                'avg_fitness': np.mean([g.fitness_score for g in self.population]),
                'best_profit': self.population[0].profit_usdt,
                'best_drawdown': self.population[0].max_drawdown_pct
            })

        logger.info("Genetic optimization complete!")
        logger.info(f"Best Strategy Found:")
        logger.info(f"  Profit: ${self.best_genome.profit_usdt:.2f}")
        logger.info(f"  Drawdown: {self.best_genome.max_drawdown_pct:.2%}")
        logger.info(f"  Sharpe: {self.best_genome.sharpe_ratio:.2f}")
        logger.info(f"  Win Rate: {self.best_genome.win_rate:.2%}")

        return self.population[:10]  # Return top 10


# Singleton instance
_genetic_optimizer = None


def get_genetic_optimizer() -> GeneticAlgorithmOptimizer:
    """Get or create genetic optimizer instance."""
    global _genetic_optimizer
    if _genetic_optimizer is None:
        _genetic_optimizer = GeneticAlgorithmOptimizer()
    return _genetic_optimizer
