#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: fix-dockerfiles.sh
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Fix Dockerfile COPY commands and create missing directories

# REVISION HISTORY:
# v4.1.0 (2025-09-01) - Fix Docker COPY syntax errors
# - Replace invalid shell syntax in COPY commands
# - Create missing directories in build context
# - Update Dockerfiles with proper syntax

# Description of Service:
# Fixes Docker build failures by correcting COPY command syntax
# and ensuring all required directories exist in the build context

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Catalyst Trading System Dockerfile Fix       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found. Please run from project root.${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Creating missing directories in build contexts...${NC}"

# Create all required directories for each service
services=(
    "news:models,sources,processors"
    "pattern:patterns,models"
    "reporting:templates,reports,charts,static"
    "technical:indicators,models"
    "trading:strategies,models"
)

for service_config in "${services[@]}"; do
    service_name="${service_config%%:*}"
    directories="${service_config#*:}"
    
    echo -e "${BLUE}Creating directories for $service_name service...${NC}"
    
    cd "services/$service_name"
    
    IFS=',' read -ra DIRS <<< "$directories"
    for dir in "${DIRS[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            # Create a placeholder file so git tracks the directory
            echo "# Placeholder file for $service_name/$dir directory" > "$dir/.gitkeep"
            echo -e "${GREEN}  ✓ Created: $dir/${NC}"
        else
            echo -e "${GREEN}  ✓ Exists: $dir/${NC}"
        fi
    done
    
    cd ../../
done

echo -e "${YELLOW}Step 2: Fixing Dockerfile COPY syntax...${NC}"

# Fix News Service Dockerfile
echo -e "${BLUE}Fixing news service Dockerfile...${NC}"
cat > services/news/Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: services/news/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for News Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('vader_lexicon'); nltk.download('punkt')"

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY models/ ./models/
COPY sources/ ./sources/
COPY processors/ ./processors/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5008/health')" || exit 1

# Run the service
CMD ["python", "-u", "news-service.py"]
EOF

# Fix Pattern Service Dockerfile
echo -e "${BLUE}Fixing pattern service Dockerfile...${NC}"
cat > services/pattern/Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: services/pattern/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for Pattern Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY patterns/ ./patterns/
COPY models/ ./models/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5002/health')" || exit 1

# Run the service
CMD ["python", "-u", "pattern-service.py"]
EOF

# Fix Reporting Service Dockerfile
echo -e "${BLUE}Fixing reporting service Dockerfile...${NC}"
cat > services/reporting/Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: services/reporting/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for Reporting Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY templates/ ./templates/
COPY reports/ ./reports/
COPY charts/ ./charts/
COPY static/ ./static/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5009

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5009/health')" || exit 1

# Run the service
CMD ["python", "-u", "reporting-service.py"]
EOF

# Fix Technical Service Dockerfile (if it exists)
if [ -d "services/technical" ]; then
    echo -e "${BLUE}Fixing technical service Dockerfile...${NC}"
    cat > services/technical/Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: services/technical/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for Technical Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY indicators/ ./indicators/
COPY models/ ./models/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5003/health')" || exit 1

# Run the service
CMD ["python", "-u", "technical-service.py"]
EOF
fi

# Fix Trading Service Dockerfile (if it exists)
if [ -d "services/trading" ]; then
    echo -e "${BLUE}Fixing trading service Dockerfile...${NC}"
    cat > services/trading/Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: services/trading/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for Trading Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY strategies/ ./strategies/
COPY models/ ./models/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5005

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5005/health')" || exit 1

# Run the service
CMD ["python", "-u", "trading-service.py"]
EOF
fi

echo -e "${YELLOW}Step 3: Setting up environment variables...${NC}"

# Check if .env file exists and create one with placeholders if it doesn't
if [ ! -f "config/.env" ]; then
    mkdir -p config
    echo -e "${BLUE}Creating config/.env file with placeholders...${NC}"
    cat > config/.env << 'EOF'
# Catalyst Trading System Configuration
# Replace these placeholders with your actual values

# Alpaca Trading API
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database (DigitalOcean Managed Database)
DATABASE_URL=postgresql://username:password@host:25060/catalyst_trading?sslmode=require

# Redis Configuration  
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=RedisCatalyst2025!SecureCache

# Service Configuration
TRADING_ENABLED=true
MAX_POSITIONS=5
MAX_POSITION_SIZE=1000
MIN_SIGNAL_CONFIDENCE=60

# Service Ports
ORCHESTRATION_SERVICE_PORT=5000
NEWS_SERVICE_PORT=5008
SCANNER_SERVICE_PORT=5001
PATTERN_SERVICE_PORT=5002
TECHNICAL_SERVICE_PORT=5003
TRADING_SERVICE_PORT=5005
REPORTING_SERVICE_PORT=5009
EOF
    echo -e "${YELLOW}⚠️  Please edit config/.env with your actual API keys and database URL${NC}"
fi

echo -e "${YELLOW}Step 4: Testing Docker builds...${NC}"

# Clean and build orchestration service first
echo -e "${BLUE}Testing orchestration service build...${NC}"
if docker-compose build orchestration --no-cache; then
    echo -e "${GREEN}✓ Orchestration service builds successfully${NC}"
else
    echo -e "${RED}✗ Orchestration service build failed${NC}"
    exit 1
fi

# Test news service build
echo -e "${BLUE}Testing news service build...${NC}"
if docker-compose build news --no-cache; then
    echo -e "${GREEN}✓ News service builds successfully${NC}"
else
    echo -e "${RED}✗ News service build failed${NC}"
fi

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║               DOCKERFILE FIX COMPLETE            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"

echo
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update config/.env with your actual API keys"
echo "2. Build all services: ${BLUE}docker-compose build${NC}"
echo "3. Start the system: ${BLUE}docker-compose up -d${NC}"
echo "4. Check service health: ${BLUE}docker-compose ps${NC}"
echo "5. View logs: ${BLUE}docker-compose logs -f${NC}"

echo
echo -e "${YELLOW}Environment Setup Required:${NC}"
echo "• Edit config/.env file with your Alpaca API credentials"
echo "• Update DATABASE_URL with your DigitalOcean database connection string"
echo "• Ensure all API keys are properly configured"
