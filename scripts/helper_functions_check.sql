-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: diagnostic-check-helper-functions.sql
-- Version: 1.0.0
-- Last Updated: 2025-10-13
-- Purpose: Verify helper functions exist and work correctly
--
-- REVISION HISTORY:
-- v1.0.0 (2025-10-13) - Initial diagnostic script
--   - Check if get_or_create_security() exists
--   - Check if get_or_create_time() exists
--   - Test both functions work
--   - Provide clear diagnostics
-- 
-- Description:
-- This script diagnoses why news articles are failing to store.
-- Run this FIRST before attempting any fixes.
-- ============================================================================

\echo '========================================='
\echo 'CATALYST TRADING SYSTEM'
\echo 'Helper Functions Diagnostic'
\echo '========================================='
\echo ''

-- ============================================================================
-- CHECK 1: Do helper functions exist?
-- ============================================================================
\echo 'CHECK 1: Helper Functions Existence'
\echo '-----------------------------------'

SELECT 
    proname as function_name,
    pg_get_function_arguments(oid) as arguments,
    pg_get_function_result(oid) as returns,
    CASE 
        WHEN proname = 'get_or_create_security' THEN '✅ EXISTS'
        WHEN proname = 'get_or_create_time' THEN '✅ EXISTS'
        ELSE '❓ UNKNOWN'
    END as status
FROM pg_proc
WHERE proname IN ('get_or_create_security', 'get_or_create_time')
ORDER BY proname;

\echo ''
\echo 'Expected: 2 functions should appear above'
\echo ''

-- Count found functions
DO $$
DECLARE
    v_function_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_function_count
    FROM pg_proc
    WHERE proname IN ('get_or_create_security', 'get_or_create_time');
    
    IF v_function_count = 0 THEN
        RAISE NOTICE '❌ CRITICAL: NO HELPER FUNCTIONS FOUND!';
        RAISE NOTICE '   This explains why ALL news articles fail to store.';
        RAISE NOTICE '   Action Required: Deploy normalized-database-schema-mcp-v50.sql';
        RAISE NOTICE '';
    ELSIF v_function_count = 1 THEN
        RAISE NOTICE '⚠️  WARNING: Only 1 of 2 helper functions found!';
        RAISE NOTICE '   Action Required: Deploy normalized-database-schema-mcp-v50.sql';
        RAISE NOTICE '';
    ELSIF v_function_count = 2 THEN
        RAISE NOTICE '✅ SUCCESS: Both helper functions exist';
        RAISE NOTICE '';
    END IF;
END $$;

-- ============================================================================
-- CHECK 2: Test get_or_create_security()
-- ============================================================================
\echo 'CHECK 2: Testing get_or_create_security()'
\echo '------------------------------------------'

DO $$
DECLARE
    v_security_id INTEGER;
    v_test_passed BOOLEAN := FALSE;
BEGIN
    -- Try to call the function
    BEGIN
        v_security_id := get_or_create_security('AAPL');
        
        IF v_security_id IS NOT NULL THEN
            RAISE NOTICE '✅ get_or_create_security(''AAPL'') returned: %', v_security_id;
            v_test_passed := TRUE;
        ELSE
            RAISE NOTICE '❌ get_or_create_security(''AAPL'') returned NULL';
        END IF;
    EXCEPTION
        WHEN undefined_function THEN
            RAISE NOTICE '❌ Function get_or_create_security() does NOT exist!';
            RAISE NOTICE '   Error: Function not found in database';
        WHEN OTHERS THEN
            RAISE NOTICE '❌ Function get_or_create_security() failed with error:';
            RAISE NOTICE '   Error: %', SQLERRM;
    END;
    
    IF NOT v_test_passed THEN
        RAISE NOTICE '';
        RAISE NOTICE '🛑 CRITICAL ISSUE: get_or_create_security() not working';
        RAISE NOTICE '   This is why news articles cannot be stored!';
        RAISE NOTICE '';
    END IF;
END $$;

-- ============================================================================
-- CHECK 3: Test get_or_create_time()
-- ============================================================================
\echo ''
\echo 'CHECK 3: Testing get_or_create_time()'
\echo '--------------------------------------'

DO $$
DECLARE
    v_time_id BIGINT;
    v_test_passed BOOLEAN := FALSE;
BEGIN
    -- Try to call the function
    BEGIN
        v_time_id := get_or_create_time(NOW());
        
        IF v_time_id IS NOT NULL THEN
            RAISE NOTICE '✅ get_or_create_time(NOW()) returned: %', v_time_id;
            v_test_passed := TRUE;
        ELSE
            RAISE NOTICE '❌ get_or_create_time(NOW()) returned NULL';
        END IF;
    EXCEPTION
        WHEN undefined_function THEN
            RAISE NOTICE '❌ Function get_or_create_time() does NOT exist!';
            RAISE NOTICE '   Error: Function not found in database';
        WHEN OTHERS THEN
            RAISE NOTICE '❌ Function get_or_create_time() failed with error:';
            RAISE NOTICE '   Error: %', SQLERRM;
    END;
    
    IF NOT v_test_passed THEN
        RAISE NOTICE '';
        RAISE NOTICE '🛑 CRITICAL ISSUE: get_or_create_time() not working';
        RAISE NOTICE '   This is why news articles cannot be stored!';
        RAISE NOTICE '';
    END IF;
END $$;

-- ============================================================================
-- CHECK 4: Verify news_sentiment table structure
-- ============================================================================
\echo ''
\echo 'CHECK 4: Verify news_sentiment Table'
\echo '-------------------------------------'

SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    CASE 
        WHEN column_name = 'url' AND character_maximum_length = 1000 THEN '⚠️  MAY BE TOO SHORT'
        WHEN column_name = 'url' AND character_maximum_length >= 2000 THEN '✅ ADEQUATE LENGTH'
        WHEN column_name = 'security_id' AND data_type = 'integer' THEN '✅ CORRECT TYPE'
        WHEN column_name = 'time_id' AND data_type = 'bigint' THEN '✅ CORRECT TYPE'
        ELSE '✅ OK'
    END as status
FROM information_schema.columns
WHERE table_name = 'news_sentiment'
AND column_name IN ('news_id', 'security_id', 'time_id', 'url', 'headline')
ORDER BY ordinal_position;

\echo ''

-- Check URL field length
DO $$
DECLARE
    v_url_length INTEGER;
BEGIN
    SELECT character_maximum_length INTO v_url_length
    FROM information_schema.columns
    WHERE table_name = 'news_sentiment' AND column_name = 'url';
    
    IF v_url_length IS NULL THEN
        RAISE NOTICE '❌ news_sentiment table or url column not found!';
    ELSIF v_url_length < 2000 THEN
        RAISE NOTICE '⚠️  WARNING: url column is VARCHAR(%), may be too short', v_url_length;
        RAISE NOTICE '   Modern URLs with tracking can exceed 1000 characters';
        RAISE NOTICE '   Recommendation: Increase to VARCHAR(2000) or TEXT';
    ELSE
        RAISE NOTICE '✅ url column length (%) is adequate', v_url_length;
    END IF;
END $$;

-- ============================================================================
-- FINAL SUMMARY
-- ============================================================================
\echo ''
\echo '========================================='
\echo 'DIAGNOSTIC SUMMARY'
\echo '========================================='

DO $$
DECLARE
    v_security_func_exists BOOLEAN;
    v_time_func_exists BOOLEAN;
    v_table_exists BOOLEAN;
    v_issues_found INTEGER := 0;
BEGIN
    -- Check function existence
    SELECT EXISTS (
        SELECT FROM pg_proc WHERE proname = 'get_or_create_security'
    ) INTO v_security_func_exists;
    
    SELECT EXISTS (
        SELECT FROM pg_proc WHERE proname = 'get_or_create_time'
    ) INTO v_time_func_exists;
    
    -- Check table existence
    SELECT EXISTS (
        SELECT FROM information_schema.tables WHERE table_name = 'news_sentiment'
    ) INTO v_table_exists;
    
    RAISE NOTICE '';
    RAISE NOTICE 'Status Check:';
    RAISE NOTICE '-------------';
    
    IF NOT v_security_func_exists THEN
        RAISE NOTICE '❌ get_or_create_security() MISSING';
        v_issues_found := v_issues_found + 1;
    ELSE
        RAISE NOTICE '✅ get_or_create_security() exists';
    END IF;
    
    IF NOT v_time_func_exists THEN
        RAISE NOTICE '❌ get_or_create_time() MISSING';
        v_issues_found := v_issues_found + 1;
    ELSE
        RAISE NOTICE '✅ get_or_create_time() exists';
    END IF;
    
    IF NOT v_table_exists THEN
        RAISE NOTICE '❌ news_sentiment table MISSING';
        v_issues_found := v_issues_found + 1;
    ELSE
        RAISE NOTICE '✅ news_sentiment table exists';
    END IF;
    
    RAISE NOTICE '';
    
    IF v_issues_found = 0 THEN
        RAISE NOTICE '✅ All critical components present';
        RAISE NOTICE '';
        RAISE NOTICE 'Next Steps:';
        RAISE NOTICE '1. Run diagnostic-test-article-insert.sql to test actual insertion';
        RAISE NOTICE '2. Check if URL length is causing failures';
        RAISE NOTICE '3. Review news service logs for specific error messages';
    ELSE
        RAISE NOTICE '❌ % critical issue(s) found!', v_issues_found;
        RAISE NOTICE '';
        RAISE NOTICE '🛑 ACTION REQUIRED:';
        RAISE NOTICE '1. Deploy schema: psql $DATABASE_URL -f normalized-database-schema-mcp-v50.sql';
        RAISE NOTICE '2. Verify deployment: psql $DATABASE_URL -f validate-schema-v50.sql';
        RAISE NOTICE '3. Restart news service after schema is deployed';
        RAISE NOTICE '';
        RAISE NOTICE 'Until schema is deployed, 100%% of news articles will fail to store!';
    END IF;
END $$;

\echo ''
\echo '========================================='
\echo 'END OF DIAGNOSTIC'
\echo '========================================='