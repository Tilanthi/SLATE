#!/usr/bin/env python3
"""
SLATE Startup Script - Automatic Discovery Demonstration

This script demonstrates SLATE's automatic discovery system:
1. Starts SLATE with automatic discovery enabled
2. Shows system status and state transitions
3. Demonstrates pause/resume functionality
4. Displays discovery results

Usage:
    python start_slate.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add slate_core to path
slate_root = Path(__file__).parent
if str(slate_root) not in sys.path:
    sys.path.insert(0, str(slate_root))

from slate_core.startup_coordinator import (
    get_startup_coordinator,
    record_user_activity,
    execute_with_discovery_paused,
    get_system_status
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_automatic_discovery():
    """Demonstrate automatic discovery system."""
    print("=" * 70)
    print("SLATE AUTOMATIC DISCOVERY DEMONSTRATION")
    print("=" * 70)
    print()

    # Step 1: Start SLATE with automatic discovery
    print("Step 1: Starting SLATE with automatic discovery...")
    coordinator = get_startup_coordinator()
    print(f"✅ SLATE started - State: {coordinator.state.value}")
    print()

    # Step 2: Wait for discovery to run
    print("Step 2: Letting discovery run for 30 seconds...")
    await asyncio.sleep(30)
    print("✅ Discovery cycle running...")
    print()

    # Step 3: Check system status
    print("Step 3: Checking system status...")
    status = get_system_status()
    print(f"State: {status['state']}")
    print(f"Discovery Running: {status['discovery_running']}")
    print(f"Idle Time: {status['idle_time_seconds']:.0f} seconds")
    print(f"Startup Complete: {status['startup_complete']}")
    print()

    # Step 4: Simulate user activity
    print("Step 4: Simulating user activity (API call)...")
    record_user_activity()
    await asyncio.sleep(2)
    status = get_system_status()
    print(f"State after user activity: {status['state']}")
    print(f"User Requested Pause: {status['user_requested_pause']}")
    print()

    # Step 5: Wait and observe auto-resume
    print("Step 5: Waiting 10 seconds to observe state...")
    await asyncio.sleep(10)
    status = get_system_status()
    print(f"State after wait: {status['state']}")
    print(f"Resume in: {status['resume_in_minutes']:.1f} minutes")
    print()

    # Step 6: Execute specific task
    print("Step 6: Executing specific user task...")
    async def sample_task():
        """Sample user task."""
        print("  → Executing user task...")
        await asyncio.sleep(2)
        print("  → Task complete!")
        return {"status": "success", "data": "sample result"}

    result = await execute_with_discovery_paused(sample_task)
    print(f"✅ Task result: {result}")
    print()

    # Step 7: Final status check
    print("Step 7: Final system status...")
    await asyncio.sleep(5)
    status = get_system_status()
    print(f"Final State: {status['state']}")
    print(f"Discovery Running: {status['discovery_running']}")
    print(f"Total Idle Time: {status['idle_time_minutes']:.1f} minutes")
    print()

    print("=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print()
    print("Key Observations:")
    print("1. Discovery starts automatically on SLATE startup")
    print("2. User activity triggers automatic pause")
    print("3. System tracks idle time for auto-resume")
    print("4. Specific tasks pause discovery during execution")
    print("5. System returns to auto-discovery when idle")
    print()


async def main():
    """Main entry point."""
    try:
        await demo_automatic_discovery()
    except KeyboardInterrupt:
        print("\n⚠️  Demonstration interrupted by user")
    except Exception as e:
        logger.error(f"Error during demonstration: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())