Catalyst Trading System MCP Implementation Guide
Phase 1: Foundation & Data Collection
Version: 1.0.0
Date: December 30, 2024
Objective: Get MCP-enabled trading system operational and collecting comprehensive market data
Target: 55% → 60% accuracy with Claude assistance

🎯 Phase 1 Goals

Operational System: All MCP services running and accessible to Claude
Data Collection: Recording 100 securities per scan, trading top 5
Paper Trading: Active trading via Alpaca paper account
Learning Foundation: Every trade recorded with full context


📋 Pre-Implementation Checklist
Required Accounts

 NewsAPI.org - Free tier (500 requests/day)
 Alpaca Markets - Paper trading account
 DigitalOcean - Droplet + Managed Database (or local Docker)
 Claude Desktop - Installed and configured

Development Environment

 Python 3.10+ installed
 Docker & Docker Compose installed
 PostgreSQL client tools
 Git repository cloned


🚀 Implementation Steps
Step 1: Infrastructure Setup (Day 1)
1.1 Create Project Structure
bashcatalyst-trading-mcp/
├── services/
│   ├── news/
│   ├── scanner/
│   ├── pattern/
│   ├── technical/
│   ├── trading/
│   ├── reporting/
│   └── orchestration/
├── database/
│   ├── migrations/
│   └── seeds/
├── config/
├── logs/
├── data/
└── docker/
1.2 Database Setup
bash# Create PostgreSQL database
createdb catalyst_trading

# Create user
psql -c "CREATE USER catalyst_user WITH PASSWORD 'your_secure_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE catalyst_trading TO catalyst_user;"
1.3 Run Database Migrations
sql-- migrations/001_initial_schema.sql
-- Core tables for Phase 1 data collection

CREATE TABLE IF NOT EXISTS news_raw (
    id BIGSERIAL,
    news_id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(10),
    headline TEXT NOT NULL,
    source VARCHAR(200) NOT NULL,
    published_timestamp TIMESTAMPTZ NOT NULL,
    content_snippet TEXT,
    sentiment_score DECIMAL(3,2),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_market_data (
    scan_id VARCHAR(100),
    symbol VARCHAR(10),
    scan_timestamp TIMESTAMPTZ,
    price DECIMAL(10,2),
    volume BIGINT,
    relative_volume DECIMAL(10,2),
    price_change_pct DECIMAL(10,2),
    rsi_14 DECIMAL(5,2),
    has_news BOOLEAN,
    news_count INTEGER,
    catalyst_score DECIMAL(10,2),
    scan_rank INTEGER,
    selected_for_trading BOOLEAN,
    PRIMARY KEY (scan_id, symbol)
);

CREATE TABLE IF NOT EXISTS trading_signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    confidence DECIMAL(5,2) NOT NULL,
    entry_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    INDEX idx_pending_signals (executed_at) WHERE executed_at IS NULL
);

CREATE TABLE IF NOT EXISTS trade_records (
    trade_id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES trading_signals(id),
    symbol VARCHAR(10) NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    quantity INTEGER NOT NULL,
    side VARCHAR(10) NOT NULL,
    exit_timestamp TIMESTAMPTZ,
    exit_price DECIMAL(10,2),
    pnl_amount DECIMAL(10,2),
    metadata JSONB
);

-- Run migrations
psql catalyst_trading < migrations/001_initial_schema.sql
Step 2: Service Configuration (Day 1-2)
2.1 Create Master Configuration
bash# config/.env
# Database
DATABASE_URL=postgresql://catalyst_user:password@localhost:5432/catalyst_trading
REDIS_URL=redis://localhost:6379/0

# API Keys (get from respective services)
NEWS_API_KEY=your_newsapi_key_here
ALPACA_API_KEY=your_alpaca_paper_key
ALPACA_SECRET_KEY=your_alpaca_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Phase 1 Configuration - Conservative Settings
TRADING_ENABLED=true
MAX_POSITIONS=5
MAX_POSITION_SIZE=1000
MIN_SIGNAL_CONFIDENCE=60
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=4.0

# Scanning - Comprehensive Data Collection
INITIAL_UNIVERSE_SIZE=200
TOP_TRACKING_SIZE=100
CATALYST_FILTER_SIZE=50
FINAL_SELECTION_SIZE=5

# Service Ports
NEWS_SERVICE_PORT=5008
SCANNER_SERVICE_PORT=5001
PATTERN_SERVICE_PORT=5002
TECHNICAL_SERVICE_PORT=5003
TRADING_SERVICE_PORT=5005
REPORTING_SERVICE_PORT=5009
ORCHESTRATION_SERVICE_PORT=5000
2.2 Docker Compose Setup
yaml# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: catalyst_trading
      POSTGRES_USER: catalyst_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/migrations:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  news-service:
    build: 
      context: ./services/news
      dockerfile: Dockerfile
    ports:
      - "5008:5008"
    env_file: ./config/.env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs

  scanner-service:
    build: 
      context: ./services/scanner
      dockerfile: Dockerfile
    ports:
      - "5001:5001"
    env_file: ./config/.env
    depends_on:
      - postgres
      - redis
      - news-service
    volumes:
      - ./logs:/app/logs

  # ... other services

volumes:
  postgres_data:
  redis_data:
Step 3: Deploy MCP Services (Day 2)
3.1 Create Service Dockerfiles
dockerfile# services/news/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY news_service_mcp.py .
COPY database_utils.py .

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Run the service
CMD ["python", "news_service_mcp.py"]
3.2 Start Services in Order
bash#!/bin/bash
# scripts/start_services.sh

echo "Starting Catalyst Trading System MCP Services..."

# 1. Start infrastructure
docker-compose up -d postgres redis
echo "Waiting for database..."
sleep 10

# 2. Start data collection services
docker-compose up -d news-service
sleep 5

docker-compose up -d scanner-service
sleep 5

# 3. Start analysis services
docker-compose up -d pattern-service technical-service
sleep 5

# 4. Start execution services
docker-compose up -d trading-service
sleep 5

# 5. Start reporting and orchestration
docker-compose up -d reporting-service orchestration-service

echo "All services started. Checking health..."
Step 4: Configure Claude Desktop (Day 2)
4.1 MCP Configuration
json// ~/.claude/config.json
{
  "mcpServers": {
    "catalyst-orchestration": {
      "command": "python",
      "args": ["/path/to/catalyst/services/orchestration/orchestration_service_mcp.py"],
      "transport": "stdio",
      "env": {
        "DATABASE_URL": "postgresql://catalyst_user:password@localhost:5432/catalyst_trading",
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
4.2 Test Claude Connection
You: "Hey Claude, can you check if the Catalyst Trading System is running?"

Claude: [Should respond with system status after querying health endpoints]
Step 5: Verify Data Collection (Day 3)
5.1 Manual Verification Script
python# scripts/verify_data_collection.py
import psycopg2
from datetime import datetime, timedelta

def verify_data_collection():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    # Check news collection
    cur.execute("""
        SELECT COUNT(*), COUNT(DISTINCT symbol) 
        FROM news_raw 
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)
    news_count, symbol_count = cur.fetchone()
    print(f"✓ News collected: {news_count} articles for {symbol_count} symbols")
    
    # Check market data collection
    cur.execute("""
        SELECT COUNT(DISTINCT scan_id), COUNT(*), COUNT(DISTINCT symbol)
        FROM scan_market_data
        WHERE scan_timestamp > NOW() - INTERVAL '1 hour'
    """)
    scans, records, symbols = cur.fetchone()
    print(f"✓ Market scans: {scans} scans, {records} records, {symbols} unique symbols")
    
    # Check signal generation
    cur.execute("""
        SELECT COUNT(*) 
        FROM trading_signals 
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)
    signals = cur.fetchone()[0]
    print(f"✓ Signals generated: {signals}")
    
    conn.close()

if __name__ == "__main__":
    verify_data_collection()
5.2 Run Collection Test with Claude
You: "Claude, run a market scan and show me what data we're collecting"

Claude: [Executes scan and reports on data collection metrics]
Step 6: Initialize Trading Loop (Day 3-4)
6.1 Configure Trading Schedule
python# config/trading_schedule.py
TRADING_SCHEDULE = {
    'pre_market': {
        'start': '04:00',
        'end': '09:30',
        'scan_frequency': 300,  # 5 minutes
        'mode': 'aggressive'
    },
    'market_hours': {
        'start': '09:30',
        'end': '16:00',
        'scan_frequency': 900,  # 15 minutes
        'mode': 'normal'
    },
    'after_hours': {
        'start': '16:00',
        'end': '20:00',
        'scan_frequency': 1800,  # 30 minutes
        'mode': 'light'
    }
}
6.2 Start Automated Trading
You: "Claude, start the automated trading cycle for today"

Claude: "I'll start the trading cycle. Based on the current time, we're in [market phase]. 
I'll run scans every [X] minutes and execute signals with confidence above 60%."
Step 7: Monitor Data Growth (Day 4-5)
7.1 Data Collection Dashboard Query
sql-- scripts/data_collection_metrics.sql
-- Run daily to track Phase 1 progress

-- Overall metrics
SELECT 
    'Total Unique Symbols' as metric,
    COUNT(DISTINCT symbol) as value
FROM (
    SELECT symbol FROM news_raw
    UNION
    SELECT symbol FROM scan_market_data
) t;

-- Daily collection rates
SELECT 
    DATE(scan_timestamp) as date,
    COUNT(DISTINCT scan_id) as scans,
    COUNT(DISTINCT symbol) as unique_symbols,
    COUNT(*) as total_records
FROM scan_market_data
GROUP BY DATE(scan_timestamp)
ORDER BY date DESC
LIMIT 7;

-- Trading activity
SELECT 
    DATE(created_at) as date,
    COUNT(*) as signals_generated,
    SUM(CASE WHEN executed_at IS NOT NULL THEN 1 ELSE 0 END) as signals_executed,
    AVG(confidence) as avg_confidence
FROM trading_signals
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 7;

🏥 Health Monitoring Tasks
Daily Health Checks
Morning Checklist (Pre-Market)
bash# scripts/morning_health_check.sh
#!/bin/bash

echo "=== Catalyst Trading System Morning Health Check ==="
echo "Time: $(date)"

# 1. Check all services are running
for service in news scanner pattern technical trading reporting; do
    response=$(curl -s http://localhost:${service_port}/health)
    if [[ $? -eq 0 ]]; then
        echo "✓ $service service: HEALTHY"
    else
        echo "✗ $service service: DOWN"
    fi
done

# 2. Check database connections
psql $DATABASE_URL -c "SELECT 'Database connection: OK';" 2>/dev/null || echo "✗ Database: FAILED"

# 3. Check Redis
redis-cli ping > /dev/null && echo "✓ Redis: HEALTHY" || echo "✗ Redis: DOWN"

# 4. Check Alpaca connection
python scripts/check_alpaca.py

# 5. Check data freshness
psql $DATABASE_URL -f scripts/data_freshness_check.sql
Continuous Monitoring
python# monitoring/health_monitor.py
import asyncio
import aiohttp
from datetime import datetime

class HealthMonitor:
    def __init__(self):
        self.services = {
            'news': 'http://localhost:5008/health',
            'scanner': 'http://localhost:5001/health',
            'pattern': 'http://localhost:5002/health',
            'technical': 'http://localhost:5003/health',
            'trading': 'http://localhost:5005/health',
            'reporting': 'http://localhost:5009/health'
        }
        
    async def check_service(self, name, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        return f"✓ {name}: OK"
                    else:
                        return f"✗ {name}: Status {response.status}"
        except Exception as e:
            return f"✗ {name}: {str(e)}"
    
    async def monitor_loop(self):
        while True:
            print(f"\n=== Health Check {datetime.now().strftime('%H:%M:%S')} ===")
            tasks = [self.check_service(name, url) for name, url in self.services.items()]
            results = await asyncio.gather(*tasks)
            for result in results:
                print(result)
            await asyncio.sleep(300)  # Check every 5 minutes

monitor = HealthMonitor()
asyncio.run(monitor.monitor_loop())
Critical Alerts Setup
yaml# config/alerts.yml
alerts:
  - name: "No Market Data"
    condition: "No scans in 30 minutes during market hours"
    query: |
      SELECT COUNT(*) FROM scan_market_data 
      WHERE scan_timestamp > NOW() - INTERVAL '30 minutes'
    threshold: 0
    action: "Restart scanner service"
    
  - name: "News Feed Down"
    condition: "No news in 1 hour"
    query: |
      SELECT COUNT(*) FROM news_raw 
      WHERE created_at > NOW() - INTERVAL '1 hour'
    threshold: 0
    action: "Check API keys and restart news service"
    
  - name: "Trading Halted"
    condition: "Trading enabled but no executions"
    query: |
      SELECT COUNT(*) FROM trade_records 
      WHERE entry_timestamp > NOW() - INTERVAL '2 hours'
    threshold: 0
    action: "Check Alpaca connection and signal generation"

📊 Phase 1 Success Metrics
Week 1 Targets

 All services operational
 100+ unique symbols tracked daily
 5+ trades executed daily
 <5% service downtime

Month 1 Targets

 1,000+ unique symbols in database
 50,000+ market data records
 100+ completed trades
 55%+ win rate achieved

Data Quality Checks
sql-- Weekly data quality report
-- scripts/weekly_data_quality.sql

-- Check for data gaps
WITH hourly_scans AS (
    SELECT 
        DATE_TRUNC('hour', scan_timestamp) as hour,
        COUNT(DISTINCT scan_id) as scan_count
    FROM scan_market_data
    WHERE scan_timestamp > NOW() - INTERVAL '7 days'
    GROUP BY 1
)
SELECT 
    hour,
    scan_count,
    CASE 
        WHEN scan_count = 0 THEN 'DATA GAP!'
        WHEN scan_count < 4 THEN 'Low activity'
        ELSE 'Normal'
    END as status
FROM hourly_scans
WHERE EXTRACT(hour FROM hour) BETWEEN 9 AND 16
ORDER BY hour DESC;

🚨 Troubleshooting Common Issues
Issue: Services Won't Start
bash# Check logs
docker-compose logs news-service
docker-compose logs scanner-service

# Restart specific service
docker-compose restart news-service

# Full restart
docker-compose down
docker-compose up -d
Issue: No Data Collection
python# scripts/debug_data_collection.py
def debug_collection():
    # 1. Test news API
    response = requests.get(f"{NEWS_API_URL}/everything", 
                          params={"q": "stock market", "apiKey": API_KEY})
    print(f"News API: {response.status_code}")
    
    # 2. Test Alpaca connection
    api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_URL)
    account = api.get_account()
    print(f"Alpaca: {account.status}")
    
    # 3. Check service connectivity
    for service in ['news', 'scanner', 'pattern']:
        try:
            r = requests.get(f"http://localhost:{ports[service]}/health")
            print(f"{service}: {r.json()['status']}")
        except:
            print(f"{service}: UNREACHABLE")

✅ Phase 1 Completion Checklist
Week 1

 Infrastructure deployed
 All services running
 Claude connected
 First automated scan completed
 First paper trade executed

Week 2-4

 500+ unique symbols tracked
 Daily trading active
 Performance tracking enabled
 Data quality verified
 Backup procedures tested

Month 1 Review

 1,000+ symbols in database
 55% win rate trending
 System stability proven
 Ready for Phase 2 (ML Integration)


📞 Support Contacts

Technical Issues: Check logs in /app/logs/
API Issues: Verify keys in .env
Database Issues: Check connection string
Claude Issues: Verify MCP configuration

Remember: Phase 1 is about data collection and foundation. Don't optimize for profits yet - focus on gathering comprehensive, quality data for future ML training.