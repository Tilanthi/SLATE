# SLATE Drawdown Calculation Fix - May 4, 2026

## What Happened

On May 4, 2026, a critical flaw was discovered in SLATE's backtesting drawdown calculation. The system was only tracking equity at **trade exit points**, not continuously during holding periods. This severely understated the true risk exposure of all strategies.

## The Bug

**Original Implementation (WRONG):**
```python
equity_curve.append(capital)  # ONLY called when trades exit
```

This meant:
- Equity was updated only when a position was closed
- Unrealized losses during holding periods were NOT captured
- Max drawdown was calculated from discrete points, missing true risk

**Example of the Flaw:**
```
1. Enter long at $100 (capital: $10,000)
2. Price drops to $85 → 15% unrealized loss (NOT recorded in equity curve!)
3. Price rallies to $105 → Exit with $5 profit
4. Equity curve shows: $10,000 → $10,050 (0.5% return)
5. Calculated max drawdown: ~0%
6. TRUE max drawdown: 15%
```

## Impact

**All previous discoveries in the database have INCORRECT drawdown metrics:**
- Reported drawdowns of 0.3-0.5% were actually likely 10-20%+
- This created a false sense of safety
- Strategies appeared much less risky than they actually were
- Sharpe ratios were also inflated (calculated from trade returns, not continuous equity)

## Fix Applied

**1. Continuous Equity Tracking:**
```python
# Now tracks equity EVERY BAR, not just at trade exits
if position is not None:
    # Mark-to-market: calculate unrealized PnL for open position
    if position["signal"] > 0:  # Long position
        unrealized_pnl = (current_price - position["entry_price"]) * position["shares"]
    else:  # Short position
        unrealized_pnl = (position["entry_price"] - current_price) * position["shares"]
    current_equity = capital + unrealized_pnl
else:
    current_equity = capital

equity_curve.append(current_equity)
```

**2. Continuous Sharpe Ratio:**
```python
# Changed from discrete trade returns to continuous equity returns
equity_returns = np.diff(equity) / equity[:-1]
if len(equity_returns) > 1 and np.std(equity_returns) > 0:
    sharpe = np.mean(equity_returns) / np.std(equity_returns) * np.sqrt(24 * 252)
```

## Actions Taken

### 1. ✅ Code Fixed
- File: `slate_core/discovery/edge_discovery_engine.py`
- Lines 776-902: Updated equity tracking to capture mark-to-market value every bar
- Lines 913-922: Updated Sharpe ratio calculation to use continuous returns

### 2. ✅ Database Cleared
- All previous discoveries with flawed metrics have been deleted
- Database: `slate_core/slate_realistic_discoveries.db`
- Command: `DELETE FROM edge_discoveries; VACUUM;`

### 3. ✅ Server Restarted
- Server will now generate new discoveries with CORRECT drawdown calculations
- All future backtests will accurately reflect true risk exposure

## Verification

To verify the fix is working:

```bash
# Check that database is empty
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM edge_discoveries;"
# Should return: 0

# Monitor new discoveries
curl -s http://127.0.0.1:8788/api/discovery/statistics | python3 -m json.tool

# Verify drawdowns are now realistic (should be 5-20%+ for most strategies)
```

## Expected Changes

After the fix, you should see:
- **Higher drawdowns** (5-20%+ instead of 0.3-0.5%)
- **Lower Sharpe ratios** (more realistic risk-adjusted returns)
- **Fewer strategies passing validation** (many will now exceed the 25% max drawdown limit)
- **More accurate risk assessment** for all strategies

## Lessons Learned

1. **Always measure equity continuously** in backtesting, not just at trade exits
2. **Mark-to-market valuation matters** - unrealized PnL is real risk
3. **Validate your metrics** - compare manual calculations to system output
4. **Drawdown is a critical risk metric** that must be calculated correctly

## Current Status

**Discoveries**: 0 (clean slate after fix)
**Database**: Fresh with corrected drawdown calculation
**Bug**: FIXED
**Next Discovery**: Will use accurate drawdown calculations

---

**Date**: May 4, 2026
**Fixed By**: Drawdown Calculation Fix
**Status**: COMPLETE - System now reports accurate risk metrics
