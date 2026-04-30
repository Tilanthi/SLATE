#!/bin/bash
###############################################################################
# SLATE START SCRIPT
# Purpose: Start SLATE server with auto-discovery
# Usage: ./start_slate.sh
###############################################################################

echo "=========================================="
echo "SLATE STARTUP"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if port 8788 is already in use
if lsof -Pi :8788 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8788 already in use"
    echo "   Stopping existing SLATE server..."
    lsof -ti:8788 | xargs kill -15 2>/dev/null
    sleep 2
    echo "   ✓ Port cleared"
fi

echo ""
echo "🚀 Starting SLATE server..."
echo "   • Port: 8788"
echo "   • Mode: Paper Trading"
echo "   • Auto-Discovery: ENABLED"
echo ""

# Start the server
python3 -m slate_core.server &

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 3

# Check if server started
if lsof -Pi :8788 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo ""
    echo "✓ SLATE server started successfully!"
    echo ""
    echo "=========================================="
    echo "SLATE IS READY"
    echo "=========================================="
    echo ""
    echo "📊 Dashboard:    http://localhost:8788"
    echo "📚 API Docs:    http://localhost:8788/docs"
    echo "🔬 Discovery:    Auto-running"
    echo ""
    echo "Discovery cycles will run automatically."
    echo "Press Ctrl+C to stop the server."
    echo ""

    # Keep script running
    wait
else
    echo "❌ Failed to start SLATE server"
    echo "   Check the logs above for errors"
    exit 1
fi
