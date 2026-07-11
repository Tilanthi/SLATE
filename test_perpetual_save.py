#!/usr/bin/env python3
"""
Test script to debug why perpetual discovery saves 0 strategies.
"""

import asyncio
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_perpetual_discovery():
    """Test the perpetual discovery integration with one simple strategy."""

    try:
        # Import the integration
        from slate_core.discovery.perpetual_discovery_integration import PerpetualDiscoveryIntegration

        logger.info("✅ Imported perpetual discovery integration")

        # Create integration
        integration = PerpetualDiscoveryIntegration()
        logger.info("✅ Created integration instance")

        # Test parameters - simple EMA crossover
        test_params = [{
            'edge_type': 'momentum_mean_reversion',
            'fast_period': 10,
            'slow_period': 20,
            'signal_threshold': 0.5,
            'position_size': 0.03
        }]

        logger.info(f"🔄 Testing with params: {test_params[0]}")

        # Process the batch
        result = await integration.process_agent_batch(test_params)

        logger.info(f"📊 Result: {result}")

        # Check database
        import sqlite3
        conn = sqlite3.connect('slate_core/slate_realistic_discoveries.db')
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM perpetual_discoveries")
        count = cursor.fetchone()[0]

        logger.info(f"💾 Database now has {count} perpetual discoveries")

        if count > 0:
            cursor.execute("SELECT strategy_name, total_profit_usdt, passed_validation FROM perpetual_discoveries ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            logger.info(f"Latest: {row}")
        else:
            logger.error("❌ Still 0 discoveries in database!")

        conn.close()

        return result

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return None

if __name__ == "__main__":
    result = asyncio.run(test_perpetual_discovery())
    sys.exit(0 if result and result.get('status') == 'success' else 1)
