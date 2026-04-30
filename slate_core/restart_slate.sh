#!/bin/bash
###############################################################################
# SLATE RESTART SCRIPT
# Created: 2026-04-18
# Updated: 2026-04-30 (moved to slate_core/)
# Purpose: Quick restart of SLATE system after shutdown
###############################################################################

echo "=========================================="
echo "SLATE SYSTEM RESTART"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Change to parent directory (SLATE root)
cd "$SCRIPT_DIR/.."

# Check if port 8788 is already in use
if lsof -Pi :8788 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8788 already in use"
    echo "   Do you want to stop the existing process? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "   Stopping existing SLATE server..."
        lsof -ti:8788 | xargs kill -15
        sleep 2
        echo "   ✓ Server stopped"
    else
        echo "   Exiting..."
        exit 1
    fi
fi

# Start SLATE server
echo ""
echo "🚀 Starting SLATE server..."
echo "   Port: 8788"
echo "   Mode: Paper Trading"
echo "   Dashboard: http://localhost:8788"
echo ""

python3 -m slate_core.server &

# Wait for server to start
sleep 3

# Check if server started successfully
if lsof -Pi :8788 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "✓ SLATE server started successfully!"
    echo ""
    echo "Access dashboards:"
    echo "  • Main: http://localhost:8788/dashboard"
    echo "  • Discovery: http://localhost:8788/discovery-dashboard"
    echo "  • API Docs: http://localhost:8788/docs"
    echo ""
    echo "Server is ready for paper trading!"
else
    echo "❌ Failed to start SLATE server"
    echo "   Check logs for errors"
    exit 1
fi

echo ""
echo "=========================================="
echo "SYSTEM READY"
echo "=========================================="
