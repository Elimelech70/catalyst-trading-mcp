# PRIMARY-002: Full System Integration Testing

**Name of Application**: Catalyst Trading System  
**Name of file**: PRIMARY-002-system-integration-testing.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: Complete end-to-end integration testing before live trading  
**Timeline**: Days 4-5 of Week 8  
**Priority**: HIGH (validates production readiness)

---

## REVISION HISTORY

**v1.0.0 (2025-10-25)** - Initial Implementation Document
- Define integration test scenarios
- Automated workflow testing
- Service communication validation
- Database integrity checks
- Error handling verification

---

## Table of Contents

1. [Test Objectives](#1-test-objectives)
2. [Test Environment Setup](#2-test-environment-setup)
3. [Integration Test Scenarios](#3-integration-test-scenarios)
4. [Automated Test Scripts](#4-automated-test-scripts)
5. [Acceptance Criteria](#5-acceptance-criteria)

---

## 1. Test Objectives

### 1.1 What We're Testing

```yaml
Service Integration:
  ✓ 9 services communicate correctly
  ✓ REST APIs respond within SLA
  ✓ Database connections stable
  ✓ Foreign key relationships maintained
  ✓ Error propagation works
  
Workflow Automation:
  ✓ Cron triggers workflows successfully
  ✓ 100→35→20→10→5 pipeline functions
  ✓ News catalyst filtering works
  ✓ Pattern recognition identifies setups
  ✓ Risk management enforces limits
  
Data Integrity:
  ✓ No orphaned records
  ✓ Referential integrity maintained
  ✓ Timestamps accurate
  ✓ Normalized structure preserved
  
Performance:
  ✓ Response times meet targets
  ✓ Database queries optimized
  ✓ No connection pool exhaustion
  ✓ Memory usage within limits
```

### 1.2 Success Criteria

**Must Pass**:
- All 9 services healthy simultaneously
- 5 consecutive successful workflow executions
- Zero critical errors in logs
- Database integrity checks pass
- Response times within SLA

**Nice to Have**:
- Zero warnings in logs
- Sub-100ms response times
- Zero database connection retries

---

## 2. Test Environment Setup

### 2.1 Prerequisites

```bash
# Verify all services running
docker-compose ps

# Expected output:
# orchestration     running
# workflow          running
# scanner           running
# pattern           running
# technical         running
# risk-manager      running
# trading           running
# news              running
# reporting         running

# Verify database accessible
psql $DATABASE_URL -c "SELECT COUNT(*) FROM securities;"

# Verify cron configured
crontab -l | grep catalyst
```

### 2.2 Test Data Preparation

```sql
-- Insert test securities (if not already present)
INSERT INTO securities (symbol, name, sector_id, is_active)
VALUES 
    ('AAPL', 'Apple Inc', 1, TRUE),
    ('TSLA', 'Tesla Inc', 2, TRUE),
    ('NVDA', 'NVIDIA Corp', 1, TRUE)
ON CONFLICT (symbol) DO NOTHING;

-- Verify test data
SELECT security_id, symbol, name FROM securities 
WHERE symbol IN ('AAPL', 'TSLA', 'NVDA');
```

---

## 3. Integration Test Scenarios

### 3.1 Scenario 1: Morning Market Open Workflow

**Trigger**: Simulated cron job (10:30 PM Perth = 9:30 AM EST)

**Test Steps**:
```bash
# Step 1: Trigger workflow manually
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "normal",
    "scan_frequency": 300,
    "max_positions": 5,
    "risk_per_trade": 0.01
  }'

# Expected response:
{
  "cycle_id": "uuid",
  "mode": "normal",
  "status": "scanning",
  "started_at": "2025-10-25T09:30:00Z"
}

# Step 2: Monitor workflow progress
watch -n 5 'curl -s http://localhost:5006/api/v1/workflow/status/CYCLE_ID'

# Expected stages:
# "scanning" → "filtering" → "analyzing" → "executing" → "completed"

# Step 3: Verify database updates
psql $DATABASE_URL -c "
SELECT 
    tc.cycle_id,
    tc.status,
    tc.candidates_scanned,
    tc.positions_opened,
    tc.completed_at
FROM trading_cycles tc
WHERE tc.cycle_id = 'CYCLE_ID';
"

# Expected: Row exists with accurate counts
```

**Validation Checks**:
```yaml
Service Communication:
  ✓ Workflow → Scanner (HTTP 200)
  ✓ Scanner → News (HTTP 200)
  ✓ Scanner → Pattern (HTTP 200)
  ✓ Pattern → Technical (HTTP 200)
  ✓ Workflow → Risk Manager (HTTP 200)
  ✓ Risk Manager → Trading (HTTP 200)
  
Database Operations:
  ✓ trading_cycles row created
  ✓ scan_results rows inserted
  ✓ positions rows inserted (if trades executed)
  ✓ orders rows inserted (if trades executed)
  
Timing:
  ✓ Full cycle completes in <5 minutes
  ✓ Scanner processes 100 candidates in <10 seconds
  ✓ Pattern recognition per symbol <2 seconds
  ✓ Risk validation <500ms
```

---

### 3.2 Scenario 2: News Catalyst Filtering

**Objective**: Verify news service filters candidates correctly

**Test Steps**:
```bash
# Step 1: Check recent news
curl http://localhost:5008/api/v1/news/recent?hours=24

# Expected: JSON array of news articles with sentiment

# Step 2: Filter candidates by catalyst
curl -X POST http://localhost:5008/api/v1/news/filter \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA", "NVDA", "GME", "AMC"],
    "catalyst_types": ["earnings", "fda", "merger"],
    "min_sentiment_score": 0.6
  }'

# Expected: Filtered list with only strong catalysts

# Step 3: Verify database storage
psql $DATABASE_URL -c "
SELECT 
    s.symbol,
    ns.headline,
    ns.sentiment_score,
    ns.catalyst_type,
    ns.published_at
FROM news_sentiment ns
JOIN securities s ON s.security_id = ns.security_id
WHERE ns.published_at > NOW() - INTERVAL '24 hours'
ORDER BY ns.sentiment_score DESC
LIMIT 10;
"
```

**Validation Checks**:
```yaml
News Service:
  ✓ Fetches news from Benzinga/NewsAPI
  ✓ Calculates sentiment scores
  ✓ Identifies catalyst types
  ✓ Stores normalized data (security_id FK)
  
Filtering Logic:
  ✓ Removes low-quality sources
  ✓ Prioritizes strong catalysts
  ✓ Handles missing data gracefully
  ✓ Returns results in <1 second
```

---

### 3.3 Scenario 3: Pattern Recognition Pipeline

**Objective**: Verify pattern service identifies valid setups

**Test Steps**:
```bash
# Step 1: Request pattern analysis
curl -X POST http://localhost:5002/api/v1/pattern/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "timeframe": "5min",
    "patterns": ["bull_flag", "ascending_triangle", "breakout"]
  }'

# Expected: Detected patterns with confidence scores

# Step 2: Verify against historical data
curl "http://localhost:5001/api/v1/scanner/history?symbol=AAPL&days=1"

# Expected: OHLCV data matches pattern requirements

# Step 3: Check database storage
psql $DATABASE_URL -c "
SELECT 
    sr.scan_id,
    s.symbol,
    sr.pattern_detected,
    sr.pattern_confidence,
    sr.technical_score,
    sr.news_score,
    sr.composite_score
FROM scan_results sr
JOIN securities s ON s.security_id = sr.security_id
WHERE s.symbol = 'AAPL'
AND sr.scan_date = CURRENT_DATE
ORDER BY sr.composite_score DESC;
"
```

**Validation Checks**:
```yaml
Pattern Service:
  ✓ Fetches OHLCV data correctly
  ✓ Detects valid patterns (bull flag, triangle, etc.)
  ✓ Calculates confidence scores
  ✓ Processes in <2 seconds per symbol
  
Technical Service:
  ✓ Calculates indicators (EMA, RSI, VWAP, MACD)
  ✓ Returns accurate values
  ✓ Handles missing data
  ✓ Responds in <1 second
```

---

### 3.4 Scenario 4: Risk Management Validation

**Objective**: Ensure risk manager enforces limits

**Test Steps**:
```bash
# Step 1: Check current risk limits
curl http://localhost:5004/api/v1/risk/limits

# Expected:
{
  "max_positions": 5,
  "max_risk_per_trade": 0.01,
  "max_daily_loss": 0.05,
  "current_positions": 0,
  "current_risk": 0.0,
  "available_capacity": 5
}

# Step 2: Simulate position request
curl -X POST http://localhost:5004/api/v1/risk/validate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "direction": "long",
    "entry_price": 150.00,
    "stop_loss": 148.50,
    "position_size": 100,
    "account_size": 10000
  }'

# Expected: Validation result with approval/rejection

# Step 3: Test limit breach scenario
curl -X POST http://localhost:5004/api/v1/risk/validate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "direction": "long",
    "entry_price": 150.00,
    "stop_loss": 100.00,
    "position_size": 1000,
    "account_size": 10000
  }'

# Expected: REJECTION (risk too high)
```

**Validation Checks**:
```yaml
Risk Manager:
  ✓ Enforces max positions (5)
  ✓ Enforces max risk per trade (1%)
  ✓ Enforces max daily loss (5%)
  ✓ Rejects oversized positions
  ✓ Logs risk events
  ✓ Responds in <500ms
```

---

### 3.5 Scenario 5: Order Execution (Paper Trading)

**Objective**: Verify trading service executes orders correctly

**Test Steps**:
```bash
# Step 1: Check Alpaca connection
curl http://localhost:5005/api/v1/trading/status

# Expected:
{
  "connected": true,
  "mode": "paper",
  "account_status": "ACTIVE",
  "buying_power": 100000.00
}

# Step 2: Place paper trade
curl -X POST http://localhost:5005/api/v1/trading/order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "qty": 10,
    "side": "buy",
    "type": "limit",
    "limit_price": 150.00,
    "time_in_force": "day"
  }'

# Expected: Order confirmation with Alpaca order ID

# Step 3: Monitor order status
curl http://localhost:5005/api/v1/trading/orders/ORDER_ID

# Expected: Order status updates (new → filled/cancelled)

# Step 4: Verify database records
psql $DATABASE_URL -c "
SELECT 
    o.order_id,
    s.symbol,
    o.side,
    o.quantity,
    o.price,
    o.status,
    o.created_at,
    o.filled_at
FROM orders o
JOIN securities s ON s.security_id = o.security_id
WHERE o.order_id = 'ORDER_ID';
"
```

**Validation Checks**:
```yaml
Trading Service:
  ✓ Connects to Alpaca (paper mode)
  ✓ Places orders successfully
  ✓ Receives order confirmations
  ✓ Tracks order status
  ✓ Stores normalized data
  ✓ Handles order rejections gracefully
```

---

## 4. Automated Test Scripts

### 4.1 Health Check Script

**File**: `scripts/integration-test-health.sh`

```bash
#!/bin/bash
# Integration test: Health checks across all services

echo "=========================================="
echo "Catalyst Trading System - Health Checks"
echo "=========================================="

SERVICES=(
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

FAILED=0

for service in "${SERVICES[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"
    
    echo -n "Testing $name (port $port)... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health)
    
    if [ "$response" == "200" ]; then
        echo "✓ OK"
    else
        echo "✗ FAILED (HTTP $response)"
        FAILED=$((FAILED + 1))
    fi
done

echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "✓ All services healthy"
    exit 0
else
    echo "✗ $FAILED services failed"
    exit 1
fi
```

---

### 4.2 Workflow Test Script

**File**: `scripts/integration-test-workflow.sh`

```bash
#!/bin/bash
# Integration test: Complete workflow execution

echo "=========================================="
echo "Testing Complete Trading Workflow"
echo "=========================================="

# Step 1: Start workflow
echo "Starting workflow..."
CYCLE_RESPONSE=$(curl -s -X POST http://localhost:5006/api/v1/workflow/start \
    -H "Content-Type: application/json" \
    -d '{"mode": "normal", "max_positions": 3, "risk_per_trade": 0.005}')

CYCLE_ID=$(echo $CYCLE_RESPONSE | jq -r '.cycle_id')
echo "Cycle ID: $CYCLE_ID"

# Step 2: Monitor progress (30 second intervals, max 5 minutes)
TIMEOUT=300
ELAPSED=0
INTERVAL=30

while [ $ELAPSED -lt $TIMEOUT ]; do
    echo "Checking status... (${ELAPSED}s elapsed)"
    
    STATUS=$(curl -s http://localhost:5006/api/v1/workflow/status/$CYCLE_ID | jq -r '.status')
    
    echo "  Status: $STATUS"
    
    if [ "$STATUS" == "completed" ]; then
        echo "✓ Workflow completed successfully"
        break
    elif [ "$STATUS" == "error" ]; then
        echo "✗ Workflow failed"
        exit 1
    fi
    
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "✗ Workflow timeout (>5 minutes)"
    exit 1
fi

# Step 3: Verify database records
echo "Verifying database records..."

CYCLE_EXISTS=$(psql $DATABASE_URL -t -c \
    "SELECT COUNT(*) FROM trading_cycles WHERE cycle_id = '$CYCLE_ID';")

if [ $CYCLE_EXISTS -gt 0 ]; then
    echo "✓ Cycle record exists in database"
else
    echo "✗ Cycle record missing"
    exit 1
fi

echo "=========================================="
echo "✓ Integration test PASSED"
exit 0
```

---

### 4.3 Database Integrity Test

**File**: `scripts/integration-test-database.sh`

```bash
#!/bin/bash
# Integration test: Database integrity checks

echo "=========================================="
echo "Database Integrity Tests"
echo "=========================================="

# Test 1: Referential integrity
echo "Test 1: Checking referential integrity..."

ORPHANED_POSITIONS=$(psql $DATABASE_URL -t -c "
SELECT COUNT(*) FROM positions p
WHERE NOT EXISTS (
    SELECT 1 FROM securities s WHERE s.security_id = p.security_id
);")

if [ $ORPHANED_POSITIONS -eq 0 ]; then
    echo "✓ No orphaned positions"
else
    echo "✗ Found $ORPHANED_POSITIONS orphaned positions"
    exit 1
fi

# Test 2: Normalization check
echo "Test 2: Verifying normalization..."

SYMBOL_DUPLICATES=$(psql $DATABASE_URL -t -c "
SELECT COUNT(*) FROM (
    SELECT symbol, COUNT(*) as cnt
    FROM securities
    GROUP BY symbol
    HAVING COUNT(*) > 1
) sub;")

if [ $SYMBOL_DUPLICATES -eq 0 ]; then
    echo "✓ No duplicate symbols"
else
    echo "✗ Found $SYMBOL_DUPLICATES duplicate symbols"
    exit 1
fi

# Test 3: Data consistency
echo "Test 3: Checking data consistency..."

INVALID_TIMESTAMPS=$(psql $DATABASE_URL -t -c "
SELECT COUNT(*) FROM trading_cycles
WHERE completed_at < started_at;")

if [ $INVALID_TIMESTAMPS -eq 0 ]; then
    echo "✓ All timestamps valid"
else
    echo "✗ Found $INVALID_TIMESTAMPS invalid timestamps"
    exit 1
fi

echo "=========================================="
echo "✓ All database integrity tests PASSED"
exit 0
```

---

## 5. Acceptance Criteria

### 5.1 Technical Acceptance

```yaml
Service Health:
  ✅ All 9 services return HTTP 200 on /health
  ✅ Docker containers running (not restarting)
  ✅ No critical errors in logs (last 24 hours)
  ✅ CPU usage <70% per container
  ✅ Memory usage <80% per container
  
Workflow Execution:
  ✅ 5 consecutive successful cycles
  ✅ Pipeline processes 100→35→20→10→5
  ✅ News filtering operational
  ✅ Pattern recognition working
  ✅ Risk validation enforced
  ✅ Orders execute (paper mode)
  
Database Integrity:
  ✅ Zero orphaned records
  ✅ All FKs valid
  ✅ Normalization maintained
  ✅ Timestamps accurate
  ✅ Connection pool <20 concurrent
  
Performance:
  ✅ Resource queries <200ms
  ✅ Workflow cycle <5 minutes
  ✅ Scanner processes 100 stocks <10s
  ✅ Pattern analysis <2s per symbol
```

### 5.2 Functional Acceptance

```yaml
End-to-End Workflow:
  ✅ Cron triggers workflow
  ✅ Scanner identifies candidates
  ✅ News service filters by catalyst
  ✅ Pattern service detects setups
  ✅ Technical service calculates indicators
  ✅ Risk manager validates trades
  ✅ Trading service places orders (paper)
  ✅ Reporting service generates summary
  
Error Handling:
  ✅ Service failures don't crash system
  ✅ Database errors logged correctly
  ✅ API errors return proper HTTP codes
  ✅ Retry logic works for transient failures
  
Data Flow:
  ✅ Data flows Scanner → Pattern → Technical → Risk → Trading
  ✅ Database updates after each stage
  ✅ Logs capture decision points
  ✅ No data loss during workflow
```

### 5.3 Business Acceptance

```yaml
Production Readiness:
  ✅ System runs autonomously (no human intervention)
  ✅ Cron automation reliable
  ✅ Risk management enforced
  ✅ Paper trading results validate strategy
  ✅ No financial risk (paper mode only)
  ✅ Foundation ready for live trading
```

---

**END OF PRIMARY-002 IMPLEMENTATION DOCUMENT**

**Status**: Ready for implementation  
**Estimated Effort**: 3-4 days  
**Dependencies**: PRIMARY-001 (optional - can run without Claude Desktop)  
**Blocking**: PRIMARY-003 (paper trading validation)

🎯 **Next Document**: PRIMARY-003-paper-trading-validation.md
