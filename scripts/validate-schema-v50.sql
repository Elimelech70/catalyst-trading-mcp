-- Name of Application: Catalyst Trading System
-- Name of file: validate-schema-v50.sql
-- Version: 5.0.0
-- Last Updated: 2025-10-06
-- Purpose: Validate that normalized database schema v5.0 is properly deployed

-- REVISION HISTORY:
-- v5.0.0 (2025-10-06) - Initial validation script for normalized schema
-- - Checks all dimension tables exist
-- - Validates FK constraints
-- - Tests helper functions
-- - Confirms materialized views
-- - Verifies no orphaned records

-- Description:
-- Comprehensive validation to prove v5.0 normalized schema is deployed
-- Run this BEFORE starting any service updates
-- All checks must pass before proceeding to Playbook Step 1

-- ============================================================================
-- VALIDATION CHECK 1: DIMENSION TABLES EXIST
-- ============================================================================

\echo '========================================='
\echo 'CHECK 1: DIMENSION TABLES (Master Data)'
\echo '========================================='

SELECT 
    'securities' as table_name,
    EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'securities'
    ) as exists,
    (
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = 'securities'
    ) as column_count,
    CASE 
        WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'securities') 
        THEN '✅ EXISTS'
        ELSE '❌ MISSING'
    END as status
UNION ALL
SELECT 
    'sectors',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sectors'),
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'sectors'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sectors') 
    THEN '✅ EXISTS' ELSE '❌ MISSING' END
UNION ALL
SELECT 
    'time_dimension',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'time_dimension'),
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'time_dimension'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'time_dimension') 
    THEN '✅ EXISTS' ELSE '❌ MISSING' END;

\echo ''
\echo 'Expected: All 3 dimension tables should show ✅ EXISTS'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 2: FACT TABLES WITH FK CONSTRAINTS
-- ============================================================================

\echo '========================================='
\echo 'CHECK 2: FACT TABLES (Must use FKs)'
\echo '========================================='

SELECT 
    'trading_history' as table_name,
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'trading_history') as exists,
    EXISTS (
        SELECT FROM information_schema.table_constraints 
        WHERE table_name = 'trading_history' 
        AND constraint_type = 'FOREIGN KEY'
    ) as has_fk,
    CASE 
        WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'trading_history')
        AND EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'trading_history' AND constraint_type = 'FOREIGN KEY')
        THEN '✅ NORMALIZED'
        ELSE '❌ MISSING/DENORMALIZED'
    END as status
UNION ALL
SELECT 
    'news_sentiment',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'news_sentiment'),
    EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'news_sentiment' AND constraint_type = 'FOREIGN KEY'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'news_sentiment') 
    AND EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'news_sentiment' AND constraint_type = 'FOREIGN KEY')
    THEN '✅ NORMALIZED' ELSE '❌ MISSING/DENORMALIZED' END
UNION ALL
SELECT 
    'technical_indicators',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'technical_indicators'),
    EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'technical_indicators' AND constraint_type = 'FOREIGN KEY'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'technical_indicators') 
    AND EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'technical_indicators' AND constraint_type = 'FOREIGN KEY')
    THEN '✅ NORMALIZED' ELSE '❌ MISSING/DENORMALIZED' END
UNION ALL
SELECT 
    'scan_results',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'scan_results'),
    EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'scan_results' AND constraint_type = 'FOREIGN KEY'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'scan_results') 
    AND EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'scan_results' AND constraint_type = 'FOREIGN KEY')
    THEN '✅ NORMALIZED' ELSE '❌ MISSING/DENORMALIZED' END;

\echo ''
\echo 'Expected: All fact tables should show ✅ NORMALIZED (exists AND has FKs)'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 3: NO SYMBOL VARCHAR IN FACT TABLES (CRITICAL!)
-- ============================================================================

\echo '========================================='
\echo 'CHECK 3: NO SYMBOL DUPLICATION (Critical!)'
\echo '========================================='

-- Check if symbol VARCHAR exists in tables that should only have security_id FK
SELECT 
    table_name,
    column_name,
    data_type,
    '❌ DENORMALIZED - Remove this column!' as status
FROM information_schema.columns
WHERE table_name IN ('scan_results', 'news_sentiment', 'trading_history', 
                     'technical_indicators', 'positions', 'orders')
AND column_name = 'symbol'
ORDER BY table_name;

\echo ''
\echo 'Expected: NO ROWS (symbol should only exist in securities table)'
\echo 'If rows appear above, schema is DENORMALIZED - DO NOT PROCEED!'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 4: HELPER FUNCTIONS EXIST
-- ============================================================================

\echo '========================================='
\echo 'CHECK 4: HELPER FUNCTIONS'
\echo '========================================='

SELECT 
    proname as function_name,
    pg_get_function_arguments(oid) as arguments,
    pg_get_function_result(oid) as returns,
    CASE 
        WHEN proname IN ('get_or_create_security', 'get_or_create_time', 'detect_volatility_regime')
        THEN '✅ EXISTS'
        ELSE '⚠️ UNEXPECTED'
    END as status
FROM pg_proc
WHERE proname IN ('get_or_create_security', 'get_or_create_time', 'detect_volatility_regime')
ORDER BY proname;

\echo ''
\echo 'Expected: 3 functions (get_or_create_security, get_or_create_time, detect_volatility_regime)'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 5: TEST HELPER FUNCTIONS WORK
-- ============================================================================

\echo '========================================='
\echo 'CHECK 5: TEST HELPER FUNCTIONS'
\echo '========================================='

-- Test get_or_create_security
\echo 'Testing get_or_create_security(AAPL)...'
SELECT 
    get_or_create_security('AAPL') as security_id_test1,
    get_or_create_security('AAPL') as security_id_test2,
    CASE 
        WHEN get_or_create_security('AAPL') = get_or_create_security('AAPL')
        THEN '✅ Returns same ID for same symbol'
        ELSE '❌ FAIL - Different IDs for same symbol!'
    END as status;

-- Test get_or_create_time
\echo ''
\echo 'Testing get_or_create_time(NOW())...'
SELECT 
    get_or_create_time(NOW()) as time_id,
    CASE 
        WHEN get_or_create_time(NOW()) IS NOT NULL
        THEN '✅ Returns time_id'
        ELSE '❌ FAIL - NULL returned!'
    END as status;

\echo ''

-- ============================================================================
-- VALIDATION CHECK 6: FOREIGN KEY CONSTRAINTS ENFORCED
-- ============================================================================

\echo '========================================='
\echo 'CHECK 6: FK CONSTRAINTS DETAILS'
\echo '========================================='

SELECT 
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    '✅ FK enforced' as status
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu 
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;

\echo ''
\echo 'Expected: Multiple FK constraints shown above'
\echo 'All fact tables must reference securities(security_id)'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 7: MATERIALIZED VIEWS EXIST
-- ============================================================================

\echo '========================================='
\echo 'CHECK 7: MATERIALIZED VIEWS (ML Features)'
\echo '========================================='

SELECT 
    matviewname as view_name,
    schemaname,
    CASE 
        WHEN matviewname IN ('v_ml_features', 'v_securities_latest', 'v_event_correlations')
        THEN '✅ EXISTS'
        ELSE '⚠️ UNEXPECTED'
    END as status
FROM pg_matviews
WHERE schemaname = 'public'
ORDER BY matviewname;

\echo ''
\echo 'Expected: v_ml_features, v_securities_latest, v_event_correlations'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 8: ADAPTIVE SAMPLING TABLES
-- ============================================================================

\echo '========================================='
\echo 'CHECK 8: ADAPTIVE SAMPLING TABLES (v5.0)'
\echo '========================================='

SELECT 
    'active_securities' as table_name,
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'active_securities') as exists,
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'active_securities')
    THEN '✅ EXISTS' ELSE '❌ MISSING' END as status
UNION ALL
SELECT 
    'volatility_regimes',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'volatility_regimes'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'volatility_regimes')
    THEN '✅ EXISTS' ELSE '❌ MISSING' END
UNION ALL
SELECT 
    'adaptive_sampling_rules',
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'adaptive_sampling_rules'),
    CASE WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'adaptive_sampling_rules')
    THEN '✅ EXISTS' ELSE '❌ MISSING' END;

\echo ''
\echo 'Expected: All 3 adaptive sampling tables should exist'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 9: NO ORPHANED RECORDS (FK Integrity)
-- ============================================================================

\echo '========================================='
\echo 'CHECK 9: NO ORPHANED RECORDS'
\echo '========================================='

-- Only run if tables exist
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'scan_results') 
       AND EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'scan_results' AND column_name = 'security_id') THEN
        RAISE NOTICE 'Checking scan_results for orphans...';
    END IF;
END $$;

-- Check scan_results
SELECT 
    'scan_results' as table_name,
    COUNT(*) as orphan_count,
    CASE 
        WHEN COUNT(*) = 0 THEN '✅ No orphans'
        ELSE '❌ ORPHANED RECORDS FOUND!'
    END as status
FROM scan_results sr
LEFT JOIN securities s ON s.security_id = sr.security_id
WHERE s.security_id IS NULL
AND EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'scan_results' AND column_name = 'security_id');

\echo ''
\echo 'Expected: 0 orphaned records (or query fails if still denormalized)'
\echo ''

-- ============================================================================
-- VALIDATION CHECK 10: SECTORS SEEDED
-- ============================================================================

\echo '========================================='
\echo 'CHECK 10: DIMENSION DATA SEEDED'
\echo '========================================='

SELECT 
    'sectors' as dimension_table,
    COUNT(*) as record_count,
    CASE 
        WHEN COUNT(*) >= 11 THEN '✅ Seeded (11 GICS sectors)'
        WHEN COUNT(*) > 0 THEN '⚠️ Partially seeded'
        ELSE '❌ NOT SEEDED'
    END as status
FROM sectors
WHERE EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sectors');

\echo ''
\echo 'Expected: 11 GICS sectors seeded'
\echo ''

-- ============================================================================
-- FINAL VALIDATION SUMMARY
-- ============================================================================

\echo ''
\echo '========================================='
\echo 'VALIDATION SUMMARY - STEP 0 CHECKLIST'
\echo '========================================='
\echo ''
\echo 'STEP 0 IS COMPLETE ONLY IF ALL BELOW ARE TRUE:'
\echo ''
\echo '✅ 1. All dimension tables exist (securities, sectors, time_dimension)'
\echo '✅ 2. All fact tables have FK constraints'
\echo '✅ 3. NO symbol VARCHAR in fact tables (only in securities!)'
\echo '✅ 4. Helper functions exist (get_or_create_security, get_or_create_time)'
\echo '✅ 5. Helper functions work correctly'
\echo '✅ 6. FK constraints enforced (scan_results → securities, etc.)'
\echo '✅ 7. Materialized views exist (v_ml_features, v_securities_latest)'
\echo '✅ 8. Adaptive sampling tables exist'
\echo '✅ 9. No orphaned records (FK integrity)'
\echo '✅ 10. Sectors seeded (11 GICS sectors)'
\echo ''
\echo '========================================='
\echo 'IF ANY CHECK FAILS → STEP 0 INCOMPLETE!'
\echo 'DO NOT PROCEED TO SERVICE UPDATES!'
\echo '========================================='
\echo ''

-- Quick status check
DO $$
DECLARE
    v_securities_exists BOOLEAN;
    v_has_symbol_in_facts BOOLEAN;
    v_has_fks BOOLEAN;
    v_helpers_exist BOOLEAN;
    v_step0_complete BOOLEAN;
BEGIN
    -- Check key requirements
    v_securities_exists := EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'securities');
    
    v_has_symbol_in_facts := EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name IN ('scan_results', 'news_sentiment', 'trading_history')
        AND column_name = 'symbol'
    );
    
    v_has_fks := EXISTS (
        SELECT FROM information_schema.table_constraints 
        WHERE table_name IN ('scan_results', 'news_sentiment', 'trading_history')
        AND constraint_type = 'FOREIGN KEY'
    );
    
    v_helpers_exist := EXISTS (
        SELECT FROM pg_proc 
        WHERE proname IN ('get_or_create_security', 'get_or_create_time')
        GROUP BY 1 HAVING COUNT(*) = 2
    );
    
    v_step0_complete := v_securities_exists AND NOT v_has_symbol_in_facts AND v_has_fks AND v_helpers_exist;
    
    IF v_step0_complete THEN
        RAISE NOTICE '🎉 STEP 0 COMPLETE - Schema v5.0 is properly deployed!';
        RAISE NOTICE '✅ Ready to proceed with service updates (Playbook Steps 1-8)';
    ELSE
        RAISE NOTICE '❌ STEP 0 INCOMPLETE - Schema v5.0 is NOT properly deployed!';
        RAISE NOTICE '';
        IF NOT v_securities_exists THEN
            RAISE NOTICE '  ❌ securities table missing';
        END IF;
        IF v_has_symbol_in_facts THEN
            RAISE NOTICE '  ❌ symbol VARCHAR still exists in fact tables (denormalized!)';
        END IF;
        IF NOT v_has_fks THEN
            RAISE NOTICE '  ❌ FK constraints missing';
        END IF;
        IF NOT v_helpers_exist THEN
            RAISE NOTICE '  ❌ Helper functions missing';
        END IF;
        RAISE NOTICE '';
        RAISE NOTICE '  🛑 DO NOT proceed with service updates!';
        RAISE NOTICE '  📋 Deploy normalized schema v5.0 first!';
    END IF;
END $$;