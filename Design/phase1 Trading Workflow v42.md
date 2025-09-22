# Catalyst Trading System - Phase 1 Trading Workflow

**Name of Application**: Catalyst Trading System  
**Name of file**: phase1-trading-workflow.md  
**Version**: 4.1.0  
**Last Updated**: 2025-09-22  
**Purpose**: Complete Phase 1 trading workflow specification with DevGenius hat on! 🎩

**REVISION HISTORY:**
v4.1.0 (2025-09-22) - Phase 1 workflow documentation  
- Complete workflow state machine
- Service orchestration patterns
- Claude interaction specifications
- Risk management integration

---

## 🎯 Phase 1 Overview

Phase 1 establishes the foundational trading workflow with **basic market data enhancement** focusing on real-time execution and pattern recognition. This phase operates with a **scan-to-trade pipeline** that processes 100 securities down to 5 final trading candidates.

### Core Objectives
- **Real-time market scanning** every 3-15 minutes
- **Pattern-based signal generation** with 60%+ win rate target
- **Risk-managed position sizing** with 1-2% account risk per trade
- **Automated stop-loss management** with trailing functionality

---

## 🔄 Trading Cycle State Machine

### State Flow Diagram
```
[IDLE] → start_trading_cycle → [INITIALIZING]
    ↓
[PRE-MARKET] → 09:30 ET → [MARKET-OPEN]
    ↓
[ACTIVE-TRADING] ⟷ continuous scanning ⟷ [MONITORING]
    ↓                                      ↓
[EXECUTING] ← pending signals found ← [ANALYZING]
    ↓                                      ↓
[MONITORING] → 15:45 ET → [CLOSING-POSITIONS]
    ↓
[AFTER-HOURS] → stop_trading → [IDLE]
```

### State Descriptions

**IDLE**: System ready, no active trading cycle
**INITIALIZING**: Services starting, health checks, configuration validation
**PRE-MARKET**: Collecting overnight news, analyzing gap conditions
**MARKET-OPEN**: Initial market scan, establishing baseline conditions
**ACTIVE-TRADING**: Main operational state with continuous workflow loop
**SCANNING**: Scanning 100 securities for opportunities
**ANALYZING**: Pattern recognition and technical analysis on candidates
**EXECUTING**: Placing trades for qualified signals
**MONITORING**: Position management and risk monitoring
**CLOSING-POSITIONS**: End-of-day position management
**AFTER-HOURS**: Post-market analysis and cycle cleanup

---

## 🚀 Detailed Workflow Phases

### Phase A: Trading Cycle Initialization

#### A1: Start Trading Cycle (Claude Command)
```
User: "Start aggressive day trading with tight stops"
Claude → start_trading_cycle(
    mode="aggressive",
    max_positions=5,
    risk_level=0.02
)
```

**System Actions:**
1. **Generate cycle ID**: `cycle_20250922_093000`
2. **Set scan frequency**: 60s (aggressive), 300s (normal), 900s (conservative)
3. **Initialize workflow state**: `WorkflowState.SCANNING`
4. **Health check all services**: Scanner, Pattern, Technical, Trading, News
5. **Start orchestration loop**: Background async task

#### A2: Service Health Validation
```yaml
Services Required:
  - orchestration-service (5000): ✅ Healthy
  - scanner-service (5001): ✅ Healthy  
  - pattern-service (5002): ✅ Healthy
  - technical-analysis (5003): ✅ Healthy
  - trading-execution (5005): ✅ Healthy
  - news-intelligence (5008): ✅ Healthy
  - reporting-service (5009): ✅ Healthy
```

---

### Phase B: Market Scanning Phase

#### B1: Initial Market Scan (100 Securities)
**Workflow State**: `SCANNING`

**Scanner Service Execution:**
```python
# Orchestration → Scanner Service
POST http://localhost:5001/scan
{
    "mode": "aggressive",
    "max_candidates": 100,
    "filters": {
        "min_volume": 1000000,
        "price_range": [1.00, 500.00],
        "market_cap": "small_to_large"
    }
}
```

**Scanner Output** (Top 100 candidates):
```yaml
candidates:
  - symbol: NVDA
    volume_ratio: 2.3
    price_change: +3.2%
    sector: technology
    market_cap: large
    
  - symbol: TSLA  
    volume_ratio: 1.8
    price_change: +2.1%
    sector: consumer_discretionary
    market_cap: large
```

#### B2: News Catalyst Filtering (100 → 35)
**News Intelligence Service:**
```python
# Check each candidate for news catalysts
for candidate in top_100_candidates:
    news_data = get_news_intelligence(candidate.symbol)
    if news_data.catalyst_score > 0.6:
        catalyst_candidates.append(candidate)
```

---

### Phase C: Analysis Phase

#### C1: Pattern Recognition (35 → 20)
**Workflow State**: `ANALYZING`

**Pattern Service Execution:**
```python
# Orchestration → Pattern Service
for candidate in catalyst_candidates:
    pattern_analysis = POST http://localhost:5002/analyze
    {
        "symbol": candidate.symbol,
        "timeframes": ["1min", "5min", "15min"],
        "pattern_types": ["breakout", "momentum", "reversal"]
    }
```

**Pattern Service Output:**
```yaml
pattern_analysis:
  symbol: NVDA
  patterns:
    - type: "ascending_triangle"
      confidence: 0.84
      timeframe: "5min"
      breakout_target: 45.20
    - type: "volume_spike"
      confidence: 0.91
      volume_ratio: 3.2
```

#### C2: Technical Analysis (20 → 10)
**Technical Analysis Service:**
```python
# Deep technical analysis on pattern candidates
technical_signals = []
for candidate in pattern_candidates:
    analysis = POST http://localhost:5003/analyze
    {
        "symbol": candidate.symbol,
        "indicators": ["rsi", "macd", "volume_profile", "support_resistance"],
        "risk_assessment": True
    }
    
    if analysis.signal_strength > 0.7:
        technical_signals.append(analysis)
```

**Technical Analysis Output:**
```yaml
technical_analysis:
  symbol: NVDA  
  signal_strength: 0.86
  direction: "bullish"
  entry_price: 44.55
  stop_loss: 43.90
  take_profit: 46.20
  risk_reward: 2.5
  indicators:
    rsi: 58 (neutral-bullish)
    macd: bullish_crossover
    volume_profile:
      poc: 44.50
      value_area: [44.00, 45.00]
```

#### C3: Risk Assessment & Final Selection (10 → 5)
**Risk Management Integration:**
```python
# Final risk assessment and position sizing
final_signals = []
for signal in technical_signals:
    risk_analysis = calculate_position_risk(
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        account_value=state.account_value,
        risk_per_trade=state.current_cycle.risk_level
    )
    
    if risk_analysis.position_size > 0:
        signal.position_size = risk_analysis.position_size
        final_signals.append(signal)

# Sort by confidence, take top 5
state.pending_signals = sorted(final_signals, 
                              key=lambda x: x.confidence, 
                              reverse=True)[:5]
```

---

### Phase D: Trading Execution

#### D1: Order Placement
**Workflow State**: `EXECUTING`

**Trading Service Execution:**
```python
# Execute top signals (respect position limits)
max_new_positions = state.current_cycle.max_positions - len(state.active_positions)

for signal in state.pending_signals[:max_new_positions]:
    order_request = {
        "signal_id": signal.id,
        "symbol": signal.symbol,
        "side": "buy",
        "quantity": signal.position_size,
        "order_type": "limit",
        "limit_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "risk_level": state.current_cycle.risk_level
    }
    
    result = POST http://localhost:5005/api/v1/orders/execute
```

**Order Execution Result:**
```yaml
execution_result:
  trade_id: "trd_20250922_001"
  symbol: "NVDA"
  status: "filled"
  fill_price: 44.54
  quantity: 1000
  commission: 1.00
  timestamp: "2025-09-22T10:35:12Z"
```

#### D2: Position Tracking
```python
# Add to active positions
if execution_result.status == "filled":
    position = {
        "position_id": execution_result.trade_id,
        "symbol": signal.symbol,
        "entry_price": execution_result.fill_price,
        "quantity": execution_result.quantity,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "unrealized_pnl": 0.0,
        "opened_at": datetime.now()
    }
    state.active_positions.append(position)
```

---

### Phase E: Position Monitoring

#### E1: Real-Time Position Management
**Workflow State**: `MONITORING`

**Continuous Monitoring Loop:**
```python
# Check positions every 30 seconds
for position in state.active_positions:
    current_price = get_real_time_price(position.symbol)
    
    # Calculate unrealized P&L
    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
    
    # Check exit conditions
    if should_exit_position(position, current_price):
        close_position(position)
        
    # Adjust trailing stops
    if should_adjust_stop(position, current_price):
        adjust_trailing_stop(position, current_price)
```

#### E2: Exit Conditions
```python
def should_exit_position(position, current_price):
    # Stop loss hit
    if current_price <= position.stop_loss:
        return True
        
    # Take profit hit  
    if current_price >= position.take_profit:
        return True
        
    # Time-based exit (end of day)
    if is_near_market_close():
        return True
        
    # Pattern failure
    if pattern_has_failed(position):
        return True
        
    return False
```

#### E3: Trailing Stop Management
```python
def adjust_trailing_stop(position, current_price):
    # Calculate new trailing stop
    profit_percent = (current_price - position.entry_price) / position.entry_price
    
    if profit_percent > 0.02:  # 2% profit threshold
        new_stop = position.entry_price + (profit_percent * 0.5 * (current_price - position.entry_price))
        
        if new_stop > position.stop_loss:
            position.stop_loss = new_stop
            
            # Update stop loss order
            update_stop_loss_order(position.position_id, new_stop)
```

---

## 🎮 Claude Interaction Patterns

### Starting a Trading Session
```
User: "Good morning Claude! Start conservative trading today"

Claude Response:
"Good morning! I'll start a conservative trading cycle for you. Let me initialize the system..."

Actions:
- start_trading_cycle(mode="conservative", max_positions=3, risk_level=0.01)
- Check all service health
- Begin market scanning

Response: "✅ Trading cycle started successfully! 
- Mode: Conservative (15-minute scans)
- Max positions: 3
- Risk per trade: 1%
- All 6 services are healthy and ready
- Beginning market scan now..."
```

### Monitoring During Trading
```
User: "What's happening right now?"

Claude Response:
"Current trading status:
- 📊 Scanning phase: Analyzing 47 stocks with unusual volume
- 🎯 Found 3 pattern candidates: NVDA (breakout), AAPL (momentum), TSLA (reversal)
- 💼 Active positions: 2 open positions, +$234.56 unrealized P&L
- ⏰ Next scan: 2 minutes
- 🔍 Looking for 1 more position (max 3)"
```

### Position Management
```
User: "How are our positions doing?"

Claude Response:
"Position Update:
📈 NVDA: +$456.78 (+2.3%) - trailing stop at $44.20
📊 AAPL: +$123.45 (+0.8%) - holding above entry
🎯 Total unrealized P&L: +$580.23
⚠️ Risk level: Normal (within parameters)"
```

### End of Day
```
User: "Close everything and stop trading"

Claude Response:
"Closing all positions and stopping trading cycle...

Final Results:
- Positions closed: 2
- Realized P&L: +$423.67
- Win rate: 75% (3 wins, 1 loss)
- Trading cycle stopped successfully
- System in safe idle state"
```

---

## 📊 Performance Metrics & Targets

### Phase 1 Success Metrics
```yaml
Performance Targets:
  win_rate: ≥ 55%
  sharpe_ratio: ≥ 1.2
  max_drawdown: ≤ 5%
  avg_risk_reward: ≥ 1.5
  daily_trades: 3-8
  position_hold_time: 30min - 4hours

Risk Management:
  max_account_risk: 2% per trade
  max_daily_loss: 4%
  max_concurrent_positions: 5
  stop_loss_always: Required
  position_sizing: Kelly Criterion + Risk Parity
```

### Service Performance SLAs
```yaml
Service Health Requirements:
  orchestration: 99.5% uptime
  scanner: < 10s response time
  pattern_recognition: < 5s analysis time  
  technical_analysis: < 3s per symbol
  trading_execution: < 2s order placement
  news_intelligence: < 30s news processing
```

---

## 🔧 Troubleshooting & Recovery

### Common Issues & Solutions

#### Service Health Failures
```bash
# Check service status
curl http://localhost:5000/health

# Restart specific service  
docker-compose restart scanner

# View service logs
docker-compose logs scanner --tail=50
```

#### Workflow State Issues
```python
# Emergency stop
User: "Emergency stop everything!"
Claude → emergency_stop(reason="user_request", close_positions=True)

# Reset workflow state
state.workflow_state = WorkflowState.IDLE
state.current_cycle = None
state.pending_signals = []
```

#### Database Connection Issues
```bash
# Test database connection
python3 scripts/database_connection_fix.py

# Check connection pool
SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name;
```

---

## 🚀 Phase 1 Success Criteria

### ✅ Ready for Phase 2 When:
1. **Consistent profitability** over 2+ weeks
2. **Win rate ≥ 60%** with current data sources  
3. **Sharpe ratio ≥ 1.5** in live trading
4. **System stability** - 99%+ uptime
5. **Risk management proven** - no catastrophic losses
6. **Claude integration seamless** - natural conversation flow

### 🎯 Phase 2 Preparation:
- Upgrade to **Alpaca Pro Real-Time** ($99/month)
- Add **Financial Modeling Prep** ($50/month) for news/earnings
- Implement **enhanced technical indicators** (Volume Profile, Order Flow)
- Develop **custom pattern recognition** improvements

---

## 📝 Daily Operations Checklist

### Morning Startup (Pre-Market)
- [ ] Check overnight news and earnings
- [ ] Verify all service health
- [ ] Review gap up/down candidates  
- [ ] Start trading cycle appropriate for market conditions
- [ ] Confirm risk parameters are set correctly

### During Market Hours
- [ ] Monitor Claude conversations for workflow status
- [ ] Watch for unusual market conditions requiring intervention
- [ ] Check position management and trailing stops
- [ ] Review new signals and pattern recognition quality

### End of Day
- [ ] Close remaining positions (unless swing trades)
- [ ] Stop trading cycle
- [ ] Review daily performance metrics
- [ ] Check logs for any errors or warnings
- [ ] Plan for next trading session

---

## 🎩 DevGenius Notes

*"The beauty of Phase 1 is its elegant simplicity - we take 100 stocks, apply rigorous filtering, and emerge with 5 high-conviction trades. The workflow state machine ensures we never miss a step, while Claude provides the perfect human-AI interface for natural trading management. This isn't just automation; it's augmented trading intelligence!"*

**Key Success Factors:**
- **Pattern recognition quality** drives everything
- **Risk management** is non-negotiable  
- **Service reliability** enables confidence
- **Claude interaction** makes it feel natural

Ready to revolutionize systematic trading! 🚀📊

---

*Phase 1 establishes the foundation for intelligent, risk-managed day trading with human oversight and AI execution.*