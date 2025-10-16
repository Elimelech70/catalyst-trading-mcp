#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: fix_scanner_column_names.sh
# Version: 1.0.0
# Last Updated: 2025-10-16
# Purpose: Fix incorrect column names in scanner service

# REVISION HISTORY:
# v1.0.0 (2025-10-16) - Fix column name mismatches
#   - Change cycle_start to started_at
#   - Change combined_score to composite_score

echo "========================================"
echo "Fixing Scanner Service Column Names"
echo "========================================"

# Get into the scanner container
CONTAINER="catalyst-scanner"

# Fix 1: Replace cycle_start with started_at
echo "Fixing cycle_start → started_at..."
docker exec $CONTAINER sed -i 's/cycle_start/started_at/g' /app/scanner-service.py

# Fix 2: Replace combined_score with composite_score  
echo "Fixing combined_score → composite_score..."
docker exec $CONTAINER sed -i 's/combined_score/composite_score/g' /app/scanner-service.py

# Restart the scanner to apply changes
echo "Restarting scanner service..."
docker-compose restart catalyst-scanner

# Wait for service to come up
sleep 5

# Test the health endpoint
echo "Testing scanner health..."
curl -f http://localhost:5001/health && echo "✅ Scanner is healthy" || echo "❌ Scanner health check failed"

echo "========================================"
echo "Fix Applied!"
echo "========================================"