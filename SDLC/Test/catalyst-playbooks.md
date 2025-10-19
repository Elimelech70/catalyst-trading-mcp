# Catalyst Trading System Playbooks

**Name of Application**: Catalyst Trading System  
**Name of file**: catalyst-playbooks.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-19  
**Purpose**: Step-by-step execution guides for trading workflow, ML learning, monitoring, and troubleshooting

---

## REVISION HISTORY:
v1.0.0 (2025-10-19) - Initial playbook collection
- Trading workflow playbooks
- ML improvement playbooks
- Provider reliability playbooks
- Performance monitoring playbooks
- Troubleshooting playbooks
- Source validation playbooks

---

## Table of Contents

### IMPLEMENTED PLAYBOOKS
1. [Pre-Market Scan Execution](#1-pre-market-scan-execution)
2. [Improve Pattern Recognition](#2-improve-pattern-recognition)
3. [News Sentiment Calibration](#3-news-sentiment-calibration)
4. [Monitor Provider Performance](#4-monitor-provider-performance)
5. [Monitor Daily Workflow Performance](#5-monitor-daily-workflow-performance)
6. [Workflow Not Delivering Stocks](#6-workflow-not-delivering-stocks)
7. [Validate ML Information Sources](#7-validate-ml-information-sources)

### MISSING PLAYBOOKS (To Be Created)
8. [Intraday Narrowing Process](#missing-playbooks)
9. [Trade Execution Workflow](#missing-playbooks)
10. [Position Management](#missing-playbooks)
11. [Risk Management Check](#missing-playbooks)
12. [End of Day Reconciliation](#missing-playbooks)
13. [Backtest New Strategy](#missing-playbooks)
14. [Feature Engineering for ML](#missing-playbooks)
15. [Model Training and Validation](#missing-playbooks)
16. [Data Quality Check](#missing-playbooks)
17. [Database Performance Issues](#missing-playbooks)
18. [API Rate Limit Hit](#missing-playbooks)
19. [Service Crash Recovery](#missing-playbooks)
20. [Latency Spike Investigation](#missing-playbooks)
21. [Incorrect Trade Signal](#missing-playbooks)
22. [News Service Downtime](#missing-playbooks)
23. [Weekly Performance Review](#missing-playbooks)
24. [Monthly Strategy Evaluation](#missing-playbooks)
25. [Quarterly System Audit](#missing-playbooks)

---

## IMPLEMENTED PLAYBOOKS

### 1. Pre-Market Scan Execution

**Category**: Trading Workflow  
**Phase**: Operations  
**Trigger**: 08:00 ET daily, market day

**Steps**:
1. Orchestration service triggers workflow service
2. Workflow queries Polygon: top 50 by volume
3. Verify: Got exactly 50 tickers
   - If < 50: Alert "Insufficient volume data"
   - If > 50: Take top 50
4. Filter by news service
5. Verify: Got 15-25 with news catalysts
   - If < 15: Alert "Weak news day, proceed cautiously"
   - If > 25: Tighten filter threshold
6. Technical filter to 5 stocks
7. Deliver by 09:25 ET
   - If late: Alert "Missed pre-market window"

**Measurements**:
- Universe selection: 50 stocks
- News filtering: 15-25 stocks
- Final output: 5 stocks
- Total time: < 30 seconds
- Delivery: Before 09:25 ET

**Outcome**: 5 stocks delivered before market open

**Troubleshooting**: If failed, see playbook #6

---

### 2. Improve Pattern Recognition

**Category**: ML Improvement  
**Phase**: Learning  
**Trigger**: Monthly review of prediction accuracy

**Steps**:
1. Pull last 30 days of predictions vs actual moves
2. Identify patterns that failed (predicted >2%, moved <1%)
3. Research authoritative sources:
   - Tier 1: Academic papers on technical analysis
   - Tier 1: QuantConnect documentation
   - Tier 1: Scikit-learn official docs for models
4. Test new pattern on historical data
5. Measure improvement: accuracy, precision, recall
6. If improvement > 5%:
   - Update pattern in workflow service
   - Document in design
7. If no improvement:
   - Discard, try different approach

**Measurements**:
- Current accuracy: X%
- New accuracy: Y%
- Improvement: (Y-X)%
- Minimum improvement threshold: 5%

**Outcome**: Pattern recognition accuracy improved by X%

**Related**: Playbook #7 (Validate ML Sources)

---

### 3. News Sentiment Calibration

**Category**: ML Improvement  
**Phase**: Learning  
**Trigger**: News-based picks underperforming

**Steps**:
1. Analyze last 50 news-catalyst trades
2. Compare sentiment score vs actual price movement
3. Research authoritative sources:
   - Tier 1: NLTK documentation for NLP
   - Tier 1: FinBERT (Hugging Face) for financial sentiment
   - Tier 1: Academic papers on news sentiment trading
4. Test improved sentiment model:
   - Does "earnings beat" correlate with >2% move?
   - Does "FDA approval" score higher than "mentioned in article"?
5. Backtest on 6 months data
6. If correlation improves:
   - Update news service sentiment logic
   - Update functional spec measurements

**Measurements**:
- Current sentiment correlation: X%
- New sentiment correlation: Y%
- Backtest win rate: Z%

**Outcome**: News sentiment predicts movement with X% accuracy

**Related**: Playbook #7 (Validate ML Sources)

---

### 4. Monitor Provider Performance

**Category**: Provider Reliability  
**Phase**: Monitoring  
**Trigger**: Daily after market close

**Steps**:
1. Check provider metrics from logs:
   - Polygon: API calls, latency, failures
   - Alpaca News: Coverage, freshness, accuracy
   - Alpaca Trading: Order fill rate, slippage
2. Measure against functional spec:
   - Polygon: < 100ms latency (p95)
   - News: Articles within 15 min of event
   - Trading: Orders filled within 5 seconds
3. If degradation detected:
   - Log specific failures
   - Check provider status page
   - If persistent > 3 days: Evaluate alternatives
4. Track reliability score per provider (monthly)

**Measurements**:
- Polygon latency: p50, p95, p99
- News freshness: minutes from event to article
- Trading fill rate: percentage of orders filled
- Provider uptime: percentage per day

**Outcome**: All providers meeting SLA, or action plan for replacement

**Escalation**: If provider fails SLA for 3+ consecutive days

---

### 5. Monitor Daily Workflow Performance

**Category**: Performance Monitoring  
**Phase**: Operations  
**Trigger**: After market close daily

**Steps**:
1. Query database for today's workflow execution:
   ```sql
   SELECT * FROM workflow_metrics WHERE date = CURRENT_DATE
   ```
2. Check measurements against functional spec:
   - ✓ Universe selection: 50 stocks? ✓/✗
   - ✓ News filtering: 15-25 stocks? ✓/✗
   - ✓ Technical filter: 5 stocks? ✓/✗
   - ✓ Scan completion: < 30 seconds? ✓/✗
   - ✓ Delivery time: Before 09:25 ET? ✓/✗
3. Check trade outcomes (if executed):
   - How many of 5 picks moved >2% by 10:30?
   - Label: Win/Loss for each
4. If any measurement failed:
   - Trigger troubleshooting playbook #6
5. Store metrics for ML training

**Measurements**:
- Daily workflow success rate: X/5 checks passed
- Trade win rate: X/5 stocks moved >2%
- Average move: X%

**Outcome**: Daily performance report, issues flagged

**Related**: Playbook #6 (Troubleshooting)

---

### 6. Workflow Not Delivering Stocks

**Category**: Troubleshooting  
**Phase**: Operations  
**Trigger**: No stocks delivered by 09:25 ET

**Steps**:
1. Check orchestration service logs:
   ```bash
   docker logs orchestration-service
   ```
   - Is it running?
   - Did it trigger at 08:00?
2. Check workflow service logs:
   ```bash
   docker logs workflow-service
   ```
   - Did it receive trigger?
   - Where did pipeline fail?
3. If failed at universe selection:
   - Check Polygon API: quota, errors, data quality
   - Verify database writes
4. If failed at news filtering:
   - Check Alpaca News API: availability, data
   - Check filter thresholds (too strict?)
5. If failed at technical filter:
   - Check technical indicators calculating correctly
   - Check filter logic
6. Fix issue, re-run pipeline
7. If can't fix in 10 min:
   - Use backup: top 5 by volume + news (simple fallback)

**Decision Points**:
- Fixed in < 10 min? → Re-run pipeline
- Can't fix quickly? → Activate fallback
- Still broken? → Escalate, skip trading today

**Outcome**: Stocks delivered OR fallback activated OR escalated

**Related**: Playbook #4 (Provider Performance)

---

### 7. Validate ML Information Sources

**Category**: ML Source Validation  
**Phase**: Continuous Learning  
**Trigger**: Before implementing any ML improvement

**Steps**:
1. Identify source of ML technique/pattern
2. Verify source tier:
   - Tier 1: Official docs, academic papers, peer-reviewed
   - Tier 2: Respected practitioners (QuantConnect blog)
   - Tier 3: Random blogs, unverified claims
3. If Tier 3: REJECT, find Tier 1 source
4. If Tier 1 or 2: 
   - Verify claim with backtest
   - Measure against YOUR data (not their claims)
5. Document source in design doc
6. Only implement if proven on YOUR system

**Tier 1 Sources (Approved)**:
- Academic journals (peer-reviewed)
- Official documentation (Scikit-learn, TensorFlow, etc.)
- Federal Reserve papers
- Academic institutions (MIT, Stanford research)
- Official API docs (Polygon, Alpaca)

**Tier 2 Sources (Verify First)**:
- QuantConnect blog/docs
- Respected quant traders with track records
- Industry white papers

**Tier 3 Sources (REJECT)**:
- Random Medium posts
- Reddit "DD"
- Unverified YouTube tutorials
- "Get rich quick" trading blogs

**Outcome**: Only authoritative ML techniques used

**Related**: All ML improvement playbooks

---

## MISSING PLAYBOOKS

The following playbooks need to be created:

### Trading Workflow Playbooks
- **#8 Intraday Narrowing Process** - How to narrow from 5 to 3 to 1 throughout the day
- **#9 Trade Execution Workflow** - Steps to execute trades via Alpaca
- **#10 Position Management** - Monitor open positions, adjust stops, take profits
- **#11 Risk Management Check** - Pre-trade risk assessment (position size, stop loss)
- **#12 End of Day Reconciliation** - Close positions, reconcile trades, update records

### ML Learning Playbooks
- **#13 Backtest New Strategy** - How to properly backtest before live implementation
- **#14 Feature Engineering for ML** - Process for creating and testing new features
- **#15 Model Training and Validation** - Train models, validate, deploy process

### Data & Infrastructure Playbooks
- **#16 Data Quality Check** - Verify data integrity from providers
- **#17 Database Performance Issues** - Diagnose and fix slow queries
- **#18 API Rate Limit Hit** - Handle rate limiting from providers
- **#19 Service Crash Recovery** - Restart services, verify state consistency
- **#20 Latency Spike Investigation** - Diagnose performance degradation

### Troubleshooting Playbooks
- **#21 Incorrect Trade Signal** - Investigate why system gave wrong signal
- **#22 News Service Downtime** - Handle news provider outage

### Review & Audit Playbooks
- **#23 Weekly Performance Review** - Analyze week's trades, patterns, improvements
- **#24 Monthly Strategy Evaluation** - Deep dive into strategy effectiveness
- **#25 Quarterly System Audit** - Full system health check, architecture review

---

## Playbook Usage Guide

### How to Use a Playbook

1. **Identify the situation** - Match your current situation to a playbook trigger
2. **Follow steps sequentially** - Don't skip steps
3. **Record measurements** - Log all data points specified
4. **Make decisions at decision points** - Follow the if/then logic
5. **Verify outcome** - Confirm the expected outcome is achieved
6. **Document deviations** - If you had to deviate, note why

### When to Create a New Playbook

Create a new playbook when:
- You encounter a situation repeatedly
- The solution requires multiple steps
- Decision points exist
- Others need to handle it
- It's complex enough to forget steps

### Playbook Maintenance

- Review quarterly
- Update when processes change
- Remove if no longer applicable
- Version control in GitHub

---

## Integration with SDLC Framework

Playbooks are the **tactical execution** within SDLC phases:

| SDLC Phase | Uses Playbooks For |
|------------|-------------------|
| Planning | Strategy evaluation, requirement gathering |
| Design | Architecture decisions, technology selection |
| Implementation | Coding workflows, testing procedures |
| Testing | Test execution, bug investigation |
| Deployment | Deployment steps, rollback procedures |
| Maintenance | Monitoring, troubleshooting, performance tuning |
| Operations | Daily trading workflow, risk management |

**Remember**: 
- SDLC Framework = Know your phase, what you need
- Playbook = Exact steps to execute in that phase