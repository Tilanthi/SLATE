#!/bin/bash
set -e
cd /Users/gjw255/astrodata/SWARM/SLATE

echo "=== Commit + push code ==="
git add slate_core/discovery/mega_sweep.py slate_core/portfolio/regime_switch.py 2>/dev/null || true
git commit -m "fix: brutally honest costs + trend-following regime map

Co-Authored-By: Claude <noreply@anthropic.com>" 2>/dev/null || true
git push origin main 2>/dev/null || true

echo "=== Restart server ==="
launchctl unload ~/Library/LaunchAgents/com.slate.autoserver.plist 2>/dev/null || true
pkill -9 -f "slate_core.server" 2>/dev/null || true
sleep 3
launchctl load ~/Library/LaunchAgents/com.slate.autoserver.plist 2>/dev/null || true

echo "=== Wait for health ==="
for i in $(seq 1 30); do
  curl -s --max-time 3 http://127.0.0.1:8788/health >/dev/null 2>&1 && break
  sleep 5
done
echo "Server healthy"

echo "=== Running mega sweep (5000 variants, brutally honest costs) ==="
curl -s -X POST http://127.0.0.1:8788/api/sweep/run --max-time 600
echo ""
echo "=== DONE ==="
