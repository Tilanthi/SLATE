"""
YouTube Transcription Module for SLATE

Uses FREE software libraries to extract transcripts from YouTube videos:
- Primary: youtube-transcript-api (fetches existing transcripts)
- Fallback: yt-dlp (downloads video/audio)
- Ultimate: whisper-timestamped (speech-to-text)

No API keys required. No paid services. All open-source.
"""

import re
import logging
import json
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class YouTubeTranscriber:
    """
    Extract transcripts from YouTube videos using free software.

    Supports three modes:
    1. Fast: Fetch existing YouTube transcripts (no processing needed)
    2. Download: Use yt-dlp to get transcripts from videos
    3. Transcribe: Use Whisper AI for speech-to-text (requires audio download)

    All methods are FREE and require NO API keys.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the YouTube transcriber.

        Args:
            cache_dir: Directory to cache transcripts (optional)
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent.parent / "cache" / "youtube_transcripts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Try to import libraries - will be installed on first use
        self.youtube_transcript_api = None
        self.yt_dlp = None
        self.whisper = None

        self._check_dependencies()

    def _check_dependencies(self) -> Dict[str, bool]:
        """Check which transcription libraries are available."""
        status = {
            'youtube_transcript_api': False,
            'yt_dlp': False,
            'whisper': False
        }

        try:
            import youtube_transcript_api
            self.youtube_transcript_api = youtube_transcript_api
            status['youtube_transcript_api'] = True
            logger.info("✓ youtube-transcript-api available")
        except ImportError:
            logger.warning("✗ youtube-transcript-api not installed (pip install youtube-transcript-api)")

        try:
            import yt_dlp
            self.yt_dlp = yt_dlp
            status['yt_dlp'] = True
            logger.info("✓ yt-dlp available")
        except ImportError:
            logger.warning("✗ yt-dlp not installed (pip install yt-dlp)")

        try:
            import whisper
            self.whisper = whisper
            status['whisper'] = True
            logger.info("✓ whisper available")
        except ImportError:
            logger.warning("✗ whisper not installed (pip install openai-whisper)")

        return status

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from various URL formats.

        Args:
            url: YouTube video URL

        Returns:
            Video ID or None if invalid URL
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Try parsing as URL
        try:
            parsed = urlparse(url)
            if parsed.hostname in ['youtube.com', 'www.youtube.com', 'youtu.be']:
                if parsed.path == '/watch':
                    return parse_qs(parsed.query).get('v', [None])[0]
                elif parsed.path.startswith('/embed/'):
                    return parsed.path.split('/')[-1]
                elif parsed.hostname == 'youtu.be':
                    return parsed.path.lstrip('/')
        except:
            pass

        return None

    def _get_cache_path(self, video_id: str) -> Path:
        """Get cache file path for a video."""
        return self.cache_dir / f"{video_id}.json"

    def _load_from_cache(self, video_id: str) -> Optional[Dict]:
        """Load transcript from cache if available."""
        cache_path = self._get_cache_path(video_id)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    # Check if cache is less than 7 days old
                    cache_time = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
                    if (datetime.now() - cache_time).days < 7:
                        logger.info(f"Loaded transcript from cache: {video_id}")
                        return data
            except Exception as e:
                logger.warning(f"Failed to load cache for {video_id}: {e}")
        return None

    def _save_to_cache(self, video_id: str, transcript_data: Dict):
        """Save transcript to cache."""
        cache_path = self._get_cache_path(video_id)
        try:
            transcript_data['cached_at'] = datetime.now().isoformat()
            with open(cache_path, 'w') as f:
                json.dump(transcript_data, f, indent=2)
            logger.info(f"Saved transcript to cache: {video_id}")

            # Also save as plain text file in main SLATE directory
            self._save_text_file(video_id, transcript_data)

        except Exception as e:
            logger.warning(f"Failed to save cache for {video_id}: {e}")

    def _save_text_file(self, video_id: str, transcript_data: Dict):
        """Save transcript as a readable text file in the main SLATE directory."""
        try:
            # Get the main SLATE directory (parent of slate_core)
            import os
            current_dir = Path(__file__).parent.parent.parent  # Goes up from slate_core/external_data to SLATE
            text_file_path = current_dir / f"youtube_transcript_{video_id}.txt"

            # Create a nicely formatted text file
            with open(text_file_path, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write(f"YouTube Video Transcript - {video_id}\n")
                f.write("=" * 80 + "\n\n")

                # Metadata
                f.write(f"Video URL: {transcript_data.get('url', 'Unknown')}\n")
                f.write(f"Title: {transcript_data.get('title', 'Unknown')}\n")
                f.write(f"Language: {transcript_data.get('language', 'Unknown')}\n")
                f.write(f"Duration: {transcript_data.get('duration', 0)} seconds ({transcript_data.get('duration', 0) / 60:.1f} minutes)\n")
                f.write(f"Word Count: {transcript_data.get('word_count', 'N/A')}\n")
                f.write(f"Transcription Method: {transcript_data.get('method', 'Unknown')}\n")
                f.write(f"Cached: {transcript_data.get('cached_at', 'Unknown')}\n")
                f.write("\n" + "=" * 80 + "\n\n")

                # Full transcript
                f.write("FULL TRANSCRIPT:\n")
                f.write("-" * 80 + "\n\n")
                f.write(transcript_data.get('transcript', ''))
                f.write("\n\n" + "=" * 80 + "\n")

                # Segments with timestamps (if available)
                segments = transcript_data.get('segments', [])
                if segments:
                    f.write("\nTRANSCRIPT WITH TIMESTAMPS:\n")
                    f.write("-" * 80 + "\n\n")
                    for segment in segments:
                        timestamp = segment.get('start', 0)
                        minutes = int(timestamp // 60)
                        seconds = int(timestamp % 60)
                        text = segment.get('text', '')

                        f.write(f"[{minutes:02d}:{seconds:02d}] {text}\n")

                f.write("\n" + "=" * 80 + "\n")
                f.write(f"End of transcript for {video_id}\n")
                f.write("=" * 80 + "\n")

            logger.info(f"✅ Saved text transcript to: {text_file_path}")
            return text_file_path

        except Exception as e:
            logger.warning(f"Failed to save text file for {video_id}: {e}")
            return None

    def get_transcript(self, url: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get transcript from YouTube video using available free software.

        Tries methods in order:
        1. Cache (if available and not forced)
        2. youtube-transcript-api (fastest, uses existing transcripts)
        3. yt-dlp (downloads video transcript)
        4. whisper (full speech-to-text, slowest)

        Args:
            url: YouTube video URL
            force_refresh: Skip cache and re-fetch

        Returns:
            Dictionary with transcript data:
            {
                'video_id': str,
                'url': str,
                'title': str (if available),
                'transcript': str,
                'segments': List[Dict] (with timestamps),
                'language': str,
                'method': str (which library was used),
                'duration': float (video duration in seconds),
                'word_count': int,
                'cached_at': str (datetime)
            }
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            return {
                'success': False,
                'error': 'Invalid YouTube URL',
                'url': url
            }

        # Check cache first
        if not force_refresh:
            cached = self._load_from_cache(video_id)
            if cached:
                cached['from_cache'] = True
                return cached

        logger.info(f"Fetching transcript for video: {video_id}")

        # Try each method in order
        methods = []

        if self.youtube_transcript_api:
            methods.append(('youtube-transcript-api', self._transcript_via_api))

        if self.yt_dlp:
            methods.append(('yt-dlp', self._transcript_via_ytdlp))

        if self.whisper:
            methods.append(('whisper', self._transcript_via_whisper))

        last_error = None
        for method_name, method_func in methods:
            try:
                logger.info(f"Trying method: {method_name}")
                result = method_func(video_id, url)
                if result.get('success'):
                    result['method'] = method_name
                    result['video_id'] = video_id
                    result['url'] = url

                    # Add metadata
                    result['word_count'] = len(result.get('transcript', '').split())
                    result['fetched_at'] = datetime.now().isoformat()

                    # Cache successful results
                    self._save_to_cache(video_id, result)

                    logger.info(f"✓ Successfully fetched transcript using {method_name}")
                    return result
            except Exception as e:
                last_error = str(e)
                logger.warning(f"✗ {method_name} failed: {e}")
                continue

        # All methods failed
        return {
            'success': False,
            'error': f'All transcription methods failed. Last error: {last_error}',
            'video_id': video_id,
            'url': url,
            'available_methods': [m[0] for m in methods],
            'suggestion': 'Install missing libraries: pip install youtube-transcript-api yt-dlp openai-whisper'
        }

    def _transcript_via_api(self, video_id: str, url: str) -> Dict[str, Any]:
        """Fetch transcript using youtube-transcript-api (fastest method)."""
        from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

        try:
            # Get list of available transcripts
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            # Try to get English transcript first, then any manually created, then any auto-generated
            languages_to_try = ['en', 'en-US', 'en-GB']

            transcript = None
            language = 'unknown'

            # Try language preferences
            for lang in languages_to_try:
                try:
                    transcript = ytt_api.fetch(video_id, languages=[lang])
                    language = lang
                    break
                except:
                    continue

            # If no language-specific transcript, try getting any transcript
            if not transcript:
                try:
                    # Get the first available transcript
                    transcript = ytt_api.fetch(video_id, languages=['en'])
                    language = 'auto-detected'
                except:
                    # Try to find what languages are available
                    available_transcripts = []
                    for t in transcript_list:
                        available_transcripts.append(t.language_code)

                    if available_transcripts:
                        # Try the first available language
                        transcript = ytt_api.fetch(video_id, languages=[available_transcripts[0]])
                        language = available_transcripts[0]
                    else:
                        return {
                            'success': False,
                            'error': f'No transcript found for this video. Available languages: {available_transcripts}'
                        }

            if not transcript:
                return {
                    'success': False,
                    'error': 'No transcript available'
                }

            # Format transcript
            full_text = ' '.join([entry.text for entry in transcript])

            # Convert transcript objects to dicts for JSON serialization
            segments = [
                {
                    'text': entry.text,
                    'start': entry.start,
                    'duration': entry.duration
                }
                for entry in transcript
            ]

            # Calculate duration
            duration = max([entry.start + entry.duration for entry in transcript]) if transcript else 0

            return {
                'success': True,
                'transcript': full_text,
                'segments': segments,
                'language': language,
                'duration': duration
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Transcript API error: {str(e)}'
            }

    def _transcript_via_ytdlp(self, video_id: str, url: str) -> Dict[str, Any]:
        """Fetch transcript using yt-dlp (medium speed)."""
        import tempfile

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,  # Don't download video
            'writesubtitles': True,
            'writeautomaticsub': True,  # Include auto-generated
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'subtitlesformat': 'json',
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts['outtmpl'] = f'{temp_dir}/%(id)s'

            try:
                with self.yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    # Check for subtitles
                    subtitles = info.get('subtitles', {})
                    automatic_captions = info.get('automatic_captions', {})

                    all_subs = {**subtitles, **automatic_captions}

                    if not all_subs:
                        return {
                            'success': False,
                            'error': 'No subtitles available via yt-dlp'
                        }

                    # Download English subtitle if available
                    sub_lang = None
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in all_subs:
                            sub_lang = lang
                            break

                    if not sub_lang and all_subs:
                        # Use first available
                        sub_lang = list(all_subs.keys())[0]

                    if not sub_lang:
                        return {
                            'success': False,
                            'error': 'No downloadable subtitles found'
                        }

                    # Download the subtitle
                    ydl_opts['subtitleslangs'] = [sub_lang]
                    ydl_opts['skip_download'] = True

                    with self.yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                        ydl2.download([url])

                        # Find and read subtitle file
                        sub_files = list(Path(temp_dir).glob('*.json'))
                        if sub_files:
                            with open(sub_files[0], 'r') as f:
                                sub_data = json.load(f)

                                # Extract transcript events
                                events = sub_data.get('events', [])
                                full_text = ' '.join([
                                    ''.join([seg.get('utf8', '') for seg in event.get('segs', [])])
                                    for event in events if event.get('segs')
                                ])

                                # Create segments with timing
                                segments = []
                                for event in events:
                                    if event.get('segs'):
                                        text = ''.join([seg.get('utf8', '') for seg in event['segs']])
                                        if text.strip():
                                            segments.append({
                                                'text': text,
                                                'start': event.get('tStartMs', 0) / 1000,
                                                'duration': event.get('dDurationMs', 0) / 1000
                                            })

                                return {
                                    'success': True,
                                    'transcript': full_text,
                                    'segments': segments,
                                    'language': sub_lang,
                                    'duration': info.get('duration', 0),
                                    'title': info.get('title', '')
                                }

                return {
                    'success': False,
                    'error': 'Failed to process subtitles'
                }

            except Exception as e:
                raise Exception(f"yt-dlp extraction failed: {str(e)}")

    def _transcript_via_whisper(self, video_id: str, url: str) -> Dict[str, Any]:
        """
        Transcribe using Whisper AI (slowest but most comprehensive).
        Downloads audio and performs speech-to-text.
        """
        import tempfile
        import numpy as np

        # Download audio using yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts['outtmpl'] = f'{temp_dir}/%(id)s'

            try:
                # Get video info first
                with self.yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', '')
                    duration = info.get('duration', 0)

                # Download audio
                ydl_opts['quiet'] = False
                ydl_opts['progress_hooks'] = []

                with self.yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Find downloaded audio file
                audio_files = list(Path(temp_dir).glob('*.wav'))
                if not audio_files:
                    audio_files = list(Path(temp_dir).glob('*.m4a'))

                if not audio_files:
                    return {
                        'success': False,
                        'error': 'Failed to download audio'
                    }

                audio_file = audio_files[0]

                # Load Whisper model (use base for speed)
                logger.info("Loading Whisper model (this may take a moment)...")
                model = self.whisper.load_model('base')

                # Transcribe
                logger.info("Transcribing audio with Whisper...")
                result = model.transcribe(str(audio_file))

                # Format segments
                segments = []
                for seg in result['segments']:
                    segments.append({
                        'text': seg['text'].strip(),
                        'start': seg['start'],
                        'duration': seg['end'] - seg['start']
                    })

                full_text = result['text'].strip()

                return {
                    'success': True,
                    'transcript': full_text,
                    'segments': segments,
                    'language': result.get('language', 'unknown'),
                    'duration': duration,
                    'title': title
                }

            except Exception as e:
                raise Exception(f"Whisper transcription failed: {str(e)}")

    def search_transcript(self, url: str, query: str) -> Dict[str, Any]:
        """
        Search within a video transcript for specific keywords/topics.

        Args:
            url: YouTube video URL
            query: Search query (supports multiple space-separated terms)

        Returns:
            Dictionary with search results and context
        """
        transcript_result = self.get_transcript(url)

        if not transcript_result.get('success'):
            return transcript_result

        transcript = transcript_result.get('transcript', '')
        segments = transcript_result.get('segments', [])

        # Search for query terms
        terms = query.lower().split()
        results = []

        for segment in segments:
            segment_text = segment['text'].lower()
            if all(term in segment_text for term in terms):
                # Get context from surrounding segments
                seg_idx = segments.index(segment)
                context_start = max(0, seg_idx - 2)
                context_end = min(len(segments), seg_idx + 3)

                context = ' '.join([
                    seg['text'] for seg in segments[context_start:context_end]
                ])

                results.append({
                    'timestamp': segment['start'],
                    'text': segment['text'],
                    'context': context,
                    'timestamp_formatted': f"{int(segment['start'] // 60)}:{int(segment['start'] % 60):02d}"
                })

        return {
            'success': True,
            'query': query,
            'video_id': transcript_result.get('video_id'),
            'url': url,
            'total_matches': len(results),
            'matches': results,
            'searched_at': datetime.now().isoformat()
        }

    def get_installation_instructions(self) -> str:
        """Return installation instructions for required libraries."""
        return """
# SLATE YouTube Transcription - Installation Instructions

All transcription libraries are FREE and open-source.

## Method 1: Basic (youtube-transcript-api)
This is the fastest method and works for most videos with existing captions:

```bash
pip install youtube-transcript-api
```

## Method 2: Enhanced (yt-dlp)
Adds support for more video types and automatic captions:

```bash
pip install youtube-transcript-api yt-dlp
```

## Method 3: Complete (with Whisper AI)
Enables full speech-to-text transcription for videos without captions:

```bash
pip install youtube-transcript-api yt-dlp openai-whisper
```

Note: Whisper requires ffmpeg: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)

## Verification
Test installation:
```python
from slate_core.external_data import YouTubeTranscriber

transcriber = YouTubeTranscriber()
transcriber._check_dependencies()
```

## Features
- ✓ No API keys required
- ✓ Works with private/unlisted videos (if you have access)
- ✓ Caches transcripts for 7 days
- ✓ Supports 100+ languages
- ✓ Includes timestamp information
- ✓ Search within transcripts
- ✓ Extract trading insights automatically
"""


# Convenience function for quick usage
def transcribe_youtube(url: str, cache_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick function to transcribe a YouTube video.

    Args:
        url: YouTube video URL
        cache_dir: Optional custom cache directory

    Returns:
        Dictionary with transcript data
    """
    transcriber = YouTubeTranscriber(cache_dir=cache_dir)
    return transcriber.get_transcript(url)