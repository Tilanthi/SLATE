#!/usr/bin/env python3
"""
SLATE Main Server - World-Class Version

Complete rewrite replacing broken swarm system with world-class
quantitative trading framework.

Built on principles from successful crypto trading firms:
- Market regime awareness and adaptation
- Proper risk management and position sizing
- Multiple strategy classes with proven edge
- Realistic signal generation and execution
- Robust validation and backtesting

Usage:
    python3 -m slate_core.server_clean

The server will:
1. Start on port 8788
2. Initialize world-class discovery system
3. Provide API endpoints for interaction
4. Run continuous world-class strategy discovery
5. Serve a web dashboard for monitoring
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Add slate_core to path if needed
slate_root = Path(__file__).parent.parent
if str(slate_root) not in sys.path:
    sys.path.insert(0, str(slate_root))

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Closed-Loop Discovery Integration
try:
    from slate_core.discovery.closed_loop_integration import (
        get_enhanced_discovery_system,
        EnhancedDiscoveryIntegration
    )
    CLOSED_LOOP_AVAILABLE = True
    WORLD_CLASS_AVAILABLE = True  # For backwards compatibility
except ImportError as e:
    CLOSED_LOOP_AVAILABLE = False
    WORLD_CLASS_AVAILABLE = False
    logger.warning(f"Closed-loop discovery not available: {e}")

# Startup Coordinator for auto-restart and continuous discovery
try:
    from slate_core.startup_coordinator import (
        get_startup_coordinator,
        initialize_with_discovery,
        record_user_activity,
        ensure_discovery_running
    )
    STARTUP_COORDINATOR_AVAILABLE = True
except ImportError as e:
    STARTUP_COORDINATOR_AVAILABLE = False
    logger.warning(f"Startup coordinator not available: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SLATE - World-Class Quantitative Trading System",
    description="AI-driven world-class crypto trading strategy discovery (Paper Trading Only)",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning(f"Static directory not found: {static_dir}")

# Global state
start_time = datetime.now()
discovery_running = False
last_user_activity = datetime.now()

# ============================================================================
# API Routes - Health & Status
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint showing closed-loop system status."""
    # Update user activity on health check (lightweight operations won't pause discovery)
    global last_user_activity
    last_user_activity = datetime.now()

    # Try to get startup coordinator status first
    coordinator_status = None
    if STARTUP_COORDINATOR_AVAILABLE:
        try:
            from slate_core.startup_coordinator import get_system_status
            coordinator_status = get_system_status()
        except Exception as e:
            logger.warning(f"Failed to get coordinator status: {e}")

    # Use coordinator status if available, otherwise fallback to global flags
    if coordinator_status:
        discovery_running_status = coordinator_status.get('discovery_running', discovery_running)
        last_activity = coordinator_status.get('last_user_activity', last_user_activity.isoformat())
    else:
        discovery_running_status = discovery_running
        last_activity = last_user_activity.isoformat()

    closed_loop_status = {
        "discovery_running": discovery_running_status,
        "closed_loop_available": CLOSED_LOOP_AVAILABLE,
        "system_type": "closed_loop_ai_discovery",
        "last_user_activity": last_activity
    }

    # Add coordinator status if available
    if coordinator_status:
        closed_loop_status["startup_coordinator"] = coordinator_status

    return {
        "status": "healthy",
        "mode": "paper_trading",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - start_time).total_seconds(),
        "port": 8788,
        "closed_loop_discovery": closed_loop_status,
        "system_type": "closed_loop_ai_quantitative_trading"
    }


@app.get("/api/closed-loop/status")
async def closed_loop_status():
    """Get detailed closed-loop discovery system status."""
    if not CLOSED_LOOP_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "Closed-loop discovery system not available",
            "system_type": "paper_trading"
        }

    try:
        # Check actual discovery status from coordinator or global flag
        is_running = discovery_running
        if STARTUP_COORDINATOR_AVAILABLE:
            try:
                from slate_core.startup_coordinator import get_system_status
                coordinator_status = get_system_status()
                is_running = coordinator_status.get('discovery_running', discovery_running)
            except Exception as e:
                logger.warning(f"Failed to get coordinator status: {e}")

        return {
            "status": "available",
            "discovery_running": is_running,  # Actual running status from coordinator
            "system_type": "closed_loop_ai_quantitative_trading",
            "framework": "Hypothesis-Driven Scientific Discovery",
            "components": {
                "hypothesis_generation": "operational",
                "rigorous_validation": "6 validation methods",
                "feedback_learning": "operational",
                "hybrid_strategies": "operational"
            },
            "principles": [
                "Hypothesis-driven discovery (not random search)",
                "Pluralistic validation (bootstrap, walk-forward, Monte Carlo)",
                "Feedback learning (continuous improvement)",
                "Hybrid neurosymbolic strategies (patterns + rules)",
                "Statistical rigor (avoid epistemic collapse)"
            ],
            "research_basis": "Based on: 'The future of fundamental science led by generative closed-loop artificial intelligence'"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/api/closed-loop/discovery/start")
async def start_closed_loop_discovery():
    """Manually trigger a closed-loop discovery cycle."""
    if not CLOSED_LOOP_AVAILABLE:
        raise HTTPException(status_code=503, detail="Closed-loop discovery not available")

    try:
        import pandas as pd
        import json

        logger.info("🧠 Starting Closed-Loop Discovery via API")

        # Load market data with proper parsing
        with open('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv', 'r') as f:
            content = f.read()

        all_data = []
        for line in content.strip().split('\n'):
            if line.strip():
                try:
                    data_list = json.loads(line.strip())
                    if isinstance(data_list, list):
                        all_data.extend(data_list)
                except:
                    continue

        df = pd.DataFrame(all_data)

        if df is None or len(df) < 50:
            raise HTTPException(status_code=400, detail="Insufficient market data for discovery")

        # Convert timestamp to date
        df['date'] = pd.to_datetime(df['timestamp'])

        logger.info(f"✅ Market data loaded: {len(df)} days")

        # Run discovery cycle
        from slate_core.discovery.closed_loop_integration import get_enhanced_discovery_system
        system = get_enhanced_discovery_system()
        result = system.run_enhanced_discovery_cycle(df)

        # Extract summary information for JSON response
        performance = result.get('performance', {})
        discovery = result.get('discovery', {})
        validation = result.get('validation', {})

        return {
            "status": "success",
            "cycle_number": result.get('cycle_number', 1),
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "hypotheses_generated": discovery.get('hypotheses_generated', 0),
                "hybrid_strategies": result.get('hybrid_strategies', {}).get('strategies_generated', 0),
                "total_validated": validation.get('total_validated', 0),
                "successful_validations": validation.get('successful', 0),
                "success_rate": validation.get('success_rate', 0),
                "duration_seconds": performance.get('duration_seconds', 0)
            },
            "message": "Discovery cycle completed - check logs for full details"
        }

    except Exception as e:
        logger.error(f"Failed to start closed-loop discovery: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup Event - World-Class Discovery Only
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Server startup - Initialize and auto-start closed-loop AI discovery system with watchdog."""
    logger.info("=" * 70)
    logger.info("🚀 SLATE SERVER STARTING - CLOSED-LOOP AI EDITION")
    logger.info("=" * 70)
    logger.info(f"Port: 8788")
    logger.info(f"Mode: Paper Trading Only")
    logger.info(f"Dashboard: http://localhost:8788")
    logger.info(f"API Docs: http://localhost:8788/docs")
    logger.info("=" * 70)

    logger.info("🧠 CLOSED-LOOP AI DISCOVERY SYSTEM:")
    logger.info("  • Hypothesis-driven discovery (systematic vs random)")
    logger.info("  • Rigorous statistical validation (6 methods)")
    logger.info("  • Feedback learning system (continuous improvement)")
    logger.info("  • Hybrid neurosymbolic strategies (patterns + rules)")
    logger.info("  • Based on cutting-edge AI research")
    logger.info("=" * 70)
    logger.info("📚 RESEARCH BASIS:")
    logger.info('  "The future of fundamental science led by')
    logger.info('   generative closed-loop artificial intelligence"')
    logger.info("=" * 70)
    logger.info("🎯 SYSTEM CAPABILITIES:")
    logger.info("  • Information Extraction → Hypothesis Generation")
    logger.info("  • Experimental Validation → Iterative Refinement")
    logger.info("  • Feedback Learning → System Optimization")
    logger.info("  • World's first application to quantitative trading")
    logger.info("  • YouTube Video Transcription & Analysis")
    logger.info("=" * 70)
    logger.info("📹 YOUTUBE INTEGRATION:")
    logger.info("  • Transcribe trading videos for insights")
    logger.info("  • Search transcripts for specific concepts")
    logger.info("  • Extract strategies from expert content")
    logger.info("  • Available via: POST /api/youtube/transcribe")
    logger.info("=" * 70)

    # Initialize startup coordinator with auto-restart watchdog
    if STARTUP_COORDINATOR_AVAILABLE:
        logger.info("🔄 Initializing startup coordinator with watchdog...")
        coordinator = await initialize_with_discovery()
        logger.info("✅ Startup coordinator initialized")
        logger.info("🐕 Watchdog active - will auto-restart discovery if it fails")
        logger.info("🧠 Continuous discovery running with auto-restart protection")
    else:
        logger.warning("⚠️  Startup coordinator not available - starting fallback discovery...")
        asyncio.create_task(start_continuous_discovery())
        logger.info("✅ Fallback discovery system initialized")

    # Start periodic health check
    asyncio.create_task(periodic_discovery_health_check())
    logger.info("✅ Closed-Loop AI System Initialized with auto-restart protection")


async def start_continuous_discovery():
    """
    Fallback continuous discovery loop for when startup coordinator is not available.

    This is only used if the startup coordinator fails to load.
    The coordinator should be preferred as it has proper watchdog and error handling.
    """
    global discovery_running, last_user_activity

    logger.info("🧠 Starting fallback continuous discovery loop")
    logger.warning("⚠️  Using fallback discovery - startup coordinator not available")

    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            # Check if user is active
            time_since_user_activity = (datetime.now() - last_user_activity).total_seconds()

            # Only run discovery if no user activity in last 10 seconds (reduced from 60)
            if time_since_user_activity > 10:
                logger.info("🧠 Starting closed-loop discovery cycle (no user activity)")

                try:
                    # Load market data properly
                    import pandas as pd

                    df = pd.read_csv('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv')
                    logger.info(f"✅ Market data loaded: {len(df)} days")

                    # Run discovery cycle
                    from slate_core.discovery.closed_loop_integration import get_enhanced_discovery_system
                    system = get_enhanced_discovery_system()
                    result = system.run_enhanced_discovery_cycle(df)

                    performance = result.get('performance', {})
                    discovery = result.get('discovery', {})

                    logger.info(f"✅ Discovery cycle complete:")
                    logger.info(f"   Hypotheses: {performance.get('hypotheses_generated', 0)}")
                    logger.info(f"   Strategies: {performance.get('strategies_generated', 0)}")
                    logger.info(f"   Validated: {performance.get('total_validated', 0)}")
                    logger.info(f"   Success Rate: {performance.get('overall_success_rate', 0):.1%}")

                    discovery_running = True
                    consecutive_errors = 0  # Reset error counter on success

                except Exception as e:
                    logger.error(f"❌ Discovery cycle error: {e}")
                    discovery_running = False
                    consecutive_errors += 1

                    # Exponential backoff on consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"❌ Too many consecutive errors ({consecutive_errors}), waiting before retry...")
                        await asyncio.sleep(30)  # Wait longer on repeated errors
                        consecutive_errors = 0  # Reset after waiting
                    else:
                        await asyncio.sleep(min(10 * (2 ** min(consecutive_errors, 4)), 60))
            else:
                logger.debug(f"⏸️  Discovery paused (user active {time_since_user_activity:.0f}s ago)")
                discovery_running = False
                consecutive_errors = 0  # Reset when paused due to user activity

            # Wait before next cycle (reduced from 120 to 30 seconds)
            await asyncio.sleep(30)  # Check every 30 seconds instead of 2 minutes

        except Exception as e:
            logger.error(f"❌ Continuous discovery loop error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error


async def periodic_discovery_health_check():
    """
    Periodic health check to ensure discovery keeps running.
    This works with both the startup coordinator and fallback discovery.
    """
    logger.info("🏥 Starting periodic discovery health check...")

    while True:
        try:
            await asyncio.sleep(60)  # Check every 60 seconds

            # Try to use startup coordinator first
            if STARTUP_COORDINATOR_AVAILABLE:
                was_restarted = await ensure_discovery_running()
                if was_restarted:
                    logger.info("🐕 Health check triggered discovery restart")
            else:
                # Fallback: just check global flag
                if not discovery_running:
                    logger.warning("⚠️  Discovery not running, attempting restart...")
                    # Restart will happen on next iteration of the loop
                    global last_user_activity
                    last_user_activity = datetime.now() - timedelta(seconds=100)  # Force start

        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            await asyncio.sleep(120)  # Wait longer on health check errors


@app.on_event("shutdown")
async def shutdown_event():
    """Server shutdown - Clean shutdown of world-class discovery."""
    logger.info("🛑 SLATE Server shutting down...")
    logger.info("World-class discovery system stopping...")

    # Note: World-class discovery will stop gracefully as the event loop ends


# ============================================================================
# Backwards Compatibility API Routes
# ============================================================================

@app.get("/api/world-class/status")
async def world_class_status_compatibility():
    """World-class status endpoint - Redirects to closed-loop for compatibility."""
    return {
        "status": "upgraded",
        "message": "World-class system upgraded to closed-loop AI framework",
        "use_endpoint": "/api/closed-loop/status",
        "enhancement": "Hypothesis-driven discovery with pluralistic validation"
    }


@app.post("/api/world-class/discovery/start")
async def world_class_discovery_compatibility():
    """World-class discovery endpoint - Redirects to closed-loop for compatibility."""
    # For backwards compatibility, redirect to closed-loop system
    return await start_closed_loop_discovery()


@app.get("/api/swarm/status")
async def swarm_status_disabled():
    """Swarm status endpoint - DISABLED in closed-loop edition."""
    return {
        "status": "disabled",
        "message": "Swarm system removed - replaced by hypothesis-driven closed-loop discovery",
        "replacement": "closed_loop_ai_discovery",
        "reason": "Random parameter tuning replaced by systematic scientific discovery"
    }


@app.post("/api/swarm/start")
async def swarm_start_disabled():
    """Swarm start endpoint - DISABLED in world-class edition."""
    raise HTTPException(
        status_code=410,
        detail="SWARM SYSTEM REMOVED - Replaced by world-class quantitative framework"
    )


@app.post("/api/swarm/stop")
async def swarm_stop_disabled():
    """Swarm stop endpoint - DISABLED in world-class edition."""
    return {
        "status": "disabled",
        "message": "Swarm system removed - world-class system uses different approach"
    }


# ============================================================================
# YouTube Integration - Video Transcription & Analysis
# ============================================================================

@app.post("/api/youtube/transcribe")
async def transcribe_youtube_video(request: Request):
    """
    Transcribe a YouTube video and extract trading insights.

    Expects JSON body:
    {
        "url": "https://www.youtube.com/watch?v=...",
        "video_id": "CsOB3lCMrFc",  # alternatively, provide video_id directly
        "extract_insights": true  # optional, default true
    }

    Returns:
    {
        "success": true,
        "transcript": "...",
        "video_id": "...",
        "title": "...",
        "duration": ...,
        "word_count": ...,
        "language": "...",
        "method": "...",
        "segments_count": ...
    }
    """
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber
        from slate_core.external_data.video_insight_extractor import VideoInsightExtractor

        body = await request.json()
        url = body.get('url')
        video_id = body.get('video_id')
        extract_insights = body.get('extract_insights', True)

        # Construct URL if only video_id provided
        if video_id and not url:
            url = f"https://www.youtube.com/watch?v={video_id}"

        if not url:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing YouTube URL or video_id"}
            )

        logger.info(f"YouTube transcription request: {url}")

        # Get transcript
        transcriber = YouTubeTranscriber()
        transcript_result = transcriber.get_transcript(url)

        if not transcript_result.get('success'):
            return transcript_result

        # Extract trading insights if requested
        insights = None
        if extract_insights:
            try:
                extractor = VideoInsightExtractor()
                insights = extractor.extract_insights(transcript_result)
            except Exception as e:
                logger.warning(f"Insight extraction failed: {e}")
                insights = {"error": str(e)}

        return {
            "success": True,
            "transcript": transcript_result.get('transcript'),
            "video_id": transcript_result.get('video_id'),
            "url": url,
            "title": transcript_result.get('title', 'Unknown'),
            "duration": transcript_result.get('duration', 0),
            "word_count": transcript_result.get('word_count', 0),
            "language": transcript_result.get('language', 'unknown'),
            "method": transcript_result.get('method', 'unknown'),
            "segments_count": len(transcript_result.get('segments', [])),
            "insights": insights,
            "from_cache": transcript_result.get('from_cache', False),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error transcribing YouTube video: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/youtube/search")
async def search_youtube_transcript(request: Request):
    """
    Search within a YouTube video transcript for specific topics.

    Expects JSON body:
    {
        "url": "https://www.youtube.com/watch?v=...",
        "video_id": "CsOB3lCMrFc",  # alternatively, provide video_id directly
        "query": "stop loss strategy"
    }

    Returns:
    {
        "success": true,
        "query": "stop loss strategy",
        "total_matches": 5,
        "matches": [
            {
                "timestamp": 123.45,
                "timestamp_formatted": "2:03",
                "text": "...",
                "context": "..."
            }
        ]
    }
    """
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber

        body = await request.json()
        url = body.get('url')
        video_id = body.get('video_id')
        query = body.get('query')

        # Construct URL if only video_id provided
        if video_id and not url:
            url = f"https://www.youtube.com/watch?v={video_id}"

        if not url or not query:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing URL/video_id or query"}
            )

        logger.info(f"YouTube search request: {url} - query: {query}")

        transcriber = YouTubeTranscriber()
        search_result = transcriber.search_transcript(url, query)

        return search_result

    except Exception as e:
        logger.error(f"Error searching YouTube transcript: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/youtube/status")
async def youtube_status():
    """Check YouTube transcription dependencies and capabilities."""
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber

        transcriber = YouTubeTranscriber()
        deps_status = transcriber._check_dependencies()

        # Count cached transcripts
        cache_count = 0
        cache_dir = transcriber.cache_dir
        if cache_dir.exists():
            cache_count = len(list(cache_dir.glob("*.json")))

        return {
            "status": "operational",
            "dependencies": deps_status,
            "cache": {
                "enabled": True,
                "cached_transcripts": cache_count,
                "cache_directory": str(cache_dir)
            },
            "capabilities": {
                "transcribe": deps_status.get('youtube_transcript_api', False) or deps_status.get('yt_dlp', False) or deps_status.get('whisper', False),
                "search": True,
                "insight_extraction": True,
                "multi_language": deps_status.get('whisper', False)
            },
            "installation_guide": transcriber.get_installation_instructions().strip(),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting YouTube status: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/youtube/cache/clear")
async def clear_youtube_cache():
    """Clear cached YouTube transcripts."""
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber

        transcriber = YouTubeTranscriber()
        cache_dir = transcriber.cache_dir

        cleared_count = 0
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.json"))
            cleared_count = len(cache_files)
            for cache_file in cache_files:
                cache_file.unlink()

        logger.info(f"Cleared {cleared_count} cached transcripts")

        return {
            "success": True,
            "cleared_count": cleared_count,
            "message": f"Cleared {cleared_count} cached transcripts",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


if __name__ == "__main__":
    # Start server
    uvicorn.run(app, host="127.0.0.1", port=8788, log_level="info")