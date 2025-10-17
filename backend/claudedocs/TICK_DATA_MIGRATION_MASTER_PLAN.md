# 🎯 TICK DATA MIGRATION - MASTER EXECUTION PLAN

**Mission**: Migrate 100% of trading system from candle-based to tick-based data architecture

**Zero Tolerance**: NO candles, NO exceptions, NO shortcuts

---

## 📊 CURRENT STATE ANALYSIS

### Critical Findings
**❌ CURRENT PROBLEM**: System uses 1-hour candles everywhere
- **Fatal Flaw**: Signals based on 1h candles = 3600-second delay
- **Consequence**: Missing 99.9% of price movements (tick updates ~100ms)
- **Impact**: Cannot capture volatility breakouts in real-time

### Files Using Candle Data (COMPLETE INVENTORY)

#### 🔴 **CRITICAL - Core Trading Components**

1. **binance_client.py** (Lines: 88-127)
   - `get_klines()` function - PRIMARY DATA SOURCE
   - Used by ALL other modules
   - Returns OHLCV candle data
   - **Migration Priority**: HIGHEST

2. **backtester.py** (Lines: 72-151, 434-625)
   - `load_historical_data()` - Loads candles for backtest
   - `run_backtest()` - Iterates through candles
   - **Requires**: Tick-based backtest engine

3. **trading_strategy.py** (Lines: 224-301, 454-517)
   - `generate_signal()` - Expects OHLCV DataFrame
   - `analyze_technical_signals()` - Uses candle-derived indicators
   - **Requires**: Tick-based indicator calculation

4. **technical_indicators.py** (ALL FUNCTIONS)
   - All indicator functions expect price arrays from candles
   - RSI, MACD, BB, ATR - all candle-based
   - **Requires**: Complete rewrite for tick data

#### 🟡 **IMPORTANT - Real-Time Trading**

5. **realtime_tick_trader.py** (Lines: 185-186)
   - ⚠️ **CONTRADICTION**: Named "tick trader" but uses candles!
   - `generate_and_execute_signals()` fetches 1m candles
   - **Current**: Hybrid (tick stream + candle analysis)
   - **Target**: Pure tick-based analysis

6. **auto_trader.py** (Lines: 85-93)
   - `get_historical_data()` - Fetches candles
   - Used for initial strategy setup

7. **paper_trader.py** (Lines: 95-102)
   - `get_historical_data()` - Fetches candles
   - Used for paper trading simulation

#### 🟢 **SUPPORTING - ML & Optimization**

8. **ml_engine.py** (Lines: 38-200)
   - All ML training expects OHLCV DataFrame
   - Feature engineering based on candle data
   - **Requires**: Tick-based feature extraction

9. **ai_trading_system.py** (Lines: 135, 179, 340)
   - ML model training uses candles
   - Strategy validation uses candles

10. **ai_strategy_manager.py** (Line: 275)
    - Strategy evaluation uses candles

11. **strategy_optimizer.py** (Line: 235)
    - Parameter optimization uses candles

#### 📁 **DATA COLLECTION**

12. **data_collector.py** (Lines: 59-160)
    - Historical OHLCV downloader
    - **Status**: Keep for historical analysis
    - **Migration**: Add tick data collection

13. **data_streamer.py** (Lines: 69-113)
    - ✅ **ALREADY TICK-BASED**: Real-time WebSocket
    - **Status**: Reference implementation
    - **Action**: Expand and integrate

#### 🛠️ **UTILITIES**

14. **main.py** (Lines: 138-148)
    - API endpoint returns candles
    - **Requires**: Add tick data endpoint

15. **backtest_engine.py** (Lines: 121-232)
    - Legacy backtest engine
    - Uses OHLCV data
    - **Replace**: With tick-based backtester

---

## 🏗️ TICK DATA ARCHITECTURE DESIGN

### 1. Data Collection Layer

#### A. WebSocket Tick Collector
```python
class TickDataCollector:
    """
    Real-time tick collection via Binance WebSocket

    Features:
    - Multi-symbol concurrent streams
    - ~100ms update frequency
    - Trade-level data (not just aggregated tickers)
    - Automatic reconnection with exponential backoff
    """

    Stream Types:
    1. Trade Stream: Individual trades (@trade)
       - Price, quantity, timestamp, buyer/seller info
       - TRUE tick-by-tick data

    2. Agg Trade Stream: Aggregated trades (@aggTrade)
       - Slightly aggregated but still ~100ms
       - Lower bandwidth, still real-time

    3. Kline Stream: Mini-candles (@kline_1s, @kline_1m)
       - ONLY for transition period
       - Eventually remove completely
```

#### B. Tick Data Storage
```python
class TickDataStore:
    """
    Efficient tick data storage

    Format Options:
    1. In-Memory (Active Trading):
       - Circular buffer (last 10,000 ticks per symbol)
       - Fast access for indicator calculation

    2. Database (Historical):
       - TimescaleDB (PostgreSQL extension for time-series)
       - Partitioned by symbol + time
       - Compressed for efficiency

    3. File Storage (Backup):
       - Parquet files (columnar, compressed)
       - Daily partitions
    """

    Tick Schema:
    - timestamp: int64 (milliseconds)
    - symbol: string
    - price: float64
    - volume: float64
    - is_buyer_maker: bool
    - trade_id: int64
```

### 2. Indicator Calculation Layer

#### A. Tick-Based Technical Indicators
```python
class TickBasedIndicators:
    """
    Calculate indicators from raw tick data

    Approach: Time-weighted moving windows
    - Not bar-based (no OHLC assumption)
    - Exponentially weighted for recent ticks
    - Volume-weighted where appropriate
    """

    Core Indicators (Tick Version):

    1. VWAP (Volume Weighted Average Price):
       - Sum(price × volume) / Sum(volume)
       - Rolling window: last N ticks or last T seconds

    2. Volatility (Tick-based):
       - Standard deviation of price changes
       - Per-tick or per-second basis
       - NOT bar-to-bar ATR

    3. Momentum:
       - Price change over last N ticks
       - Rate of price change (velocity)

    4. Bollinger Bands (Tick version):
       - VWAP ± (k × tick volatility)
       - Adaptive bands based on tick frequency

    5. Volume Profile:
       - Volume distribution at each price level
       - Real-time order book depth

    6. Tick Velocity:
       - Trades per second
       - Price movement per tick
       - Acceleration/deceleration
```

#### B. Signal Generation (Tick-Based)
```python
class TickBasedStrategy:
    """
    Two-Way Volatility Strategy - Tick Version

    Entry Conditions:
    1. Volatility Compression:
       - Bollinger bandwidth < threshold
       - Measured in tick volatility

    2. Volatility Expansion:
       - Tick volatility increasing
       - Measured as σ(price) per second

    3. Volume Surge:
       - Trades/second > average
       - Large trades detected

    4. Breakout Confirmation:
       - Price momentum > threshold
       - NOT candle body - actual tick momentum
    """

    Advantages:
    - Detect breakouts in milliseconds
    - No 1-hour lag
    - Capture intrabar volatility
    - React to large trades instantly
```

### 3. Backtesting Layer

#### A. Tick-Based Backtest Engine
```python
class TickBacktester:
    """
    Backtest using historical tick data

    Process:
    1. Load tick data from storage
    2. Replay tick-by-tick
    3. Calculate indicators on each tick
    4. Generate signals in real-time simulation
    5. Execute trades with realistic slippage
    """

    Features:
    - Microsecond-level precision
    - Realistic order execution
    - Slippage modeling based on tick data
    - Fill price = next tick after signal
```

#### B. Performance Comparison
```
BEFORE (1h candles):
- 8,760 data points per year
- Signal delay: up to 3600 seconds
- Miss: 99.9% of price movements

AFTER (tick data @ 100ms):
- ~315,360,000 ticks per year
- Signal delay: 100 milliseconds
- Capture: 100% of price movements
```

### 4. Real-Time Trading Layer

#### A. Tick-Based Live Trader
```python
class TickBasedLiveTrader:
    """
    Live trading using tick stream

    Flow:
    1. Subscribe to tick streams (all symbols)
    2. Update indicators on each tick
    3. Check signals every tick
    4. Execute orders immediately
    5. Update trailing stops on each tick
    """

    Optimization:
    - Update indicators incrementally (not recalculate)
    - Async processing (don't block tick stream)
    - Queue-based order execution
```

---

## 📋 DETAILED MIGRATION CHECKLIST

### Phase 1: Foundation (Days 1-3)

#### ✅ Task 1.1: Create Tick Data Collection
**Files to Create**:
- `tick_data_collector.py` - New WebSocket collector
- `tick_data_store.py` - Storage engine
- `tick_buffer.py` - In-memory circular buffer

**Implementation**:
```python
# tick_data_collector.py
class TickDataCollector:
    async def subscribe_trades(self, symbol: str):
        """Subscribe to trade stream (true tick data)"""
        stream = f"{symbol.lower()}@trade"
        # WebSocket implementation

    async def on_trade(self, trade_data: dict):
        """Process individual trade tick"""
        tick = {
            'timestamp': trade_data['T'],
            'symbol': trade_data['s'],
            'price': float(trade_data['p']),
            'volume': float(trade_data['q']),
            'is_buyer_maker': trade_data['m']
        }
        await self.tick_buffer.add(tick)
```

#### ✅ Task 1.2: Create Tick-Based Indicators
**Files to Create**:
- `tick_indicators.py` - All indicators rewritten for ticks

**Migration**:
```
OLD: technical_indicators.py (KEEP for reference)
NEW: tick_indicators.py

Changes:
- calculate_rsi() → calculate_tick_rsi()
  Input: List of tick prices (NOT OHLC)
  Window: Last N ticks or T seconds

- calculate_bollinger_bands() → calculate_tick_bollinger_bands()
  Middle band: VWAP (not SMA)
  Std dev: Tick price volatility

- calculate_atr() → calculate_tick_volatility()
  No "true range" concept
  Use: σ(price_changes) per second
```

#### ✅ Task 1.3: Update Binance Client
**File**: `binance_client.py`

**Changes**:
```python
# ADD NEW METHODS:
async def subscribe_trade_stream(self, symbol: str, callback):
    """Subscribe to trade stream (tick data)"""
    stream_name = f"{symbol.lower()}@trade"
    # Implementation

async def get_historical_trades(self, symbol: str, start_time: int, limit: int = 1000):
    """Fetch historical trade data (ticks)"""
    # Uses Binance /api/v3/aggTrades endpoint

# KEEP OLD METHOD (for transition):
async def get_klines(...):
    """DEPRECATED - Use tick data instead"""
    # Keep for gradual migration
```

**Lines to Modify**:
- Lines 88-127: Add deprecation warning to `get_klines()`
- Add new tick stream methods after line 147

### Phase 2: Core Migration (Days 4-7)

#### ✅ Task 2.1: Migrate Trading Strategy
**File**: `trading_strategy.py`

**Line-by-Line Changes**:

Line 224-301: `generate_signal()` function
```python
# BEFORE:
def generate_signal(self, data: pd.DataFrame, indicators: Dict, symbol: str = None) -> Dict:
    # Expects OHLCV DataFrame

# AFTER:
def generate_signal(self, tick_buffer: TickBuffer, symbol: str = None) -> Dict:
    """Generate signal from tick data"""
    # Calculate indicators from tick buffer
    indicators = TickIndicators.calculate_all(tick_buffer)
    # Rest of logic remains similar
```

Line 102-223: `analyze_technical_signals()`
```python
# CHANGE:
# Remove dependency on 'bb' dict from candle-based calculation
# Use tick-based Bollinger calculation

# OLD:
bb_data = indicators['bb']  # From candle-based calculation

# NEW:
bb_data = TickIndicators.calculate_tick_bollinger_bands(
    prices=tick_buffer.get_prices(lookback=1000),
    volumes=tick_buffer.get_volumes(lookback=1000)
)
```

#### ✅ Task 2.2: Migrate Backtester
**File**: `backtester.py`

**Complete Rewrite Required**:
- Lines 72-151: `load_historical_data()` → `load_historical_ticks()`
- Lines 153-186: `analyze_bar()` → `analyze_tick()`
- Lines 434-625: `run_backtest()` → Complete tick-based loop

**New Implementation**:
```python
async def load_historical_ticks(self, symbol: str, start_date: str, end_date: str):
    """Load tick data from storage"""
    return await self.tick_store.fetch_ticks(symbol, start_date, end_date)

async def run_backtest(self, start_date: str, end_date: str):
    """Tick-by-tick backtest"""
    for symbol in self.symbols:
        ticks = await self.load_historical_ticks(symbol, start_date, end_date)

        tick_buffer = TickBuffer(maxlen=10000)

        for tick in ticks:
            # Add tick to buffer
            tick_buffer.add(tick)

            # Update indicators incrementally
            if len(tick_buffer) >= 100:  # Minimum for indicators
                signal = self.strategy.generate_signal(tick_buffer, symbol)

                # Execute if signal generated
                if signal['signal'] != 'HOLD':
                    self.execute_backtest_trade(signal, symbol)

                # Check trailing stops
                self.check_trailing_stops(symbol, tick['price'], tick['timestamp'])
```

#### ✅ Task 2.3: Fix "Tick Trader" (Currently Uses Candles!)
**File**: `realtime_tick_trader.py`

**Line 185-186: CRITICAL FIX**
```python
# CURRENT (WRONG):
klines = await self.binance_client.get_klines(symbol, '1m', limit=100)
# Then passes candles to strategy

# CORRECTED:
# Strategy should use tick_buffer already maintained by on_tick()
# NO candle fetching needed!

async def generate_and_execute_signals(self, symbol: str, price: float, tick: dict):
    """Generate signals using tick data only"""
    # Get tick buffer for this symbol
    tick_buffer = self.tick_buffers[symbol]

    if len(tick_buffer) < 100:
        return  # Need minimum ticks

    # Generate signal from ticks
    signal = self.strategy.generate_signal(tick_buffer, symbol)

    # Execute
    if signal['signal'] == 'BOTH':
        await self.execute_two_way_entry(symbol, price, signal, tick['timestamp'])
```

### Phase 3: ML & Advanced Features (Days 8-10)

#### ✅ Task 3.1: Migrate ML Engine
**File**: `ml_engine.py`

**Changes**:
- Lines 38-200: All functions expect OHLCV → Change to tick data
- Feature engineering: Extract from tick statistics

**New Features from Ticks**:
```python
def extract_tick_features(tick_buffer: TickBuffer) -> pd.DataFrame:
    """Extract ML features from tick data"""
    features = {
        'vwap': TickIndicators.calculate_vwap(tick_buffer),
        'tick_volatility': TickIndicators.calculate_volatility(tick_buffer),
        'tick_velocity': len(tick_buffer) / tick_buffer.time_span(),
        'volume_surge': tick_buffer.volume_ratio(),
        'momentum': TickIndicators.calculate_momentum(tick_buffer),
        # ... more tick-specific features
    }
    return pd.DataFrame(features, index=[0])
```

#### ✅ Task 3.2: Update Supporting Systems
**Files**:
- `auto_trader.py` (Line 93)
- `paper_trader.py` (Line 102)
- `ai_trading_system.py` (Lines 135, 179, 340)
- `ai_strategy_manager.py` (Line 275)
- `strategy_optimizer.py` (Line 235)

**Pattern**: Replace all `get_klines()` calls
```python
# OLD:
klines = await client.get_klines(symbol, '1h', 100)
data = pd.DataFrame(klines)

# NEW:
ticks = await client.get_recent_ticks(symbol, limit=10000)  # ~100 seconds of data
tick_buffer = TickBuffer(ticks)
```

### Phase 4: Data Pipeline (Days 11-12)

#### ✅ Task 4.1: Enhance Data Collector
**File**: `data_collector.py`

**ADD** (don't remove candle collection):
```python
async def download_historical_ticks(self, symbol: str, start_date: datetime, end_date: datetime):
    """Download historical tick data"""
    # Use Binance /api/v3/aggTrades
    # Store in TimescaleDB or Parquet files

async def download_all_ticks(self, days: int = 30):
    """Download ticks for all symbols"""
    # Parallel download
```

#### ✅ Task 4.2: Upgrade Data Streamer
**File**: `data_streamer.py`

**CURRENT**: Already tick-based! ✅
**ACTION**: Integrate with tick storage
```python
# Add to DataStreamer:
async def save_to_tick_store(self, tick: dict):
    """Save tick to persistent storage"""
    await self.tick_store.insert(tick)
```

### Phase 5: API & Integration (Day 13)

#### ✅ Task 5.1: Update Main API
**File**: `main.py`

**Line 138-148: Add tick endpoint**
```python
@app.get("/api/ticks/{symbol}")
async def get_ticks(symbol: str, limit: int = 1000):
    """Get recent tick data"""
    ticks = await tick_store.fetch_recent(symbol, limit)
    return {"symbol": symbol, "ticks": ticks}

@app.get("/api/klines/{symbol}")
async def get_klines(symbol: str, interval: str = "1h", limit: int = 100):
    """DEPRECATED - Use /api/ticks instead"""
    # Keep for backward compatibility
```

### Phase 6: Testing & Validation (Days 14-15)

#### ✅ Task 6.1: Validation Tests
**Create**: `test_tick_migration.py`

```python
class TestTickMigration:
    """Validate tick-based system"""

    async def test_no_candle_calls(self):
        """CRITICAL: Ensure NO get_klines() calls in live trading"""
        # Static code analysis
        # Grep for get_klines in active trading modules

    async def test_tick_indicator_accuracy(self):
        """Compare tick vs candle indicators"""
        # Should be similar on same data

    async def test_backtest_speed(self):
        """Tick backtest should complete in reasonable time"""
        # Target: 1M ticks in < 5 minutes

    async def test_signal_generation(self):
        """Signals should generate from ticks"""
        # No candle dependency
```

#### ✅ Task 6.2: Performance Benchmarks
```python
Metrics to Track:
1. Tick processing latency: < 1ms per tick
2. Indicator calculation: < 10ms
3. Signal generation: < 50ms
4. Total tick-to-order: < 100ms (vs 3600s with candles!)
```

---

## 🎯 EXECUTION SEQUENCE (15-Day Plan)

### Week 1: Foundation
```
Day 1-2:   Task 1.1 - Tick collection infrastructure
Day 3:     Task 1.2 - Tick indicators
Day 4:     Task 1.3 - Update Binance client
Day 5-7:   Task 2.1-2.2 - Migrate strategy & backtester
```

### Week 2: Integration
```
Day 8-9:   Task 2.3 + 3.1 - Fix tick trader, ML migration
Day 10-11: Task 3.2 + 4.1 - Supporting systems, data pipeline
Day 12-13: Task 4.2 + 5.1 - Streamer integration, API updates
```

### Week 3: Validation
```
Day 14:    Task 6.1 - Comprehensive testing
Day 15:    Task 6.2 - Performance validation & production deploy
```

---

## ✅ VALIDATION CHECKLIST

### Pre-Deployment Validation

#### 🔴 CRITICAL CHECKS (Must Pass 100%)
- [ ] **Zero Candle Calls**: `grep -r "get_klines" *.py` in active trading modules = 0 results
- [ ] **Tick Stream Active**: All symbols receiving ticks at ~10/second
- [ ] **Indicator Calculation**: Works on tick data only
- [ ] **Signal Generation**: No OHLCV DataFrame dependencies
- [ ] **Backtest Functional**: Can backtest using tick data
- [ ] **Live Trading**: Executes orders from tick signals

#### 🟡 PERFORMANCE CHECKS (Must Meet Targets)
- [ ] **Tick Latency**: < 100ms from exchange to indicator
- [ ] **Signal Latency**: < 200ms from tick to signal
- [ ] **Order Execution**: < 300ms from signal to order
- [ ] **Total Latency**: < 500ms (vs 3600000ms with candles!)
- [ ] **Backtest Speed**: 1M ticks in < 5 minutes
- [ ] **Memory Usage**: < 2GB for 10 symbols, 10K ticks each

#### 🟢 QUALITY CHECKS (Must Be Operational)
- [ ] **Data Persistence**: Ticks saved to storage
- [ ] **Error Recovery**: Automatic reconnection on disconnect
- [ ] **Indicator Accuracy**: Within 1% of candle-based (on same data)
- [ ] **ML Models**: Can train on tick features
- [ ] **Monitoring**: Dashboard shows tick metrics

### Post-Deployment Monitoring

```python
Monitor for 7 Days:
1. Tick reception rate (should be ~10/second per symbol)
2. Signal generation frequency
3. Trade execution success rate
4. System latency (tick-to-order)
5. Compare: Tick-based P&L vs Candle-based P&L (historical)
```

---

## 📁 FILE STRUCTURE (After Migration)

```
backend/
├── tick_data/                    # NEW
│   ├── tick_data_collector.py   # WebSocket tick collection
│   ├── tick_data_store.py       # Storage engine
│   ├── tick_buffer.py            # In-memory circular buffer
│   └── tick_indicators.py        # Tick-based indicators
│
├── binance_client.py             # MODIFIED (add tick methods)
├── trading_strategy.py           # MODIFIED (use tick data)
├── backtester.py                 # MODIFIED (tick-based backtest)
├── realtime_tick_trader.py      # MODIFIED (remove candle calls)
├── ml_engine.py                  # MODIFIED (tick features)
│
├── technical_indicators.py       # KEEP (legacy, deprecated)
├── data_collector.py             # KEEP + ENHANCE (add tick download)
├── data_streamer.py              # KEEP + INTEGRATE (already tick-based)
│
└── legacy/                       # MOVE OLD VERSIONS
    ├── candle_based_strategy.py.old
    └── candle_backtester.py.old
```

---

## 🚨 CRITICAL SUCCESS FACTORS

### Must Have
1. ✅ **Zero Candle Dependencies** in live trading
2. ✅ **Sub-second Latency** for tick processing
3. ✅ **100% Tick Coverage** for all signals
4. ✅ **Reliable WebSocket** with auto-reconnect
5. ✅ **Efficient Storage** for tick data

### Must Avoid
1. ❌ **ANY get_klines() calls** in realtime_tick_trader.py
2. ❌ **OHLCV DataFrame** requirements in strategy
3. ❌ **Candle-based indicators** in signal generation
4. ❌ **Time delays** > 1 second for signal generation
5. ❌ **Data loss** during WebSocket disconnections

---

## 📊 EXPECTED OUTCOMES

### Performance Improvements
```
Metric                  | Before (1h candles) | After (Ticks)     | Improvement
------------------------|---------------------|-------------------|-------------
Data Frequency          | 1 per hour          | ~10 per second    | 36,000x
Signal Latency          | 0-3600 seconds      | 0.1 seconds       | 36,000x faster
Breakout Detection      | Next candle         | Immediate         | Real-time
Volatility Capture      | Intrabar hidden     | Every tick        | 100% capture
Trade Execution Speed   | Minutes             | Milliseconds      | 1000x faster
Backtest Accuracy       | Approximation       | Realistic         | True simulation
```

### Risk Reduction
- **No Missing Breakouts**: Capture volatility in real-time
- **No Delayed Stops**: Trailing stops update every tick
- **No Candle Lag**: Signals based on current price
- **No Sampling Errors**: Full price history captured

---

## 🎓 LESSONS LEARNED (Pre-Mortem)

### Common Pitfalls to Avoid
1. **Partial Migration**: Leaving any candle calls = failure
2. **Performance Neglect**: Tick processing MUST be optimized
3. **Storage Underestimation**: Ticks = 36,000x more data
4. **Indicator Miscalculation**: Tick indicators ≠ candle indicators
5. **Testing Shortcuts**: Must test with realistic tick volume

### Success Patterns
1. **Clean Break**: Separate tick code from candle code
2. **Incremental Testing**: Test each component with tick data
3. **Performance First**: Optimize BEFORE adding features
4. **Storage Planning**: Database + compression essential
5. **Monitoring**: Real-time metrics for tick pipeline

---

## 📞 NEXT ACTIONS

### Immediate (Today)
1. Review this plan with team
2. Set up development environment
3. Create `tick_data/` directory structure
4. Begin Task 1.1: Tick collection infrastructure

### This Week
1. Complete Phase 1 (Foundation)
2. Validate tick collection works
3. Verify indicator calculations
4. Test with live data (small scale)

### Next Week
1. Complete Phase 2 (Core Migration)
2. Run tick-based backtests
3. Compare results vs candle-based
4. Performance optimization

---

**END OF MASTER PLAN**

**Remember**: This is mission-critical. Every single candle reference must be eliminated from the live trading path. No exceptions, no shortcuts.
