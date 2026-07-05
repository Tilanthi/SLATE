#!/usr/bin/env python3
"""
SLATE Startup Script - Auto-restart enabled

This is the main entry point for running SLATE with automatic
restart capability. Use this instead of running the server directly.

Usage:
    python3 start_slate.py

The watchdog will:
1. Start the SLATE server automatically
2. Monitor server health continuously
3. Auto-restart if server crashes
4. Ensure discovery pipeline is always running
5. Handle graceful shutdown on Ctrl+C

For manual server control:
    python3 -m slate_core.server    # Direct server start (no auto-restart)
"""

import sys
import subprocess
from pathlib import Path

# Change to SLATE directory
slate_dir = Path(__file__).parent
import os
os.chdir(slate_dir)

print("=" * 70)
print("🚀 SLATE - Autonomous Quantitative Trading System")
print("🧠 Closed-Loop AI Scientific Discovery Framework")
print("=" * 70)
print("Starting with auto-restart watchdog...")
print("Press Ctrl+C to stop")
print("=" * 70)

# Start the watchdog
subprocess.run([sys.executable, "slate_watchdog.py"])