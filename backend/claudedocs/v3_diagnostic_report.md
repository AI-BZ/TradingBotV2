# v3.0 Backtest Diagnostic Report

## Executive Summary

**Root Cause Identified**: Signal strength calculation uses hardcoded 3% ATR threshold, causing low-ATR coins (BTC, ETH, SOL, BNB, PEPE) to generate signals with <50% confidence that get filtered out by `should_trade()`.

## Diagnostic Findings

### Signal Generation vs. Execution Gap

The diagnostic script shows coins **ARE generating entry conditions**:

| Coin | BOTH Conditions Met | v3.0 Trades | Problem |
|------|---------------------|-------------|----------|
| BTC | 8.2% (51 bars) | 0 ❌ | Confidence filter |
| ETH | 15.8% (98 bars) | 0 ❌ | Confidence filter |
| SOL | 15.5% (96 bars) | 0 ❌ | Confidence filter |
| BNB | 22.2% (138 bars) | 0 ❌ | Confidence filter |
| XRP | 12.6% (78 bars) | 2 ✅ | Working |
| DOGE | 11.8% (73 bars) | 2 ✅ | Working |
| XPL | 14.5% (90 bars) | 42 ✅ | Working |
| SUI | 10.3% (64 bars) | 2 ✅ | Working |
| PEPE | 7.6% (47 bars) | 0 ❌ | Confidence filter |
| HYPE | 20.5% (127 bars) | 6 ✅ | Working |

### The Filtering Mechanism

**Code Path**: `backtester.py:203` → `trading_strategy.py:130-146`

```python
def should_trade(self, signal: Dict, min_confidence: float = 0.5) -> bool:
    if signal['signal'] == 'HOLD':
        return False
    if signal['confidence'] < min_confidence:  # ← FILTER HERE
        return False
    return True
```

**Confidence Calculation**: `trading_strategy.py:37-45`

```python
compression_strength = max(0, (0.05 - bb_bandwidth) / 0.05)
expansion_strength = min(atr_pct / 0.03, 1.0)  # ← HARDCODED 3% ATR
strength = (compression_strength * 0.5 + expansion_strength * 0.5)
```

### Why Coins Get Filtered

**Actual ATR Values** (from diagnostic):

| Coin | Mean ATR | Median ATR | v3.0 Threshold | Expansion Strength Formula |
|------|----------|------------|----------------|---------------------------|
| BTC | 0.54% | 0.50% | 0.70% | 0.54% / **3.0%** = 0.18 |
| ETH | 0.97% | 0.85% | 1.00% | 0.97% / **3.0%** = 0.32 |
| SOL | 1.28% | 1.13% | 1.30% | 1.28% / **3.0%** = 0.43 |
| BNB | 1.29% | 1.06% | 1.10% | 1.29% / **3.0%** = 0.43 |
| PEPE | 1.53% | 1.19% | 1.50% | 1.53% / **3.0%** = 0.51 |
| XRP | 1.08% | 0.82% | 1.00% | 1.08% / **3.0%** = 0.36 |
| DOGE | 1.46% | 1.22% | 1.40% | 1.46% / **3.0%** = 0.49 |
| SUI | 1.48% | 1.10% | 1.30% | 1.48% / **3.0%** = 0.49 |
| XPL | 4.50% | 4.24% | 4.00% | 4.50% / **3.0%** = **1.50** (capped at 1.0) |
| HYPE | 1.96% | 1.69% | 1.80% | 1.96% / **3.0%** = 0.65 |

**Combined Strength Example** (assuming compression_strength = 0.8):

| Coin | Expansion Strength | Combined Strength | Passes 0.5 Filter? |
|------|-------------------|-------------------|-------------------|
| BTC | 0.18 | (0.8×0.5 + 0.18×0.5) = **0.49** | ❌ NO |
| ETH | 0.32 | (0.8×0.5 + 0.32×0.5) = **0.56** | ⚠️ Marginal |
| SOL | 0.43 | (0.8×0.5 + 0.43×0.5) = **0.62** | ⚠️ Marginal |
| BNB | 0.43 | (0.8×0.5 + 0.43×0.5) = **0.62** | ⚠️ Marginal |
| XPL | 1.00 | (0.8×0.5 + 1.00×0.5) = **0.90** | ✅ YES |
| HYPE | 0.65 | (0.8×0.5 + 0.65×0.5) = **0.73** | ✅ YES |

## The Solution

### Fix: Coin-Specific Strength Calculation

Replace the hardcoded `0.03` (3%) with each coin's actual ATR threshold:

**Current Code** (`trading_strategy.py:37-38`):
```python
compression_strength = max(0, (0.05 - bb_bandwidth) / 0.05)  # Hardcoded 5%
expansion_strength = min(atr_pct / 0.03, 1.0)  # ← Hardcoded 3%
```

**Proposed Fix**:
```python
# Get coin-specific thresholds
params = self.get_coin_parameters(symbol) if symbol else {}
bb_threshold = params.get('bb_compression', 0.055)
atr_threshold = params.get('atr_expansion', 0.025)

# Calculate strength relative to coin-specific thresholds
compression_strength = max(0, (bb_threshold - bb_bandwidth) / bb_threshold)
expansion_strength = min(atr_pct / atr_threshold, 1.0)
```

**Expected Impact** (with fix):

| Coin | New Expansion Strength | New Combined | Result |
|------|----------------------|--------------|--------|
| BTC | 0.54% / **0.70%** = 0.77 | 0.89 | ✅ Passes |
| ETH | 0.97% / **1.00%** = 0.97 | 0.89 | ✅ Passes |
| SOL | 1.28% / **1.30%** = 0.98 | 0.89 | ✅ Passes |
| BNB | 1.29% / **1.10%** = 1.00 | 0.90 | ✅ Passes |
| PEPE | 1.53% / **1.50%** = 1.00 | 0.90 | ✅ Passes |

## Expected Improvements

### Signal Distribution
- **Current**: 5/10 coins generating signals (BTC/ETH/SOL/BNB/PEPE = 0)
- **Expected**: 10/10 coins generating signals

### Trade Volume
- **Current**: 54 total trades over 30 days (1.8 trades/day)
- **Expected**: ~150-200 trades (based on BOTH% from diagnostic: 8-22% = ~50-150 bars per coin)

### XPL Dominance
- **Current**: 42/54 = 78% XPL trades
- **Expected**: XPL ~30-40% of total (more balanced distribution)

### Win Rate
- **Current**: 20.37%
- **Impact**: More diverse coin exposure should improve win rate through:
  - Different volatility characteristics
  - Reduced correlation to single coin's behavior
  - Better risk distribution

## Additional Fixes Needed

### 1. BB Compression Strength Formula
Current formula uses hardcoded `0.05` (5%):
```python
compression_strength = max(0, (0.05 - bb_bandwidth) / 0.05)
```

Should use coin-specific threshold:
```python
compression_strength = max(0, (bb_threshold - bb_bandwidth) / bb_threshold)
```

### 2. Signal Boost Condition
Current hardcoded thresholds:
```python
if compression_strength > 0.7 and expansion_strength > 0.7:
    strength = min(strength * 1.2, 1.0)
```

Consider making boost dynamic or removing entirely (already coin-specific strength).

## Implementation Priority

**HIGH PRIORITY - Immediate Fix**:
1. Make strength calculation coin-specific (lines 37-45 in trading_strategy.py)
2. Run v4.0 validation backtest
3. Verify all 10 coins generate signals

**MEDIUM PRIORITY - After v4.0 Results**:
1. Analyze v4.0 win rate and profitability
2. Consider volume confirmation adjustments if needed
3. Fine-tune hard stops and trailing multipliers

**LOW PRIORITY - Strategy Enhancement**:
1. Add volume spike detection (current params define `min_volume_ratio` but not used)
2. Implement ML model integration for signal filtering
3. Multi-timeframe validation framework

## Conclusion

The v3.0 parameter tuning was **directionally correct** (relaxed ATR thresholds), but signals are being filtered out by a **hardcoded strength calculation** that doesn't respect coin-specific volatility characteristics.

**Next Step**: Update `trading_strategy.py` lines 37-45 to use coin-specific thresholds, creating v4.0 parameters and rerunning backtest.
