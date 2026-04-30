#!/bin/bash
###############################################################################
# SLATE RESTART SCRIPT
# Purpose: Quick restart of SLATE server
###############################################################################

echo "=========================================="
echo "SLATE RESTART"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Change to parent directory (SLATE root)
cd "$SCRIPT_DIR/.."

# Stop existing server if running
if lsof -Pi :8788 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "🛑 Stopping existing SLATE server..."
    lsof -ti:8788 | xargs kill -15 2>/dev/null
    sleep 2
    echo "   ✓ Server stopped"
fi

# Start the server
echo ""
echo "🚀 Starting SLATE server..."
echo ""

# Use the start script
exec ./start_slate.sh
