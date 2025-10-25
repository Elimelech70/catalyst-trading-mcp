# SECONDARY-001: Research Functional Specification Outline

**Name of Application**: Catalyst Trading System - Research Instance  
**Name of file**: SECONDARY-001-research-functional-spec-outline.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: Outline for research-functional-spec-v1.0.0.md  
**Timeline**: Weeks 9-10 (design only, no implementation)  
**Priority**: HIGH (design foundation for Research instance)

---

## Document Structure

This outline defines the structure for `research-functional-spec-v1.0.0.md` to be created in Weeks 9-10.

---

## 1. System Overview

### 1.1 Purpose
- ML experimentation and pattern discovery
- Economic indicator tracking (Dalio framework)
- Crisis detection (GFC indicators)
- Multi-market analysis (US, China, Japan)
- Backtest engine for strategy validation

### 1.2 Scope (Research vs Production)

**Research Instance (THIS spec)**:
```yaml
IN SCOPE:
  ✅ ML training services
  ✅ Pattern discovery (unsupervised learning)
  ✅ Economic Intelligence Service (FRED API)
  ✅ Multi-agent AI coordinator
  ✅ Backtest engine
  ✅ Paper trading sandbox
  ✅ Multi-market support (China, Japan)
  ✅ Reference-based storage (5GB)
  
OUT OF SCOPE:
  ❌ Live trading (Production handles this)
  ❌ Real money risk
  ❌ Production database
```

**Production Instance** (see functional-spec-mcp-v6.1.0.md):
```yaml
  ✅ 9 services for live trading
  ✅ US markets only
  ✅ Rule-based trading (Stage 1)
  ✅ Real capital deployment
```

---

## 2. Service Matrix (5 NEW Services)

### 2.1 Service Inventory

| # | Service | Port | Purpose | Technology |
|---|---------|------|---------|------------|
| 1 | Economic Intelligence | 6001 | FRED API, empire indicators | FastAPI + Redis |
| 2 | ML Training | 6002 | Pattern discovery, model training | FastAPI + PyTorch |
| 3 | Backtest Engine | 6003 | Strategy validation | FastAPI + Pandas |
| 4 | Pattern Discovery | 6004 | Unsupervised learning | FastAPI + Scikit-learn |
| 5 | Multi-Agent Coordinator | 6000 | Claude + GPT-4 + Perplexity | FastMCP |

### 2.2 Service Details

#### Service 1: Economic Intelligence (Port 6001)
```yaml
Purpose: Track macroeconomic indicators

Responsibilities:
  - FRED API integration (18,000+ series)
  - Ray Dalio empire framework (18 determinants)
  - GFC leading indicators (12 metrics)
  - Country power score calculations
  - Crisis detection algorithms
  
Data Sources:
  - FRED (Federal Reserve Economic Data)
  - World Bank APIs
  - IMF data
  - BIS (Bank for International Settlements)
  
Key Endpoints:
  - GET /api/v1/economic/indicators
  - GET /api/v1/economic/empire-scores
  - GET /api/v1/economic/crisis-probability
  - POST /api/v1/economic/collect
  
Database Tables:
  - empire_determinants
  - gfc_indicators
  - fred_data_references
  - country_power_scores
```

#### Service 2: ML Training (Port 6002)
```yaml
Purpose: Train ML models for pattern recognition

Responsibilities:
  - Reference-based data loading (on-demand from Alpaca)
  - Feature engineering
  - Model training (PyTorch, TensorFlow)
  - Performance validation
  - Model versioning
  
Training Pipeline:
  1. Load historical data (via references)
  2. Generate features (technical indicators, news sentiment)
  3. Train models (supervised/unsupervised)
  4. Validate on holdout set
  5. Deploy if performance meets threshold
  
Key Endpoints:
  - POST /api/v1/ml/train
  - GET /api/v1/ml/models
  - GET /api/v1/ml/experiments
  - POST /api/v1/ml/predict
  
Database Tables:
  - ml_experiments
  - ml_models
  - ml_training_jobs
  - feature_engineering_configs
```

#### Service 3: Backtest Engine (Port 6003)
```yaml
Purpose: Validate trading strategies historically

Responsibilities:
  - Historical data retrieval (reference-based)
  - Strategy simulation
  - Performance metrics (Sharpe, Sortino, Max DD)
  - Walk-forward validation
  - Multi-market support
  
Backtest Types:
  - Single symbol
  - Portfolio (multi-symbol)
  - Multi-strategy
  - Monte Carlo simulation
  
Key Endpoints:
  - POST /api/v1/backtest/run
  - GET /api/v1/backtest/results/{id}
  - GET /api/v1/backtest/metrics
  - POST /api/v1/backtest/compare
  
Database Tables:
  - backtest_runs
  - backtest_trades
  - backtest_metrics
  - strategy_configs
```

#### Service 4: Pattern Discovery (Port 6004)
```yaml
Purpose: Discover new patterns via unsupervised learning

Responsibilities:
  - Unsupervised pattern detection
  - Clustering similar chart patterns
  - Anomaly detection
  - Pattern validation against outcomes
  
Algorithms:
  - K-means clustering
  - DBSCAN
  - Isolation Forest (anomalies)
  - Autoencoders (pattern compression)
  
Key Endpoints:
  - POST /api/v1/patterns/discover
  - GET /api/v1/patterns/library
  - POST /api/v1/patterns/validate
  - GET /api/v1/patterns/performance
  
Database Tables:
  - discovered_patterns
  - pattern_validation
  - pattern_categories
  - pattern_performance
```

#### Service 5: Multi-Agent Coordinator (Port 6000)
```yaml
Purpose: Orchestrate multiple AI models for research

Agents:
  - Claude: Strategic reasoning, decision-making
  - GPT-4: Pattern analysis, hypothesis generation
  - Perplexity: Real-time research, news analysis
  - Gemini: Multi-modal analysis (charts + text)
  
Coordination:
  - Consensus building (vote on hypotheses)
  - Task distribution (parallel research)
  - Result synthesis (combine outputs)
  
Protocol: MCP (Model Context Protocol)

Key MCP Resources:
  - research://experiments
  - research://patterns
  - research://economic-indicators
  - research://backtests
  
Key MCP Tools:
  - start_research_task
  - query_economic_data
  - run_backtest
  - discover_patterns
```

---

## 3. Integration with Strategy Documents

### 3.1 Ray Dalio Empire Framework Integration

**Source**: `ray-dalio-country-collapse-indicators.md` (v1.0.0)

**Implementation**:
```yaml
Economic Intelligence Service:
  - Track 18 determinants of empire power
  - Calculate country power scores (0-1 scale)
  - Monitor 3 interconnected cycles:
    1. Debt cycle
    2. Internal conflict cycle
    3. External conflict cycle
  - Detect 6 stages of debt crisis
  
Database Tables:
  empire_determinants:
    - education_quality_score
    - innovation_competitiveness
    - trade_balance
    - military_strength
    - currency_reserve_status
    - ... (18 total)
  
  country_power_scores:
    - country_code
    - power_score (0-1)
    - trend (rising/declining)
    - updated_at
```

### 3.2 GFC Leading Indicators Integration

**Source**: `gfc-leading-indicators-real-data.md` (v1.0.0)

**Implementation**:
```yaml
Economic Intelligence Service:
  - Track 12 critical GFC indicators
  - All data from FRED API (freely available)
  - Calculate composite crisis index
  - Alert when threshold breached
  
Key Indicators:
  1. TED Spread (TEDRATE)
  2. Credit Spreads (BAA10Y)
  3. Yield Curve (T10Y2Y)
  4. Unemployment Rate (UNRATE)
  5. Housing Starts (HOUST)
  6. Consumer Confidence (UMCSENT)
  7. Bank Lending Standards (DRTSCLCC)
  8. Corporate Profits (CP)
  9. Household Debt Service (TDSP)
  10. Commercial Real Estate (DCOILWTICO)
  11. International Reserves (TRESEGUSM052N)
  12. Real Exchange Rate (RBUSBIS)
  
Database Tables:
  gfc_indicators:
    - indicator_name
    - fred_series_id
    - current_value
    - historical_percentile
    - crisis_threshold
    - alert_status
```

### 3.3 Empire Transition Investment Strategy

**Source**: `empire-transition-investment-strategy.md` (v1.0.0)

**Implementation**:
```yaml
Use Case: Identify which markets to expand trading to

Analysis:
  - US vs China power score comparison
  - Leading vs lagging indicators
  - Transition timeline (Phases 1-3)
  - Geographic relocation decision
  
Trading System Impact:
  Phase 1 (2025-2030): US markets primary, China secondary
  Phase 2 (2030-2040): Equal weight US + China
  Phase 3 (2040+): China primary, US secondary
  
Research Instance Role:
  - Monitor empire transition indicators
  - Alert when phase transition detected
  - Recommend market allocation shifts
```

### 3.4 Reference-Based Storage Strategy

**Source**: `free-data-sources-ml-storage-strategy.md` (v1.0.0)

**Implementation**:
```yaml
Storage Approach: Reference-based (NOT full data storage)

What We Store (5GB):
  ✅ Trading decisions (what we chose, why)
  ✅ Outcomes (win/loss, P&L, R:R)
  ✅ References (symbol + timestamp + source)
  ✅ Composite scores (our calculations)
  
What We DON'T Store (195GB saved):
  ❌ Raw OHLCV data (download from Alpaca on-demand)
  ❌ Full news articles (reference by URL)
  ❌ Technical indicators (recalculate from OHLCV)
  
ML Training Workflow:
  1. Query decision_logs table (references only)
  2. Download OHLCV data from Alpaca (10-30 min)
  3. Recalculate indicators
  4. Train model
  5. Discard raw data (keep model only)
  
Cost Savings:
  Storage: $120/month → $15/month (8x reduction)
  Database: 200GB → 5GB
  Trade-off: ML training takes 10-30 min longer
```

---

## 4. Data Flow Specifications

### 4.1 ML Training Pipeline

```
1. Human Request (via Multi-Agent Coordinator)
   "Train a model to predict bull flag success rate"
   
2. ML Training Service:
   a. Query Production database (decision_logs)
   b. Identify relevant trades (bull flag pattern)
   c. Extract symbol + timestamp references
   
3. Data Retrieval:
   a. Download OHLCV from Alpaca (historical)
   b. Fetch news articles from archived URLs
   c. Recalculate technical indicators
   
4. Feature Engineering:
   a. Generate features (200+ indicators)
   b. Normalize data
   c. Split train/validation/test
   
5. Model Training:
   a. Train PyTorch model
   b. Validate performance
   c. Save model + metadata
   
6. Deployment:
   a. Store model in ml_models table
   b. Update Pattern Discovery Service
   c. Notify Multi-Agent Coordinator
```

### 4.2 Economic Indicator Monitoring

```
1. FRED API Polling (daily, 2:00 AM AWST)
   Economic Intelligence Service → FRED API
   
2. Data Collection:
   - Fetch 18 empire determinants
   - Fetch 12 GFC indicators
   - Store in fred_data_references
   
3. Score Calculation:
   - Calculate country power scores
   - Calculate crisis probability index
   - Compare to historical thresholds
   
4. Alert Generation:
   IF crisis_probability > 0.7:
     - Log alert in risk_events
     - Notify Multi-Agent Coordinator
     - Generate report for human review
```

### 4.3 Backtest Execution

```
1. Human Request (via Multi-Agent Coordinator)
   "Backtest bull flag strategy on AAPL (2020-2024)"
   
2. Backtest Engine:
   a. Load strategy config
   b. Query decision_logs for AAPL bull flags
   c. Download OHLCV from Alpaca (2020-2024)
   
3. Simulation:
   a. Replay historical price action
   b. Execute strategy rules
   c. Track simulated positions
   d. Calculate P&L
   
4. Performance Metrics:
   a. Win rate, R:R, Sharpe, Sortino, Max DD
   b. Monte Carlo simulation (1000 runs)
   c. Walk-forward validation
   
5. Results:
   a. Store in backtest_runs
   b. Generate report
   c. Return to Multi-Agent Coordinator
```

---

## 5. Performance Requirements

### 5.1 Economic Intelligence Service

```yaml
Data Collection:
  - FRED API polling: Once daily (off-peak)
  - Response time: <5s per indicator
  - Batch processing: 30 indicators in <2 min
  
Score Calculation:
  - Country power score: <1s
  - Crisis probability: <2s
  - Historical comparison: <3s
```

### 5.2 ML Training Service

```yaml
Data Loading:
  - Reference query: <1s
  - OHLCV download: 10-30 min (acceptable)
  - Feature generation: 5-10 min
  
Model Training:
  - Simple model (< 1M params): <30 min
  - Complex model (> 10M params): <4 hours
  - Acceptable: Overnight batch processing
```

### 5.3 Backtest Engine

```yaml
Simple Backtest (single symbol, 1 year):
  - Data loading: 1-2 min
  - Simulation: <5 min
  - Metrics calculation: <1 min
  - Total: <10 min
  
Complex Backtest (portfolio, 5 years):
  - Data loading: 10-20 min
  - Simulation: 30-60 min
  - Monte Carlo (1000 runs): 2-4 hours
  - Acceptable: Overnight processing
```

---

## 6. Security Requirements

### 6.1 Data Access

```yaml
Production Database:
  - Read-only access for Research instance
  - No writes to Production tables
  - Separate credentials
  
Research Database:
  - Full access for Research services
  - Separate from Production database
  - Independent backups
```

### 6.2 API Keys

```yaml
FRED API:
  - Free tier (unlimited for education/research)
  - API key stored in environment variables
  
Alpaca API:
  - Paper trading keys for backtesting
  - NO live trading keys in Research instance
  
Multi-Agent APIs:
  - OpenAI (GPT-4)
  - Anthropic (Claude)
  - Google (Gemini)
  - Perplexity
```

---

## 7. Success Criteria

### 7.1 Functional Success

```yaml
✅ All 5 services deployed and healthy
✅ Economic indicators tracked (18 + 12)
✅ ML training pipeline operational
✅ Backtest engine produces valid results
✅ Pattern discovery finds novel patterns
✅ Multi-agent coordination works
```

### 7.2 Performance Success

```yaml
✅ Economic data collected daily
✅ ML training completes overnight
✅ Backtests complete in reasonable time
✅ Reference-based storage working (5GB)
✅ FRED API integration reliable
```

### 7.3 Integration Success

```yaml
✅ Strategy documents fully integrated
✅ Production database accessible (read-only)
✅ Multi-agent AI produces useful insights
✅ Crisis detection alerts functional
✅ ML models improve trading decisions
```

---

## 8. Implementation Notes

**This is a DESIGN document only (Weeks 9-10)**
- No implementation until Production succeeds (Month 6+)
- Design can be refined based on Production learnings
- Phased deployment:
  1. Economic Intelligence (Month 6)
  2. ML Training (Month 7-8)
  3. Backtest + Pattern Discovery (Month 9+)

**Dependencies**:
- Production profitable for 3 months
- Budget available ($136/month)
- Strategy documents uploaded to GitHub

---

**END OF SECONDARY-001 OUTLINE**

**Next**: SECONDARY-002 (Database Schema Outline)  
**Timeline**: Week 9-10 (design), Month 6+ (implementation)  
**Purpose**: Foundation for Research instance development

🎯 Ready for detailed specification creation!
