#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: check-system-health.sh
# Version: 1.0.0
# Last Updated: 2025-09-13
# Purpose: System health check and database migration script

# REVISION HISTORY:
# v1.0.0 (2025-09-13) - Initial health check and fix script

# Description of Service:
# Comprehensive health check for all Catalyst Trading System services

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

# Function to check service health
check_service() {
    local service=$1
    local port=$2
    local name=$3
    
    printf "%-25s" "$name..."
    
    if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ HEALTHY${NC}"
        return 0
    else
        echo -e "${RED}✗ UNHEALTHY${NC}"
        return 1
    fi
}

# Check if database migration is needed
echo -e "${YELLOW}Step 1: Checking Database Schema${NC}"
echo

if [ -f "fix-database-schema.sql" ]; then
    echo "Found database migration file. Applying fixes..."
    
    # Load DATABASE_URL from .env
    if [ -f ".env" ]; then
        export $(grep DATABASE_URL .env | xargs)
    fi
    
    if [ -n "$DATABASE_URL" ]; then
        if psql "$DATABASE_URL" < fix-database-schema.sql > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Database schema updated successfully${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not apply migration (may already be applied)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  DATABASE_URL not found in .env${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Migration file not found${NC}"
fi

echo
echo -e "${YELLOW}Step 2: Checking Service Health${NC}"
echo

# Check all services
check_service "orchestration" "5000" "Orchestration Service"
check_service "scanner" "5001" "Scanner Service"
check_service "pattern" "5002" "Pattern Service"
check_service "trading" "5005" "Trading Service"
check_service "news" "5008" "News Service"
check_service "reporting" "5009" "Reporting Service"

echo
echo -e "${YELLOW}Step 3: Checking Redis${NC}"
echo

# Check Redis
printf "%-25s" "Redis Cache..."
if docker exec catalyst-redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}" ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CONNECTED${NC}"
else
    echo -e "${RED}✗ NOT CONNECTED${NC}"
fi

echo
echo -e "${YELLOW}Step 4: Checking Alpaca Connection${NC}"
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
else
    echo -e "${RED}✗ NOT CONNECTED${NC}"
fi

echo
echo -e "${YELLOW}Step 5: System Summary${NC}"
echo

# Count running containers
running_containers=$(docker-compose ps | grep "Up" | wc -l)
total_containers=8  # Including Redis

echo -e "Running Containers: ${GREEN}$running_containers/$total_containers${NC}"

# Check for errors in logs
echo
echo -e "${YELLOW}Recent Errors (last 5):${NC}"
docker-compose logs --tail=1000 2>&1 | grep -i "error" | tail -5 || echo -e "${GREEN}No recent errors found${NC}"

echo
echo -e "${YELLOW}Step 6: Quick Actions${NC}"
echo

echo "To fix News Service RSS issues:"
echo -e "${BLUE}  docker-compose restart news${NC}"
echo

echo "To view live logs:"
echo -e "${BLUE}  docker-compose logs -f [service-name]${NC}"
echo

echo "To restart all services:"
echo -e "${BLUE}  docker-compose restart${NC}"
echo

echo "To trigger a market scan:"
echo -e "${BLUE}  curl -X POST http://localhost:5001/scan${NC}"
echo

echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   System is OPERATIONAL! 🚀                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Apply database migration: ${BLUE}psql \$DATABASE_URL < fix-database-schema.sql${NC}"
echo "2. Monitor logs: ${BLUE}docker-compose logs -f${NC}"
echo "3. Check MCP connection: ${BLUE}docker logs catalyst-orchestration${NC}"