# 🎯 TradingBot V2 - Master Plan
**Project Restart Date**: 2025-10-15
**Target Launch**: 2025-10-17 (3 Days)
**Goal**: Real profit-generating AI trading system with 100% authentic data

---

## 📋 Executive Summary

### Critical Lessons from V1
```yaml
❌ V1 Problems:
  - Fake/dummy data used for UI demonstration
  - No real Binance API integration
  - AI engine was placeholder with alert messages
  - No actual trading execution
  - Misleading profit displays

✅ V2 Core Principles:
  - 100% Real Binance data (REST + WebSocket)
  - Actual trading execution (Testnet → Mainnet)
  - Transparent P&L tracking
  - AI-driven strategy adaptation
  - Professional trader-grade UI
```

---

## 🎯 Project Requirements (User-Confirmed)

### 1. AI Market Analysis Scope (Comprehensive)
- ✅ Technical Analysis: RSI, MACD, Bollinger Bands, Moving Averages, Volume, etc.
- ✅ Sentiment Analysis: News aggregation, social media trends
- ✅ On-chain Data: Whale movements, exchange flows (optional Phase 2)
- ✅ Multi-timeframe: 1m, 5m, 15m, 1h, 4h, 1d charts

### 2. AI Engine Decision
**Primary**: Self-hosted ML Engine (Python FastAPI + Scikit-learn/TensorFlow)
**Fallback**: Claude API ($20/month Pro plan or $3/million tokens API)

**Rationale**:
- Self-hosted: No recurring AI costs, full control, faster iteration
- Claude API: Better for complex NLP (news/sentiment), expensive for 24/7 trading
- **Hybrid Approach**: Self-hosted for technical analysis + Claude API for news analysis

### 3. Trading Pairs
- **Initial**: Top 10 cryptocurrencies by market cap
  - BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT
  - ADA/USDT, DOGE/USDT, AVAX/USDT, DOT/USDT, MATIC/USDT
- **Expansion**: Add more pairs if low volatility prevents trading
- **Selection Logic**: AI prioritizes pairs with optimal volatility + liquidity

### 4. Trading Style (Adaptive Hybrid)
```yaml
Core Principle: Profit > Trading Fees ALWAYS

Strategy Mix:
  - Scalping: High-frequency (seconds to minutes)
  - Day Trading: Intraday positions (minutes to hours)
  - Swing Trading: Multi-day positions (days to weeks)

AI Decision Logic:
  - Calculate break-even: (Entry Price × Fee%) × 2
  - Minimum Profit Target: Break-even + 0.5%
  - Accept Small Losses: -0.3% to -0.5% for better opportunities
  - Big Win Strategy: Accumulate small wins → 1 big profitable trade

Trade Frequency: UNLIMITED (as long as profitable)
```

### 5. Risk Management (AI-Optimized)
```yaml
Loss Tolerance (Initial Conservative Settings):
  - Single Trade Max Loss: -3% (wider than average to reduce false stop-outs)
  - Daily Max Loss: -10%
  - Total Drawdown Limit: -25%

AI Optimization:
  - Monitor win rate, profit factor, Sharpe ratio
  - Dynamically adjust stop-loss based on volatility
  - Test different settings → recommend optimal parameters

Stop-Loss Logic:
  - Avoid frequent stop-outs (use ATR-based trailing stops)
  - Risk-reward ratio: Minimum 1:2 (risk $1 to make $2)
```

### 6. Leverage Strategy (Conservative Scaling)
```yaml
Initial: SPOT TRADING ONLY (No leverage)

Leverage Unlock Conditions:
  100% Profit → 2x leverage on 50% of profits
  200% Profit → 3x leverage on 50% of profits
  300% Profit → 4x leverage on 50% of profits

Leverage Risk Control:
  - If futures losses reach -30% of profit → reduce leverage
  - Liquidation Prevention: NEVER risk more than 30% of profit
  - Formula: Max Position = (Principal + 70% Profit) only

AI Volatility Adjustment:
  - High volatility (VIX crypto > 80) → reduce leverage
  - Low volatility → consider increasing leverage within limits
```

### 7. Testing Strategy
```yaml
Virtual Balance: USDT 10,000

Test Phases:
  Day 1: Backtesting with historical data (2024-01 to 2024-10)
  Day 2: Paper trading on Binance Testnet (real-time, no real money)
  Day 3: Live trading with USDT 50-100 on Mainnet

Acceptable Test Outcomes:
  - Losses are OK during testing
  - Focus: Strategy validation, bug detection, performance tuning
  - Criteria for Mainnet: Testnet win rate > 50%, profit factor > 1.3
```

---

## 🏗️ Technical Architecture V2

### System Overview
```
┌─────────────────────────────────────────────────────┐
│  🧠 AI Strategy Engine (Python FastAPI)            │
│  ├─ Technical Analysis (TA-Lib, Pandas)            │
│  ├─ ML Models (Scikit-learn, XGBoost)              │
│  ├─ Sentiment Analysis (Claude API - Optional)     │
│  ├─ Risk Calculator                                 │
│  └─ Strategy Optimizer                              │
└─────────────────────────────────────────────────────┘
           ↓ Trading Signals (Buy/Sell/Hold)
┌─────────────────────────────────────────────────────┐
│  📊 Data Pipeline (Ruby + Python)                   │
│  ├─ Binance WebSocket (Real-time ticks)            │
│  ├─ Historical Data Fetcher (Klines API)           │
│  ├─ Technical Indicators Calculator                 │
│  ├─ News Aggregator (CoinGecko, CryptoNews)        │
│  └─ Redis Cache (30-second TTL)                     │
└─────────────────────────────────────────────────────┘
           ↓ Verified Market Data
┌─────────────────────────────────────────────────────┐
│  💼 Trading Execution (Rails + Binance API)        │
│  ├─ Order Manager (Market/Limit orders)            │
│  ├─ Position Tracker (Real-time P&L)               │
│  ├─ Risk Controller (Auto stop-loss/take-profit)   │
│  ├─ Portfolio Manager (Asset allocation)           │
│  └─ Trade Logger (All transactions)                 │
└─────────────────────────────────────────────────────┘
           ↓ Real-time Status
┌─────────────────────────────────────────────────────┐
│  🖥️ Professional Dashboard (React + TradingView)   │
│  ├─ Multi-chart Layout (4-16 charts)               │
│  ├─ Order Book + Depth Chart                        │
│  ├─ Position Monitor (Unrealized P&L)              │
│  ├─ Performance Analytics (Daily/Weekly/Monthly)    │
│  ├─ Trade History (Win rate, Profit factor)        │
│  ├─ System Health (API latency, errors)            │
│  └─ AI Insights Panel (Strategy explanations)      │
└─────────────────────────────────────────────────────┘
```

### Technology Stack
```yaml
Backend Core:
  Main App: Ruby on Rails 8.0.2.1
  AI Engine: Python 3.11 + FastAPI
  Real-time: ActionCable + Redis
  Job Queue: Sidekiq (background jobs)

AI/ML Stack:
  Technical Analysis: TA-Lib, Pandas, NumPy
  Machine Learning: Scikit-learn, XGBoost, LightGBM
  Deep Learning: TensorFlow/PyTorch (optional Phase 2)
  Backtesting: Backtrader, vectorbt
  NLP (Optional): Claude API for news/sentiment

Data Layer:
  Primary DB: PostgreSQL 15 (trades, accounts, configs)
  Time-series: TimescaleDB extension (price data)
  Cache: Redis 7 (real-time data, sessions)
  File Storage: Local disk (backtest results, logs)

Frontend:
  Framework: React 18 + TypeScript
  Charts: TradingView Lightweight Charts
  UI Library: Ant Design (professional trader theme)
  State: Redux Toolkit + RTK Query
  Real-time: WebSocket (ActionCable client)

APIs:
  Trading: Binance Spot API + Futures API
  Market Data: Binance WebSocket + Klines
  News: CoinGecko API, CryptoPanic API
  Monitoring: Prometheus + Grafana

Infrastructure:
  Development: Docker Compose (local)
  Production: Vultr High Performance
    - Plan: 4 vCPU, 8GB RAM, 160GB NVMe SSD
    - Location: Seoul (5ms latency) or Tokyo (35ms)
    - Cost: $48/month
  CI/CD: GitHub Actions
  Monitoring: Prometheus + Grafana
  Alerting: Telegram Bot API
```

---

## 📅 3-Day Development Sprint

### Day 1 (2025-10-15): Data Foundation & Backtesting
```yaml
Morning (08:00 - 12:00):
  ✅ Project Setup
    - Backup TradingBotV1 to TradingBotV1_backup
    - Create TradingBotV2 project structure
    - Setup Docker Compose (Rails + Python + PostgreSQL + Redis)
    - Configure Binance API credentials

  ✅ Real-time Data Pipeline
    - Binance WebSocket client (price streams)
    - Historical data downloader (Klines API)
    - Redis caching layer
    - Technical indicators (RSI, MACD, BB, SMA, EMA)

Afternoon (12:00 - 18:00):
  ✅ Backtesting Framework
    - Integrate Backtrader library
    - Load historical data (2024-01 to 2024-10)
    - Implement basic strategies:
      * MA Crossover (SMA 20/50)
      * RSI Mean Reversion (30/70)
      * Bollinger Band Bounce
    - Performance metrics (Sharpe, win rate, profit factor)

  ✅ Initial Testing
    - Backtest on BTC/USDT with USDT 10,000
    - Generate performance report
    - Identify best-performing strategy

Evening (18:00 - 20:00):
  ✅ Documentation
    - Document API endpoints
    - Write setup instructions
    - Create backtest result analysis

📊 Day 1 Deliverable: Working backtesting system with real historical data
```

### Day 2 (2025-10-16): AI Engine & Live Trading
```yaml
Morning (08:00 - 12:00):
  ✅ AI Strategy Engine (Python)
    - FastAPI service setup
    - Feature engineering (50+ technical features)
    - ML model training:
      * Random Forest Classifier
      * XGBoost for trend prediction
      * LSTM for price forecasting (optional)
    - Model evaluation and selection

  ✅ Strategy Signal Generator
    - Combine technical + ML predictions
    - Risk-reward calculator
    - Position sizing algorithm
    - Trade signal API endpoint

Afternoon (12:00 - 16:00):
  ✅ Trading Execution System
    - Binance order placement (market/limit)
    - Order status monitoring
    - Position tracker (real-time P&L)
    - Auto stop-loss/take-profit
    - Portfolio manager (multi-pair allocation)

  ✅ Risk Management
    - Single trade risk limiter (-3%)
    - Daily loss circuit breaker (-10%)
    - Drawdown monitor (-25% total)
    - Trade fee calculator
    - Profit > Fee validation

Evening (16:00 - 20:00):
  ✅ Paper Trading (Binance Testnet)
    - Connect to testnet API
    - Execute live trades with virtual money
    - Monitor performance for 4 hours
    - Fix bugs and optimize strategies

  ✅ Testing Goals
    - At least 20 trades executed
    - Win rate > 50%
    - Profit factor > 1.3
    - No critical errors

📊 Day 2 Deliverable: AI-powered auto-trading system running on Testnet
```

### Day 3 (2025-10-17): Professional UI & Mainnet Launch
```yaml
Morning (08:00 - 12:00):
  ✅ Professional Trading Dashboard
    - Multi-chart layout (TradingView charts)
    - Real-time price updates (WebSocket)
    - Order book visualization
    - Depth chart + volume profile

  ✅ Position Monitor Panel
    - Current holdings (coins + USDT)
    - Unrealized P&L (real-time)
    - Entry price, current price, % change
    - Stop-loss and take-profit levels

  ✅ Performance Analytics
    - Daily/Weekly/Monthly profit chart
    - Win rate, profit factor, Sharpe ratio
    - Trade history table (sortable, filterable)
    - Equity curve graph

Afternoon (12:00 - 16:00):
  ✅ System Health Dashboard
    - API connection status
    - WebSocket latency
    - Trade execution speed
    - Error logs and warnings

  ✅ AI Insights Panel
    - Current market sentiment
    - Active strategy explanation
    - Risk level indicator
    - Recommended actions

  ✅ Vultr Deployment
    - Deploy to Vultr High Performance (Seoul/Tokyo)
    - Configure environment variables
    - Setup SSL certificate
    - Enable monitoring (Prometheus + Grafana)

Evening (16:00 - 20:00):
  ✅ Mainnet Preparation
    - Final testnet validation
    - Security audit (API keys, secrets)
    - Rate limiting check
    - Backup and recovery plan

  ✅ Go Live (Small Scale)
    - Switch to Binance Mainnet API
    - Start with USDT 50-100
    - Monitor first 10 trades closely
    - Validate real profit tracking

  ✅ Final Documentation
    - User manual
    - Operational procedures
    - Emergency shutdown process

📊 Day 3 Deliverable: Production-ready system with real money trading
```

---

## 🎨 Professional UI Design Specifications

### Design Principles
- **Theme**: Dark mode (reduce eye strain for 24/7 monitoring)
- **Style**: Professional trader aesthetic (similar to TradingView, Binance Pro)
- **Layout**: Information-dense but organized
- **Colors**: Green (profit), Red (loss), Blue (neutral), Yellow (warnings)

### Dashboard Layout
```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] TradingBot V2    Balance: $10,523  24h: +5.2%  🟢  │
├──────────┬──────────────────────────────────┬───────────────┤
│  Pairs   │  Main Chart (TradingView)        │  Order Book   │
│  ──────  │  ────────────────────────────    │  ───────────  │
│  BTC/USDT│  [Candlestick Chart]             │  Asks (Red)   │
│  ETH/USDT│  [Volume Bars]                   │  ···          │
│  BNB/USDT│  [Indicators: RSI, MACD]         │  Spread       │
│  SOL/USDT│                                   │  Bids (Green) │
│  ···     │                                   │               │
├──────────┴──────────────────────────────────┴───────────────┤
│  Open Positions (3)                   Unrealized P&L: +$234 │
│  ──────────────────────────────────────────────────────────│
│  BTC/USDT | Long | Entry: $43,210 | Current: $43,987 | +1.8%│
│  ETH/USDT | Long | Entry: $2,301  | Current: $2,389  | +3.8%│
│  ···                                                         │
├──────────────────────────────────────────────────────────────┤
│  Trade History        Win Rate: 62%   Profit Factor: 1.85   │
│  ──────────────────────────────────────────────────────────│
│  Time     | Pair      | Type | Entry  | Exit   | P&L      │
│  ──────────────────────────────────────────────────────────│
│  10:34:21 | BTC/USDT  | Long | 43,100 | 43,450 | +$35.00  │
│  ···                                                         │
├──────────────────────────────────────────────────────────────┤
│  AI Insights                         System Health: 🟢      │
│  ──────────────────────────────────────────────────────────│
│  Current Strategy: Trend Following + Mean Reversion         │
│  Market Sentiment: Bullish (RSI: 58, MACD: Positive)        │
│  Risk Level: MODERATE (Daily Drawdown: -2.3%)               │
│  API Latency: 12ms | WebSocket: Connected | Trades: 147     │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security & Risk Controls

### API Security
- Environment variables for all secrets
- Never commit API keys to Git
- Use Binance IP whitelist
- Separate Testnet/Mainnet credentials
- Enable 2FA on Binance account

### Trade Safeguards
- Position size limits (max 20% of balance per trade)
- Daily trade count limit (max 100 trades/day)
- Minimum time between trades (5 seconds)
- Emergency stop button (halt all trading)
- Automatic circuit breaker (if daily loss > 10%)

### Monitoring & Alerts
- Telegram alerts for:
  - Large profits/losses (> $100)
  - System errors
  - API connection issues
  - Daily performance summary
- Prometheus metrics collection
- Grafana dashboard for DevOps

---

## 📊 Success Metrics

### Phase 1: Backtesting (Day 1)
- ✅ Successfully fetch 10 months of historical data
- ✅ Execute 500+ backtested trades
- ✅ Generate performance report with Sharpe > 1.0

### Phase 2: Paper Trading (Day 2)
- ✅ 20+ Testnet trades executed
- ✅ Win rate > 50%
- ✅ Profit factor > 1.3
- ✅ Zero critical system errors

### Phase 3: Live Trading (Day 3)
- ✅ Successfully deploy to Vultr
- ✅ Execute 10 Mainnet trades with real money
- ✅ Positive P&L (even if small)
- ✅ Professional dashboard operational

### Long-term Goals (Week 2+)
- 🎯 Daily profit target: 2% (initial conservative goal)
- 🎯 Weekly profit: 10-15%
- 🎯 Monthly profit: 40-60%
- 🎯 Max drawdown: < 25%
- 🎯 Win rate: > 55%
- 🎯 Profit factor: > 1.5

---

## 🚀 Next Steps

1. **Immediate Action**: Backup current project
2. **Start Day 1**: Setup TradingBotV2 structure
3. **Focus**: Real data integration (no fake data allowed)
4. **Validate**: Every component with real Binance data
5. **Document**: Everything for future reference

---

**Last Updated**: 2025-10-15
**Status**: MASTER PLAN APPROVED - READY TO BUILD
**Next**: Begin Day 1 Development Sprint
