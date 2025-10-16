#!/bin/bash
# Name of Application: Catalyst Trading MCP
# Name of file: fix-technical-service.sh
# Version: 1.0.0
# Last Updated: 2025-10-16
# Purpose: Fix technical service variable naming error

# REVISION HISTORY:
# v1.0.0 (2025-10-16) - Fix SERVICE_TITLE -> SERVICE_NAME

echo "🔧 Fixing Technical Service..."

# Navigate to the service directory
cd /root/catalyst-trading-mcp/services/technical

# Fix the variable name error
sed -i 's/SERVICE_TITLE/SERVICE_NAME/g' technical-service.py
sed -i 's/SERVICE_VERSION/"5.0.0"/g' technical-service.py

# Verify the fix
echo "✅ Checking fix..."
grep -n "FastAPI(title=" technical-service.py

# Rebuild the Docker image
echo "🔨 Rebuilding Docker image..."
docker-compose build technical

# Restart the service
echo "🔄 Restarting service..."
docker-compose restart technical

echo "✅ Technical Service fix complete!"