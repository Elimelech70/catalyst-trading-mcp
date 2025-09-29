#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: fix_all_connection_pools.sh
# Version: 1.0.0
# Last Updated: 2025-09-29
# Purpose: Fix all service connection pools for 25-connection database

echo "========================================================================"
echo "🎩 CATALYST TRADING SYSTEM - CONNECTION POOL FIX"
echo "========================================================================"
echo "Database Limit: 25 connections"
echo "Target: 1-2 connections per service (14 total)"
echo "========================================================================"
echo ""

# Function to fix a service file
fix_service() {
    local file=$1
    local service_name=$2
    
    if [ -f "$file" ]; then
        echo "📝 Fixing $service_name..."
        
        # Backup original
        cp "$file" "${file}.backup"
        
        # Replace min_size and max_size in asyncpg.create_pool calls
        # This handles multi-line pool creation
        sed -i 's/min_size=[0-9]\+/min_size=1/g' "$file"
        sed -i 's/max_size=[0-9]\+/max_size=2/g' "$file"
        
        echo "   ✅ Updated $service_name (min=1, max=2)"
        echo "   📋 Backup saved: ${file}.backup"
    else
        echo "   ❌ File not found: $file"
    fi
    echo ""
}

# Fix all services
fix_service "services/scanner/scanner-service.py" "Scanner Service"
fix_service "services/pattern/pattern-service.py" "Pattern Service"  
fix_service "services/risk-manager/risk-manager-service.py" "Risk Manager Service"
fix_service "services/trading/trading-service.py" "Trading Service"
fix_service "services/news/news-service.py" "News Service"
fix_service "services/reporting/reporting-service.py" "Reporting Service"
fix_service "services/orchestration/orchestration-service.py" "Orchestration Service"

echo "========================================================================"
echo "📊 SUMMARY"
echo "========================================================================"
echo "Total allocation: 7 services × 2 max = 14 connections"
echo "Database limit: 25 connections"
echo "Reserved for admin: 5 connections"
echo "Status: ✅ SAFE (14 < 20 available)"
echo "========================================================================"
echo ""
echo "🚀 NEXT STEPS:"
echo "1. Restart all services:"
echo "   docker-compose restart"
echo ""
echo "2. Monitor startup:"
echo "   docker-compose logs -f --tail=100"
echo ""
echo "3. Verify all services healthy:"
echo "   docker-compose ps"
echo ""
echo "✅ Connection pool fix complete!"
