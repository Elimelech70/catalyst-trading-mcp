# PRIMARY-004: Live Trading Enablement

**Name of Application**: Catalyst Trading System  
**Name of file**: PRIMARY-004-live-trading-enablement.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: Enable live trading with real capital after paper trading success  
**Timeline**: Days 11-12 of Week 8  
**Priority**: HIGH (final production deployment step)

---

## REVISION HISTORY

**v1.0.0 (2025-10-25)** - Initial Implementation Document
- Live trading prerequisites
- Conservative mode configuration
- Gradual ramp-up procedure
- Monitoring and safety protocols

---

## 1. Prerequisites (MUST BE MET)

```yaml
Paper Trading Results:
  ✅ 5+ days completed successfully
  ✅ Win rate ≥50%
  ✅ Average R:R ≥1.5:1
  ✅ Total P&L positive
  ✅ Max drawdown <10%
  ✅ No risk limit breaches

System Stability:
  ✅ Zero critical errors (5 days)
  ✅ 99%+ uptime during market hours
  ✅ All services healthy
  ✅ Database performance good
  ✅ Order execution 100% reliable

Human Readiness:
  ✅ Understand strategy completely
  ✅ Know emergency stop procedures
  ✅ Can monitor system during market hours
  ✅ Comfortable with risk parameters
  ✅ Have reviewed all paper trades
```

**⚠️ If ANY prerequisite not met → DO NOT proceed with live trading**

---

## 2. Conservative Mode Configuration

### 2.1 Initial Live Trading Parameters

```bash
# Update .env file for live trading
ALPACA_API_KEY=your_live_api_key
ALPACA_SECRET_KEY=your_live_secret_key
ALPACA_BASE_URL=https://api.alpaca.markets  # LIVE
ALPACA_MODE=live  # CRITICAL: Switch to live

# CONSERVATIVE parameters (first 3 days)
MAX_POSITIONS=3              # Reduced from 5
RISK_PER_TRADE=0.005         # 0.5% (half of paper trading)
MAX_DAILY_LOSS=0.03          # 3% (tighter than paper)
MAX_ACCOUNT_RISK=0.015       # 1.5% total exposure

# Starting capital (your actual funded amount)
LIVE_ACCOUNT_SIZE=10000      # $10k recommended minimum
```

### 2.2 Gradual Ramp-Up Schedule

```yaml
Days 1-3 (Conservative Mode):
  max_positions: 3
  risk_per_trade: 0.5%
  max_daily_loss: 3%
  goal: Validate live execution

Days 4-7 (Moderate Mode):
  max_positions: 4
  risk_per_trade: 0.75%
  max_daily_loss: 4%
  goal: Increase exposure gradually

Days 8-14 (Normal Mode):
  max_positions: 5
  risk_per_trade: 1.0%
  max_daily_loss: 5%
  goal: Full production parameters

Day 15+ (Evaluated):
  IF profitable: Continue normal mode
  IF losing: Return to conservative mode
  IF major loss: Stop and analyze
```

---

## 3. Live Trading Enablement Checklist

### 3.1 Pre-Go-Live Checklist (Day Before)

```bash
# 1. Verify Alpaca account funded
curl -H "APCA-API-KEY-ID: $LIVE_KEY" \
     -H "APCA-API-SECRET-KEY: $LIVE_SECRET" \
     https://api.alpaca.markets/v2/account

# Expected: "status": "ACTIVE", "buying_power": >=$10,000

# 2. Update environment variables
nano .env
# Change ALPACA_MODE=live
# Update API keys to LIVE keys
# Set conservative parameters

# 3. Restart services with new config
docker-compose down
docker-compose up -d

# 4. Verify live mode active
curl http://localhost:5005/api/v1/trading/status
# Expected: "mode": "live" (NOT "paper")

# 5. Final health check
./scripts/integration-test-health.sh

# 6. Test emergency stop
curl -X POST http://localhost:5006/api/v1/emergency-stop
curl -X POST http://localhost:5006/api/v1/emergency-resume

# ✅ All checks must pass before market open
```

### 3.2 Go-Live Day (Market Open)

```bash
# 30 minutes before market open (9:00 AM EST)

# 1. Final system check
docker-compose ps
./scripts/integration-test-health.sh

# 2. Verify conservative mode
curl http://localhost:5004/api/v1/risk/limits
# Expected: max_positions=3, risk_per_trade=0.005

# 3. Watch first workflow execution
tail -f /var/log/catalyst/trading.log

# 4. Monitor first trade closely
# Stay at computer for first 2 hours minimum
```

---

## 4. Intensive Monitoring (First 3 Days)

### 4.1 Real-Time Monitoring

```bash
# Terminal 1: Service logs
docker-compose logs -f workflow trading risk-manager

# Terminal 2: Position monitoring
watch -n 30 'curl -s http://localhost:5006/api/v1/positions/active | jq'

# Terminal 3: Account status
watch -n 60 'curl -s http://localhost:5005/api/v1/trading/account | jq'

# Check every 15 minutes:
# - Any errors in logs?
# - Positions sized correctly?
# - Stop losses set properly?
# - P&L tracking accurately?
```

### 4.2 Emergency Stop Procedures

**When to Stop Trading**:
```yaml
IMMEDIATE STOP:
  ❌ Daily loss exceeds 3%
  ❌ Single position loss >2%
  ❌ Critical system error
  ❌ Order execution failures
  ❌ Risk management breach
  
INVESTIGATE:
  ⚠️ Win rate drops below 40% (3+ trades)
  ⚠️ Unexpected behavior
  ⚠️ Performance warnings
```

**Emergency Stop Command**:
```bash
# SSH into droplet
ssh root@catalyst-droplet

# Execute emergency stop
curl -X POST http://localhost:5006/api/v1/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual intervention required"}'

# Verify all positions closed
curl http://localhost:5006/api/v1/positions/active
# Expected: Empty array []

# Disable cron temporarily
crontab -r

# Review logs
docker-compose logs --tail=1000 > emergency-$(date +%Y%m%d-%H%M%S).log
```

---

## 5. First Week Daily Procedures

### 5.1 Morning Routine (8:00-9:00 AM EST)

```bash
# 1. Health check
./scripts/integration-test-health.sh

# 2. Review yesterday's trades
./scripts/paper-trading-snapshot.sh  # Still works for live

# 3. Check for overnight issues
docker-compose logs --since 12h | grep -E "ERROR|CRITICAL"

# 4. Verify correct mode
curl http://localhost:5005/api/v1/trading/status
# MUST show "mode": "live"

# 5. Confirm risk parameters
curl http://localhost:5004/api/v1/risk/limits
# Verify max_positions, risk_per_trade match expectations
```

### 5.2 End of Day Routine (4:30-5:00 PM EST)

```bash
# 1. Generate daily report
./scripts/paper-trading-snapshot.sh > reports/live-$(date +%Y%m%d).txt

# 2. Review all trades
psql $DATABASE_URL -c "
SELECT 
    s.symbol,
    p.direction,
    p.entry_price,
    p.exit_price,
    p.realized_pnl,
    p.opened_at,
    p.closed_at
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'closed'
AND DATE(p.opened_at) = CURRENT_DATE
ORDER BY p.opened_at;
"

# 3. Calculate cumulative P&L
psql $DATABASE_URL -c "
SELECT 
    COUNT(*) as total_trades,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(realized_pnl), 2) as total_pnl,
    ROUND((SUM(realized_pnl) / 10000.0) * 100, 3) as return_pct
FROM positions
WHERE status = 'closed'
AND opened_at >= (CURRENT_DATE - INTERVAL '7 days');
"

# 4. Document any issues
echo "$(date): Daily review complete" >> logs/daily-review.txt

# 5. Backup database
docker-compose exec -T postgres pg_dump -U catalyst_user -d catalyst_trading | \
gzip > backups/live-$(date +%Y%m%d).sql.gz
```

---

## 6. Acceptance Criteria

### 6.1 First 3 Days (Conservative Mode)

```yaml
✅ No critical errors
✅ All trades executed correctly
✅ Stop losses always set
✅ Position sizing accurate (0.5% risk)
✅ Max 3 concurrent positions enforced
✅ No risk limit breaches
✅ Total P&L ≥ $0 (breakeven minimum)
✅ Human monitoring completed
```

### 6.2 First Week (Transition to Normal)

```yaml
✅ Win rate ≥45% (live may be lower than paper)
✅ Average R:R ≥1.3:1 (live may be lower)
✅ Max drawdown <5%
✅ System stable (no crashes)
✅ Comfortable with live trading
✅ Ready to increase parameters
```

### 6.3 First Month (Full Production)

```yaml
✅ Win rate ≥50%
✅ Average R:R ≥1.5:1
✅ Profitable overall
✅ System autonomous
✅ Minimal human intervention
✅ Ready for Research instance (if profitable 3 months)
```

---

## 7. Troubleshooting Live Trading Issues

### 7.1 Issue: Real Results Worse Than Paper

**Cause**: Slippage, commissions, market impact

**Solution**:
```yaml
Accept Reality:
  - Live trading has friction costs
  - Paper trading is optimistic
  - 5-10% performance degradation is normal

Adjustments:
  - Tighten entry criteria (be more selective)
  - Avoid illiquid stocks (>$50M daily volume)
  - Use limit orders (not market orders)
  - Factor in commissions when sizing
```

### 7.2 Issue: Emotional Stress

**Cause**: Real money at risk

**Solution**:
```yaml
Trust the System:
  - System follows rules consistently
  - Paper trading validated strategy
  - Risk management protects capital

Reduce Exposure:
  - Stay in conservative mode longer
  - Reduce position sizes further (0.25% risk)
  - Take break if overwhelmed
```

---

**END OF PRIMARY-004 IMPLEMENTATION DOCUMENT**

**Status**: Ready for implementation (AFTER PRIMARY-003 passes)  
**Estimated Effort**: 1-2 days setup, 3 days intensive monitoring  
**Dependencies**: PRIMARY-003 (paper trading success REQUIRED)  
**Result**: Production trading system operational with real capital

🎉 **PRIMARY INITIATIVE COMPLETE** - System operational!  
🎯 **NEXT**: SECONDARY Initiative (Research Instance Design)
