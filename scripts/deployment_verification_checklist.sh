#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: verify_deployment.sh
# Version: 1.0.0
# Last Updated: 2025-10-04
# Purpose: Verify what's ACTUALLY deployed vs what's claimed to be implemented

echo "🎩 CATALYST TRADING MCP - DEPLOYMENT VERIFICATION"
echo "=================================================="
echo ""
echo "This script verifies what's ACTUALLY running vs what exists in code/docs"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check functions
check_passed() { echo -e "${GREEN}✅ PASS${NC}: $1"; }
check_failed() { echo -e "${RED}❌ FAIL${NC}: $1"; }
check_warn() { echo -e "${YELLOW}⚠️  WARN${NC}: $1"; }

echo "📋 SECTION 1: DOCKER CONTAINERS STATUS"
echo "========================================"
echo ""

echo "1.1 What containers are running?"
docker ps --filter "name=catalyst" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || check_failed "Docker not accessible"
echo ""

echo "1.2 Expected containers check:"
for container in orchestration scanner pattern technical trading news reporting risk-manager; do
    if docker ps | grep -q "catalyst-$container"; then
        check_passed "$container container is running"
    else
        check_failed "$container container NOT running"
    fi
done
echo ""

echo "📡 SECTION 2: SERVICE HEALTH ENDPOINTS"
echo "======================================="
echo ""

declare -A service_ports=(
    ["orchestration"]=5000
    ["scanner"]=5001
    ["pattern"]=5002
    ["technical"]=5003
    ["risk-manager"]=5004
    ["trading"]=5005
    ["news"]=5008
    ["reporting"]=5009
)

for service in "${!service_ports[@]}"; do
    port=${service_ports[$service]}
    if response=$(curl -s -m 5 "http://localhost:$port/health" 2>/dev/null); then
        if echo "$response" | grep -q "healthy"; then
            check_passed "$service (port $port) responding healthy"
        else
            check_warn "$service (port $port) responding but not healthy: $response"
        fi
    else
        check_failed "$service (port $port) not responding"
    fi
done
echo ""

echo "🗄️  SECTION 3: DATABASE VERIFICATION"
echo "====================================="
echo ""

if [ -z "$DATABASE_URL" ]; then
    check_failed "DATABASE_URL not set in environment"
    echo "  Run: export \$(grep -v '^#' .env | xargs)"
else
    check_passed "DATABASE_URL is set"
    
    # Check if DigitalOcean
    if echo "$DATABASE_URL" | grep -q "ondigitalocean.com"; then
        check_passed "Using DigitalOcean managed PostgreSQL"
    else
        check_warn "Not using DigitalOcean database"
    fi
    
    echo ""
    echo "3.1 Checking database tables existence:"
    
    # Test database connection and check tables
    if command -v psql >/dev/null 2>&1; then
        # Check critical tables
        for table in trading_cycles scan_results positions news_articles risk_parameters daily_risk_metrics; do
            if psql "$DATABASE_URL" -tAc "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='$table');" 2>/dev/null | grep -q "t"; then
                check_passed "Table '$table' exists"
            else
                check_failed "Table '$table' does NOT exist"
            fi
        done
    else
        check_warn "psql not installed - cannot verify database tables"
        echo "  Install with: sudo apt-get install postgresql-client"
    fi
fi
echo ""

echo "🔧 SECTION 4: GITHUB REPOSITORY STATUS"
echo "======================================="
echo ""

if [ -d ".git" ]; then
    echo "4.1 Latest commits:"
    git log --oneline -5 || check_warn "Cannot read git log"
    echo ""
    
    echo "4.2 Current branch:"
    current_branch=$(git branch --show-current)
    check_passed "On branch: $current_branch"
    echo ""
    
    echo "4.3 Uncommitted changes:"
    if git diff --quiet && git diff --cached --quiet; then
        check_passed "No uncommitted changes"
    else
        check_warn "There are uncommitted changes:"
        git status --short
    fi
    echo ""
    
    echo "4.4 Service files last modified:"
    for service in orchestration scanner pattern technical trading news reporting; do
        if [ -f "services/$service/$service-service.py" ]; then
            last_commit=$(git log -1 --format="%h %ci" -- "services/$service/$service-service.py" 2>/dev/null)
            if [ -n "$last_commit" ]; then
                echo "  $service: $last_commit"
            else
                check_warn "$service-service.py never committed"
            fi
        else
            check_failed "$service-service.py file NOT found"
        fi
    done
else
    check_failed "Not in a git repository"
fi
echo ""

echo "🔍 SECTION 5: FEATURE IMPLEMENTATION VERIFICATION"
echo "=================================================="
echo ""

echo "5.1 Connection Pool Optimization:"
if grep -r "min_size.*max_size" services/*/optimized_database.py 2>/dev/null | grep -q "min_size=.*max_size="; then
    check_passed "OptimizedDatabaseManager exists with connection limits"
else
    check_failed "OptimizedDatabaseManager NOT found"
fi

echo "5.2 News Service Multi-Source:"
news_sources=$(grep -c "alphavantage\|finnhub\|newsapi" services/news/news-service.py 2>/dev/null || echo 0)
if [ "$news_sources" -gt 1 ]; then
    check_passed "News service has multiple sources ($news_sources)"
else
    check_warn "News service only has $news_sources source(s)"
fi

echo "5.3 Volume Profile Indicators:"
if grep -q "calculate_volume_profile\|vpoc\|vah\|val" services/technical/technical-service.py 2>/dev/null; then
    check_passed "Volume profile indicators implemented"
else
    check_failed "Volume profile indicators NOT found"
fi

echo "5.4 Economic Indicators (FRED):"
if grep -q "FRED\|fred\|Federal Reserve" services/*/

*.py 2>/dev/null; then
    check_passed "FRED economic indicators integration found"
else
    check_failed "FRED economic indicators NOT implemented"
fi

echo "5.5 Enhanced Risk Schema v4.2:"
if psql "$DATABASE_URL" -tAc "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='risk_parameters');" 2>/dev/null | grep -q "t"; then
    check_passed "Enhanced risk tables (v4.2) deployed"
else
    check_failed "Enhanced risk tables (v4.2) NOT deployed"
fi

echo "5.6 Lazy Error Handling Fixes:"
bad_catches=$(grep -r "except Exception" services/ --include="*.py" 2>/dev/null | wc -l)
if [ "$bad_catches" -gt 20 ]; then
    check_failed "Found $bad_catches broad 'except Exception' catches (lazy error handling)"
else
    check_passed "Error handling looks improved (only $bad_catches broad catches)"
fi
echo ""

echo "📊 SECTION 6: DEPLOYMENT LOG ANALYSIS"
echo "======================================"
echo ""

echo "6.1 Container startup times:"
for container in catalyst-orchestration catalyst-scanner catalyst-trading catalyst-news; do
    if docker ps | grep -q "$container"; then
        started=$(docker inspect "$container" --format='{{.State.StartedAt}}' 2>/dev/null)
        echo "  $container: $started"
    fi
done
echo ""

echo "6.2 Recent container restarts:"
for container in $(docker ps --filter "name=catalyst" --format "{{.Names}}"); do
    restarts=$(docker inspect "$container" --format='{{.RestartCount}}' 2>/dev/null)
    if [ "$restarts" -gt 0 ]; then
        check_warn "$container has restarted $restarts times"
    else
        check_passed "$container has not restarted"
    fi
done
echo ""

echo "6.3 Service error logs (last 50 lines):"
for service in orchestration scanner trading news; do
    echo "  === $service errors ==="
    docker logs "catalyst-$service" 2>&1 | tail -50 | grep -i "error\|exception\|failed" | head -3 || echo "  No recent errors"
    echo ""
done

echo "🎯 SECTION 7: FINAL VERIFICATION SUMMARY"
echo "========================================"
echo ""

# Count checks
total_containers=$(docker ps --filter "name=catalyst" | wc -l)
total_containers=$((total_containers - 1))  # Remove header line

healthy_services=0
for port in 5000 5001 5002 5003 5004 5005 5008 5009; do
    if curl -s -m 2 "http://localhost:$port/health" 2>/dev/null | grep -q "healthy"; then
        healthy_services=$((healthy_services + 1))
    fi
done

echo "📈 System Status:"
echo "  - Running Containers: $total_containers"
echo "  - Healthy Services: $healthy_services/8"
echo "  - Database Connection: $([ -n "$DATABASE_URL" ] && echo "Configured" || echo "NOT configured")"
echo "  - Git Repository: $([ -d ".git" ] && echo "Present" || echo "NOT found")"
echo ""

if [ "$healthy_services" -eq 8 ] && [ "$total_containers" -ge 7 ]; then
    echo -e "${GREEN}✅ SYSTEM APPEARS FULLY DEPLOYED AND HEALTHY${NC}"
    echo ""
    echo "🚀 Ready for:"
    echo "  - Claude Desktop connection"
    echo "  - Live trading (paper mode)"
    echo "  - Production deployment"
elif [ "$healthy_services" -gt 4 ]; then
    echo -e "${YELLOW}⚠️  SYSTEM PARTIALLY DEPLOYED${NC}"
    echo ""
    echo "🔧 Next steps:"
    echo "  1. Check failed services above"
    echo "  2. Review container logs: docker-compose logs <service>"
    echo "  3. Restart failed services: docker-compose restart <service>"
else
    echo -e "${RED}❌ SYSTEM NOT PROPERLY DEPLOYED${NC}"
    echo ""
    echo "💥 Critical issues detected:"
    echo "  1. Most services not running or unhealthy"
    echo "  2. Review deployment logs"
    echo "  3. Consider full redeploy: docker-compose down && docker-compose up -d"
fi

echo ""
echo "📝 VERIFICATION COMPLETE"
echo "========================"
echo "Generated: $(date)"
echo ""
echo "💡 To fix issues, review the specific section failures above"
echo "🎩 Catalyst Trading MCP Deployment Verification v1.0.0"