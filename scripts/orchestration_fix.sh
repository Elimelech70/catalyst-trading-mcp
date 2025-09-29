#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: fix_orchestration_http.sh
# Version: 1.1.0
# Last Updated: 2025-09-29
# Purpose: Fix orchestration service to enable HTTP health endpoints
#
# REVISION HISTORY:
# v1.1.0 (2025-09-29) - Updated to use v4.4.0
# - Use orchestration-service.py (v4.4.0 from header)
# - Enable standalone mode with HTTP server
# - HTTP Transport for both MCP and REST endpoints
#
# Description of Service:
# Fixes the orchestration service to support both MCP (Claude Desktop)
# and HTTP (REST API for health checks and service communication)

echo "🎩 DevGenius Fix - Orchestration HTTP Server (v4.4.0)"
echo "====================================================="
echo ""

echo "📊 STEP 1: Check Current Orchestration Status"
echo "----------------------------------------------"
docker ps --filter "name=catalyst-orchestration" --format "Status: {{.Status}}"
echo ""

echo "📊 STEP 2: Verify orchestration-service.py Version"
echo "---------------------------------------------------"
cd ~/catalyst-trading-mcp/services/orchestration
if [ -f "orchestration-service.py" ]; then
    echo "✅ orchestration-service.py found"
    echo "   Version info:"
    head -20 orchestration-service.py | grep -E "Version:|Last Updated:"
    echo ""
else
    echo "❌ orchestration-service.py NOT FOUND!"
    exit 1
fi

echo "📊 STEP 3: Backup Current Dockerfile"
echo "-------------------------------------"
cp Dockerfile Dockerfile.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Dockerfile backed up"
echo ""

echo "📊 STEP 4: Update Dockerfile for v4.4.0"
echo "----------------------------------------"
cat > Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: services/orchestration/Dockerfile
# Version: 4.4.0
# Last Updated: 2025-09-29
# Purpose: Docker container for Orchestration Service v4.4.0 with HTTP support

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install the Anthropic MCP Python SDK
RUN pip install "mcp[cli]"

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy orchestration-service.py (v4.4.0 with HTTP Transport support)
COPY orchestration-service.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=standalone
ENV SERVICE_PORT=5000

# Health check using HTTP endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the orchestration service
# v4.4.0 automatically provides HTTP server in standalone mode
CMD ["python", "-u", "orchestration-service.py"]
EOF

echo "✅ Dockerfile updated to use orchestration-service.py (v4.4.0)"
echo ""

echo "📊 STEP 5: Stop Current Orchestration Service"
echo "----------------------------------------------"
cd ~/catalyst-trading-mcp
docker-compose stop orchestration
echo "✅ Orchestration service stopped"
echo ""

echo "📊 STEP 6: Rebuild Orchestration Container"
echo "-------------------------------------------"
docker-compose build orchestration
if [ $? -eq 0 ]; then
    echo "✅ Orchestration container rebuilt successfully"
else
    echo "❌ Container build failed! Check errors above"
    exit 1
fi
echo ""

echo "📊 STEP 7: Start Orchestration Service"
echo "---------------------------------------"
docker-compose up -d orchestration
echo "✅ Orchestration service started"
echo ""

echo "📊 STEP 8: Monitor Service Startup"
echo "-----------------------------------"
echo "Watching logs for 30 seconds..."
timeout 30 docker logs -f catalyst-orchestration 2>&1 | grep -E "(Starting|Initializing|INFO|ERROR|health|port)" &
wait $!
echo ""

echo "📊 STEP 9: Wait for Service to Initialize"
echo "------------------------------------------"
echo "Waiting 40 seconds for service to fully start..."
for i in {40..1}; do
    echo -ne "   $i seconds remaining...\r"
    sleep 1
done
echo "                                  "
echo ""

echo "📊 STEP 10: Test HTTP Health Endpoint"
echo "--------------------------------------"
echo "Testing http://localhost:5000/health..."
for i in {1..10}; do
    echo -n "Attempt $i/10: "
    response=$(curl -s -w "\n%{http_code}" "http://localhost:5000/health" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ SUCCESS (HTTP 200)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        echo ""
        break
    elif [ "$http_code" = "000" ]; then
        echo "⏳ Not ready yet (Connection refused)"
    else
        echo "❌ HTTP $http_code"
        echo "Response: $body"
    fi
    
    if [ $i -lt 10 ]; then
        echo "   Waiting 5 seconds before retry..."
        sleep 5
    fi
done
echo ""

echo "📊 STEP 11: Check All Service Health"
echo "-------------------------------------"
services=(
    "orchestration:5000"
    "scanner:5001"
    "pattern:5002"
    "technical:5003"
    "trading:5005"
    "news:5008"
    "reporting:5009"
)

healthy_count=0
total_count=${#services[@]}

for service in "${services[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" 2>&1)
    
    if [ "$response" = "200" ]; then
        echo "✅ $name (port $port) - HEALTHY"
        ((healthy_count++))
    else
        echo "❌ $name (port $port) - UNHEALTHY (HTTP $response)"
    fi
done

echo ""
echo "📊 Summary: $healthy_count/$total_count services healthy"
echo ""

if [ $healthy_count -eq $total_count ]; then
    echo "🎉 SUCCESS! All services are now healthy!"
    echo ""
    echo "✅ System Status:"
    echo "   • Orchestration v4.4.0 running with HTTP transport"
    echo "   • All 7 services responding to health checks"
    echo "   • Ready for Claude Desktop connection"
    echo ""
    echo "📋 Next Steps:"
    echo "   1. Test status endpoint: curl http://localhost:5000/status | jq"
    echo "   2. Configure Claude Desktop to connect to your server"
    echo "   3. Test MCP connection with Claude"
    echo ""
    echo "🔗 Available Endpoints:"
    echo "   • http://localhost:5000/health - Health check"
    echo "   • http://localhost:5000/status - Detailed status"
    echo "   • http://localhost:5000/api/health - API health"
    echo "   • http://localhost:5000/api/status - API status"
else
    echo "⚠️  Some services still unhealthy"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check orchestration logs:"
    echo "      docker logs catalyst-orchestration --tail 50"
    echo ""
    echo "   2. Verify environment variables:"
    echo "      docker exec catalyst-orchestration env | grep -E '(DATABASE|REDIS)'"
    echo ""
    echo "   3. Test manual connection:"
    echo "      docker exec -it catalyst-orchestration python -c 'import asyncio; print(asyncio.run(1))'"
fi

echo ""
echo "🎩 DevGenius Fix Complete!"
