#!/usr/bin/env python3
"""
SLATE Block Bootstrap Engine

Generates alternative realistic price paths from real order book data
using block bootstrap methodology.
"""

import numpy as np
import random
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BootstrapPath:
    """A single bootstrapped price path."""
    path_id: str
    blocks: List[int]  # Block indices used
    prices: List[float]  # Mid prices
    spreads: List[float]  # Bid-ask spreads
    volumes: List[float]  # Simulated volumes
    timestamps: List[str]

    def __len__(self):
        return len(self.prices)


class BlockBootstrapEngine:
    """
    Generate alternative price paths using block bootstrap.

    Method:
    1. Divide real order book data into blocks (preserves microstructure)
    2. Randomly shuffle blocks to create new paths
    3. Each path made entirely of real data blocks
    4. Preserves realistic market dynamics
    """

    def __init__(self, block_size: int = 1000, cache_dir: str = "./palace_data/bootstrap"):
        self.block_size = block_size
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Storage for paths
        self.generated_paths = []

    def create_blocks_from_orderbooks(self, orderbook_snapshots: List[Dict]) -> List[Dict]:
        """Convert order book snapshots into blocks."""
        blocks = []

        for i in range(0, len(orderbook_snapshots), self.block_size):
            block_end = min(i + self.block_size, len(orderbook_snapshots))
            block_data = orderbook_snapshots[i:block_end]

            # Calculate block statistics
            mid_prices = []
            spreads = []
            volumes = []

            for snapshot in block_data:
                # Calculate mid price
                if snapshot.get('bid') and snapshot.get('ask'):
                    mid = (snapshot['bid'] + snapshot['ask']) / 2
                    mid_prices.append(mid)

                    # Spread
                    spread = ((snapshot['ask'] - snapshot['bid']) / mid) * 10000
                    spreads.append(spread)

                # Simulate volume (random but realistic)
                volume = np.random.lognormal(10, 1)  # Lognormal volume
                volumes.append(volume)

            if mid_prices:
                blocks.append({
                    'block_id': i // self.block_size,
                    'start_idx': i,
                    'end_idx': block_end,
                    'mid_prices': mid_prices,
                    'spreads': spreads,
                    'volumes': volumes,
                    'volatility': np.std(mid_prices) / np.mean(mid_prices) if mid_prices else 0,
                    'trend': (mid_prices[-1] - mid_prices[0]) / mid_prices[0] if mid_prices else 0
                })

        logger.info(f"Created {len(blocks)} blocks from {len(orderbook_snapshots)} snapshots")
        return blocks

    def generate_alternative_path(self, blocks: List[Dict],
                                   path_id: Optional[str] = None) -> BootstrapPath:
        """Generate one alternative price path by shuffling blocks."""
        if not blocks:
            raise ValueError("No blocks available")

        # Randomly select blocks with replacement
        num_blocks = max(50, len(blocks) // 2)  # Use 50+ blocks for sufficient length
        selected_blocks = []

        # Block-based shuffling (preserves microstructure)
        for _ in range(num_blocks):
            block_idx = random.randint(0, len(blocks) - 1)
            selected_blocks.append(blocks[block_idx])

        # Flatten blocks into path
        prices = []
        spreads = []
        volumes = []
        timestamps = []

        current_time = datetime.now()
        time_delta = 60  # 1 minute between blocks

        for i, block in enumerate(selected_blocks):
            # Add block data
            prices.extend(block['mid_prices'])
            spreads.extend(block['spreads'])
            volumes.extend(block['volumes'])

            # Add synthetic timestamps
            block_time = current_time + timedelta(seconds=i * time_delta * len(block['mid_prices']))
            for j in range(len(block['mid_prices'])):
                timestamps.append((block_time + timedelta(seconds=j)).isoformat())

        # Add small random transitions between blocks (realistic gap trading)
        for i in range(len(selected_blocks) - 1):
            gap_idx = len(prices) - 1  # End of current block

            # Small price jump (gap trading)
            gap_change = np.random.normal(0, 0.0002)  # 2bps standard deviation
            prices[gap_idx] *= (1 + gap_change)

        path_id = path_id or f"path_{datetime.now().timestamp()}"

        return BootstrapPath(
            path_id=path_id,
            blocks=[b['block_id'] for b in selected_blocks],
            prices=prices,
            spreads=spreads,
            volumes=volumes,
            timestamps=timestamps
        )

    def generate_multiple_paths(self, blocks: List[Dict],
                                num_paths: int = 100) -> List[BootstrapPath]:
        """Generate multiple alternative paths."""
        paths = []

        for i in range(num_paths):
            path = self.generate_alternative_path(blocks, f"path_{i}")
            paths.append(path)

            if (i + 1) % 10 == 0:
                logger.info(f"Generated {i + 1}/{num_paths} paths")

        return paths

    def calculate_path_statistics(self, path: BootstrapPath) -> Dict:
        """Calculate statistics for a bootstrapped path."""
        prices = np.array(path.prices)
        returns = np.diff(prices) / prices[:-1]

        # Filter out infinite and NaN values
        returns = returns[np.isfinite(returns)]

        if len(returns) == 0:
            return {
                'volatility': 0,
                'trend': 0,
                'autocorrelation': 0,
                'fat_tail_ratio': 0
            }

        # Volatility
        volatility = np.std(returns)

        # Trend
        trend = (prices[-1] - prices[0]) / prices[0]

        # Autocorrelation (market microstructure effect)
        if len(returns) > 20:
            autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1] if returns.size > 1 else 0
        else:
            autocorr = 0

        # Fat tail ratio (kurtosis)
        if len(returns) > 10:
            fat_tail_ratio = np.mean(returns**4) / (np.std(returns)**4) if volatility > 0 else 0
        else:
            fat_tail_ratio = 0

        return {
            'volatility': volatility,
            'trend': trend,
            'autocorrelation': autocorr,
            'fat_tail_ratio': fat_tail_ratio,
            'num_ticks': len(prices)
        }

    def validate_realism(self, path: BootstrapPath,
                        original_stats: Dict) -> Dict[str, bool]:
        """Validate that bootstrapped path maintains realistic properties."""
        path_stats = self.calculate_path_statistics(path)

        # Check realism criteria
        checks = {
            'has_volatility': 0.0001 < path_stats['volatility'] < 0.01,  # Realistic volatility range
            'reasonable_trend': abs(path_stats['trend']) < 0.5,  # Less than 50% trend
            'autocorrelation_present': path_stats['autocorrelation'] > 0.01,  # Some microstructure effect
            'not_degenerate': path_stats['num_ticks'] > 100
        }

        return checks

    def save_path(self, path: BootstrapPath):
        """Save a bootstrapped path to cache."""
        path_dir = self.cache_dir / "paths"
        path_dir.mkdir(parents=True, exist_ok=True)

        filepath = path_dir / f"{path.path_id}.json"

        data = {
            'path_id': path.path_id,
            'blocks': path.blocks,
            'prices': path.prices,
            'spreads': path.spreads,
            'volumes': path.volumes,
            'timestamps': path.timestamps,
            'statistics': self.calculate_path_statistics(path)
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved path {path.path_id} to {filepath}")

    def load_path(self, path_id: str) -> Optional[BootstrapPath]:
        """Load a bootstrapped path from cache."""
        path_dir = self.cache_dir / "paths"
        filepath = path_dir / f"{path_id}.json"

        if not filepath.exists():
            return None

        with open(filepath, 'r') as f:
            data = json.load(f)

        return BootstrapPath(
            path_id=data['path_id'],
            blocks=data['blocks'],
            prices=data['prices'],
            spreads=data['spreads'],
            volumes=data['volumes'],
            timestamps=data['timestamps']
        )


class BootstrapOHLCVGenerator:
    """Generate OHLCV candles from bootstrapped paths for backtesting."""

    def __init__(self, candle_seconds: int = 60):
        """Initialize OHLCV generator.

        Args:
            candle_seconds: Length of each candle in seconds
        """
        self.candle_seconds = candle_seconds

    def generate_ohlcv(self, path: BootstrapPath) -> List[Dict]:
        """Convert bootstrapped path to OHLCV candles."""
        candles = []
        ticks_per_candle = self.candle_seconds  # Assuming 1-second data

        for i in range(0, len(path.prices), ticks_per_candle):
            candle_start = i
            candle_end = min(i + ticks_per_candle, len(path.prices))

            if candle_end >= len(path.prices):
                break

            # Extract candle data
            candle_prices = path.prices[candle_start:candle_end]

            if not candle_prices:
                continue

            ohlcv = {
                'timestamp': path.timestamps[candle_start],
                'open': candle_prices[0],
                'high': max(candle_prices),
                'low': min(candle_prices),
                'close': candle_prices[-1],
                'volume': sum(path.volumes[candle_start:candle_end]) if path.volumes else 0
            }

            candles.append(ohlcv)

        return candles


class BootstrapValidator:
    """Validate that bootstrapped paths maintain realistic market properties."""

    def __init__(self):
        self.real_market_properties = {
            'volatility_range': (0.0001, 0.01),  # Realistic tick volatility
            'spread_range': (1, 50),  # Spread in basis points
            'autocorr_range': (0.01, 0.5),  # Tick autocorrelation
            'fat_tail_min': 3.0,  # Minimum kurtosis
        }

    def validate_path(self, path: BootstrapPath) -> Tuple[bool, List[str]]:
        """Validate a bootstrapped path against realistic criteria."""
        issues = []

        # Calculate statistics
        stats = self._calculate_statistics(path)

        # Check volatility
        if not (self.real_market_properties['volatility_range'][0] < stats['volatility'] <
                self.real_market_properties['volatility_range'][1]):
            issues.append(f"Unrealistic volatility: {stats['volatility']:.6f}")

        # Check spreads
        avg_spread = np.mean(path.spreads) if path.spreads else 0
        if not (self.real_market_properties['spread_range'][0] <= avg_spread <=
                self.real_market_properties['spread_range'][1]):
            issues.append(f"Unrealistic spread: {avg_spread:.2f} bps")

        # Check autocorrelation
        if not (self.real_market_properties['autocorr_range'][0] <= abs(stats['autocorr']) <=
                self.real_market_properties['autocorr_range'][1]):
            issues.append(f"Unrealistic autocorrelation: {stats['autocorr']:.3f}")

        # Check for degenerate paths
        if len(path.prices) < 100:
            issues.append(f"Path too short: {len(path.prices)} ticks")

        is_valid = len(issues) == 0
        return is_valid, issues

    def _calculate_statistics(self, path: BootstrapPath) -> Dict:
        """Calculate path statistics."""
        prices = np.array(path.prices)
        returns = np.diff(prices) / prices[:-1]

        # Filter invalid returns
        returns = returns[np.isfinite(returns)]

        stats = {
            'volatility': np.std(returns) if len(returns) > 0 else 0,
            'autocorr': np.corrcoef(returns[:-1], returns[1:])[0, 1] if len(returns) > 2 else 0,
            'fat_tail': np.mean(returns**4) / (np.std(returns)**4) if len(returns) > 0 and np.std(returns) > 0 else 0,
            'trend': (prices[-1] - prices[0]) / prices[0] if len(prices) > 0 and prices[0] > 0 else 0
        }

        return stats


def create_sample_blocks_from_candles(candles: List[Dict],
                                         block_size: int = 100) -> List[Dict]:
    """Create bootstrap blocks from candle data (for backward compatibility)."""
    blocks = []

    for i in range(0, len(candles), block_size):
        block_end = min(i + block_size, len(candles))
        block_candles = candles[i:block_end]

        if not block_candles:
            continue

        # Extract block data
        mid_prices = [c['close'] for c in block_candles]
        spreads = [2.0] * len(mid_prices)  # Default spread
        volumes = [c.get('volume', 1000) for c in block_candles]

        blocks.append({
            'block_id': i // block_size,
            'start_idx': i,
            'end_idx': block_end,
            'mid_prices': mid_prices,
            'spreads': spreads,
            'volumes': volumes,
            'volatility': np.std(mid_prices) / np.mean(mid_prices) if mid_prices else 0,
            'trend': (mid_prices[-1] - mid_prices[0]) / mid_prices[0] if mid_prices else 0
        })

    return blocks


# Global instance
_bootstrap_engine = None


def get_bootstrap_engine() -> BlockBootstrapEngine:
    """Get the global bootstrap engine instance."""
    global _bootstrap_engine
    if _bootstrap_engine is None:
        _bootstrap_engine = BlockBootstrapEngine()
    return _bootstrap_engine
