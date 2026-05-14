# Volume Imbalance Strategy Optimization

## Optimization Framework Setup

### Objective
Find optimal parameters for the Volume Imbalance strategy that maximize risk-adjusted returns while minimizing drawdown, reproducing and improving upon the paper's optimization results.

### Parameter Space (Based on Paper's Figure 4)

| Parameter | Range | Values Tested |
|-----------|-------|---------------|
| **VI_Period** | 6-24 | 6, 9, 12, 15, 18, 21, 24 |
| **VI_Threshold** | 0.15-0.50 | 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50 |
| **Stop_Loss_Pct** | 1.0%-3.5% | 1.0%, 1.5%, 2.0%, 2.5%, 3.0%, 3.5% |
| **Take_Profit_Pct** | 2.0%-8.0% | 2.0%, 3.0%, 4.0%, 5.0%, 6.0%, 7.0%, 8.0% |
| **Trailing_Stop_Pct** | 0.5%-3.0% | 0.5%, 1.0%, 1.5%, 2.0%, 2.5%, 3.0% |

**Total Search Space**: 7 × 8 × 6 × 7 × 6 = **14,112 combinations**

### Optimization Method: Smart Grid Search

Two-stage optimization for efficiency:

#### Stage 1: Coarse Grid Search
- Tests broader parameter ranges
- Identifies promising regions
- ~4,000-6,000 combinations

#### Stage 2: Fine Grid Search
- Focuses around top 10 parameters from Stage 1
- Refines with smaller increments
- ~1,000-2,000 additional combinations

**Advantages**:
- More efficient than exhaustive search
- Better than random search
- No bias from previous runs
- Parallelizable

### Multi-Objective Scoring

The optimization uses a **composite score** that balances:

```python
score = total_return × (1 - max_drawdown × 2)
```

**Components**:
1. **Total Return**: Primary objective (maximize)
2. **Max Drawdown**: Risk penalty (minimize)
3. **Profit Factor**: Reward risk-adjusted winners
4. **Sharpe Ratio**: Reward consistent performers
5. **Win Rate**: Consider (but not primary)

**Scoring Logic**:
- Negative returns get negative scores (heavily penalized)
- Positive returns rewarded proportional to gain
- Drawdown doubles as penalty factor (2x weight)
- Best parameters have high return + low drawdown

### Parallel Processing

- Uses **4 workers** for parallel execution
- Processes multiple parameter combinations simultaneously
- Reduces computation time by ~75%

### Performance Metrics Tracked

For each parameter combination, we calculate:

1. **Return Metrics**
   - Total Return (%)
   - Final Equity ($)
   - Total Profit ($)

2. **Risk Metrics**
   - Maximum Drawdown (%)
   - Number of Trades
   - Average Win/Loss amounts

3. **Risk-Adjusted Metrics**
   - Sharpe Ratio
   - Profit Factor
   - Win Rate (%)
   - Payoff Ratio

### Expected Optimization Time

- **Stage 1** (coarse): ~15-20 minutes
- **Stage 2** (fine): ~5-10 minutes
- **Total**: ~20-30 minutes

### Output Files

1. **optimization_results.csv** - All 14,112 combinations with metrics
2. **optimization_summary.txt** - Top 10 best parameters
3. **optimization_visualizations.png** - 6-panel analysis:
   - Return vs Drawdown scatter
   - VI Period distribution (profitable)
   - VI Threshold distribution (profitable)
   - Stop Loss impact analysis
   - Take Profit impact analysis
   - Profit Factor histogram
   - Top 20 comparison chart
4. **optimized_equity_curve.png** - Equity curve with best parameters
5. **optimized_statistics.txt** - Detailed trade stats for best params

### Optimization Strategy

#### Why Smart Grid Search?

1. **Exhaustive Search**: 14,112 combinations = feasible
2. **Bayesian Optimization**: Not ideal - complex parameter interactions
3. **Random Search**: Less efficient, misses promising regions
4. **Genetic Algorithms**: Overkill for this search space

#### Search Priorities

**Primary**: Find profitable parameter combinations
**Secondary**: Optimize risk-adjusted returns
**Tertiary**: Refine for stability (consistency)

### Success Criteria

Optimization successful if:
1. Find parameters with **positive return** (baseline: -5.94%)
2. **Maximize return** while keeping drawdown < 15%
3. **Profit factor** > 1.2 (wins outweigh losses)
4. **Consistent** across multiple parameter sets (not just luck)

### Comparison with Paper

The paper shows optimization reaching **Profit Factor > 2.0**. We aim to:
- Reproduce similar findings
- Validate on our data (different time period)
- Potentially exceed with modern optimization techniques

### Monitoring Progress

```
Stage 1: Testing coarse grid...
  Progress: XXXX/6000 (XX%)

Top performers emerge...

Stage 2: Fine-tuning around best 10...
  Progress: XXXX/2000 (XX%)

Final analysis...
```

---

**Status**: Optimization running in background
**Expected completion**: 20-30 minutes
**Next**: Analyze results and report findings
