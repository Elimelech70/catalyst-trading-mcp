# PRIMARY-003: Paper Trading Validation

**Name of Application**: Catalyst Trading System  
**Name of file**: PRIMARY-003-paper-trading-validation.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: 1-week paper trading validation before live trading  
**Timeline**: Days 6-10 of Week 8 (5 trading days minimum)  
**Priority**: CRITICAL (validates strategy before real money)

---

## REVISION HISTORY

**v1.0.0 (2025-10-25)** - Initial Implementation Document
- Paper trading requirements
- Performance metrics tracking
- Strategy validation criteria
- Risk management verification
- Go/No-Go decision framework

---

## Table of Contents

1. [Paper Trading Objectives](#1-paper-trading-objectives)
2. [Validation Metrics](#2-validation-metrics)
3. [Daily Monitoring Procedures](#3-daily-monitoring-procedures)
4. [Go/No-Go Decision Criteria](#4-gono-go-decision-criteria)
5. [Acceptance Criteria](#5-acceptance-criteria)

---

## 1. Paper Trading Objectives

### 1.1 What We're Validating

```yaml
Strategy Validation:
  ✓ Ross Cameron momentum methodology works
  ✓ News catalyst filtering adds edge
  ✓ Pattern recognition identifies valid setups
  ✓ Technical indicators confirm entries
  ✓ Risk management prevents large losses
  
System Reliability:
  ✓ Cron automation executes reliably
  ✓ Services remain stable during market hours
  ✓ Database operations perform well under load
  ✓ No critical errors during trading
  ✓ Orders execute without issues
  
Performance Targets:
  ✓ Win rate ≥50% (Ross Cameron baseline)
  ✓ Average R:R ≥2:1 (momentum trading standard)
  ✓ Max drawdown <5% of account
  ✓ Daily trades: 5-10 range (not over-trading)
  ✓ No single loss >1.5% of account
```

### 1.2 Paper Trading Configuration

```bash
# Configure Alpaca for paper trading
# In .env file:

ALPACA_API_KEY=your_paper_api_key
ALPACA_SECRET_KEY=your_paper_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_MODE=paper

# Paper account settings
PAPER_ACCOUNT_SIZE=100000  # $100k starting capital
MAX_POSITIONS=5            # Conservative start
RISK_PER_TRADE=0.01       # 1% risk per trade
MAX_DAILY_LOSS=0.05       # 5% max daily drawdown
```

---

## 2. Validation Metrics

### 2.1 Daily Performance Tracking

**Track These Metrics Daily**:

```sql
-- Daily P&L Summary
SELECT 
    DATE(p.opened_at) as trade_date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN p.realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN p.realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
    ROUND(AVG(CASE WHEN p.realized_pnl > 0 THEN p.realized_pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN p.realized_pnl < 0 THEN ABS(p.realized_pnl) END), 2) as avg_loss,
    ROUND(SUM(p.realized_pnl), 2) as daily_pnl,
    ROUND((SUM(p.realized_pnl) / 100000.0) * 100, 3) as daily_return_pct
FROM positions p
WHERE p.status = 'closed'
AND DATE(p.opened_at) = CURRENT_DATE
GROUP BY DATE(p.opened_at);

-- Win Rate Calculation
SELECT 
    ROUND(
        (SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)::float / 
         COUNT(*)::float) * 100, 
        2
    ) as win_rate_pct
FROM positions
WHERE status = 'closed'
AND opened_at >= CURRENT_DATE - INTERVAL '7 days';

-- Average R:R Ratio
SELECT 
    ROUND(
        AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END) / 
        AVG(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) END),
        2
    ) as avg_risk_reward_ratio
FROM positions
WHERE status = 'closed'
AND opened_at >= CURRENT_DATE - INTERVAL '7 days';

-- Max Drawdown
WITH daily_pnl AS (
    SELECT 
        DATE(opened_at) as trade_date,
        SUM(realized_pnl) as daily_pnl
    FROM positions
    WHERE status = 'closed'
    GROUP BY DATE(opened_at)
    ORDER BY DATE(opened_at)
),
cumulative_pnl AS (
    SELECT 
        trade_date,
        daily_pnl,
        SUM(daily_pnl) OVER (ORDER BY trade_date) as cumulative_pnl,
        MAX(SUM(daily_pnl) OVER (ORDER BY trade_date)) OVER (ORDER BY trade_date) as peak_balance
    FROM daily_pnl
)
SELECT 
    MAX(peak_balance - cumulative_pnl) as max_drawdown,
    ROUND((MAX(peak_balance - cumulative_pnl) / 100000.0) * 100, 2) as max_drawdown_pct
FROM cumulative_pnl;
```

### 2.2 Performance Dashboard

**Create Daily Snapshot**:

```bash
#!/bin/bash
# scripts/paper-trading-snapshot.sh

DATE=$(date +%Y-%m-%d)
echo "=========================================="
echo "Paper Trading Snapshot - $DATE"
echo "=========================================="

# Total P&L
psql $DATABASE_URL -c "
SELECT 
    COUNT(*) as trades,
    ROUND(SUM(realized_pnl), 2) as total_pnl,
    ROUND((SUM(realized_pnl) / 100000.0) * 100, 3) as return_pct
FROM positions
WHERE status = 'closed';
" -t

# Win Rate
psql $DATABASE_URL -c "
SELECT 
    ROUND(
        (SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)::float / 
         COUNT(*)::float) * 100, 
        2
    ) as win_rate_pct
FROM positions
WHERE status = 'closed';
" -t

# Average R:R
psql $DATABASE_URL -c "
SELECT 
    ROUND(
        AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END) / 
        AVG(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) END),
        2
    ) as avg_rr
FROM positions
WHERE status = 'closed';
" -t

echo "=========================================="
```

---

## 3. Daily Monitoring Procedures

### 3.1 Pre-Market Checklist (8:00 AM EST)

```bash
# 1. Verify all services healthy
docker-compose ps
./scripts/integration-test-health.sh

# 2. Check database connections
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM pg_stat_activity 
WHERE datname = 'catalyst_trading';
"
# Should be <10 connections

# 3. Verify Alpaca connection
curl http://localhost:5005/api/v1/trading/status
# Should show "connected": true, "mode": "paper"

# 4. Review yesterday's performance
./scripts/paper-trading-snapshot.sh

# 5. Check for any errors overnight
docker-compose logs --since 12h | grep ERROR

# ✅ If all checks pass: Ready for market open
# ❌ If any checks fail: Investigate before trading
```

### 3.2 Market Hours Monitoring (9:30 AM - 4:00 PM EST)

```bash
# Every 30 minutes: Quick health check
curl http://localhost:5006/health

# Every 2 hours: Review current positions
curl http://localhost:5006/api/v1/positions/active

# Check for any warnings/errors
docker-compose logs --since 30m | grep -E "ERROR|WARNING"

# Monitor system resources
docker stats --no-stream
```

### 3.3 After-Market Analysis (4:30 PM EST)

```bash
# 1. Generate daily report
./scripts/paper-trading-snapshot.sh > reports/$(date +%Y-%m-%d).txt

# 2. Review all trades
psql $DATABASE_URL -c "
SELECT 
    s.symbol,
    p.direction,
    p.entry_price,
    p.exit_price,
    p.quantity,
    p.realized_pnl,
    ROUND((p.realized_pnl / (p.entry_price * p.quantity)) * 100, 2) as return_pct,
    p.opened_at,
    p.closed_at,
    EXTRACT(EPOCH FROM (p.closed_at - p.opened_at))/60 as hold_time_minutes
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'closed'
AND DATE(p.opened_at) = CURRENT_DATE
ORDER BY p.opened_at;
"

# 3. Identify best/worst trades
echo "TOP 3 WINNERS:"
psql $DATABASE_URL -c "
SELECT s.symbol, ROUND(p.realized_pnl, 2) as profit
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'closed'
AND DATE(p.opened_at) = CURRENT_DATE
ORDER BY p.realized_pnl DESC
LIMIT 3;
"

echo "TOP 3 LOSERS:"
psql $DATABASE_URL -c "
SELECT s.symbol, ROUND(p.realized_pnl, 2) as loss
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'closed'
AND DATE(p.opened_at) = CURRENT_DATE
ORDER BY p.realized_pnl ASC
LIMIT 3;
"

# 4. Check for any rule violations
psql $DATABASE_URL -c "
SELECT 
    re.event_type,
    re.description,
    re.occurred_at
FROM risk_events re
WHERE DATE(re.occurred_at) = CURRENT_DATE
AND re.severity IN ('high', 'critical');
"

# 5. Backup database
docker-compose exec -T postgres pg_dump -U catalyst_user -d catalyst_trading | \
gzip > backups/paper-trading-$(date +%Y%m%d).sql.gz
```

---

## 4. Go/No-Go Decision Criteria

### 4.1 Minimum Requirements (MUST MEET ALL)

```yaml
Technical Requirements:
  ✅ System uptime: 99%+ during market hours (5 days)
  ✅ Zero critical errors
  ✅ All services stable (no restarts)
  ✅ Database performance acceptable (<20 connections)
  ✅ Order execution 100% success rate
  
Trading Requirements:
  ✅ Total trades: 15-50 range (not over/under trading)
  ✅ Win rate: ≥50% minimum
  ✅ Average R:R: ≥1.5:1 minimum
  ✅ Max single loss: <2% of account
  ✅ Max drawdown: <10% of account
  ✅ Positive total P&L (profitable overall)
  
Risk Management:
  ✅ No risk limit breaches
  ✅ Max 5 concurrent positions enforced
  ✅ Stop losses always set
  ✅ Position sizing correct (1% risk)
  ✅ No manual interventions required
```

### 4.2 Target Performance (DESIRED)

```yaml
Excellent Performance:
  🎯 Win rate: ≥60%
  🎯 Average R:R: ≥2:1
  🎯 Max drawdown: <5%
  🎯 Daily trades: 5-10 range
  🎯 Total return: +5% to +15%
  
Good Performance:
  👍 Win rate: 50-60%
  👍 Average R:R: 1.5-2:1
  👍 Max drawdown: 5-10%
  👍 Daily trades: 3-12 range
  👍 Total return: +1% to +5%
  
Acceptable Performance:
  ✅ Win rate: 50%
  ✅ Average R:R: 1.5:1
  ✅ Max drawdown: <10%
  ✅ Daily trades: 2-15 range
  ✅ Total return: >0%
```

### 4.3 Go/No-Go Decision Tree

```
After 5 Trading Days:

IF (Win Rate ≥50% AND Avg R:R ≥1.5 AND Max DD <10% AND Total P&L >0):
    DECISION: GO (proceed to live trading)
    ACTION: PRIMARY-004-live-trading-enablement.md
    CONFIDENCE: High
    
ELIF (Win Rate 45-50% AND Total P&L >0):
    DECISION: EXTEND (3 more days paper trading)
    ACTION: Continue monitoring, tune parameters
    CONFIDENCE: Medium
    
ELIF (Win Rate <45% OR Total P&L <0):
    DECISION: NO-GO (strategy needs work)
    ACTION: Analyze failures, adjust strategy
    CONFIDENCE: Low (not ready for live trading)
    
ELIF (System Errors OR Risk Breaches):
    DECISION: NO-GO (system not stable)
    ACTION: Fix technical issues first
    CONFIDENCE: Not assessed (technical problems)
```

---

## 5. Acceptance Criteria

### 5.1 Technical Acceptance

```yaml
System Stability:
  ✅ 5 consecutive days without critical errors
  ✅ All services running continuously
  ✅ Database performance stable
  ✅ Order execution 100% reliable
  ✅ Cron automation working flawlessly
  
Data Quality:
  ✅ All trades logged correctly
  ✅ P&L calculations accurate
  ✅ Timestamps valid
  ✅ Database integrity maintained
  ✅ No missing or orphaned records
```

### 5.2 Trading Performance Acceptance

```yaml
Strategy Validation:
  ✅ Win rate ≥50%
  ✅ Average R:R ≥1.5:1
  ✅ Positive total P&L
  ✅ Max drawdown <10%
  ✅ Risk management enforced
  
Pattern Validation:
  ✅ Candidates identified daily (100+ scanned)
  ✅ News catalysts filter effectively (100→35)
  ✅ Patterns detected correctly (35→20)
  ✅ Technical confirmation works (20→10)
  ✅ Final selection valid (10→5)
```

### 5.3 Business Acceptance

```yaml
Production Readiness:
  ✅ Strategy proven profitable (paper mode)
  ✅ System operates autonomously
  ✅ Risk controls effective
  ✅ No unexpected behaviors
  ✅ Confidence to deploy real capital
  
Documentation:
  ✅ Daily performance logs saved
  ✅ All trades documented
  ✅ Best/worst trades analyzed
  ✅ Lessons learned captured
  ✅ Parameters tuned if needed
```

---

## 6. Common Issues & Troubleshooting

### 6.1 Poor Win Rate (<50%)

**Symptoms**: More losing trades than winning trades

**Possible Causes**:
1. News catalyst filter too loose (allowing weak catalysts)
2. Pattern recognition confidence threshold too low
3. Technical confirmation not strict enough
4. Entry timing suboptimal (chasing breakouts)

**Solutions**:
```yaml
Tighten Filters:
  - Increase news sentiment threshold (0.6 → 0.7)
  - Increase pattern confidence threshold (0.6 → 0.7)
  - Require stronger technical confirmation
  - Wait for pullback entries (not breakout chases)
  
Verify Data Quality:
  - Check if news data is accurate
  - Validate pattern detection logic
  - Review technical indicator calculations
```

### 6.2 Poor Risk:Reward (<1.5:1)

**Symptoms**: Wins too small, losses too large

**Possible Causes**:
1. Stop losses too tight (getting stopped out early)
2. Profit targets too close (taking profits too soon)
3. Not letting winners run
4. Cutting winners short

**Solutions**:
```yaml
Adjust Targets:
  - Widen stop losses (1.5R → 2R)
  - Set profit targets to 3R minimum
  - Trail stops on winning trades
  - Hold for larger moves (Ross Cameron targets 3-5R)
```

### 6.3 Over-Trading (>15 trades/day)

**Symptoms**: Too many positions opened

**Possible Causes**:
1. Filters too loose (finding too many "opportunities")
2. Scan frequency too high
3. FOMO causing entries on marginal setups

**Solutions**:
```yaml
Reduce Frequency:
  - Increase scan interval (30min → 1hr)
  - Tighten candidate filters
  - Require ALL criteria met (news + pattern + technical)
  - Reduce max_positions (5 → 3)
```

---

## 7. Paper Trading Success Story Example

**Hypothetical 5-Day Results (Target)**:

```
Day 1 (Monday):
  Trades: 7
  Wins: 4 (57%)
  Losses: 3
  P&L: +$1,245
  Best: TSLA +$650
  Worst: NVDA -$380

Day 2 (Tuesday):
  Trades: 5
  Wins: 3 (60%)
  Losses: 2
  P&L: +$890
  Best: AAPL +$520
  Worst: AMD -$280

Day 3 (Wednesday):
  Trades: 8
  Wins: 5 (62.5%)
  Losses: 3
  P&L: +$1,520
  Best: GME +$780
  Worst: F -$320

Day 4 (Thursday):
  Trades: 6
  Wins: 3 (50%)
  Losses: 3
  P&L: +$340
  Best: META +$480
  Worst: NFLX -$410

Day 5 (Friday):
  Trades: 4
  Wins: 3 (75%)
  Losses: 1
  P&L: +$1,105
  Best: MSFT +$620
  Worst: DIS -$275

========================================
WEEK SUMMARY:
  Total Trades: 30
  Total Wins: 18 (60%)
  Total Losses: 12
  Total P&L: +$5,100 (+5.1% of $100k account)
  Average Win: +$505
  Average Loss: -$344
  Average R:R: 1.47:1 (close to 1.5:1 target)
  Max Drawdown: -2.8% (Day 4 intraday)
  
DECISION: GO ✅
  - Win rate above 50% ✓
  - R:R close to 1.5:1 ✓
  - Max DD <10% ✓
  - Profitable overall ✓
  - System stable ✓
  
NEXT STEP: PRIMARY-004 (Live Trading Enablement)
```

---

**END OF PRIMARY-003 IMPLEMENTATION DOCUMENT**

**Status**: Ready for implementation  
**Estimated Effort**: 5 trading days (1 week)  
**Dependencies**: PRIMARY-002 (integration testing)  
**Blocking**: PRIMARY-004 (live trading enablement)

🎯 **Next Document**: PRIMARY-004-live-trading-enablement.md
