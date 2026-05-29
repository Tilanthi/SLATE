#!/bin/bash
# SLATE Auto-Start Script
# Ensures SLATE discovery engine starts on system boot
# Place in: ~/Library/LaunchAgents/com.slate.auto.plist

SLATE_DIR="/Users/gjw255/astrodata/SWARM/SLATE"
cd "$SLATE_DIR"

# Start server
nohup python3 -m slate_core.server > slate_server.log 2>&1 &
echo $! > slate_server.pid

# Start watchdog
nohup ./slate_watchdog.sh > slate_watchdog.log 2>&1 &
echo $! > slate_watchdog.pid

echo "SLATE auto-started at $(date)"
