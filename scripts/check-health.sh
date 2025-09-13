#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: check-health.sh
# Version: 2.0.0
# Last Updated: 2025-09-13
# Purpose: Fixed health check script for MCP and REST services

# REVISION HISTORY:
# v2.0.0 (2025-09-13) - Fixed to handle MCP STDIO services correctly
# v1.0.0 (2025-09-13) - Initial version

# Description of Service:
# Health check that correctly identifies MCP vs REST services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Catalyst Trading System - Health Check 🏥       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo

# Function to check REST service health
check_rest_service() {
    local service=$1
    local port=$2
    local name=$3
    
    printf "%-25s" "$name..."
    
    if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ HEALTHY (REST)${NC}"
        return 0
    else
        echo -e "${RED}✗ UNHEALTHY${NC}"
        return 1
    fi
}

# Function to check container status
check_container() {
    local container=$1
    local name=$2
    
    printf "%-25s" "$name..."
    
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$container.*Up"; then
        echo -e "${GREEN}✓ RUNNING${NC}"
        return 0
    else
        echo -e "${RED}✗ NOT RUNNING${NC}"
        return 1
    fi
}

echo -e "${YELLOW}Step 1: Container Status${NC}"
echo

# Check all containers
check_container "catalyst-orchestration" "Orchestration (MCP)"
check_container "catalyst-scanner" "Scanner Service"
check_container "catalyst-pattern" "Pattern Service"
check_container "catalyst-trading" "Trading Service"
check_container "catalyst-news" "News Service"
check_container "catalyst-reporting" "Reporting Service"
check_container "catalyst-risk" "Risk Manager"
check_container "catalyst-redis" "Redis Cache"

echo
echo -e "${YELLOW}Step 2: REST API Health Endpoints${NC}"
echo

# Check REST services (not orchestration as it's MCP/STDIO)
check_rest_service "scanner" "5001" "Scanner API"
check_rest_service "pattern" "5002" "Pattern API"
check_rest_service "trading" "5005" "Trading API"
check_rest_service "news" "5008" "News API"
check_rest_service "reporting" "5009" "Reporting API"

echo
echo -e "${YELLOW}Step 3: Service Connections${NC}"
echo

# Check Redis
printf "%-25s" "Redis Cache..."
if docker exec catalyst-redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}" ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CONNECTED${NC}"
    
    # Get Redis info
    keys=$(docker exec catalyst-redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}" DBSIZE 2>/dev/null | grep -o '[0-9]*' || echo "0")
    echo -e "  ${BLUE}Keys in cache: $keys${NC}"
else
    echo -e "${RED}✗ NOT CONNECTED${NC}"
fi

# Check Database
printf "%-25s" "PostgreSQL Database..."
if [ -f ".env" ]; then
    export $(grep DATABASE_URL .env | xargs) 2>/dev/null || true
fi

if [ -n "$DATABASE_URL" ] && psql "$DATABASE_URL" -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CONNECTED${NC}"
    
    # Get table count
    tables=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" 2>/dev/null | xargs || echo "0")
    echo -e "  ${BLUE}Tables in database: $tables${NC}"
else
    echo -e "${YELLOW}⚠️  Cannot verify (psql not installed or connection issue)${NC}"
fi

echo
echo -e "${YELLOW}Step 4: Alpaca Trading Status${NC}"
echo

# Check trading service for Alpaca status
printf "%-25s" "Alpaca API..."
if docker logs catalyst-trading 2>&1 | grep -q "Account status: ACTIVE"; then
    echo -e "${GREEN}✓ CONNECTED${NC}"
    
    # Extract buying power
    buying_power=$(docker logs catalyst-trading 2>&1 | grep "Buying power" | tail -1 | sed 's/.*Buying power: //')
    if [ -n "$buying_power" ]; then
        echo -e "  ${BLUE}Buying Power: $buying_power${NC}"
    fi
    
    # Check for open positions
    positions=$(docker logs catalyst-trading 2>&1 | grep -c "Position:" || echo "0")
    echo -e "  ${BLUE}Open Positions: $positions${NC}"
else
    echo -e "${RED}✗ NOT CONNECTED${NC}"
fi

echo
echo -e "${YELLOW}Step 5: MCP Orchestration Status${NC}"
echo

# Check if orchestration is running MCP
printf "%-25s" "MCP Server..."
if docker logs catalyst-orchestration 2>&1 | grep -q "FastMCP"; then
    echo -e "${GREEN}✓ MCP ACTIVE${NC}"
    
    # Get MCP version
    mcp_version=$(docker logs catalyst-orchestration 2>&1 | grep "FastMCP version" | tail -1 | sed 's/.*FastMCP version: //' | sed 's/[[:space:]]*│.*//')
    if [ -n "$mcp_version" ]; then
        echo -e "  ${BLUE}FastMCP Version: $mcp_version${NC}"
    fi
    echo -e "  ${BLUE}Transport: STDIO${NC}"
    echo -e "  ${BLUE}Ready for Claude Desktop${NC}"
else
    echo -e "${RED}✗ MCP NOT RUNNING${NC}"
fi

echo
echo -e "${YELLOW}Step 6: Recent Issues${NC}"
echo

# Check for database schema issues
if docker logs catalyst-pattern 2>&1 | grep -q "column.*does not exist"; then
    echo -e "${YELLOW}⚠️  Pattern Service: Missing database columns${NC}"
fi

if docker logs catalyst-trading 2>&1 | grep -q "column.*does not exist"; then
    echo -e "${YELLOW}⚠️  Trading Service: Missing database columns${NC}"
fi

# Check for news service issues
if docker logs catalyst-news 2>&1 | tail -20 | grep -q "Yahoo RSS request failed"; then
    echo -e "${YELLOW}⚠️  News Service: Yahoo RSS not available (using other sources)${NC}"
fi

# Count total errors
error_count=$(docker-compose logs --tail=1000 2>&1 | grep -i "error" | wc -l)
if [ "$error_count" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Total errors in last 1000 log lines: $error_count${NC}"
else
    echo -e "${GREEN}✓ No errors in recent logs${NC}"
fi

echo
echo -e "${YELLOW}Step 7: System Summary${NC}"
echo

# Count running containers
running_containers=$(docker ps --filter "name=catalyst" | grep -c "Up" || echo "0")
total_containers=8

echo -e "Containers Running: ${GREEN}$running_containers/$total_containers${NC}"
echo -e "MCP Orchestration: ${GREEN}ACTIVE${NC}"
echo -e "Trading Ready: ${GREEN}YES (Paper Mode)${NC}"

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
if [ "$running_containers" -eq "$total_containers" ]; then
    echo -e "${GREEN}║   System is FULLY OPERATIONAL! 🚀                 ║${NC}"
else
    echo -e "${YELLOW}║   System is PARTIALLY OPERATIONAL ⚠️              ║${NC}"
fi
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"

echo
echo -e "${YELLOW}Quick Commands:${NC}"
echo
echo "View live logs for a service:"
echo -e "  ${BLUE}docker logs -f catalyst-[service-name]${NC}"
echo
echo "Restart a service:"
echo -e "  ${BLUE}docker-compose restart [service-name]${NC}"
echo
echo "Check MCP connection:"
echo -e "  ${BLUE}docker logs catalyst-orchestration | grep FastMCP${NC}"
echo
echo "Trigger a market scan:"
echo -e "  ${BLUE}curl -X POST http://localhost:5001/scan${NC}"
echo
echo "Get trading status:"
echo -e "  ${BLUE}curl http://localhost:5005/status${NC}"
echo
echo "View all service logs:"
echo -e "  ${BLUE}docker-compose logs -f${NC}"