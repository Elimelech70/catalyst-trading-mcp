-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: fix-background-job-sql-bug.sql
-- Version: 1.0.0
-- Last Updated: 2025-10-13
-- Purpose: Fix SQL type casting error in news price impact calculation
--
-- REVISION HISTORY:
-- v1.0.0 (2025-10-13) - Background Job SQL Fix
--   - Fix timestamp + interval comparison issue
--   - Proper type casting for timestamp arithmetic
--   - Test the corrected query
--
-- Description:
-- The background job calculate_news_price_impact() has a SQL bug:
-- "operator does not exist: timestamp with time zone >= interval"
--
-- Root cause: Comparing timestamp directly with interval result
-- Fix: Properly cast and add interval to timestamp before comparison
-- ============================================================================

\echo '========================================='
\echo 'CATALYST TRADING SYSTEM'
\echo 'Fix Background Job SQL Bug'
\echo '========================================='
\echo ''

-- ============================================================================
-- STEP 1: Demonstrate the problem
-- ============================================================================
\echo 'STEP 1: Demonstrating the SQL error'
\echo '------------------------------------'

\echo 'This query will FAIL (same error as background job):'
\echo ''

-- This will fail with "operator does not exist" error
-- SELECT NOW()::timestamptz >= NOW() + INTERVAL '5 minutes';

\echo 'Attempting problematic query pattern...'

DO $$
DECLARE
    v_test_time TIMESTAMPTZ := NOW();
BEGIN
    BEGIN
        -- This is the WRONG pattern (what the code currently does)
        PERFORM *
        FROM (SELECT NOW()::timestamptz as ts) sub
        WHERE ts >= v_test_time + INTERVAL '5 minutes';
        
        RAISE NOTICE '❌ Should have failed but didn''t!';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE '✅ Confirmed error: %', SQLERRM;
            RAISE NOTICE '   This is the bug affecting the background job!';
    END;
END $$;

\echo ''

-- ============================================================================
-- STEP 2: Show the correct pattern
-- ============================================================================
\echo 'STEP 2: Correct SQL pattern'
\echo '----------------------------'

\echo 'This query will WORK (proper timestamp arithmetic):'
\echo ''

DO $$
DECLARE
    v_test_time TIMESTAMPTZ := NOW();
    v_target_time TIMESTAMPTZ;
    v_result BOOLEAN;
BEGIN
    -- CORRECT: Add interval to timestamp FIRST, then compare
    v_target_time := v_test_time + INTERVAL '5 minutes';
    v_result := NOW()::timestamptz >= v_target_time;
    
    RAISE NOTICE '✅ Correct pattern works!';
    RAISE NOTICE '   Start time: %', v_test_time;
    RAISE NOTICE '   Target time (+5min): %', v_target_time;
    RAISE NOTICE '   Comparison result: %', v_result;
END $$;

\echo ''

-- ============================================================================
-- STEP 3: Test the corrected query pattern
-- ============================================================================
\echo 'STEP 3: Testing corrected query with real data'
\echo '-----------------------------------------------'

\echo 'Creating test data...'

-- Insert test article if not exists
DO $$
DECLARE
    v_security_id INTEGER;
    v_time_id BIGINT;
    v_news_id BIGINT;
    v_published_time TIMESTAMPTZ := NOW() - INTERVAL '10 minutes';
BEGIN
    -- Get/create security
    v_security_id := get_or_create_security('TEST_SQL_FIX');
    v_time_id := get_or_create_time(v_published_time);
    
    -- Insert test news article
    INSERT INTO news_sentiment (
        security_id, time_id,
        headline, source,
        sentiment_score, sentiment_label,
        catalyst_type, catalyst_strength
    ) VALUES (
        v_security_id, v_time_id,
        'SQL FIX TEST - ' || NOW()::TEXT,
        'diagnostic-test',
        0.5, 'neutral',
        'earnings', 'moderate'
    )
    ON CONFLICT DO NOTHING
    RETURNING news_id INTO v_news_id;
    
    IF v_news_id IS NOT NULL THEN
        RAISE NOTICE '✅ Test article created: news_id=%', v_news_id;
    ELSE
        RAISE NOTICE 'ℹ️  Test article already exists (conflict)';
    END IF;
END $$;

\echo ''
\echo 'Testing WRONG query pattern (current bug):'

-- This demonstrates the current bug
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    BEGIN
        -- WRONG: This is what the background job currently does
        SELECT COUNT(*) INTO v_count
        FROM news_sentiment ns
        JOIN time_dimension td ON td.time_id = ns.time_id
        WHERE td.timestamp >= td.timestamp + INTERVAL '5 minutes';
        
        RAISE NOTICE '❌ Query should have failed but returned: %', v_count;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE '✅ Confirmed bug: %', SQLERRM;
    END;
END $$;

\echo ''
\echo 'Testing CORRECT query pattern (the fix):'

-- This is the corrected pattern
DO $$
DECLARE
    v_count INTEGER;
    v_base_time TIMESTAMPTZ := NOW() - INTERVAL '10 minutes';
BEGIN
    -- CORRECT: Pre-calculate the target time
    SELECT COUNT(*) INTO v_count
    FROM (
        SELECT 
            td.timestamp,
            (v_base_time + INTERVAL '5 minutes') as target_time
        FROM time_dimension td
        WHERE td.timestamp >= (v_base_time + INTERVAL '5 minutes')
    ) sub;
    
    RAISE NOTICE '✅ Corrected query works! Found % records', v_count;
END $$;

\echo ''

-- ============================================================================
-- STEP 4: Show the fix for the actual background job query
-- ============================================================================
\echo 'STEP 4: Corrected background job query'
\echo '---------------------------------------'

\echo 'This is how the Python code should construct the query:'
\echo ''
\echo '-- BEFORE (WRONG - causes the error):'
\echo 'SELECT close FROM trading_history th'
\echo 'JOIN time_dimension td ON td.time_id = th.time_id'
\echo 'WHERE th.security_id = $1'
\echo '  AND td.timestamp >= $2 + INTERVAL ''5 minutes'''
\echo '                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^'
\echo '                      This causes type error!'
\echo ''
\echo '-- AFTER (CORRECT - fix the comparison):'
\echo 'SELECT close FROM trading_history th'
\echo 'JOIN time_dimension td ON td.time_id = th.time_id'
\echo 'WHERE th.security_id = $1'
\echo '  AND td.timestamp >= ($2::timestamptz + INTERVAL ''5 minutes'')'
\echo '                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^'
\echo '                       Proper casting and parentheses!'
\echo ''

-- Demonstrate with actual query
DO $$
DECLARE
    v_published_at TIMESTAMPTZ := NOW() - INTERVAL '15 minutes';
    v_security_id INTEGER := 1;
    v_price DECIMAL;
BEGIN
    RAISE NOTICE 'Testing corrected query pattern...';
    RAISE NOTICE 'Published at: %', v_published_at;
    RAISE NOTICE 'Looking for price 5 minutes after: %', v_published_at + INTERVAL '5 minutes';
    
    -- CORRECTED QUERY (this is what the code should do)
    SELECT close INTO v_price
    FROM trading_history th
    JOIN time_dimension td ON td.time_id = th.time_id
    WHERE th.security_id = v_security_id
      AND td.timestamp >= (v_published_at + INTERVAL '5 minutes')
    ORDER BY td.timestamp ASC
    LIMIT 1;
    
    IF v_price IS NOT NULL THEN
        RAISE NOTICE '✅ Query executed successfully! Price found: $%', v_price;
    ELSE
        RAISE NOTICE 'ℹ️  Query executed (no price data for this test)';
    END IF;
END $$;

-- ============================================================================
-- CLEANUP
-- ============================================================================
\echo ''
\echo 'Cleaning up test data...'

DELETE FROM news_sentiment 
WHERE headline LIKE 'SQL FIX TEST%';

\echo '✅ Test data cleaned'

-- ============================================================================
-- SUMMARY
-- ============================================================================
\echo ''
\echo '========================================='
\echo 'SUMMARY & FIX INSTRUCTIONS'
\echo '========================================='
\echo ''
\echo 'Problem Identified:'
\echo '  • Background job has SQL type casting error'
\echo '  • Comparing "timestamp >= interval" fails'
\echo '  • Error: "operator does not exist: timestamp with time zone >= interval"'
\echo ''
\echo 'Root Cause:'
\echo '  • Query: WHERE td.timestamp >= $2 + INTERVAL ''5 minutes'''
\echo '  • PostgreSQL evaluates this as: timestamp >= (timestamp + interval)'
\echo '  • But the result is: timestamp >= interval (type error!)'
\echo ''
\echo 'The Fix (in Python code):'
\echo '  Change this:'
\echo '    AND td.timestamp >= $2 + INTERVAL ''5 minutes'''
\echo ''
\echo '  To this:'
\echo '    AND td.timestamp >= ($2::timestamptz + INTERVAL ''5 minutes'')'
\echo ''
\echo '  Or better yet, pre-calculate in Python:'
\echo '    target_time = published_at + timedelta(minutes=5)'
\echo '    AND td.timestamp >= $2'
\echo ''
\echo 'Location to Fix:'
\echo '  • File: services/news/news-service.py (or news-service-v520.py)'
\echo '  • Function: calculate_news_price_impact()'
\echo '  • Lines: SQL query for price_5min, price_15min, price_30min'
\echo ''
\echo 'Next Steps:'
\echo '  1. Update the Python code with corrected SQL'
\echo '  2. Rebuild the Docker image'
\echo '  3. Restart the news service'
\echo '  4. Background job errors should stop'
\echo ''
\echo '========================================='
\echo 'END OF FIX DOCUMENTATION'
\echo '========================================='