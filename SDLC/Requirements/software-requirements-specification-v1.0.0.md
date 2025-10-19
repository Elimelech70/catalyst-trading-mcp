# Catalyst Trading System - Software Requirements Specification (SRS)

**Name of Application**: Catalyst Trading System  
**Name of file**: software-requirements-specification-v10.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-18  
**Derived From**: functional-spec-mcp-v41.md + Ross Cameron Day Trading Methodology  
**Purpose**: Formal software requirements specification for development and validation

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-10-18 | Claude (Requirements Phase) | Initial SRS derived from functional spec v4.1 |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [User Requirements](#5-user-requirements)
6. [External Interface Requirements](#6-external-interface-requirements)
7. [Data Requirements](#7-data-requirements)
8. [Performance Requirements](#8-performance-requirements)
9. [Security Requirements](#9-security-requirements)
10. [Ross Cameron Trading Requirements](#10-ross-cameron-trading-requirements)
11. [Acceptance Criteria](#11-acceptance-criteria)
12. [Constraints & Assumptions](#12-constraints--assumptions)

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) defines the requirements for the Catalyst Trading System, an intelligent day trading platform implementing Ross Cameron momentum trading methodology with AI-assisted decision making.

### 1.2 Scope
The system provides:
- Automated market scanning with multi-stage filtering (100 → 5 stocks)
- Pattern recognition and technical analysis
- News catalyst detection and sentiment analysis
- Risk-managed trade execution
- AI-powered trading assistance via Claude Desktop
- Real-time performance tracking and reporting

### 1.3 Definitions
| Term | Definition |
|------|------------|
| **MCP** | Model Context Protocol - Communication protocol for Claude |
| **Catalyst** | News event that drives significant price movement |
| **Cycle** | Complete trading workflow from scan to close |
| **Candidate** | Stock that passes filtering criteria |
| **Signal** | Confirmed trading opportunity with entry/exit levels |
| **Ross Cameron Strategy** | Momentum-based day trading methodology |

### 1.4 References
- functional-spec-mcp-v41.md - Functional specification v4.1.0
- database-schema-mcp-v50.md - Database schema v5.0
- architecture-mcp-v41.md - System architecture v4.1.0
- Ross Cameron day trading methodology
- phase1-trading-workflow-v42.md - Trading workflow specification

---

## 2. System Overview

### 2.1 System Context
The Catalyst Trading System is a hybrid architecture combining:
- **MCP Protocol**: Single orchestration service for Claude interaction
- **REST APIs**: Internal microservices for business logic
- **PostgreSQL**: Normalized database (v5.0 schema)
- **Redis**: Caching and pub/sub messaging
- **External APIs**: Alpaca (trading), news sources, market data

### 2.2 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              CATALYST TRADING SYSTEM                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐         ┌──────────────┐            │
│  │ Claude Desktop│◄────────┤Orchestration │            │
│  │   (User)     │  MCP    │Service (5000)│            │
│  └──────────────┘         └──────┬───────┘            │
│                                  │ REST                │
│         ┌────────────────────────┼──────────┐         │
│         │         │         │    │     │    │         │
│    ┌────▼──┐ ┌───▼───┐ ┌──▼──┐ ┌▼──┐ ┌▼──┐ ┌▼──┐    │
│    │Scanner│ │Pattern│ │Tech │ │News│ │Trd│ │Rpt│    │
│    │ 5001  │ │ 5002  │ │5003 │ │5008│ │505│ │509│    │
│    └───┬───┘ └───┬───┘ └──┬──┘ └─┬──┘ └─┬─┘ └─┬─┘    │
│        │         │         │      │      │     │      │
│        └─────────┴─────────┴──────┴──────┴─────┘      │
│                          │                             │
│                  ┌───────▼────────┐                    │
│                  │  PostgreSQL    │                    │
│                  │  (v5.0 Schema) │                    │
│                  └────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Service Matrix

| Service | Type | Port | Primary Responsibility |
|---------|------|------|------------------------|
| Orchestration | MCP | 5000 | Claude interface, workflow coordination |
| Scanner | REST | 5001 | Market scanning (100→35→20→10→5) |
| Pattern | REST | 5002 | Pattern detection and confidence scoring |
| Technical | REST | 5003 | Technical indicators and signals |
| Trading | REST | 5005 | Order execution and position management |
| News | REST | 5008 | Catalyst detection and sentiment analysis |
| Reporting | REST | 5009 | Performance analytics and visualization |

---

## 3. Functional Requirements

### 3.1 Market Scanning (FR-SCAN)

#### FR-SCAN-001: Universe Selection
**Requirement**: System SHALL select initial universe of 100 most active stocks
**Priority**: CRITICAL
**Rationale**: Ross Cameron methodology focuses on high-volume momentum stocks

**Acceptance Criteria**:
- Retrieve top 100 stocks by dollar volume
- Filter by minimum volume: 1,000,000 shares/day
- Filter by price range: $1.00 - $500.00
- Update universe every scan cycle
- Complete selection in < 5 seconds

#### FR-SCAN-002: News Catalyst Filtering
**Requirement**: System SHALL filter universe to 35 stocks with news catalysts
**Priority**: CRITICAL
**Rationale**: News catalysts drive momentum moves

**Acceptance Criteria**:
- Check each stock for news in last 24 hours
- Calculate catalyst strength score (0.0 - 1.0)
- Filter for catalyst_score ≥ 0.3
- Categorize catalyst types (earnings, FDA, M&A, analyst, etc.)
- Complete filtering in < 10 seconds

#### FR-SCAN-003: Pattern Detection Filtering
**Requirement**: System SHALL detect patterns on 35 candidates, select top 20
**Priority**: CRITICAL
**Rationale**: Pattern confirmation reduces false signals

**Acceptance Criteria**:
- Detect patterns: breakout, momentum, reversal, consolidation
- Calculate pattern confidence (0.0 - 1.0)
- Filter for pattern_confidence ≥ 0.60
- Support multiple timeframes (1min, 5min, 15min)
- Complete detection in < 15 seconds

#### FR-SCAN-004: Technical Analysis Filtering
**Requirement**: System SHALL perform deep technical analysis, select top 10
**Priority**: CRITICAL
**Rationale**: Technical confirmation validates pattern signals

**Acceptance Criteria**:
- Calculate: RSI, MACD, Volume Profile, Support/Resistance
- Generate signal strength score (0.0 - 1.0)
- Filter for signal_strength ≥ 0.70
- Calculate entry, stop-loss, and take-profit levels
- Complete analysis in < 10 seconds

#### FR-SCAN-005: Final Selection
**Requirement**: System SHALL select final 5 stocks for trading
**Priority**: CRITICAL
**Rationale**: Focus on highest-conviction opportunities

**Acceptance Criteria**:
- Calculate composite score from all filters
- Rank by composite score
- Select top 5 candidates
- Store all candidates in scan_results table
- Flag selected candidates for trading

#### FR-SCAN-006: Scan Frequency
**Requirement**: System SHALL support configurable scan frequencies
**Priority**: HIGH
**Rationale**: Adapt to market conditions and user preference

**Acceptance Criteria**:
- Aggressive mode: 60-second scans
- Normal mode: 300-second (5-minute) scans
- Conservative mode: 900-second (15-minute) scans
- User can change mode during trading cycle
- Scan timing persists in database

---

### 3.2 Pattern Recognition (FR-PATTERN)

#### FR-PATTERN-001: Supported Patterns
**Requirement**: System SHALL detect Ross Cameron momentum patterns
**Priority**: CRITICAL
**Rationale**: Pattern-based entry is core to methodology

**Supported Patterns**:
- **Breakout Patterns**: Ascending triangle, bull flag, cup & handle
- **Momentum Patterns**: Consecutive green candles, volume spike, gap continuation
- **Reversal Patterns**: Hammer, morning star, bullish engulfing
- **Consolidation Patterns**: Tight range, decreasing volatility

**Acceptance Criteria**:
- Detect patterns across 1min, 5min, 15min timeframes
- Confidence score for each pattern (0.0 - 1.0)
- Identify breakout levels and targets
- Support pattern sub-types
- Store pattern analysis in pattern_analysis table

#### FR-PATTERN-002: Pattern Confidence Scoring
**Requirement**: System SHALL calculate pattern confidence based on quality
**Priority**: HIGH
**Rationale**: Filter weak patterns to reduce false signals

**Confidence Factors**:
- Pattern structure quality (0-40%)
- Volume confirmation (0-30%)
- Timeframe alignment (0-20%)
- Historical success rate (0-10%)

**Acceptance Criteria**:
- Confidence ≥ 0.80: High confidence
- Confidence 0.60-0.79: Medium confidence
- Confidence < 0.60: Low confidence (filtered out)
- Store confidence breakdown in metadata

---

### 3.3 Technical Analysis (FR-TECH)

#### FR-TECH-001: Core Indicators
**Requirement**: System SHALL calculate standard technical indicators
**Priority**: CRITICAL
**Rationale**: Technical confirmation validates trading signals

**Required Indicators**:
- **Moving Averages**: SMA(20, 50, 200), EMA(9, 21)
- **Momentum**: RSI(14), MACD, Stochastic
- **Volatility**: ATR(14), Bollinger Bands
- **Volume**: OBV, Volume Ratio, VPOC
- **Support/Resistance**: Dynamic levels

**Acceptance Criteria**:
- Calculate for 1min, 5min, 15min, 1hour, 1day timeframes
- Store in technical_indicators table with security_id + time_id FKs
- Update indicators real-time during market hours
- Flag unusual volume situations

#### FR-TECH-002: Signal Generation
**Requirement**: System SHALL generate trading signals from indicators
**Priority**: HIGH
**Rationale**: Objective entry/exit criteria

**Signal Types**:
- **Bullish**: RSI > 50, MACD crossover, volume spike, above VWAP
- **Bearish**: RSI < 50, MACD cross down, below VWAP
- **Neutral**: Consolidation, low volatility

**Acceptance Criteria**:
- Calculate signal strength (0.0 - 1.0)
- Require ≥ 3 confirming indicators
- Generate entry price ± 1 ATR
- Calculate stop-loss at support/resistance
- Calculate take-profit at 1.5-3.0 R:R ratio

---

### 3.4 News Intelligence (FR-NEWS)

#### FR-NEWS-001: News Collection
**Requirement**: System SHALL collect news from multiple sources
**Priority**: HIGH
**Rationale**: Comprehensive catalyst coverage

**News Sources**:
- Primary: Benzinga, Alpha Vantage
- Secondary: Finnhub, News API
- Earnings: Company filings

**Acceptance Criteria**:
- Poll sources every 5 minutes
- Store in news_sentiment table
- De-duplicate articles
- Track source reliability scores
- Handle API rate limits gracefully

#### FR-NEWS-002: Catalyst Detection
**Requirement**: System SHALL detect and categorize catalysts
**Priority**: CRITICAL
**Rationale**: Catalyst strength drives selection

**Catalyst Categories**:
- **Earnings**: Beats, misses, guidance
- **FDA**: Approvals, rejections, trials
- **M&A**: Acquisitions, mergers, buyouts
- **Analyst**: Upgrades, downgrades, initiations
- **Legal**: Lawsuits, settlements, regulatory
- **Product**: Launches, recalls, partnerships

**Acceptance Criteria**:
- Categorize with ≥ 90% accuracy
- Calculate catalyst_strength (0.0 - 1.0)
- Flag "very_strong" catalysts (≥ 0.8)
- Store metadata with source reliability

#### FR-NEWS-003: Sentiment Analysis
**Requirement**: System SHALL analyze sentiment of news articles
**Priority**: HIGH
**Rationale**: Sentiment confirms catalyst direction

**Sentiment Scoring**:
- Very Positive: +0.5 to +1.0
- Positive: +0.1 to +0.5
- Neutral: -0.1 to +0.1
- Negative: -0.5 to -0.1
- Very Negative: -1.0 to -0.5

**Acceptance Criteria**:
- Use VADER + TextBlob sentiment analysis
- Calculate polarity and subjectivity
- Store sentiment_score in news_sentiment
- Track price impact correlation

---

### 3.5 Trading Execution (FR-TRADE)

#### FR-TRADE-001: Order Management
**Requirement**: System SHALL manage order lifecycle
**Priority**: CRITICAL
**Rationale**: Reliable execution is essential

**Order Types**:
- Market orders (immediate execution)
- Limit orders (price-specific)
- Stop-loss orders (risk management)
- Trailing stop orders (profit protection)

**Acceptance Criteria**:
- Submit orders to Alpaca API
- Track order status real-time
- Store orders in orders table
- Handle partial fills
- Retry failed orders (3 attempts)
- Cancel stale orders

#### FR-TRADE-002: Position Management
**Requirement**: System SHALL track open positions
**Priority**: CRITICAL
**Rationale**: Portfolio tracking and risk management

**Position Tracking**:
- Entry price and quantity
- Current price and unrealized P&L
- Stop-loss and take-profit levels
- Position duration
- Trailing stop adjustments

**Acceptance Criteria**:
- Update positions every 1 second
- Calculate unrealized P&L real-time
- Store in positions table
- Trigger alerts on stop-loss hit
- Auto-close at take-profit

#### FR-TRADE-003: Risk Management
**Requirement**: System SHALL enforce risk limits
**Priority**: CRITICAL
**Rationale**: Capital preservation

**Risk Limits**:
- Max 2% account risk per trade
- Max 5 concurrent positions
- Max 4% daily loss limit
- Position sizing via Kelly Criterion
- Stop-loss required on all positions

**Acceptance Criteria**:
- Reject orders exceeding limits
- Calculate position size automatically
- Track daily P&L
- Auto-close all positions at daily loss limit
- Log all risk checks

---

### 3.6 Claude Integration (FR-CLAUDE)

#### FR-CLAUDE-001: MCP Resource Access
**Requirement**: System SHALL expose hierarchical MCP resources
**Priority**: HIGH
**Rationale**: Claude needs structured data access

**MCP Resources**:
```
trading-cycle/
  ├── current                 # Current cycle status
  ├── history                 # Historical cycles
  └── performance             # Cycle performance metrics

market-scan/
  ├── candidates              # All scanned candidates
  ├── active                  # Top 5 active candidates
  └── patterns                # Detected patterns

positions/
  ├── open                    # Current open positions
  ├── closed                  # Historical positions
  └── performance             # Position analytics

portfolio/
  ├── summary                 # Account summary
  ├── risk-metrics            # Risk analysis
  └── performance             # Performance metrics
```

**Acceptance Criteria**:
- All resources return JSON
- Include context parameters
- Response time < 200ms
- Proper error handling with McpError

#### FR-CLAUDE-002: MCP Tool Execution
**Requirement**: System SHALL provide trading tools via MCP
**Priority**: CRITICAL
**Rationale**: Claude must execute trading actions

**MCP Tools**:
- `start-trading-cycle`: Begin trading workflow
- `stop-trading-cycle`: End trading workflow
- `review-candidates`: Analyze scan results
- `execute-trade`: Submit trade order
- `close-position`: Exit trade
- `get-performance`: Retrieve metrics

**Acceptance Criteria**:
- Input validation on all tools
- Return structured responses
- Tool execution < 500ms
- Audit trail for all actions

---

### 3.7 Reporting & Analytics (FR-REPORT)

#### FR-REPORT-001: Performance Metrics
**Requirement**: System SHALL calculate trading performance metrics
**Priority**: HIGH
**Rationale**: Track system effectiveness

**Metrics Required**:
- Win rate (% profitable trades)
- Sharpe ratio (risk-adjusted returns)
- Max drawdown (worst loss period)
- Average risk:reward ratio
- Profit factor (gross wins / gross losses)
- Daily/weekly/monthly P&L

**Acceptance Criteria**:
- Update metrics real-time
- Store in performance tables
- Generate daily reports
- Compare to benchmarks
- Alert on degrading performance

#### FR-REPORT-002: Trade Analytics
**Requirement**: System SHALL analyze trade execution quality
**Priority**: MEDIUM
**Rationale**: Continuous improvement

**Analytics**:
- Entry timing accuracy
- Pattern success rates
- Catalyst effectiveness
- Indicator reliability
- Hold time analysis
- Slippage tracking

**Acceptance Criteria**:
- Store detailed trade data
- Generate weekly analysis reports
- Identify best/worst patterns
- Track improvement trends

---

## 4. Non-Functional Requirements

### 4.1 Performance (NFR-PERF)

#### NFR-PERF-001: Response Time
**Requirement**: System SHALL meet response time SLAs

| Operation | Target | Maximum |
|-----------|--------|---------|
| MCP resource queries | 50ms | 200ms |
| MCP tool executions | 100ms | 500ms |
| Market scans | 2s | 5s |
| Order execution | 100ms | 1s |
| Position updates | 50ms | 200ms |

#### NFR-PERF-002: Throughput
**Requirement**: System SHALL support required throughput

| Metric | Requirement |
|--------|-------------|
| Concurrent trading cycles | 1 (single user) |
| Scans per minute | 12 (5-second frequency) |
| Orders per minute | 20 maximum |
| MCP queries per second | 100 |
| Database connections | 50 pool max |

### 4.2 Reliability (NFR-REL)

#### NFR-REL-001: Uptime
**Requirement**: System SHALL achieve uptime targets

| Component | Target Uptime | Max Downtime/Month |
|-----------|---------------|-------------------|
| MCP Service | 99.9% | 43 minutes |
| REST APIs | 99.5% | 3.6 hours |
| Database | 99.95% | 22 minutes |
| Redis Cache | 99.9% | 43 minutes |

#### NFR-REL-002: Data Integrity
**Requirement**: System SHALL maintain data integrity
- All database operations use transactions
- Foreign key constraints enforced
- No orphaned records permitted
- Automatic backup every 24 hours
- Point-in-time recovery capability

### 4.3 Scalability (NFR-SCALE)

#### NFR-SCALE-001: Data Growth
**Requirement**: System SHALL handle data growth

| Data Type | Growth Rate | Retention |
|-----------|-------------|-----------|
| Price data | 100k rows/day | 2 years |
| News articles | 1k rows/day | 1 year |
| Trade history | 50 rows/day | Permanent |
| Scan results | 500 rows/day | 90 days |
| Technical indicators | 200k rows/day | 1 year |

### 4.4 Maintainability (NFR-MAINT)

#### NFR-MAINT-001: Code Quality
**Requirement**: System SHALL maintain code quality standards
- Type hints on all functions
- Docstrings on all public methods
- Test coverage ≥ 80%
- Linting with Ruff/Black
- No critical security vulnerabilities

#### NFR-MAINT-002: Logging
**Requirement**: System SHALL provide comprehensive logging
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Request tracing with correlation IDs
- Error stack traces captured
- Log rotation (10MB files, 5 backups)

---

## 5. User Requirements

### 5.1 Primary User: Day Trader

#### UR-001: Natural Language Control
**User Need**: Control trading system via natural conversation with Claude
**Requirement**: Claude Desktop integration with MCP protocol
**Acceptance**: User can start/stop trading, review positions, analyze opportunities through chat

#### UR-002: Real-Time Visibility
**User Need**: See what the system is doing in real-time
**Requirement**: Claude provides status updates and explanations
**Acceptance**: User receives updates on scans, signals, executions, position changes

#### UR-003: Risk Control
**User Need**: Confidence that risk limits are enforced
**Requirement**: Transparent risk management with user-configurable limits
**Acceptance**: User can set risk parameters, receives alerts on limit approaches

#### UR-004: Performance Tracking
**User Need**: Understand if strategy is working
**Requirement**: Clear performance metrics and analytics
**Acceptance**: Daily/weekly/monthly reports showing win rate, P&L, Sharpe ratio

---

## 6. External Interface Requirements

### 6.1 Alpaca Trading API (EXT-ALPACA)

#### EXT-ALPACA-001: Authentication
**Requirement**: System SHALL authenticate with Alpaca API
- API key and secret stored securely
- Support both paper and live accounts
- Base URL configurable (paper vs live)

#### EXT-ALPACA-002: Market Data
**Requirement**: System SHALL retrieve real-time market data
- Quotes (bid/ask/last)
- Bars (1min, 5min, 15min, 1hour, 1day)
- Order book (Level II)
- Rate limits: 200 requests/minute

#### EXT-ALPACA-003: Order Submission
**Requirement**: System SHALL submit orders via Alpaca
- Order types: market, limit, stop, trailing stop
- Time in force: day, GTC, IOC
- Order status updates via WebSocket
- Support fractional shares

### 6.2 News APIs (EXT-NEWS)

#### EXT-NEWS-001: Benzinga
**Requirement**: System SHALL collect news from Benzinga
- Endpoint: /news endpoint
- Rate limit: 50 requests/minute
- Coverage: Real-time company news

#### EXT-NEWS-002: Alpha Vantage
**Requirement**: System SHALL collect news from Alpha Vantage
- Endpoint: /query?function=NEWS_SENTIMENT
- Rate limit: 5 requests/minute (free tier)
- Coverage: Market news and sentiment

### 6.3 Claude Desktop (EXT-CLAUDE)

#### EXT-CLAUDE-001: MCP Protocol
**Requirement**: System SHALL implement MCP specification
- Protocol version: 2024-11-05
- Transport: HTTP (port 5000) or HTTPS (port 443)
- Content-Type: application/json
- Authentication: API key in headers

---

## 7. Data Requirements

### 7.1 Database Schema (DATA-SCHEMA)

#### DATA-SCHEMA-001: Normalized Schema v5.0
**Requirement**: System SHALL use normalized database schema
- **Dimension Tables**: securities, sectors, time_dimension
- **Fact Tables**: trading_history, news_sentiment, technical_indicators, etc.
- **Foreign Keys**: All fact tables reference security_id and time_id
- **No Duplication**: Symbol stored ONLY in securities table

#### DATA-SCHEMA-002: Data Integrity
**Requirement**: System SHALL enforce data integrity
- Primary keys on all tables
- Foreign key constraints enforced
- NOT NULL constraints on critical fields
- CHECK constraints on enums
- Unique constraints on natural keys

### 7.2 Data Retention (DATA-RETAIN)

#### DATA-RETAIN-001: Trading Data
**Requirement**: Permanent retention of trading history
- Orders: Permanent
- Positions: Permanent
- Trading cycles: Permanent
- Performance metrics: Permanent

#### DATA-RETAIN-002: Market Data
**Requirement**: Time-limited retention of market data
- Price history: 2 years
- News articles: 1 year
- Scan results: 90 days
- Technical indicators: 1 year

### 7.3 Data Privacy (DATA-PRIVACY)

#### DATA-PRIVACY-001: Sensitive Data
**Requirement**: System SHALL protect sensitive data
- API keys encrypted at rest
- Database credentials in environment variables
- No sensitive data in logs
- Audit trail for access to financial data

---

## 8. Performance Requirements

### 8.1 Ross Cameron Timing Requirements

#### PERF-RC-001: Pre-Market Preparation
**Requirement**: System SHALL prepare for market open
- 30 minutes before market open
- Load pre-market gappers (≥5% gap)
- Identify overnight news catalysts
- Calculate pre-market levels

#### PERF-RC-002: Opening Range
**Requirement**: System SHALL monitor first 5 minutes
- No trades in first 5 minutes (Ross Cameron rule)
- Identify opening range highs/lows
- Track volume profile formation
- Set breakout levels

#### PERF-RC-003: Active Trading Window
**Requirement**: System SHALL focus on 9:30-11:30 AM ET
- Highest volume and volatility
- Most reliable patterns
- Reduced activity after 11:30 AM
- No new entries after 3:00 PM

#### PERF-RC-004: Position Management Timing
**Requirement**: System SHALL manage positions actively
- Check positions every 1 second
- Update trailing stops every 5 seconds
- Re-evaluate at every new 5-minute bar
- Close all positions by 3:55 PM

---

## 9. Security Requirements

### 9.1 Authentication & Authorization (SEC-AUTH)

#### SEC-AUTH-001: API Authentication
**Requirement**: System SHALL authenticate API requests
- API key required for MCP access
- Rate limiting: 100 requests/minute per key
- API key rotation supported
- Failed authentication logged

#### SEC-AUTH-002: Service Security
**Requirement**: System SHALL secure internal services
- Internal services not exposed to internet
- Nginx reverse proxy for MCP endpoint
- TLS 1.3 for external connections
- Firewall: Only port 443 open

### 9.2 Data Security (SEC-DATA)

#### SEC-DATA-001: Encryption
**Requirement**: System SHALL encrypt sensitive data
- API keys encrypted at rest (Fernet)
- TLS for data in transit
- Database connections encrypted
- No plaintext credentials in code

#### SEC-DATA-002: Audit Logging
**Requirement**: System SHALL maintain audit trail
- All trading actions logged
- User interactions via Claude logged
- Failed authentication attempts logged
- Logs retained for 1 year

---

## 10. Ross Cameron Trading Requirements

### 10.1 Strategy Requirements (RC-STRATEGY)

#### RC-STRATEGY-001: Momentum Focus
**Requirement**: System SHALL implement momentum trading
- Focus on stocks in motion (≥2% daily move)
- Require volume spike (≥2x average)
- Trade in direction of momentum
- Avoid counter-trend trades

#### RC-STRATEGY-002: Pattern-Based Entry
**Requirement**: System SHALL use pattern confirmations
- Wait for pattern completion
- Confirm with volume
- Enter on breakout, not anticipation
- Set stop below pattern support

#### RC-STRATEGY-003: Risk Management
**Requirement**: System SHALL follow Ross Cameron risk rules
- Risk max 2% per trade
- Position size based on stop distance
- Always use stop-loss orders
- Take profits at 1.5-3.0 R:R
- Max 5 concurrent positions

#### RC-STRATEGY-004: Trading Hours
**Requirement**: System SHALL trade during optimal hours
- Focus: 9:30-11:30 AM ET
- Reduced activity: 11:30 AM-3:00 PM
- No new entries after 3:00 PM
- Close all by 3:55 PM

### 10.2 Screening Criteria (RC-SCREEN)

#### RC-SCREEN-001: Volume Requirements
**Requirement**: System SHALL filter by volume
- Minimum: 1 million shares daily
- Preferred: ≥5 million shares
- Volume spike: ≥2x 20-day average
- Unusual volume flag required

#### RC-SCREEN-002: Price Requirements
**Requirement**: System SHALL filter by price
- Minimum: $1.00 (avoid penny stocks)
- Maximum: $500.00 (allow high-priced momentum)
- Preferred range: $5-$100 (optimal liquidity)

#### RC-SCREEN-003: Float Size
**Requirement**: System SHOULD prefer small float stocks
- Ideal: 10-50 million shares float
- Avoid: Large cap (harder to move)
- Track float data from data providers

### 10.3 Entry Criteria (RC-ENTRY)

#### RC-ENTRY-001: Breakout Entry
**Requirement**: System SHALL enter on confirmed breakouts
- Price breaks above resistance with volume
- Wait for 1-minute candle close above
- Entry within 5 cents of breakout
- Stop 10-20 cents below breakout

#### RC-ENTRY-002: Pullback Entry
**Requirement**: System SHALL support pullback entries
- Stock pulls back to support after initial move
- Hold above key moving average (9 EMA)
- Re-enter when momentum resumes
- Tighter stop at pullback low

### 10.4 Exit Criteria (RC-EXIT)

#### RC-EXIT-001: Profit Targets
**Requirement**: System SHALL use Ross Cameron profit targets
- Scale out: 50% at 1:1 R:R, 50% at 2:1 R:R
- Move stop to breakeven after first partial
- Trail remaining position with ATR
- Full exit if pattern breaks

#### RC-EXIT-002: Stop Loss
**Requirement**: System SHALL enforce strict stops
- Initial stop: Below pattern support
- Mental stop: Max acceptable loss ($)
- Trailing stop: ATR-based or key levels
- NO moving stops wider

---

## 11. Acceptance Criteria

### 11.1 System Acceptance (ACCEPT-SYS)

#### ACCEPT-SYS-001: Complete Workflow
**Acceptance Test**: Run full trading cycle end-to-end
**Steps**:
1. Start trading cycle via Claude
2. System scans market → 100 stocks
3. Filters for catalysts → 35 stocks
4. Detects patterns → 20 stocks
5. Technical analysis → 10 stocks
6. Selects top 5 for trading
7. Generates trading signals
8. Executes trades (paper account)
9. Manages positions real-time
10. Closes positions by end of day
11. Generates performance report

**Pass Criteria**:
- All stages complete without errors
- ≥3 valid signals generated
- Orders submitted to Alpaca successfully
- Positions tracked correctly
- Performance metrics calculated

#### ACCEPT-SYS-002: Performance Targets
**Acceptance Test**: Validate performance over 2-week period
**Pass Criteria**:
- Win rate ≥ 55%
- Sharpe ratio ≥ 1.2
- Max drawdown ≤ 5%
- Average R:R ≥ 1.5
- System uptime ≥ 99%

### 11.2 User Acceptance (ACCEPT-USER)

#### ACCEPT-USER-001: Natural Interaction
**Acceptance Test**: User controls system via Claude
**Scenarios**:
- "Start trading in aggressive mode"
- "How are my positions doing?"
- "Show me the scan results"
- "Close all positions and stop trading"

**Pass Criteria**:
- Claude understands all commands
- Executes actions correctly
- Provides clear status updates
- Responds in < 2 seconds

---

## 12. Constraints & Assumptions

### 12.1 Technical Constraints (CONST-TECH)

#### CONST-TECH-001: Single User
**Constraint**: System designed for single concurrent user
**Rationale**: Personal trading system, not multi-tenant
**Impact**: Simplified state management, no user isolation required

#### CONST-TECH-002: Market Hours
**Constraint**: System operates 9:30 AM - 4:00 PM ET, Mon-Fri
**Rationale**: US stock market hours
**Impact**: Background jobs only during market hours

#### CONST-TECH-003: Paper Trading Initially
**Constraint**: Launch with paper trading (Alpaca Paper API)
**Rationale**: Validate system before risking capital
**Impact**: No real money at risk, full functionality testing

### 12.2 Assumptions (ASSUME)

#### ASSUME-001: Market Data
**Assumption**: Alpaca provides sufficient real-time data
**Risk**: If data quality poor, signals may be inaccurate
**Mitigation**: Upgrade to Alpaca Pro if needed ($99/month)

#### ASSUME-002: News Quality
**Assumption**: Free news APIs provide adequate catalyst coverage
**Risk**: May miss important catalysts
**Mitigation**: Add premium sources (Benzinga Pro) if needed

#### ASSUME-003: Execution Speed
**Assumption**: Alpaca execution is fast enough for day trading
**Risk**: Slippage on volatile stocks
**Mitigation**: Use limit orders, monitor slippage metrics

---

## Appendix A: Traceability Matrix

| Requirement ID | Functional Spec Reference | Test Case |
|----------------|--------------------------|-----------|
| FR-SCAN-001 | functional-spec-mcp-v41.md § 4.1 | TC-SCAN-001 |
| FR-SCAN-002 | functional-spec-mcp-v41.md § 4.1 | TC-SCAN-002 |
| FR-PATTERN-001 | functional-spec-mcp-v41.md § 4.2 | TC-PATTERN-001 |
| RC-STRATEGY-001 | Ross Cameron methodology | TC-RC-001 |
| NFR-PERF-001 | functional-spec-mcp-v41.md § 8.1 | TC-PERF-001 |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **ATR** | Average True Range - volatility indicator |
| **Breakout** | Price moves above resistance with volume |
| **Catalyst** | News event driving price movement |
| **Float** | Number of shares available for public trading |
| **MACD** | Moving Average Convergence Divergence |
| **MCP** | Model Context Protocol |
| **R:R** | Risk:Reward ratio |
| **RSI** | Relative Strength Index |
| **VWAP** | Volume Weighted Average Price |
| **VPOC** | Volume Point of Control |

---

**END OF SOFTWARE REQUIREMENTS SPECIFICATION v1.0.0**

*This SRS is derived from functional-spec-mcp-v41.md and incorporates Ross Cameron day trading methodology requirements. All requirements are traceable to source specifications and shall be validated through acceptance testing.*