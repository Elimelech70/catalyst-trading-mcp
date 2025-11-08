# CRON SCHEDULE IMPLEMENTATION GUIDE
## Catalyst Trading System - Production Automation

**Name of Application**: Catalyst Trading System  
**Name of file**: cron-schedule-implementation.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-27  
**Purpose**: Complete implementation guide for cron job configuration on DigitalOcean

---

## EXECUTIVE SUMMARY

This guide provides step-by-step instructions to configure **cron automation as the PRIMARY workflow initiator** for the Catalyst Trading System. Cron executes 10+ automated trading workflows daily during US market hours (9:30 AM - 4:00 PM EST / 10:30 PM - 5:00 AM AWST).

**Critical Understanding**: 
- **Cron = PRIMARY** (Runs the business - automated trading)
- **Claude Desktop = SECONDARY** (Improves the business - monitoring & ML)

---

## TABLE OF CONTENTS

1. [Prerequisites](#prerequisites)
2. [Phase 1: System Preparation](#phase-1-system-preparation)
3. [Phase 2: Health Check Script](#phase-2-health-check-script)
4. [Phase 3: Cron Configuration](#phase-3-cron-configuration)
5. [Phase 4: Installation](#phase-4-installation)
6. [Phase 5: Verification](#phase-5-verification)
7. [Emergency Procedures](#emergency-procedures)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance Schedule](#maintenance-schedule)

---

## PREREQUISITES

### Requirements Checklist

- [ ] SSH access to DigitalOcean droplet (root user)
- [ ] Docker & Docker Compose installed and running
- [ ] All 9 services operational (orchestration, workflow, scanner, pattern, technical, risk-manager, trading, news, reporting)
- [ ] Database connection confirmed (DigitalOcean managed PostgreSQL)
- [ ] `.env` file configured with all API keys and credentials
- [ ] Timezone set to Australia/Perth (AWST = UTC+8)

### Verify Prerequisites

```bash
# SSH into droplet
ssh root@<your-droplet-ip>

# Check cron daemon
systemctl status cron
# Expected: active (running)

# Verify timezone
timedatectl
# Expected: Time zone: Australia/Perth (AWST, +0800)

# If timezone needs adjustment:
timedatectl set-timezone Australia/Perth

# Verify Docker
docker --version && docker-compose --version

# Verify services are healthy
docker-compose ps
# Expected: All services "Up" status

# Check project directory
ls -la /root/catalyst-trading-mcp
# Expected: docker-compose.yml, .env, services/, scripts/
```

---

## PHASE 1: SYSTEM PREPARATION

### Step 1.1: Create Directory Structure

```bash
# Create log directory
mkdir -p /var/log/catalyst

# Create backup directory
mkdir -p /backups/catalyst

# Create scripts directory if not exists
mkdir -p /root/catalyst-trading-mcp/scripts

# Set permissions
chmod 755 /var/log/catalyst
chmod 755 /backups/catalyst
chmod 755 /root/catalyst-trading-mcp/scripts

# Verify creation
ls -ld /var/log/catalyst /backups/catalyst
```

**Expected Output**:
```
drwxr-xr-x 2 root root 4096 Oct 27 09:00 /var/log/catalyst
drwxr-xr-x 2 root root 4096 Oct 27 09:00 /backups/catalyst
```

---

### Step 1.2: Verify Environment Configuration

```bash
# Check .env file exists
ls -la /root/catalyst-trading-mcp/.env

# Verify critical variables (without exposing secrets)
grep -E "^(DATABASE_URL|WORKFLOW_PORT|ALPACA_API_KEY)=" /root/catalyst-trading-mcp/.env | sed 's/=.*/=***HIDDEN***/'

# Test database connection
docker-compose exec -T postgres psql -U catalyst_user -d catalyst_trading -c "SELECT 1;"
# Expected: (1 row)
```

---

## PHASE 2: HEALTH CHECK SCRIPT

### Step 2.1: Create Health Check Script

```bash
# Create the script file
nano /root/catalyst-trading-mcp/scripts/health-check.sh
```

**Paste this content**:

```bash
#!/bin/bash
# ============================================================================
# Name of Application: Catalyst Trading System
# Name of file: health-check.sh
# Version: 1.0.0
# Last Updated: 2025-10-27
# Purpose: Health check all 9 microservices
#
# REVISION HISTORY:
# v1.0.0 (2025-10-27) - Initial health check script
#   - Check all 9 services via HTTP health endpoints
#   - Log results to /var/log/catalyst/health.log
#   - Exit 0 if all healthy, exit 1 if any failures
#
# Description:
# Called by cron every 15 minutes to verify system health.
# Tests each service's /health endpoint and logs results.
# ============================================================================

LOG_FILE="/var/log/catalyst/health.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Service array: name => port
declare -A SERVICES=(
    ["orchestration"]="5000"
    ["scanner"]="5001"
    ["pattern"]="5002"
    ["technical"]="5003"
    ["risk-manager"]="5004"
    ["trading"]="5005"
    ["workflow"]="5006"
    ["news"]="5008"
    ["reporting"]="5009"
)

echo "[$TIMESTAMP] ========== HEALTH CHECK START ==========" >> $LOG_FILE

FAILED_COUNT=0
FAILED_SERVICES=""

# Check each service
for service in "${!SERVICES[@]}"; do
    port="${SERVICES[$service]}"
    
    # Test health endpoint (5 second timeout)
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:$port/health 2>/dev/null)
    
    if [ "$response" == "200" ]; then
        echo "[$TIMESTAMP] ✓ $service (port $port) - HEALTHY" >> $LOG_FILE
    else
        echo "[$TIMESTAMP] ✗ $service (port $port) - FAILED (HTTP $response)" >> $LOG_FILE
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_SERVICES="$FAILED_SERVICES $service"
    fi
done

# Summary
echo "[$TIMESTAMP] Summary: $((${#SERVICES[@]} - FAILED_COUNT))/${#SERVICES[@]} services healthy" >> $LOG_FILE

if [ $FAILED_COUNT -gt 0 ]; then
    echo "[$TIMESTAMP] ⚠️  WARNING: Failed services:$FAILED_SERVICES" >> $LOG_FILE
    echo "[$TIMESTAMP] ========== HEALTH CHECK FAILED ==========" >> $LOG_FILE
    exit 1
else
    echo "[$TIMESTAMP] ✓ All services operational" >> $LOG_FILE
    echo "[$TIMESTAMP] ========== HEALTH CHECK PASSED ==========" >> $LOG_FILE
    exit 0
fi
```

**Save and exit**: `Ctrl+X`, `Y`, `Enter`

---

### Step 2.2: Make Script Executable and Test

```bash
# Make executable
chmod +x /root/catalyst-trading-mcp/scripts/health-check.sh

# Test the script
/root/catalyst-trading-mcp/scripts/health-check.sh

# Check the log output
tail -30 /var/log/catalyst/health.log
```

**Expected Output** (in log file):
```
[2025-10-27 09:15:00] ========== HEALTH CHECK START ==========
[2025-10-27 09:15:00] ✓ orchestration (port 5000) - HEALTHY
[2025-10-27 09:15:00] ✓ scanner (port 5001) - HEALTHY
[2025-10-27 09:15:00] ✓ pattern (port 5002) - HEALTHY
[2025-10-27 09:15:00] ✓ technical (port 5003) - HEALTHY
[2025-10-27 09:15:00] ✓ risk-manager (port 5004) - HEALTHY
[2025-10-27 09:15:00] ✓ trading (port 5005) - HEALTHY
[2025-10-27 09:15:00] ✓ workflow (port 5006) - HEALTHY
[2025-10-27 09:15:00] ✓ news (port 5008) - HEALTHY
[2025-10-27 09:15:00] ✓ reporting (port 5009) - HEALTHY
[2025-10-27 09:15:00] Summary: 9/9 services healthy
[2025-10-27 09:15:00] ✓ All services operational
[2025-10-27 09:15:00] ========== HEALTH CHECK PASSED ==========
```

---

## PHASE 3: CRON CONFIGURATION

### Step 3.1: Create Cron Configuration File

```bash
# Create the cron configuration file
nano /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt
```

**Paste this complete configuration**:

```bash
# ============================================================================
# CATALYST TRADING SYSTEM - PRODUCTION CRON CONFIGURATION
# ============================================================================
# Installation: crontab /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt
# View: crontab -l
# Edit: crontab -e
# Remove: crontab -r
# Logs: tail -f /var/log/catalyst/*.log
#
# Server Timezone: Perth, Western Australia (AWST = UTC+8)
# US Market Hours: 9:30 AM - 4:00 PM EST
# Perth Equivalent: 10:30 PM - 5:00 AM AWST (next day)
#
# CRITICAL: This cron schedule is the PRIMARY workflow initiator.
# These jobs execute automated trading operations 10+ times daily.
# ============================================================================

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
SHELL=/bin/bash
HOME=/root
CATALYST_HOME=/root/catalyst-trading-mcp

# ============================================================================
# MARKET HOURS AUTOMATION - TRADING OPERATIONS
# ============================================================================

# Pre-market startup (9:00 PM Perth = 4:00 AM EST)
# Start all Docker services 1.5 hours before market open
0 21 * * 1-5 cd $CATALYST_HOME && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1

# Market open workflow (10:30 PM Perth = 9:30 AM EST)
# Initiate first trading workflow at market open
30 22 * * 1-5 curl -s -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode": "normal", "max_positions": 5, "risk_per_trade": 0.01}' >> /var/log/catalyst/trading.log 2>&1

# Periodic workflow triggers (every 30 minutes during market hours)
# 11:00 PM - 4:30 AM Perth = 10:00 AM - 3:30 PM EST
0,30 23 * * 1-5 curl -s -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode": "normal"}' >> /var/log/catalyst/trading.log 2>&1
0,30 0-4 * * 2-6 curl -s -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode": "normal"}' >> /var/log/catalyst/trading.log 2>&1

# Market close workflow (5:00 AM Perth = 4:00 PM EST)
# Final conservative scan before market close
0 5 * * 2-6 curl -s -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode": "conservative", "max_positions": 3}' >> /var/log/catalyst/trading.log 2>&1

# After-hours shutdown (9:00 AM Perth = 8:00 PM EST)
# Stop all services 4 hours after market close
0 9 * * 2-6 cd $CATALYST_HOME && docker-compose stop >> /var/log/catalyst/shutdown.log 2>&1

# ============================================================================
# SYSTEM MAINTENANCE - HEALTH & MONITORING
# ============================================================================

# Health check (every 15 minutes, 24/7)
# Verifies all 9 services responding on their ports
*/15 * * * * /root/catalyst-trading-mcp/scripts/health-check.sh >> /dev/null 2>&1

# Auto-restart failed services (every 5 minutes)
# Automatically recovers from service crashes
*/5 * * * * cd $CATALYST_HOME && docker-compose ps | grep -q "Exit" && docker-compose up -d >> /var/log/catalyst/auto-restart.log 2>&1

# ============================================================================
# DATA MANAGEMENT - BACKUPS & CLEANUP
# ============================================================================

# Database backup (daily 2:00 AM Perth)
# Creates compressed backup of trading database
0 2 * * * cd $CATALYST_HOME && docker-compose exec -T postgres pg_dump -U catalyst_user -d catalyst_trading | gzip > /backups/catalyst/catalyst_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz 2>&1

# Log rotation (weekly Sunday 3:00 AM)
# Delete logs older than 7 days
0 3 * * 0 find /var/log/catalyst -name "*.log" -mtime +7 -delete 2>&1

# Backup retention (weekly Sunday 3:00 AM)
# Delete backups older than 30 days
0 3 * * 0 find /backups/catalyst -name "*.sql.gz" -mtime +30 -delete 2>&1

# ============================================================================
# REPORTING - PERFORMANCE TRACKING
# ============================================================================

# Daily performance report (6:00 AM Perth)
# Generates JSON report of last 50 workflow cycles
0 6 * * * cd $CATALYST_HOME && docker-compose exec -T workflow curl -s http://localhost:5006/api/v1/workflow/history?limit=50 | python3 -m json.tool > /var/log/catalyst/daily_report_$(date +\%Y\%m\%d).json 2>&1

# ============================================================================
# END OF CONFIGURATION
# ============================================================================
```

**Save and exit**: `Ctrl+X`, `Y`, `Enter`

---

### Step 3.2: Understand the Schedule

**Market Hours Schedule (Mon-Fri)**:

| Time (Perth) | Time (EST) | Action | Frequency |
|-------------|-----------|--------|-----------|
| 9:00 PM | 4:00 AM | 🚀 Start all services | Once |
| 10:30 PM | 9:30 AM | 📊 Market open workflow | Once |
| 11:00 PM - 4:30 AM | 10:00 AM - 3:30 PM | 🔄 Periodic scans | Every 30 min (13 scans) |
| 5:00 AM | 4:00 PM | 📉 Market close workflow | Once |
| 9:00 AM | 8:00 PM | 🛑 Stop all services | Once |

**Maintenance Schedule (24/7)**:

| Time | Action | Frequency |
|------|--------|-----------|
| Every 15 min | ❤️ Health checks | Continuous |
| Every 5 min | 🔧 Auto-restart failed services | Continuous |
| 2:00 AM daily | 💾 Database backup | Daily |
| 3:00 AM Sunday | 🧹 Log cleanup | Weekly |
| 6:00 AM daily | 📋 Performance report | Daily |

**Total Daily Workflows**: 15-16 automated trading cycles per market day

---

## PHASE 4: INSTALLATION

### Step 4.1: Backup Existing Crontab (if any)

```bash
# Check if crontab exists
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d).txt 2>/dev/null || echo "No existing crontab"

# Verify backup
ls -la /tmp/crontab_backup_*.txt
```

---

### Step 4.2: Install New Crontab

```bash
# Install cron configuration
crontab /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt

# Verify installation
crontab -l

# Check cron service is running
systemctl status cron

# Restart cron service (ensures new jobs loaded)
systemctl restart cron
```

**Expected Output** (from `crontab -l`):
```
# CATALYST TRADING SYSTEM - PRODUCTION CRON CONFIGURATION
...
[All cron jobs should be visible]
```

---

### Step 4.3: Verify Cron Syntax

```bash
# Check for syntax errors in cron logs
grep CRON /var/log/syslog | tail -20

# Should see entries like:
# Oct 27 09:00:01 catalyst CRON[12345]: (root) CMD (/root/catalyst-trading-mcp/scripts/health-check.sh)
```

---

## PHASE 5: VERIFICATION

### Step 5.1: Test Manual Workflow Trigger

```bash
# Test workflow endpoint (mimics cron behavior)
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "conservative", "max_positions": 1, "risk_per_trade": 0.005}'

# Expected response:
# {"cycle_id": "abc123...", "status": "initiated", "mode": "conservative"}
```

---

### Step 5.2: Monitor Next Scheduled Run

```bash
# Wait for next 15-minute interval (health check)
# Watch cron logs in real-time
tail -f /var/log/syslog | grep CRON

# In another terminal, watch health log
tail -f /var/log/catalyst/health.log

# You should see health check execute every 15 minutes
```

---

### Step 5.3: Verify Database Logging

```bash
# Check recent workflow cycles
docker-compose exec -T postgres psql -U catalyst_user -d catalyst_trading -c \
  "SELECT cycle_id, started_at, status, mode FROM trading_cycles ORDER BY started_at DESC LIMIT 5;"

# Expected: Recent test cycle visible
```

---

### Step 5.4: Monitor First Market Day

**IMPORTANT**: Full verification requires waiting for next market open.

**Checklist for First Market Day**:

```bash
# Day before (Sunday evening or Monday morning before 9:00 PM Perth)

# 1. Verify services are stopped
docker-compose ps
# Expected: No services running or all stopped

# 2. Watch startup log (starts at 9:00 PM Perth)
tail -f /var/log/catalyst/startup.log

# At 9:00 PM Perth (4:00 AM EST)
# Services should auto-start

# 3. Verify services started
docker-compose ps
# Expected: All services "Up" status

# At 10:30 PM Perth (9:30 AM EST)
# Watch trading log for first workflow

# 4. Monitor trading activity
tail -f /var/log/catalyst/trading.log

# Expected output every 30 minutes:
# {"cycle_id": "...", "status": "initiated", ...}

# 5. Throughout market hours
# Watch health checks
tail -f /var/log/catalyst/health.log

# 6. At 5:00 AM Perth (4:00 PM EST)
# Final conservative workflow should trigger

# 7. At 9:00 AM Perth (8:00 PM EST)
# Services should auto-stop
docker-compose ps
# Expected: All services "Exited" status
```

---

## EMERGENCY PROCEDURES

### Emergency Stop (Immediately Halt Trading)

```bash
# Create emergency stop script
nano /root/catalyst-trading-mcp/scripts/emergency-stop.sh
```

**Paste**:

```bash
#!/bin/bash
# ============================================================================
# EMERGENCY STOP - Immediately halt all trading operations
# ============================================================================

echo "🚨 EMERGENCY STOP INITIATED"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. Call emergency stop API
echo "Step 1: Calling emergency stop API..."
curl -X POST http://localhost:5006/api/v1/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual emergency stop", "initiated_by": "emergency_script"}'
echo ""

# 2. Backup current crontab
echo "Step 2: Backing up crontab..."
crontab -l > /tmp/crontab_emergency_backup_$(date +%Y%m%d_%H%M%S).txt
echo "✓ Backup saved to /tmp/crontab_emergency_backup_*.txt"

# 3. Disable all cron jobs
echo "Step 3: Disabling cron jobs..."
crontab -r
echo "✓ All cron jobs disabled"

# 4. Stop workflow service (prevents new cycles)
echo "Step 4: Stopping workflow service..."
cd /root/catalyst-trading-mcp
docker-compose stop workflow
echo "✓ Workflow service stopped"

# 5. Verify no active positions
echo "Step 5: Checking active positions..."
curl -s http://localhost:5006/api/v1/positions/active | python3 -m json.tool
echo ""

echo "🚨 EMERGENCY STOP COMPLETE"
echo ""
echo "Services still running: $(docker-compose ps --filter 'status=running' --format '{{.Service}}' | tr '\n' ' ')"
echo ""
echo "To RECOVER system:"
echo "  1. Fix the issue"
echo "  2. Verify services healthy: /root/catalyst-trading-mcp/scripts/health-check.sh"
echo "  3. Run recovery script: /root/catalyst-trading-mcp/scripts/recover-system.sh"
```

**Make executable**:
```bash
chmod +x /root/catalyst-trading-mcp/scripts/emergency-stop.sh
```

**To execute**:
```bash
/root/catalyst-trading-mcp/scripts/emergency-stop.sh
```

---

### System Recovery (After Emergency Stop)

```bash
# Create recovery script
nano /root/catalyst-trading-mcp/scripts/recover-system.sh
```

**Paste**:

```bash
#!/bin/bash
# ============================================================================
# SYSTEM RECOVERY - Restore normal operations after emergency stop
# ============================================================================

echo "🔄 SYSTEM RECOVERY INITIATED"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. Verify all services healthy
echo "Step 1: Checking service health..."
/root/catalyst-trading-mcp/scripts/health-check.sh

if [ $? -ne 0 ]; then
    echo "❌ RECOVERY ABORTED: Services not healthy"
    echo "Fix issues before attempting recovery."
    exit 1
fi
echo "✓ All services healthy"
echo ""

# 2. Verify database connectivity
echo "Step 2: Testing database connection..."
cd /root/catalyst-trading-mcp
docker-compose exec -T postgres psql -U catalyst_user -d catalyst_trading -c "SELECT 1;" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "❌ RECOVERY ABORTED: Database connection failed"
    exit 1
fi
echo "✓ Database connection verified"
echo ""

# 3. Test workflow endpoint manually
echo "Step 3: Testing workflow endpoint (conservative mode)..."
RESPONSE=$(curl -s -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "conservative", "max_positions": 1, "risk_per_trade": 0.005}')

if [ $? -eq 0 ]; then
    echo "✓ Workflow endpoint responding"
    echo "   Response: $RESPONSE"
else
    echo "❌ RECOVERY ABORTED: Workflow endpoint not responding"
    exit 1
fi
echo ""

# 4. Restore cron configuration
echo "Step 4: Restoring cron jobs..."
crontab /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt
echo "✓ Cron jobs restored"
echo ""

# 5. Verify cron installation
echo "Step 5: Verifying cron installation..."
CRON_COUNT=$(crontab -l | grep -c "curl.*5006")
echo "✓ Found $CRON_COUNT workflow triggers in crontab"
echo ""

# 6. Restart cron service
echo "Step 6: Restarting cron service..."
systemctl restart cron
echo "✓ Cron service restarted"
echo ""

echo "🔄 SYSTEM RECOVERY COMPLETE"
echo ""
echo "✅ System is now operational"
echo "✅ Cron jobs active and monitoring"
echo ""
echo "MONITOR LOGS:"
echo "  Trading: tail -f /var/log/catalyst/trading.log"
echo "  Health:  tail -f /var/log/catalyst/health.log"
echo ""
echo "VERIFY NEXT CRON RUN:"
echo "  grep CRON /var/log/syslog | tail -10"
```

**Make executable**:
```bash
chmod +x /root/catalyst-trading-mcp/scripts/recover-system.sh
```

**To execute**:
```bash
/root/catalyst-trading-mcp/scripts/recover-system.sh
```

---

## TROUBLESHOOTING

### Problem 1: Cron Jobs Not Executing

**Symptoms**:
- No entries in `/var/log/catalyst/trading.log`
- Health checks not running
- Services not auto-starting at scheduled time

**Diagnosis**:
```bash
# Check cron service status
systemctl status cron

# Check cron system logs
grep CRON /var/log/syslog | tail -50

# Verify crontab installed
crontab -l | head -20

# Test script manually
/root/catalyst-trading-mcp/scripts/health-check.sh
```

**Solutions**:
1. **Restart cron service**: `systemctl restart cron`
2. **Fix PATH issues**: Ensure PATH in crontab includes `/usr/local/bin`
3. **Check permissions**: `chmod +x /root/catalyst-trading-mcp/scripts/*.sh`
4. **Verify CATALYST_HOME**: Should be `/root/catalyst-trading-mcp`

---

### Problem 2: Health Checks Failing

**Symptoms**:
- Health log shows services failed
- Multiple services returning non-200 status

**Diagnosis**:
```bash
# Check Docker containers
docker-compose ps

# Test individual service
curl http://localhost:5006/health

# Check service logs
docker-compose logs workflow --tail 50
```

**Solutions**:
1. **Restart failed services**: `docker-compose restart <service-name>`
2. **Check database connection**: Verify DATABASE_URL in `.env`
3. **Review Docker logs**: `docker-compose logs --tail 100`
4. **Verify port availability**: `netstat -tlnp | grep 500[0-9]`

---

### Problem 3: Workflow API Not Responding

**Symptoms**:
- Cron runs but no workflow cycles created
- Trading log empty
- curl commands timeout

**Diagnosis**:
```bash
# Test workflow health
curl http://localhost:5006/health

# Check workflow container
docker-compose logs workflow --tail 100

# Test database connection from workflow
docker-compose exec workflow python -c "import asyncpg; print('Import OK')"
```

**Solutions**:
1. **Restart workflow service**: `docker-compose restart workflow`
2. **Check environment variables**: `docker-compose exec workflow env | grep DATABASE`
3. **Verify database pool**: Check for connection pool exhaustion
4. **Review startup logs**: `docker-compose logs workflow | grep "startup\|error"`

---

### Problem 4: Database Backup Failing

**Symptoms**:
- No backup files in `/backups/catalyst`
- Backup cron job errors in syslog

**Diagnosis**:
```bash
# Test manual backup
cd /root/catalyst-trading-mcp
docker-compose exec -T postgres pg_dump -U catalyst_user -d catalyst_trading > /tmp/test_backup.sql

# Check disk space
df -h /backups

# Verify database credentials
grep DATABASE_URL .env | sed 's/:[^@]*@/:***@/'
```

**Solutions**:
1. **Check disk space**: Ensure `/backups` has free space
2. **Verify permissions**: `chmod 755 /backups/catalyst`
3. **Test database connection**: `docker-compose exec postgres pg_isready`
4. **Fix credentials**: Update DATABASE_URL in `.env`

---

### Problem 5: Wrong Timezone

**Symptoms**:
- Jobs running at wrong times
- Market open workflows trigger too early/late

**Diagnosis**:
```bash
# Check current timezone
timedatectl

# Check system time
date

# Check what time cron thinks it is
date -d "now" "+%H:%M %Z"
```

**Solutions**:
```bash
# Set correct timezone
timedatectl set-timezone Australia/Perth

# Verify
timedatectl

# Expected output:
# Time zone: Australia/Perth (AWST, +0800)

# Restart cron to pick up timezone
systemctl restart cron
```

---

## MAINTENANCE SCHEDULE

### Daily Tasks (Automated by Cron)

- ✅ **Health checks every 15 minutes** - Monitors all 9 services
- ✅ **Auto-restart every 5 minutes** - Recovers from crashes
- ✅ **Database backup at 2:00 AM** - Daily backup to `/backups/catalyst`
- ✅ **Performance report at 6:00 AM** - JSON report generation

### Weekly Tasks (Automated by Cron)

- ✅ **Log rotation Sunday 3:00 AM** - Deletes logs >7 days old
- ✅ **Backup cleanup Sunday 3:00 AM** - Deletes backups >30 days old

### Manual Tasks (As Needed)

- 📋 **Review performance reports** - Check `/var/log/catalyst/daily_report_*.json`
- 📊 **Analyze trading outcomes** - Query database for cycle results
- 🔍 **Investigate health check failures** - Review `/var/log/catalyst/health.log`
- 🛠️ **Optimize scan parameters** - Adjust frequency/risk based on results

### Monthly Tasks

- 🔐 **Rotate API keys** - Update Alpaca, Benzinga, NewsAPI credentials
- 💾 **Verify backup integrity** - Test restore from backup file
- 📈 **Review system performance** - CPU, memory, disk usage trends
- 📋 **Update documentation** - Document any configuration changes

---

## VALIDATION CHECKLIST

### ✅ Installation Complete

- [ ] Timezone set to Australia/Perth (UTC+8)
- [ ] Directories created (`/var/log/catalyst`, `/backups/catalyst`)
- [ ] Health check script installed and executable
- [ ] Cron configuration file created
- [ ] Crontab installed successfully (`crontab -l` shows all jobs)
- [ ] Cron service running (`systemctl status cron`)
- [ ] Manual health check passes
- [ ] Manual workflow trigger succeeds

### ✅ First Market Day (Mon-Fri)

- [ ] Services auto-started at 9:00 PM Perth (4:00 AM EST)
- [ ] First workflow triggered at 10:30 PM Perth (9:30 AM EST)
- [ ] Periodic workflows executing every 30 minutes
- [ ] Health checks logging every 15 minutes
- [ ] Trading log shows activity (`/var/log/catalyst/trading.log`)
- [ ] Database contains trading_cycles records
- [ ] Market close workflow at 5:00 AM Perth (4:00 PM EST)
- [ ] Services auto-stopped at 9:00 AM Perth (8:00 PM EST)

### ✅ System Maintenance Verified

- [ ] Database backup created at 2:00 AM Perth
- [ ] Backup file exists in `/backups/catalyst/*.sql.gz`
- [ ] Health logs continuously updated
- [ ] Failed services auto-restart (test by stopping one service)
- [ ] Daily report generated at 6:00 AM Perth
- [ ] Old logs cleaned up (after 7 days)
- [ ] Old backups cleaned up (after 30 days)

### ✅ Emergency Procedures Tested

- [ ] Emergency stop script created and executable
- [ ] Emergency stop tested (outside market hours)
- [ ] Cron jobs successfully disabled
- [ ] Recovery script created and executable
- [ ] Recovery script tested successfully
- [ ] System restored to normal operation

---

## CRITICAL REMINDERS

### 🚨 Production Safety

- ⚠️ **NEVER** test emergency stop during market hours
- ⚠️ **ALWAYS** verify health before re-enabling cron
- ⚠️ **MONITOR** first 3 market days closely
- ⚠️ **BACKUP** crontab before making changes
- ⚠️ **TEST** in non-market hours when possible

### 📝 Documentation

- 📄 Log all cron configuration changes
- 📄 Document timezone-related issues
- 📄 Keep emergency procedures updated
- 📄 Record all manual interventions

### 🔐 Security

- 🔒 Cron configuration contains sensitive endpoints
- 🔒 `.env` file NEVER committed to version control
- 🔒 Database credentials secured
- 🔒 Backup files contain sensitive data
- 🔒 Restrict SSH access to droplet

### 📊 Monitoring

- 👁️ Review health logs daily
- 👁️ Check trading outcomes after each session
- 👁️ Monitor disk space weekly
- 👁️ Verify backups monthly

---

## APPENDIX: COMPLETE SCHEDULE REFERENCE

### Market Hours Operations (Mon-Fri)

```
WEEKDAY TRADING SCHEDULE:
  21:00 Perth (04:00 EST) - Start services
  22:30 Perth (09:30 EST) - Market open workflow
  23:00-04:30 Perth (10:00-15:30 EST) - Periodic workflows (every 30 min)
  05:00 Perth (16:00 EST) - Market close workflow
  09:00 Perth (20:00 EST) - Stop services
```

### Continuous Monitoring (24/7)

```
HEALTH & MAINTENANCE:
  Every 15 minutes - Health checks
  Every 5 minutes - Auto-restart failed services
  Daily 02:00 Perth - Database backup
  Daily 06:00 Perth - Performance report
  Weekly Sunday 03:00 - Log rotation
  Weekly Sunday 03:00 - Backup cleanup
```

### Files & Directories Created

```
SCRIPTS:
  /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt
  /root/catalyst-trading-mcp/scripts/health-check.sh
  /root/catalyst-trading-mcp/scripts/emergency-stop.sh
  /root/catalyst-trading-mcp/scripts/recover-system.sh

LOGS:
  /var/log/catalyst/health.log
  /var/log/catalyst/trading.log
  /var/log/catalyst/startup.log
  /var/log/catalyst/shutdown.log
  /var/log/catalyst/auto-restart.log
  /var/log/catalyst/daily_report_YYYYMMDD.json

BACKUPS:
  /backups/catalyst/catalyst_YYYYMMDD_HHMMSS.sql.gz
```

---

**END OF IMPLEMENTATION GUIDE**

This comprehensive guide provides all necessary steps to implement cron automation for the Catalyst Trading System. Follow phases sequentially and complete all validation checklists before declaring production-ready.

For additional support, refer to Catalyst Trading System Functional Specifications v6.1.0b.