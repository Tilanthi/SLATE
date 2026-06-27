# SLATE Automatic Discovery Architecture

## Overview

SLATE has been reconfigured to **always start with automatic discovery enabled**. This means that whenever you start SLATE, it will immediately begin discovering trading strategies continuously in the background.

## What Changed

### 1. New Core Components

#### `slate_core/__init__.py`
- Main module entry point
- Provides `create_slate_system()` for easy initialization
- Exports core functionality

#### `slate_core/startup_coordinator.py`
- **NEW**: Manages automatic discovery on startup
- Handles pause/resume based on user activity
- Tracks system state and idle time
- Ensures discovery always runs unless doing specific tasks

### 2. Updated Architecture

**Before**: Manual discovery start required
```python
# Old way - had to manually start discovery
engine = EdgeDiscoveryEngine()
results = await engine.run_multi_timeframe_discovery_cycle()
```

**After**: Automatic discovery by default
```python
# New way - discovery starts automatically
coordinator = get_startup_coordinator()
# Discovery is already running in background
```

### 3. System States

The coordinator manages these states:
- `AUTO_DISCOVERY`: Running continuous discovery (default)
- `USER_TASK`: Executing specific user request
- `PAUSED`: Temporarily paused
- `IDLE`: Waiting to resume

### 4. Smart Pause/Resume

- User activity automatically pauses discovery
- API calls, queries, and tasks trigger pause
- Resumes after 5 minutes of user inactivity
- Ensures user requests get priority

## How It Works

### Startup Sequence

1. **Server Launch**: `python -m slate_core.server`
2. **Coordinator Init**: Startup coordinator initializes automatically
3. **Discovery Start**: Background discovery begins immediately
4. **Continuous Operation**: Runs in 5-second cycles
5. **Smart Pause**: User activity triggers automatic pause
6. **Auto Resume**: Resumes after 5 minutes idle

### User Interaction

```python
# Record user activity (auto-pauses discovery)
from slate_core.startup_coordinator import record_user_activity
record_user_activity()

# Execute specific task with discovery paused
from slate_core.startup_coordinator import execute_with_discovery_paused
result = await execute_with_discovery_paused(my_function, arg1, arg2)

# Check system status
from slate_core.startup_coordinator import get_system_status
status = get_system_status()
```

## Usage Examples

### Basic Usage (Automatic Discovery)

```bash
# Start SLATE - discovery begins automatically
cd /Users/gjw255/astrodata/SWARM/SLATE
python -m slate_core.server
```

### Programmatic Usage

```python
import asyncio
from slate_core.startup_coordinator import get_startup_coordinator

async def main():
    # Get coordinator (auto-starts discovery)
    coordinator = get_startup_coordinator()

    # Discovery is now running continuously
    # Do other work while discovery continues in background

    await asyncio.sleep(60)  # Let discovery run for 1 minute

    # Check status
    status = coordinator.get_status()
    print(f"Discovery: {status['discovery_running']}")

asyncio.run(main())
```

### With User Tasks

```python
from slate_core.startup_coordinator import execute_with_discovery_paused

async def my_analysis_task():
    # This function will run with discovery paused
    # Discovery resumes automatically when done
    return {"result": "analysis complete"}

# Execute with automatic pause/resume
result = await execute_with_discovery_paused(my_analysis_task)
```

## Configuration

### Default Settings

```python
idle_timeout_minutes = 5  # Resume discovery after 5 minutes idle
discovery_cycle_interval_seconds = 5  # Run discovery every 5 seconds
```

### Custom Configuration

```python
from slate_core.startup_coordinator import get_startup_coordinator

coordinator = get_startup_coordinator()
coordinator.idle_timeout_minutes = 10  # Customize idle timeout
coordinator.discovery_cycle_interval_seconds = 10  # Customize interval
```

## API Integration

### Server Integration

The startup coordinator is integrated into the SLATE server:

```python
# In server.py startup event
startup_coordinator = await initialize_with_discovery()

# All API endpoints track user activity
@app.post("/api/discovery/start")
async def start_discovery():
    track_user_activity()  # Automatically pauses discovery
    # ... user request handling
```

### Health Check

```bash
curl http://localhost:8788/health
```

Returns:
```json
{
  "status": "healthy",
  "discovery_running": true,
  "startup_coordinator": {
    "state": "auto_discovery",
    "idle_time_seconds": 123.4,
    "resume_in_minutes": 3.2,
    "user_requested_pause": false
  }
}
```

## Testing

### Verification Script

```bash
python verify_startup.py
```

Tests:
1. Coordinator initialization
2. Initial state check
3. Discovery engine initialization
4. Status structure validation
5. Configuration verification

### Manual Testing

```bash
# 1. Start server
python -m slate_core.server

# 2. Check logs for automatic discovery
# Should see: "Discovery loop started - will run continuously"

# 3. Make API call (triggers pause)
curl http://localhost:8788/api/discovery/statistics

# 4. Wait 5 minutes (auto-resume)

# 5. Check status
curl http://localhost:8788/health
```

## Benefits

1. **Always On**: SLATE is continuously discovering strategies
2. **Smart Resource Management**: Pauses for user work, resumes when idle
3. **Better Utilization**: Maximizes discovery time
4. **User Priority**: User requests always get priority
5. **Improved Safety**: Better activity tracking and state management

## Safety Constraints

The automatic discovery system maintains all safety constraints:

- **Paper Trading Only**: Never real money
- **Realistic Costs**: Always applies transaction costs
- **Resource Limits**: CPU, memory, time constraints
- **File Safety**: Only modifies files in `slate_core/`
- **Data Integrity**: Only uses real market data (never synthetic)

## Troubleshooting

### Discovery Not Starting

```bash
# Check coordinator status
python -c "from slate_core.startup_coordinator import get_system_status; import pprint; pprint.pprint(get_system_status())"

# Verify discovery engine
python -c "from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine; engine = EdgeDiscoveryEngine(); print('Engine OK')"
```

### Discovery Not Pausing on User Activity

```bash
# Check activity tracking
python -c "from slate_core.startup_coordinator import record_user_activity; record_user_activity(); print('Activity recorded')"

# Verify state change
python -c "from slate_core.startup_coordinator import get_system_status; print(get_system_status()['state'])"
```

### Database Issues

```bash
# Reset database
rm -f slate_core/slate_realistic_discoveries.db

# Restart server
python -m slate_core.server
```

## Future Enhancements

Planned improvements to the automatic discovery system:

1. **Adaptive Intervals**: Adjust discovery frequency based on results
2. **Priority Tasks**: Queue system for user tasks during discovery
3. **Resource Monitoring**: Better CPU/memory tracking
4. **Result Streaming**: Real-time discovery result streaming
5. **Multi-Symbol**: Expand beyond SOLUSDT to multiple pairs

## Summary

The automatic discovery architecture ensures SLATE is **always discovering** unless you're doing specific tasks. This maximizes strategy discovery while maintaining user priority and system safety.

**Key Point**: You no longer need to manually start discovery - it starts automatically when SLATE launches and runs continuously in the background.