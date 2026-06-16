"""
Video Insight Extractor for SLATE

Processes YouTube video transcripts to extract trading-relevant insights,
strategy ideas, market analysis, and other valuable information for
autonomous trading strategy discovery.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)

class VideoInsightExtractor:
    """
    Extract trading-relevant insights from video transcripts.

    Identifies:
    - Trading strategies mentioned
    - Technical indicators discussed
    - Market analysis and predictions
    - Risk management techniques
    - Asset classes and symbols mentioned
    - Timeframes and strategies
    """

    def __init__(self):
        """Initialize the insight extractor with trading keyword patterns."""
        self.trading_keywords = {
            'strategies': [
                'momentum', 'mean reversion', 'breakout', 'fade', 'scalping',
                'day trading', 'swing trading', 'position trading', 'arbitrage',
                'market making', 'trend following', 'counter trend', 'pairs trading',
                'statistical arbitrage', 'high frequency', 'algorithmic trading',
                'quant trading', 'carry trade', 'grid trading', 'dca'
            ],
            'indicators': [
                'moving average', 'sma', 'ema', 'rsi', 'macd', 'bollinger bands',
                'stochastic', 'atr', 'volume', 'vwap', 'support', 'resistance',
                'fibonacci', 'ichimoku', 'adx', 'cci', 'williams', 'momentum',
                'obv', 'pivot points', 'candlestick', 'doji', 'hammer', 'engulfing'
            ],
            'assets': [
                'bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 'binance coin', 'bnb',
                'cardano', 'ada', 'ripple', 'xrp', 'polkadot', 'dot', 'dogecoin', 'doge',
                'forex', 'eur/usd', 'gbp/usd', 'usd/jpy', 'gold', 'silver', 'oil',
                'sp500', 's&p 500', 'nasdaq', 'dow jones', 'indices', 'stocks'
            ],
            'risk_management': [
                'stop loss', 'take profit', 'position sizing', 'risk management',
                'leverage', 'margin', 'drawdown', 'risk reward', 'portfolio',
                'diversification', 'hedging', ' Kelly criterion', 'risk per trade'
            ],
            'timeframes': [
                '1 minute', '5 minute', '15 minute', '1 hour', '4 hour', 'daily',
                'weekly', 'monthly', 'tick', 'intraday', 'scalp', 'swing'
            ],
            'patterns': [
                'bull flag', 'bear flag', 'double top', 'double bottom', 'head and shoulders',
                'cup and handle', 'triangle', 'wedge', 'pennant', 'rectangle',
                'rising wedge', 'falling wedge', 'ascending triangle', 'descending triangle'
            ]
        }

    def extract_insights(self, transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract trading insights from transcript data.

        Args:
            transcript_data: Transcript data from YouTubeTranscriber

        Returns:
            Dictionary with extracted insights:
            {
                'strategies_found': List[str],
                'indicators_found': List[str],
                'assets_mentioned': List[str],
                'risk_management_topics': List[str],
                'timeframes': List[str],
                'patterns_found': List[str],
                'key_quotes': List[Dict],
                'sentiment': str,
                'complexity_score': int,
                'trading_relevance_score': float
            }
        """
        transcript = transcript_data.get('transcript', '')
        segments = transcript_data.get('segments', [])

        if not transcript:
            return {
                'success': False,
                'error': 'No transcript provided'
            }

        logger.info("Extracting trading insights from transcript...")

        insights = {
            'success': True,
            'video_id': transcript_data.get('video_id'),
            'video_url': transcript_data.get('url'),
            'video_title': transcript_data.get('title', 'Unknown'),
            'analyzed_at': datetime.now().isoformat(),
            'transcript_length': len(transcript),
            'word_count': transcript_data.get('word_count', 0),
            'duration_seconds': transcript_data.get('duration', 0),
        }

        # Extract each category
        insights['strategies_found'] = self._find_keywords(transcript, self.trading_keywords['strategies'])
        insights['indicators_found'] = self._find_keywords(transcript, self.trading_keywords['indicators'])
        insights['assets_mentioned'] = self._find_keywords(transcript, self.trading_keywords['assets'])
        insights['risk_management_topics'] = self._find_keywords(transcript, self.trading_keywords['risk_management'])
        insights['timeframes'] = self._find_keywords(transcript, self.trading_keywords['timeframes'])
        insights['patterns_found'] = self._find_keywords(transcript, self.trading_keywords['patterns'])

        # Extract key quotes (sentences with trading keywords)
        insights['key_quotes'] = self._extract_key_quotes(transcript, segments)

        # Analyze sentiment
        insights['sentiment'] = self._analyze_sentiment(transcript)

        # Calculate relevance and complexity scores
        insights['trading_relevance_score'] = self._calculate_relevance_score(insights)
        insights['complexity_score'] = self._calculate_complexity_score(insights)

        # Generate summary
        insights['summary'] = self._generate_summary(insights)

        # Generate SLATE action items
        insights['slate_action_items'] = self._generate_slate_actions(insights)

        logger.info(f"✓ Extracted {insights['trading_relevance_score']:.1f}% relevant trading insights")

        return insights

    def _find_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Find which keywords from a list are present in the text."""
        text_lower = text.lower()
        found = []

        for keyword in keywords:
            if keyword.lower() in text_lower:
                found.append(keyword)

        return found

    def _extract_key_quotes(self, transcript: str, segments: List[Dict]) -> List[Dict]:
        """Extract meaningful quotes from the transcript."""
        # Split transcript into sentences
        sentences = re.split(r'[.!?]+', transcript)

        key_quotes = []
        all_keywords = []

        # Flatten all keyword lists
        for category_keywords in self.trading_keywords.values():
            all_keywords.extend(category_keywords)

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue

            # Check if sentence contains trading keywords
            sentence_lower = sentence.lower()
            keywords_in_sentence = [kw for kw in all_keywords if kw.lower() in sentence_lower]

            if keywords_in_sentence:
                # Find corresponding segment for timestamp
                timestamp = None
                if segments:
                    # Approximate timestamp based on position in transcript
                    char_position = transcript.find(sentence[:50])
                    if char_position >= 0:
                        # Find which segment this likely belongs to
                        for seg in segments:
                            if seg['text'][:50].lower() in sentence_lower:
                                timestamp = seg['start']
                                break

                key_quotes.append({
                    'text': sentence,
                    'keywords_found': keywords_in_sentence,
                    'timestamp': timestamp,
                    'timestamp_formatted': f"{int(timestamp // 60)}:{int(timestamp % 60):02d}" if timestamp else "Unknown"
                })

        # Return top 10 most relevant quotes
        key_quotes.sort(key=lambda x: len(x['keywords_found']), reverse=True)
        return key_quotes[:10]

    def _analyze_sentiment(self, text: str) -> str:
        """Analyze market sentiment expressed in the transcript."""
        text_lower = text.lower()

        bullish_terms = ['bullish', 'up', 'rise', 'rally', 'breakout', 'moon', 'pump', 'buy', 'long', 'higher', 'gain']
        bearish_terms = ['bearish', 'down', 'fall', 'drop', 'crash', 'dump', 'sell', 'short', 'lower', 'loss']
        neutral_terms = ['sideways', 'range', 'consolidate', 'chop', 'neutral', 'wait', 'hold', 'stable']

        bullish_count = sum(1 for term in bullish_terms if term in text_lower)
        bearish_count = sum(1 for term in bearish_terms if term in text_lower)
        neutral_count = sum(1 for term in neutral_terms if term in text_lower)

        if bullish_count > bearish_count and bullish_count > neutral_count:
            return 'bullish'
        elif bearish_count > bullish_count and bearish_count > neutral_count:
            return 'bearish'
        elif neutral_count > max(bullish_count, bearish_count):
            return 'neutral'
        elif bullish_count == bearish_count:
            return 'balanced'
        else:
            return 'mixed'

    def _calculate_relevance_score(self, insights: Dict) -> float:
        """Calculate how relevant this video is to trading (0-100)."""
        score = 0.0

        # Points for each category found
        if insights['strategies_found']:
            score += 20
        if insights['indicators_found']:
            score += 15
        if insights['assets_mentioned']:
            score += 10
        if insights['risk_management_topics']:
            score += 15
        if insights['patterns_found']:
            score += 10
        if insights['timeframes']:
            score += 5
        if insights['key_quotes']:
            score += 15
        if insights['sentiment'] in ['bullish', 'bearish']:
            score += 10

        return min(100.0, score)

    def _calculate_complexity_score(self, insights: Dict) -> int:
        """Calculate complexity level (1-5) based on content."""
        score = 0

        # More complex topics = higher score
        score += min(3, len(insights['strategies_found']))
        score += min(2, len(insights['indicators_found']))
        score += min(2, len(insights['risk_management_topics']))

        if 'statistical' in ' '.join(insights['strategies_found']).lower():
            score += 2
        if 'machine learning' in ' '.join(insights['strategies_found']).lower():
            score += 2
        if 'algorithmic' in ' '.join(insights['strategies_found']).lower():
            score += 1

        return min(5, max(1, score))

    def _generate_summary(self, insights: Dict) -> str:
        """Generate a human-readable summary of the insights."""
        parts = []

        if insights['strategies_found']:
            parts.append(f"Discusses {len(insights['strategies_found'])} trading strategies")
        if insights['indicators_found']:
            parts.append(f"Mentions {len(insights['indicators_found'])} technical indicators")
        if insights['assets_mentioned']:
            parts.append(f"Covers {len(insights['assets_mentioned'])} assets/markets")
        if insights['risk_management_topics']:
            parts.append(f"Includes {len(insights['risk_management_topics'])} risk management topics")

        if not parts:
            return "General market content with limited specific trading insights."

        return ". ".join(parts) + "."

    def _generate_slate_actions(self, insights: Dict) -> List[str]:
        """Generate suggested actions for SLATE based on insights."""
        actions = []

        # Suggest strategy discovery
        if insights['strategies_found']:
            actions.append(f"Research strategies: {', '.join(insights['strategies_found'][:5])}")

        # Suggest indicator integration
        if insights['indicators_found']:
            actions.append(f"Test indicators: {', '.join(insights['indicators_found'][:5])}")

        # Suggest market research
        if insights['assets_mentioned']:
            actions.append(f"Analyze markets: {', '.join(insights['assets_mentioned'][:3])}")

        # Suggest timeframe testing
        if insights['timeframes']:
            actions.append(f"Backtest timeframes: {', '.join(insights['timeframes'][:3])}")

        # Suggest risk management
        if insights['risk_management_topics']:
            actions.append("Review risk management parameters")

        if not actions:
            actions.append("Low trading relevance - may not require immediate action")

        return actions

    def search_transcript(self, transcript_data: Dict, query: str) -> Dict[str, Any]:
        """
        Search transcript for specific trading concepts.

        Args:
            transcript_data: Transcript data from YouTubeTranscriber
            query: Search query

        Returns:
            Search results with context and timestamps
        """
        transcript = transcript_data.get('transcript', '')
        segments = transcript_data.get('segments', [])

        if not transcript:
            return {'success': False, 'error': 'No transcript available'}

        # Find all occurrences
        results = []
        query_lower = query.lower()

        for segment in segments:
            if query_lower in segment['text'].lower():
                # Get context from nearby segments
                seg_idx = segments.index(segment)
                context_start = max(0, seg_idx - 1)
                context_end = min(len(segments), seg_idx + 2)

                context = ' '.join([
                    seg['text'] for seg in segments[context_start:context_end]
                ])

                results.append({
                    'timestamp': segment['start'],
                    'timestamp_formatted': f"{int(segment['start'] // 60)}:{int(segment['start'] % 60):02d}",
                    'text': segment['text'],
                    'context': context
                })

        return {
            'success': True,
            'query': query,
            'total_matches': len(results),
            'results': results
        }