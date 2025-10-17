# Continuous Optimization Plan - v5.0 to v∞

**Start Time**: 2025-10-17 00:29 KST
**Deadline**: 2025-10-17 06:00 KST
**Duration**: ~5.5 hours
**Status**: 🔄 **ACTIVE**

---

## 🎯 Objective

**Automatically improve trading strategy through iterative backtesting and optimization until 06:00 KST**

Starting from v5.0 (Dynamic Hard Stop), continuously:
1. Run backtest (1-month for speed)
2. Analyze results (per-coin performance, win rate, drawdown)
3. Identify improvements (exclude losers, adjust stops, tune parameters)
4. Create new version (v6.0, v7.0, ...)
5. Repeat until deadline

---

## 🔄 Current Running Processes

### 1. v5.0 Multi-Timeframe Backtest
- **Status**: 🔄 Running (1-month test in progress)
- **Started**: 00:01:53 KST
- **Expected Completion**: ~00:08:00 KST (6-7 minutes)
- **Purpose**: Comprehensive validation of Dynamic Hard Stop across 4 timeframes
- **Process ID**: d4fc7d
- **Log**: `v5_multi_timeframe_output.log`

**Current Progress**:
```
✅ Data loaded for all 10 coins (721 candles each)
🔄 Backtest simulation in progress
📊 1-month test: 30% complete (216/721 bars processed)
💰 Current balance: $8,957.71 (from $10,000 start)
```

### 2. Continuous Optimization Monitor
- **Status**: 👀 Monitoring v5.0 completion
- **Started**: 00:29:06 KST
- **Function**: Waits for v5.0 → launches auto-optimization
- **Process ID**: 8ee0ec
- **Log**: `continuous_optimization.log`

**Monitoring Strategy**:
- Checks v5.0 log every 60 seconds
- Max wait: 3 hours
- Auto-launches optimization on completion
- Logs progress every 10 minutes

### 3. Auto-Optimization System (Waiting)
- **Status**: ⏳ Waiting for v5.0 completion
- **Launch Trigger**: v5.0 multi-timeframe done
- **Script**: `run_continuous_optimization.py`
- **Will Run Until**: 06:00 KST

---

## 📋 Optimization Algorithm

### Phase 1: Quick Validation (6-7 mins per version)
```python
# 1-month backtest for fast iteration
symbols = active_coins  # Start with 10, may exclude some
params = {
    'hard_stop_atr_multiplier': 2.0,  # Will be adjusted
    'use_dynamic_hard_stop': True
}

results = run_backtest(symbols, params)
```

### Phase 2: Per-Coin Analysis
```python
for coin in results:
    analyze_metrics = {
        'total_pnl': coin.pnl,
        'win_rate': coin.wins / coin.trades,
        'avg_pnl_per_trade': coin.pnl / coin.trades,
        'max_loss': max(coin.losses)
    }
```

### Phase 3: Improvement Identification

**Strategy A: Exclude Worst Performers**
```python
if coin.pnl < 0:
    # Losing coin detected
    if coin == worst_performer:
        exclude_list.add(coin)
        # v6.0: 9 coins (XPL excluded?)
        # v7.0: 8 coins (XPL + another excluded?)
```

**Strategy B: Adjust Hard Stop Multiplier**
```python
if max_drawdown > 20%:
    # Too much risk
    hard_stop_multiplier -= 0.2  # Tighten stops
    # v6.0: 2.0 → 1.8
elif max_drawdown < 10% and win_rate < 35%:
    # Too conservative
    hard_stop_multiplier += 0.2  # Widen stops
    # v6.0: 2.0 → 2.2
```

**Strategy C: Confidence Threshold**
```python
if total_trades < 150:
    # Too few trades
    recommendation = "Lower confidence threshold from 0.5 to 0.4"
elif total_trades > 400:
    # Too many trades
    recommendation = "Raise confidence threshold from 0.5 to 0.6"
```

### Phase 4: Version Creation & Testing
```python
new_version = increment_version(current_version)
# v5.0 → v6.0 → v7.0 → ...

new_params = apply_improvements(current_params, improvements)
new_symbols = exclude_coins(current_symbols, losers)

results = run_backtest(new_symbols, new_params)
```

### Phase 5: Best Version Tracking
```python
# Composite score (weighted metrics)
score = (
    total_return * 0.4 +
    (win_rate - 30) * 0.3 +
    sharpe * 10 * 0.2 +
    (profit_factor - 1) * 20 * 0.1
)

if score > best_score:
    best_version = current_version
    best_score = score
```

---

## 🎯 Expected Improvement Sequence

### v5.0 → v6.0 (First Iteration)

**Likely Scenario Based on v5.0 1-month Validation**:
- v5.0 Results (known):
  - Return: +3.30%
  - Win Rate: 37.92%
  - Total Trades: 240
  - XPL: 32 trades (13.3%)

**Expected v6.0 Improvements**:
1. **XPL Analysis**: If XPL shows negative P&L or very low win rate
   - Action: **Exclude XPL** from v6.0
   - New symbols: 9 coins (BTC, ETH, SOL, BNB, XRP, DOGE, SUI, PEPE, HYPE)

2. **Hard Stop Adjustment**: Based on drawdown
   - If DD > 20%: Tighten to 1.8x ATR
   - If DD < 10%: Widen to 2.2x ATR

3. **Expected v6.0**:
   - Symbols: 9 (XPL excluded)
   - Hard Stop: 1.8-2.2x ATR
   - Target: Win Rate > 40%, Return > 4%

### v6.0 → v7.0 (Second Iteration)

**Likely Scenario**:
- v6.0 tested with 9 coins
- Identify next weakest performer (PEPE? HYPE?)
- Further fine-tune hard stop multiplier

**Expected v7.0**:
- Symbols: 8-9 coins
- Hard Stop: Fine-tuned based on v6.0 results
- Target: Stable performance, high win rate

### v7.0 → v8.0+ (Subsequent Iterations)

**Optimization Focus**:
- Fine-tune confidence thresholds
- Optimize coin selection (6-9 coins optimal?)
- Balance risk vs return
- Maximize Sharpe ratio

**Stop Conditions**:
1. Time limit: 06:00 KST
2. Optimal balance found (8-9 iterations expected)
3. No more improvements possible

---

## 📊 Success Metrics

### Per-Version Tracking
```json
{
  "version": "6.0",
  "total_return": 4.5,
  "win_rate": 40.2,
  "total_trades": 220,
  "profit_factor": 1.15,
  "sharpe": 0.68,
  "max_drawdown": 15.3,
  "composite_score": 8.2,
  "symbols": ["BTC/USDT", "ETH/USDT", ...],
  "excluded": ["XPL/USDT"],
  "params": {
    "hard_stop_atr_multiplier": 1.8
  }
}
```

### Best Version Selection
- **Primary**: Highest composite score
- **Secondary**: Best risk-adjusted return (Sharpe ratio)
- **Tertiary**: Highest win rate with stable drawdown

---

## 🗂️ Output Files

### 1. Optimization History
**File**: `claudedocs/continuous_optimization_history.json`
```json
{
  "deadline_kst": "2025-10-17T06:00:00",
  "best_version": {
    "version": "7.0",
    "composite_score": 9.5,
    "total_return": 5.2,
    "win_rate": 42.1
  },
  "excluded_symbols": ["XPL/USDT", "PEPE/USDT"],
  "versions": [
    { "version": "5.0", "score": 7.8 },
    { "version": "6.0", "score": 8.3 },
    { "version": "7.0", "score": 9.5 }
  ]
}
```

### 2. Continuous Optimization Log
**File**: `continuous_optimization.log`
- Real-time progress of all iterations
- Per-version results
- Improvement decisions
- Final summary

### 3. v5.0 Multi-Timeframe Results
**File**: `v5_multi_timeframe_output.log`
- Complete 4-timeframe validation
- Per-coin detailed analysis
- Baseline for all improvements

---

## ⚠️ Risk Management

### Safeguards
1. **Minimum Coin Count**: Never go below 6 coins
2. **Stop Multiplier Bounds**: Keep between 1.5x and 3.0x ATR
3. **Confidence Threshold Bounds**: Keep between 0.3 and 0.7
4. **Validation Required**: Every version must complete 1-month backtest

### Fallback Strategy
- If all improvements fail: Revert to best previous version
- If time runs out: Return best version found so far
- If errors occur: Log and continue with next iteration

---

## 🏁 Expected Outcome (by 06:00 KST)

### Optimistic Scenario
- **Iterations**: 8-10 versions tested (v5.0 → v13.0)
- **Best Version**: v8.0 or v9.0
- **Improvements**:
  - Optimal coin selection: 7-8 coins
  - Fine-tuned hard stops: 1.8-2.2x ATR
  - Win rate: 42-45%
  - Return: 5-6% (1-month)
  - Sharpe: 0.7-0.8
  - Drawdown: <15%

### Realistic Scenario
- **Iterations**: 5-7 versions tested (v5.0 → v11.0)
- **Best Version**: v7.0 or v8.0
- **Improvements**:
  - XPL excluded
  - 1-2 other weak coins excluded
  - Hard stop optimized: 1.8-2.0x ATR
  - Win rate: 38-42%
  - Return: 4-5% (1-month)

### Conservative Scenario
- **Iterations**: 3-4 versions tested (v5.0 → v8.0)
- **Best Version**: v6.0
- **Improvements**:
  - XPL excluded
  - Minor hard stop adjustment
  - Win rate: 38-40%
  - Return: 3.5-4.5%

---

## 📝 Key Decisions to Watch

### XPL Exclusion
- **Critical Question**: Does XPL drag down overall performance?
- **Decision Point**: v6.0 creation
- **Impact**: If XPL is consistently losing, excluding it could improve return by 1-2%

### Hard Stop Multiplier
- **Current**: 2.0x ATR
- **Optimization Range**: 1.5x - 2.5x
- **Trade-off**: Tighter = fewer losses but lower win rate, Wider = higher win rate but bigger losses

### Coin Count Optimization
- **Start**: 10 coins
- **Expected End**: 7-9 coins
- **Hypothesis**: 7-9 profitable coins better than 10 mixed-performance coins

---

## 🔍 Monitoring Commands

Check progress:
```bash
# v5.0 multi-timeframe progress
tail -f v5_multi_timeframe_output.log | grep -E "TIMEFRAME|Progress|Results"

# Continuous optimization progress
tail -f continuous_optimization.log | grep -E "ITERATION|Best|Excluded|Score"

# Monitor process
tail -f continuous_optimization.log
```

Check if complete:
```bash
# Check for completion
grep -E "OPTIMIZATION COMPLETE|BEST VERSION" continuous_optimization.log

# Check version history
cat claudedocs/continuous_optimization_history.json | jq '.versions[] | {version, score: .composite_score}'
```

---

## 🎯 Success Criteria

By 06:00 KST, we should achieve:

✅ **Minimum**:
- [ ] v5.0 multi-timeframe complete
- [ ] At least 3 optimization iterations (v5.0 → v8.0)
- [ ] XPL inclusion/exclusion decision made with data
- [ ] Best version identified and documented

✅ **Target**:
- [ ] 5-7 optimization iterations (v5.0 → v11.0)
- [ ] Optimal coin count identified (7-9 coins)
- [ ] Hard stop multiplier optimized
- [ ] Win rate improved to 40%+
- [ ] Return improved to 4-5%+

✅ **Stretch**:
- [ ] 8-10 optimization iterations
- [ ] Win rate 42-45%
- [ ] Return 5-6%+
- [ ] Sharpe ratio 0.7-0.8
- [ ] Comprehensive multi-timeframe validation of best version

---

**Status**: 🚀 **SYSTEM ACTIVE - OPTIMIZATION IN PROGRESS**

**Next Milestone**: v5.0 Multi-Timeframe Complete (~00:08:00 KST)
**Then**: Automatic launch of continuous optimization loop

**Estimated Completion**: 05:30-06:00 KST
**Final Report**: `claudedocs/continuous_optimization_history.json`
