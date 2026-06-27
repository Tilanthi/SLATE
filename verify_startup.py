#!/usr/bin/env python3
"""
SLATE Startup Verification Script

Tests the automatic discovery startup system.
"""

import sys
import asyncio
from pathlib import Path

# Add slate_core to path
slate_root = Path(__file__).parent
if str(slate_root) not in sys.path:
    sys.path.insert(0, str(slate_root))

from slate_core.startup_coordinator import get_startup_coordinator, get_system_status


async def test_startup_system():
    """Test the startup coordinator system."""
    print("=" * 60)
    print("SLATE STARTUP SYSTEM VERIFICATION")
    print("=" * 60)

    # Test 1: Initialize coordinator
    print("\n✓ Test 1: Initialize Startup Coordinator")
    coordinator = get_startup_coordinator()
    assert coordinator is not None, "Coordinator initialization failed"
    print("  Coordinator initialized successfully")

    # Test 2: Check initial state
    print("\n✓ Test 2: Check Initial State")
    status = get_system_status()
    print(f"  State: {status['state']}")
    print(f"  Startup Complete: {status['startup_complete']}")
    assert status['state'] == 'auto_discovery', f"Expected auto_discovery, got {status['state']}"

    # Test 3: Discovery engine
    print("\n✓ Test 3: Discovery Engine Initialization")
    assert coordinator.discovery_engine is not None, "Discovery engine not initialized"
    print("  Discovery engine initialized")

    # Test 4: Status structure
    print("\n✓ Test 4: Status Structure")
    required_keys = ['state', 'startup_complete', 'discovery_running',
                   'idle_time_seconds', 'configuration']
    for key in required_keys:
        assert key in status, f"Missing key: {key}"
    print(f"  All required status keys present: {required_keys}")

    # Test 5: Configuration
    print("\n✓ Test 5: Configuration Check")
    config = status['configuration']
    assert 'idle_timeout_minutes' in config, "Missing idle_timeout_minutes"
    assert 'discovery_cycle_interval_seconds' in config, "Missing discovery_cycle_interval_seconds"
    print(f"  Idle timeout: {config['idle_timeout_minutes']} minutes")
    print(f"  Discovery interval: {config['discovery_cycle_interval_seconds']} seconds")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print("\nStartup system is working correctly!")
    print("\nNext steps:")
    print("1. Start server: python -m slate_core.server")
    print("2. Check dashboard: http://localhost:8788")
    print("3. Monitor automatic discovery in logs")


if __name__ == "__main__":
    try:
        asyncio.run(test_startup_system())
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)