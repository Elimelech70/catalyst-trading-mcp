# Database Schema Validation Analysis v5.0.2

**Name of Application**: Catalyst Trading System  
**Name of file**: database-schema-validation-v502.md  
**Version**: 5.0.2  
**Last Updated**: 2025-10-04  
**Purpose**: Validate current schema against ML strategy requirements and identify gaps

---

## 🎯 Executive Summary

**Current Status**: Database schema v4.2 is SOLID for Phase 1 & 2, but needs enhancements for Phase 3+ ML capabilities.

**Key Findings**:
- ✅ **Core Infrastructure**: Excellent foundation for basic trading
- ⚠️ **ML Features**: Missing critical data structures for advanced pattern recognition
- ❌ **Economic Data**: No table for FRED indicators (FREE data!)
- ❌ **Sector Analysis**: No correlation/ranking tracking
- ⚠️ **News Intelligence**: Good structure but missing source reliability & short-term impact

---

## ✅ What We Have (Current Schema v4.2)

### **1. Core Trading Tables** - EXCELLENT
```sql
✅ trading_cycles       -- Cycle management with risk config
✅ scan_results         -- Market scanning results  
✅ positions           -- Position tracking with P&L
✅ orders              -- Order execution tracking
```

### **2. Risk Management** - COMPREHENSIVE
```sql
✅ risk_parameters      -- Dynamic risk configuration
✅ daily_risk_metrics   -- Daily risk tracking
✅ risk_events          -- Risk alerts and violations
✅ position_risk_metrics -- Individual position risk
✅ portfolio_exposure   -- Exposure tracking
```

### **3. Analysis Support** - GOOD
```sql
✅ pattern_analysis     -- Pattern detection storage
✅ news_articles        -- News with catalyst tracking
```

**Schema Grade**: **A-** for current Phase 1/2 needs

---

## ⚠️ What's Missing (Critical for ML Strategy)

### **GAP 1: News Source Reliability Tracking**

**Strategy Requirement** (from strategy-data-access-requirements-v41):
> "Source reliability scoring - Track which sources are accurate"

**Current Schema**:
```sql
-- news_articles has:
source VARCHAR(100) NOT NULL,
-- But NO reliability tracking!
```

**Required Addition**:
```sql
ALTER TABLE news_articles ADD COLUMN
    source_reliability_score DECIMAL(4,3),  -- 0.000 to 1.000
    source_accuracy_history JSONB,          -- Historical performance
    price_impact_5min DECIMAL(6,3),         -- Very short-term impact
    price_impact_15min DECIMAL(6,3);        -- Day trading critical
```

**Impact**: **HIGH** - Knowing which sources reliably predict price movement is crucial for ML

---

### **GAP 2: Technical Indicators - Volume Profile**

**Strategy Requirement**:
> "Additional Indicators Needed: Volume Profile (VPOC, VAH, VAL), Market Microstructure (Bid-Ask spread)"

**Current Schema**: ❌ NO technical_indicators table at all!

**Required New Table**:
```sql
CREATE TABLE technical_indicators (
    indicator_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- 1min, 5min, 15min, 1hour, 1day
    
    -- Moving Averages
    sma_20 DECIMAL(12,4),
    sma_50 DECIMAL(12,4),
    sma_200 DECIMAL(12,4),
    ema_9 DECIMAL(12,4),
    ema_21 DECIMAL(12,4),
    
    -- Momentum Indicators
    rsi_14 DECIMAL(6,3),
    macd DECIMAL(12,4),
    macd_signal DECIMAL(12,4),
    macd_histogram DECIMAL(12,4),
    
    -- Volatility
    atr_14 DECIMAL(12,4),
    bollinger_upper DECIMAL(12,4),
    bollinger_middle DECIMAL(12,4),
    bollinger_lower DECIMAL(12,4),
    
    -- Volume Analysis ⭐ NEW FOR ML
    vpoc DECIMAL(12,4),              -- Volume Point of Control
    vah DECIMAL(12,4),               -- Value Area High
    val DECIMAL(12,4),               -- Value Area Low
    obv BIGINT,                      -- On-Balance Volume
    volume_ratio DECIMAL(6,3),
    unusual_volume_flag BOOLEAN,
    
    -- Market Microstructure ⭐ NEW FOR ML
    bid_ask_spread DECIMAL(8,4),     -- Liquidity measure
    order_flow_imbalance DECIMAL(6,3), -- Buy vs sell pressure
    
    -- Support/Resistance
    support_level DECIMAL(12,4),
    resistance_level DECIMAL(12,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp, timeframe)
);

CREATE INDEX idx_tech_symbol_time ON technical_indicators(symbol, timestamp DESC);
CREATE INDEX idx_tech_timeframe ON technical_indicators(timeframe);
CREATE INDEX idx_tech_unusual_volume ON technical_indicators(unusual_volume_flag) 
    WHERE unusual_volume_flag = TRUE;
```

**Impact**: **CRITICAL** - Volume profile and microstructure are core to ML pattern recognition

---

### **GAP 3: Sector Correlation & Ranking**

**Strategy Requirement**:
> "Cross-Sectional Features: Performance vs. sector ETF, Ranking within industry group, Correlation with market indices"

**Current Schema**: ❌ NO sector correlation tracking!

**Required New Table**:
```sql
CREATE TABLE sector_correlations (
    correlation_id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    
    -- Sector Performance
    sector VARCHAR(50) NOT NULL,
    sector_etf_symbol VARCHAR(10),           -- e.g., XLK for tech
    sector_relative_strength DECIMAL(6,3),   -- Performance vs sector ETF
    sector_rank INTEGER,                      -- Ranking within sector
    total_in_sector INTEGER,                  -- How many stocks in sector
    
    -- Market Correlations
    correlation_spy DECIMAL(5,3),            -- S&P 500 correlation
    correlation_qqq DECIMAL(5,3),            -- NASDAQ correlation
    correlation_iwm DECIMAL(5,3),            -- Russell 2000 correlation
    correlation_rolling_30d DECIMAL(5,3),    -- 30-day rolling correlation
    
    -- Beta Analysis
    beta_spy DECIMAL(6,3),
    beta_stability_score DECIMAL(5,3),       -- How stable is beta over time
    
    -- Sector Rotation Signals
    sector_momentum VARCHAR(20),             -- 'accumulating', 'distributing', 'neutral'
    rotation_score DECIMAL(6,3),             -- Sector rotation strength
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, date)
);

CREATE INDEX idx_sector_corr_symbol_date ON sector_correlations(symbol, date DESC);
CREATE INDEX idx_sector_corr_sector ON sector_correlations(sector);
CREATE INDEX idx_sector_corr_rank ON sector_correlations(sector_rank);
```

**Impact**: **HIGH** - Critical for understanding relative strength and sector rotation patterns

---

### **GAP 4: Economic Indicators (FREE DATA!)**

**Strategy Requirement**:
> "Macro Economic Data (FRED - Free): Interest rates, Inflation data, Employment statistics"

**Current Schema**: ❌ NO economic indicators table!

**Required New Table**:
```sql
CREATE TABLE economic_indicators (
    indicator_id SERIAL PRIMARY KEY,
    
    -- Indicator Info
    indicator_code VARCHAR(50) NOT NULL,     -- e.g., 'DFF' (Fed Funds Rate)
    indicator_name VARCHAR(200),
    category VARCHAR(50) NOT NULL,           -- 'interest_rate', 'inflation', 'employment', 'gdp'
    
    -- Time Series Data
    date DATE NOT NULL,
    value DECIMAL(12,4),
    
    -- Change Analysis
    value_change_1d DECIMAL(12,4),
    value_change_1w DECIMAL(12,4),
    value_change_1m DECIMAL(12,4),
    
    -- Market Impact
    market_correlation DECIMAL(5,3),         -- How it correlates with S&P
    volatility_impact VARCHAR(20),           -- 'low', 'medium', 'high'
    
    -- Metadata
    source VARCHAR(50) DEFAULT 'FRED',
    units VARCHAR(50),                       -- 'percentage', 'dollars', 'index'
    frequency VARCHAR(20),                   -- 'daily', 'weekly', 'monthly'
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(indicator_code, date)
);

CREATE INDEX idx_econ_code_date ON economic_indicators(indicator_code, date DESC);
CREATE INDEX idx_econ_category ON economic_indicators(category);
CREATE INDEX idx_econ_date ON economic_indicators(date DESC);

-- Predefined indicators to track
INSERT INTO economic_indicators (indicator_code, indicator_name, category, units, frequency) VALUES
    ('DFF', 'Federal Funds Effective Rate', 'interest_rate', 'percentage', 'daily'),
    ('T10Y2Y', '10-Year Treasury - 2-Year Spread', 'interest_rate', 'percentage', 'daily'),
    ('CPIAUCSL', 'Consumer Price Index', 'inflation', 'index', 'monthly'),
    ('UNRATE', 'Unemployment Rate', 'employment', 'percentage', 'monthly'),
    ('PAYEMS', 'Nonfarm Payrolls', 'employment', 'thousands', 'monthly'),
    ('GDP', 'Gross Domestic Product', 'gdp', 'billions', 'quarterly'),
    ('VIXCLS', 'VIX Volatility Index', 'market_sentiment', 'index', 'daily')
ON CONFLICT (indicator_code, date) DO NOTHING;
```

**Impact**: **MEDIUM-HIGH** - FREE data that enhances market regime detection

---

### **GAP 5: Enhanced Earnings Data**

**Strategy Requirement**:
> "Earnings Patterns: Pre-announcement drift, Post-earnings momentum, Guidance revision impact"

**Current Schema**: ❌ NO security_fundamentals or earnings tracking!

**Required New Tables**:
```sql
-- Quarterly fundamentals
CREATE TABLE security_fundamentals (
    fundamental_id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    
    -- Period
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    
    -- Earnings Timing
    earnings_announcement_date DATE,
    earnings_announcement_time VARCHAR(20),  -- 'BMO' (Before Market Open), 'AMC' (After Market Close)
    
    -- Financial Metrics
    revenue DECIMAL(18,2),
    earnings DECIMAL(18,2),
    eps DECIMAL(10,2),
    
    -- Estimate vs Actual ⭐ NEW FOR ML
    eps_estimate DECIMAL(10,2),
    eps_actual DECIMAL(10,2),
    eps_surprise DECIMAL(6,2),               -- (actual - estimate) / estimate
    
    revenue_estimate DECIMAL(18,2),
    revenue_actual DECIMAL(18,2),
    revenue_surprise DECIMAL(6,2),
    
    -- Guidance ⭐ NEW FOR ML
    guidance_raised BOOLEAN,
    guidance_lowered BOOLEAN,
    guidance_text TEXT,
    
    -- Valuation
    pe_ratio DECIMAL(8,2),
    pb_ratio DECIMAL(8,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, fiscal_year, fiscal_quarter)
);

-- Analyst estimates tracking
CREATE TABLE analyst_estimates (
    estimate_id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    
    -- Estimate Details
    estimate_date DATE NOT NULL,
    analyst_firm VARCHAR(100),
    eps_estimate DECIMAL(10,2),
    revenue_estimate DECIMAL(18,2),
    
    -- Revision Tracking ⭐ NEW FOR ML
    is_revision BOOLEAN DEFAULT FALSE,
    previous_eps_estimate DECIMAL(10,2),
    revision_direction VARCHAR(10),          -- 'upgrade', 'downgrade', 'maintain'
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fundamentals_symbol ON security_fundamentals(symbol, fiscal_year DESC, fiscal_quarter DESC);
CREATE INDEX idx_fundamentals_earnings_date ON security_fundamentals(earnings_announcement_date);
CREATE INDEX idx_estimates_symbol ON analyst_estimates(symbol, estimate_date DESC);
CREATE INDEX idx_estimates_revisions ON analyst_estimates(is_revision) WHERE is_revision = TRUE;
```

**Impact**: **MEDIUM** - Important for earnings play strategies

---

### **GAP 6: OHLCV Time Series (Historical Data)**

**Strategy Requirement**:
> "Multi-timeframe analysis (1min, 5min, 15min, 1hour, daily) - 5 years of minute data"

**Current Schema**: ❌ NO trading_history table!

**Required New Table**:
```sql
CREATE TABLE trading_history (
    history_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    
    -- Timing
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('1min', '5min', '15min', '1hour', '1day')),
    
    -- OHLCV
    open DECIMAL(12,4) NOT NULL,
    high DECIMAL(12,4) NOT NULL,
    low DECIMAL(12,4) NOT NULL,
    close DECIMAL(12,4) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Additional Data
    vwap DECIMAL(12,4),                     -- Volume-weighted average price
    trade_count INTEGER,                     -- Number of trades in period
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp, timeframe)
) PARTITION BY RANGE (timestamp);  -- ⭐ PARTITIONED for performance

-- Create monthly partitions (example for Oct 2024)
CREATE TABLE trading_history_2024_10 PARTITION OF trading_history
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

CREATE TABLE trading_history_2024_11 PARTITION OF trading_history
    FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

-- Indexes on partitioned table
CREATE INDEX idx_history_symbol_time ON trading_history(symbol, timestamp DESC);
CREATE INDEX idx_history_timeframe ON trading_history(timeframe);
```

**Storage Estimate**: 5 years × 1000 stocks × 1min data = ~500GB
**Mitigation**: Use partitioning + compression

**Impact**: **CRITICAL** - Foundation for all time-series ML features

---

## 🎯 Phase Alignment Assessment

### **Phase 1: Foundation** ✅
**Status**: COMPLETE  
**Schema Coverage**: 95%  
**Missing**: Nothing critical for Phase 1

### **Phase 2: Claude Desktop** ✅  
**Status**: READY  
**Schema Coverage**: 90%  
**Missing**: Some nice-to-haves for better Claude analysis

### **Phase 3: Intelligence Enhancement** ⚠️
**Status**: NEEDS WORK  
**Schema Coverage**: 60%  
**Missing**: 
- ❌ Sector correlations
- ❌ Economic indicators  
- ❌ Enhanced technical indicators
- ❌ Source reliability tracking

### **Phase 4: Advanced ML** ❌
**Status**: NOT READY  
**Schema Coverage**: 40%  
**Missing**:
- ❌ OHLCV time series (partitioned)
- ❌ Earnings estimate tracking
- ❌ Options flow (future subscription)
- ❌ Social sentiment (future subscription)

---

## 📋 Priority Recommendations

### **MUST ADD BEFORE NEWS v5.0.2 LAUNCH**

#### **Priority 1: News Service Enhancements** ⭐ IMMEDIATE
```sql
-- Add to existing news_articles table
ALTER TABLE news_articles ADD COLUMN
    source_reliability_score DECIMAL(4,3) DEFAULT 0.500,
    price_impact_5min DECIMAL(6,3),
    price_impact_15min DECIMAL(6,3),
    price_impact_30min DECIMAL(6,3),
    verified_accuracy BOOLEAN DEFAULT FALSE,
    source_track_record JSONB DEFAULT '{}';

-- Index for filtering reliable sources
CREATE INDEX idx_news_reliable ON news_articles(source_reliability_score DESC) 
    WHERE source_reliability_score > 0.700;
```

#### **Priority 2: Technical Indicators Table** ⭐ HIGH
```sql
-- Create full technical_indicators table (see GAP 2 above)
-- This is CRITICAL for ML pattern recognition
```

#### **Priority 3: Economic Indicators** ⭐ HIGH (FREE DATA!)
```sql
-- Create economic_indicators table (see GAP 4 above)
-- Source: FRED API (free)
```

### **SHOULD ADD FOR PHASE 3**

#### **Priority 4: Sector Correlations** 
```sql
-- Create sector_correlations table (see GAP 3 above)
```

#### **Priority 5: OHLCV Historical Data**
```sql
-- Create partitioned trading_history table (see GAP 6 above)
```

#### **Priority 6: Earnings Enhancement**
```sql
-- Create security_fundamentals and analyst_estimates (see GAP 5 above)
```

### **CAN ADD LATER (Phase 4)**

#### **Optional 1: Options Flow** (when we pay $199/month)
```sql
CREATE TABLE options_flow (
    flow_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Option Details
    contract_type VARCHAR(4) CHECK (contract_type IN ('call', 'put')),
    strike_price DECIMAL(10,2),
    expiration_date DATE,
    
    -- Flow Metrics
    premium DECIMAL(12,2),
    volume INTEGER,
    open_interest INTEGER,
    
    -- Classification
    flow_type VARCHAR(20) CHECK (flow_type IN ('sweep', 'block', 'split', 'unusual')),
    sentiment VARCHAR(10) CHECK (sentiment IN ('bullish', 'bearish', 'neutral')),
    
    -- Institutional Detection
    is_institutional BOOLEAN,
    dark_pool_flag BOOLEAN,
    
    source VARCHAR(50) DEFAULT 'flowalgo',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### **Optional 2: Social Sentiment** (when we pay)
```sql
CREATE TABLE social_sentiment (
    sentiment_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    platform VARCHAR(20),            -- 'twitter', 'stocktwits', 'reddit'
    
    timestamp TIMESTAMPTZ NOT NULL,
    message_count INTEGER,
    sentiment_score DECIMAL(4,3),
    bullish_ratio DECIMAL(4,3),
    
    top_keywords TEXT[],
    influencer_mentions INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 💡 Database Performance Optimizations

### **Partitioning Strategy**
```sql
-- For high-volume tables, use range partitioning
-- Example: trading_history partitioned by month
-- Benefit: Faster queries, easier data management, better compression
```

### **Index Strategy**
```sql
-- Create partial indexes for common queries
CREATE INDEX idx_news_high_impact ON news_articles(symbol, published_at DESC)
    WHERE catalyst_strength = 'strong' AND source_reliability_score > 0.700;

-- Create GIN indexes for array columns
CREATE INDEX idx_news_symbols_gin ON news_articles USING GIN(symbols);

-- Create BRIN indexes for time-series data (if using partitions)
CREATE INDEX idx_history_brin ON trading_history USING BRIN(timestamp);
```

### **Materialized Views for Analytics**
```sql
-- Pre-aggregate common queries for performance
CREATE MATERIALIZED VIEW mv_daily_sector_performance AS
SELECT 
    date,
    sector,
    AVG(sector_relative_strength) as avg_rel_strength,
    COUNT(*) as stock_count,
    AVG(correlation_spy) as avg_spy_correlation
FROM sector_correlations
GROUP BY date, sector;

-- Refresh daily
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sector_performance;
```

---

## 🚀 Migration Plan

### **Step 1: News Service v5.0.2** (This Week)
```bash
# Add source reliability to news_articles
psql -f migrations/add_news_reliability.sql

# Add short-term price impact columns
psql -f migrations/add_news_short_term_impact.sql
```

### **Step 2: Technical Analysis Foundation** (Next Week)
```bash
# Create technical_indicators table
psql -f migrations/create_technical_indicators.sql

# Backfill with historical indicators
python scripts/backfill_technical_indicators.py
```

### **Step 3: Economic Intelligence** (Week 3)
```bash
# Create economic_indicators table
psql -f migrations/create_economic_indicators.sql

# Fetch FRED data (FREE!)
python scripts/fetch_fred_data.py
```

### **Step 4: Sector Analysis** (Week 4)
```bash
# Create sector_correlations table
psql -f migrations/create_sector_correlations.sql

# Calculate initial correlations
python scripts/calculate_sector_correlations.py
```

### **Step 5: Historical OHLCV** (Month 2)
```bash
# Create partitioned trading_history
psql -f migrations/create_trading_history_partitioned.sql

# Download historical data
python scripts/download_historical_ohlcv.py --years=5
```

---

## ✅ Validation Checklist

### **For News v5.0.2 Launch**
- [ ] Add source_reliability_score to news_articles
- [ ] Add price_impact_5min, price_impact_15min
- [ ] Create index for high-reliability sources
- [ ] Update news service to populate new fields
- [ ] Add source tracking logic

### **For Phase 3 Readiness**
- [ ] Create technical_indicators table
- [ ] Create economic_indicators table  
- [ ] Create sector_correlations table
- [ ] Set up FRED API integration
- [ ] Implement sector ranking logic

### **For Phase 4 ML Capabilities**
- [ ] Create partitioned trading_history table
- [ ] Create security_fundamentals table
- [ ] Create analyst_estimates table
- [ ] Set up earnings data pipeline
- [ ] Implement ML feature extraction views

---

## 🎯 Final Answer to Your Questions

### **1. Timeframes - Do we need 30min, 4hour, weekly?**
**Answer**: YES for Phase 3+
```sql
-- Update CHECK constraint:
timeframe CHECK (timeframe IN ('1min', '5min', '15min', '30min', '1hour', '4hour', '1day', '1week'))
```

### **2. Economic Data - Which FRED indicators?**
**Answer**: Start with these 7 FREE indicators:
1. DFF - Federal Funds Rate (interest rate regime)
2. T10Y2Y - Yield Curve (recession indicator)
3. CPIAUCSL - CPI (inflation)
4. UNRATE - Unemployment (economic health)
5. VIXCLS - VIX (market fear gauge)
6. DGS10 - 10-Year Treasury (risk-free rate)
7. DEXUSEU - USD/EUR (currency strength)

### **3. Earnings - Subscribe to FMP now?**
**Answer**: WAIT until Phase 3
- News v5.0.2 doesn't need it yet
- Create the tables NOW (they're free)
- Subscribe to Financial Modeling Prep ($50/month) when doing earnings plays

### **4. Partitioning - Now or later?**
**Answer**: Implement with trading_history creation
- Don't add partitioning to existing tables yet
- When creating trading_history (Phase 3), partition from day 1
- Much easier than retrofitting later

### **5. Options Flow - Phase 3 or 4?**
**Answer**: Phase 4 (or when capital > $50k)
- FlowAlgo costs $199/month
- High value but not critical for news-based day trading
- Add table structure in Phase 3, populate in Phase 4

---

## 📊 Summary Score

### **Current Schema (v4.2)**
- ✅ **Trading Infrastructure**: 95% (A)
- ✅ **Risk Management**: 100% (A+)  
- ⚠️ **ML Features**: 60% (C)
- ❌ **Time Series Data**: 30% (F)
- ⚠️ **News Intelligence**: 75% (B-)

### **After Recommended Changes**
- ✅ **Trading Infrastructure**: 95% (A)
- ✅ **Risk Management**: 100% (A+)
- ✅ **ML Features**: 90% (A-)
- ✅ **Time Series Data**: 85% (B+)
- ✅ **News Intelligence**: 95% (A)

**Overall Grade**: **B+** → **A-** after changes

---

*This schema will support News v5.0.2 AND set strong foundation for Phase 3 ML enhancements!* 🎩✨