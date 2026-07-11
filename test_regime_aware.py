#!/usr/bin/env python3
"""
Test script to verify regime-aware discovery implementation
"""
import asyncio
import sys
sys.path.append('/Users/gjw255/astrodata/SWARM/SLATE')

async def test_regime_aware_discovery():
    """Test the regime-aware discovery system."""
    print("🧠 Testing Regime-Aware Discovery Implementation")
    print("=" * 60)

    try:
        from slate_core.intelligence.regime_aware_discovery import get_regime_aware_manager
        from slate_core.swarm.swarm_integration import SwarmDiscoveryIntegration

        print("✅ Imported regime-aware modules successfully")

        # Test regime-aware manager initialization
        manager = get_regime_aware_manager()
        print(f"✅ Regime-aware manager initialized: {manager}")

        # Test swarm integration with regime awareness
        integration = SwarmDiscoveryIntegration()
        print(f"✅ Swarm integration created: {integration}")

        # Check if regime-aware manager is set
        if hasattr(integration, 'regime_aware_manager'):
            print(f"✅ Regime-aware manager in integration: {integration.regime_aware_manager}")

        # Test initialization
        print("\n🔄 Testing initialization...")
        init_result = await integration.initialize()
        print(f"Initialization result: {init_result}")

        if init_result['status'] == 'success':
            print("✅ Regime-aware discovery initialized successfully")
            print(f"✅ Message: {init_result['message']}")

            # Test stats
            if hasattr(integration, 'integration_stats'):
                stats = integration.integration_stats
                print(f"✅ Integration stats: {stats}")

            return True
        else:
            print(f"❌ Initialization failed: {init_result}")
            return False

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_regime_aware_discovery())
    print("\n" + "=" * 60)
    if success:
        print("✅ REGIME-AWARE DISCOVERY TEST PASSED")
    else:
        print("❌ REGIME-AWARE DISCOVERY TEST FAILED")
    sys.exit(0 if success else 1)