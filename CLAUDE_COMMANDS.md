# CLAUDE_COMMANDS.md - Complete Command Reference

**Purpose:** Comprehensive command reference for SLATE system operation and monitoring

---

## Quick Start Commands

### Start SLATE System
```bash
# Navigate to SLATE directory
cd /Users/gjw255/astrodata/SWARM/SLATE/

# Start the server
python -m slate_core.server
```

### Check Basic System Status
```bash
# Overall system health
curl http://127.0.0.1:8788/health

# Check server is running
curl http://127.0.0.1:8788/
```

---

## Trading Intelligence Commands

### Intelligence System Status
```bash
# Comprehensive intelligence system status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.'

# Component availability status
curl http://127.0.0.1:8788/api/intelligence/components | jq '.'

# Orchestrator status specifically
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.orchestrator_status'

# Portfolio status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.portfolio_status'

# Health monitoring status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.health_monitor_status'

# Risk control status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.risk_controller_status'
```

### Toggle Intelligence System
```bash
# Enable intelligence layer
curl -X POST "http://127.0.0.1:8788/api/intelligence/toggle?enabled=true"

# Disable intelligence layer
curl -X POST "http://127.0.0.1:8788/api/intelligence/toggle?enabled=false"
```

---

## Discovery Commands

### Phase 1 Enhanced Discovery
```bash
# Start Phase 1 enhanced discovery (25 strategies)
curl -X POST "http://127.0.0.1:8788/api/discovery/phase1/start?num_strategies=25"

# Start Phase 1 enhanced discovery (100 strategies)
curl -X POST "http://127.0.0.1:8788/api/discovery/phase1/start?num_strategies=100"

# Get Phase 1 statistics
curl http://127.0.0.1:8788/api/discovery/phase1/stats | jq '.'

# Start Phase 1 enhanced discovery (custom number)
curl -X POST "http://127.0.0.1:8788/api/discovery/phase1/start?num_strategies=50"
```

### Enhanced Discovery System
```bash
# Start full enhanced discovery (100 strategies)
curl -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=100"

# Start full enhanced discovery (500 strategies)
curl -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=500"

# Get enhanced system statistics
curl http://127.0.0.1:8788/api/discovery/enhanced/stats | jq '.'

# Performance comparison (baseline vs enhanced)
curl http://127.0.0.1:8788/api/discovery/performance | jq '.'
```

---

## Database Commands

### Direct Database Access
```bash
# Access database directly
sqlite3 slate_core/slate_realistic_discoveries.db

# Once in SQLite, run queries:
# .tables                    # List all tables
# .schema                    # Show table structure
# SELECT COUNT(*) FROM discoveries;  # Total discoveries
# .quit                      # Exit SQLite
```

### Database Query Examples
```bash
# Count total discoveries
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM discoveries;"

# Count profitable strategies
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM discoveries WHERE total_return > 0;"

# Count recent discoveries (last 24 hours)
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM discoveries WHERE created_at > datetime('now', '-24 hours');"

# Show recent discoveries with returns
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT symbol, timeframe, edge_type, total_return FROM discoveries ORDER BY created_at DESC LIMIT 10;"

# Show profitable strategies with win rates
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT symbol, timeframe, edge_type, total_return, win_rate FROM discoveries WHERE total_return > 0 ORDER BY total_return DESC LIMIT 10;"
```

---

## Monitoring Commands

### Real-Time Monitoring
```bash
# Watch intelligence status (continuous)
watch -n 5 'curl -s http://127.0.0.1:8788/api/intelligence/status | jq ."intelligence_system"'

# Watch discovery progress
watch -n 10 'curl -s http://127.0.0.1:8788/api/discovery/enhanced/stats | jq ."enhanced_discovery"'

# Monitor portfolio status
watch -n 5 'curl -s http://127.0.0.1:8788/api/intelligence/status | jq ."intelligence_system.portfolio_status"'
```

### Log Monitoring
```bash
# Follow server logs (if logging to file)
tail -f slate_core/logs/server.log

# Follow intelligence orchestrator logs
tail -f slate_core/logs/intelligence_orchestrator.log

# Search for errors in logs
grep -i error slate_core/logs/*.log

# Search for recent deployment activity
grep -i "deployed" slate_core/logs/intelligence_orchestrator.log | tail -20
```

---

## System Administration Commands

### Verify System Status
```bash
# Check if server is running
ps aux | grep "slate_core.server"

# Check port 8788 is listening
lsof -i :8788

# Check system resources
top | grep python

# Check disk space for database
df -h | grep slate_core
```

### Git Repository Status
```bash
# Confirm you're in SLATE directory
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/

# Check git remote (should be SLATE repository)
git remote -v  # Should show: https://github.com/Tilanthi/SLATE.git

# Check git status
git status

# Check current branch
git branch

# Check recent commits
git log --oneline -5
```

---

## GitHub Push Commands

### Push to GitHub (SLATE Repository)
```bash
# Always confirm you're in SLATE before pushing
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/

# Verify git remote (should be SLATE repository)
git remote -v  # Should show: https://github.com/Tilanthi/SLATE.git

# Stage all changes
git add .

# Commit changes
git commit -m "Your commit message here"

# Push to main branch
git push origin main
```

### GitHub Push Verification
```bash
# Confirm push succeeded
git log --oneline -1

# Check remote branch status
git status
```

---

## Testing and Validation Commands

### Test Intelligence System
```bash
# Test intelligence status endpoint
curl -v http://127.0.0.1:8788/api/intelligence/status

# Test components endpoint
curl -v http://127.0.0.1:8788/api/intelligence/components

# Test toggle endpoint
curl -v -X POST "http://127.0.0.1:8788/api/intelligence/toggle?enabled=true"
```

### Test Discovery System
```bash
# Test Phase 1 discovery
curl -v -X POST "http://127.0.0.1:8788/api/discovery/phase1/start?num_strategies=10"

# Test enhanced discovery
curl -v -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=10"

# Test stats endpoints
curl -v http://127.0.0.1:8788/api/discovery/phase1/stats
curl -v http://127.0.0.1:8788/api/discovery/enhanced/stats
```

---

## Performance Analysis Commands

### Discovery Performance
```bash
# Get discovery performance comparison
curl http://127.0.0.1:8788/api/discovery/performance | jq '.'

# Get enhanced discovery stats
curl http://127.0.0.1:8788/api/discovery/enhanced/stats | jq '.enhanced_discovery'

# Get Phase 1 stats
curl http://127.0.0.1:8788/api/discovery/phase1/stats | jq '.phase1_discovery'
```

### Intelligence Performance
```bash
# Get intelligence cycle statistics
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.orchestrator_status.cycle_stats'

# Get portfolio performance
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.portfolio_status.performance'

# Get health monitoring statistics
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.health_monitor_status.monitoring_stats'
```

---

## Troubleshooting Commands

### Check System Health
```bash
# Overall system health
curl http://127.0.0.1:8788/health | jq '.'

# Intelligence system health
curl http://127.0.0.1:8788/api/intelligence/status | jq '.system_health'

# Component health
curl http://127.0.0.1:8788/api/intelligence/components | jq '.'
```

### Check for Errors
```bash
# Check for system errors
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.orchestrator_status.error_count'

# Check for risk alerts
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.risk_controller_status.risk_alerts'

# Check for unhealthy strategies
curl http://127.0.0.1:8788/api/intelligence/status | jq '.intelligence_system.health_monitor_status.unhealthy_strategies'
```

### Restart Components
```bash
# Restart SLATE server
# First, find the process
ps aux | grep "slate_core.server"

# Then kill the process (replace PID with actual process ID)
kill <PID>

# Restart the server
python -m slate_core.server
```

---

## Quick Reference Summary

### Most Common Commands
```bash
# Start system
python -m slate_core.server

# Check status
curl http://127.0.0.1:8788/health

# Intelligence status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.'

# Start discovery
curl -X POST "http://127.0.0.1:8788/api/discovery/enhanced/start?num_strategies=100"

# Database access
sqlite3 slate_core/slate_realistic_discoveries.db
```

### Status Monitoring
```bash
# Overall health
curl http://127.0.0.1:8788/health

# Intelligence status
curl http://127.0.0.1:8788/api/intelligence/status | jq '.'

# Component status
curl http://127.0.0.1:8788/api/intelligence/components | jq '.'
```

### GitHub Push
```bash
# Verify directory
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/

# Stage and commit
git add .
git commit -m "Update documentation"

# Push to main
git push origin main
```

---

## Notes

- **All curl commands assume server is running on port 8788**
- **jq is used for JSON formatting - install with: brew install jq**
- **SQLite commands require sqlite3 to be installed**
- **GitHub commands assume git is configured and authenticated**
- **Always verify you're in SLATE directory before pushing to GitHub**

---

*Last Updated: 2026-06-30*
*Complete command reference for SLATE Autonomous Quantitative Trading System*