#!/bin/bash
# ============================================================================
# Name of Application: Catalyst Trading System
# Name of file: test-news-storage-after-fix.sh
# Version: 1.0.0
# Last Updated: 2025-10-13
# Purpose: Test news storage after URL length fix
#
# REVISION HISTORY:
# v1.0.0 (2025-10-13) - Initial test script
#   - Restart news service
#   - Fetch news for test symbols
#   - Show storage diagnostics
#   - Compare success rates
#
# Description:
# This script verifies that the URL length fix resolved the storage issues.
# Expected outcome: Storage success rate should improve from ~40% to 95%+
# ============================================================================

echo "========================================="
echo "CATALYST TRADING SYSTEM"
echo "News Storage Test (Post-Fix)"
echo "========================================="
echo ""

# ============================================================================
# STEP 1: Get baseline - current articles in database
# ============================================================================
echo "STEP 1: Current database state"
echo "-------------------------------"

echo "Querying current article count..."
BEFORE_COUNT=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM news_sentiment;")
echo "Current articles in news_sentiment: $BEFORE_COUNT"
echo ""

# ============================================================================
# STEP 2: Restart news service (clear cached errors)
# ============================================================================
echo "STEP 2: Restarting news service"
echo "--------------------------------"

echo "Finding news service container..."
NEWS_CONTAINER=$(docker ps --filter "name=news" --format "{{.Names}}" | head -1)

if [ -z "$NEWS_CONTAINER" ]; then
    echo "❌ News service container not found!"
    echo "   Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    echo ""
    echo "Action Required:"
    echo "  1. Check if news service is running"
    echo "  2. Start news service if needed"
    exit 1
fi

echo "Found container: $NEWS_CONTAINER"
echo "Restarting..."
docker restart $NEWS_CONTAINER
echo "✅ News service restarted"
echo ""
echo "Waiting 10 seconds for service to initialize..."
sleep 10
echo ""

# ============================================================================
# STEP 3: Check service health
# ============================================================================
echo "STEP 3: Verifying service health"
echo "---------------------------------"

# Find the port (usually 5008)
NEWS_PORT=$(docker port $NEWS_CONTAINER 2>/dev/null | grep "5008" | cut -d: -f2 | head -1)

if [ -z "$NEWS_PORT" ]; then
    NEWS_PORT="5008"  # Default
fi

echo "Testing health endpoint at localhost:$NEWS_PORT..."
HEALTH_RESPONSE=$(curl -s http://localhost:$NEWS_PORT/health 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ Service responding"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo "⚠️  Service not responding on port $NEWS_PORT"
    echo "   Checking service logs..."
    docker logs --tail 20 $NEWS_CONTAINER
fi
echo ""

# ============================================================================
# STEP 4: Fetch news for test symbols
# ============================================================================
echo "STEP 4: Testing news fetching"
echo "------------------------------"

TEST_SYMBOLS=("AAPL" "TSLA" "NVDA")

for SYMBOL in "${TEST_SYMBOLS[@]}"; do
    echo ""
    echo "Testing: $SYMBOL"
    echo "----------------"
    
    echo "Fetching catalysts (this may take 10-20 seconds)..."
    RESPONSE=$(curl -s "http://localhost:$NEWS_PORT/api/v1/catalysts/$SYMBOL?hours=24" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Parse response for count
        COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('count', 0))" 2>/dev/null)
        
        if [ ! -z "$COUNT" ]; then
            echo "✅ Response received: $COUNT catalysts found"
            
            # Check for storage diagnostics
            STORAGE_DIAG=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('storage_diagnostics', {}), indent=2))" 2>/dev/null)
            
            if [ "$STORAGE_DIAG" != "{}" ] && [ ! -z "$STORAGE_DIAG" ]; then
                echo ""
                echo "Storage Diagnostics:"
                echo "$STORAGE_DIAG"
            fi
        else
            echo "⚠️  Unexpected response format"
            echo "$RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
        fi
    else
        echo "❌ Request failed for $SYMBOL"
    fi
    
    sleep 2  # Brief delay between requests
done

echo ""
echo ""

# ============================================================================
# STEP 5: Check database for new articles
# ============================================================================
echo "STEP 5: Database verification"
echo "------------------------------"

echo "Querying updated article count..."
AFTER_COUNT=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM news_sentiment;")
echo "Articles after test: $AFTER_COUNT"

NEW_ARTICLES=$((AFTER_COUNT - BEFORE_COUNT))
echo "New articles stored: $NEW_ARTICLES"
echo ""

if [ $NEW_ARTICLES -gt 0 ]; then
    echo "✅ Articles are being stored successfully!"
    echo ""
    
    # Show sample of recent articles
    echo "Sample of recent articles:"
    echo "--------------------------"
    psql $DATABASE_URL -c "
        SELECT 
            s.symbol,
            ns.headline,
            LENGTH(ns.url) as url_length,
            ns.sentiment_label,
            td.timestamp
        FROM news_sentiment ns
        JOIN securities s ON s.security_id = ns.security_id
        JOIN time_dimension td ON td.time_id = ns.time_id
        ORDER BY td.timestamp DESC
        LIMIT 5;
    "
    echo ""
    
    # Check URL lengths
    echo "URL length statistics:"
    echo "----------------------"
    psql $DATABASE_URL -c "
        SELECT 
            COUNT(*) as total_articles,
            AVG(LENGTH(url))::INTEGER as avg_url_length,
            MAX(LENGTH(url)) as max_url_length,
            COUNT(*) FILTER (WHERE LENGTH(url) > 1000) as urls_over_1000
        FROM news_sentiment
        WHERE url IS NOT NULL;
    "
else
    echo "⚠️  No new articles stored during test"
    echo ""
    echo "Possible causes:"
    echo "  1. News service not finding articles for test symbols"
    echo "  2. All articles are duplicates (already stored)"
    echo "  3. Storage still failing (need more diagnostics)"
    echo ""
    echo "Checking recent service logs..."
    docker logs --tail 30 $NEWS_CONTAINER | grep -i "error\|fail\|stored"
fi

echo ""

# ============================================================================
# STEP 6: Check for storage errors in logs
# ============================================================================
echo "STEP 6: Checking for storage errors"
echo "------------------------------------"

echo "Searching service logs for storage-related errors..."
ERRORS=$(docker logs --tail 100 $NEWS_CONTAINER 2>&1 | grep -i "failed to store\|database error\|constraint violation" | wc -l)

if [ $ERRORS -eq 0 ]; then
    echo "✅ No storage errors found in recent logs"
else
    echo "⚠️  Found $ERRORS storage-related error messages"
    echo ""
    echo "Recent errors:"
    docker logs --tail 100 $NEWS_CONTAINER 2>&1 | grep -i "failed to store\|database error\|constraint violation" | tail -10
fi

echo ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo ""

if [ $NEW_ARTICLES -gt 0 ] && [ $ERRORS -eq 0 ]; then
    echo "✅ SUCCESS: News storage is working!"
    echo ""
    echo "Results:"
    echo "  • New articles stored: $NEW_ARTICLES"
    echo "  • Storage errors: $ERRORS"
    echo "  • URL fix: Working (TEXT column accepting long URLs)"
    echo ""
    echo "Next Steps:"
    echo "  1. Monitor storage success rate over next hour"
    echo "  2. Should see 95%+ success rate (vs ~40% before)"
    echo "  3. Check detailed logs if any failures persist"
elif [ $NEW_ARTICLES -gt 0 ] && [ $ERRORS -gt 0 ]; then
    echo "⚠️  PARTIAL SUCCESS: Articles storing but errors present"
    echo ""
    echo "Results:"
    echo "  • New articles stored: $NEW_ARTICLES"
    echo "  • Storage errors: $ERRORS"
    echo ""
    echo "Next Steps:"
    echo "  1. Review error messages above"
    echo "  2. May need additional diagnostics"
    echo "  3. Run: docker logs $NEWS_CONTAINER | tail -50"
elif [ $NEW_ARTICLES -eq 0 ]; then
    echo "⚠️  NO NEW ARTICLES: Need investigation"
    echo ""
    echo "Possible issues:"
    echo "  • Service not fetching articles (API issues)"
    echo "  • All articles are duplicates"
    echo "  • Storage still failing (different constraint)"
    echo ""
    echo "Next Steps:"
    echo "  1. Review service logs: docker logs $NEWS_CONTAINER"
    echo "  2. Test API directly: curl localhost:$NEWS_PORT/api/v1/catalysts/AAPL"
    echo "  3. May need additional diagnostic script"
fi

echo ""
echo "========================================="
echo "END OF TEST"
echo "========================================="