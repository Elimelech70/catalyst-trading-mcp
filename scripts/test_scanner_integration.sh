#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: test-scanner-news-integration.sh
# Version: 1.0.0
# Last Updated: 2025-10-06
# Purpose: Test that scanner and news services are working together

# REVISION HISTORY:
# v1.0.0 (2025-10-06) - Initial integration test

# Description:
# Tests that scanner can communicate with news service and both work correctly

echo "🧪 Catalyst Trading System - Integration Test"
echo "=============================================="
echo ""

echo "1️⃣ Test News Service Health:"
echo "   GET http://localhost:5008/health"
curl -s http://localhost:5008/health | jq '.'
echo ""
echo ""

echo "2️⃣ Test Scanner Service Health:"
echo "   GET http://localhost:5001/health"
curl -s http://localhost:5001/health | jq '.'
echo ""
echo ""

echo "3️⃣ Test News Service - Fetch Catalysts for AAPL:"
echo "   GET http://localhost:5008/api/v1/catalysts/AAPL?hours=24"
curl -s "http://localhost:5008/api/v1/catalysts/AAPL?hours=24&min_strength=0.3" | jq '.'
echo ""
echo ""

echo "4️⃣ Test Scanner Service - Run Scan:"
echo "   POST http://localhost:5001/api/v1/scan"
curl -s -X POST "http://localhost:5001/api/v1/scan" \
  -H "Content-Type: application/json" \
  -d '{"mode": "conservative", "max_results": 10}' | jq '.'
echo ""
echo ""

echo "✅ Integration Test Complete!"
echo ""
echo "Expected Results:"
echo "  - Both services return 'healthy' status"
echo "  - News service returns catalysts for AAPL"
echo "  - Scanner returns scan results with candidates"
echo ""
echo "If all tests passed, your system is ready! 🚀"
