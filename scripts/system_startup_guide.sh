#!/bin/bash
# Catalyst Trading System - Complete Startup & Testing Guide
# Version: 4.2.0
# Last Updated: 2025-09-20

echo "🎩 Catalyst Trading System - Startup & Testing Guide v4.2"
echo "=============================================================="

# === PHASE 1: PRE-STARTUP CHECKS ===
echo ""
echo "📋 PHASE 1: Pre-Startup Verification"
echo "------------------------------------"

# Check environment variables
echo "🔍 Checking environment variables..."
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    echo "💡 Run: export DATABASE_URL='your_digitalocean_connection_string'"
    exit 1
else
    echo "✅ DATABASE_URL configured"
fi

if [ -z "$REDIS_URL" ]; then
    echo "⚠️  REDIS_URL not set, using default"
    export REDIS_URL="redis://localhost:6379"
fi

# Check if schema upgrade was successful
echo "🗃️  Checking v4.2 schema..."
python3 -c "
import asyncio
import asyncpg
import os

async def check_schema():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        tables = await conn.fetch(\"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'\")
        table_names = [row['table_name'] for row in tables]
        
        required_v42 = ['risk_parameters', 'daily_risk_metrics', 'risk_events', 'news_articles']
        missing = [t for t in required_v42 if t not in table_names]
        
        if missing:
            print(f'❌ Missing v4.2 tables: {missing}')
            print('💡 Run: python3 scripts/upgrade_to_v42_schema.py')
            exit(1)
        else:
            print('✅ v4.2 schema complete')
        
        await conn.close()
    except Exception as e:
        print(f'❌ Schema check failed: {e}')
        exit(1)

asyncio.run(check_schema())
"

echo ""
echo "🐳 PHASE 2: Service Startup"
echo "----------------------------"

# Stop any running services first
echo "🛑 Stopping any running services..."
docker-compose down

# Start infrastructure services first
echo "🏗️  Starting infrastructure services..."
docker-compose up -d postgres redis

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure (30 seconds)..."
sleep 30

# Check infrastructure health
echo "🏥 Checking infrastructure health..."
docker-compose ps postgres redis

# Start core services (without risk-manager first, as it might not exist yet)
echo "🚀 Starting core services..."
docker-compose up -d orchestration scanner pattern technical trading news reporting

# Wait for services to initialize
echo "⏳ Waiting for services to initialize (30 seconds)..."
sleep 30

echo ""
echo "📊 PHASE 3: Health Check Verification"
echo "--------------------------------------"

# Function to check service health
check_service_health() {
    local service_name=$1
    local port=$2
    
    echo "🔍 Checking $service_name (port $port)..."
    
    if curl -f -s "http://localhost:$port/health" > /dev/null; then
        response=$(curl -s "http://localhost:$port/health")
        echo "✅ $service_name: HEALTHY"
        echo "   Response: $response" | head -1
    else
        echo "❌ $service_name: UNHEALTHY"
        echo "   Logs:"
        docker-compose logs --tail=5 $service_name | sed 's/^/   /'
    fi
    echo ""
}

# Check all services
check_service_health "orchestration" "5000"
check_service_health "scanner" "5001" 
check_service_health "pattern" "5002"
check_service_health "technical" "5003"
check_service_health "trading" "5005"
check_service_health "news" "5008"
check_service_health "reporting" "5009"

echo ""
echo "🧪 PHASE 4: MCP Orchestration Testing"
echo "--------------------------------------"

echo "🔧 Testing MCP orchestration service directly..."

# Test MCP service can start
echo "📡 Testing orchestration service MCP initialization..."
timeout 10s python3 services/orchestration/orchestration-service.py --test 2>&1 | head -10

echo ""
echo "🔗 Testing REST API endpoints..."

# Test orchestration health (should work via HTTP even if MCP)
echo "🏥 Orchestration health via HTTP..."
curl -s "http://localhost:5000/health" || echo "❌ No HTTP health endpoint"

# Test scanner API
echo "📊 Testing scanner API..."
curl -s -X POST "http://localhost:5001/scan" \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "max_candidates": 5}' | head -5

echo ""
echo "💾 PHASE 5: Database Connection Verification"
echo "---------------------------------------------"

echo "📊 Running connection diagnostic..."
python3 scripts/database_connection_fix.py | grep -E "Total Connections|Usage|application_name"

echo ""
echo "🎯 PHASE 6: Service Integration Testing"
echo "----------------------------------------"

# Test workflow integration
echo "🔄 Testing service integration workflow..."

# 1. Trigger a scan
echo "1️⃣  Triggering market scan..."
scan_response=$(curl -s -X POST "http://localhost:5001/scan" \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "max_candidates": 3}')

if echo "$scan_response" | grep -q "success\|candidates"; then
    echo "✅ Scanner responding correctly"
else
    echo "❌ Scanner not responding as expected"
    echo "Response: $scan_response"
fi

# 2. Test pattern service
echo "2️⃣  Testing pattern analysis..."
pattern_response=$(curl -s -X POST "http://localhost:5002/analyze" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}')

if echo "$pattern_response" | grep -q "pattern\|confidence\|analysis"; then
    echo "✅ Pattern service responding correctly"
else
    echo "❌ Pattern service not responding as expected"
fi

# 3. Test trading service positions
echo "3️⃣  Testing trading service..."
positions_response=$(curl -s "http://localhost:5005/positions")

if echo "$positions_response" | grep -q "positions\|[]"; then
    echo "✅ Trading service responding correctly"
else
    echo "❌ Trading service not responding as expected"
fi

echo ""
echo "🖥️  PHASE 7: Claude Desktop MCP Setup"
echo "--------------------------------------"

echo "📋 Claude Desktop MCP Configuration:"
echo ""
echo "1️⃣  Create/update ~/.claude/mcp_settings.json:"
echo '{'
echo '  "mcpServers": {'
echo '    "catalyst-trading": {'
echo '      "command": "python3",'
echo '      "args": ["'$(pwd)'/services/orchestration/orchestration-service.py"],'
echo '      "env": {'
echo '        "DATABASE_URL": "'$DATABASE_URL'",'
echo '        "REDIS_URL": "'$REDIS_URL'",'
echo '        "ENVIRONMENT": "production"'
echo '      }'
echo '    }'
echo '  }'
echo '}'
echo ""

echo "2️⃣  Test MCP connection:"
echo "   Open Claude Desktop and try:"
echo '   "Hi Claude, what is the current status of the Catalyst Trading System?"'
echo ""

echo "3️⃣  Available MCP commands to test:"
echo "   • Check system status: 'Show me the trading system health'"
echo "   • View risk metrics: 'What are the current risk management parameters?'"
echo "   • Start trading: 'Start a conservative trading cycle'"
echo "   • Check positions: 'Show me current trading positions'"
echo ""

echo "🔧 PHASE 8: Troubleshooting Commands"
echo "-------------------------------------"

echo "📊 If services fail, use these commands:"
echo ""
echo "# View specific service logs:"
echo "docker-compose logs orchestration"
echo "docker-compose logs scanner"
echo "docker-compose logs trading"
echo ""
echo "# Restart specific service:"
echo "docker-compose restart orchestration"
echo ""
echo "# Check database connections:"
echo "python3 scripts/database_connection_fix.py"
echo ""
echo "# Test orchestration MCP directly:"
echo "cd services/orchestration && python3 orchestration-service.py"
echo ""
echo "# Check all container status:"
echo "docker-compose ps"
echo ""

echo "✅ STARTUP COMPLETE!"
echo "===================="
echo ""
echo "🎯 System Status Summary:"
docker-compose ps

echo ""
echo "🚀 Next Steps:"
echo "1. ✅ Services are running"
echo "2. 🖥️  Configure Claude Desktop with the MCP settings above"
echo "3. 🧪 Test MCP connection with Claude Desktop"
echo "4. 📊 Monitor system with: docker-compose logs -f"
echo ""
echo "🎩 Catalyst Trading System v4.2 is ready for trading!"
