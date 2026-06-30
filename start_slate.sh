#!/bin/bash
# SLATE Auto-Start Script
# This script ensures SLATE server is running with autonomous discovery

SLATE_DIR="/Users/gjw255/astrodata/SWARM/SLATE"
LOG_FILE="/tmp/slate_startup.log"

cd "$SLATE_DIR" || exit 1

# Check if SLATE is already running
if curl -s http://127.0.0.1:8788/health > /dev/null 2>&1; then
    echo "$(date): SLATE server already running" >> "$LOG_FILE"
    exit 0
fi

echo "$(date): Starting SLATE server with autonomous discovery" >> "$LOG_FILE"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Start SLATE server
python -m slate_core.server >> "$LOG_FILE" 2>&1 &

# Wait for startup
sleep 5

# Verify it started
if curl -s http://127.0.0.1:8788/health > /dev/null 2>&1; then
    echo "$(date): SLATE server started successfully" >> "$LOG_FILE"
else
    echo "$(date): Failed to start SLATE server" >> "$LOG_FILE"
    exit 1
fi
