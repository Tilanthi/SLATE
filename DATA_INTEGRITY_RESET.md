# SLATE Data Integrity Reset - May 4, 2026

## What Happened

On May 4, 2026, it was discovered that SLATE's visualization and analysis had used **synthetic, artificially generated price data** instead of the real market data that was actually used for strategy discovery. This violated the core principle of SLATE: discovering **genuine market edges** using only authentic market conditions.

## The Violation

- **What**: Created regime-switching price simulation with artificial patterns
- **Impact**: Misleading visualizations that didn't match real market behavior  
- **Violation**: Core SLATE principle of using ONLY real market data

## Actions Taken

### 1. Policy Updates
- ✅ Updated `/Users/gjw255/.claude/CLAUDE.md` with synthetic data prohibition
- ✅ Created `/Users/gjw255/astrodata/SWARM/SLATE/CLAUDE.md` with project-specific rules
- ✅ Updated README.md with real data policy section

### 2. Data Purge
- ✅ Deleted discovery database (`slate_realistic_discoveries.db`)
- ✅ Cleared all knowledge graph files
- ✅ Removed reflection memory logs
- ✅ Cleared checkpoint databases

### 3. Fresh Initialization
- ✅ Created new database with REAL_DATA_ONLY policy
- ✅ Added metadata tracking for data integrity
- ✅ Verified all fake data removed

## Permanent Rules

**ABSOLUTELY FORBIDDEN:**
- ❌ Synthetic price data generation
- ❌ Artificial market simulations
- ❌ Fake regime-switching patterns
- ❌ Any fabricated trading data

**MANDATORY REQUIREMENTS:**
- ✅ Use ONLY real Binance market data (or other exchange APIs)
- ✅ Apply brutally realistic transaction costs (fees, slippage, fill rates)
- ✅ Never assume 100% fill rates or zero slippage
- ✅ Always verify data sources are authentic

## Transaction Cost Policy (Non-Negotiable)

```
Maker Fee: 0.02%
Taker Fee: 0.05%
Slippage: 10-20 bps (volatility-adjusted)
Fill Rate: 85% (never 100%)
Partial Fills: 15% probability
Position Limits: 5% max per position
```

## Current Status

**Discoveries**: 0 (clean slate)
**Database**: Fresh with real data policy
**Policy**: REAL_DATA_ONLY enforced
**Next Discovery**: Will use only authentic market data

## Recovery

SLATE will now restart discovery cycles from scratch, using only genuine market data to discover legitimate trading edges. All future visualizations and analyses must use the actual cached market data from `sol_data_cache/SOLUSDT_1h_1y.csv`.

**Rule**: If synthetic data is ever discovered, the entire system will be reset again without exception.

---

**Date**: May 4, 2026  
**Reset By**: Data Integrity Policy Enforcement  
**Status**: COMPLETE - System Clean and Ready for Authentic Discovery
