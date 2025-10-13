# Catalyst Trading System - Docker Deployment Guide

**Version**: 5.1.0  
**Last Updated**: 2025-10-13  
**Purpose**: Complete production deployment using Docker Compose

---

## 📋 Prerequisites

1. **Docker & Docker Compose** installed
   ```bash
   docker --version  # Should be 20.10+
   docker-compose --version  # Should be 1.29+
   ```

2. **API Keys** (optional for testing, required for production)
   - Alpha Vantage (market data)
   - Benzinga (news)
   - Alpaca (trading - use paper trading!)

3. **System Requirements**
   - 4GB RAM minimum (8GB recommended)
   - 10GB disk space
   - Linux/macOS/Windows with WSL2

---

## 🚀 Quick Start (5 minutes)

### Step 1: Clone and Setup Environment

```bash
# Navigate to project root
cd ~/catalyst-trading-mcp

# Copy environment template
cp .env.example .env

# Edit .env with your API keys (or leave blank for testing)
nano .env
```

### Step 2: Build All Services

```bash
# Build all Docker images (takes 5-10 minutes first time)
docker-compose build

# Verify images built
docker images | grep catalyst
```

### Step 3: Start the System

```bash
# Start all services in background
docker-compose up -d

# Watch logs (Ctrl+C to exit, services keep running)
docker-compose logs -f

# Or watch specific service
docker-compose logs -f news
```

### Step 4: Verify Health

```bash
# Check all services are running
docker-compose ps

# Health check all services
curl http://localhost:5000/health  # Orchestration (may not respond if MCP)
curl http://localhost:5001/health  # Scanner
curl http://localhost:5002/health  # Pattern
curl http://localhost:5003/health  # Technical
curl http://localhost:5004/health  # Risk Manager
curl http://localhost:5005/health  # Trading
curl http://localhost:5008/health  # News
curl http://localhost:5009/health  # Reporting

# All should return: {"status": "healthy", ...}
```

---

## 📊 Service Architecture

```
Port 5000: Orchestration (MCP) - Claude Desktop interface
Port 5001: Scanner - Market scanning (100 → 5 candidates)
Port 5002: Pattern - Chart pattern detection
Port 5003: Technical - Indicator calculations
Port 5004: Risk Manager - Trade validation
Port 5005: Trading - Order execution
Port 5008: News - Catalyst detection & sentiment
Port 5009: Reporting - Analytics & performance
Port 5432: PostgreSQL - Database
```

---

## 🛠️ Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f scanner

# Last 50 lines
docker-compose logs --tail=50 news

# Filter by error level
docker-compose logs scanner | grep ERROR

# Save logs to file
docker-compose logs --no-color > system-logs.txt
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart news

# Restart after code changes
docker-compose down
docker-compose build news
docker-compose up -d
```

### Database Operations

```bash
# Access PostgreSQL directly
docker exec -it catalyst-postgres psql -U catalyst -d catalyst_trading

# Run SQL query
docker exec -it catalyst-postgres psql -U catalyst -d catalyst_trading -c "SELECT COUNT(*) FROM securities;"

# Backup database
docker exec catalyst-postgres pg_dump -U catalyst catalyst_trading > backup-$(date +%Y%m%d).sql

# Restore database
cat backup-20251013.sql | docker exec -i catalyst-postgres psql -U catalyst catalyst_trading
```

### Monitor Resources

```bash
# Resource usage
docker stats

# Disk usage
docker system df

# Service details
docker-compose ps -a
```

---

## 🔧 Troubleshooting

### Problem: Service Won't Start

```bash
# Check logs
docker-compose logs service-name

# Check if port is already in use
sudo lsof -i :5008

# Rebuild service
docker-compose build --no-cache service-name
docker-compose up -d service-name
```

### Problem: Database Connection Errors

```bash
# Check postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Verify database exists
docker exec catalyst-postgres psql -U catalyst -l

# Test connection
docker exec catalyst-postgres psql -U catalyst -d catalyst_trading -c "SELECT 1;"
```

### Problem: "Price impact" Errors in News Service

This was fixed in v5.3.1. Ensure you have the latest version:

```bash
# Check news service version
curl http://localhost:5008/health | jq '.version'
# Should show: "5.3.1" or higher

# If not, rebuild
docker-compose build news
docker-compose up -d news
```

### Problem: Out of Memory

```bash
# Stop non-essential services temporarily
docker-compose stop reporting
docker-compose stop pattern

# Or increase Docker memory limit
# Docker Desktop: Settings → Resources → Memory → 8GB
```

---

## 📦 Production Deployment

### Step 1: Security Hardening

```bash
# 1. Change database password in docker-compose.yml
# 2. Use secrets management (Docker Swarm secrets or Kubernetes)
# 3. Enable HTTPS with reverse proxy (nginx)
# 4. Set up firewall rules
# 5. Use non-root users in containers
```

### Step 2: Enable Monitoring

```bash
# Add Prometheus + Grafana
# Add this to docker-compose.yml:

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - catalyst-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    networks:
      - catalyst-network
```

### Step 3: Automated Backups

```bash
# Add to crontab
crontab -e

# Daily database backup at 2 AM
0 2 * * * cd ~/catalyst-trading-mcp && docker exec catalyst-postgres pg_dump -U catalyst catalyst_trading > backups/db-$(date +\%Y\%m\%d).sql
```

### Step 4: Log Rotation

Docker already handles this via logging config in docker-compose.yml:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## 🧪 Testing

### Run Health Checks

```bash
# Quick health check script
for port in 5001 5002 5003 5004 5005 5008 5009; do
  echo "Checking port $port..."
  curl -s http://localhost:$port/health | jq '.status'
done
```

### Test Scanner Endpoint

```bash
# Run a scan
curl -X POST http://localhost:5001/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"hours_back": 1}' | jq
```

### Test News Fetch

```bash
# Fetch news for AAPL
curl -X POST http://localhost:5008/api/v1/news/fetch \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "hours_back": 24}' | jq
```

### Test Technical Indicators

```bash
# Calculate indicators for AAPL
curl -X POST http://localhost:5003/api/v1/indicators/calculate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "timeframe": "5min"}' | jq
```

---

## 🗂️ File Structure

```
catalyst-trading-mcp/
├── docker-compose.yml          # Main orchestration file
├── .env                         # Environment variables (not in git)
├── .env.example                 # Template for .env
├── services/
│   ├── orchestration/
│   │   ├── Dockerfile
│   │   ├── orchestration-service.py  (v5.1.0)
│   │   └── requirements.txt
│   ├── scanner/
│   │   ├── Dockerfile
│   │   ├── scanner-service.py        (v5.4.0)
│   │   └── requirements.txt
│   ├── news/
│   │   ├── Dockerfile
│   │   ├── news-service.py           (v5.3.1)
│   │   └── requirements.txt
│   ├── technical/
│   │   ├── Dockerfile
│   │   ├── technical-service.py      (v5.1.0)
│   │   └── requirements.txt
│   ├── pattern/
│   │   ├── Dockerfile
│   │   ├── pattern-service.py        (v5.1.0)
│   │   └── requirements.txt
│   ├── risk-manager/
│   │   ├── Dockerfile
│   │   ├── risk-manager-service.py   (v5.0.0)
│   │   └── requirements.txt
│   ├── trading/
│   │   ├── Dockerfile
│   │   ├── trading-service.py        (v5.0.1)
│   │   └── requirements.txt
│   └── reporting/
│       ├── Dockerfile
│       ├── reporting-service.py      (v5.1.0)
│       └── requirements.txt
└── database/
    └── schema/
        └── normalized-database-schema-mcp-v50.sql
```

---

## 🎯 Deployment Checklist

Before deploying to production:

- [ ] All services show `"status": "healthy"`
- [ ] Database schema v5.0 deployed
- [ ] All API keys configured in .env
- [ ] Using paper trading (not live)
- [ ] Logs show no errors
- [ ] Health checks pass
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Docker logs rotation enabled
- [ ] Database backups automated
- [ ] Security hardening complete

---

## 📞 Support & Maintenance

### Daily Checks

```bash
# Morning routine
docker-compose ps              # All services running?
docker-compose logs --tail=50  # Any errors overnight?
docker system df               # Enough disk space?
```

### Weekly Maintenance

```bash
# Clean up unused resources
docker system prune -f

# Update images (if needed)
docker-compose pull
docker-compose up -d
```

### Emergency Shutdown

```bash
# Graceful shutdown
docker-compose down

# Force shutdown (if hung)
docker-compose kill
docker-compose down -v  # Also removes volumes (BE CAREFUL!)
```

---

## 🎉 Success Criteria

Your system is ready when:

1. ✅ All 8 services return `"status": "healthy"`
2. ✅ Database has tables: `securities`, `trading_history`, `news_sentiment`, etc.
3. ✅ No errors in logs (check `docker-compose logs`)
4. ✅ Scanner can find candidates
5. ✅ News service background job runs without SQL errors
6. ✅ Trading service can create cycles (paper trading)

---

**Next Steps**: Connect Claude Desktop via MCP to orchestration service on port 5000!

*DevGenius hat staying on for deployment!* 🎩
