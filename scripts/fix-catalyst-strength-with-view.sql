-- Name of Application: Catalyst Trading System
-- Name of file: fix-catalyst-strength-with-view.sql
-- Version: 5.1.1
-- Last Updated: 2025-10-06
-- Purpose: Fix catalyst_strength type and recreate dependent materialized view

-- REVISION HISTORY:
-- v5.1.1 (2025-10-06) - Change catalyst_strength VARCHAR → DECIMAL and recreate v_ml_features

-- Description:
-- The v_ml_features materialized view depends on catalyst_strength column
-- Must drop view with CASCADE, change column type, then recreate view

-- STEP 1: Drop materialized view (this will allow column change)
DROP MATERIALIZED VIEW IF EXISTS v_ml_features CASCADE;

-- STEP 2: Change catalyst_strength from VARCHAR to DECIMAL
ALTER TABLE news_sentiment DROP COLUMN catalyst_strength;
ALTER TABLE news_sentiment ADD COLUMN catalyst_strength DECIMAL(4,3);

-- Add constraint (0.0 to 1.0)
ALTER TABLE news_sentiment ADD CONSTRAINT catalyst_strength_range 
CHECK (catalyst_strength >= 0 AND catalyst_strength <= 1);

-- STEP 3: Recreate v_ml_features materialized view
CREATE MATERIALIZED VIEW v_ml_features AS
SELECT 
    s.security_id,
    s.symbol,
    s.company_name,
    sec.sector_name,
    td.timestamp,
    td.date,
    th.timeframe,
    
    -- Price action
    th.close,
    th.volume,
    th.vwap,
    
    -- Technical indicators
    ti.rsi_14,
    ti.macd,
    ti.vpoc,
    ti.bid_ask_spread,
    ti.unusual_volume_flag,
    
    -- Sector context
    sc.sector_relative_strength,
    sc.sector_rank,
    sc.correlation_spy,
    sc.beta_spy,
    
    -- Economic context
    ei_vix.value as vix_level,
    ei_rates.value as fed_funds_rate,
    
    -- News catalyst (1 hour window) - NOW USES DECIMAL catalyst_strength
    COUNT(ns.news_id) as news_count_1h,
    MAX(ns.catalyst_strength) as max_catalyst_strength,  -- Now DECIMAL!
    AVG(ns.sentiment_score) as avg_sentiment
    
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
    AND (SELECT timestamp FROM time_dimension WHERE time_id = ns.time_id) 
        >= td.timestamp - INTERVAL '1 hour'

WHERE th.timeframe IN ('5min', '15min', '1hour')
GROUP BY 
    s.security_id, s.symbol, s.company_name, sec.sector_name,
    td.timestamp, td.date, th.timeframe,
    th.close, th.volume, th.vwap,
    ti.rsi_14, ti.macd, ti.vpoc, ti.bid_ask_spread, ti.unusual_volume_flag,
    sc.sector_relative_strength, sc.sector_rank, sc.correlation_spy, sc.beta_spy,
    ei_vix.value, ei_rates.value;

CREATE UNIQUE INDEX idx_ml_features_unique 
    ON v_ml_features(security_id, timestamp, timeframe);

-- STEP 4: Verify changes
SELECT column_name, data_type, numeric_precision, numeric_scale 
FROM information_schema.columns 
WHERE table_name = 'news_sentiment' AND column_name = 'catalyst_strength';

SELECT matviewname FROM pg_matviews WHERE matviewname = 'v_ml_features';

-- Success message
SELECT '✅ catalyst_strength fixed and v_ml_features recreated' as status;
