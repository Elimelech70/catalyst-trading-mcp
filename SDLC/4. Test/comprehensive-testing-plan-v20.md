# Catalyst Trading System - Comprehensive Testing Plan v2.0

**Name of Application:** Catalyst Trading System  
**Document Name:** comprehensive-testing-plan-v20.md  
**Version:** 2.0.0  
**Last Updated:** 2025-10-23  
**Purpose:** Detailed testing strategy validating all trading workflows against design specifications v5.0

---

## REVISION HISTORY:

**v2.0.0 (2025-10-23)** - Updated for 9-Service Architecture
- Updated for functional specification v5.0 (9-service architecture)
- Added Workflow service testing (Port 5006)
- Updated Orchestration service tests (MCP-only, no business logic)
- Added Orchestration → Workflow integration tests
- Updated service interaction patterns
- Maintained all quality gates and success criteria

**v1.0.0 (2025-10-23)** - Initial Testing Plan (superseded)
- Based on functional specification v4.1 (7-service architecture)
- Orchestration handled both MCP and workflow

---

## Executive Summary

This testing plan validates the Catalyst Trading System against:
- **Functional Specification v5.0** (functional-spec-mcp-v50.md) ✅ **UPDATED**
- **Architecture v5.0** (Architecture v5.0.0.md)
- **Database Schema v5.0** (Database schema v510.md)
- **Trading Workflow v4.2** (phase1 Trading Workflow v42.md)
- **Software Requirements Specification v1.0** (software-requirements-specification-v1.0.0.md)

### Testing Scope
- ✅ **9 Microservices** (Orchestration, **Workflow**, Scanner, Pattern, Technical, Risk Manager, Trading, News, Reporting)
- ✅ **Separated Architecture** - Orchestration (MCP-only) + Workflow (coordination)
- ✅ Complete trading cycle workflows
- ✅ Multi-stage filtering (100 → 35 → 20 → 10 → 5)
- ✅ Risk management validation
- ✅ Database normalization and integrity
- ✅ Performance under market conditions

### Key Architecture Changes from v1.0

**Orchestration Service (Port 5000 - MCP)**:
- ❌ **REMOVED**: Trade coordination logic
- ❌ **REMOVED**: Direct service orchestration
- ✅ **RETAINED**: MCP resources (read-only)
- ✅ **RETAINED**: MCP tools (command triggers)
- ✅ **NEW**: All tools call Workflow service via REST

**Workflow Service (Port 5006 - REST)** - NEW:
- ✅ Receives commands from Orchestration
- ✅ Coordinates all internal services
- ✅ Manages trading cycles
- ✅ Routes trade signals
- ✅ Handles emergency stops

---

## Table of Contents

1. [Testing Strategy & Approach](#1-testing-strategy--approach)
2. [Service-Level Testing](#2-service-level-testing)
3. [Workflow Testing](#3-workflow-testing)
4. [Integration Testing](#4-integration-testing)
5. [Database Testing](#5-database-testing)
6. [Performance Testing](#6-performance-testing)
7. [Risk Management Testing](#7-risk-management-testing)
8. [Test Execution Plan](#8-test-execution-plan)
9. [Success Criteria](#9-success-criteria)
10. [Test Environment Setup](#10-test-environment-setup)

---

## 1. Testing Strategy & Approach

### 1.1 Testing Philosophy

**The Three Questions Applied to Testing:**

1. **What is my PURPOSE right now?**
   - 🎯 **Testing/QA Phase** → Verify system works as designed per functional spec v5.0

2. **What QUALITY information do I need?**
   - 📚 Design Documents (Architecture v5.0, Functional Spec v5.0, Database Schema v5.0)
   - 📖 Software Requirements Specification v1.0
   - 🔍 Trading Workflow Specification v4.2

3. **Am I FOCUSED or scattered?**
   - ✅ **Focused** → One workflow at a time, specific outcomes, measurable criteria

### 1.2 Testing Levels

```
┌──────────────────────────────────────────────────────┐
│              TESTING PYRAMID                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│           E2E Testing (Complete Cycles)              │
│           ▲                                          │
│          ╱ ╲                                         │
│         ╱   ╲     Integration Testing                │
│        ╱     ╲    (Service to Service)               │
│       ╱       ╲                                      │
│      ╱─────────╲  Component Testing                  │
│     ╱           ╲ (Individual Services)              │
│    ╱─────────────╲                                   │
│   ╱               ╲ Unit Testing                     │
│  ╱                 ╲ (Functions/Methods)             │
│ ╱───────────────────╲                                │
└──────────────────────────────────────────────────────┘
```

### 1.3 Testing Types

| Test Type | Purpose | Scope | Tools |
|-----------|---------|-------|-------|
| **Unit Tests** | Validate individual functions | Single function/method | pytest |
| **Component Tests** | Validate service behavior | Single service API | pytest + httpx |
| **Integration Tests** | Validate service interactions | Multiple services | pytest + docker-compose |
| **Workflow Tests** | Validate complete workflows | End-to-end cycle | pytest + MCP client |
| **Performance Tests** | Validate speed/throughput | System under load | locust, pytest-benchmark |
| **Database Tests** | Validate schema/data integrity | Database operations | pytest-asyncio, asyncpg |

---

## 2. Service-Level Testing

### 2.1 Orchestration Service (Port 5000 - MCP) ✅ **UPDATED**

#### Test Suite: test_orchestration_service_v50.py

**Key Change**: Orchestration now has NO business logic, only MCP interface

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **ORCH-001** | MCP Resources (Read-only) | Data access via MCP | - All resources return valid JSON<br>- Data fetched from Workflow/other services<br>- Response time < 500ms<br>- No state modifications |
| **ORCH-002** | `resource("trading-cycle/current")` | Current cycle info | - Calls Workflow service GET /api/v1/cycle/current<br>- Returns formatted JSON<br>- Handles Workflow unavailable |
| **ORCH-003** | `resource("market-scan/candidates/active")` | Active candidates | - Calls Scanner service<br>- Returns top 5 candidates<br>- Formatted for Claude |
| **ORCH-004** | `resource("portfolio/positions/open")` | Open positions | - Calls Trading service<br>- Real-time P&L data<br>- Formatted clearly |
| **ORCH-005** | `resource("risk/current")` | Risk metrics | - Calls Risk Manager service<br>- Current exposure data<br>- Limit status |
| **ORCH-006** | `resource("system/health")` | Health check | - Checks all 9 services<br>- Returns aggregated status<br>- Service-by-service details |
| **ORCH-007** | `tool("start_trading_cycle")` | Start cycle command | - Validates parameters<br>- **Calls Workflow POST /api/v1/cycle/start**<br>- Returns cycle_id<br>- NO direct business logic |
| **ORCH-008** | `tool("stop_trading_cycle")` | Stop cycle command | - **Calls Workflow POST /api/v1/cycle/stop**<br>- Confirms stop<br>- Returns summary |
| **ORCH-009** | `tool("execute_trade")` | Trade execution command | - Validates trade parameters<br>- **Calls Workflow POST /api/v1/trade/execute**<br>- Returns execution result |
| **ORCH-010** | `tool("emergency_stop_trading")` | Emergency stop | - **Calls Workflow POST /api/v1/cycle/emergency-stop**<br>- Immediate response<br>- Confirms all positions closed |
| **ORCH-011** | `tool("update_risk_parameters")` | Risk parameter update | - **Calls Workflow POST /api/v1/risk/update**<br>- Confirms update<br>- Returns new limits |
| **ORCH-012** | Error Handling | McpError responses | - Proper error types<br>- Detailed error messages<br>- Service errors propagated correctly |
| **ORCH-013** | Service Communication | HTTP to Workflow | - HTTP client works<br>- Retries on transient errors<br>- Timeouts configured |

**Success Measurement:**
- ✅ All 13 tests pass
- ✅ **NO business logic in Orchestration** (all delegated to Workflow)
- ✅ Response time < 500ms for reads
- ✅ Response time < 2s for tool executions (includes Workflow call)
- ✅ MCP protocol compliance verified
- ✅ FastMCP best practices followed

---

### 2.2 Workflow Service (Port 5006 - REST) ✅ **NEW SERVICE**

#### Test Suite: test_workflow_service.py

**New Service**: All trade coordination logic moved here from Orchestration

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **WORK-001** | `POST /api/v1/cycle/start` | Cycle initialization | - Creates trading_cycles record<br>- Generates cycle_id<br>- Sets scan frequency<br>- Returns cycle configuration |
| **WORK-002** | `GET /api/v1/cycle/current` | Current cycle query | - Returns active cycle data<br>- Includes runtime metrics<br>- Status and configuration |
| **WORK-003** | `POST /api/v1/cycle/stop` | Cycle termination | - Updates cycle status to stopped<br>- Evaluates open positions<br>- Returns final summary |
| **WORK-004** | `POST /api/v1/cycle/emergency-stop` | Emergency halt | - Broadcasts stop to all services<br>- Closes all positions immediately<br>- Updates cycle status<br>- Returns positions closed |
| **WORK-005** | **Stage 1: Market Scan** | Scanner coordination (100 candidates) | - **Calls Scanner POST /api/v1/scan**<br>- Receives 100 candidates<br>- Duration < 10s<br>- Results persisted in scan_results |
| **WORK-006** | **Stage 2: News Filter** | News intelligence (100 → 35) | - **Calls News service** for each candidate<br>- Filters by sentiment_threshold<br>- 35 candidates remain<br>- Duration < 15s |
| **WORK-007** | **Stage 3: Pattern Filter** | Pattern recognition (35 → 20) | - **Calls Pattern service**<br>- Filters by pattern_confidence ≥ 0.6<br>- 20 candidates remain<br>- Duration < 20s |
| **WORK-008** | **Stage 4: Technical Filter** | Technical analysis (20 → 10) | - **Calls Technical service**<br>- Calculates composite score<br>- 10 candidates remain<br>- Duration < 10s |
| **WORK-009** | **Stage 5: Risk Validation** | Risk Manager approval (10 → 5) | - **Calls Risk Manager service**<br>- Position sizing calculated<br>- Risk limits validated<br>- 5 approved for trading |
| **WORK-010** | **Stage 6: Trade Execution** | Trading service coordination | - **Calls Trading service**<br>- Executes approved trades<br>- Updates position tracking<br>- Returns execution status |
| **WORK-011** | `POST /api/v1/trade/execute` | Single trade execution | - Receives trade signal<br>- Validates parameters<br>- Coordinates Risk → Trading<br>- Returns result |
| **WORK-012** | `POST /api/v1/trade/signal` | Trade signal routing | - Routes signal through workflow<br>- Pattern → Technical → Risk → Trading<br>- Returns decision |
| **WORK-013** | `POST /api/v1/risk/update` | Risk parameter update | - Updates risk parameters<br>- Validates new limits<br>- Applies immediately<br>- Confirms update |
| **WORK-014** | Mode Adaptation | Aggressive/Normal/Conservative | - Thresholds adjust by mode<br>- Scan frequency changes<br>- Risk multiplier applied |
| **WORK-015** | State Machine | Workflow state transitions | - SCANNING → FILTERING_NEWS → PATTERN_ANALYSIS → TECHNICAL_ANALYSIS → RISK_VALIDATION → EXECUTING → MONITORING<br>- All transitions logged |
| **WORK-016** | Error Recovery | Failed service calls | - Retries on transient errors<br>- Skips failed candidates<br>- Workflow continues<br>- Logs failures |
| **WORK-017** | Health Check | Service availability | - `GET /health` endpoint<br>- Returns 200 OK<br>- Service metadata included |

**Success Measurement:**
- ✅ All 17 tests pass
- ✅ Complete 100→35→20→10→5 filter cascade
- ✅ Total workflow time < 60 seconds
- ✅ All stages logged and traceable
- ✅ Error handling prevents cascade failures
- ✅ **Core business logic correctly implemented**

---

### 2.3 Scanner Service (Port 5001 - REST)

#### Test Suite: test_scanner_service.py

*No changes from v1.0 - Scanner service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **SCAN-001** | `POST /api/v1/scan` | Market scanning | - Returns 100 candidates<br>- Sorted by composite_score DESC<br>- Duration < 5s |
| **SCAN-002** | Volume Filtering | Min volume requirements | - All candidates meet volume threshold<br>- volume_ratio calculated correctly<br>- No low-liquidity stocks |
| **SCAN-003** | Price Filtering | Price range enforcement | - All prices in [1.00, 500.00] range<br>- No penny stocks<br>- No ETFs/crypto |
| **SCAN-004** | Momentum Scoring | Momentum calculation | - momentum_score in [0.0, 1.0]<br>- Based on price change + volume<br>- Normalized correctly |
| **SCAN-005** | Composite Scoring | Multi-factor score | - composite_score = weighted average<br>- All factors represented<br>- Score in [0.0, 1.0] |
| **SCAN-006** | Database Persistence | scan_results table | - Results saved with cycle_id<br>- Uses security_id FK (not symbol)<br>- Timestamp accurate |
| **SCAN-007** | Real-time Data | Market data freshness | - Data < 15 seconds old<br>- Pre-market data available<br>- After-hours handling |

**Success Measurement:**
- ✅ All 7 tests pass
- ✅ Scan completes in < 5 seconds
- ✅ 100% of results meet criteria
- ✅ Database writes succeed
- ✅ No duplicate entries

---

### 2.4 Pattern Service (Port 5002 - REST)

#### Test Suite: test_pattern_service.py

*No changes from v1.0 - Pattern service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **PAT-001** | `POST /api/v1/analyze` | Pattern detection | - Detects Ross Cameron patterns<br>- Returns pattern list<br>- Confidence scores included |
| **PAT-002** | Breakout Patterns | Bull flag, cup & handle | - Identifies breakout structures<br>- Calculates breakout levels<br>- Volume confirmation |
| **PAT-003** | Momentum Patterns | Consecutive green candles | - Detects momentum sequences<br>- Validates with volume<br>- Identifies pullbacks |
| **PAT-004** | Reversal Patterns | Hammer, morning star | - Identifies reversal signals<br>- Support/resistance context<br>- Risk/reward ratios |
| **PAT-005** | Pattern Confidence | Quality scoring | - Confidence in [0.0, 1.0]<br>- Based on structure + volume<br>- Filters confidence < 0.6 |
| **PAT-006** | Multi-Timeframe | 1min, 5min, 15min | - Analyzes all timeframes<br>- Identifies alignment<br>- Higher confidence when aligned |
| **PAT-007** | Database Persistence | pattern_analysis table | - Patterns saved with confidence<br>- Links to security_id<br>- Metadata preserved |

**Success Measurement:**
- ✅ All 7 tests pass
- ✅ Pattern detection < 1s per symbol
- ✅ Confidence scores accurate
- ✅ All pattern types supported
- ✅ Database writes succeed

---

### 2.5 Technical Analysis Service (Port 5003 - REST)

#### Test Suite: test_technical_service.py

*No changes from v1.0 - Technical service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **TECH-001** | `GET /api/v1/indicators/{symbol}` | Indicator calculation | - RSI, MACD, ATR calculated<br>- All timeframes supported<br>- Values within expected ranges |
| **TECH-002** | Moving Averages | SMA, EMA | - SMA(20, 50, 200) correct<br>- EMA(9, 21) correct<br>- Crossovers detected |
| **TECH-003** | Momentum Indicators | RSI, MACD, Stochastic | - RSI in [0, 100]<br>- MACD histogram correct<br>- Stochastic in [0, 100] |
| **TECH-004** | Volatility Indicators | ATR, Bollinger Bands | - ATR(14) calculated<br>- BB(20, 2) correct<br>- Squeeze detection |
| **TECH-005** | Volume Analysis | OBV, Volume Ratio | - OBV calculation correct<br>- Volume ratio vs average<br>- VPOC identified |
| **TECH-006** | Support/Resistance | Dynamic levels | - S/R levels identified<br>- Proximity to price noted<br>- Strength scored |
| **TECH-007** | Signal Generation | Buy/Sell signals | - Signals from multiple indicators<br>- signal_strength score<br>- Entry/exit levels |
| **TECH-008** | Database Persistence | technical_indicators table | - Indicators saved per timeframe<br>- Uses security_id + time_id FKs<br>- Historical data preserved |

**Success Measurement:**
- ✅ All 8 tests pass
- ✅ Indicator calculation < 500ms
- ✅ Mathematical accuracy verified
- ✅ Signal generation logical
- ✅ Database writes succeed

---

### 2.6 Risk Manager Service (Port 5004 - REST)

#### Test Suite: test_risk_manager_service.py

*No changes from v1.0 - Risk Manager service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **RISK-001** | `POST /api/v1/validate` | Trade validation | - Validates against all limits<br>- Returns approved/rejected<br>- Provides rejection reason |
| **RISK-002** | Position Sizing | Kelly Criterion | - Calculates optimal size<br>- Applies risk_level (1-2% capital)<br>- Never exceeds max position |
| **RISK-003** | Daily Loss Limit | Account protection | - Tracks daily P&L<br>- Rejects when limit hit<br>- Triggers emergency stop |
| **RISK-004** | Position Limits | Max concurrent positions | - Enforces max_positions (5)<br>- Considers open + pending<br>- Rejects when maxed |
| **RISK-005** | Exposure Limits | Total capital at risk | - Calculates total exposure<br>- Never exceeds 10% account<br>- Sector diversification |
| **RISK-006** | Risk Budget | Per-cycle budget | - Allocates risk per cycle<br>- Tracks used vs available<br>- Prevents over-allocation |
| **RISK-007** | Stop Loss Calculation | Risk-based stops | - ATR-based stop distance<br>- Never > 2% account risk<br>- Minimum tick size respected |
| **RISK-008** | Emergency Stop | Circuit breaker | - Triggers at -daily_loss_limit<br>- Closes all positions<br>- Prevents new trades |
| **RISK-009** | Database Persistence | risk_parameters table | - Parameters saved per cycle<br>- Risk metrics updated real-time<br>- Audit trail maintained |

**Success Measurement:**
- ✅ All 9 tests pass
- ✅ Validation time < 50ms
- ✅ 100% compliance with limits
- ✅ Emergency stop works
- ✅ Position sizing accurate

---

### 2.7 Trading Execution Service (Port 5005 - REST)

#### Test Suite: test_trading_service.py

*No changes from v1.0 - Trading service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **TRADE-001** | `POST /api/v1/execute` | Order placement | - Places order via Alpaca<br>- Returns order confirmation<br>- Updates positions table |
| **TRADE-002** | Order Types | Market, Limit, Stop | - Supports all order types<br>- Parameters validated<br>- Price limits respected |
| **TRADE-003** | Position Tracking | Open positions | - Creates position record<br>- Links to cycle_id<br>- Uses security_id FK |
| **TRADE-004** | Stop Loss Orders | Protective stops | - Places stop-loss with entry<br>- Trailing stop updates<br>- Auto-closes on trigger |
| **TRADE-005** | Take Profit Orders | Profit targets | - Places take-profit order<br>- Multiple targets supported<br>- Partial position closes |
| **TRADE-006** | Position Closing | Exit management | - Closes positions on signal<br>- Calculates P&L<br>- Updates realized_pnl |
| **TRADE-007** | Order Status Monitoring | Alpaca webhooks | - Receives order updates<br>- Updates position status<br>- Handles rejections |
| **TRADE-008** | Emergency Close | Market close all | - Closes all positions immediately<br>- Market orders used<br>- Risk manager notified |
| **TRADE-009** | Database Persistence | positions + orders tables | - Position tracking accurate<br>- Order history complete<br>- P&L calculations correct |

**Success Measurement:**
- ✅ All 9 tests pass
- ✅ Order placement < 200ms
- ✅ 100% order tracking accuracy
- ✅ P&L calculations correct
- ✅ Stop-loss functionality verified

---

### 2.8 News Intelligence Service (Port 5008 - REST)

#### Test Suite: test_news_service.py

*No changes from v1.0 - News service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **NEWS-001** | `POST /api/v1/analyze` | News catalyst detection | - Fetches recent news<br>- Returns sentiment + catalysts<br>- catalyst_score calculated |
| **NEWS-002** | Sentiment Analysis | NLP processing | - Sentiment in [-1.0, 1.0]<br>- Bullish/bearish classification<br>- Confidence score included |
| **NEWS-003** | Catalyst Identification | Event detection | - Earnings, FDA, M&A, etc.<br>- Catalyst type classified<br>- Impact score estimated |
| **NEWS-004** | News Freshness | Time-based filtering | - Only recent news (< 24h)<br>- Pre-market emphasis<br>- Source quality considered |
| **NEWS-005** | Relevance Scoring | Stock-specific news | - Filters irrelevant articles<br>- Company/ticker mentioned<br>- relevance_score calculated |
| **NEWS-006** | Database Persistence | news_sentiment table | - News saved per security<br>- Links to security_id + time_id<br>- Deduplication handled |

**Success Measurement:**
- ✅ All 6 tests pass
- ✅ News fetch < 2s per symbol
- ✅ Sentiment accuracy verified
- ✅ Catalyst detection reliable
- ✅ Database writes succeed

---

### 2.9 Reporting Service (Port 5009 - REST)

#### Test Suite: test_reporting_service.py

*No changes from v1.0 - Reporting service unchanged*

| Test ID | Function Under Test | Measures | Success Criteria |
|---------|-------------------|----------|------------------|
| **REPORT-001** | `GET /api/v1/performance` | Performance metrics | - Returns daily/weekly/monthly P&L<br>- Win rate calculated<br>- Sharpe ratio computed |
| **REPORT-002** | Trade Analytics | Per-trade statistics | - Average win/loss<br>- Hold time analysis<br>- Best/worst trades |
| **REPORT-003** | Risk Metrics | Risk-adjusted returns | - Max drawdown<br>- Risk/reward ratios<br>- Capital preservation |
| **REPORT-004** | Pattern Performance | Strategy analysis | - P&L by pattern type<br>- Pattern success rates<br>- Optimal conditions |
| **REPORT-005** | Daily Summary | End-of-day report | - Total P&L<br>- Trades executed<br>- Risk metrics<br>- Top performers |

**Success Measurement:**
- ✅ All 5 tests pass
- ✅ Report generation < 1s
- ✅ Calculations accurate
- ✅ Historical data accessible

---

## 3. Workflow Testing

### 3.1 Complete Trading Cycle (E2E) ✅ **UPDATED**

#### Test Suite: test_trading_cycle_workflow_v50.py

**Updated Flow**: Claude → Orchestration → **Workflow** → Other Services

| Test ID | Workflow Phase | Measures | Success Criteria |
|---------|---------------|----------|------------------|
| **WF-E2E-001** | **Initialization** | `start_trading_cycle()` | - **Claude calls Orchestration tool**<br>- **Orchestration calls Workflow POST /api/v1/cycle/start**<br>- Workflow creates cycle in database<br>- Status = ACTIVE<br>- All services healthy |
| **WF-E2E-002** | **Stage 1: Scan** | 100 candidates identified | - **Workflow calls Scanner**<br>- Scanner returns 100 stocks<br>- Volume + price filters applied<br>- Results in scan_results table<br>- Duration < 10s |
| **WF-E2E-003** | **Stage 2: News** | 100 → 35 filter | - **Workflow calls News** for all 100<br>- Sentiment filtering applied<br>- 35 candidates remain<br>- Duration < 20s |
| **WF-E2E-004** | **Stage 3: Pattern** | 35 → 20 filter | - **Workflow calls Pattern** on 35<br>- Confidence ≥ 0.6 required<br>- 20 candidates remain<br>- Duration < 30s |
| **WF-E2E-005** | **Stage 4: Technical** | 20 → 10 filter | - **Workflow calls Technical** for 20<br>- Signal strength scored<br>- 10 candidates remain<br>- Duration < 15s |
| **WF-E2E-006** | **Stage 5: Risk** | 10 → 5 approval | - **Workflow calls Risk Manager** for each<br>- Position sizing calculated<br>- 5 approved for trading<br>- Duration < 5s |
| **WF-E2E-007** | **Stage 6: Execute** | 5 trades placed | - **Workflow calls Trading** service<br>- Orders placed via Alpaca<br>- Positions created<br>- Stop-loss orders set<br>- Duration < 10s |
| **WF-E2E-008** | **Monitoring** | Position management | - Real-time P&L tracking<br>- Trailing stops updated<br>- Risk limits monitored<br>- Continuous |
| **WF-E2E-009** | **Closing** | End-of-day close | - **Workflow closes** all positions<br>- P&L calculated<br>- Performance saved<br>- Cycle completed |
| **WF-E2E-010** | **Complete Cycle** | Start to finish | - Total time < 90 seconds<br>- All stages logged<br>- Database consistent<br>- No errors<br>- **Orchestration → Workflow → Services flow verified** |

**Success Measurement:**
- ✅ Complete 100→35→20→10→5 cascade
- ✅ Total cycle time < 90 seconds
- ✅ 5 trades executed successfully
- ✅ All data persisted correctly
- ✅ Risk limits enforced throughout
- ✅ **Orchestration → Workflow delegation works correctly**

---

### 3.2 Mode Variations

#### Test Suite: test_trading_modes.py

*No changes from v1.0 - Mode variations unchanged*

| Test ID | Mode | Parameter Variations | Success Criteria |
|---------|------|---------------------|------------------|
| **MODE-001** | **Aggressive** | - Scan frequency: 60s<br>- sentiment_threshold: 0.2<br>- pattern_confidence: 0.5<br>- risk_multiplier: 1.5 | - More frequent scans<br>- Lower filter thresholds<br>- Higher risk per trade<br>- More trades executed |
| **MODE-002** | **Normal** | - Scan frequency: 300s<br>- sentiment_threshold: 0.3<br>- pattern_confidence: 0.6<br>- risk_multiplier: 1.0 | - Standard scanning<br>- Moderate thresholds<br>- Standard risk levels<br>- Balanced trading |
| **MODE-003** | **Conservative** | - Scan frequency: 900s<br>- sentiment_threshold: 0.5<br>- pattern_confidence: 0.7<br>- risk_multiplier: 0.5 | - Infrequent scans<br>- High filter thresholds<br>- Lower risk per trade<br>- Fewer trades |
| **MODE-004** | **Mode Switching** | Change mode mid-cycle | - Mode updates immediately<br>- Next scan uses new params<br>- Open positions unaffected<br>- Logged in database |

**Success Measurement:**
- ✅ Each mode produces different results
- ✅ Thresholds applied correctly
- ✅ Risk scaling works
- ✅ Mode switching seamless

---

## 4. Integration Testing

### 4.1 Service-to-Service Communication ✅ **UPDATED**

#### Test Suite: test_service_integration_v50.py

**Key Update**: Added Orchestration ↔ Workflow integration tests

| Test ID | Integration | Tests | Success Criteria |
|---------|-------------|-------|------------------|
| **INT-001** | **Orchestration ↔ Workflow** ✅ **NEW** | MCP to REST translation | - **MCP tool calls invoke Workflow REST APIs**<br>- Status updates returned<br>- Errors propagated correctly<br>- All tools tested |
| **INT-002** | **Workflow ↔ Scanner** | Scan coordination | - Workflow triggers scan<br>- Results returned correctly<br>- Timeout handling works |
| **INT-003** | **Workflow ↔ Pattern** | Pattern coordination | - Workflow sends candidates<br>- Patterns returned<br>- Batch processing efficient |
| **INT-004** | **Workflow ↔ Technical** | Technical coordination | - Indicators requested<br>- Signals generated<br>- Multi-symbol batching |
| **INT-005** | **Workflow ↔ Risk Manager** | Risk validation | - Validation requests processed<br>- Sizing calculations returned<br>- Rejections handled |
| **INT-006** | **Workflow ↔ Trading** | Trade execution | - Orders placed successfully<br>- Status updates received<br>- Position tracking linked |
| **INT-007** | **Workflow ↔ News** | News enrichment | - News fetched per candidate<br>- Sentiment scores returned<br>- Catalyst flags set |
| **INT-008** | **All Services ↔ Database** | Database access | - All services read/write correctly<br>- Foreign keys respected<br>- Transactions isolated |
| **INT-009** | **Orchestration Resources** ✅ **NEW** | Read-only data access | - Resources query Workflow/other services<br>- No direct DB access from Orchestration<br>- Formatted for Claude |

**Success Measurement:**
- ✅ All 9 integrations pass
- ✅ No timeout errors
- ✅ Error handling works
- ✅ Data consistency maintained
- ✅ **Orchestration → Workflow → Services chain verified**

---

## 5. Database Testing

### 5.1 Schema Validation

#### Test Suite: test_database_schema.py

*No changes from v1.0 - Database schema unchanged*

| Test ID | Schema Component | Validates | Success Criteria |
|---------|-----------------|-----------|------------------|
| **DB-001** | **Table Existence** | All v5.0 tables present | - 20+ tables created<br>- Correct column types<br>- Indexes present |
| **DB-002** | **Foreign Keys** | Referential integrity | - All FKs defined<br>- Cascade rules correct<br>- No orphaned records |
| **DB-003** | **Normalization** | 3NF compliance | - No symbol duplication<br>- securities table authoritative<br>- All FKs use security_id |
| **DB-004** | **Constraints** | Data validation | - NOT NULL enforced<br>- CHECK constraints work<br>- Unique constraints valid |
| **DB-005** | **Indexes** | Query performance | - Primary keys indexed<br>- Foreign keys indexed<br>- Composite indexes optimal |
| **DB-006** | **Triggers** | Automated updates | - updated_at triggers fire<br>- Audit triggers work<br>- Calculated fields update |

**Success Measurement:**
- ✅ Schema matches v5.0 specification
- ✅ All constraints enforced
- ✅ Referential integrity maintained
- ✅ Indexes optimize queries

---

### 5.2 Data Integrity

#### Test Suite: test_data_integrity.py

*No changes from v1.0 - Data integrity tests unchanged*

| Test ID | Data Component | Validates | Success Criteria |
|---------|---------------|-----------|------------------|
| **DATA-001** | **Trading Cycles** | Cycle lifecycle | - Cycle creation valid<br>- Status transitions correct<br>- Risk metrics updated |
| **DATA-002** | **Positions** | Position tracking | - Positions link to cycles<br>- P&L calculations correct<br>- Close reasons logged |
| **DATA-003** | **Scan Results** | Scanner data | - Results link to cycles<br>- Composite scores valid<br>- Ranking correct |
| **DATA-004** | **Orders** | Trade execution | - Orders link to positions<br>- Status updates tracked<br>- Fills recorded |
| **DATA-005** | **Cross-Table** | Referential integrity | - No orphaned FKs<br>- Cascade deletes work<br>- Joins performant |

**Success Measurement:**
- ✅ All data relationships valid
- ✅ No data corruption
- ✅ Audit trails complete
- ✅ Historical data preserved

---

## 6. Performance Testing

### 6.1 Response Time Requirements ✅ **UPDATED**

#### Test Suite: test_performance_v50.py

**Key Updates**: Added Orchestration → Workflow latency testing

| Test ID | Operation | Target | Measurement | Success Criteria |
|---------|-----------|--------|-------------|------------------|
| **PERF-001** | **MCP Resource Read** ✅ **UPDATED** | < 500ms | Resource query via Orchestration | - 95th percentile < 500ms<br>- **Includes Orchestration → Service call**<br>- Caching works |
| **PERF-002** | **MCP Tool Execution** ✅ **UPDATED** | < 2s | Tool call via Orchestration | - 95th percentile < 2s<br>- **Includes Orchestration → Workflow → Service chain**<br>- No blocking |
| **PERF-003** | **Workflow API Call** ✅ **NEW** | < 500ms | Direct Workflow REST call | - Average < 500ms<br>- 99th percentile < 1s |
| **PERF-004** | **Market Scan** | < 5s | End-to-end scan of 100 stocks | - 95th percentile < 5s<br>- No timeouts<br>- Consistent performance |
| **PERF-005** | **Pattern Analysis** | < 1s per symbol | Pattern detection per stock | - Average < 1s<br>- 99th percentile < 2s |
| **PERF-006** | **Technical Indicators** | < 500ms | Indicator calculation per symbol | - Average < 500ms<br>- All timeframes processed |
| **PERF-007** | **Risk Validation** | < 50ms | Risk check per trade | - 99th percentile < 100ms<br>- No blocking |
| **PERF-008** | **Trade Execution** | < 200ms | Order placement | - Average < 200ms<br>- Alpaca latency considered |
| **PERF-009** | **Complete Workflow** ✅ **UPDATED** | < 90s | 100→5 cascade + execution | - 95th percentile < 90s<br>- **Includes Orchestration → Workflow overhead**<br>- No stage bottlenecks |
| **PERF-010** | **Database Queries** | < 100ms | Common queries | - Indexed queries < 50ms<br>- Aggregations < 100ms |

**Success Measurement:**
- ✅ All targets met at 95th percentile
- ✅ No performance degradation over time
- ✅ System handles market open volatility
- ✅ Scalable to increased volume
- ✅ **Orchestration → Workflow overhead minimal (<50ms)**

---

### 6.2 Throughput Testing

#### Test Suite: test_throughput.py

*No changes from v1.0 - Throughput tests unchanged*

| Test ID | Scenario | Load | Success Criteria |
|---------|----------|------|------------------|
| **THRU-001** | **Concurrent Scans** | 10 scans simultaneously | - All complete successfully<br>- No resource exhaustion<br>- Response times stable |
| **THRU-002** | **High-Frequency Mode** | 60-second scan intervals | - Sustained over 1 hour<br>- No memory leaks<br>- CPU usage acceptable |
| **THRU-003** | **Position Monitoring** | 50 open positions | - Real-time updates<br>- No lag in P&L calculations<br>- Stop-loss triggers immediate |

**Success Measurement:**
- ✅ System stable under load
- ✅ No resource leaks
- ✅ Graceful degradation if limits hit

---

## 7. Risk Management Testing

### 7.1 Risk Controls Validation

#### Test Suite: test_risk_controls.py

*No changes from v1.0 - Risk controls unchanged*

| Test ID | Risk Control | Test Scenario | Success Criteria |
|---------|--------------|---------------|------------------|
| **RISK-C-001** | **Daily Loss Limit** | Simulate losing trades hitting limit | - Trading stops when limit hit<br>- No new positions opened<br>- Alert sent to Claude |
| **RISK-C-002** | **Position Limits** | Attempt to exceed max positions | - 6th position rejected<br>- Clear rejection reason<br>- Risk budget preserved |
| **RISK-C-003** | **Position Sizing** | Various account sizes | - Never exceeds 2% risk per trade<br>- Scales with account size<br>- Minimum tick size respected |
| **RISK-C-004** | **Stop Loss** | Price moves against position | - Stop triggered automatically<br>- Position closed at/near stop<br>- Slippage recorded |
| **RISK-C-005** | **Emergency Stop** | Critical risk breach | - All positions closed<br>- Trading halted<br>- Manual restart required |
| **RISK-C-006** | **Exposure Limits** | Sector concentration | - Max 30% in one sector<br>- Diversification enforced<br>- Correlation considered |

**Success Measurement:**
- ✅ All risk limits enforced
- ✅ No limit bypasses possible
- ✅ Emergency procedures work
- ✅ Capital preserved in worst case

---

## 8. Test Execution Plan

### 8.1 Test Phases

```
Phase 1: Unit Tests (Week 1)
├── Individual service functions
├── Database operations
└── Utility functions

Phase 2: Component Tests (Week 2)
├── Orchestration service (MCP-only) ✅ UPDATED
├── Workflow service (NEW) ✅ NEW
├── Scanner, Pattern, Technical services
├── Risk Manager, Trading services
└── News, Reporting services

Phase 3: Integration Tests (Week 3)
├── Orchestration → Workflow ✅ NEW
├── Workflow → All services
├── Service-to-service communication
├── Database integration
└── External API integration

Phase 4: Workflow Tests (Week 4)
├── Complete trading cycles
├── Mode variations
└── Edge cases

Phase 5: Performance Tests (Week 5)
├── Load testing
├── Stress testing
├── Orchestration → Workflow latency ✅ NEW
└── Endurance testing

Phase 6: UAT (Week 6)
├── Real market conditions
├── Paper trading validation
└── Final approval
```

### 8.2 Test Data Strategy

| Data Type | Source | Approach |
|-----------|--------|----------|
| **Historical Market Data** | Alpaca API | - Use past trading days<br>- Known patterns/outcomes<br>- Reproducible scenarios |
| **Test Securities** | Fixed symbols | - AAPL, TSLA, NVDA, AMD, META<br>- Known characteristics<br>- Active liquidity |
| **Mock News** | Synthetic | - Predefined catalysts<br>- Controlled sentiment<br>- Reproducible |
| **Simulated Trades** | Paper trading | - Real market orders<br>- No real capital<br>- Alpaca paper account |

---

## 9. Success Criteria

### 9.1 Overall System Success

| Category | Metric | Target | Critical |
|----------|--------|--------|----------|
| **Functional** | Tests passing | 100% | ✅ YES |
| **Performance** | Workflow completion | < 90s | ✅ YES |
| **Reliability** | Uptime | > 99.9% | ✅ YES |
| **Accuracy** | Signal quality | Win rate ≥ 60% | ✅ YES |
| **Risk** | No limit breaches | 100% compliance | ✅ YES |
| **Data** | Referential integrity | 100% | ✅ YES |
| **Architecture** ✅ **NEW** | Orchestration delegation | 100% to Workflow | ✅ YES |

### 9.2 Per-Component Success ✅ **UPDATED**

| Component | Pass Criteria |
|-----------|---------------|
| **Orchestration** | **All MCP operations work, NO business logic, all tools delegate to Workflow, < 500ms response** ✅ **UPDATED** |
| **Workflow** | **Complete 100→5 cascade in < 60s, all service coordination works** ✅ **NEW** |
| **Scanner** | 100 candidates in < 5s, meets criteria |
| **Pattern** | Detects patterns with ≥ 60% accuracy |
| **Technical** | Indicators calculated correctly, < 500ms |
| **Risk Manager** | 100% limit enforcement, no breaches |
| **Trading** | Orders execute successfully, P&L accurate |
| **News** | Sentiment scores reasonable, catalysts identified |
| **Reporting** | Accurate metrics, < 1s generation |

### 9.3 Quality Gates

```
Gate 1: Unit Tests
├── 100% pass required
└── Proceed to Component Tests

Gate 2: Component Tests
├── 100% pass required
├── Orchestration MCP-only verified ✅ NEW
├── Workflow coordination verified ✅ NEW
└── Proceed to Integration Tests

Gate 3: Integration Tests
├── 100% pass required
├── Orchestration → Workflow verified ✅ NEW
├── Performance targets met
└── Proceed to Workflow Tests

Gate 4: Workflow Tests
├── 100% pass required
├── E2E cycle succeeds
├── 9-service architecture validated ✅ NEW
└── Proceed to UAT

Gate 5: UAT
├── Paper trading successful
├── Risk controls validated
└── PRODUCTION READY ✅
```

---

## 10. Test Environment Setup

### 10.1 Environment Requirements

```yaml
Test Environment:
  - Docker Compose (all 9 services) ✅ UPDATED
  - PostgreSQL 15 (test database)
  - Redis 7 (test cache)
  - Python 3.11+ (pytest)
  - Alpaca Paper Trading Account
  - Mock News API (or real with low quotas)

Services to Deploy:
  1. Orchestration (Port 5000 - MCP)
  2. Workflow (Port 5006 - REST) ✅ NEW
  3. Scanner (Port 5001 - REST)
  4. Pattern (Port 5002 - REST)
  5. Technical (Port 5003 - REST)
  6. Risk Manager (Port 5004 - REST)
  7. Trading (Port 5005 - REST)
  8. News (Port 5008 - REST)
  9. Reporting (Port 5009 - REST)

Hardware:
  - 4 CPU cores minimum
  - 8GB RAM minimum (9 services now) ✅ UPDATED
  - SSD for database

Network:
  - Internet connectivity (APIs)
  - Low latency to Alpaca (< 100ms)
```

### 10.2 Test Tools

| Tool | Purpose | Version |
|------|---------|---------|
| **pytest** | Test framework | 7.4+ |
| **pytest-asyncio** | Async testing | 0.21+ |
| **httpx** | HTTP client | 0.24+ |
| **asyncpg** | PostgreSQL driver | 0.28+ |
| **pytest-benchmark** | Performance tests | 4.0+ |
| **locust** | Load testing | 2.15+ |
| **docker-compose** | Environment | 2.20+ |
| **mcp-client** ✅ **NEW** | MCP protocol testing | Latest |

### 10.3 CI/CD Integration

```yaml
GitHub Actions Workflow:
  - Trigger: On push to main/develop
  - Steps:
    1. Checkout code
    2. Start Docker services (9 services) ✅ UPDATED
    3. Run database migrations
    4. Wait for Workflow service ready ✅ NEW
    5. Execute test suite
    6. Generate coverage report
    7. Performance benchmarks
    8. Deploy if all pass
```

---

## Conclusion

This comprehensive testing plan v2.0 ensures the Catalyst Trading System **9-service architecture** meets all design specifications, performance requirements, and risk management objectives. 

### Key Updates from v1.0:

1. ✅ **Orchestration Service** - Now MCP-only (no business logic)
2. ✅ **Workflow Service** - NEW service with all coordination logic
3. ✅ **Integration Tests** - Added Orchestration ↔ Workflow tests
4. ✅ **Performance Tests** - Added latency testing for service chain
5. ✅ **Quality Gates** - Added architecture validation gates

### Validation Checklist:

1. ✅ **Functional Requirements** - All features work as designed per v5.0
2. ✅ **Performance Requirements** - System meets speed/throughput targets
3. ✅ **Risk Management** - Capital protection enforced at all times
4. ✅ **Data Integrity** - Database normalized and consistent
5. ✅ **Reliability** - System handles errors and edge cases
6. ✅ **Scalability** - 9-service architecture supports growth
7. ✅ **Architecture** - Orchestration → Workflow separation verified

**Next Steps:**
1. Review and approve testing plan v2.0
2. Set up test environment with 9 services
3. Implement test suites
4. Execute testing phases
5. Document results
6. Fix any issues found
7. Retest until 100% pass
8. Proceed to production deployment

---

**Testing Principle:** *"Test what you fly, fly what you test"*

This plan ensures comprehensive validation of the **9-service architecture** before risking real capital in live markets.

---

**Document Status:** ✅ **APPROVED FOR IMPLEMENTATION**  
**Based On:** Functional Specification v5.0.0 (2025-10-22)  
**Architecture:** 9-Service with Orchestration/Workflow separation
