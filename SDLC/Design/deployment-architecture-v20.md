# Deployment Architecture Design v2.0

**Name of Application**: Catalyst Trading System  
**Name of file**: deployment-architecture-v20.md  
**Version**: 2.0.0  
**Last Updated**: 2025-10-18  
**Phase**: DESIGN  
**Purpose**: Single DigitalOcean Droplet deployment with Docker Compose

---

## REVISION HISTORY

**v2.0.0 (2025-10-18)** - Single Droplet Architecture
- ✅ Removed all App Platform references
- ✅ Single Droplet deployment model only
- ✅ Docker Compose orchestration
- ✅ DigitalOcean Managed Database (connection string)
- ✅ Local Redis container (simplified)
- ✅ No AWS - Pure DigitalOcean
- ✅ Cost optimized: ~$63/month

---

## Document Control

**Status**: ✅ **APPROVED FOR IMPLEMENTATION**  
**Classification**: PRODUCTION DESIGN  
**Derived From**:
- Architecture v5.0 (9-service architecture)
- Database Schema v5.0 (PostgreSQL requirements)
- Docker Compose v5.2.0 (current working config)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Infrastructure Overview](#2-infrastructure-overview)
3. [Network Architecture](#3-network-architecture)
4. [Service Deployment](#4-service-deployment)
5. [Data Layer](#5-data-layer)
6. [Security Architecture](#6-security-architecture)
7. [Monitoring & Health](#7-monitoring--health)
8. [Disaster Recovery](#8-disaster-recovery)
9. [Deployment Procedures](#9-deployment-procedures)
10. [Cost Analysis](#10-cost-analysis)

---

## 1. Executive Summary

### 1.1 Deployment Model

**Infrastructure**: Single DigitalOcean Droplet  
**Orchestration**: Docker Compose  
**Cost**: ~$63/month  
**Complexity**: Low  
**Best For**: Single-user trading system

### 1.2 Architecture Decision

```
✅ SELECTED: Single Droplet + Docker Compose
- One DigitalOcean Droplet (4vCPU, 8GB RAM)
- All 9 services in Docker containers on same machine
- DigitalOcean Managed PostgreSQL (via connection string)
- Local Redis container
- Nginx reverse proxy for Claude Desktop MCP access
```

**Why This Architecture?**
- ✅ **Cost Effective**: $63/mo vs $114/mo (App Platform)
- ✅ **Simple**: One machine to manage
- ✅ **Flexible**: Full control over containers
- ✅ **Proven**: Docker Compose is battle-tested
- ✅ **Fast Development**: Easy to iterate and debug

**Trade-offs Accepted**:
- ⚠️ Single point of failure (acceptable for single-user)
- ⚠️ Manual scaling (not needed for 1 user)
- ⚠️ More hands-on management than App Platform

---

## 2. Infrastructure Overview

### 2.1 Physical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET (Public)                        │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS (443)
                         │ SSH (22)
            ┌────────────▼────────────┐
            │ DigitalOcean Droplet    │
            │ sfo3 region             │
            │ 4vCPU, 8GB RAM, 160GB   │
            │ Ubuntu 22.04 LTS        │
            │                         │
            │  ┌──────────────────┐  │
            │  │ Nginx            │  │
            │  │ Port 443         │  │
            │  │ - SSL/TLS        │  │
            │  │ - API Key Auth   │  │
            │  └────────┬─────────┘  │
            │           │             │
            │  ┌────────▼─────────┐  │
            │  │ Docker Bridge    │  │
            │  │ 172.18.0.0/16    │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Redis        │ │  │
            │  │ │ (6379)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │Orchestration │ │  │
            │  │ │(5000) MCP    │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Scanner      │ │  │
            │  │ │ (5001)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Pattern      │ │  │
            │  │ │ (5002)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Technical    │ │  │
            │  │ │ (5003)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Risk Manager │ │  │
            │  │ │ (5004)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Trading      │ │  │
            │  │ │ (5005)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ News         │ │  │
            │  │ │ (5008)       │ │  │
            │  │ └──────────────┘ │  │
            │  │                  │  │
            │  │ ┌──────────────┐ │  │
            │  │ │ Reporting    │ │  │
            │  │ │ (5009)       │ │  │
            │  │ └──────────────┘ │  │
            │  └──────────────────┘  │
            └─────────┬───────────────┘
                      │
                      │ Private Network
                      │ (Connection String)
            ┌─────────▼───────────┐
            │ DigitalOcean Cloud  │
            │                     │
            │  ┌───────────────┐ │
            │  │ PostgreSQL 15 │ │
            │  │ Managed DB    │ │
            │  │ 1vCPU, 1GB    │ │
            │  │ Port 25060    │ │
            │  └───────────────┘ │
            └─────────────────────┘
```

### 2.2 Component Inventory

| Component | Type | Location | Purpose |
|-----------|------|----------|---------|
| **Droplet** | Virtual Machine | DigitalOcean | Host all containers |
| **PostgreSQL** | Managed Database | DigitalOcean | Data persistence |
| **Redis** | Docker Container | Droplet | Caching |
| **Nginx** | System Service | Droplet | Reverse proxy + SSL |
| **Orchestration** | Docker Container | Droplet | MCP interface |
| **Scanner** | Docker Container | Droplet | Market scanning |
| **Pattern** | Docker Container | Droplet | Pattern detection |
| **Technical** | Docker Container | Droplet | Technical analysis |
| **Risk Manager** | Docker Container | Droplet | Risk validation |
| **Trading** | Docker Container | Droplet | Order execution |
| **News** | Docker Container | Droplet | News intelligence |
| **Reporting** | Docker Container | Droplet | Analytics |

---

## 3. Network Architecture

### 3.1 Network Topology

```
┌──────────────────────────────────────────────────┐
│ PUBLIC ZONE                                      │
│ 0.0.0.0/0                                        │
│                                                  │
│  Your Computer ────┐                            │
│  Claude Desktop    │                            │
└────────────────────┼──────────────────────────────┘
                     │ HTTPS (443)
                     │ SSH (22)
┌────────────────────▼──────────────────────────────┐
│ FIREWALL ZONE                                    │
│ UFW (Uncomplicated Firewall)                    │
│                                                  │
│  Rules:                                          │
│  ✅ Allow 443/tcp (HTTPS)                       │
│  ✅ Allow 22/tcp (SSH - YOUR_IP only)           │
│  ❌ Block everything else                       │
└────────────────────┬──────────────────────────────┘
                     │
┌────────────────────▼──────────────────────────────┐
│ HOST ZONE                                        │
│ 10.10.0.0/24 (Droplet)                           │
│                                                  │
│  ┌─────────────┐                                │
│  │ Nginx       │                                │
│  │ 443 → 5000  │                                │
│  └──────┬──────┘                                │
│         │                                        │
│  ┌──────▼──────────────────────────────────┐   │
│  │ Docker Bridge Network                   │   │
│  │ 172.18.0.0/16                            │   │
│  │                                          │   │
│  │  Services communicate via:              │   │
│  │  - Container names (DNS)                │   │
│  │  - Internal ports (5000-5009)           │   │
│  │  - No external exposure                 │   │
│  └──────────────────────────────────────────┘   │
└──────────────────┬───────────────────────────────┘
                   │
                   │ Encrypted Connection
                   │ (TLS, Connection String)
┌──────────────────▼───────────────────────────────┐
│ DATABASE ZONE (DigitalOcean Private Network)    │
│                                                  │
│  ┌────────────────────────────────────┐         │
│  │ Managed PostgreSQL                 │         │
│  │ 10.10.1.0/24                        │         │
│  │ Port 25060 (TLS Required)          │         │
│  │                                     │         │
│  │ Access: Via connection string only │         │
│  │ No direct internet access          │         │
│  └────────────────────────────────────┘         │
└──────────────────────────────────────────────────┘
```

### 3.2 Port Configuration

**Public Ports (Internet-facing)**:
```
443/tcp  → Nginx → Orchestration (5000)
22/tcp   → SSH (Admin access only, IP restricted)
```

**Internal Ports (Docker network only)**:
```
5000  → Orchestration (MCP)
5001  → Scanner
5002  → Pattern
5003  → Technical
5004  → Risk Manager
5005  → Trading
5008  → News
5009  → Reporting
6379  → Redis
```

**Database Port (DigitalOcean managed)**:
```
25060 → PostgreSQL (TLS required, connection string)
```

### 3.3 Firewall Rules

**UFW Configuration**:
```bash
# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (YOUR IP ONLY - replace with actual IP)
ufw allow from YOUR_IP_ADDRESS to any port 22 proto tcp

# Allow HTTPS
ufw allow 443/tcp

# Enable firewall
ufw enable
```

---

## 4. Service Deployment

### 4.1 Docker Compose Configuration

**File**: `docker-compose.yml` (v5.2.0)

**Service Start Order**:
```
1. Redis         (10s startup)
2. News          (wait for Redis)
3. Orchestration (wait for Redis)
4. Scanner       (wait for News)
5. Pattern       (wait for Redis)
6. Technical     (wait for Redis)
7. Risk Manager  (wait for Redis)
8. Trading       (wait for Scanner, Pattern, Technical)
9. Reporting     (wait for Trading)
```

### 4.2 Resource Allocation

**Per Service Resources** (Docker limits):
```yaml
orchestration:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
      reservations:
        cpus: '0.25'
        memory: 256M
```

**Total Resource Usage** (Expected):
| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| Orchestration | 0.5 | 512MB | 1GB |
| Scanner | 0.5 | 512MB | 1GB |
| Pattern | 0.5 | 512MB | 1GB |
| Technical | 0.5 | 512MB | 1GB |
| Risk Manager | 0.5 | 512MB | 1GB |
| Trading | 0.5 | 512MB | 1GB |
| News | 0.5 | 512MB | 1GB |
| Reporting | 0.5 | 512MB | 1GB |
| Redis | 0.25 | 256MB | 1GB |
| Nginx | 0.25 | 128MB | 100MB |
| System | 0.5 | 512MB | 10GB |
| **TOTAL** | **5.0** | **6GB** | **20GB** |

**Droplet Sizing**:
- **Minimum**: 4vCPU, 8GB RAM (leaves 25% headroom)
- **Recommended**: 4vCPU, 8GB RAM, 160GB SSD
- **Cost**: $48/month

### 4.3 Health Checks

**Every Service Exposes**:
```
GET /health

Response (200 OK):
{
  "status": "healthy",
  "service": "scanner",
  "version": "5.3.0",
  "schema": "v5.0 normalized",
  "timestamp": "2025-10-18T12:00:00Z",
  "database": "connected",
  "redis": "connected"
}
```

**Docker Health Check**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

**System Health Monitor** (`scripts/health-check.sh`):
```bash
#!/bin/bash
services=(
    "orchestration:5000"
    "scanner:5001"
    "pattern:5002"
    "technical:5003"
    "risk-manager:5004"
    "trading:5005"
    "news:5008"
    "reporting:5009"
    "redis:6379"
)

for svc in "${services[@]}"; do
    name="${svc%%:*}"
    port="${svc##*:}"
    
    if [ "$name" = "redis" ]; then
        if docker exec catalyst-redis redis-cli ping | grep -q PONG; then
            echo "✓ $name: healthy"
        else
            echo "✗ $name: UNHEALTHY"
        fi
    else
        if curl -sf "http://localhost:$port/health" > /dev/null; then
            echo "✓ $name: healthy"
        else
            echo "✗ $name: UNHEALTHY"
        fi
    fi
done
```

---

## 5. Data Layer

### 5.1 PostgreSQL (Managed Database)

**Provider**: DigitalOcean Managed Database  
**Plan**: Basic (1vCPU, 1GB RAM, 10GB SSD)  
**Version**: PostgreSQL 15  
**Cost**: $15/month

**Features**:
- ✅ Automated daily backups (7-day retention)
- ✅ Point-in-time recovery
- ✅ Automatic failover (99.95% SLA)
- ✅ Automated security updates
- ✅ Connection pooling (100 connections)
- ✅ TLS/SSL required

**Connection Method**:
```bash
# In .env file
DATABASE_URL=postgresql://user:password@host:25060/catalyst?sslmode=require

# Services connect via asyncpg
pool = await asyncpg.create_pool(
    os.getenv("DATABASE_URL"),
    min_size=2,
    max_size=10,
    command_timeout=30
)
```

**Why Managed vs Self-Hosted?**
| Feature | Self-Hosted | Managed | Winner |
|---------|-------------|---------|--------|
| Cost | $0 (uses Droplet) | +$15/mo | Self-Hosted |
| Backups | Manual | Automatic | Managed ✅ |
| Updates | Manual | Automatic | Managed ✅ |
| Monitoring | Manual | Built-in | Managed ✅ |
| Failover | None | Automatic | Managed ✅ |
| CPU Impact | Uses Droplet CPU | Separate | Managed ✅ |
| **Verdict** | | | **Managed** ✅ |

**Decision**: Use Managed ($15/mo for peace of mind)

### 5.2 Redis (Docker Container)

**Deployment**: Docker container on Droplet  
**Image**: redis:7-alpine  
**Memory**: 256MB limit  
**Persistence**: Append-only file (AOF)  
**Cost**: $0 (uses Droplet resources)

**Configuration**:
```yaml
redis:
  image: redis:7-alpine
  container_name: catalyst-redis
  command: >
    redis-server
    --appendonly yes
    --maxmemory 256mb
    --maxmemory-policy allkeys-lru
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
```

**Usage Patterns**:
- Market data caching (TTL: 60s)
- Technical indicator caching (TTL: 300s)
- Real-time position updates (pub/sub)
- Rate limiting

**Why Not Managed Redis?**
- Managed Redis: +$15/month
- Cache can be rebuilt if lost (not critical data)
- 256MB sufficient for single-user system
- **Decision**: Use local Redis container ✅

---

## 6. Security Architecture

### 6.1 Security Layers

```
Layer 1: Network Security
├─ UFW Firewall (block all except 443, 22)
├─ SSH key-only (no passwords)
└─ IP whitelist for SSH

Layer 2: Transport Security
├─ TLS 1.3 (Let's Encrypt)
├─ Certificate auto-renewal
└─ HSTS enabled

Layer 3: Application Security
├─ API key authentication (Nginx)
├─ Rate limiting (100 req/min)
└─ Request validation

Layer 4: Service Security
├─ Container isolation
├─ No root processes
└─ Read-only file systems

Layer 5: Data Security
├─ Database TLS required
├─ Secrets in .env (chmod 600)
└─ No secrets in code/git
```

### 6.2 Nginx Configuration

**File**: `/etc/nginx/sites-available/catalyst-mcp`

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.3;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # MCP Endpoint
    location /mcp {
        # API Key Authentication
        set $api_key "YOUR_SECURE_API_KEY";
        if ($http_authorization != "Bearer $api_key") {
            return 401 '{"error": "Unauthorized"}';
        }

        # Rate Limiting
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;

        # Proxy to Orchestration
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Health Check (no auth)
    location /health {
        proxy_pass http://localhost:5000/health;
    }
}
```

### 6.3 Secrets Management

**Environment Variables** (`.env` file):
```bash
# Database (from DigitalOcean)
DATABASE_URL=postgresql://user:pass@host:25060/catalyst?sslmode=require

# API Keys (user-provided)
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
NEWS_API_KEY=...
ALPHA_VANTAGE_KEY=...

# MCP Authentication
MCP_API_KEY=catalyst_$(openssl rand -hex 16)
```

**Security Practices**:
```bash
# Create .env
cp .env.example .env
chmod 600 .env

# Add to .gitignore
echo ".env" >> .gitignore

# Never commit secrets
git add .gitignore
git commit -m "Add .env to .gitignore"
```

---

## 7. Monitoring & Health

### 7.1 Monitoring Stack

**Built-in Monitoring**:
- ✅ Docker health checks (every 30s)
- ✅ Service `/health` endpoints
- ✅ Nginx access/error logs
- ✅ DigitalOcean Droplet monitoring (CPU, RAM, disk)

**Monitoring Script** (`scripts/monitor.sh`):
```bash
#!/bin/bash
# Continuous monitoring with alerts

while true; do
    # Check services
    ./scripts/health-check.sh
    
    # Check resources
    CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    MEM=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
    DISK=$(df -h / | awk 'NR==2 {print $5}' | cut -d'%' -f1)
    
    echo "CPU: ${CPU}% | MEM: ${MEM}% | DISK: ${DISK}%"
    
    # Alert if critical
    if (( $(echo "$CPU > 90" | bc -l) )); then
        echo "ALERT: High CPU usage!"
    fi
    
    if (( $(echo "$MEM > 90" | bc -l) )); then
        echo "ALERT: High memory usage!"
    fi
    
    if [ "$DISK" -gt 90 ]; then
        echo "ALERT: High disk usage!"
    fi
    
    sleep 60
done
```

### 7.2 Logging

**Log Configuration**:
```yaml
# docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "5"
```

**Log Locations**:
```
/var/lib/docker/containers/*/  → Container logs (Docker)
/var/log/nginx/                → Nginx logs
./logs/                        → Application logs (mounted)
```

**Log Rotation**:
```bash
# /etc/logrotate.d/catalyst
/var/log/nginx/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload nginx
    endscript
}
```

---

## 8. Disaster Recovery

### 8.1 Backup Strategy

**Database Backups** (Automatic):
- ✅ DigitalOcean manages daily backups
- ✅ 7-day retention
- ✅ Point-in-time recovery available
- ✅ No manual intervention needed

**Droplet Backups** (Manual):
```bash
# Create snapshot (via DigitalOcean API or dashboard)
doctl compute droplet-action snapshot DROPLET_ID --snapshot-name "catalyst-$(date +%Y%m%d)"

# Automated weekly snapshots (crontab)
0 2 * * 0 /root/scripts/backup-droplet.sh
```

**Configuration Backup**:
```bash
#!/bin/bash
# scripts/backup-config.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/config_$DATE"

mkdir -p $BACKUP_DIR

# Backup configs (excluding secrets)
cp docker-compose.yml $BACKUP_DIR/
cp nginx.conf $BACKUP_DIR/
cp -r scripts/ $BACKUP_DIR/

# Create archive
tar -czf backups/config_$DATE.tar.gz -C backups config_$DATE/
rm -rf $BACKUP_DIR

echo "Configuration backup: config_$DATE.tar.gz"
```

### 8.2 Recovery Procedures

**Service Failure** (Single container):
```bash
# Auto-restart (Docker handles this)
# Manual restart if needed:
docker-compose restart scanner
```

**Complete System Failure**:
```bash
# 1. Provision new Droplet (5 min)
doctl compute droplet create catalyst-trading \
    --region sfo3 \
    --size s-4vcpu-8gb \
    --image ubuntu-22-04-x64

# 2. Install Docker (5 min)
curl -fsSL https://get.docker.com | sh
apt install docker-compose

# 3. Restore code (2 min)
git clone https://github.com/your-org/catalyst-trading.git
cd catalyst-trading

# 4. Restore .env (1 min)
cp backups/.env.production .env

# 5. Start services (5 min)
docker-compose up -d

# Total: ~20 minutes
```

**Database Failure**:
- DigitalOcean handles automatic failover
- If catastrophic: Restore from backup via dashboard
- RPO: <24 hours (daily backups)
- RTO: <2 hours

---

## 9. Deployment Procedures

### 9.1 Initial Deployment

**Prerequisites**:
```bash
- DigitalOcean account
- API keys (Alpaca, news sources)
- Domain name (optional, can use IP)
- SSH key pair
```

**Step 1: Create Managed Database** (~10 min):
```bash
# Via DigitalOcean dashboard:
1. Create → Databases
2. Choose PostgreSQL 15
3. Select Basic plan (1vCPU, 1GB)
4. Choose region (sfo3)
5. Copy connection string
```

**Step 2: Create Droplet** (~5 min):
```bash
doctl compute droplet create catalyst-trading \
    --region sfo3 \
    --size s-4vcpu-8gb \
    --image ubuntu-22-04-x64 \
    --ssh-keys YOUR_SSH_KEY_ID
```

**Step 3: Configure Droplet** (~20 min):
```bash
# SSH into droplet
ssh root@droplet-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install docker-compose -y

# Install Nginx
apt install nginx certbot python3-certbot-nginx -y

# Configure firewall
ufw allow 22/tcp
ufw allow 443/tcp
ufw enable
```

**Step 4: Deploy Application** (~15 min):
```bash
# Clone repository
git clone https://github.com/your-org/catalyst-trading.git
cd catalyst-trading

# Configure environment
cp .env.example .env
nano .env  # Add DATABASE_URL, API keys
chmod 600 .env

# Deploy database schema
psql $DATABASE_URL -f normalized-database-schema-mcp-v50.sql

# Start services
docker-compose up -d

# Verify
./scripts/health-check.sh
```

**Step 5: Configure Nginx** (~10 min):
```bash
# Copy config
cp deployment/nginx.conf /etc/nginx/sites-available/catalyst-mcp
ln -s /etc/nginx/sites-available/catalyst-mcp /etc/nginx/sites-enabled/

# Get SSL certificate
certbot --nginx -d your-domain.com

# Restart Nginx
systemctl restart nginx
```

**Total Initial Deployment**: ~60 minutes

### 9.2 Update Deployment

**Zero-downtime rolling update**:
```bash
#!/bin/bash
# scripts/deploy-update.sh

# Pull latest code
git pull origin main

# Rebuild changed services
docker-compose build

# Update services one by one
services=(
    "reporting" "news" "trading" 
    "risk-manager" "technical" "pattern" 
    "scanner" "orchestration"
)

for svc in "${services[@]}"; do
    echo "Updating $svc..."
    docker-compose up -d --no-deps --build $svc
    sleep 10
    
    if ./scripts/health-check-single.sh $svc; then
        echo "✓ $svc updated"
    else
        echo "✗ $svc failed - rolling back"
        docker-compose restart $svc
        exit 1
    fi
done

echo "✓ All services updated"
```

---

## 10. Cost Analysis

### 10.1 Monthly Costs

| Component | Spec | Monthly Cost |
|-----------|------|--------------|
| **Droplet** | 4vCPU, 8GB RAM, 160GB SSD | $48.00 |
| **Managed PostgreSQL** | 1vCPU, 1GB RAM, 10GB | $15.00 |
| **Redis** | Docker container (no cost) | $0.00 |
| **Bandwidth** | 5TB included | $0.00 |
| **Backups** | Database backups included | $0.00 |
| **SSL** | Let's Encrypt (free) | $0.00 |
| **Domain** | Optional | ~$1.00/mo |
| **TOTAL** | | **$63/month** |

### 10.2 Cost Comparison

| Deployment Model | Monthly Cost | Pros | Cons |
|------------------|--------------|------|------|
| **Single Droplet** (Current) | $63 | Simple, flexible, full control | Single point of failure |
| **App Platform** | $114 | Managed, scalable, HA | Higher cost, less control |
| **Self-Managed DB** | $48 | Cheapest | No backups, more maintenance |

**Decision**: Single Droplet is optimal for single-user system ✅

### 10.3 Scaling Costs

**If More Resources Needed**:
| Upgrade | New Cost | When Needed |
|---------|----------|-------------|
| 6vCPU, 16GB RAM | $96/mo | CPU >80% consistently |
| 8vCPU, 32GB RAM | $192/mo | Multiple concurrent users |
| Read Replica | +$15/mo | High read load |

---

## 11. Success Criteria

Deployment considered successful when:

- [x] All 9 services running and healthy
- [x] Database schema v5.0 deployed
- [x] SSL certificate obtained and configured
- [x] Firewall configured correctly
- [x] API authentication working
- [x] Health checks passing
- [x] Claude Desktop connected via MCP
- [x] Backups configured
- [x] Monitoring operational

---

## Appendix A: Quick Reference

```bash
# Service Management
docker-compose up -d          # Start all services
docker-compose down           # Stop all services
docker-compose restart        # Restart all services
docker-compose logs -f        # View logs

# Health Checks
./scripts/health-check.sh     # Check all services
curl localhost:5000/health    # Check orchestration

# Monitoring
docker stats                  # Resource usage
htop                          # System resources
journalctl -u nginx -f        # Nginx logs

# Backup
./scripts/backup-config.sh    # Backup configuration
doctl compute droplet-action snapshot DROPLET_ID  # Snapshot droplet

# Updates
./scripts/deploy-update.sh    # Rolling update
git pull && docker-compose up -d --build  # Full rebuild
```

---

**END OF DEPLOYMENT ARCHITECTURE v2.0**

*Single DigitalOcean Droplet deployment with Docker Compose orchestration. No AWS. No App Platform. Simple, cost-effective, production-ready.*