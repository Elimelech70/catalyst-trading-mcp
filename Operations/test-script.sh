#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: test_catalyst.sh
# Version: 1.0.0
# Last Updated: 2025-10-16
# Purpose: Quick testing script for Catalyst Trading workflow

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================================================"
echo "           CATALYST TRADING SYSTEM - QUICK TEST v1.0.0"
echo "========================================================================"
echo "Testing all services and workflow components..."
echo ""

# Function to check service health
check_service() {
    local name=$1
    local port=$2
    local url="http://localhost:${port}/health"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 $url)
    
    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✅${NC} $name (port $port): RUNNING"
        return 0
    else
        echo -e "${RED}❌${NC} $name (port $port): NOT RESPONDING"
        return 1
    fi
}

# Function to test API endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local url=$3
    local data=$4
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" $url 2>/dev/null)
    else
        response=$(curl -s -X $method -H "Content-Type: application/json" \
                  -d "$data" -w "\n%{http_code}" $url 2>/dev/null)
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}PASSED${NC} (HTTP $http_code)"
        return 0
    else
        echo -e "${RED}FAILED${NC} (HTTP $http_code)"
        return 1
    fi
}

# ============================================================================
# STEP 1: SERVICE HEALTH CHECKS
# ============================================================================
echo "STEP 1: Service Health Checks"
echo "------------------------------"

services_up=0
total_services=8

check_service "Scanner Service" 5001 && ((services_up++))
check_service "Pattern Service" 5002 && ((services_up++))
check_service "Technical Service" 5003 && ((services_up++))
check_service "Risk Manager" 5004 && ((services_up++))
check_service "Trading Service" 5005 && ((services_up++))
check_service "News Service" 5008 && ((services_up++))
check_service "Reporting Service" 5009 && ((services_up++))
check_service "Redis Cache" 6379 && ((services_up++))

echo ""
echo "Services Running: $services_up/$total_services"

if [ $services_up -lt 6 ]; then
    echo -e "${RED}⚠️ WARNING: Not enough services running for complete test${NC}"
fi

echo ""

# ============================================================================
# STEP 2: DATABASE CONNECTIVITY
# ============================================================================
echo "STEP 2: Database Connectivity"
echo "------------------------------"

# Test database through one of the services
response=$(curl -s http://localhost:5001/health 2>/dev/null | grep -o '"database":"[^"]*"' | cut -d'"' -f4)

if [ "$response" = "connected" ]; then
    echo -e "${GREEN}✅${NC} Database: CONNECTED"
else
    echo -e "${RED}❌${NC} Database: DISCONNECTED"
fi

echo ""

# ============================================================================
# STEP 3: WORKFLOW TESTS
# ============================================================================
echo "STEP 3: Workflow Component Tests"
echo "---------------------------------"

# Test 1: News Ingestion
echo -e "\n${BLUE}Test 1: News Ingestion${NC}"
test_endpoint "News ingestion" "POST" \
    "http://localhost:5008/api/v1/news/ingest?symbol=AAPL&headline=Test%20news&summary=Test%20summary&source=test"

# Test 2: Market Scan
echo -e "\n${BLUE}Test 2: Market Scan${NC}"
echo "Triggering market scan (this may take 10-30 seconds)..."
scan_response=$(curl -s -X POST http://localhost:5001/api/v1/scan 2>/dev/null)
scan_success=$(echo $scan_response | grep -o '"success":true')

if [ ! -z "$scan_success" ]; then
    candidates=$(echo $scan_response | grep -o '"candidates":[0-9]*' | cut -d':' -f2)
    echo -e "${GREEN}✅${NC} Scan completed: $candidates candidates found"
else
    echo -e "${RED}❌${NC} Scan failed"
fi

# Test 3: Get Candidates
echo -e "\n${BLUE}Test 3: Retrieve Candidates${NC}"
candidates_response=$(curl -s "http://localhost:5001/api/v1/candidates?limit=5" 2>/dev/null)
count=$(echo $candidates_response | grep -o '"count":[0-9]*' | cut -d':' -f2)

if [ ! -z "$count" ] && [ "$count" -gt "0" ]; then
    echo -e "${GREEN}✅${NC} Retrieved $count candidates"
    
    # Extract first symbol for pattern test
    first_symbol=$(echo $candidates_response | grep -o '"symbol":"[^"]*"' | head -1 | cut -d'"' -f4)
else
    echo -e "${YELLOW}⚠️${NC} No candidates available"
    first_symbol="AAPL"  # Default symbol
fi

# Test 4: Pattern Detection
echo -e "\n${BLUE}Test 4: Pattern Detection${NC}"
pattern_data='{"symbol":"'$first_symbol'","timeframe":"5m","lookback_bars":50,"min_confidence":0.3}'
pattern_response=$(curl -s -X POST -H "Content-Type: application/json" \
    -d "$pattern_data" http://localhost:5002/api/v1/detect 2>/dev/null)
patterns_found=$(echo $pattern_response | grep -o '"patterns_found":[0-9]*' | cut -d':' -f2)

if [ ! -z "$patterns_found" ]; then
    echo -e "${GREEN}✅${NC} Pattern detection: $patterns_found patterns found for $first_symbol"
else
    echo -e "${YELLOW}⚠️${NC} Pattern detection failed or no patterns"
fi

# Test 5: Risk Validation
echo -e "\n${BLUE}Test 5: Risk Validation${NC}"
risk_data='{
    "cycle_id": 1,
    "symbol": "'$first_symbol'",
    "side": "long",
    "quantity": 100,
    "entry_price": 175.50,
    "stop_price": 172.00,
    "target_price": 180.00
}'
test_endpoint "Risk validation" "POST" \
    "http://localhost:5004/api/v1/validate-position" "$risk_data"

# Test 6: Get Processing Stats
echo -e "\n${BLUE}Test 6: News Processing Stats${NC}"
stats_response=$(curl -s http://localhost:5008/api/v1/stats 2>/dev/null)
backlog=$(echo $stats_response | grep -o '"current_backlog":[0-9]*' | cut -d':' -f2)

if [ ! -z "$backlog" ]; then
    echo -e "${GREEN}✅${NC} News processing backlog: $backlog events"
else
    echo -e "${YELLOW}⚠️${NC} Could not get processing stats"
fi

echo ""
echo "========================================================================"
echo "                         TEST SUMMARY"
echo "========================================================================"

# Check if core services are running
if [ $services_up -ge 6 ]; then
    echo -e "${GREEN}✅ Core services operational${NC}"
    echo -e "${GREEN}✅ Catalyst Trading System is ready for use${NC}"
else
    echo -e "${RED}❌ Some services are not running${NC}"
    echo -e "${YELLOW}Run 'docker-compose ps' to check service status${NC}"
fi

echo ""
echo "For detailed testing, run: python3 test_catalyst_workflow.py"
echo "========================================================================"
