#!/bin/bash
# SLATE Auto-Restart Watchdog
# Ensures SLATE discovery engine is ALWAYS running
# Restarts automatically if server crashes

SLATE_DIR="/Users/gjw255/astrodata/SWARM/SLATE"
LOG_FILE="$SLATE_DIR/slate_watchdog.log"
PID_FILE="$SLATE_DIR/slate_server.pid"
SERVER_CMD="python3 -m slate_core.server"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_server() {
    log_message "Starting SLATE server..."
    cd "$SLATE_DIR"

    # Kill any existing process on port 8788
    lsof -ti:8788 | xargs kill -9 2>/dev/null

    # Start server in background
    nohup $SERVER_CMD > slate_server.log 2>&1 &
    echo $! > "$PID_FILE"

    # Wait a moment for startup
    sleep 5

    # Verify it's running
    if curl -s http://127.0.0.1:8788/health > /dev/null 2>&1; then
        log_message "✅ SLATE server started successfully (PID: $(cat $PID_FILE))"
        return 0
    else
        log_message "❌ Failed to start SLATE server"
        return 1
    fi
}

check_server() {
    # Check if PID file exists and process is running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            # Process is running, check if server is responsive
            if curl -s http://127.0.0.1:8788/health > /dev/null 2>&1; then
                return 0  # Server is healthy
            else
                log_message "⚠️  Server process exists but not responding"
                return 1  # Server not responding
            fi
        else
            log_message "⚠️  PID file exists but process not running"
            return 1  # Process dead
        fi
    else
        log_message "⚠️  No PID file found"
        return 1  # No server running
    fi
}

restart_server() {
    log_message "🔄 RESTARTING SLATE server..."

    # Try graceful shutdown first
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null
        sleep 3

        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null
        fi
    fi

    # Clear port if needed
    lsof -ti:8788 | xargs kill -9 2>/dev/null

    # Start fresh
    start_server
}

# Main watchdog loop
log_message "🐕 SLATE Watchdog started - ensuring discovery engine ALWAYS runs"
log_message "Will auto-restart if server crashes"

# Initial start
if ! check_server; then
    start_server
fi

# Monitor loop
while true; do
    sleep 30  # Check every 30 seconds

    if ! check_server; then
        log_message "⚠️  Server not responding - RESTARTING"
        restart_server
    fi

    # Log periodic status
    if [ $(( $(date +%s) % 300 )) -lt 30 ]; then  # Every 5 minutes
        log_message "✅ SLATE server running (PID: $(cat $PID_FILE)), discovery active"
    fi
done
