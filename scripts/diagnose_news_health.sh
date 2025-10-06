#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: diagnose-news-health.sh
# Version: 1.0.0
# Last Updated: 2025-10-06
# Purpose: Diagnose why news service health check is failing

# REVISION HISTORY:
# v1.0.0 (2025-10-06) - Initial diagnostic script

# Description:
# Tests the news service health endpoint multiple ways to find the issue

echo "🔍 News Service Health Check Diagnosis"
echo "========================================"
echo ""

echo "1️⃣ Check if news container is running:"
docker ps | grep catalyst-news
echo ""

echo "2️⃣ Test health endpoint from HOST machine:"
echo "   curl http://localhost:5008/health"
curl -v http://localhost:5008/health 2>&1
echo ""
echo ""

echo "3️⃣ Test health endpoint from INSIDE container:"
echo "   (This is what Docker healthcheck does)"
docker exec catalyst-news python -c "import requests; print(requests.get('http://localhost:5008/health', timeout=5).json())" 2>&1
echo ""

echo "4️⃣ Check if uvicorn is actually listening on port 5008:"
docker exec catalyst-news netstat -tlnp 2>/dev/null | grep 5008 || echo "netstat not available, trying ss..."
docker exec catalyst-news ss -tlnp 2>/dev/null | grep 5008 || echo "Can't check listening ports"
echo ""

echo "5️⃣ Check recent logs from news service:"
docker logs catalyst-news --tail 20
echo ""

echo "6️⃣ Manual health check test:"
echo "   If you can curl from host but health check fails inside container,"
echo "   it means the Dockerfile health check command needs fixing."
echo ""

echo "💡 LIKELY ISSUE:"
echo "   The health check in Dockerfile tries to import requests, but"
echo "   uvicorn might not be fully ready when health check runs."
echo ""
echo "   Solution: Increase start-period in HEALTHCHECK or use curl instead"
