#!/bin/bash
# ============================================================================
# Name of Application: Catalyst Trading System
# Name of file: diagnose-news-storage-failures.sh
# Version: 1.0.0
# Last Updated: 2025-10-13
# Purpose: Deep diagnostic of why news articles aren't being stored
#
# REVISION HISTORY:
# v1.0.0 (2025-10-13) - Initial diagnostic script
#   - Analyze service logs for specific error patterns
#   - Test API endpoints directly
#   - Show detailed error messages
#   - Identify root cause of storage failures
#
# Description:
# This script investigates why articles aren't being stored after URL fix.
# It looks for: API errors, constraint violations, duplicate handling,
# foreign key issues, and service configuration problems.
# ============================================================================

echo "========================================="
echo "CATALYST TRADING SYSTEM"
echo "News Storage Failure Diagnostics"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# ============================================================================
# STEP 1: Find and verify news service
# ============================================================================
echo "STEP 1: Locating news service"
echo "------------------------------"

NEWS_CONTAINER=$(docker ps --filter "name=news" --format "{{.Names}}" | head -1)

if [ -z "$NEWS_CONTAINER" ]; then
    echo -e "${RED}❌ News service container not found!${NC}"
    echo ""
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    exit 1
fi

echo -e "${GREEN}✅ Found container: $NEWS_CONTAINER${NC}"
echo ""

# Get port
NEWS_PORT=$(docker port $NEWS_CONTAINER 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1)
if [ -z "$NEWS_PORT" ]; then
    NEWS_PORT="5008"
fi
echo "Service port: $NEWS_PORT"
echo ""

# ============================================================================
# STEP 2: Check service logs for errors
# ============================================================================
echo "STEP 2: Analyzing service logs"
echo "-------------------------------"

echo "Last 50 lines of service logs:"
echo "================================"
docker logs --tail 50 $NEWS_CONTAINER 2>&1
echo "================================"
echo ""

# Count specific error types
echo "Error Pattern Analysis:"
echo "-----------------------"

API_ERRORS=$(docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "newsapi\|api error\|api key" | wc -l)
DB_ERRORS=$(docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "database error\|failed to store\|asyncpg" | wc -l)
CONSTRAINT_ERRORS=$(docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "constraint\|violation\|foreign key" | wc -l)
DUPLICATE_MESSAGES=$(docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "duplicate\|conflict" | wc -l)

echo "  • API errors: $API_ERRORS"
echo "  • Database errors: $DB_ERRORS"
echo "  • Constraint violations: $CONSTRAINT_ERRORS"
echo "  • Duplicate messages: $DUPLICATE_MESSAGES"
echo ""

# Show specific error messages if found
if [ $DB_ERRORS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Database errors found:${NC}"
    docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "failed to store\|database error" | tail -5
    echo ""
fi

if [ $CONSTRAINT_ERRORS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Constraint violations found:${NC}"
    docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "constraint\|violation" | tail -5
    echo ""
fi

if [ $API_ERRORS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  API errors found:${NC}"
    docker logs --tail 200 $NEWS_CONTAINER 2>&1 | grep -i "newsapi\|api error" | tail -5
    echo ""
fi

# ============================================================================
# STEP 3: Test API endpoint directly
# ============================================================================
echo "STEP 3: Testing API endpoint directly"
echo "--------------------------------------"

echo "Calling: GET /api/v1/catalysts/AAPL?hours=24"
echo ""

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:$NEWS_PORT/api/v1/catalysts/AAPL?hours=24")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

echo "HTTP Status: $HTTP_STATUS"
echo ""

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ API responded successfully${NC}"
    echo ""
    echo "Response body:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    echo ""
    
    # Parse key fields
    COUNT=$(echo "$BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('count', 'N/A'))" 2>/dev/null)
    echo "Catalysts found: $COUNT"
    
    # Check for storage diagnostics
    STORAGE_INFO=$(echo "$BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); sd=data.get('storage_diagnostics', {}); print(f\"Fetched: {sd.get('articles_fetched', 0)}, Stored: {sd.get('articles_stored', 0)}, Failed: {sd.get('articles_failed', 0)}\") if sd else print('No diagnostics')" 2>/dev/null)
    echo "Storage: $STORAGE_INFO"
    
    # Check for error details
    ERROR_DETAIL=$(echo "$BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); detail=data.get('detail', {}); print(detail.get('message', 'N/A')) if isinstance(detail, dict) else print('N/A')" 2>/dev/null)
    if [ "$ERROR_DETAIL" != "N/A" ] && [ ! -z "$ERROR_DETAIL" ]; then
        echo -e "${YELLOW}Error detail: $ERROR_DETAIL${NC}"
    fi
    
else
    echo -e "${RED}❌ API returned error status: $HTTP_STATUS${NC}"
    echo ""
    echo "Response:"
    echo "$BODY"
fi

echo ""

# ============================================================================
# STEP 4: Check database for recent activity
# ============================================================================
echo "STEP 4: Database activity check"
echo "--------------------------------"

echo "Recent articles (last 10):"
psql $DATABASE_URL -c "
    SELECT 
        ns.news_id,
        s.symbol,
        SUBSTRING(ns.headline, 1, 50) || '...' as headline,
        LENGTH(ns.url) as url_len,
        td.timestamp::timestamp(0) as published
    FROM news_sentiment ns
    JOIN securities s ON s.security_id = ns.security_id
    JOIN time_dimension td ON td.time_id = ns.time_id
    ORDER BY ns.news_id DESC
    LIMIT 10;
" 2>/dev/null

echo ""

# Check for AAPL specifically
AAPL_COUNT=$(psql $DATABASE_URL -t -c "
    SELECT COUNT(*) 
    FROM news_sentiment ns
    JOIN securities s ON s.security_id = ns.security_id
    WHERE s.symbol = 'AAPL' 
    AND ns.created_at > NOW() - INTERVAL '1 hour';
" 2>/dev/null | xargs)

echo "AAPL articles in last hour: $AAPL_COUNT"
echo ""

# ============================================================================
# STEP 5: Test individual article insertion
# ============================================================================
echo "STEP 5: Testing direct database insertion"
echo "------------------------------------------"

echo "Attempting to insert a test article directly..."

TEST_RESULT=$(psql $DATABASE_URL << 'EOSQL'
DO $$
DECLARE
    v_security_id INTEGER;
    v_time_id BIGINT;
    v_news_id BIGINT;
    v_test_url TEXT;
BEGIN
    -- Create test URL (long, to verify URL fix worked)
    v_test_url := 'https://www.test-diagnostic.com/very-long-path/' || 
                  REPEAT('x', 1200) || 
                  '?param=value';
    
    -- Get security and time IDs
    BEGIN
        v_security_id := get_or_create_security('AAPL');
        v_time_id := get_or_create_time(NOW());
        
        RAISE NOTICE 'Helper functions working: security_id=%, time_id=%', v_security_id, v_time_id;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE '❌ Helper function error: %', SQLERRM;
            RETURN;
    END;
    
    -- Try direct insertion
    BEGIN
        INSERT INTO news_sentiment (
            security_id,
            time_id,
            headline,
            url,
            source,
            sentiment_score,
            sentiment_label,
            catalyst_type,
            catalyst_strength
        ) VALUES (
            v_security_id,
            v_time_id,
            'DIAGNOSTIC TEST - ' || NOW()::TEXT,
            v_test_url,
            'diagnostic-test',
            0.5,
            'neutral',
            'earnings',
            'moderate'
        )
        RETURNING news_id INTO v_news_id;
        
        RAISE NOTICE '✅ Direct insertion successful: news_id=%', v_news_id;
        RAISE NOTICE '   URL length: % characters', LENGTH(v_test_url);
        
        -- Clean up
        DELETE FROM news_sentiment WHERE news_id = v_news_id;
        RAISE NOTICE '   Test article cleaned up';
        
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE '⚠️  Duplicate key violation (article may already exist)';
        WHEN foreign_key_violation THEN
            RAISE NOTICE '❌ Foreign key violation: %', SQLERRM;
        WHEN check_violation THEN
            RAISE NOTICE '❌ Check constraint violation: %', SQLERRM;
        WHEN OTHERS THEN
            RAISE NOTICE '❌ Insertion failed: %', SQLERRM;
            RAISE NOTICE '   Error detail: %', SQLSTATE;
    END;
END $$;
EOSQL
)

echo "$TEST_RESULT"
echo ""

# ============================================================================
# STEP 6: Check service environment variables
# ============================================================================
echo "STEP 6: Service configuration check"
echo "------------------------------------"

echo "Checking environment variables..."
docker exec $NEWS_CONTAINER env | grep -E "NEWS_API_KEY|DATABASE_URL" | sed 's/\(NEWS_API_KEY=\).*/\1[REDACTED]/' | sed 's/\(DATABASE_URL=.*:.*@\).*/\1[REDACTED]/'
echo ""

# Check if NEWS_API_KEY is set
NEWS_KEY_SET=$(docker exec $NEWS_CONTAINER env | grep "NEWS_API_KEY=" | wc -l)
DB_URL_SET=$(docker exec $NEWS_CONTAINER env | grep "DATABASE_URL=" | wc -l)

if [ $NEWS_KEY_SET -eq 0 ]; then
    echo -e "${RED}❌ NEWS_API_KEY not set in container!${NC}"
    echo "   This will cause all API requests to fail"
else
    echo -e "${GREEN}✅ NEWS_API_KEY is set${NC}"
fi

if [ $DB_URL_SET -eq 0 ]; then
    echo -e "${RED}❌ DATABASE_URL not set in container!${NC}"
    echo "   This will cause all database operations to fail"
else
    echo -e "${GREEN}✅ DATABASE_URL is set${NC}"
fi

echo ""

# ============================================================================
# FINAL DIAGNOSIS
# ============================================================================
echo "========================================="
echo "DIAGNOSTIC SUMMARY"
echo "========================================="
echo ""

# Analyze patterns and provide diagnosis
if [ $API_ERRORS -gt 5 ]; then
    echo -e "${RED}🔴 PRIMARY ISSUE: API Errors${NC}"
    echo ""
    echo "Root Cause:"
    echo "  • NewsAPI is returning errors (likely API key or rate limit)"
    echo ""
    echo "Evidence:"
    echo "  • $API_ERRORS API-related errors in logs"
    echo ""
    echo "Fix:"
    echo "  1. Verify NEWS_API_KEY is valid"
    echo "  2. Check NewsAPI rate limits (free tier: 100 req/day)"
    echo "  3. Test API key: curl 'https://newsapi.org/v2/everything?q=AAPL&apiKey=YOUR_KEY'"
    
elif [ $DB_ERRORS -gt 5 ]; then
    echo -e "${RED}🔴 PRIMARY ISSUE: Database Errors${NC}"
    echo ""
    echo "Root Cause:"
    echo "  • Articles are fetched but failing to store in database"
    echo ""
    echo "Evidence:"
    echo "  • $DB_ERRORS database-related errors in logs"
    echo ""
    echo "Review the specific error messages above and fix accordingly"
    
elif [ $DUPLICATE_MESSAGES -gt 10 ]; then
    echo -e "${YELLOW}🟡 PRIMARY ISSUE: All Articles Are Duplicates${NC}"
    echo ""
    echo "Root Cause:"
    echo "  • Articles are being fetched but already exist in database"
    echo "  • ON CONFLICT DO NOTHING is preventing re-insertion"
    echo ""
    echo "Evidence:"
    echo "  • $DUPLICATE_MESSAGES duplicate-related messages in logs"
    echo "  • AAPL articles in last hour: $AAPL_COUNT"
    echo ""
    echo "This is EXPECTED behavior - not an error!"
    echo "The system is working correctly and avoiding duplicate storage."
    
elif [ "$HTTP_STATUS" != "200" ]; then
    echo -e "${RED}🔴 PRIMARY ISSUE: API Endpoint Not Working${NC}"
    echo ""
    echo "Root Cause:"
    echo "  • News service API is not responding correctly"
    echo ""
    echo "Evidence:"
    echo "  • HTTP status: $HTTP_STATUS (expected: 200)"
    echo ""
    echo "Fix:"
    echo "  1. Check service logs above for startup errors"
    echo "  2. Verify service is fully initialized"
    echo "  3. Check port $NEWS_PORT is correct"
    
else
    echo -e "${GREEN}🟢 No obvious errors detected${NC}"
    echo ""
    echo "Possible scenarios:"
    echo "  1. ✅ System is working - all fetched articles are duplicates"
    echo "  2. ⚠️  NewsAPI returning no results for test symbols"
    echo "  3. ⚠️  Service working but fetching articles outside test window"
    echo ""
    echo "Evidence:"
    echo "  • API responding: $HTTP_STATUS"
    echo "  • Database errors: $DB_ERRORS"
    echo "  • API errors: $API_ERRORS"
    echo ""
    echo "Recommendation:"
    echo "  • Review the full service logs above"
    echo "  • Check if articles are being fetched but already exist"
    echo "  • Try a different symbol or longer time window"
fi

echo ""
echo "========================================="
echo "END OF DIAGNOSTICS"
echo "========================================="