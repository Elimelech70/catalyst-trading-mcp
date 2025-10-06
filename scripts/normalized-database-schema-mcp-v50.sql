-- ============================================================================
-- Catalyst Trading System - NORMALIZED Database Schema v5.0
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: normalized-database-schema-mcp-v50.sql
-- Version: 5.0.0
-- Last Updated: 2025-10-06
-- Purpose: FULLY NORMALIZED schema with proper dimension tables and FKs
--
-- REVISION HISTORY:
-- v5.0.0 (2025-10-06) - Complete normalization + ML enhancements
--   - Created securities (master entity) - SINGLE SOURCE OF TRUTH
--   - Created time_dimension table (time as its own entity)  
--   - Created sectors table (normalized sector data)
--   - All tables use security_id FK (NO symbol duplication!)
--   - Added ML enhancement tables with proper FKs
--   - Partitioned time-series tables for performance
--
-- Description:
-- Fully normalized 3NF database schema where:
-- 1. Securities table is master entity (security_id PK)
-- 2. Time is its own dimension (time_id PK)
-- 3. NO duplicate data across tables
-- 4. All relationships use FKs
-- 5. ML-ready with proper normalization
-- ============================================================================

-- ============================================================================
-- DIMENSION TABLES (Master Data - Single Source of Truth)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. SECURITIES - Master Entity (Single Source of Truth for ALL stock data)
-- ---------------------------------------------------------------------------
CREATE TABLE securities (
    security_id SERIAL PRIMARY KEY,
    
    -- Identification
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(200),
    company_name VARCHAR(200),
    
    -- Classification
    sector_id INTEGER,  -- FK to sectors table
    industry VARCHAR(100),
    exchange VARCHAR(20),
    asset_type VARCHAR(20) DEFAULT 'stock'
        CHECK (asset_type IN ('stock', 'etf', 'index', 'option', 'crypto')),
    
    -- Trading Info
    is_active BOOLEAN DEFAULT TRUE,
    is_tradeable BOOLEAN DEFAULT TRUE,
    market_cap DECIMAL(18,2),
    shares_outstanding BIGINT,
    
    -- Timestamps
    listed_date DATE,
    delisted_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_sector ON securities(sector_id);
CREATE INDEX idx_securities_active ON securities(is_active) WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- 2. SECTORS - Normalized Sector/Industry Data
-- ---------------------------------------------------------------------------
CREATE TABLE sectors (
    sector_id SERIAL PRIMARY KEY,
    
    sector_name VARCHAR(100) NOT NULL UNIQUE,
    sector_code VARCHAR(20) UNIQUE,  -- e.g., 'XLK' for Technology
    description TEXT,
    
    -- Parent sector (for sub-sectors)
    parent_sector_id INTEGER REFERENCES sectors(sector_id),
    
    -- Sector ETF for correlation
    sector_etf_symbol VARCHAR(10),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add FK constraint after both tables exist
ALTER TABLE securities 
    ADD CONSTRAINT fk_securities_sector 
    FOREIGN KEY (sector_id) REFERENCES sectors(sector_id);

CREATE INDEX idx_sectors_name ON sectors(sector_name);

-- ---------------------------------------------------------------------------
-- 3. TIME DIMENSION - Time as its own entity
-- ---------------------------------------------------------------------------
CREATE TABLE time_dimension (
    time_id BIGSERIAL PRIMARY KEY,
    
    -- Full timestamp
    timestamp TIMESTAMPTZ NOT NULL UNIQUE,
    
    -- Date components
    date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    week INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,  -- 0=Sunday, 6=Saturday
    day_of_year INTEGER NOT NULL,
    
    -- Time components
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    
    -- Market session info
    market_session VARCHAR(20)  -- 'pre_market', 'regular', 'after_hours', 'closed'
        CHECK (market_session IN ('pre_market', 'regular', 'after_hours', 'closed')),
    is_trading_day BOOLEAN DEFAULT TRUE,
    is_market_holiday BOOLEAN DEFAULT FALSE,
    
    -- Week/Month/Quarter boundaries
    is_month_start BOOLEAN,
    is_month_end BOOLEAN,
    is_quarter_start BOOLEAN,
    is_quarter_end BOOLEAN,
    is_year_start BOOLEAN,
    is_year_end BOOLEAN,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_time_timestamp ON time_dimension(timestamp);
CREATE INDEX idx_time_date ON time_dimension(date);
CREATE INDEX idx_time_trading_day ON time_dimension(is_trading_day) 
    WHERE is_trading_day = TRUE;

-- ============================================================================
-- FACT/EVENT TABLES (Use FKs to dimension tables - NO DUPLICATION)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 4. TRADING_HISTORY - OHLCV Time Series (PARTITIONED)
-- ---------------------------------------------------------------------------
CREATE TABLE trading_history (
    history_id BIGSERIAL,
    security_id INTEGER NOT NULL,  -- FK to securities
    time_id BIGINT NOT NULL,        -- FK to time_dimension
    timeframe VARCHAR(10) NOT NULL 
        CHECK (timeframe IN ('1min', '5min', '15min', '30min', '1hour', '4hour', '1day', '1week')),
    
    -- OHLCV Data
    open DECIMAL(12,4) NOT NULL,
    high DECIMAL(12,4) NOT NULL,
    low DECIMAL(12,4) NOT NULL,
    close DECIMAL(12,4) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Additional Metrics
    vwap DECIMAL(12,4),
    trade_count INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (security_id, time_id, timeframe),
    FOREIGN KEY (security_id) REFERENCES securities(security_id),
    FOREIGN KEY (time_id) REFERENCES time_dimension(time_id)
) PARTITION BY RANGE (time_id);

-- Create partitions (example - create monthly in application)
-- Partition naming: trading_history_YYYYMM

CREATE INDEX idx_trading_history_security ON trading_history(security_id);
CREATE INDEX idx_trading_history_time ON trading_history(time_id);
CREATE INDEX idx_trading_history_timeframe ON trading_history(timeframe);

-- ---------------------------------------------------------------------------
-- 5. NEWS_SENTIMENT - News with Impact Tracking (NO symbol duplication!)
-- ---------------------------------------------------------------------------
CREATE TABLE news_sentiment (
    news_id BIGSERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL,  -- FK to securities
    time_id BIGINT NOT NULL,        -- FK to time_dimension (when published)
    
    -- Content
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    url VARCHAR(1000),
    
    -- Source (normalized separately if needed)
    source_id INTEGER,  -- FK to news_sources table
    source VARCHAR(100) NOT NULL,  -- Temporary until sources normalized
    
    -- Sentiment Analysis
    sentiment_score DECIMAL(4,3),
    sentiment_label VARCHAR(20)
        CHECK (sentiment_label IN ('very_negative', 'negative', 'neutral', 'positive', 'very_positive')),
    
    -- Catalyst Tracking
    catalyst_type VARCHAR(50),
    catalyst_strength VARCHAR(20)
        CHECK (catalyst_strength IN ('weak', 'moderate', 'strong', 'very_strong')),
    
    -- Source Reliability (ML Feature)
    source_reliability_score DECIMAL(4,3) DEFAULT 0.500,
    verified_accuracy BOOLEAN DEFAULT FALSE,
    
    -- Price Impact (ML Feature - CRITICAL!)
    price_impact_5min DECIMAL(6,3),   -- Very short-term
    price_impact_15min DECIMAL(6,3),  -- Day trading critical
    price_impact_30min DECIMAL(6,3),
    price_impact_1h DECIMAL(6,3),
    price_impact_4h DECIMAL(6,3),
    price_impact_1d DECIMAL(6,3),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    FOREIGN KEY (security_id) REFERENCES securities(security_id),
    FOREIGN KEY (time_id) REFERENCES time_dimension(time_id)
);

CREATE INDEX idx_news_security ON news_sentiment(security_id);
CREATE INDEX idx_news_time ON news_sentiment(time_id);
CREATE INDEX idx_news_catalyst ON news_sentiment(catalyst_strength);
CREATE INDEX idx_news_reliable ON news_sentiment(source_reliability_score DESC) 
    WHERE source_reliability_score > 0.700;

-- ---------------------------------------------------------------------------
-- 6. TECHNICAL_INDICATORS - All indicators with FK to security & time
-- ---------------------------------------------------------------------------
CREATE TABLE technical_indicators (
    indicator_id BIGSERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL,  -- FK to securities
    time_id BIGINT NOT NULL,        -- FK to time_dimension
    timeframe VARCHAR(10) NOT NULL,
    
    -- Moving Averages
    sma_20 DECIMAL(12,4),
    sma_50 DECIMAL(12,4),
    sma_200 DECIMAL(12,4),
    ema_9 DECIMAL(12,4),
    ema_21 DECIMAL(12,4),
    
    -- Momentum
    rsi_14 DECIMAL(6,3),
    macd DECIMAL(12,4),
    macd_signal DECIMAL(12,4),
    macd_histogram DECIMAL(12,4),
    
    -- Volatility
    atr_14 DECIMAL(12,4),
    bollinger_upper DECIMAL(12,4),
    bollinger_middle DECIMAL(12,4),
    bollinger_lower DECIMAL(12,4),
    
    -- Volume Analysis (ML Critical)
    vpoc DECIMAL(12,4),
    vah DECIMAL(12,4),
    val DECIMAL(12,4),
    obv BIGINT,
    volume_ratio DECIMAL(6,3),
    unusual_volume_flag BOOLEAN,
    
    -- Market Microstructure (ML Critical)
    bid_ask_spread DECIMAL(8,4),
    order_flow_imbalance DECIMAL(6,3),
    
    -- Support/Resistance
    support_level DECIMAL(12,4),
    resistance_level DECIMAL(12,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(security_id, time_id, timeframe),
    FOREIGN KEY (security_id) REFERENCES securities(security_id),
    FOREIGN KEY (time_id) REFERENCES time_dimension(time_id)
);

CREATE INDEX idx_tech_security_time ON technical_indicators(security_id, time_id);
CREATE INDEX idx_tech_timeframe ON technical_indicators(timeframe);
CREATE INDEX idx_tech_unusual_volume ON technical_indicators(unusual_volume_flag) 
    WHERE unusual_volume_flag = TRUE;

-- ---------------------------------------------------------------------------
-- 7. SECTOR_CORRELATIONS - Cross-sectional Analysis (Daily)
-- ---------------------------------------------------------------------------
CREATE TABLE sector_correlations (
    correlation_id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL,  -- FK to securities
    date DATE NOT NULL,
    
    -- Sector Performance (sector data from securities.sector_id)
    sector_relative_strength DECIMAL(6,3),
    sector_rank INTEGER,
    total_in_sector INTEGER,
    
    -- Market Correlations
    correlation_spy DECIMAL(5,3),
    correlation_qqq DECIMAL(5,3),
    correlation_iwm DECIMAL(5,3),
    correlation_rolling_30d DECIMAL(5,3),
    
    -- Beta Analysis
    beta_spy DECIMAL(6,3),
    beta_stability_score DECIMAL(5,3),
    
    -- Sector Rotation
    sector_momentum VARCHAR(20)
        CHECK (sector_momentum IN ('accumulating', 'distributing', 'neutral', 'unknown')),
    rotation_score DECIMAL(6,3),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(security_id, date),
    FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE INDEX idx_sector_corr_security_date ON sector_correlations(security_id, date DESC);
CREATE INDEX idx_sector_corr_date ON sector_correlations(date DESC);

-- ---------------------------------------------------------------------------
-- 8. ECONOMIC_INDICATORS - FREE FRED Data (No security FK - market-wide)
-- ---------------------------------------------------------------------------
CREATE TABLE economic_indicators (
    indicator_id SERIAL PRIMARY KEY,
    
    indicator_code VARCHAR(50) NOT NULL,
    indicator_name VARCHAR(200),
    category VARCHAR(50) NOT NULL
        CHECK (category IN ('interest_rate', 'inflation', 'employment', 'gdp', 'market_sentiment')),
    
    date DATE NOT NULL,
    value DECIMAL(12,4),
    
    -- Change Analysis
    value_change_1d DECIMAL(12,4),
    value_change_1w DECIMAL(12,4),
    value_change_1m DECIMAL(12,4),
    
    -- Market Impact
    market_correlation DECIMAL(5,3),
    volatility_impact VARCHAR(20)
        CHECK (volatility_impact IN ('low', 'medium', 'high', 'unknown')),
    
    -- Metadata
    source VARCHAR(50) DEFAULT 'FRED',
    units VARCHAR(50),
    frequency VARCHAR(20),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(indicator_code, date)
);

CREATE INDEX idx_econ_code_date ON economic_indicators(indicator_code, date DESC);
CREATE INDEX idx_econ_category ON economic_indicators(category);
CREATE INDEX idx_econ_date ON economic_indicators(date DESC);

-- ---------------------------------------------------------------------------
-- 9. SECURITY_FUNDAMENTALS - Quarterly Earnings (FK to securities)
-- ---------------------------------------------------------------------------
CREATE TABLE security_fundamentals (
    fundamental_id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL,  -- FK to securities
    
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    
    -- Earnings Timing
    earnings_announcement_date DATE,
    earnings_announcement_time VARCHAR(20),
    
    -- Financial Metrics
    revenue DECIMAL(18,2),
    earnings DECIMAL(18,2),
    eps DECIMAL(10,2),
    
    -- Estimate vs Actual (ML Feature)
    eps_estimate DECIMAL(10,2),
    eps_actual DECIMAL(10,2),
    eps_surprise DECIMAL(6,2),
    revenue_estimate DECIMAL(18,2),
    revenue_actual DECIMAL(18,2),
    revenue_surprise DECIMAL(6,2),
    
    -- Guidance (ML Feature)
    guidance_raised BOOLEAN,
    guidance_lowered BOOLEAN,
    guidance_text TEXT,
    
    -- Valuation
    pe_ratio DECIMAL(8,2),
    pb_ratio DECIMAL(8,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(security_id, fiscal_year, fiscal_quarter),
    FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE INDEX idx_fundamentals_security ON security_fundamentals(security_id, fiscal_year DESC);
CREATE INDEX idx_fundamentals_earnings_date ON security_fundamentals(earnings_announcement_date);

-- ---------------------------------------------------------------------------
-- 10. ANALYST_ESTIMATES - Estimate Tracking (FK to securities)
-- ---------------------------------------------------------------------------
CREATE TABLE analyst_estimates (
    estimate_id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL,  -- FK to securities
    
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    
    estimate_date DATE NOT NULL,
    analyst_firm VARCHAR(100),
    eps_estimate DECIMAL(10,2),
    revenue_estimate DECIMAL(18,2),
    
    -- Revision Tracking (ML Feature)
    is_revision BOOLEAN DEFAULT FALSE,
    previous_eps_estimate DECIMAL(10,2),
    revision_direction VARCHAR(10)
        CHECK (revision_direction IN ('upgrade', 'downgrade', 'maintain', NULL)),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE INDEX idx_estimates_security ON analyst_estimates(security_id, estimate_date DESC);
CREATE INDEX idx_estimates_revisions ON analyst_estimates(is_revision) WHERE is_revision = TRUE;

-- ============================================================================
-- TRADING TABLES (Still use security_id FK!)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 11. TRADING_CYCLES - Trading Cycle Management
-- ---------------------------------------------------------------------------
CREATE TABLE trading_cycles (
    cycle_id VARCHAR(20) PRIMARY KEY,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('aggressive', 'normal', 'conservative')),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    
    -- Risk Configuration
    max_positions INTEGER NOT NULL DEFAULT 5,
    max_daily_loss DECIMAL(12,2) NOT NULL DEFAULT 2000.00,
    position_size_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.0,
    risk_level DECIMAL(3,2) NOT NULL DEFAULT 0.02,
    
    -- Timing
    scan_frequency INTEGER NOT NULL DEFAULT 300,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    
    -- Risk Metrics
    total_risk_budget DECIMAL(12,2) NOT NULL DEFAULT 2000.00,
    used_risk_budget DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    current_positions INTEGER NOT NULL DEFAULT 0,
    current_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 12. POSITIONS - Position Tracking (Uses security_id FK!)
-- ---------------------------------------------------------------------------
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id INTEGER NOT NULL,  -- FK to securities (NOT symbol!)
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),
    
    -- Position Details
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    
    -- Risk Management
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    risk_amount DECIMAL(12,2) NOT NULL,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'partial', 'risk_reduced')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    
    -- P&L
    unrealized_pnl DECIMAL(12,2),
    realized_pnl DECIMAL(12,2),
    pnl_percent DECIMAL(6,2),
    
    close_reason VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status);

-- ---------------------------------------------------------------------------
-- 13. SCAN_RESULTS - Scanner Results (Uses security_id FK!)
-- ---------------------------------------------------------------------------
CREATE TABLE scan_results (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id INTEGER NOT NULL,  -- FK to securities
    scan_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Scores
    momentum_score DECIMAL(5,2) NOT NULL,
    volume_score DECIMAL(5,2) NOT NULL,
    catalyst_score DECIMAL(5,2) NOT NULL,
    technical_score DECIMAL(5,2),
    composite_score DECIMAL(5,2) NOT NULL,
    
    -- Market Data (snapshot - detailed data in trading_history)
    price DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Rankings
    rank INTEGER,
    selected_for_trading BOOLEAN DEFAULT FALSE,
    
    scan_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE INDEX idx_scan_results_cycle ON scan_results(cycle_id, scan_timestamp DESC);
CREATE INDEX idx_scan_results_security ON scan_results(security_id);
CREATE INDEX idx_scan_results_score ON scan_results(composite_score DESC);

-- ============================================================================
-- ML FEATURE VIEWS (JOINs across normalized tables)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- V_ML_FEATURES - Complete ML feature set via JOINs
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW v_ml_features AS
SELECT 
    s.security_id,
    s.symbol,
    s.company_name,
    sec.sector_name,
    td.timestamp,
    td.date,
    th.timeframe,
    
    -- Price Action
    th.close,
    th.volume,
    th.vwap,
    
    -- Technical Indicators
    ti.rsi_14,
    ti.macd,
    ti.vpoc,
    ti.bid_ask_spread,
    ti.order_flow_imbalance,
    ti.unusual_volume_flag,
    
    -- Sector Context
    sc.sector_relative_strength,
    sc.sector_rank,
    sc.correlation_spy,
    sc.beta_spy,
    
    -- Economic Context
    ei_vix.value as vix_level,
    ei_rates.value as fed_funds_rate,
    
    -- News Catalyst (last 1 hour)
    COUNT(ns.news_id) FILTER (WHERE td.timestamp - INTERVAL '1 hour' <= ns_time.timestamp) as news_count_1h,
    MAX(ns.catalyst_strength) FILTER (WHERE td.timestamp - INTERVAL '1 hour' <= ns_time.timestamp) as max_catalyst_strength,
    AVG(ns.sentiment_score) FILTER (WHERE td.timestamp - INTERVAL '1 hour' <= ns_time.timestamp) as avg_sentiment
    
FROM trading_history th
JOIN securities s ON s.security_id = th.security_id
JOIN time_dimension td ON td.time_id = th.time_id
LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
LEFT JOIN technical_indicators ti ON ti.security_id = th.security_id 
    AND ti.time_id = th.time_id 
    AND ti.timeframe = th.timeframe
LEFT JOIN sector_correlations sc ON sc.security_id = th.security_id 
    AND sc.date = td.date
LEFT JOIN economic_indicators ei_vix ON ei_vix.indicator_code = 'VIXCLS' 
    AND ei_vix.date = td.date
LEFT JOIN economic_indicators ei_rates ON ei_rates.indicator_code = 'DFF' 
    AND ei_rates.date = td.date
LEFT JOIN news_sentiment ns ON ns.security_id = th.security_id
LEFT JOIN time_dimension ns_time ON ns_time.time_id = ns.time_id

WHERE th.timeframe IN ('5min', '15min', '1hour')
GROUP BY 
    s.security_id, s.symbol, s.company_name, sec.sector_name,
    td.timestamp, td.date, th.timeframe,
    th.close, th.volume, th.vwap,
    ti.rsi_14, ti.macd, ti.vpoc, ti.bid_ask_spread, ti.order_flow_imbalance, ti.unusual_volume_flag,
    sc.sector_relative_strength, sc.sector_rank, sc.correlation_spy, sc.beta_spy,
    ei_vix.value, ei_rates.value;

CREATE UNIQUE INDEX idx_ml_features_unique ON v_ml_features(security_id, timestamp, timeframe);

-- ---------------------------------------------------------------------------
-- V_SECURITIES_LATEST - Latest security data with all context
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW v_securities_latest AS
SELECT 
    s.security_id,
    s.symbol,
    s.company_name,
    sec.sector_name,
    s.is_active,
    
    -- Latest price data
    (SELECT close FROM trading_history th 
     JOIN time_dimension td ON td.time_id = th.time_id
     WHERE th.security_id = s.security_id 
     AND th.timeframe = '1day'
     ORDER BY td.timestamp DESC LIMIT 1) as latest_price,
    
    -- Latest news
    (SELECT ns_time.timestamp FROM news_sentiment ns
     JOIN time_dimension ns_time ON ns_time.time_id = ns.time_id
     WHERE ns.security_id = s.security_id
     ORDER BY ns_time.timestamp DESC LIMIT 1) as latest_news_date,
    
    -- Latest sector correlation
    (SELECT correlation_spy FROM sector_correlations sc
     WHERE sc.security_id = s.security_id
     ORDER BY sc.date DESC LIMIT 1) as latest_spy_correlation

FROM securities s
LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
WHERE s.is_active = TRUE;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Function: Get or create security_id from symbol
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    -- Try to get existing
    SELECT security_id INTO v_security_id
    FROM securities
    WHERE symbol = p_symbol;
    
    -- If not found, create it
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, name)
        VALUES (p_symbol, p_symbol)
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Function: Get or create time_id from timestamp
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_or_create_time(p_timestamp TIMESTAMPTZ)
RETURNS BIGINT AS $$
DECLARE
    v_time_id BIGINT;
BEGIN
    -- Try to get existing
    SELECT time_id INTO v_time_id
    FROM time_dimension
    WHERE timestamp = p_timestamp;
    
    -- If not found, create it
    IF v_time_id IS NULL THEN
        INSERT INTO time_dimension (
            timestamp, date, year, quarter, month, week,
            day_of_month, day_of_week, day_of_year,
            hour, minute
        ) VALUES (
            p_timestamp,
            DATE(p_timestamp),
            EXTRACT(YEAR FROM p_timestamp),
            EXTRACT(QUARTER FROM p_timestamp),
            EXTRACT(MONTH FROM p_timestamp),
            EXTRACT(WEEK FROM p_timestamp),
            EXTRACT(DAY FROM p_timestamp),
            EXTRACT(DOW FROM p_timestamp),
            EXTRACT(DOY FROM p_timestamp),
            EXTRACT(HOUR FROM p_timestamp),
            EXTRACT(MINUTE FROM p_timestamp)
        )
        RETURNING time_id INTO v_time_id;
    END IF;
    
    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Insert default sectors
INSERT INTO sectors (sector_name, sector_code, sector_etf_symbol) VALUES
    ('Technology', 'XLK', 'XLK'),
    ('Healthcare', 'XLV', 'XLV'),
    ('Financials', 'XLF', 'XLF'),
    ('Consumer Discretionary', 'XLY', 'XLY'),
    ('Communication Services', 'XLC', 'XLC'),
    ('Industrials', 'XLI', 'XLI'),
    ('Consumer Staples', 'XLP', 'XLP'),
    ('Energy', 'XLE', 'XLE'),
    ('Utilities', 'XLU', 'XLU'),
    ('Real Estate', 'XLRE', 'XLRE'),
    ('Materials', 'XLB', 'XLB')
ON CONFLICT (sector_name) DO NOTHING;

-- Insert FRED economic indicators to track
INSERT INTO economic_indicators (indicator_code, indicator_name, category, units, frequency, date, value) VALUES
    ('DFF', 'Federal Funds Effective Rate', 'interest_rate', 'percentage', 'daily', CURRENT_DATE, 0),
    ('T10Y2Y', '10-Year Treasury - 2-Year Spread', 'interest_rate', 'percentage', 'daily', CURRENT_DATE, 0),
    ('CPIAUCSL', 'Consumer Price Index', 'inflation', 'index', 'monthly', CURRENT_DATE, 0),
    ('UNRATE', 'Unemployment Rate', 'employment', 'percentage', 'monthly', CURRENT_DATE, 0),
    ('PAYEMS', 'Nonfarm Payrolls', 'employment', 'thousands', 'monthly', CURRENT_DATE, 0),
    ('GDP', 'Gross Domestic Product', 'gdp', 'billions', 'quarterly', CURRENT_DATE, 0),
    ('VIXCLS', 'VIX Volatility Index', 'market_sentiment', 'index', 'daily', CURRENT_DATE, 0)
ON CONFLICT (indicator_code, date) DO NOTHING;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================

/*
-- Example 1: Store news with proper FKs
security_id = SELECT get_or_create_security('AAPL');
time_id = SELECT get_or_create_time(NOW());

INSERT INTO news_sentiment (security_id, time_id, headline, sentiment_score, ...)
VALUES (security_id, time_id, 'Apple announces...', 0.85, ...);

-- Example 2: Query with JOINs (NO symbol duplication!)
SELECT 
    s.symbol,
    s.company_name,
    sec.sector_name,
    ns.headline,
    ns.sentiment_score,
    td.timestamp
FROM news_sentiment ns
JOIN securities s ON s.security_id = ns.security_id
JOIN sectors sec ON sec.sector_id = s.sector_id
JOIN time_dimension td ON td.time_id = ns.time_id
WHERE td.timestamp >= NOW() - INTERVAL '1 day'
ORDER BY td.timestamp DESC;

-- Example 3: Use ML feature view (everything pre-joined!)
SELECT * FROM v_ml_features
WHERE symbol = 'AAPL'
AND timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
*/