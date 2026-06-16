#!/usr/bin/env python3
"""
SLATE YouTube Transcription CLI

Command-line interface for transcribing YouTube videos and extracting trading insights.

Usage:
    # Transcribe a video
    python youtube_cli.py transcribe "https://www.youtube.com/watch?v=..."

    # Search within a transcript
    python youtube_cli.py search "https://www.youtube.com/watch?v=..." "stop loss strategy"

    # Check system status
    python youtube_cli.py status

    # Clear transcript cache
    python youtube_cli.py clear-cache
"""

import sys
import json
import argparse
from pathlib import Path

# Add slate_core to path
slate_root = Path(__file__).parent
if str(slate_root) not in sys.path:
    sys.path.insert(0, str(slate_root))

from slate_core.external_data.youtube_transcriber import YouTubeTranscriber
from slate_core.external_data.video_insight_extractor import VideoInsightExtractor


def print_json(data):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def print_transcript_summary(result):
    """Print a human-readable summary of transcription results."""
    if not result.get('success'):
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        return

    print("=" * 70)
    print(f"📹 YouTube Video Transcribed Successfully")
    print("=" * 70)
    print(f"🔗 URL: {result.get('url', 'Unknown')}")
    print(f"🆔 Video ID: {result.get('video_id', 'Unknown')}")
    print(f"📝 Title: {result.get('title', 'Unknown')}")
    print(f"⏱️  Duration: {result.get('duration', 0):.0f} seconds")
    print(f"📏 Word Count: {result.get('word_count', 0)}")
    print(f"🌍 Language: {result.get('language', 'unknown')}")
    print(f"🔧 Method: {result.get('method', 'unknown')}")
    print(f"📊 Segments: {result.get('segments_count', 0)}")
    print()

    # Print insights if available
    insights = result.get('insights')
    if insights:
        print("🔍 Trading Insights:")
        print("-" * 70)

        if insights.get('strategies_found'):
            print(f"📈 Strategies: {', '.join(insights['strategies_found'])}")

        if insights.get('indicators_found'):
            print(f"📊 Indicators: {', '.join(insights['indicators_found'])}")

        if insights.get('assets_mentioned'):
            print(f"💰 Assets: {', '.join(insights['assets_mentioned'])}")

        if insights.get('risk_management_topics'):
            print(f"⚠️  Risk Management: {', '.join(insights['risk_management_topics'])}")

        print()
        print(f"🎯 Trading Relevance: {insights.get('trading_relevance_score', 0):.1f}%")
        print(f"📊 Complexity: {insights.get('complexity_score', 0)}/5")
        print(f"💭 Sentiment: {insights.get('sentiment', 'unknown')}")

        if insights.get('summary'):
            print(f"\n📋 Summary: {insights['summary']}")

        if insights.get('slate_action_items'):
            print(f"\n⚡ SLATE Action Items:")
            for i, action in enumerate(insights['slate_action_items'], 1):
                print(f"   {i}. {action}")

        if insights.get('key_quotes'):
            print(f"\n💬 Key Quotes (Top {len(insights['key_quotes'])}):")
            for i, quote in enumerate(insights['key_quotes'][:5], 1):
                timestamp = quote.get('timestamp_formatted', 'Unknown')
                text = quote.get('text', '')
                print(f"   [{i}] @ {timestamp}")
                print(f"       \"{text[:100]}...\"")

    print()
    print("=" * 70)
    print(f"📄 Full Transcript Preview (first 500 characters):")
    print("-" * 70)
    transcript = result.get('transcript', '')
    print(f"{transcript[:500]}...")
    print()
    print("=" * 70)
    print(f"💾 Cached for 7 days. Call again to load from cache.")


def cmd_transcribe(url, extract_insights=True, output_json=False):
    """Transcribe a YouTube video."""
    print(f"🎥 Transcribing YouTube video: {url}")
    print()

    transcriber = YouTubeTranscriber()
    result = transcriber.get_transcript(url)

    if not result.get('success'):
        print_json(result)
        return 1

    # Extract insights if requested
    if extract_insights:
        extractor = VideoInsightExtractor()
        insights = extractor.extract_insights(result)
        result['insights'] = insights

    if output_json:
        print_json(result)
    else:
        print_transcript_summary(result)

    return 0


def cmd_search(url, query, output_json=False):
    """Search within a transcript."""
    print(f"🔍 Searching transcript for: {query}")
    print(f"🎥 Video: {url}")
    print()

    transcriber = YouTubeTranscriber()
    result = transcriber.search_transcript(url, query)

    if not result.get('success'):
        print_json(result)
        return 1

    if output_json:
        print_json(result)
    else:
        print(f"✅ Found {result.get('total_matches', 0)} matches")
        print()
        for i, match in enumerate(result.get('results', []), 1):
            timestamp = match.get('timestamp_formatted', 'Unknown')
            text = match.get('text', '')
            context = match.get('context', '')
            print(f"[{i}] @ {timestamp}")
            print(f"    Text: {text}")
            print(f"    Context: {context}")
            print()

    return 0


def cmd_status(output_json=False):
    """Check YouTube transcription status."""
    transcriber = YouTubeTranscriber()
    deps_status = transcriber._check_dependencies()

    if output_json:
        print_json({
            'dependencies': deps_status,
            'cache_dir': str(transcriber.cache_dir),
            'cache_files': len(list(transcriber.cache_dir.glob("*.json"))) if transcriber.cache_dir.exists() else 0
        })
    else:
        print("🔧 YouTube Transcription Status")
        print("=" * 50)
        print()

        print("📦 Dependencies:")
        for dep, status in deps_status.items():
            icon = "✅" if status else "❌"
            print(f"   {icon} {dep}")

        print()
        print(f"💾 Cache Directory: {transcriber.cache_dir}")
        if transcriber.cache_dir.exists():
            cache_files = list(transcriber.cache_dir.glob("*.json"))
            print(f"   Cached transcripts: {len(cache_files)}")
        else:
            print("   Cache directory does not exist")

        print()
        print(transcriber.get_installation_instructions())

    return 0


def cmd_clear_cache():
    """Clear transcript cache."""
    transcriber = YouTubeTranscriber()

    if transcriber.cache_dir.exists():
        cache_files = list(transcriber.cache_dir.glob("*.json"))
        for file in cache_files:
            file.unlink()

        print(f"✅ Cleared {len(cache_files)} cached transcripts")
    else:
        print("No cache directory found")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SLATE YouTube Transcription CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transcribe a video with insights
  python youtube_cli.py transcribe "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

  # Get JSON output for programmatic use
  python youtube_cli.py transcribe "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json

  # Search transcript for specific topic
  python youtube_cli.py search "https://www.youtube.com/watch?v=dQw4w9WgXcQ" "trading strategy"

  # Check system status
  python youtube_cli.py status

  # Clear cache
  python youtube_cli.py clear-cache
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Transcribe command
    transcribe_parser = subparsers.add_parser('transcribe', help='Transcribe a YouTube video')
    transcribe_parser.add_argument('url', help='YouTube video URL')
    transcribe_parser.add_argument('--no-insights', action='store_true',
                                   help='Skip insight extraction')
    transcribe_parser.add_argument('--json', action='store_true',
                                   help='Output JSON instead of human-readable')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search within a transcript')
    search_parser.add_argument('url', help='YouTube video URL')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--json', action='store_true',
                              help='Output JSON instead of human-readable')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check system status')
    status_parser.add_argument('--json', action='store_true',
                              help='Output JSON instead of human-readable')

    # Clear cache command
    clear_parser = subparsers.add_parser('clear-cache', help='Clear transcript cache')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == 'transcribe':
            return cmd_transcribe(args.url, not args.no_insights, args.json)
        elif args.command == 'search':
            return cmd_search(args.url, args.query, args.json)
        elif args.command == 'status':
            return cmd_status(args.json)
        elif args.command == 'clear-cache':
            return cmd_clear_cache()
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())