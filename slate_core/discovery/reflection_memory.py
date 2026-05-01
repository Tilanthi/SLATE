#!/usr/bin/env python3
"""
SLATE Reflection Memory - Learning from Past Discoveries

Inspired by TradingAgents' decision memory system, this module provides:
- Markdown-based persistent storage of discovery decisions
- Automatic reflection generation on performance
- Cross-cycle learning from past successes/failures
- Injection of historical lessons into new discovery cycles

Memory is stored at: ~/.slate/memory/discovery_memory.md
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
import re

logger = logging.getLogger(__name__)

# Default memory directory
DEFAULT_MEMORY_DIR = Path.home() / ".slate" / "memory"


@dataclass
class DiscoveryDecision:
    """A single discovery decision record."""
    cycle_id: str
    timestamp: str
    strategy_type: str
    description: str
    outcome: str  # 'success', 'failure', 'mixed'
    profit_usdt: float
    return_pct: float
    beat_market: bool
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    key_factors: List[str]
    reflection: str


class ReflectionMemory:
    """
    Manages persistent memory of discovery decisions with reflection.

    Similar to TradingAgents' trading_memory.md approach, this system:
    - Logs each completed discovery cycle
    - Generates reflections on what worked/didn't work
    - Provides historical context for future cycles
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        """
        Initialize reflection memory system.

        Args:
            memory_dir: Directory for memory storage. Defaults to ~/.slate/memory
        """
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.memory_path = self.memory_dir / "discovery_memory.md"

        # Initialize memory file if it doesn't exist
        if not self.memory_path.exists():
            self._init_memory_file()

        logger.info(f"ReflectionMemory initialized at {self.memory_path}")

    def _init_memory_file(self):
        """Create initial memory file with header."""
        content = f"""# SLATE Discovery Memory

**Auto-generated memory of discovery cycles and reflections**

Generated: {datetime.now().isoformat()}

---

## Memory Structure

Each entry contains:
- **Decision**: Strategy description and parameters
- **Outcome**: Performance metrics (USDT profit, return %, Sharpe)
- **Reflection**: Analysis of what worked/didn't work
- **Lessons**: Key takeaways for future cycles

---

## Discovery Entries

"""
        self.memory_path.write_text(content)

    def log_discovery_cycle(
        self,
        cycle_id: str,
        results: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a completed discovery cycle to memory with reflection.

        Args:
            cycle_id: Unique identifier for the cycle
            results: All tested strategy results
            top_performers: Top performing strategies
            market_conditions: Optional market condition data
        """
        if not results:
            logger.warning("No results to log for cycle {cycle_id}")
            return

        # Generate reflection
        reflection = self._generate_reflection(results, top_performers, market_conditions)

        # Create markdown entry
        entry = self._format_entry(cycle_id, results, top_performers, reflection, market_conditions)

        # Append to memory file
        with open(self.memory_path, 'a') as f:
            f.write(entry + "\n")

        logger.info(f"Logged discovery cycle {cycle_id} to memory")

    def _generate_reflection(
        self,
        results: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        market_conditions: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate reflection on discovery cycle performance.

        Analyzes what worked, what didn't, and key lessons learned.
        """
        if not results:
            return "No results to reflect upon."

        # Calculate statistics
        profitable = [r for r in results if r.get('total_profit_usdt', 0) > 0]
        beat_market = [r for r in results if r.get('beat_market', False)]
        high_sharpe = [r for r in results if r.get('sharpe_ratio', 0) > 1.5]

        total_profit = sum(r.get('total_profit_usdt', 0) for r in results)
        avg_return = sum(r.get('total_return_pct', 0) for r in results) / len(results)

        reflection_parts = [
            "### Performance Summary",
            f"- Total strategies tested: {len(results)}",
            f"- Profitable strategies: {len(profitable)} ({len(profitable)/len(results)*100:.1f}%)",
            f"- Strategies beating buy-and-hold: {len(beat_market)} ({len(beat_market)/len(results)*100:.1f}%)",
            f"- High Sharpe ratio (>1.5) strategies: {len(high_sharpe)}",
            f"- Total profit across all strategies: {total_profit:.2f} USDT",
            f"- Average return: {avg_return:.2f}%",
            ""
        ]

        # Analyze top performers
        if top_performers:
            reflection_parts.extend([
                "### Top Performers Analysis",
                ""
            ])

            for i, performer in enumerate(top_performers[:3], 1):
                profit = performer.get('total_profit_usdt', 0)
                ret = performer.get('total_return_pct', 0)
                sharpe = performer.get('sharpe_ratio', 0)
                win_rate = performer.get('win_rate', 0) * 100

                reflection_parts.extend([
                    f"**#{i}**: {performer.get('description', 'Unknown')}",
                    f"- Profit: {profit:.2f} USDT ({ret:.2f}%)",
                    f"- Sharpe: {sharpe:.2f}, Win Rate: {win_rate:.1f}%",
                    f"- Beat Market: {performer.get('beat_market', False)}",
                    ""
                ])

        # Generate lessons learned
        lessons = self._extract_lessons(results, top_performers)
        if lessons:
            reflection_parts.extend([
                "### Key Lessons Learned",
                ""
            ])
            for lesson in lessons:
                reflection_parts.append(f"- {lesson}")
            reflection_parts.append("")

        # Generate recommendations
        recommendations = self._generate_recommendations(results, top_performers)
        if recommendations:
            reflection_parts.extend([
                "### Recommendations for Next Cycle",
                ""
            ])
            for rec in recommendations:
                reflection_parts.append(f"- {rec}")
            reflection_parts.append("")

        return "\n".join(reflection_parts)

    def _extract_lessons(
        self,
        results: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract key lessons from results."""
        lessons = []

        if not results:
            return lessons

        # Analyze what worked
        if top_performers:
            top_types = set()
            for p in top_performers[:5]:
                desc = p.get('description', '').lower()
                # Extract strategy type from description
                if 'momentum' in desc:
                    top_types.add('momentum')
                elif 'mean reversion' in desc:
                    top_types.add('mean_reversion')
                elif 'volatility' in desc:
                    top_types.add('volatility')
                elif 'breakout' in desc:
                    top_types.add('breakout')

            if top_types:
                lessons.append(f"Strong performance from {', '.join(top_types)} strategies")

        # Analyze profit factors
        high_pf = [r for r in results if r.get('profit_factor', 0) > 2.0]
        if high_pf:
            lessons.append(f"{len(high_pf)} strategies showed strong profit factors (>2.0)")

        # Analyze risk metrics
        low_dd = [r for r in results if r.get('max_drawdown_pct', 100) < 15]
        if low_dd:
            lessons.append(f"{len(low_dd)} strategies maintained low drawdown (<15%)")

        # Market regime insights
        profitable_count = len([r for r in results if r.get('total_profit_usdt', 0) > 0])
        if profitable_count > len(results) * 0.6:
            lessons.append("Bullish market conditions favored most strategies")
        elif profitable_count < len(results) * 0.3:
            lessons.append("Challenging market conditions - few strategies profitable")

        return lessons

    def _generate_recommendations(
        self,
        results: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations for next discovery cycle."""
        recommendations = []

        if not results:
            return recommendations

        # Check if we should focus on specific strategy types
        if top_performers:
            desc = top_performers[0].get('description', '').lower()
            if 'momentum' in desc and top_performers[0].get('total_profit_usdt', 0) > 100:
                recommendations.append("Focus discovery on momentum-based strategies")

            elif 'mean reversion' in desc and top_performers[0].get('total_profit_usdt', 0) > 100:
                recommendations.append("Prioritize mean reversion strategy variations")

        # Check risk management
        high_dd = [r for r in results if r.get('max_drawdown_pct', 0) > 25]
        if len(high_dd) > len(results) * 0.5:
            recommendations.append("Tighten risk parameters - many strategies exceeded drawdown limits")

        # Check market performance
        beat_market_count = len([r for r in results if r.get('beat_market', False)])
        if beat_market_count < len(results) * 0.3:
            recommendations.append("Consider increasing buy-and-hold baseline comparison periods")

        # Check win rates
        low_wr = [r for r in results if r.get('win_rate', 0) < 0.4]
        if len(low_wr) > len(results) * 0.5:
            recommendations.append("Improve entry signal accuracy - low win rates detected")

        return recommendations

    def _format_entry(
        self,
        cycle_id: str,
        results: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        reflection: str,
        market_conditions: Optional[Dict[str, Any]]
    ) -> str:
        """Format discovery cycle as markdown entry."""
        timestamp = datetime.now().isoformat()

        parts = [
            f"## Discovery Cycle: {cycle_id}",
            f"**Time**: {timestamp}",
            ""
        ]

        if market_conditions:
            parts.extend([
                "### Market Conditions",
                f"- Regime: {market_conditions.get('regime', 'Unknown')}",
                f"- Volatility: {market_conditions.get('volatility', 'Unknown')}",
                ""
            ])

        parts.extend([
            "### Results",
            f"- Total strategies tested: {len(results)}",
            f"- Top performer: {top_performers[0].get('description', 'N/A') if top_performers else 'N/A'}",
            ""
        ])

        parts.extend([
            "### Reflection",
            reflection,
            "---"
        ])

        return "\n".join(parts)

    def get_recent_lessons(self, limit: int = 10) -> List[str]:
        """
        Extract recent lessons from memory for context injection.

        Args:
            limit: Maximum number of lessons to return

        Returns:
            List of recent lesson strings
        """
        if not self.memory_path.exists():
            return []

        content = self.memory_path.read_text()

        # Extract lessons using regex
        lesson_pattern = r'-\s+(.+?)(?=\n|$)'
        lessons = re.findall(lesson_pattern, content)

        # Get most recent lessons (they're in reverse chronological order)
        recent_lessons = []
        seen = set()

        for lesson in reversed(lessons):
            lesson = lesson.strip()
            if lesson and lesson not in seen and len(recent_lessons) < limit:
                recent_lessons.append(lesson)
                seen.add(lesson)

        return recent_lessons

    def get_context_for_new_cycle(self) -> str:
        """
        Get contextual information for a new discovery cycle.

        Returns formatted string with recent lessons and patterns.
        """
        lessons = self.get_recent_lessons(limit=5)

        if not lessons:
            return "No prior discovery memory available."

        context = [
            "## Prior Discovery Context",
            "",
            "Recent lessons from past cycles:",
            ""
        ]

        for i, lesson in enumerate(lessons, 1):
            context.append(f"{i}. {lesson}")

        context.extend([
            "",
            "Use these insights to guide the current discovery cycle.",
            "---"
        ])

        return "\n".join(context)

    def clear_memory(self) -> None:
        """Clear all discovery memory (with confirmation)."""
        if self.memory_path.exists():
            self.memory_path.unlink()
            self._init_memory_file()
            logger.info("Discovery memory cleared")


# Global reflection memory instance
_reflection_memory: Optional[ReflectionMemory] = None


def get_reflection_memory() -> ReflectionMemory:
    """Get the global reflection memory instance."""
    global _reflection_memory
    if _reflection_memory is None:
        _reflection_memory = ReflectionMemory()
    return _reflection_memory
