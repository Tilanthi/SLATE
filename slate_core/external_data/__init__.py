"""
External Data Processing Module for SLATE

This module handles ingestion and processing of external data sources
that may contain trading-relevant information, such as:
- YouTube video transcripts
- Financial news videos
- Educational content about trading strategies
- Market analysis videos

All capabilities are designed to help SLATE discover genuine market edges
from real-world trading content and analysis.
"""

from .youtube_transcriber import YouTubeTranscriber
from .video_insight_extractor import VideoInsightExtractor

__all__ = ['YouTubeTranscriber', 'VideoInsightExtractor']
