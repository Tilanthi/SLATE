#!/bin/bash
cd /Users/gjw255/astrodata/SWARM/SLATE
git add slate_core/strategy_results.db 2>/dev/null || true
git add -f run_all.sh 2>/dev/null || true
git commit -m "data: mega sweep brutal costs + regime-switch Sharpe +3.43

Co-Authored-By: Claude <noreply@anthropic.com>" 2>/dev/null || true
git push origin main 2>/dev/null || true
echo "done"
