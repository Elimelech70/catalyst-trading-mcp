# Catalyst Trading System - MCP Functional Specification v3.0.0

**Version**: 3.0.0  
**Date**: December 30, 2024  
**Platform**: DigitalOcean with MCP Architecture  
**Status**: MCP Implementation Ready  
**Previous Version**: 2.1.0 (July 9, 2025)

## Revision History

### v3.0.0 (December 30, 2024)
- **MCP Architecture**: All services exposed via MCP protocol
- **AI-Native Operations**: Business logic accessible to Claude
- **Resource/Tool Model**: Endpoints replaced with MCP resources and tools
- **Session Workflows**: Complex operations via MCP sessions
- **Natural Language**: Business rules interpretable by AI
- **Maintained Core Logic**: 50 securities scanned, top 5 traded

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Core Business Logic in MCP](#2-core-business-logic-in-mcp)
3. [MCP Service Specifications](#3-mcp-service-specifications)
4. [MCP Data Flow Specifications](#4-mcp-data-flow-specifications)
5. [MCP Data Management](#5-mcp-data-management)
6. [Integration Points](#6-integration-points)
7. [Performance Requirements](#7-performance-requirements)
8. [Security Requirements](#8-security-requirements)
9. [Error Handling](#9-error-handling)

---

## 1. System Overview

### 1.1 Purpose
The Catalyst Trading System is an AI-native, news-driven algorithmic trading platform where Claude and other AI assistants can discover and execute day trading opportunities through natural language interaction with MCP services.

### 1.2 Key Differentiators with MCP
- **AI-First Design**: Business logic exposed as MCP resources and tools
- **Natural Language Trading**: Claude interprets market conditions and executes trades
- **Comprehensive Monitoring**: ALL 50 scanned securities recorded via MCP
- **Focused Execution**: Only TOP 5 proceed to trading
- **Stateful Workflows**: Complex trading strategies via MCP sessions
- **Intelligent Automation**: AI-driven decision making at each step

### 1.3 Operating Modes via MCP

```yaml
# Get current market mode
resource: trading/mode/current
returns:
  mode: pre-market|normal|after-hours|weekend
  scan_frequency: 5min|30min|60min
  aggressiveness: high|medium|low

# Set operating mode
tool: set_trading_mode
params:
  mode: aggressive|normal|light|maintenance
  reason?: string
returns:
  mode_changed: boolean
  next_scan: timestamp
```

### 1.4 Data Growth Management with MCP

```yaml
# Monitor data growth
resource: data/growth/statistics
returns:
  unique_securities:
    total: 1247
    added_today: 23
    added_this_week: 89
  storage_metrics:
    total_records: 623000
    compressed_records: 187000
    compression_ratio: 0.70

# Trigger data aggregation
tool: aggregate_market_data
params:
  older_than_days: 7
  target_timeframe: 15min|1hour|daily
returns:
  records_processed: 45000
  space_saved: 2.3GB
  duration_ms: 4500
```

---

## 2. Core Business Logic in MCP

### 2.1 Catalyst Scoring as MCP Resource

```yaml
# Calculate catalyst score
resource: analysis/catalyst-score
params:
  symbol: string
  news_ids: string[]
returns:
  catalyst_score: number
  components:
    source_tier_weight: number
    recency_weight: number
    keyword_weight: number
    market_state_multiplier: number
  formula: string
  confidence: number

# Bulk catalyst scoring
resource: analysis/catalyst-scores/bulk
params:
  symbols: string[]
returns:
  scores: {symbol: string, score: number}[]
```

### 2.2 Multi-Stage Filtering via MCP Session

```python
class TradingSelectionSession:
    """MCP session for multi-stage security selection"""
    
    async def select_trading_candidates(self):
        async with MCPSession("selection") as session:
            # Stage 1: Collect all news
            news = await session.resource("news/active", {
                "limit": 1000,
                "min_tier": 5
            })
            
            # Stage 2: Identify 50 most active with catalysts
            active_symbols = await session.tool("identify_active_securities", {
                "news_symbols": news.symbols,
                "limit": 50
            })
            
            # Stage 3: RECORD ALL 50 to market_data
            await session.tool("record_market_data_bulk", {
                "symbols": active_symbols.all_50,
                "save_all": True
            })
            
            # Stage 4: Technical validation → 20
            validated = await session.tool("validate_technicals", {
                "symbols": active_symbols.all_50,
                "limit": 20
            })
            
            # Stage 5: Final selection → TOP 5
            top_5 = await session.tool("select_final_candidates", {
                "candidates": validated.symbols,
                "limit": 5
            })
            
            # Stage 6: Save only TOP 5 as trading candidates
            await session.tool("save_trading_candidates", {
                "candidates": top_5.selections
            })
            
            return {
                "scan_id": session.scan_id,
                "total_evaluated": 50,
                "data_recorded": 50,
                "trading_candidates": 5
            }
```

### 2.3 Continuous Learning via MCP

```yaml
# Track unique securities growth
resource: learning/securities/growth
params:
  timeframe: daily|weekly|monthly
returns:
  growth_chart:
    - date: 2024-12-01
      new_symbols: 45
      cumulative: 1023
    - date: 2024-12-02
      new_symbols: 38
      cumulative: 1061

# Get ML training dataset
resource: learning/dataset/ready
params:
  min_observations: 10
  include_outcomes: true
returns:
  securities_count: 1247
  total_observations: 89234
  features_available: 156
  ready_for_training: true
```

---

## 3. MCP Service Specifications

### 3.1 News Intelligence MCP Server (Port 5008)

#### Resources (Read Operations)
```yaml
# Get active news
resource: news/active
params:
  since?: timestamp
  market_state?: pre-market|regular|after-hours
  min_tier?: number
returns:
  articles: NewsArticle[]
  symbols: string[]
  catalyst_types: object

# Get news sentiment
resource: news/sentiment/{symbol}
returns:
  overall_sentiment: bullish|neutral|bearish
  confidence: number
  key_themes: string[]
  source_consensus: number
```

#### Tools (Write Operations)
```yaml
# Collect news from all sources
tool: collect_news_all_sources
params:
  mode: aggressive|normal|light
  sources?: string[]
returns:
  collected: number
  new_articles: number
  processing_time_ms: number

# Analyze news catalyst
tool: analyze_news_catalyst
params:
  symbol: string
  timeframe: string
returns:
  catalyst_strength: number
  catalyst_type: string
  expected_duration: string
```

### 3.2 Security Scanner MCP Server (Port 5001)

#### Enhanced Specifications for Comprehensive Data Collection

```yaml
# Execute market scan - records ALL 50
tool: execute_dynamic_scan
params:
  mode: normal|aggressive|light
  universe_size: number (default: 100)
returns:
  scan_id: string
  stages:
    universe_evaluated: 100
    with_catalysts: 75
    top_scored: 50          # ALL recorded
    technically_valid: 20
    final_candidates: 5     # Trading only
  data_recording:
    market_data_saved: 50   # Comprehensive
    trading_candidates: 5   # Focused

# Get scan history showing data collection
resource: scanner/history/comprehensive
params:
  date: string
returns:
  scans:
    - scan_id: string
      timestamp: timestamp
      unique_symbols_recorded: 50
      new_symbols_discovered: 12
      total_data_points: 3900
```

### 3.3 Pattern Analysis MCP Server (Port 5002)

#### Focused on TOP 5 Only
```yaml
# Detect patterns - TOP 5 candidates only
tool: detect_patterns_for_candidates
params:
  scan_id: string  # Links to scanner results
returns:
  analyzed_symbols: 5  # Only the trading candidates
  patterns_detected:
    SYMBOL_A: [bull_flag, ascending_triangle]
    SYMBOL_B: [morning_star]
  skipped_symbols: 45  # The rest of the 50

# Pattern success with catalyst
resource: patterns/success-rates/catalyst-aligned
params:
  pattern_type: string
  catalyst_type: string
returns:
  success_rate: number
  sample_size: number
  confidence_interval: number[]
```

### 3.4 Technical Analysis MCP Server (Port 5003)

#### Signal Generation for TOP 5
```yaml
# Generate signals - TOP 5 only
tool: generate_trading_signals
params:
  candidates: string[]  # Max 5 symbols
  risk_profile: conservative|moderate|aggressive
returns:
  signals_generated: number
  signals:
    - symbol: string
      confidence: number
      entry: number
      stop: number
      targets: number[]

# Get signal confidence factors
resource: signals/confidence-factors/{signal_id}
returns:
  overall_confidence: number
  factors:
    catalyst_strength: number
    pattern_alignment: number
    technical_setup: number
    volume_confirmation: number
```

### 3.5 Trading Execution MCP Server (Port 5005)

```yaml
# Execute paper trade
tool: execute_paper_trade
params:
  signal_id: string
  size_override?: number
  slippage_tolerance?: number
returns:
  trade_id: string
  execution:
    requested_price: number
    fill_price: number
    slippage: number
  position_opened: boolean

# Monitor position
resource: trading/positions/{position_id}/monitor
returns:
  current_pnl: number
  stop_distance: number
  target_distance: number
  catalyst_status: active|fading|expired
  recommended_action: hold|tighten_stop|exit
```

### 3.6 Orchestration MCP Server (Port 5009)

#### Complete Workflow Management
```python
class OrchestrationWorkflow:
    """Claude-friendly workflow orchestration"""
    
    async def run_complete_trading_cycle(self):
        async with MCPSession("orchestration") as session:
            # 1. Check market conditions
            market = await session.resource("market/conditions")
            
            # 2. Determine mode
            mode = self._determine_mode(market)
            
            # 3. Collect news
            await session.tool("news/collect_news_all_sources", {
                "mode": mode
            })
            
            # 4. Run comprehensive scan (saves all 50)
            scan_result = await session.tool("scanner/execute_dynamic_scan", {
                "mode": mode
            })
            
            # 5. Analyze patterns (top 5 only)
            patterns = await session.tool("patterns/detect_patterns_for_candidates", {
                "scan_id": scan_result.scan_id
            })
            
            # 6. Generate signals (top 5 only)
            signals = await session.tool("technical/generate_trading_signals", {
                "candidates": scan_result.final_candidates
            })
            
            # 7. Execute trades
            for signal in signals.high_confidence:
                await session.tool("trading/execute_paper_trade", {
                    "signal_id": signal.signal_id
                })
            
            # 8. Complete cycle
            await session.tool("complete_cycle", {
                "cycle_id": session.cycle_id,
                "metrics": self._collect_metrics()
            })
```

### 3.7 Market Data Aggregation (Scheduled Task)

```yaml
# Aggregation status
resource: data/aggregation/status
returns:
  last_run: timestamp
  next_scheduled: timestamp
  pending_records: number
  estimated_duration: string

# Manual aggregation trigger
tool: run_data_aggregation
params:
  age_threshold_days: number
  target_compression: 15min|1hour|daily
  dry_run?: boolean
returns:
  records_processed: number
  space_saved_gb: number
  unique_symbols_affected: number
  compression_ratio: number
```

---

## 4. MCP Data Flow Specifications

### 4.1 Complete Trading Flow via MCP

```yaml
Trading Cycle Flow:
  1. News Collection:
     - tool: collect_news_all_sources
     - Output: 500+ articles
     - Frequency: 5-60 min based on mode
  
  2. Security Scanning:
     - tool: execute_dynamic_scan
     - Evaluates: 100 securities
     - Records: ALL 50 to market_data
     - Outputs: TOP 5 to trading_candidates
  
  3. Pattern Analysis:
     - tool: detect_patterns_for_candidates
     - Input: 5 symbols only
     - Output: catalyst-aligned patterns
  
  4. Signal Generation:
     - tool: generate_trading_signals
     - Input: patterns + indicators
     - Output: 0-5 high-confidence signals
  
  5. Trade Execution:
     - tool: execute_paper_trade
     - Input: signals > threshold
     - Output: position records
  
  6. Data Management:
     - tool: run_data_aggregation (nightly)
     - Compresses: data older than 7 days
     - Maintains: comprehensive history
```

### 4.2 Claude Interaction Flow

```
User: "How's the morning trading looking?"

Claude: Let me check the pre-market conditions and run a scan.

[Session starts]
[Checks resource: market/conditions]
[Checks resource: news/active?market_state=pre-market]

I see significant pre-market activity with 47 stocks showing news catalysts. 
Let me run a comprehensive scan.

[Executes tool: execute_dynamic_scan with mode=aggressive]

Scan complete! I've recorded data for 50 securities and identified these top 5 
trading candidates:

1. SYMBOL_A - Strong earnings catalyst (score: 8.5)
2. SYMBOL_B - FDA approval news (score: 8.2)
3. SYMBOL_C - Major partnership announced (score: 7.9)
4. SYMBOL_D - Analyst upgrade cycle (score: 7.6)
5. SYMBOL_E - Sector momentum play (score: 7.3)

Shall I analyze patterns and generate trading signals for these candidates?
```

---

## 5. MCP Data Management

### 5.1 Comprehensive Collection Metrics

```yaml
# Real-time collection stats
resource: data/collection/real-time
returns:
  current_scan:
    securities_evaluated: 100
    securities_recorded: 50
    new_symbols: 8
    data_points_added: 3900
  
  daily_totals:
    scans_completed: 24
    unique_symbols: 127
    total_data_points: 93600
  
  growth_projection:
    symbols_end_of_month: 1500
    storage_needed_gb: 2.4
```

### 5.2 Intelligent Data Lifecycle

```yaml
# Data lifecycle management
tool: manage_data_lifecycle
params:
  policy:
    raw_retention_days: 7
    15min_retention_days: 30
    hourly_retention_days: 90
    daily_retention: unlimited
  
  execute_now?: boolean
returns:
  policy_applied: boolean
  estimated_savings_gb: number
  records_to_process: number
```

---

## 6. Integration Points

### 6.1 External API Integration via MCP

```yaml
# External API status
resource: integrations/external/status
returns:
  apis:
    newsapi: {status: healthy, rate_limit_remaining: 450}
    alphavantage: {status: healthy, calls_today: 234}
    yfinance: {status: healthy, latency_ms: 45}
    alpaca: {status: healthy, orders_today: 12}

# Manage API keys
tool: rotate_api_key
params:
  service: newsapi|alphavantage|alpaca
  new_key: string
returns:
  rotated: boolean
  next_rotation_due: timestamp
```

### 6.2 Internal MCP Communication

```yaml
Service Discovery:
  - resource: services/registry
  - Returns all available MCP servers and their capabilities

Service Health:
  - resource: services/health/{service_name}
  - Returns health status and metrics

Cross-Service Sessions:
  - Sessions can span multiple MCP servers
  - Automatic transaction coordination
  - Shared context across services
```

---

## 7. Performance Requirements

### 7.1 MCP Response Times

```yaml
Resource Response Times:
  - Simple queries: < 50ms
  - Aggregated data: < 200ms
  - Historical queries: < 500ms
  - Real-time streams: < 10ms latency

Tool Execution Times:
  - collect_news: < 5 seconds
  - execute_scan: < 30 seconds
  - detect_patterns: < 5 seconds per symbol
  - generate_signal: < 2 seconds
  - execute_trade: < 1 second
```

### 7.2 Throughput Requirements

```yaml
System Capacity:
  - Concurrent MCP sessions: 100+
  - Resources per second: 1000+
  - Tools per second: 100+
  - Events per second: 10000+
  - Market data records/day: 100000+
```

### 7.3 MCP-Specific Optimizations

```yaml
Caching Strategy:
  - Resource responses cached by TTL
  - Session state maintained in Redis
  - Frequently accessed data pre-warmed
  - Query results materialized

Batching:
  - Bulk operations for market data
  - Batch pattern detection
  - Aggregated news collection
  - Grouped signal generation
```

---

## 8. Security Requirements

### 8.1 MCP Authentication

```yaml
Authentication Modes:
  - API Key: For external clients
  - Session Token: For Claude Desktop
  - mTLS: For service-to-service
  - OAuth2: For web clients

Authorization:
  - Resource-level permissions
  - Tool execution rights
  - Rate limiting per client
  - Audit logging
```

### 8.2 Trading Security via MCP

```yaml
Trading Safeguards:
  - tool: execute_trade requires "trader" role
  - Position limits enforced at MCP layer
  - Stop losses validated before execution
  - Manual override through special session
  - All trades logged with full context
```

### 8.3 Data Security

```yaml
Data Protection:
  - TLS for all MCP transports
  - Encryption at rest
  - No PII in MCP responses
  - Masked sensitive data
  - Secure credential storage
```

---

## 9. Error Handling

### 9.1 MCP Error Responses

```yaml
Error Format:
  error:
    type: resource_not_found|tool_failed|invalid_params
    message: Human-readable description
    code: HTTP-equivalent status code
    retry_after?: seconds
    details?: Additional context

Common Errors:
  - rate_limited: Too many requests
  - invalid_session: Session expired
  - insufficient_permissions: Access denied
  - tool_timeout: Operation took too long
  - resource_unavailable: Temporary failure
```

### 9.2 Session Recovery

```python
class MCPSessionRecovery:
    """Automatic session recovery"""
    
    async def with_recovery(self, operation):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await operation()
            except MCPSessionError as e:
                if attempt < max_retries - 1:
                    await self.recover_session()
                    continue
                raise
```

### 9.3 Claude Error Handling

```
Claude's Automatic Error Handling:
- Connection lost → Automatic reconnection
- Rate limited → Backoff and retry
- Tool failed → Explain issue and suggest alternatives
- Session expired → Create new session transparently
- Service down → Route to backup service
```

---

## Implementation Priority

### Phase 1: MCP Wrapper Services (Week 1)
1. Wrap existing services in MCP protocol
2. Implement basic resources and tools
3. Test with Claude Desktop
4. Verify comprehensive data collection

### Phase 2: Native MCP Services (Week 2)
1. Rewrite core services as MCP-native
2. Implement session management
3. Add event streaming
4. Optimize performance

### Phase 3: Advanced Features (Week 3)
1. Complex workflow sessions
2. Natural language interfaces
3. Intelligent error recovery
4. Performance optimization

This specification provides the complete functional blueprint for implementing the Catalyst Trading System with MCP architecture, enabling AI-native trading operations while maintaining comprehensive data collection and focused execution.