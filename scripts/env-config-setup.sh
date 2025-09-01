#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: setup-environment.sh
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Setup environment configuration for Catalyst Trading System

# REVISION HISTORY:
# v4.1.0 (2025-09-01) - Environment setup for Docker deployment
# - Create .env files for all services
# - Setup Alpaca API configuration
# - Configure database connections

# Description of Service:
# Sets up all required environment configuration files
# for the Catalyst Trading System Docker deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Catalyst Trading System Environment Setup    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo

# Create config directory
mkdir -p config

echo -e "${YELLOW}Step 1: Creating main environment file...${NC}"

# Create the main .env file in project root (for docker-compose)
cat > .env << 'EOF'
# Catalyst Trading System - Main Environment Configuration
# This file is used by docker-compose.yml

# Alpaca Trading API Configuration
ALPACA_API_KEY=PKTEST12345678901234567890
ALPACA_SECRET_KEY=abcdefghijklmnopqrstuvwxyz1234567890abcdef
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database Configuration (DigitalOcean Managed Database)
# Replace with your actual database URL
DATABASE_URL=postgresql://catalyst:your_password@your-db-host:25060/catalyst_trading?sslmode=require
DB_PASSWORD=your_secure_password

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=RedisCatalyst2025!SecureCache

# System Configuration
ENVIRONMENT=production
MCP_MODE=production
LOG_LEVEL=INFO

# Trading Configuration
TRADING_ENABLED=true
MAX_POSITIONS=5
MAX_POSITION_SIZE=1000
MIN_SIGNAL_CONFIDENCE=60
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=4.0

# Scanning Configuration
INITIAL_UNIVERSE_SIZE=200
TOP_TRACKING_SIZE=100
CATALYST_FILTER_SIZE=50
FINAL_SELECTION_SIZE=5

# Service Ports (for internal communication)
ORCHESTRATION_SERVICE_PORT=5000
NEWS_SERVICE_PORT=5008
SCANNER_SERVICE_PORT=5001
PATTERN_SERVICE_PORT=5002
TECHNICAL_SERVICE_PORT=5003
TRADING_SERVICE_PORT=5005
REPORTING_SERVICE_PORT=5009
REDIS_PORT=6379

# Market Data Configuration
MARKET_DATA_PROVIDER=alpaca
UPDATE_FREQUENCY=60
PREMARKET_START=04:00
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
POSTMARKET_END=20:00

# News API Configuration (add your API keys here)
NEWS_API_KEY=your_news_api_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
FINNHUB_API_KEY=your_finnhub_key

# Risk Management
MAX_DAILY_LOSS=2000
MAX_POSITION_RISK=0.02
POSITION_SIZE_MULTIPLIER=1.0
RISK_FREE_RATE=0.05

# Notification Settings
SLACK_WEBHOOK_URL=your_slack_webhook_url
EMAIL_ALERTS_ENABLED=false
DISCORD_WEBHOOK_URL=your_discord_webhook_url
EOF

echo -e "${GREEN}✓ Main .env file created${NC}"

echo -e "${YELLOW}Step 2: Creating service-specific environment files...${NC}"

# Create config/.env for services that need it
cat > config/.env << 'EOF'
# Catalyst Trading System - Service Configuration
# This file is used by individual services

# Inherit from main environment
ALPACA_API_KEY=${ALPACA_API_KEY}
ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
ALPACA_BASE_URL=${ALPACA_BASE_URL}
DATABASE_URL=${DATABASE_URL}
REDIS_URL=${REDIS_URL}

# Service-specific overrides
SERVICE_TIMEOUT=30
HTTP_TIMEOUT=15
MAX_RETRIES=3
RETRY_DELAY=1

# Logging
LOG_FORMAT=json
LOG_ROTATION=daily
LOG_RETENTION_DAYS=30
EOF

echo -e "${GREEN}✓ Service configuration file created${NC}"

echo -e "${YELLOW}Step 3: Creating example production environment...${NC}"

# Create an example production environment file
cat > config/.env.production.example << 'EOF'
# Catalyst Trading System - Production Environment Example
# Copy this to .env.production and update with your actual values

# Alpaca Trading API (Production)
ALPACA_API_KEY=your_live_api_key_here
ALPACA_SECRET_KEY=your_live_secret_key_here
ALPACA_BASE_URL=https://api.alpaca.markets

# Database (Production)
DATABASE_URL=postgresql://catalyst_user:secure_password@your-prod-db:25060/catalyst_trading?sslmode=require

# Redis (Production)
REDIS_URL=redis://your-redis-host:6379/0
REDIS_PASSWORD=your_secure_redis_password

# Production Trading Settings
TRADING_ENABLED=true
MAX_POSITIONS=10
MAX_POSITION_SIZE=5000
MIN_SIGNAL_CONFIDENCE=70

# Production Monitoring
LOG_LEVEL=WARNING
ENVIRONMENT=production
ALERTS_ENABLED=true

# API Keys (Production)
NEWS_API_KEY=your_production_news_api_key
ALPHA_VANTAGE_API_KEY=your_production_alpha_vantage_key
FINNHUB_API_KEY=your_production_finnhub_key

# Security
JWT_SECRET_KEY=your_jwt_secret_key
ENCRYPTION_KEY=your_encryption_key
SSL_VERIFY=true
EOF

echo -e "${GREEN}✓ Production environment example created${NC}"

echo -e "${YELLOW}Step 4: Creating Docker environment file...${NC}"

# Create .env.docker for Docker-specific settings
cat > .env.docker << 'EOF'
# Docker-specific environment settings
COMPOSE_PROJECT_NAME=catalyst-trading
COMPOSE_HTTP_TIMEOUT=120
DOCKER_BUILDKIT=1

# Container resource limits
POSTGRES_MEMORY=512m
REDIS_MEMORY=256m
SERVICE_MEMORY=512m

# Network settings
NETWORK_NAME=catalyst-network
EXTERNAL_NETWORK=false
EOF

echo -e "${GREEN}✓ Docker environment file created${NC}"

echo -e "${YELLOW}Step 5: Creating environment validation script...${NC}"

# Create a script to validate environment setup
cat > scripts/validate-env.sh << 'EOF'
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
EOF

chmod +x scripts/validate-env.sh

echo -e "${GREEN}✓ Environment validation script created${NC}"

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ENVIRONMENT SETUP COMPLETE             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"

echo
echo -e "${YELLOW}Files Created:${NC}"
echo "• .env (main environment file for docker-compose)"
echo "• config/.env (service-specific configuration)"
echo "• config/.env.production.example (production template)"
echo "• .env.docker (Docker-specific settings)"
echo "• scripts/validate-env.sh (environment validation)"

echo
echo -e "${RED}⚠️  IMPORTANT: Update Required Configuration${NC}"
echo
echo -e "${YELLOW}1. Edit .env file and replace placeholders:${NC}"
echo "   • ALPACA_API_KEY=your_actual_api_key"
echo "   • ALPACA_SECRET_KEY=your_actual_secret_key"
echo "   • DATABASE_URL=your_digitalocean_database_url"
echo
echo -e "${YELLOW}2. Validate your configuration:${NC}"
echo "   ./scripts/validate-env.sh"
echo
echo -e "${YELLOW}3. Build and start services:${NC}"
echo "   docker-compose build"
echo "   docker-compose up -d"

echo
echo -e "${BLUE}Get Alpaca API Keys:${NC}"
echo "1. Go to: https://alpaca.markets/"
echo "2. Sign up for paper trading account"
echo "3. Generate API keys in dashboard"
echo "4. Use paper trading URL: https://paper-api.alpaca.markets"
