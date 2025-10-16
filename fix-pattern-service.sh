#!/bin/bash
# Name of Application: Catalyst Trading MCP
# Name of file: fix-pattern-service.sh
# Version: 1.0.0
# Last Updated: 2025-10-16
# Purpose: Fix pattern service missing CORSMiddleware import

# REVISION HISTORY:
# v1.0.0 (2025-10-16) - Add missing CORSMiddleware import

echo "🔧 Fixing Pattern Service..."

# Navigate to the service directory
cd /root/catalyst-trading-mcp/services/pattern

# Add the missing import at the top of the file after FastAPI import
echo "✏️ Adding missing import..."
sed -i '/from fastapi import FastAPI/a from fastapi.middleware.cors import CORSMiddleware' pattern-service.py

# Verify the fix
echo "✅ Checking fix..."
grep -n "CORSMiddleware" pattern-service.py | head -3

# Rebuild the Docker image
echo "🔨 Rebuilding Docker image..."
docker-compose build pattern

# Restart the service
echo "🔄 Restarting service..."
docker-compose restart pattern

echo "✅ Pattern Service fix complete!"