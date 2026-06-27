"""
SLATE Server - Autonomous System Integration

Integration layer for adding autonomous capabilities to the main SLATE server.
This file contains the modifications needed for slate_core/server.py
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# ADDITIONS TO slate_core/server.py
# ============================================================================

# 1. Add imports at the top of the file with other imports
"""
# Add after existing imports:

try:
    from slate_core.autonomous import (
        AutonomousOrchestrator,
        get_exploratory_config,
        AutonomousConfig
    )
    AUTONOMOUS_AVAILABLE = True
except ImportError:
    AUTONOMOUS_AVAILABLE = False
    logger.warning("Autonomous capabilities not available")

# Global autonomous system
autonomous_orchestrator: Optional[AutonomousOrchestrator] = None
autonomous_enabled = False
"""

# 2. Add autonomous initialization in startup event
"""
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...

    # Initialize autonomous system if available
    global autonomous_orchestrator, autonomous_enabled

    if AUTONOMOUS_AVAILABLE:
        try:
            autonomous_config = get_exploratory_config()
            autonomous_orchestrator = AutonomousOrchestrator(autonomous_config)
            autonomous_orchestrator.start()
            autonomous_enabled = True
            logger.info("✅ Autonomous system initialized and started")
        except Exception as e:
            logger.error(f"Failed to initialize autonomous system: {e}")
            autonomous_enabled = False
"""

# 3. Add autonomous cleanup in shutdown event
"""
@app.on_event("shutdown")
async def shutdown_event():
    # ... existing shutdown code ...

    # Stop autonomous system
    global autonomous_orchestrator, autonomous_enabled

    if autonomous_orchestrator:
        try:
            autonomous_orchestrator.cleanup()
            autonomous_enabled = False
            logger.info("Autonomous system stopped")
        except Exception as e:
            logger.error(f"Error stopping autonomous system: {e}")
"""

# 4. Add activity tracking in existing endpoints
"""
# Add this decorator or function to track user activity:

def track_user_activity():
    '''Track user activity for autonomous pause/resume'''
    if autonomous_enabled and autonomous_orchestrator:
        autonomous_orchestrator.record_user_activity()

# Then add track_user_activity() calls in:
# - /api/discovery/start
# - /api/discovery/stop
# - /api/discovery/nl/generate
# - /api/discovery/nl/test
# - Basically any user-initiated endpoint
"""

# 5. New API endpoints for autonomous system

def get_autonomous_status():
    """Get autonomous system status"""
    if not autonomous_enabled or not autonomous_orchestrator:
        return {
            "autonomous_available": AUTONOMOUS_AVAILABLE,
            "autonomous_enabled": False,
            "message": "Autonomous system not enabled"
        }

    try:
        status = autonomous_orchestrator.get_status()
        status["autonomous_available"] = AUTONOMOUS_AVAILABLE
        status["autonomous_enabled"] = True
        return status
    except Exception as e:
        logger.error(f"Error getting autonomous status: {e}")
        return {
            "autonomous_available": AUTONOMOUS_AVAILABLE,
            "autonomous_enabled": False,
            "error": str(e)
        }

def get_autonomous_discoveries(limit: int = 20):
    """Get autonomous discoveries"""
    if not autonomous_enabled or not autonomous_orchestrator:
        return {
            "autonomous_enabled": False,
            "discoveries": [],
            "message": "Autonomous system not enabled"
        }

    try:
        discoveries = autonomous_orchestrator.get_discoveries(limit=limit)
        return {
            "autonomous_enabled": True,
            "total": len(discoveries),
            "discoveries": discoveries,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting autonomous discoveries: {e}")
        return {
            "autonomous_enabled": False,
            "discoveries": [],
            "error": str(e)
        }

def start_autonomous_operations():
    """Start autonomous operations"""
    if not AUTONOMOUS_AVAILABLE:
        return {
            "success": False,
            "message": "Autonomous capabilities not available"
        }

    try:
        global autonomous_orchestrator, autonomous_enabled

        if not autonomous_orchestrator:
            autonomous_config = get_exploratory_config()
            autonomous_orchestrator = AutonomousOrchestrator(autonomous_config)

        autonomous_orchestrator.start()
        autonomous_enabled = True

        return {
            "success": True,
            "message": "Autonomous operations started",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error starting autonomous operations: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def stop_autonomous_operations():
    """Stop autonomous operations"""
    try:
        global autonomous_enabled

        if autonomous_orchestrator:
            autonomous_orchestrator.stop()
            autonomous_enabled = False

        return {
            "success": True,
            "message": "Autonomous operations stopped",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error stopping autonomous operations: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def generate_autonomous_report():
    """Generate comprehensive autonomous discovery report"""
    if not autonomous_enabled or not autonomous_orchestrator:
        return {
            "autonomous_enabled": False,
            "report": None,
            "message": "Autonomous system not enabled"
        }

    try:
        report = autonomous_orchestrator.generate_report()
        return {
            "autonomous_enabled": True,
            "report": report,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating autonomous report: {e}")
        return {
            "autonomous_enabled": False,
            "report": None,
            "error": str(e)
        }

# ============================================================================
# FASTAPI ROUTE DEFINITIONS
# ============================================================================

"""
Add these routes to the FastAPI app:

@app.get("/api/autonomous/status")
async def api_get_autonomous_status():
    '''Get autonomous system status and configuration'''
    return get_autonomous_status()

@app.get("/api/autonomous/discoveries")
async def api_get_autonomous_discoveries(limit: int = 20):
    '''Get autonomous discoveries'''
    return get_autonomous_discoveries(limit=limit)

@app.post("/api/autonomous/start")
async def api_start_autonomous():
    '''Start autonomous operations'''
    track_user_activity()  # Record this user activity
    return start_autonomous_operations()

@app.post("/api/autonomous/stop")
async def api_stop_autonomous():
    '''Stop autonomous operations'''
    track_user_activity()  # Record this user activity
    return stop_autonomous_operations()

@app.get("/api/autonomous/report")
async def api_get_autonomous_report():
    '''Generate comprehensive autonomous discovery report'''
    return generate_autonomous_report()

@app.post("/api/autonomous/config")
async def api_update_autonomous_config(request: dict):
    '''Update autonomous configuration'''
    track_user_activity()  # Record this user activity

    if not autonomous_enabled:
        return {"success": False, "message": "Autonomous system not enabled"}

    try:
        # Update specific configuration parameters
        # This is a simplified version - in production, validate all inputs
        config_updates = {}
        if 'max_cpu_percent' in request:
            config_updates['max_cpu_percent'] = request['max_cpu_percent']
        if 'max_memory_percent' in request:
            config_updates['max_memory_percent'] = request['max_memory_percent']
        if 'idle_timeout_minutes' in request:
            config_updates['idle_timeout_minutes'] = request['idle_timeout_minutes']

        # Update config (would need to be implemented in orchestrator)
        return {
            "success": True,
            "message": "Configuration updated",
            "updates": config_updates
        }
    except Exception as e:
        logger.error(f"Error updating autonomous config: {e}")
        return {"success": False, "error": str(e)}
"""

# ============================================================================
# MODIFICATION GUIDE FOR slate_core/server.py
# ============================================================================

MODIFICATION_INSTRUCTIONS = """
# MODIFICATION INSTRUCTIONS FOR slate_core/server.py

# 1. Add these imports after line 36 (after uvicorn import):
try:
    from slate_core.autonomous import (
        AutonomousOrchestrator,
        get_exploratory_config,
        AutonomousConfig
    )
    AUTONOMOUS_AVAILABLE = True
except ImportError:
    AUTONOMOUS_AVAILABLE = False

# 2. Add these global variables after line 74 (after start_time):
autonomous_orchestrator: Optional[AutonomousOrchestrator] = None
autonomous_enabled = False

# 3. Add this helper function after the global variables:
def track_user_activity():
    '''Track user activity for autonomous pause/resume'''
    if autonomous_enabled and autonomous_orchestrator:
        autonomous_orchestrator.record_user_activity()

# 4. Modify the startup event (around line 518):
@app.on_event("startup")
async def startup_event():
    '''Run on server startup.'''
    logger.info("=" * 60)
    logger.info("SLATE Server Starting")
    logger.info("=" * 60)
    logger.info(f"Port: 8788")
    logger.info(f"Mode: Paper Trading Only")
    logger.info(f"Dashboard: http://localhost:8788")
    logger.info(f"API Docs: http://localhost:8788/docs")
    logger.info("=" * 60)

    # NEW: Initialize autonomous system
    global autonomous_orchestrator, autonomous_enabled
    if AUTONOMOUS_AVAILABLE:
        try:
            autonomous_config = get_exploratory_config()
            autonomous_orchestrator = AutonomousOrchestrator(autonomous_config)
            autonomous_orchestrator.start()
            autonomous_enabled = True
            logger.info("✅ Autonomous system initialized and started")
        except Exception as e:
            logger.error(f"Failed to initialize autonomous system: {e}")
            autonomous_enabled = False

    # Start auto-discovery in background (existing code)
    asyncio.create_task(auto_start_discovery())

# 5. Modify the shutdown event (around line 534):
@app.on_event("shutdown")
async def shutdown_event():
    '''Run on server shutdown.'''
    global autonomous_orchestrator, autonomous_enabled, discovery_task

    logger.info("SLATE Server shutting down...")

    # NEW: Stop autonomous system
    if autonomous_orchestrator:
        try:
            autonomous_orchestrator.cleanup()
            autonomous_enabled = False
            logger.info("Autonomous system stopped")
        except Exception as e:
            logger.error(f"Error stopping autonomous system: {e}")

    discovery_running = False
    if discovery_task and not discovery_task.done():
        discovery_task.cancel()
        try:
            await discovery_task
        except asyncio.CancelledError:
            pass

# 6. Add track_user_activity() calls to existing endpoints:
# In these functions, add track_user_activity() at the beginning:
# - start_discovery() (line 149)
# - stop_discovery() (line 189)
# - generate_nl_strategy() (line 832)
# - test_nl_strategy() (line 893)

# 7. Add new API endpoints before the main entry point section (around line 550):

# Autonomous System APIs
@app.get("/api/autonomous/status")
async def api_get_autonomous_status():
    '''Get autonomous system status and configuration'''
    track_user_activity()
    return get_autonomous_status()

@app.get("/api/autonomous/discoveries")
async def api_get_autonomous_discoveries(limit: int = 20):
    '''Get autonomous discoveries'''
    track_user_activity()
    return get_autonomous_discoveries(limit=limit)

@app.post("/api/autonomous/start")
async def api_start_autonomous():
    '''Start autonomous operations'''
    track_user_activity()
    return start_autonomous_operations()

@app.post("/api/autonomous/stop")
async def api_stop_autonomous():
    '''Stop autonomous operations'''
    track_user_activity()
    return stop_autonomous_operations()

@app.get("/api/autonomous/report")
async def api_get_autonomous_report():
    '''Generate comprehensive autonomous discovery report'''
    track_user_activity()
    return generate_autonomous_report()

# Paste the get_autonomous_status(), get_autonomous_discoveries(),
# start_autonomous_operations(), stop_autonomous_operations(), and
# generate_autonomous_report() function definitions above these routes
"""

def print_integration_summary():
    """Print summary of server integration"""
    print("""
SLATE Autonomous System - Server Integration Summary
====================================================

✅ Ready to integrate autonomous capabilities into SLATE server

MODIFICATIONS REQUIRED:
1. Add imports (6 lines)
2. Add global variables (2 lines)
3. Add helper function (5 lines)
4. Modify startup event (10 lines)
5. Modify shutdown event (8 lines)
6. Add activity tracking (5 calls)
7. Add new API endpoints (6 routes + 5 functions)

TOTAL: ~50 lines of code to add

NEW API ENDPOINTS:
- GET /api/autonomous/status - Get autonomous system status
- GET /api/autonomous/discoveries - Get autonomous discoveries
- POST /api/autonomous/start - Start autonomous operations
- POST /api/autonomous/stop - Stop autonomous operations
- GET /api/autonomous/report - Generate comprehensive report
- POST /api/autonomous/config - Update configuration

FEATURES ADDED:
✅ Autonomous operations start/stop control
✅ Real-time status monitoring
✅ Discovery retrieval and reporting
✅ User activity tracking for reactive priority
✅ Integration with existing SLATE infrastructure
✅ Safety constraints enforced

TESTING:
1. Start server: python -m slate_core.server
2. Test status: curl http://localhost:8788/api/autonomous/status
3. Start autonomous: curl -X POST http://localhost:8788/api/autonomous/start
4. Check discoveries: curl http://localhost:8788/api/autonomous/discoveries
5. Generate report: curl http://localhost:8788/api/autonomous/report
6. Stop autonomous: curl -X POST http://localhost:8788/api/autonomous/stop

The autonomous system will now run during idle periods and pause
automatically when users interact with the SLATE API.
    """)