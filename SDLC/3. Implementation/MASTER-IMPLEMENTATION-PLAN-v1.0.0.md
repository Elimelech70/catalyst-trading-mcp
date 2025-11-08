# MASTER IMPLEMENTATION PLAN - Catalyst Trading System

**Name of Application**: Catalyst Trading System  
**Name of file**: MASTER-IMPLEMENTATION-PLAN-v1.0.0.md  
**Version**: 1.0.0  
**Last Updated**: 2025-11-06  
**Purpose**: Complete implementation plan with all requirements for Production system  

---

## REVISION HISTORY

**v1.0.0 (2025-11-06)** - Master Implementation Plan
- Corrected current state assessment (cron NOT implemented, email NOT implemented)
- Comprehensive implementation steps with all requirements
- All scripts, configurations, and setup procedures included
- Complete testing and validation procedures
- Proper sequencing with dependencies

---

## Table of Contents

1. [Current Actual State](#1-current-actual-state)
2. [Implementation Phases Overview](#2-implementation-phases-overview)
3. [Phase 1: Infrastructure Setup](#3-phase-1-infrastructure-setup)
4. [Phase 2: Cron Automation Implementation](#4-phase-2-cron-automation-implementation)
5. [Phase 3: Email Alert System](#5-phase-3-email-alert-system)
6. [Phase 4: System Validation](#6-phase-4-system-validation)
7. [Phase 5: Integration Testing](#7-phase-5-integration-testing)
8. [Phase 6: Paper Trading](#8-phase-6-paper-trading)
9. [Phase 7: Live Trading](#9-phase-7-live-trading)

---

## 1. Current Actual State

### 1.1 What EXISTS (Design/Documentation) ✅

```yaml
Design Documents:
  ✅ architecture-mcp-v6.0.0.md
  ✅ database-schema-mcp-v6.0.0.md
  ✅ functional-spec-mcp-v6.1.0.md
  ✅ deployment-playbook-mcp-v5.0.md

Script Files (Created but NOT deployed):
  ✅ production-manager.sh (in design docs)
  ✅ system_monitor.py (in design docs)
  ✅ health-check scripts (in design docs)
  ✅ cron schedules (in functional spec)

Docker Infrastructure:
  ✅ docker-compose.yml exists
  ✅ 9 services defined
  ✅ Network configuration complete

Database:
  ✅ Schema v6.0.0 designed
  ✅ Normalized structure documented
  ✅ DigitalOcean managed PostgreSQL provisioned
```

### 1.2 What is NOT IMPLEMENTED ❌

```yaml
Cron Automation:
  ❌ Cron jobs NOT configured on server
  ❌ production-manager.sh NOT deployed to /root/catalyst-trading-mcp/scripts/
  ❌ Market hours automation NOT running
  ❌ Health checks NOT scheduled
  ❌ Database backups NOT automated
  ❌ Log rotation NOT configured

Email Alert System:
  ❌ DigitalOcean Email Service NOT configured
  ❌ SMTP credentials NOT set in .env
  ❌ DNS records (SPF/DKIM/DMARC) NOT created
  ❌ system_monitor.py NOT deployed
  ❌ Alert templates NOT implemented
  ❌ Email testing NOT completed

System Operations:
  ❌ Services may be deployed but operational automation missing
  ❌ No automated workflow execution
  ❌ No health monitoring running
  ❌ No automated recovery procedures

Testing:
  ❌ Integration tests NOT executed
  ❌ End-to-end workflows NOT validated
  ❌ Paper trading NOT started
  ❌ Performance NOT measured under load
```

### 1.3 Critical Gap Summary

**The Core Issue**: We have excellent design documents and scripts, but **ZERO actual implementation** of the operational automation layer.

**Result**: The system cannot run autonomously. Even if services are deployed via docker-compose, there's no:
- Automated workflow execution (no cron)
- Health monitoring (no scheduled checks)
- Alert system (no email notifications)
- Automated recovery (no restart procedures)
- Operational reliability (no production-grade automation)

---

## 2. Implementation Phases Overview

### 2.1 Phase Sequence

```yaml
PHASE 1: Infrastructure Setup (1-2 hours)
  Goal: Prepare server environment for automation
  Tasks: Create directories, set permissions, install tools
  Deliverable: Clean operational foundation

PHASE 2: Cron Automation (2-3 hours)
  Goal: Implement automated workflow execution
  Tasks: Deploy scripts, configure cron, test execution
  Deliverable: Automated trading cycles running

PHASE 3: Email Alert System (2-3 hours)
  Goal: Implement monitoring and notifications
  Tasks: Configure SMTP, deploy monitor, test alerts
  Deliverable: Alert system operational

PHASE 4: System Validation (1-2 days)
  Goal: Verify 48+ hours stable operation
  Tasks: Monitor executions, check logs, validate health
  Deliverable: Operational foundation proven

PHASE 5: Integration Testing (3-4 days)
  Goal: Validate end-to-end system functionality
  Tasks: Execute test suite, measure performance, fix issues
  Deliverable: System ready for paper trading

PHASE 6: Paper Trading (5-10 days)
  Goal: Validate strategy profitability
  Tasks: Execute 20+ trades, track metrics, analyze results
  Deliverable: Go/No-Go decision for live trading

PHASE 7: Live Trading (2 days setup + ongoing)
  Goal: Production trading with real capital
  Tasks: Configure live mode, start conservative, ramp up gradually
  Deliverable: Production system operational
```

### 2.2 Total Timeline Estimate

```yaml
Phases 1-3 (Implementation): 6-8 hours (1 day intensive work)
Phase 4 (Validation): 2-3 days (mostly waiting/monitoring)
Phase 5 (Testing): 3-4 days
Phase 6 (Paper Trading): 5-10 days
Phase 7 (Live Trading): 2 days + ongoing

Total: 12-20 days from start to production trading
```

---

## 3. Phase 1: Infrastructure Setup

### 3.1 Prerequisites Check

**Before Starting**:
```bash
# Verify you're on the DigitalOcean droplet
ssh root@<your-droplet-ip>

# Verify Docker is running
docker ps

# Verify docker-compose.yml exists
ls -la /root/catalyst-trading-mcp/docker-compose.yml

# Verify .env file exists with DATABASE_URL
grep DATABASE_URL /root/catalyst-trading-mcp/.env
```

### 3.2 Create Directory Structure

```bash
# Create all required directories
mkdir -p /root/catalyst-trading-mcp/scripts
mkdir -p /var/log/catalyst
mkdir -p /backups/catalyst
mkdir -p /root/catalyst-trading-mcp/config

# Set proper permissions
chmod 755 /root/catalyst-trading-mcp/scripts
chmod 755 /var/log/catalyst
chmod 755 /backups/catalyst

# Verify creation
ls -la /root/catalyst-trading-mcp/
ls -la /var/log/catalyst/
ls -la /backups/catalyst/
```

### 3.3 Install Required System Tools

```bash
# Update package list
apt-get update

# Install required tools
apt-get install -y \
    curl \
    jq \
    postgresql-client \
    mailutils \
    cron \
    logrotate

# Verify cron is running
systemctl status cron

# If cron not running, start it
systemctl enable cron
systemctl start cron
```

### 3.4 Verification

```bash
# Verify all directories exist
ls -la /root/catalyst-trading-mcp/scripts
ls -la /var/log/catalyst
ls -la /backups/catalyst

# Verify cron daemon running
ps aux | grep cron

# Verify Docker services accessible
curl -f http://localhost:5000/health || echo "Orchestration service not accessible"
curl -f http://localhost:5006/health || echo "Workflow service not accessible"
```

**Success Criteria**:
- ✅ All directories created
- ✅ Permissions set correctly
- ✅ Required tools installed
- ✅ Cron daemon running

---

## 4. Phase 2: Cron Automation Implementation

### 4.1 Deploy production-manager.sh Script

**File**: `/root/catalyst-trading-mcp/scripts/production-manager.sh`

```bash
#!/bin/bash
# Catalyst Trading System - Production Manager
# Handles market hours automation, health checks, and maintenance

set -euo pipefail

# Configuration
COMPOSE_FILE="/root/catalyst-trading-mcp/docker-compose.yml"
LOG_DIR="/var/log/catalyst"
BACKUP_DIR="/backups/catalyst"
ALERT_EMAIL="${ALERT_EMAIL:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/production-manager.log"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    log "SUCCESS: $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    log "ERROR: $1"
}

print_status() {
    echo -e "${YELLOW}→${NC} $1"
    log "STATUS: $1"
}

# Check if we're in market hours (EST)
is_market_hours() {
    hour=$(TZ='America/New_York' date +%H)
    day=$(TZ='America/New_York' date +%u)  # 1=Monday, 7=Sunday
    
    # Monday-Friday (1-5), 9:30 AM - 4:00 PM EST
    if [ "$day" -le 5 ] && [ "$hour" -ge 9 ] && [ "$hour" -lt 16 ]; then
        return 0  # True
    else
        return 1  # False
    fi
}

# Start all services
start_system() {
    print_status "Starting Catalyst Trading System..."
    
    cd /root/catalyst-trading-mcp || exit 1
    
    # Start services
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    sleep 30
    
    # Check health
    if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
        print_success "All services started successfully"
    else
        print_error "Service health check failed"
        return 1
    fi
}

# Stop all services gracefully
stop_system() {
    print_status "Stopping Catalyst Trading System..."
    
    cd /root/catalyst-trading-mcp || exit 1
    
    docker-compose -f "$COMPOSE_FILE" down
    
    print_success "System stopped"
}

# Service health check
status_check() {
    print_status "Checking service health..."
    
    services=(
        "orchestration:5000"
        "workflow:5006"
        "scanner:5001"
        "pattern:5002"
        "technical:5003"
        "risk-manager:5004"
        "trading:5005"
        "news:5008"
        "reporting:5009"
    )
    
    failed=0
    
    for service in "${services[@]}"; do
        name="${service%%:*}"
        port="${service##*:}"
        
        if curl -sf "http://localhost:$port/health" >/dev/null 2>&1; then
            print_success "$name service healthy"
        else
            print_error "$name service unhealthy"
            failed=$((failed + 1))
        fi
    done
    
    if [ $failed -eq 0 ]; then
        print_success "All services healthy"
        return 0
    else
        print_error "$failed services unhealthy"
        return 1
    fi
}

# Database backup
backup_database() {
    print_status "Creating database backup..."
    
    backup_file="$BACKUP_DIR/catalyst_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    # Extract database URL components
    # Format: postgresql://user:pass@host:port/dbname
    if [ -f /root/catalyst-trading-mcp/.env ]; then
        source /root/catalyst-trading-mcp/.env
        
        # Use pg_dump with connection string
        if PGPASSWORD="${DATABASE_PASSWORD:-}" pg_dump -h "${DATABASE_HOST:-}" \
            -U "${DATABASE_USER:-}" \
            -d "${DATABASE_NAME:-catalyst_trading}" \
            -f "$backup_file" 2>/dev/null; then
            
            print_success "Database backup created: $backup_file"
            
            # Compress backup
            gzip "$backup_file"
            print_success "Backup compressed: ${backup_file}.gz"
            
            # Clean old backups (keep last 30 days)
            find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
            
            return 0
        else
            print_error "Database backup failed"
            return 1
        fi
    else
        print_error ".env file not found"
        return 1
    fi
}

# Quick health check for cron
quick_health_check() {
    if ! curl -sf http://localhost:5000/health >/dev/null 2>&1; then
        print_error "Health check failed - attempting restart"
        
        # Log to separate alert file
        echo "[$(date)] ALERT: Health check failed, restarting system" >> "$LOG_DIR/alerts.log"
        
        # Attempt restart
        docker-compose -f "$COMPOSE_FILE" restart
        
        # Wait and recheck
        sleep 30
        
        if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
            print_success "System recovered after restart"
        else
            print_error "System still unhealthy after restart"
            
            # Send email alert if configured
            if [ -n "$ALERT_EMAIL" ]; then
                echo "Catalyst Trading System health check failed at $(date). Manual intervention required." | \
                    mail -s "CRITICAL: Catalyst System Down" "$ALERT_EMAIL"
            fi
        fi
    fi
}

# Market open notification
market_open_workflow() {
    print_status "Market open - Starting trading workflow..."
    
    # Trigger workflow via REST API
    response=$(curl -sf -X POST http://localhost:5006/api/v1/workflow/start \
        -H "Content-Type: application/json" \
        -d '{"mode": "normal", "max_positions": 5, "risk_per_trade": 0.01}')
    
    if [ $? -eq 0 ]; then
        print_success "Trading workflow started"
        log "Workflow response: $response"
    else
        print_error "Failed to start trading workflow"
    fi
}

# Market close operations
market_close_workflow() {
    print_status "Market close - Running end-of-day operations..."
    
    # Trigger end-of-day report
    curl -sf -X POST http://localhost:5009/api/v1/reports/daily >/dev/null 2>&1 || true
    
    print_success "End-of-day operations complete"
}

# Weekly maintenance
weekly_maintenance() {
    print_status "Running weekly maintenance..."
    
    # Backup database
    backup_database
    
    # Clean old logs (keep 30 days)
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete
    
    # Docker cleanup
    docker system prune -f
    
    # Restart services for fresh start
    print_status "Restarting services..."
    stop_system
    sleep 30
    start_system
    
    print_success "Weekly maintenance completed"
}

# Log rotation
rotate_logs() {
    print_status "Rotating logs..."
    
    # Find logs larger than 100MB
    find "$LOG_DIR" -name "*.log" -size +100M -exec gzip {} \;
    
    # Archive old compressed logs
    find "$LOG_DIR" -name "*.log.gz" -mtime +7 -exec mv {} "$LOG_DIR/archive/" \; 2>/dev/null || true
    
    print_success "Log rotation complete"
}

# Main command handler
case "${1:-}" in
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        stop_system
        sleep 10
        start_system
        ;;
    status)
        status_check
        ;;
    backup)
        backup_database
        ;;
    health)
        quick_health_check
        ;;
    market-open)
        market_open_workflow
        ;;
    market-close)
        market_close_workflow
        ;;
    weekly-maintenance)
        weekly_maintenance
        ;;
    rotate-logs)
        rotate_logs
        ;;
    *)
        echo "Catalyst Trading System - Production Manager"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  start               - Start all services"
        echo "  stop                - Stop all services"
        echo "  restart             - Restart all services"
        echo "  status              - Check service health"
        echo "  backup              - Create database backup"
        echo "  health              - Quick health check (for cron)"
        echo "  market-open         - Market open workflow"
        echo "  market-close        - Market close workflow"
        echo "  weekly-maintenance  - Weekly maintenance tasks"
        echo "  rotate-logs         - Rotate and compress logs"
        exit 1
        ;;
esac
```

**Deploy the script**:
```bash
# Create the script file
cat > /root/catalyst-trading-mcp/scripts/production-manager.sh << 'ENDOFSCRIPT'
[PASTE ENTIRE SCRIPT ABOVE HERE]
ENDOFSCRIPT

# Make executable
chmod +x /root/catalyst-trading-mcp/scripts/production-manager.sh

# Test the script
/root/catalyst-trading-mcp/scripts/production-manager.sh status
```

### 4.2 Configure Cron Jobs

**File**: Create cron configuration

```bash
# Edit crontab
crontab -e

# Add the following lines (adjust times for your timezone):
```

**Cron Configuration** (copy this into crontab):
```cron
# Catalyst Trading System - Automated Operations
# All times in EST (US Eastern Time)

# Health Check - Every 5 minutes (24/7)
*/5 * * * * /root/catalyst-trading-mcp/scripts/production-manager.sh health >> /var/log/catalyst/health-check.log 2>&1

# Market Open Workflow - 9:30 AM EST Monday-Friday
30 9 * * 1-5 /root/catalyst-trading-mcp/scripts/production-manager.sh market-open >> /var/log/catalyst/market-open.log 2>&1

# Mid-morning Scan - 11:00 AM EST Monday-Friday  
0 11 * * 1-5 /root/catalyst-trading-mcp/scripts/production-manager.sh market-open >> /var/log/catalyst/mid-morning.log 2>&1

# Lunch Scan - 1:00 PM EST Monday-Friday
0 13 * * 1-5 /root/catalyst-trading-mcp/scripts/production-manager.sh market-open >> /var/log/catalyst/lunch-scan.log 2>&1

# Market Close Workflow - 4:00 PM EST Monday-Friday
0 16 * * 1-5 /root/catalyst-trading-mcp/scripts/production-manager.sh market-close >> /var/log/catalyst/market-close.log 2>&1

# Daily Database Backup - 11:00 PM EST Every Night
0 23 * * * /root/catalyst-trading-mcp/scripts/production-manager.sh backup >> /var/log/catalyst/backup.log 2>&1

# Weekly Maintenance - Sunday 2:00 AM EST
0 2 * * 0 /root/catalyst-trading-mcp/scripts/production-manager.sh weekly-maintenance >> /var/log/catalyst/weekly-maintenance.log 2>&1

# Log Rotation - Daily at 3:00 AM EST
0 3 * * * /root/catalyst-trading-mcp/scripts/production-manager.sh rotate-logs >> /var/log/catalyst/log-rotation.log 2>&1
```

**Save and verify**:
```bash
# Save crontab (Ctrl+X, then Y, then Enter)

# Verify cron configuration
crontab -l

# Check if cron daemon is running
systemctl status cron

# Watch cron logs to see if jobs are scheduled
tail -f /var/log/syslog | grep CRON
```

### 4.3 Test Cron Execution

```bash
# Test each command manually first

# 1. Test health check
/root/catalyst-trading-mcp/scripts/production-manager.sh health

# 2. Test status check
/root/catalyst-trading-mcp/scripts/production-manager.sh status

# 3. Test backup (this will actually create a backup)
/root/catalyst-trading-mcp/scripts/production-manager.sh backup

# 4. Check logs were created
ls -la /var/log/catalyst/
ls -la /backups/catalyst/

# 5. Wait for next cron execution (5 minutes max) and verify
# Watch the health-check.log file
tail -f /var/log/catalyst/health-check.log

# You should see entries every 5 minutes if cron is working
```

### 4.4 Verification Checklist

```yaml
Cron Automation Verification:
  ✅ production-manager.sh deployed to /root/catalyst-trading-mcp/scripts/
  ✅ Script is executable (chmod +x)
  ✅ Script runs successfully when called manually
  ✅ Crontab configured with all jobs
  ✅ Cron daemon running (systemctl status cron)
  ✅ First cron execution verified (check /var/log/catalyst/)
  ✅ Logs being created in /var/log/catalyst/
  ✅ Health checks running every 5 minutes
  ✅ All services accessible (curl health endpoints)

Success Criteria:
  - Manual execution of production-manager.sh works for all commands
  - Crontab shows 8 scheduled jobs
  - Health check log shows entries every 5 minutes
  - No errors in /var/log/catalyst/*.log files
```

---

## 5. Phase 3: Email Alert System

### 5.1 Configure DigitalOcean Email Service

**Step 1: Get SMTP Credentials**

```bash
# Log into DigitalOcean Control Panel
# Navigate to: Account > Settings > Email

# Create SMTP credentials:
1. Click "Add SMTP Credential"
2. Name: catalyst-trading-alerts
3. Copy the generated credentials:
   - SMTP Host: smtp.digitalocean.com
   - Port: 587
   - Username: <your-username>
   - Password: <your-password>
```

**Step 2: Configure DNS Records**

In your domain's DNS settings, add:
```dns
# SPF Record
Type: TXT
Name: @
Value: v=spf1 include:_spf.smtp.digitalocean.com ~all

# DKIM Record (provided by DigitalOcean)
Type: TXT  
Name: <provided-by-digitalocean>
Value: <provided-by-digitalocean>

# DMARC Record
Type: TXT
Name: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:postmaster@yourdomain.com
```

**Step 3: Add SMTP Configuration to .env**

```bash
# Edit .env file
nano /root/catalyst-trading-mcp/.env

# Add these lines:
SMTP_HOST=smtp.digitalocean.com
SMTP_PORT=587
SMTP_USERNAME=<your-smtp-username>
SMTP_PASSWORD=<your-smtp-password>
SMTP_FROM=alerts@yourdomain.com
SMTP_USE_TLS=True
ALERT_EMAIL=your-email@example.com
```

### 5.2 Deploy System Monitor Script

**File**: `/root/catalyst-trading-mcp/scripts/system_monitor.py`

```python
"""
Catalyst Trading System - System Monitor
Monitors service health and sends email alerts
"""

import asyncio
import aiohttp
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("system_monitor")

class SystemMonitor:
    def __init__(self):
        self.services = {
            "orchestration": "http://localhost:5000/health",
            "workflow": "http://localhost:5006/health",
            "scanner": "http://localhost:5001/health",
            "pattern": "http://localhost:5002/health",
            "technical": "http://localhost:5003/health",
            "risk-manager": "http://localhost:5004/health",
            "trading": "http://localhost:5005/health",
            "news": "http://localhost:5008/health",
            "reporting": "http://localhost:5009/health"
        }
        
        self.alert_cooldown = {}  # Prevent alert spam
        self.failed_services = {}  # Track failures
        
        # Email configuration
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.digitalocean.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_from = os.getenv('SMTP_FROM', 'alerts@localhost')
        self.alert_email = os.getenv('ALERT_EMAIL', '')
        
    async def check_service_health(self, service: str, url: str) -> Dict:
        """Check individual service health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return {
                            "service": service,
                            "status": "healthy",
                            "code": 200
                        }
                    else:
                        return {
                            "service": service,
                            "status": "unhealthy",
                            "code": response.status
                        }
        except Exception as e:
            return {
                "service": service,
                "status": "failed",
                "error": str(e)
            }
    
    async def send_email_alert(self, subject: str, body: str):
        """Send email alert using SMTP"""
        if not self.alert_email:
            logger.warning("No alert email configured, skipping email send")
            return
        
        # Check cooldown (don't send same alert more than once per 15 minutes)
        now = datetime.now()
        if subject in self.alert_cooldown:
            if now - self.alert_cooldown[subject] < timedelta(minutes=15):
                logger.info(f"Alert cooldown active for: {subject}")
                return
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = self.alert_email
            msg['Subject'] = f"[CATALYST ALERT] {subject}"
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Create secure SSL context
            context = ssl.create_default_context()
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            # Update cooldown
            self.alert_cooldown[subject] = now
            logger.info(f"Alert sent successfully: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    async def handle_service_failure(self, service: str, result: Dict):
        """Handle a failed service"""
        # Track failures
        if service not in self.failed_services:
            self.failed_services[service] = {
                "first_failure": datetime.now(),
                "failure_count": 1
            }
        else:
            self.failed_services[service]["failure_count"] += 1
        
        failure_info = self.failed_services[service]
        failure_count = failure_info["failure_count"]
        
        # Send alert on first failure and every 5th failure thereafter
        if failure_count == 1 or failure_count % 5 == 0:
            subject = f"Service Failure: {service}"
            body = f"""Catalyst Trading System Alert

Service: {service}
Status: {result['status']}
Failure Count: {failure_count}
First Failure: {failure_info['first_failure'].strftime('%Y-%m-%d %H:%M:%S')}
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Error Details:
{result.get('error', 'HTTP ' + str(result.get('code', 'unknown')))}

Action Required: Please check the service logs and restart if necessary.

Service Health Check URL: {self.services[service]}
"""
            await self.send_email_alert(subject, body)
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting system monitor...")
        
        while True:
            try:
                # Check all services
                service_results = []
                for service, url in self.services.items():
                    result = await self.check_service_health(service, url)
                    service_results.append(result)
                    
                    # Handle failures
                    if result['status'] != 'healthy':
                        await self.handle_service_failure(service, result)
                    else:
                        # Clear failure tracking if service recovered
                        if service in self.failed_services:
                            # Send recovery notification
                            subject = f"Service Recovered: {service}"
                            body = f"""Catalyst Trading System Alert

Service: {service}
Status: Recovered
Recovery Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The service is now healthy and responding normally.
"""
                            await self.send_email_alert(subject, body)
                            del self.failed_services[service]
                
                # Log summary
                healthy = sum(1 for r in service_results if r['status'] == 'healthy')
                logger.info(f"Health check complete: {healthy}/{len(service_results)} services healthy")
                
                # Sleep 2 minutes between checks
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(60)

if __name__ == "__main__":
    # Load environment variables from .env
    from pathlib import Path
    env_file = Path("/root/catalyst-trading-mcp/.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    monitor = SystemMonitor()
    asyncio.run(monitor.monitor_loop())
```

**Deploy the monitor**:
```bash
# Create the script
cat > /root/catalyst-trading-mcp/scripts/system_monitor.py << 'ENDOFMONITOR'
[PASTE ENTIRE SCRIPT ABOVE]
ENDOFMONITOR

# Install required Python packages
pip3 install aiohttp

# Test the monitor manually (Ctrl+C to stop)
cd /root/catalyst-trading-mcp
python3 scripts/system_monitor.py
```

### 5.3 Create Systemd Service for Monitor

**File**: `/etc/systemd/system/catalyst-monitor.service`

```bash
# Create systemd service file
cat > /etc/systemd/system/catalyst-monitor.service << 'ENDOFSERVICE'
[Unit]
Description=Catalyst Trading System Monitor
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/catalyst-trading-mcp
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /root/catalyst-trading-mcp/scripts/system_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
ENDOFSERVICE

# Reload systemd
systemctl daemon-reload

# Enable and start the monitor
systemctl enable catalyst-monitor
systemctl start catalyst-monitor

# Check status
systemctl status catalyst-monitor

# View logs
journalctl -u catalyst-monitor -f
```

### 5.4 Test Email Alerts

**Send Test Email**:
```bash
# Method 1: Using production-manager.sh
# Temporarily break a service to trigger alert
docker-compose stop scanner

# Wait 5-10 minutes for health check to detect and send alert
# Check your email inbox

# Restart service
docker-compose start scanner

# Method 2: Send test email directly using Python
python3 << ENDOFTEST
import smtplib
import ssl
from email.mime.text import MIMEText
import os

# Load .env
with open('/root/catalyst-trading-mcp/.env') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

smtp_host = os.getenv('SMTP_HOST')
smtp_port = int(os.getenv('SMTP_PORT'))
smtp_user = os.getenv('SMTP_USERNAME')
smtp_pass = os.getenv('SMTP_PASSWORD')
smtp_from = os.getenv('SMTP_FROM')
alert_email = os.getenv('ALERT_EMAIL')

msg = MIMEText('This is a test email from Catalyst Trading System')
msg['Subject'] = '[CATALYST TEST] Email Alert Test'
msg['From'] = smtp_from
msg['To'] = alert_email

context = ssl.create_default_context()

with smtplib.SMTP(smtp_host, smtp_port) as server:
    server.starttls(context=context)
    server.login(smtp_user, smtp_pass)
    server.send_message(msg)
    print("Test email sent successfully!")
ENDOFTEST
```

### 5.5 Verification Checklist

```yaml
Email Alert System Verification:
  ✅ SMTP credentials obtained from DigitalOcean
  ✅ DNS records configured (SPF, DKIM, DMARC)
  ✅ SMTP configuration added to .env
  ✅ system_monitor.py deployed to /root/catalyst-trading-mcp/scripts/
  ✅ Required Python packages installed (aiohttp)
  ✅ Systemd service created and enabled
  ✅ Monitor service running (systemctl status catalyst-monitor)
  ✅ Test email sent successfully
  ✅ Email received in inbox (check spam folder)
  ✅ Service failure alert tested (stop a service, wait for alert)
  ✅ Service recovery alert tested (restart service, wait for alert)

Success Criteria:
  - Test email arrives in inbox
  - Monitor logs show healthy service checks
  - Alerts sent when service fails
  - Recovery notification sent when service restores
  - No SMTP authentication errors
```

---

## 6. Phase 4: System Validation

### 6.1 48-Hour Operational Test

**Goal**: Verify system runs stably for 48 continuous hours

**Monitoring Checklist**:
```bash
# Day 1 Morning - Start validation period
date > /var/log/catalyst/validation-start.txt

# Check every 6 hours (4 times per day for 2 days = 8 checks)

# Check 1: Services running
docker ps | grep catalyst

# Check 2: Health status
/root/catalyst-trading-mcp/scripts/production-manager.sh status

# Check 3: Cron executions (should show 5-minute intervals)
tail -20 /var/log/catalyst/health-check.log

# Check 4: Monitor service running
systemctl status catalyst-monitor

# Check 5: Email alerts (check inbox - should have none if all healthy)

# Check 6: Resource usage
docker stats --no-stream | grep catalyst

# Check 7: Log for errors
grep -i error /var/log/catalyst/*.log | tail -20

# Check 8: Database connectivity
docker exec catalyst-orchestration curl -f http://localhost:5000/health
```

**Daily Validation Report**:
```bash
# Create daily report script
cat > /root/catalyst-trading-mcp/scripts/daily-validation-report.sh << 'ENDOFREPORT'
#!/bin/bash

echo "=============================="
echo "Catalyst System Daily Report"
echo "Date: $(date)"
echo "=============================="
echo ""

echo "1. Service Status:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep catalyst
echo ""

echo "2. Health Checks (last 10):"
tail -10 /var/log/catalyst/health-check.log
echo ""

echo "3. Cron Executions Today:"
grep "$(date +%Y-%m-%d)" /var/log/catalyst/*.log | wc -l
echo ""

echo "4. Errors Today:"
grep -i error /var/log/catalyst/*.log | grep "$(date +%Y-%m-%d)" | wc -l
echo ""

echo "5. Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep catalyst
echo ""

echo "6. Disk Space:"
df -h /var/log/catalyst /backups/catalyst
echo ""

echo "=============================="
ENDOFREPORT

chmod +x /root/catalyst-trading-mcp/scripts/daily-validation-report.sh

# Run daily report
/root/catalyst-trading-mcp/scripts/daily-validation-report.sh
```

### 6.2 Validation Success Criteria

```yaml
48-Hour Validation Success:
  ✅ All 9 services running continuously
  ✅ Health checks executing every 5 minutes (576 executions over 48 hours)
  ✅ Cron jobs executing on schedule (market-open, market-close, backup)
  ✅ System monitor service running continuously
  ✅ Zero service crashes or restarts (unless intentional)
  ✅ Zero critical errors in logs
  ✅ Email alerts functioning (test with intentional failure)
  ✅ Database backups created successfully
  ✅ Resource usage stable (CPU <70%, Memory <80%)
  ✅ No database connection pool exhaustion

Proceed to Phase 5 if ALL criteria met
```

---

## 7. Phase 5: Integration Testing

### 7.1 Test Suite Execution

**Deploy Integration Test Scripts** (from PRIMARY-002 document):

```bash
# Create integration test directory
mkdir -p /root/catalyst-trading-mcp/tests

# Test 1: Health Check Script
cat > /root/catalyst-trading-mcp/tests/test-health.sh << 'ENDOFTEST'
#!/bin/bash
echo "Testing service health..."

services=(
    "orchestration:5000"
    "workflow:5006"
    "scanner:5001"
    "pattern:5002"
    "technical:5003"
    "risk-manager:5004"
    "trading:5005"
    "news:5008"
    "reporting:5009"
)

failed=0
for service in "${services[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"
    
    if curl -sf "http://localhost:$port/health" >/dev/null 2>&1; then
        echo "✓ $name"
    else
        echo "✗ $name FAILED"
        failed=$((failed + 1))
    fi
done

if [ $failed -eq 0 ]; then
    echo "✓ All services healthy"
    exit 0
else
    echo "✗ $failed services failed"
    exit 1
fi
ENDOFTEST

chmod +x /root/catalyst-trading-mcp/tests/test-health.sh
```

**Test 2: Workflow Execution**:
```bash
cat > /root/catalyst-trading-mcp/tests/test-workflow.sh << 'ENDOFTEST'
#!/bin/bash
echo "Testing complete workflow execution..."

# Start workflow
response=$(curl -sf -X POST http://localhost:5006/api/v1/workflow/start \
    -H "Content-Type: application/json" \
    -d '{"mode": "test", "max_positions": 1, "risk_per_trade": 0.001}')

if [ $? -eq 0 ]; then
    cycle_id=$(echo "$response" | jq -r '.cycle_id')
    echo "✓ Workflow started: $cycle_id"
    
    # Monitor for completion (max 5 minutes)
    timeout=300
    elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        status=$(curl -sf "http://localhost:5006/api/v1/workflow/status/$cycle_id" | jq -r '.status')
        
        if [ "$status" == "completed" ]; then
            echo "✓ Workflow completed successfully"
            exit 0
        elif [ "$status" == "error" ]; then
            echo "✗ Workflow failed"
            exit 1
        fi
        
        sleep 30
        elapsed=$((elapsed + 30))
    done
    
    echo "✗ Workflow timeout"
    exit 1
else
    echo "✗ Failed to start workflow"
    exit 1
fi
ENDOFTEST

chmod +x /root/catalyst-trading-mcp/tests/test-workflow.sh
```

**Test 3: Database Integrity**:
```bash
cat > /root/catalyst-trading-mcp/tests/test-database.sh << 'ENDOFTEST'
#!/bin/bash
echo "Testing database integrity..."

# Source .env for DATABASE_URL
source /root/catalyst-trading-mcp/.env

# Test 1: Connection
if psql "$DATABASE_URL" -c "SELECT 1" >/dev/null 2>&1; then
    echo "✓ Database connection"
else
    echo "✗ Database connection FAILED"
    exit 1
fi

# Test 2: Schema exists
tables=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")

if [ "$tables" -gt 10 ]; then
    echo "✓ Database schema ($tables tables)"
else
    echo "✗ Database schema INCOMPLETE"
    exit 1
fi

# Test 3: Foreign key constraints
fks=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_type='FOREIGN KEY'")

if [ "$fks" -gt 5 ]; then
    echo "✓ Foreign key constraints ($fks FKs)"
else
    echo "✗ Foreign key constraints MISSING"
    exit 1
fi

echo "✓ Database integrity verified"
exit 0
ENDOFTEST

chmod +x /root/catalyst-trading-mcp/tests/test-database.sh
```

### 7.2 Run Complete Test Suite

```bash
# Execute all tests
echo "===================================="
echo "Catalyst Trading System Test Suite"
echo "===================================="

/root/catalyst-trading-mcp/tests/test-health.sh
/root/catalyst-trading-mcp/tests/test-database.sh
/root/catalyst-trading-mcp/tests/test-workflow.sh

echo "===================================="
echo "Test suite complete"
```

### 7.3 Integration Testing Success Criteria

```yaml
Integration Testing Success:
  ✅ All services respond to health checks
  ✅ Database connection successful
  ✅ Database schema complete (11+ tables)
  ✅ Foreign key constraints present (5+ FKs)
  ✅ Workflow execution completes successfully
  ✅ All stages of pipeline execute (Scanner → News → Pattern → Technical → Risk → Trading)
  ✅ Test trade recorded in database
  ✅ Reporting service generates summary
  ✅ Zero critical errors during test
  ✅ Performance within targets (<5 min per cycle)

Proceed to Phase 6 (Paper Trading) if ALL criteria met
```

---

## 8. Phase 6: Paper Trading

### 8.1 Configure Paper Trading Mode

**Update .env for Paper Trading**:
```bash
# Edit .env file
nano /root/catalyst-trading-mcp/.env

# Verify/Add these settings:
TRADING_MODE=paper
ALPACA_API_KEY=<your-paper-trading-key>
ALPACA_SECRET_KEY=<your-paper-trading-secret>
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Risk parameters (conservative for paper trading)
MAX_POSITIONS=3
RISK_PER_TRADE=0.01
MAX_DAILY_LOSS=0.02
```

**Restart Trading Service**:
```bash
docker-compose restart trading
docker logs -f catalyst-trading | grep "Paper trading mode"
```

### 8.2 Paper Trading Execution Plan

**Duration**: Minimum 5 days, target 10 days

**Daily Routine**:
```bash
# Morning (before market open)
1. Check service health
/root/catalyst-trading-mcp/scripts/production-manager.sh status

2. Review yesterday's trades
curl http://localhost:5009/api/v1/reports/daily

3. Ensure paper trading mode active
docker logs catalyst-trading | tail -20 | grep mode

# During Market Hours
4. Monitor workflow executions
tail -f /var/log/catalyst/market-open.log

5. Check for alerts
# (Email alerts will notify of any issues)

# End of Day
6. Generate performance report
curl http://localhost:5009/api/v1/reports/daily > daily-report-$(date +%Y%m%d).json

7. Calculate metrics
python3 /root/catalyst-trading-mcp/scripts/calculate-metrics.py
```

**Metrics Calculation Script**:
```bash
cat > /root/catalyst-trading-mcp/scripts/calculate-metrics.py << 'ENDOFMETRICS'
#!/usr/bin/env python3
import os
import psycopg2
import json
from datetime import datetime, timedelta

# Load DATABASE_URL from .env
with open('/root/catalyst-trading-mcp/.env') as f:
    for line in f:
        if line.startswith('DATABASE_URL='):
            db_url = line.strip().split('=', 1)[1]
            break

# Connect to database
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Get trades from last 10 days
start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')

cur.execute("""
    SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
        SUM(pnl) as total_pnl,
        AVG(pnl) as avg_pnl,
        MAX(pnl) as max_win,
        MIN(pnl) as max_loss
    FROM trades
    WHERE entry_time >= %s
    AND status = 'closed'
""", (start_date,))

result = cur.fetchone()

# Calculate metrics
total_trades = result[0]
winning_trades = result[1]
losing_trades = result[2]
total_pnl = float(result[3]) if result[3] else 0
avg_pnl = float(result[4]) if result[4] else 0
max_win = float(result[5]) if result[5] else 0
max_loss = float(result[6]) if result[6] else 0

win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
avg_win = avg_pnl if avg_pnl > 0 else 0
avg_loss = abs(avg_pnl) if avg_pnl < 0 else 0
rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0

# Display results
print("="*50)
print("PAPER TRADING PERFORMANCE METRICS")
print(f"Period: Last 10 days (since {start_date})")
print("="*50)
print(f"Total Trades: {total_trades}")
print(f"Winning Trades: {winning_trades}")
print(f"Losing Trades: {losing_trades}")
print(f"Win Rate: {win_rate:.2f}%")
print(f"Total P&L: ${total_pnl:.2f}")
print(f"Average P&L: ${avg_pnl:.2f}")
print(f"Risk:Reward Ratio: {rr_ratio:.2f}:1")
print(f"Max Win: ${max_win:.2f}")
print(f"Max Loss: ${max_loss:.2f}")
print("="*50)

# Decision criteria
print("\nGO/NO-GO DECISION:")
if win_rate >= 50 and rr_ratio >= 1.5 and total_trades >= 20:
    print("✓ PASS - Ready for live trading")
    print(f"  - Win rate ({win_rate:.1f}%) meets 50% minimum")
    print(f"  - R:R ratio ({rr_ratio:.2f}) meets 1.5:1 minimum")
    print(f"  - Trade count ({total_trades}) meets 20 minimum")
else:
    print("✗ FAIL - Continue paper trading")
    if win_rate < 50:
        print(f"  - Win rate ({win_rate:.1f}%) below 50% minimum")
    if rr_ratio < 1.5:
        print(f"  - R:R ratio ({rr_ratio:.2f}) below 1.5:1 minimum")
    if total_trades < 20:
        print(f"  - Trade count ({total_trades}) below 20 minimum")

print("="*50)

cur.close()
conn.close()
ENDOFMETRICS

chmod +x /root/catalyst-trading-mcp/scripts/calculate-metrics.py
```

### 8.3 Paper Trading Success Criteria

```yaml
Paper Trading Success (Go/No-Go Decision):
  ✅ Win Rate: ≥50%
  ✅ Risk:Reward Ratio: ≥1.5:1
  ✅ Max Drawdown: <10%
  ✅ Total Trades: ≥20
  ✅ Days Traded: ≥5 consecutive days
  ✅ System Stability: Zero crashes during period
  ✅ All workflows executed correctly
  ✅ Risk management enforced (no violations)

If ALL criteria met → Proceed to Phase 7 (Live Trading)
If ANY criteria failed → Continue paper trading, tune parameters, repeat
```

---

## 9. Phase 7: Live Trading

### 9.1 Enable Live Trading Mode

**⚠️ CRITICAL**: Only proceed if paper trading successful

```bash
# Backup current .env
cp /root/catalyst-trading-mcp/.env /root/catalyst-trading-mcp/.env.paper.backup

# Edit .env for live trading
nano /root/catalyst-trading-mcp/.env

# Change these settings:
TRADING_MODE=live
ALPACA_API_KEY=<your-live-trading-key>
ALPACA_SECRET_KEY=<your-live-trading-secret>
ALPACA_BASE_URL=https://api.alpaca.markets

# Conservative risk parameters for Stage 1
MAX_POSITIONS=3
RISK_PER_TRADE=0.005  # 0.5% per trade
MAX_DAILY_LOSS=0.02   # 2% max daily loss

# Restart trading service
docker-compose restart trading

# Verify live mode active
docker logs catalyst-trading | grep "Live trading mode"
```

### 9.2 Gradual Ramp-Up Strategy

**Stage 1 (Days 1-3): Ultra Conservative**
```bash
# Settings in .env:
MAX_POSITIONS=3
RISK_PER_TRADE=0.005  # 0.5% risk
MAX_DAILY_LOSS=0.02   # 2% daily loss

# Monitor VERY closely
# Daily checks mandatory
```

**Stage 2 (Days 4-6): Conservative**
```bash
# After Stage 1 successful:
MAX_POSITIONS=4
RISK_PER_TRADE=0.0075  # 0.75% risk
MAX_DAILY_LOSS=0.025   # 2.5% daily loss
```

**Stage 3 (Day 7+): Normal Operations**
```bash
# After Stage 2 successful:
MAX_POSITIONS=5
RISK_PER_TRADE=0.01  # 1% risk
MAX_DAILY_LOSS=0.03  # 3% daily loss
```

### 9.3 Live Trading Monitoring

**Daily Monitoring Checklist**:
```bash
# 1. Morning pre-market
/root/catalyst-trading-mcp/scripts/production-manager.sh status
curl http://localhost:5009/api/v1/reports/daily

# 2. Check account balance
curl "http://localhost:5005/api/v1/account" | jq

# 3. Review open positions
curl "http://localhost:5005/api/v1/positions" | jq

# 4. End of day metrics
python3 /root/catalyst-trading-mcp/scripts/calculate-metrics.py

# 5. Weekly review
# Every Sunday, review full week performance
```

### 9.4 Emergency Stop Procedures

**Create Emergency Stop Script**:
```bash
cat > /root/catalyst-trading-mcp/scripts/emergency-stop.sh << 'ENDOFSTOP'
#!/bin/bash
echo "======================================"
echo "EMERGENCY STOP - CATALYST TRADING SYSTEM"
echo "======================================"

# 1. Close all open positions immediately
echo "Closing all positions..."
curl -X POST "http://localhost:5005/api/v1/close-all" \
    -H "Content-Type: application/json"

# 2. Stop cron jobs temporarily
echo "Disabling cron jobs..."
crontab -l > /tmp/crontab.backup
crontab -r

# 3. Set trading mode to paper
echo "Switching to paper trading mode..."
sed -i 's/TRADING_MODE=live/TRADING_MODE=paper/' /root/catalyst-trading-mcp/.env

# 4. Restart trading service
echo "Restarting trading service..."
docker-compose restart trading

# 5. Send emergency alert
if [ -n "$ALERT_EMAIL" ]; then
    echo "Emergency stop executed at $(date)" | \
        mail -s "EMERGENCY: Trading System Stopped" "$ALERT_EMAIL"
fi

echo "======================================"
echo "Emergency stop complete"
echo "System is now in PAPER TRADING MODE"
echo "Cron jobs DISABLED"
echo "Manual intervention required to resume"
echo "======================================"
ENDOFSTOP

chmod +x /root/catalyst-trading-mcp/scripts/emergency-stop.sh
```

### 9.5 Live Trading Success Criteria

```yaml
Live Trading Operational Success:
  ✅ Stage 1 completed (3 days, zero losses >0.5%)
  ✅ Stage 2 completed (3 days, zero losses >0.75%)
  ✅ Stage 3 operational (full production)
  ✅ Win rate sustained ≥50%
  ✅ R:R ratio sustained ≥1.5:1
  ✅ Risk management enforced (no violations)
  ✅ Emergency stop tested (verify positions close)
  ✅ System operates autonomously
  ✅ Daily monitoring routine established
  ✅ Weekly performance reviews conducted

Production System Complete!
```

---

## 10. Appendix A: Quick Reference Commands

### A.1 Common Operations

```bash
# Check system status
/root/catalyst-trading-mcp/scripts/production-manager.sh status

# Manual health check
/root/catalyst-trading-mcp/scripts/production-manager.sh health

# View cron jobs
crontab -l

# Check monitor service
systemctl status catalyst-monitor

# View recent logs
tail -f /var/log/catalyst/health-check.log

# Check Docker services
docker ps | grep catalyst

# Restart specific service
docker-compose restart <service-name>

# View service logs
docker logs -f catalyst-<service-name>

# Emergency stop
/root/catalyst-trading-mcp/scripts/emergency-stop.sh
```

### A.2 Troubleshooting

```bash
# Service not responding
docker logs catalyst-<service-name>
docker-compose restart <service-name>

# Cron not executing
systemctl status cron
tail -f /var/log/syslog | grep CRON

# Email alerts not working
# Check SMTP credentials in .env
# Test email manually (see Phase 3)

# Database connection issues
psql $DATABASE_URL -c "SELECT 1"
# Check connection pool settings

# High resource usage
docker stats | grep catalyst
# Consider scaling resources
```

---

## 11. Appendix B: File Locations Reference

```yaml
Configuration:
  .env: /root/catalyst-trading-mcp/.env
  docker-compose.yml: /root/catalyst-trading-mcp/docker-compose.yml
  crontab: (use 'crontab -l' to view)

Scripts:
  production-manager.sh: /root/catalyst-trading-mcp/scripts/production-manager.sh
  system_monitor.py: /root/catalyst-trading-mcp/scripts/system_monitor.py
  calculate-metrics.py: /root/catalyst-trading-mcp/scripts/calculate-metrics.py
  emergency-stop.sh: /root/catalyst-trading-mcp/scripts/emergency-stop.sh

Logs:
  Health checks: /var/log/catalyst/health-check.log
  Market open: /var/log/catalyst/market-open.log
  Market close: /var/log/catalyst/market-close.log
  Backups: /var/log/catalyst/backup.log
  Alerts: /var/log/catalyst/alerts.log

Backups:
  Database backups: /backups/catalyst/catalyst_backup_*.sql.gz

Tests:
  Test scripts: /root/catalyst-trading-mcp/tests/

Systemd:
  Monitor service: /etc/systemd/system/catalyst-monitor.service
```

---

**END OF MASTER IMPLEMENTATION PLAN**

**Status**: Complete implementation guide with all requirements  
**Next Action**: Execute Phase 1 (Infrastructure Setup)  
**Timeline**: 12-20 days to production trading  

🎯 **Ready for implementation!**
