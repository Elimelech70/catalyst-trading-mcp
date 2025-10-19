# Catalyst Trading System - Database Schema Relationships v5.0

**Name of Application**: Catalyst Trading System  
**Name of file**: database-relationships-diagram-v50.md  
**Version**: 5.0.0  
**Last Updated**: 2025-10-06  
**Purpose**: Visual representation of normalized schema relationships and ML feature views

---

## Table of Contents

1. [Schema Overview](#schema-overview)
2. [Dimension Tables (Master Data)](#dimension-tables-master-data)
3. [Fact Tables (Events/Time-Series)](#fact-tables-eventstime-series)
4. [Trading Operations Tables](#trading-operations-tables)
5. [View Relationships](#view-relationships)
6. [Data Flow Diagram](#data-flow-diagram)

---

## Schema Overview

```
🎯 NORMALIZED 3NF ARCHITECTURE

DIMENSION TABLES          FACT TABLES               TRADING TABLES
(Master Data)            (Events/Time-Series)      (Operations)
┌─────────────┐          ┌──────────────────┐      ┌─────────────────┐
│ securities  │──────────│ trading_history  │      │ trading_cycles  │
│  (PK: id)   │          │  (FK: security)  │      │  (PK: cycle_id) │
└─────────────┘          └──────────────────┘      └─────────────────┘
      │                           │                          │
      │                  ┌──────────────────┐               │
      ├──────────────────│ news_sentiment   │               │
      │                  │  (FK: security)  │               │
      │                  └──────────────────┘               │
      │                           │                         │
┌─────────────┐          ┌──────────────────┐      ┌─────────────────┐
│   sectors   │          │technical_indic.  │      │   positions     │
│  (PK: id)   │          │  (FK: security)  │      │  (FK: security) │
└─────────────┘          └──────────────────┘      └─────────────────┘
      │                           │                          │
      │                  ┌──────────────────┐      ┌─────────────────┐
      │                  │sector_correl.    │      │  scan_results   │
      │                  │  (FK: security)  │      │  (FK: security) │
      │                  └──────────────────┘      └─────────────────┘
      │                           │                          │
┌─────────────┐          ┌──────────────────┐      ┌─────────────────┐
│time_dimension│         │security_fundam.  │      │     orders      │
│  (PK: id)   │          │  (FK: security)  │      │  (FK: security) │
└─────────────┘          └──────────────────┘      └─────────────────┘
      │                           │
      │                  ┌──────────────────┐
      │                  │analyst_estimates │
      │                  │  (FK: security)  │
      │                  └──────────────────┘
      │
      │                  ┌──────────────────┐
      └──────────────────│economic_indic.   │
                         │  (no security FK)│
                         └──────────────────┘

ALL FACT TABLES USE FOREIGN KEYS - NO SYMBOL DUPLICATION!
```

---

## Dimension Tables (Master Data)

### 1. Securities (Master Entity - Hub)

```
┌─────────────────────────────────────────────────────────┐
│                    SECURITIES                           │
│  (SINGLE SOURCE OF TRUTH FOR ALL SECURITY DATA)         │
├─────────────────────────────────────────────────────────┤
│  PK: security_id (SERIAL)                               │
│                                                         │
│  • symbol (UNIQUE) ← Used for display only             │
│  • company_name                                         │
│  • sector_id (FK → sectors)                            │
│  • industry                                             │
│  • exchange                                             │
│  • is_active                                            │
│  • is_tradeable                                         │
│  • market_cap                                           │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Referenced by (FK):
                          ├── trading_history.security_id
                          ├── news_sentiment.security_id
                          ├── technical_indicators.security_id
                          ├── sector_correlations.security_id
                          ├── security_fundamentals.security_id
                          ├── analyst_estimates.security_id
                          ├── positions.security_id
                          ├── scan_results.security_id
                          └── orders.security_id
```

### 2. Sectors (Normalized Sector Data)

```
┌─────────────────────────────────────────────────────────┐
│                      SECTORS                            │
│     (NORMALIZED SECTOR/INDUSTRY CLASSIFICATION)         │
├─────────────────────────────────────────────────────────┤
│  PK: sector_id (SERIAL)                                 │
│                                                         │
│  • sector_name (UNIQUE)                                │
│  • sector_code (e.g., 'XLK')                           │
│  • parent_sector_id (FK → sectors) ← Hierarchical      │
│  • sector_etf_symbol                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Referenced by:
                          └── securities.sector_id
```

**Pre-populated Data:**
- Technology (XLK)
- Healthcare (XLV)
- Financials (XLF)
- Consumer Discretionary (XLY)
- Communication Services (XLC)
- Industrials (XLI)
- Consumer Staples (XLP)
- Energy (XLE)
- Utilities (XLU)
- Real Estate (XLRE)
- Materials (XLB)

### 3. Time Dimension (Time as Entity)

```
┌─────────────────────────────────────────────────────────┐
│                  TIME_DIMENSION                         │
│         (SINGLE SOURCE OF TRUTH FOR TIME DATA)          │
├─────────────────────────────────────────────────────────┤
│  PK: time_id (BIGSERIAL)                                │
│                                                         │
│  • timestamp (UNIQUE) ← Actual datetime                │
│  • date, year, quarter, month, week                    │
│  • day_of_month, day_of_week, day_of_year              │
│  • hour, minute                                         │
│  • market_session (pre/regular/after/closed)           │
│  • is_trading_day, is_market_holiday                   │
│  • is_month_start/end, quarter_start/end               │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Referenced by (FK):
                          ├── trading_history.time_id
                          ├── news_sentiment.time_id
                          └── technical_indicators.time_id
```

---

## Fact Tables (Events/Time-Series)

### 4. Trading History (OHLCV - Partitioned)

```
┌─────────────────────────────────────────────────────────┐
│                 TRADING_HISTORY                         │
│              (PARTITIONED BY time_id)                   │
├─────────────────────────────────────────────────────────┤
│  PK: (security_id, time_id, timeframe)                  │
│  FK: security_id → securities                           │
│  FK: time_id → time_dimension                           │
│                                                         │
│  • timeframe ('1min', '5min', '15min', '1hour', etc)   │
│  • open, high, low, close, volume                      │
│  • vwap, trade_count                                    │
└─────────────────────────────────────────────────────────┘

Partitions:
  ├── trading_history_202410  (Oct 2024)
  ├── trading_history_202411  (Nov 2024)
  ├── trading_history_202412  (Dec 2024)
  └── ... (created monthly)
```

### 5. News Sentiment (Enhanced)

```
┌─────────────────────────────────────────────────────────┐
│                  NEWS_SENTIMENT                         │
│         (NEWS WITH ML IMPACT TRACKING)                  │
├─────────────────────────────────────────────────────────┤
│  PK: news_id (BIGSERIAL)                                │
│  FK: security_id → securities                           │
│  FK: time_id → time_dimension                           │
│                                                         │
│  • headline, summary, url, source                      │
│  • sentiment_score, sentiment_label                    │
│  • catalyst_type, catalyst_strength                    │
│                                                         │
│  ML FEATURES:                                           │
│  • source_reliability_score (0-1)                      │
│  • price_impact_5min, 15min, 30min                     │
│  • price_impact_1h, 4h, 1d                             │
│  • verified_accuracy                                    │
└─────────────────────────────────────────────────────────┘
```

### 6. Technical Indicators

```
┌─────────────────────────────────────────────────────────┐
│              TECHNICAL_INDICATORS                       │
│       (ALL CALCULATED INDICATORS WITH FKS)              │
├─────────────────────────────────────────────────────────┤
│  PK: indicator_id (BIGSERIAL)                           │
│  FK: security_id → securities                           │
│  FK: time_id → time_dimension                           │
│  UNIQUE: (security_id, time_id, timeframe)              │
│                                                         │
│  Moving Averages: sma_20/50/200, ema_9/21              │
│  Momentum: rsi_14, macd, macd_signal                   │
│  Volatility: atr_14, bollinger_upper/middle/lower      │
│                                                         │
│  ML CRITICAL:                                           │
│  • Volume Profile: vpoc, vah, val, obv                 │
│  • Microstructure: bid_ask_spread, order_flow_imb.     │
│  • unusual_volume_flag                                  │
└─────────────────────────────────────────────────────────┘
```

### 7. Sector Correlations (Daily)

```
┌─────────────────────────────────────────────────────────┐
│              SECTOR_CORRELATIONS                        │
│         (DAILY CROSS-SECTIONAL ANALYSIS)                │
├─────────────────────────────────────────────────────────┤
│  PK: correlation_id (SERIAL)                            │
│  FK: security_id → securities                           │
│  UNIQUE: (security_id, date)                            │
│                                                         │
│  • sector_relative_strength                            │
│  • sector_rank, total_in_sector                        │
│  • correlation_spy/qqq/iwm                             │
│  • correlation_rolling_30d                             │
│  • beta_spy, beta_stability_score                      │
│  • sector_momentum, rotation_score                     │
└─────────────────────────────────────────────────────────┘
```

### 8. Economic Indicators (FRED Data)

```
┌─────────────────────────────────────────────────────────┐
│             ECONOMIC_INDICATORS                         │
│          (FREE FRED DATA - MARKET WIDE)                 │
├─────────────────────────────────────────────────────────┤
│  PK: indicator_id (SERIAL)                              │
│  NO security FK (market-wide data)                      │
│  UNIQUE: (indicator_code, date)                         │
│                                                         │
│  Pre-populated:                                         │
│  • DFF (Fed Funds Rate)                                │
│  • T10Y2Y (Yield Curve)                                │
│  • VIXCLS (VIX)                                        │
│  • CPIAUCSL (CPI)                                      │
│  • UNRATE (Unemployment)                               │
│  • PAYEMS (Payrolls)                                   │
│  • GDP                                                  │
└─────────────────────────────────────────────────────────┘
```

### 9. Security Fundamentals (Quarterly)

```
┌─────────────────────────────────────────────────────────┐
│            SECURITY_FUNDAMENTALS                        │
│              (QUARTERLY EARNINGS)                       │
├─────────────────────────────────────────────────────────┤
│  PK: fundamental_id (SERIAL)                            │
│  FK: security_id → securities                           │
│  UNIQUE: (security_id, fiscal_year, fiscal_quarter)     │
│                                                         │
│  • earnings_announcement_date                          │
│  • revenue, eps                                         │
│                                                         │
│  ML FEATURES:                                           │
│  • eps_estimate, eps_actual, eps_surprise              │
│  • revenue_estimate, revenue_actual, revenue_surprise  │
│  • guidance_raised, guidance_lowered                   │
└─────────────────────────────────────────────────────────┘
```

### 10. Analyst Estimates

```
┌─────────────────────────────────────────────────────────┐
│              ANALYST_ESTIMATES                          │
│            (ESTIMATE TRACKING)                          │
├─────────────────────────────────────────────────────────┤
│  PK: estimate_id (SERIAL)                               │
│  FK: security_id → securities                           │
│                                                         │
│  • fiscal_year, fiscal_quarter                         │
│  • estimate_date, analyst_firm                         │
│  • eps_estimate, revenue_estimate                      │
│                                                         │
│  ML FEATURES:                                           │
│  • is_revision (upgrade/downgrade)                     │
│  • previous_eps_estimate                               │
│  • revision_direction                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Trading Operations Tables

### 11. Trading Cycles

```
┌─────────────────────────────────────────────────────────┐
│               TRADING_CYCLES                            │
│           (CYCLE CONFIGURATION)                         │
├─────────────────────────────────────────────────────────┤
│  PK: cycle_id (VARCHAR)                                 │
│                                                         │
│  • mode (aggressive/normal/conservative)               │
│  • status (active/stopped/completed)                   │
│  • max_positions, max_daily_loss                       │
│  • risk_level, position_size_multiplier                │
│  • total_risk_budget, used_risk_budget                 │
│  • current_positions, current_exposure                 │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Referenced by:
                          ├── positions.cycle_id
                          ├── scan_results.cycle_id
                          └── orders.cycle_id
```

### 12. Positions (Uses security_id FK!)

```
┌─────────────────────────────────────────────────────────┐
│                   POSITIONS                             │
│         (POSITION TRACKING WITH FK)                     │
├─────────────────────────────────────────────────────────┤
│  PK: position_id (SERIAL)                               │
│  FK: cycle_id → trading_cycles                          │
│  FK: security_id → securities  ← NOT symbol!           │
│                                                         │
│  • side (long/short)                                    │
│  • quantity, entry_price, exit_price                   │
│  • stop_loss, take_profit, risk_amount                 │
│  • status (open/closed/partial/risk_reduced)           │
│  • unrealized_pnl, realized_pnl, pnl_percent           │
│  • opened_at, closed_at, close_reason                  │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Referenced by:
                          └── orders.position_id
```

### 13. Scan Results (Uses security_id FK!)

```
┌─────────────────────────────────────────────────────────┐
│                 SCAN_RESULTS                            │
│          (SCANNER OUTPUT WITH FK)                       │
├─────────────────────────────────────────────────────────┤
│  PK: id (SERIAL)                                        │
│  FK: cycle_id → trading_cycles                          │
│  FK: security_id → securities  ← NOT symbol!           │
│                                                         │
│  • scan_timestamp                                       │
│  • momentum_score, volume_score                        │
│  • catalyst_score, technical_score                     │
│  • composite_score                                      │
│  • price, volume (snapshot)                            │
│  • rank, selected_for_trading                          │
└─────────────────────────────────────────────────────────┘
```

### 14. Orders (Uses security_id FK!)

```
┌─────────────────────────────────────────────────────────┐
│                     ORDERS                              │
│           (ORDER EXECUTION TRACKING)                    │
├─────────────────────────────────────────────────────────┤
│  PK: order_id (VARCHAR)                                 │
│  FK: position_id → positions                            │
│  FK: cycle_id → trading_cycles                          │
│  FK: security_id → securities  ← NOT symbol!           │
│                                                         │
│  • side (buy/sell), order_type                         │
│  • quantity, limit_price, stop_price                   │
│  • status (pending/submitted/filled/cancelled)         │
│  • submitted_at, filled_at, cancelled_at               │
│  • filled_quantity, filled_price, fees                 │
└─────────────────────────────────────────────────────────┘
```

---

## View Relationships

### v_ml_features (Complete ML Feature Set)

**Purpose**: Pre-join ALL data for ML training via normalized FKs

```
┌─────────────────────────────────────────────────────────┐
│                  V_ML_FEATURES                          │
│         (MATERIALIZED VIEW - REFRESH EVERY 5MIN)        │
├─────────────────────────────────────────────────────────┤
│  FROM: trading_history th                               │
│  JOIN: securities s         (via security_id)          │
│  JOIN: sectors sec          (via sector_id)            │
│  JOIN: time_dimension td    (via time_id)              │
│  LEFT JOIN: technical_indicators ti                     │
│  LEFT JOIN: sector_correlations sc                      │
│  LEFT JOIN: economic_indicators ei                      │
│  LEFT JOIN: news_sentiment ns                           │
│                                                         │
│  OUTPUT COLUMNS:                                        │
│  ├── Identification: security_id, symbol, company_name │
│  ├── Classification: sector_name                       │
│  ├── Time: timestamp, date, timeframe                  │
│  ├── Price: close, volume, vwap                        │
│  ├── Technical: rsi_14, macd, vpoc, bid_ask_spread    │
│  ├── Volume: unusual_volume_flag, order_flow_imb.     │
│  ├── Sector: sector_rel_strength, rank, corr_spy      │
│  ├── Beta: beta_spy                                    │
│  ├── Economic: vix_level, fed_funds_rate              │
│  └── News: news_count_1h, max_catalyst, avg_sentiment │
└─────────────────────────────────────────────────────────┘

Usage:
  SELECT * FROM v_ml_features
  WHERE symbol = 'AAPL'
  AND timestamp >= NOW() - INTERVAL '1 day'
  ORDER BY timestamp DESC;
```

**Data Flow for v_ml_features:**

```
trading_history (security_id, time_id)
        │
        ├─→ JOIN securities (security_id)  → get symbol, company_name
        │           │
        │           └─→ JOIN sectors (sector_id) → get sector_name
        │
        ├─→ JOIN time_dimension (time_id) → get timestamp, date
        │
        ├─→ LEFT JOIN technical_indicators (security_id, time_id)
        │                                    → get rsi, macd, vpoc, etc.
        │
        ├─→ LEFT JOIN sector_correlations (security_id, date)
        │                                  → get sector_rank, correlation
        │
        ├─→ LEFT JOIN economic_indicators (date)
        │                                  → get vix, fed_funds_rate
        │
        └─→ LEFT JOIN news_sentiment (security_id, time window)
                                      → get news_count, catalyst, sentiment

Result: Complete feature set with NO duplicate data!
```

### v_securities_latest (Latest Security Data)

```
┌─────────────────────────────────────────────────────────┐
│              V_SECURITIES_LATEST                        │
│        (MATERIALIZED VIEW - REFRESH EVERY 15MIN)        │
├─────────────────────────────────────────────────────────┤
│  FROM: securities s                                     │
│  LEFT JOIN: sectors sec                                 │
│                                                         │
│  SUBQUERIES:                                            │
│  ├── Latest price (from trading_history)               │
│  ├── Latest news date (from news_sentiment)            │
│  └── Latest SPY correlation (from sector_correlations) │
│                                                         │
│  OUTPUT:                                                │
│  • security_id, symbol, company_name                   │
│  • sector_name, is_active                              │
│  • latest_price                                         │
│  • latest_news_date                                     │
│  • latest_spy_correlation                               │
└─────────────────────────────────────────────────────────┘

Usage:
  SELECT * FROM v_securities_latest
  WHERE is_active = TRUE
  ORDER BY latest_news_date DESC;
```

---

## Data Flow Diagram

### Complete Flow: From Data Ingestion → ML Features

```
┌─────────────────────────────────────────────────────────────────┐
│                  DATA INGESTION FLOW                            │
└─────────────────────────────────────────────────────────────────┘

1. NEWS ARRIVES
   ├─→ get_or_create_security('AAPL')     → security_id = 1
   ├─→ get_or_create_time(published_at)   → time_id = 12345
   └─→ INSERT news_sentiment (security_id=1, time_id=12345, ...)

2. PRICE DATA ARRIVES
   ├─→ get_or_create_security('AAPL')     → security_id = 1
   ├─→ get_or_create_time(bar_time)       → time_id = 12346
   └─→ INSERT trading_history (security_id=1, time_id=12346, ...)

3. TECHNICAL INDICATORS CALCULATED
   ├─→ security_id = 1 (from securities)
   ├─→ time_id = 12346 (from time_dimension)
   └─→ INSERT technical_indicators (security_id=1, time_id=12346, ...)

4. SECTOR CORRELATIONS CALCULATED (Daily)
   ├─→ security_id = 1
   └─→ INSERT sector_correlations (security_id=1, date=today, ...)

5. ML FEATURES EXTRACTED (View Refresh)
   └─→ REFRESH MATERIALIZED VIEW v_ml_features
       ├─→ JOINs trading_history + securities + sectors
       ├─→ JOINs time_dimension
       ├─→ JOINs technical_indicators
       ├─→ JOINs sector_correlations
       ├─→ JOINs economic_indicators
       └─→ JOINs news_sentiment
       
   Result: Complete feature vector for ML training!

6. ML MODEL TRAINING
   └─→ SELECT * FROM v_ml_features
       WHERE timestamp >= '2024-01-01'
       
   Features include:
   ✅ Price action (from trading_history)
   ✅ Technical signals (from technical_indicators)
   ✅ Sector context (from sector_correlations via securities)
   ✅ Economic regime (from economic_indicators)
   ✅ News catalyst (from news_sentiment)
   ✅ NO DUPLICATE DATA - all via FKs!
```

### Query Pattern Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUERY PATTERN                                │
└─────────────────────────────────────────────────────────────────┘

Application wants: "Show me AAPL news from last hour"

❌ OLD WAY (Denormalized):
   SELECT * FROM news_articles 
   WHERE symbol = 'AAPL'  ← Symbol stored in table
   AND published_at > NOW() - INTERVAL '1 hour'

   Problems:
   - Symbol duplicated in every row
   - No sector info
   - Can't join to other tables easily

✅ NEW WAY (Normalized):
   SELECT 
       s.symbol,
       s.company_name,
       sec.sector_name,
       td.timestamp,
       ns.headline,
       ns.sentiment_score,
       ns.catalyst_strength
   FROM news_sentiment ns
   JOIN securities s ON s.security_id = ns.security_id
   JOIN sectors sec ON sec.sector_id = s.sector_id
   JOIN time_dimension td ON td.time_id = ns.time_id
   WHERE s.symbol = 'AAPL'
   AND td.timestamp > NOW() - INTERVAL '1 hour'
   ORDER BY td.timestamp DESC;

   Benefits:
   ✅ Symbol stored once (in securities)
   ✅ Sector from normalized sectors table
   ✅ Time from time_dimension with rich metadata
   ✅ Can easily add correlations, indicators, etc.
```

---

## Relationship Summary

### Primary Relationships (Foreign Keys)

```
securities (security_id)
    ↓ (1:N)
    ├── trading_history.security_id
    ├── news_sentiment.security_id
    ├── technical_indicators.security_id
    ├── sector_correlations.security_id
    ├── security_fundamentals.security_id
    ├── analyst_estimates.security_id
    ├── positions.security_id
    ├── scan_results.security_id
    └── orders.security_id

sectors (sector_id)
    ↓ (1:N)
    ├── securities.sector_id
    └── sectors.parent_sector_id (hierarchical)

time_dimension (time_id)
    ↓ (1:N)
    ├── trading_history.time_id
    ├── news_sentiment.time_id
    └── technical_indicators.time_id

trading_cycles (cycle_id)
    ↓ (1:N)
    ├── positions.cycle_id
    ├── scan_results.cycle_id
    └── orders.cycle_id

positions (position_id)
    ↓ (1:N)
    └── orders.position_id
```

### View Dependencies

```
v_ml_features depends on:
    ├── trading_history (base fact table)
    ├── securities (for symbol/company)
    ├── sectors (for sector_name)
    ├── time_dimension (for timestamp/date)
    ├── technical_indicators (for signals)
    ├── sector_correlations (for sector context)
    ├── economic_indicators (for macro context)
    └── news_sentiment (for catalyst info)

v_securities_latest depends on:
    ├── securities (base)
    ├── sectors (for sector_name)
    ├── trading_history (for latest price)
    ├── news_sentiment (for latest news)
    └── sector_correlations (for latest correlation)
```

---

## Key Principles Visualized

### ✅ Normalization Rules Applied

```
RULE 1: Master Data Lives in ONE Place
┌─────────────┐
│ securities  │ ← Symbol stored ONCE
└─────────────┘
       ↓ FK
All other tables reference security_id (NOT symbol!)

RULE 2: Time as Entity
┌─────────────┐
│time_dimension│ ← Timestamp stored ONCE with rich metadata
└─────────────┘
       ↓ FK
All event tables reference time_id (NOT duplicate timestamps!)

RULE 3: Sectors Normalized
┌─────────────┐
│   sectors   │ ← Sector data stored ONCE
└─────────────┘
       ↓ FK
securities.sector_id → Sector name appears nowhere else!
```

### ✅ Query Via JOINs (Not Duplication)

```
Want: Symbol + Sector + News

❌ WRONG: Store all in news table
┌──────────────────────────────────┐
│        news_articles             │
├──────────────────────────────────┤
│ symbol | sector | headline | ... │ ← DUPLICATED!
└──────────────────────────────────┘

✅ RIGHT: JOIN via FKs
news_sentiment.security_id → securities.symbol
securities.sector_id → sectors.sector_name

Result: Same data, no duplication!
```

---

## 📊 Performance Characteristics

### Index Strategy

```
Primary Keys (auto-indexed):
  ✅ securities.security_id
  ✅ sectors.sector_id
  ✅ time_dimension.time_id
  ✅ All other PKs

Foreign Keys (indexed):
  ✅ All security_id columns
  ✅ All time_id columns
  ✅ All cycle_id columns

Unique Constraints (indexed):
  ✅ securities.symbol
  ✅ time_dimension.timestamp
  ✅ (security_id, time_id, timeframe) combinations

Partial Indexes (optimized queries):
  ✅ WHERE is_active = TRUE
  ✅ WHERE is_trading_day = TRUE
  ✅ WHERE unusual_volume_flag = TRUE
  ✅ WHERE source_reliability_score > 0.700

Composite Indexes (common queries):
  ✅ (security_id, time_id DESC)
  ✅ (cycle_id, composite_score DESC)
  ✅ (security_id, date DESC)
```

### Partitioning Strategy

```
trading_history
  ├── PARTITIONED BY: time_id (RANGE)
  ├── trading_history_202410
  ├── trading_history_202411
  └── trading_history_202412
  
Benefits:
  ✅ Faster time-range queries
  ✅ Easier data archival
  ✅ Better compression per partition
  ✅ Parallel query execution
```

---

## ✅ Validation Queries

### Check Normalization (No Orphans)

```sql
-- Should return 0 (all news has valid security)
SELECT COUNT(*) FROM news_sentiment ns
LEFT JOIN securities s ON s.security_id = ns.security_id
WHERE s.security_id IS NULL;

-- Should return 0 (all positions have valid security)
SELECT COUNT(*) FROM positions p
LEFT JOIN securities s ON s.security_id = p.security_id
WHERE s.security_id IS NULL;

-- Should return 0 (all trading_history has valid time)
SELECT COUNT(*) FROM trading_history th
LEFT JOIN time_dimension td ON td.time_id = th.time_id
WHERE td.time_id IS NULL;
```

### Check View Functionality

```sql
-- ML features view works
SELECT COUNT(*) FROM v_ml_features;

-- Latest securities view works
SELECT * FROM v_securities_latest LIMIT 10;

-- Can join everything together
SELECT 
    s.symbol,
    sec.sector_name,
    COUNT(DISTINCT th.time_id) as price_records,
    COUNT(DISTINCT ns.news_id) as news_records,
    COUNT(DISTINCT ti.indicator_id) as indicator_records
FROM securities s
LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
LEFT JOIN trading_history th ON th.security_id = s.security_id
LEFT JOIN news_sentiment ns ON ns.security_id = s.security_id
LEFT JOIN technical_indicators ti ON ti.security_id = s.security_id
GROUP BY s.symbol, sec.sector_name;
```

---

*This normalized schema ensures clean, consistent data for ML training!* 🎩✨