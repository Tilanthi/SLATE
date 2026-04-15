# SLATE Port Configuration Change

## Summary

SLATE server port has been changed from **8787** to **8788** to avoid conflicts with another SLATE instance running on localhost:8787.

## Files Updated

### 1. Server Configuration
- **`slate_core/server.py`** - Changed default port and added environment variable override
  - Added `SLATE_PORT` environment variable support
  - Default port changed from 8787 → 8788

### 2. Documentation
- **`README.md`** - Updated dashboard URL reference
- **`graphpalace_integration/README.md`** - Updated all API endpoint examples
- **`graphpalace_integration/GRAPHPALACE_SLATE_PATCH.md`** - Updated test commands
- **`graphpalace_integration/INTEGRATION_SUMMARY.md`** - Updated quick start guide

### 3. Configuration
- **`.env.example`** - Updated port with explanatory comment
  - Added note: "Port 8788 avoids conflict with ASTRA running on 8787"
  - Added GraphPalace configuration section

## Usage

### Start SLATE on port 8788 (default)
```bash
cd /Users/gjw255/astrodata/SWARM/SLATE
python3 -m slate_core.server
```

### Start SLATE on custom port
```bash
export SLATE_PORT=9000
python3 -m slate_core.server
```

### Start with GraphPalace enabled
```bash
export SLATE_PORT=8788
export GRAPHPALACE_ENABLED=true
export GRAPHPALACE_PATH=./palace_data
python3 -m slate_core.server
```

## Access Points

| Service | URL |
|---------|-----|
| **SLATE API** | http://localhost:8788 |
| **Dashboard** | http://localhost:8788/dashboard |
| **API Docs** | http://localhost:8788/docs |
| **GraphPalace** | http://localhost:8788/api/palace/* |
| **Health Check** | http://localhost:8788/health |

## Port Conflicts

The following ports are now allocated:

| Port | Service |
|------|---------|
| 8787 | ASTRA (existing instance) |
| 8788 | SLATE (this instance) |

## Testing

Test that SLATE is running on the correct port:

```bash
# Health check
curl http://localhost:8788/health

# Should return:
# {"status":"healthy","mode":"paper_trading","timestamp":"..."}

# GraphPalace health
curl http://localhost:8788/api/palace/health

# Should return:
# {"available":true,"status":"healthy",...}
```

## Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
# Edit .env if needed
```

Key variables:
- `SLATE_PORT=8788` - Server port (default: 8788)
- `GRAPHPALACE_ENABLED=true` - Enable GraphPalace
- `GRAPHPALACE_PATH=./palace_data` - Palace data directory

## Notes

- ASTRA documentation (`CLAUDE.md`) still references port 8787 as it's a separate system
- The port change only affects this SLATE instance
- All GraphPalace integration examples have been updated to use port 8788
- The server now supports runtime port configuration via `SLATE_PORT` environment variable

---

**Updated**: 2026-04-14
**Status**: ✅ Complete
