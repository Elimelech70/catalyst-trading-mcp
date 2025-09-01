#!/bin/bash
# Environment validation script

set -e

echo "Validating Catalyst Trading System Environment..."

# Load environment
if [ -f ".env" ]; then
    source .env
else
    echo "ERROR: .env file not found!"
    exit 1
fi

# Check required variables
required_vars=(
    "ALPACA_API_KEY"
    "ALPACA_SECRET_KEY"
    "DATABASE_URL"
    "REDIS_URL"
)

missing_vars=0
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" = "your_"* ]; then
        echo "❌ $var is not set or contains placeholder value"
        ((missing_vars++))
    else
        echo "✅ $var is configured"
    fi
done

if [ $missing_vars -gt 0 ]; then
    echo ""
    echo "❌ $missing_vars required environment variables need configuration"
    echo "Please edit .env file with your actual values"
    exit 1
else
    echo ""
    echo "✅ All required environment variables are configured"
fi
