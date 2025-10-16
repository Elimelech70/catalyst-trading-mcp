#!/bin/bash
# Name of Application: Catalyst Trading MCP
# Name of file: apply-all-fixes.sh
# Version: 1.0.0
# Last Updated: 2025-10-16
# Purpose: Apply all service fixes and verify system health

# REVISION HISTORY:
# v1.0.0 (2025-10-16) - Master fix script for all service issues

set -e  # Exit on any error

echo "============================================"
echo "🎩 CATALYST TRADING MCP - SYSTEM REPAIR"
echo "============================================"
echo ""

# Navigate to project root
cd /root/catalyst-trading-mcp

# FIX 1: Technical Service
echo "🔧 [1/3] Fixing Technical Service..."
echo "----------------------------------------"
cd services/technical

# Fix line 148 - SERVICE_TITLE should be SERVICE_NAME
sed -i 's/title=SERVICE_TITLE/title=SERVICE_NAME/g' technical-service.py
sed -i 's/version=SERVICE_VERSION/version="5.0.0"/g' technical-service.py

# Also ensure SERVICE_NAME is defined at the top
if ! grep -q "SERVICE_NAME = " technical-service.py; then
    sed -i '1a SERVICE_NAME = "Technical Analysis Service"' technical-service.py
fi

echo "✅ Technical Service fixed"
echo ""

# FIX 2: Pattern Service
echo "🔧 [2/3] Fixing Pattern Service..."
echo "----------------------------------------"
cd ../pattern

# Add missing CORSMiddleware import
if ! grep -q "from fastapi.middleware.cors import CORSMiddleware" pattern-service.py; then
    sed -i '/from fastapi import FastAPI/a from fastapi.middleware.cors import CORSMiddleware' pattern-service.py
fi

echo "✅ Pattern Service fixed"
echo ""

# FIX 3: Orchestration Service (Most Complex)
echo "🔧 [3/3] Fixing Orchestration Service..."
echo "----------------------------------------"
cd ../orchestration

# Remove the problematic on_initialize decorator
# The new FastMCP doesn't use on_initialize, it uses lifespan events
sed -i '/@mcp.on_initialize()/d' orchestration-service.py

# Remove the function that was decorated (likely the next few lines)
# We need to be careful here - let's create a backup first
cp orchestration-service.py orchestration-service.py.backup

# Use Python to properly fix the file
cat > /tmp/fix_mcp.py << 'PYFIX'
import re

# Read the file
with open('orchestration-service.py', 'r') as f:
    content = f.read()

# Remove the on_initialize pattern and its function
pattern = r'@mcp\.on_initialize\(\)[\s\S]*?(?=\n(?:@|def|class|\Z))'
content = re.sub(pattern, '', content)

# Add proper initialization using FastMCP run method
if 'if __name__ == "__main__":' not in content:
    content += '''
# Run the MCP server
if __name__ == "__main__":
    import sys
    mcp.run(transport="stdio")
'''

# Write back
with open('orchestration-service.py', 'w') as f:
    f.write(content)
PYFIX

python3 /tmp/fix_mcp.py
rm /tmp/fix_mcp.py

echo "✅ Orchestration Service fixed"
echo ""

# Rebuild all affected services
echo "🔨 Rebuilding Docker images..."
echo "----------------------------------------"
cd /root/catalyst-trading-mcp

docker-compose build technical pattern orchestration

echo ""
echo "🔄 Restarting services..."
echo "----------------------------------------"
docker-compose restart technical pattern orchestration

# Wait for services to start
echo ""
echo "⏳ Waiting for services to initialize (30 seconds)..."
sleep 30

# Check service health
echo ""
echo "📊 Service Health Check:"
echo "----------------------------------------"

# Function to check service
check_service() {
    local service=$1
    local port=$2
    
    if docker-compose ps | grep -q "catalyst-$service.*Up"; then
        echo "✅ $service: RUNNING"
        
        # Try to hit health endpoint
        if curl -s -f -o /dev/null "http://localhost:$port/health" 2>/dev/null; then
            echo "   └─ Health endpoint: RESPONSIVE"
        else
            echo "   └─ Health endpoint: NOT RESPONDING"
        fi
    else
        echo "❌ $service: DOWN"
        # Show last error
        echo "   └─ Last error:"
        docker-compose logs --tail 5 $service 2>&1 | grep -E "(Error|Exception|Traceback)" | head -3 | sed 's/^/      /'
    fi
}

check_service "technical" "5003"
check_service "pattern" "5002"
check_service "orchestration" "5000"
check_service "scanner" "5001"
check_service "trading" "5005"
check_service "risk-manager" "5004"
check_service "reporting" "5009"
check_service "news" "5008"

echo ""
echo "============================================"
echo "🎯 SYSTEM REPAIR COMPLETE"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Check logs: docker-compose logs -f technical pattern orchestration"
echo "2. If services still failing, check: docker-compose ps"
echo "3. For news service performance issue, may need to check API rate limits"
echo ""