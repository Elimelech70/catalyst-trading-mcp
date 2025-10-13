#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: validate-deployment.sh
# Version: 5.1.0
# Last Updated: 2025-10-13
# Purpose: Automated deployment validation and health checks

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

echo "=========================================="
echo "Catalyst Trading System - Deployment Validation"
echo "Version: 5.1.0"
echo "=========================================="
echo ""

# Function to check service health
check_service() {
    local service=$1
    local port=$2
    local expected_version=$3
    
    echo -n "Checking $service (port $port)... "
    
    response=$(curl -s --max-time 5 http://localhost:$port/health 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}FAIL${NC} - Service not responding"
        ((FAIL++))
        return 1
    fi
    
    status=$(echo $response | jq -r '.status // "unknown"')
    version=$(echo $response | jq -r '.version // "unknown"')
    
    if [ "$status" = "healthy" ]; then
        if [ "$version" = "$expected_version" ]; then
            echo -e "${GREEN}PASS${NC} - v$version"
            ((PASS++))
        else
            echo -e "${YELLOW}WARN${NC} - v$version (expected v$expected_version)"
            ((WARN++))
        fi
        return 0
    else
        echo -e "${RED}FAIL${NC} - Status: $status"
        ((FAIL++))
        return 1
    fi
}

# Function to check database
check_database() {
    echo -n "Checking PostgreSQL... "
    
    result=$(docker exec catalyst-postgres psql -U catalyst -d catalyst_trading -c "SELECT 1;" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}PASS${NC} - Database accessible"
        ((PASS++))
        
        # Check key tables exist
        echo -n "  - Checking schema v5.0 tables... "
        tables=$(docker exec catalyst-postgres psql -U catalyst -d catalyst_trading -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('securities', 'trading_history', 'news_sentiment', 'technical_indicators', 'pattern_analysis', 'positions', 'time_dimension');" 2>/dev/null | tr -d ' ')
        
        if [ "$tables" = "7" ]; then
            echo -e "${GREEN}PASS${NC} - All 7 core tables present"
            ((PASS++))
        else
            echo -e "${RED}FAIL${NC} - Expected 7 tables, found $tables"
            ((FAIL++))
        fi
    else
        echo -e "${RED}FAIL${NC} - Database not accessible"
        ((FAIL++))
    fi
}

# Function to check containers
check_containers() {
    echo ""
    echo "Checking Docker containers..."
    
    services=("catalyst-postgres" "catalyst-scanner" "catalyst-pattern" "catalyst-technical" "catalyst-risk-manager" "catalyst-trading" "catalyst-news" "catalyst-reporting")
    
    for service in "${services[@]}"; do
        echo -n "  - $service... "
        status=$(docker inspect -f '{{.State.Status}}' $service 2>/dev/null)
        
        if [ "$status" = "running" ]; then
            echo -e "${GREEN}RUNNING${NC}"
            ((PASS++))
        elif [ "$status" = "restarting" ]; then
            echo -e "${YELLOW}RESTARTING${NC}"
            ((WARN++))
        else
            echo -e "${RED}NOT RUNNING${NC} (status: $status)"
            ((FAIL++))
        fi
    done
}

# Function to check disk space
check_disk_space() {
    echo ""
    echo -n "Checking disk space... "
    
    disk_usage=$(docker system df --format "{{.Type}}\t{{.Size}}" 2>/dev/null | grep Images | awk '{print $2}')
    
    if [ ! -z "$disk_usage" ]; then
        echo -e "${GREEN}OK${NC} - Docker images: $disk_usage"
        ((PASS++))
    else
        echo -e "${YELLOW}WARN${NC} - Could not check disk usage"
        ((WARN++))
    fi
}

# Function to test API endpoints
test_endpoints() {
    echo ""
    echo "Testing API endpoints..."
    
    # Test scanner
    echo -n "  - Scanner scan endpoint... "
    response=$(curl -s -X POST http://localhost:5001/api/v1/scan \
        -H "Content-Type: application/json" \
        -d '{"hours_back": 1}' \
        --max-time 10 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASS++))
    else
        echo -e "${RED}FAIL${NC}"
        ((FAIL++))
    fi
    
    # Test news
    echo -n "  - News fetch endpoint... "
    response=$(curl -s -X POST http://localhost:5008/api/v1/news/fetch \
        -H "Content-Type: application/json" \
        -d '{"symbol": "AAPL", "hours_back": 1}' \
        --max-time 10 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASS++))
    else
        echo -e "${RED}FAIL${NC}"
        ((FAIL++))
    fi
}

# Function to check logs for errors
check_logs() {
    echo ""
    echo "Checking logs for critical errors..."
    
    services=("scanner" "news" "technical" "pattern" "risk-manager" "trading" "reporting")
    
    for service in "${services[@]}"; do
        echo -n "  - $service logs... "
        errors=$(docker-compose logs --tail=100 $service 2>/dev/null | grep -i "CRITICAL\|FATAL" | wc -l)
        
        if [ "$errors" -eq 0 ]; then
            echo -e "${GREEN}OK${NC} - No critical errors"
            ((PASS++))
        else
            echo -e "${RED}WARN${NC} - $errors critical errors found"
            ((WARN++))
        fi
    done
}

# Function to check environment variables
check_environment() {
    echo ""
    echo "Checking environment configuration..."
    
    echo -n "  - .env file exists... "
    if [ -f .env ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASS++))
        
        # Check for API keys
        echo -n "  - API keys configured... "
        if grep -q "ALPACA_API_KEY=your_" .env 2>/dev/null; then
            echo -e "${YELLOW}WARN${NC} - Using placeholder API keys"
            ((WARN++))
        else
            echo -e "${GREEN}PASS${NC}"
            ((PASS++))
        fi
    else
        echo -e "${RED}FAIL${NC} - .env file not found"
        ((FAIL++))
    fi
}

# Main execution
echo "=== PHASE 1: Container Status ==="
check_containers

echo ""
echo "=== PHASE 2: Database Check ==="
check_database

echo ""
echo "=== PHASE 3: Service Health Checks ==="
check_service "Scanner" 5001 "5.4.0"
check_service "Pattern" 5002 "5.1.0"
check_service "Technical" 5003 "5.1.0"
check_service "Risk Manager" 5004 "5.0.0"
check_service "Trading" 5005 "5.0.1"
check_service "News" 5008 "5.3.1"
check_service "Reporting" 5009 "5.1.0"

echo ""
echo "=== PHASE 4: System Resources ==="
check_disk_space

echo ""
echo "=== PHASE 5: API Endpoint Tests ==="
test_endpoints

echo ""
echo "=== PHASE 6: Log Analysis ==="
check_logs

echo ""
echo "=== PHASE 7: Environment Check ==="
check_environment

# Summary
echo ""
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo -e "${GREEN}PASSED:${NC} $PASS"
echo -e "${YELLOW}WARNINGS:${NC} $WARN"
echo -e "${RED}FAILED:${NC} $FAIL"
echo "=========================================="

# Overall result
echo ""
if [ $FAIL -eq 0 ]; then
    if [ $WARN -eq 0 ]; then
        echo -e "${GREEN}✓ DEPLOYMENT FULLY VALIDATED${NC}"
        echo "All systems operational!"
        exit 0
    else
        echo -e "${YELLOW}⚠ DEPLOYMENT VALIDATED WITH WARNINGS${NC}"
        echo "System is operational but check warnings above."
        exit 0
    fi
else
    echo -e "${RED}✗ DEPLOYMENT VALIDATION FAILED${NC}"
    echo "Please address the failures above before proceeding."
    echo ""
    echo "Quick troubleshooting:"
    echo "  - Check logs: docker-compose logs -f"
    echo "  - Restart services: docker-compose restart"
    echo "  - Rebuild: docker-compose build && docker-compose up -d"
    exit 1
fi
