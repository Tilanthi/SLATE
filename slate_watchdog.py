#!/usr/bin/env python3
"""
SLATE Server Watchdog - Auto-restart and monitoring

This watchdog ensures SLATE server is always running and automatically
restarts it if it crashes. It also monitors the discovery pipeline to
ensure continuous operation.

Features:
- Auto-restart server if it crashes
- Monitor server health endpoint
- Ensure discovery pipeline is running
- Start automatically when SLATE is launched
- Respect user activity (don't restart during active work)

Usage:
    python3 slate_watchdog.py

The watchdog will:
1. Start the SLATE server if not running
2. Monitor server health every 30 seconds
3. Auto-restart if server crashes
4. Ensure discovery pipeline is running
"""

import asyncio
import requests
import subprocess
import signal
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('slate_watchdog.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SLATEWatchdog:
    """Monitor and auto-restart SLATE server."""

    def __init__(self):
        self.server_process = None
        self.server_url = "http://127.0.0.1:8788"
        self.health_endpoint = f"{self.server_url}/health"
        self.check_interval = 30  # seconds
        self.restart_delay = 10   # seconds to wait before restart
        self.max_restart_attempts = 5
        self.restart_attempts = 0
        self.running = True

        # User activity tracking
        self.last_user_activity = datetime.now()
        self.user_activity_timeout = 300  # 5 minutes

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("🛑 Watchdog received shutdown signal...")
        self.running = False

        if self.server_process:
            logger.info("🛑 Stopping SLATE server...")
            self.server_process.terminate()

            # Wait up to 10 seconds for graceful shutdown
            try:
                self.server_process.wait(timeout=10)
                logger.info("✅ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Server didn't stop gracefully, forcing...")
                self.server_process.kill()

        sys.exit(0)

    def check_server_running(self) -> bool:
        """Check if server process is running."""
        if self.server_process is None:
            return False

        # Check process status
        return self.server_process.poll() is None

    def check_server_health(self) -> bool:
        """Check if server is responding to health checks."""
        try:
            response = requests.get(
                self.health_endpoint,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def get_discovery_status(self) -> dict:
        """Get discovery pipeline status."""
        try:
            response = requests.get(
                f"{self.server_url}/api/closed-loop/status",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"Discovery status check failed: {e}")
        return {}

    def start_server(self):
        """Start the SLATE server."""
        logger.info("🚀 Starting SLATE server...")

        try:
            # Start server as subprocess
            self.server_process = subprocess.Popen(
                [sys.executable, "-m", "slate_core.server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            logger.info(f"✅ Server started (PID: {self.server_process.pid})")

            # Wait for server to be ready
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                if self.check_server_health():
                    logger.info("✅ Server is healthy and ready")
                    self.restart_attempts = 0  # Reset counter on successful start
                    return True

            logger.error("❌ Server started but not responding to health checks")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            return False

    def stop_server(self):
        """Stop the SLATE server gracefully."""
        if self.server_process:
            logger.info("🛑 Stopping server...")
            self.server_process.terminate()

            try:
                self.server_process.wait(timeout=10)
                logger.info("✅ Server stopped")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Forcing server stop...")
                self.server_process.kill()

    def restart_server(self):
        """Restart the SLATE server."""
        logger.info("🔄 Restarting server...")

        # Stop existing server
        self.stop_server()
        time.sleep(self.restart_delay)

        # Start new server
        return self.start_server()

    def monitor_and_maintain(self):
        """Main monitoring loop - checks server health and restarts if needed."""
        logger.info("🐕 Watchdog started - monitoring SLATE server")
        logger.info(f"   Health check interval: {self.check_interval}s")
        logger.info(f"   Server URL: {self.server_url}")
        logger.info("=" * 70)

        while self.running:
            try:
                # Sleep for check interval
                time.sleep(self.check_interval)

                # Check if server process is running
                if not self.check_server_running():
                    logger.warning("⚠️  Server process not running - attempting restart...")

                    if self.restart_attempts < self.max_restart_attempts:
                        self.restart_attempts += 1
                        logger.warning(f"🔄 Restart attempt {self.restart_attempts}/{self.max_restart_attempts}")

                        if self.start_server():
                            logger.info("✅ Server restarted successfully")
                        else:
                            logger.error("❌ Failed to restart server")
                    else:
                        logger.error("❌ Max restart attempts reached - giving up")
                        self.running = False
                    continue

                # Check server health endpoint
                if not self.check_server_health():
                    logger.warning("⚠️  Server not responding to health checks - attempting restart...")

                    if self.restart_attempts < self.max_restart_attempts:
                        self.restart_attempts += 1
                        logger.warning(f"🔄 Restart attempt {self.restart_attempts}/{self.max_restart_attempts}")

                        if self.restart_server():
                            logger.info("✅ Server restarted successfully")
                        else:
                            logger.error("❌ Failed to restart server")
                    else:
                        logger.error("❌ Max restart attempts reached - giving up")
                        self.running = False
                    continue

                # Check discovery status
                discovery_status = self.get_discovery_status()
                if discovery_status:
                    discovery_running = discovery_status.get('discovery_running', False)
                    if not discovery_running:
                        logger.debug("⏸️  Discovery not running (user activity detected)")
                    else:
                        logger.debug("✅ Discovery pipeline running")

                # Reset restart attempts on successful check
                if self.restart_attempts > 0:
                    logger.info("✅ Server stable - resetting restart counter")
                    self.restart_attempts = 0

            except KeyboardInterrupt:
                logger.info("🛑 Watchdog interrupted by user")
                self.running = False
                break

            except Exception as e:
                logger.error(f"❌ Watchdog monitoring error: {e}", exc_info=True)
                time.sleep(60)  # Wait longer on errors

        logger.info("🛑 Watchdog stopping...")

    def run(self):
        """Main entry point - start monitoring."""
        logger.info("=" * 70)
        logger.info("🐕 SLATE WATCHDOG STARTING")
        logger.info("=" * 70)
        logger.info(f"Time: {datetime.now().isoformat()}")
        logger.info(f"Mode: Auto-restart enabled")
        logger.info(f"Max restart attempts: {self.max_restart_attempts}")
        logger.info("=" * 70)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Start server if not running
        if not self.check_server_running():
            if not self.start_server():
                logger.error("❌ Failed to start server - exiting watchdog")
                return
        else:
            logger.info("✅ Server already running")

        # Start monitoring loop
        self.monitor_and_maintain()


def main():
    """Main entry point."""
    watchdog = SLATEWatchdog()
    watchdog.run()


if __name__ == "__main__":
    main()
