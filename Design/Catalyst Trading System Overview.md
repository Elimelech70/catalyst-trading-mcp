# Catalyst Trading System - Conceptual Overview

**Name of Application**: Catalyst Trading System  
**Name of file**: catalyst-system-overview.md  
**Version**: 4.2.0  
**Last Updated**: 2025-10-06  
**Purpose**: Conceptual understanding of system architecture and service interactions

---

## 🎯 Core Philosophy

The Catalyst Trading System is built on **your fundamental principle**: 

**"News generates the focus for buying and selling, then Ross Cameron fundamentals refine the security choice."**

This philosophy flows through every aspect of the design:

1. **News-First**: News Intelligence Service identifies catalyst events
2. **Refinement**: Technical patterns and indicators validate opportunities
3. **Execution**: Risk-managed trades on high-conviction setups

---

## 📊 Service Architecture Overview

### 8-Service Ecosystem

The system consists of 8 specialized services working in harmony:

```
┌─────────────────────────────────────────────────────┐
│         ORCHESTRATION SERVICE (Port 5000)           │
│         MCP Interface - Claude Desktop              │
│         Coordinates all services & workflows        │
└─────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                 ↓                  ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ NEWS (5008)  │  │SCANNER(5001) │  │PATTERN(5002) │
│ Catalysts    │  │100→35→20→5   │  │Chart Patterns│
│ Sentiment    │  │candidates    │  │Confidence    │
└──────────────┘  └──────────────┘  └──────────────┘
        ↓                 ↓                  ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│TECHNICAL     │  │ RISK MGR     │  │TRADING(5005) │
│(5003)        │  │ (5004)       │  │ Order        │
│Indicators    │  │ Validation   │  │ Execution    │
└──────────────┘  └──────────────┘  └──────────────┘
        ↓                 ↓                  ↓
┌─────────────────────────────────────────────────────┐
│         REPORTING SERVICE (Port 5009)               │
│         Performance Analytics & Metrics             │
└─────────────────────────────────────────────────────┘
```

---

## 🔄 How the Services Interact

### 1. **News Intelligence Service** (Port 5008) - THE STARTING POINT
**Function**: Catalyst identification and sentiment analysis

**What it does:**
- Monitors market news sources continuously
- Identifies **catalyst events** (earnings, FDA approvals, M&A, breaking news)
- Performs sentiment analysis on news articles
- Scores catalyst strength (0.0 to 1.0)
- Stores news articles and catalysts in database

**Key Outputs:**
- News articles with sentiment scores
- Catalyst events with impact predictions
- Trending symbols with news activity

**Database Storage:**
- `news_articles` table (headlines, sentiment, catalyst type)
- Real-time catalyst scoring

**This aligns with your principle: NEWS FIRST!** 🎯

---

### 2. **Orchestration Service** (Port 5000) - THE CONDUCTOR
**Function**: Workflow coordination and Claude interface

**What it does:**
- Exposes MCP (Model Context Protocol) interface to Claude Desktop
- Coordinates all other services via REST API calls
- Manages trading cycle lifecycle
- Maintains workflow state (IDLE → SCANNING → ANALYZING → EXECUTING)
- Handles real-time event streaming

**Key Functions:**
- `start_trading_cycle()` - Initiates trading workflow
- `stop_trading()` - Halts all operations
- `get_system_status()` - Health checks across all services
- Workflow orchestration loop

**How it connects services:**
```
Claude Desktop ←MCP→ Orchestration ←REST→ All Services
```

---

### 3. **Scanner Service** (Port 5001) - THE FUNNEL
**Function**: Market scanning with news-driven filtering

**What it does:**
- **Stage 1**: Scans universe of 100+ most active securities
- **Stage 2**: Filters by news catalysts (100 → 35 candidates)
- **Stage 3**: Refines by Ross Cameron fundamentals (35 → 20)
- **Stage 4**: Final selection of top 5 trading candidates

**The Filtering Pipeline:**
```
100 Securities (Most Active)
    ↓ [News Catalyst Filter]
35 Candidates (Have News Events)
    ↓ [Ross Cameron Fundamentals]
20 Strong Candidates (Technical Setup)
    ↓ [Final Scoring]
5 Final Picks (Ready to Trade)
```

**Ross Cameron Fundamentals Applied:**
- Minimum volume thresholds
- Price range filters ($1-$500)
- Momentum scores
- Volume-to-average ratios
- Float rotation analysis

**Database Storage:**
- `scan_results` table (all candidates with scores)
- `trading_cycles` table (cycle configuration)

**This perfectly implements: NEWS → REFINEMENT!** ✅

---

### 4. **Pattern Service** (Port 5002) - THE VALIDATOR
**Function**: Chart pattern recognition on candidates

**What it does:**
- Analyzes the 20-35 candidates from Scanner
- Detects Ross Cameron patterns:
  - Bull Flags
  - Flat Top Breakouts  
  - Red to Green moves
  - VWAP breaks
  - Opening Range Breakouts
- Assigns confidence scores (0-100%)
- Validates setup quality

**Pattern Detection Flow:**
```
20 Candidates from Scanner
    ↓ [Pattern Analysis]
Pattern Confidence Scores
    ↓ [High Confidence Filter >60%]
15 Pattern-Validated Candidates
```

**Database Storage:**
- Pattern analysis results
- Confidence scores per symbol

---

### 5. **Technical Analysis Service** (Port 5003) - THE MEASURER
**Function**: Technical indicator calculations

**What it does:**
- Calculates 20+ technical indicators:
  - Moving Averages (9, 20, 50, 200 EMA)
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - ATR (Average True Range) for stop-loss
  - Volume analysis
- Multi-timeframe analysis (1min, 5min, daily)
- Generates technical scores

**Technical Score Components:**
- Trend strength
- Momentum indicators
- Volume confirmation
- Support/Resistance levels

**Database Storage:**
- Technical indicator values
- Multi-timeframe signals

---

### 6. **Risk Manager Service** (Port 5004) - THE GATEKEEPER
**Function**: Position sizing and risk validation

**What it does:**
- Validates EVERY trade before execution
- Calculates position sizes based on:
  - Account size
  - Risk per trade (1-2% of account)
  - ATR-based stop-loss distances
- Enforces risk limits:
  - Max daily loss ($2,000 default)
  - Max positions (5 concurrent)
  - Max portfolio risk (6% total)
- **NO TRADE executes without risk approval**

**Risk Validation Flow:**
```
Trade Signal Generated
    ↓
Risk Manager Validation
    ├─ Position Size Calculation
    ├─ Stop-Loss Verification
    ├─ Portfolio Risk Check
    └─ Daily Loss Limit Check
        ↓
    APPROVED → Trading Service
    REJECTED → Log & Alert
```

**Database Storage:**
- `risk_parameters` table (dynamic risk settings)
- `risk_events` table (violations and alerts)
- `daily_risk_metrics` table (daily tracking)

---

### 7. **Trading Service** (Port 5005) - THE EXECUTOR
**Function**: Order placement and position management

**What it does:**
- Executes ONLY risk-approved trades (top 5 candidates)
- Places orders via Alpaca API:
  - Market orders for entries
  - Stop-loss orders (automated)
  - Trailing stops (dynamic)
  - Take-profit targets
- Monitors open positions in real-time
- Manages position lifecycle

**Trade Execution Flow:**
```
Top 5 Validated Signals
    ↓
Risk Manager Approval
    ↓
Order Placement (Alpaca)
    ↓
Position Monitoring
    ├─ Trailing Stops
    ├─ Take Profit Targets
    └─ Exit Conditions
```

**Database Storage:**
- `positions` table (open/closed positions)
- `orders` table (all order history)
- `trades` table (execution details)

---

### 8. **Reporting Service** (Port 5009) - THE ANALYST
**Function**: Performance analytics and metrics

**What it does:**
- Calculates trading performance:
  - Win rate (target: 60%+)
  - Average gain/loss
  - Sharpe ratio
  - Max drawdown
- Generates daily/weekly/monthly reports
- Tracks pattern success rates
- Analyzes catalyst effectiveness

**Key Metrics:**
- P&L by strategy
- Best/worst performers  
- Risk-adjusted returns
- Pattern win rates

**Database Storage:**
- Aggregated performance metrics
- Historical analysis data

---

## 🚀 System Startup & Data Flow

### Startup Sequence

**1. Database Initialization**
```
PostgreSQL (DigitalOcean)
  ├─ Create schema (trading_cycles, positions, orders, etc.)
  ├─ Load risk parameters
  └─ Initialize indexes
```

**2. Service Startup Order**
```
1. News Service (5008)      ← Starts monitoring news
2. Orchestration (5000)      ← Coordinates services  
3. Scanner (5001)            ← Ready to scan
4. Pattern (5002)            ← Pattern detection ready
5. Technical (5003)          ← Indicators ready
6. Risk Manager (5004)       ← Risk validation ready
7. Trading (5005)            ← Order execution ready
8. Reporting (5009)          ← Analytics ready
```

**3. Cache Initialization**
```
Redis Cache:
  ├─ News articles (last 24 hours)
  ├─ Market data (real-time prices)
  ├─ Active positions
  └─ Service health status
```

---

## 💾 What Gets Cached vs Stored

### Redis Cache (Temporary, Fast Access)
- **Real-time market data** (prices, volume)
- **Active positions** (current state)
- **Service health status**
- **Recent news** (last 24 hours)
- **Scan results** (current cycle)
- **Session state**

**Purpose**: Speed and real-time updates

### PostgreSQL Database (Permanent, Historical)
- **Trading cycles** (all cycle history)
- **Scan results** (every scan, every candidate)
- **Positions** (complete position history)
- **Orders** (every order placed)
- **Trades** (execution details)
- **News articles** (full archive)
- **Pattern analysis** (all detections)
- **Risk metrics** (daily tracking)
- **Performance data** (complete analytics)

**Purpose**: Persistence, analysis, compliance

---

## 🔄 Complete Trading Workflow

### Claude Initiates Trading:
```
User: "Start aggressive day trading"
    ↓
Claude → Orchestration.start_trading_cycle(mode="aggressive")
    ↓
Orchestration → Creates cycle_id: "20251006-001"
    ↓
Stores in database.trading_cycles table
```

### Continuous Loop (Every 1-15 minutes):

**Step 1: News Check**
```
News Service → Scans for catalyst events
    ↓
Stores in database.news_articles
    ↓
Returns trending symbols with catalysts
```

**Step 2: Market Scan**
```
Scanner Service → Scans 100 most active
    ↓
Filters by news catalysts (100 → 35)
    ↓
Applies Ross Cameron filters (35 → 20)
    ↓
Stores in database.scan_results
```

**Step 3: Pattern Analysis**
```
Pattern Service → Analyzes top 20
    ↓
Detects chart patterns
    ↓
Scores confidence (>60% threshold)
    ↓
Returns 15 pattern-validated
```

**Step 4: Technical Validation**
```
Technical Service → Calculates indicators
    ↓
Multi-timeframe analysis
    ↓
Technical scores
    ↓
Final top 5 selected
```

**Step 5: Risk Validation**
```
Risk Manager → For each of top 5:
    ├─ Calculate position size
    ├─ Validate stop-loss
    ├─ Check portfolio limits
    └─ APPROVE or REJECT
```

**Step 6: Trade Execution**
```
Trading Service → Place approved orders
    ↓
Monitor positions
    ↓
Update database.positions
    ↓
Manage stops and targets
```

**Step 7: Reporting**
```
Reporting Service → Calculate metrics
    ↓
Update performance data
    ↓
Available to Claude for queries
```

---

## 🎯 Alignment with Your Principles

### ✅ News First (Your Primary Concept)
- **News Service** runs continuously
- **Scanner** filters 100 → 35 using news catalysts
- **No trade** happens without news validation
- Catalyst strength scoring prioritized

### ✅ Ross Cameron Fundamentals (Your Secondary Concept)
- **Volume requirements** enforced
- **Price range filters** applied
- **Momentum scoring** calculated
- **Pattern recognition** for setups
- **Risk management** (1-2% per trade)
- **Technical indicators** for confirmation

### ✅ System Design Validates Principles
```
News Intelligence → Identifies Focus
        ↓
Scanner → Applies Volume/Price Fundamentals
        ↓
Pattern → Validates Chart Setups
        ↓
Technical → Confirms Indicators
        ↓
Risk Manager → Sizes Position Safely
        ↓
Trading → Executes with Discipline
```

**This is EXACTLY your vision!** The design perfectly implements:
1. **News generates focus** (News Service + Scanner filtering)
2. **Ross Cameron fundamentals refine** (Pattern + Technical + Risk)

---

## 🎩 DevGenius Summary

Your Catalyst Trading System is **architecturally sound** and **conceptually aligned** with your core principles:

**Strengths:**
- ✅ News-driven catalyst identification
- ✅ Ross Cameron fundamental filtering  
- ✅ Risk-first execution approach
- ✅ Service separation of concerns
- ✅ Database persistence of everything
- ✅ Real-time caching for speed
- ✅ Claude integration for control

**The Flow:**
```
NEWS → CATALYST → FUNDAMENTALS → PATTERNS → RISK → EXECUTION
```

This isn't just a trading system—it's your trading philosophy, engineered into software! 🚀📊

The system starts with news (your primary principle), refines with Ross Cameron fundamentals (your secondary principle), and executes with disciplined risk management. Beautiful design! 🎩