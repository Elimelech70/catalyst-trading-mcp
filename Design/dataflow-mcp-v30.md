# Catalyst Trading System - MCP Data Flow & Service Interaction Map v3.0.0

**Version**: 3.0.0  
**Last Updated**: 2024-12-30  
**Purpose**: Complete map of data flow through MCP resources and tools

## Overview

This document traces how data flows through the MCP-based Catalyst Trading System, showing resource access patterns, tool invocations, and event streams that replace traditional REST APIs and direct database access.

## MCP Data Flow Architecture

### Key Concepts

1. **Resources**: Read-only data access points (replacing GET endpoints)
2. **Tools**: Action invocations that modify state (replacing POST/PUT/DELETE)
3. **Events**: Real-time data streams via MCP subscriptions
4. **Sessions**: Stateful contexts for multi-step workflows

## Data Flow Stages with MCP

### Stage 1: News Collection & Intelligence

#### News Intelligence MCP Server (Port 5008)

**Resource Access Patterns:**
```yaml
# Read news data
resource: news/raw
params:
  since: <timestamp>
  limit: 100
  filters:
    market_state: pre-market
    source_tier: [1,2]
returns:
  type: news_collection
  data: [NewsArticle]
  metadata: {count, last_updated}

# Get symbol-specific news
resource: news/by-symbol/{symbol}
params:
  timeframe: 24h
  include_sentiment: true
returns:
  type: symbol_news
  data: [NewsWithSentiment]
```

**Tool Invocations:**
```yaml
# Trigger news collection
tool: collect_news
params:
  sources: [newsapi, alphavantage, finnhub]
  mode: aggressive
returns:
  collected: 145
  new: 89
  duplicates: 56
  duration: 4.2s

# Analyze sentiment
tool: analyze_sentiment
params:
  symbol: SYMBOL_A
  include_related: true
returns:
  sentiment: bullish
  confidence: 0.85
  key_themes: [earnings_beat, sector_growth]
```

**Event Streams:**
```python
# Subscribe to real-time news
subscription: news.realtime
filter:
  symbols: [SYMBOL_A, SYMBOL_B, SYMBOL_C]
  min_tier: 3
events:
  - type: news.article
    data: {symbol, headline, sentiment, catalyst_score}
  - type: news.alert
    data: {symbol, alert_type, urgency}
```

### Stage 2: Security Scanning & Selection

#### Scanner MCP Server (Port 5001)

**Resource Access:**
```yaml
# Get current candidates
resource: candidates/active
returns:
  type: trading_candidates
  data:
    - symbol: SYMBOL_A
      catalyst_score: 85.2
      rank: 1
      scan_id: SCAN_20241230_093000

# Get scan history
resource: candidates/history
params:
  date: 2024-12-30
  mode: pre-market
returns:
  scans: [ScanResult]
  total_symbols_evaluated: 500
  unique_symbols: 127
```

**Tool Invocations:**
```yaml
# Run market scan
tool: scan_market
params:
  mode: aggressive  # pre-market mode
  universe_size: 100
  output_limit: 50
returns:
  scan_id: SCAN_20241230_093000
  evaluated: 100
  recorded: 50  # ALL saved to market_data
  candidates: 5  # TOP 5 for trading
  
# Analyze specific catalyst
tool: analyze_catalyst
params:
  symbol: SYMBOL_A
  news_ids: [news_001, news_002]
returns:
  catalyst_type: earnings
  strength: 8.5/10
  expected_impact: high
  time_sensitivity: 4_hours
```

**MCP Session for Scanning Workflow:**
```python
# Stateful scanning session
async with MCPSession("scanner") as session:
    # Step 1: Check market state
    market = await session.resource("market/status")
    
    # Step 2: Get news universe
    news_symbols = await session.resource("news/symbols/active")
    
    # Step 3: Run appropriate scan
    if market.is_premarket:
        result = await session.tool("scan_premarket", {
            "symbols": news_symbols.top_100
        })
    else:
        result = await session.tool("scan_market", {
            "mode": "normal"
        })
    
    # Step 4: Save scan results
    await session.tool("save_scan", {
        "scan_id": result.scan_id,
        "persist_all": True  # Save all 50 to market_data
    })
```

### Stage 3: Pattern Analysis

#### Pattern Analysis MCP Server (Port 5002)

**Resource Access:**
```yaml
# Get detected patterns
resource: patterns/by-symbol/{symbol}
params:
  timeframe: [5m, 15m]
  min_confidence: 0.7
returns:
  patterns:
    - type: bull_flag
      confidence: 0.85
      timeframe: 15m
      catalyst_aligned: true

# Get pattern success rates
resource: patterns/statistics
params:
  pattern_types: [bull_flag, cup_handle]
  catalyst_present: true
returns:
  success_rates:
    bull_flag_with_catalyst: 0.72
    cup_handle_with_catalyst: 0.68
```

**Tool Invocations:**
```yaml
# Detect patterns for symbols
tool: detect_patterns
params:
  symbols: [SYMBOL_A, SYMBOL_B, SYMBOL_C, SYMBOL_D, SYMBOL_E]  # TOP 5 only
  timeframes: [5m, 15m, 1h]
  catalyst_context: true
returns:
  detections:
    SYMBOL_A:
      - pattern: bull_flag
        confidence: 0.85
        catalyst_aligned: true
        entry_point: 485.50
```

### Stage 4: Technical Analysis & Signal Generation

#### Technical Analysis MCP Server (Port 5003)

**Resource Access:**
```yaml
# Get current indicators
resource: indicators/{symbol}/current
params:
  timeframe: 5m
  indicators: [rsi, macd, vwap]
returns:
  rsi: 68.5
  macd: {value: 2.3, signal: 1.8, histogram: 0.5}
  vwap: 484.20

# Get pending signals
resource: signals/pending
returns:
  signals:
    - signal_id: SIG_SYMBOL_A_20241230_093500
      confidence: 82.5
      entry: 485.50
      stop: 478.00
      targets: [492.00, 498.00]
```

**Tool Invocations:**
```yaml
# Generate trading signal
tool: generate_signal
params:
  symbol: SYMBOL_A
  pattern_id: PTN_12345
  catalyst_score: 8.5
returns:
  signal_id: SIG_SYMBOL_A_20241230_093500
  type: BUY
  confidence: 82.5
  components:
    catalyst: 8.5
    pattern: 7.8
    technical: 8.1
    volume: 7.9
```

### Stage 5: Trade Execution

#### Trading Execution MCP Server (Port 5005)

**Resource Access:**
```yaml
# Get open positions
resource: positions/open
returns:
  positions:
    - symbol: SYMBOL_A
      quantity: 100
      entry: 485.50
      current: 487.20
      unrealized_pnl: 170.00
      stop_loss: 478.00

# Get account status
resource: account/status
returns:
  buying_power: 25000.00
  positions_value: 48720.00
  daily_pnl: 1250.00
  open_orders: 0
```

**Tool Invocations:**
```yaml
# Execute trade
tool: execute_trade
params:
  signal_id: SIG_SYMBOL_A_20241230_093500
  size_override: null  # Use signal recommendation
  order_type: market
returns:
  trade_id: TRD_SYMBOL_A_20241230_093545
  status: filled
  fill_price: 485.45
  quantity: 100
  
# Update stop loss
tool: update_stop_loss
params:
  position_id: POS_SYMBOL_A_12345
  new_stop: 483.00
  trail: true
returns:
  updated: true
  order_id: ORD_67890
```

### Stage 6: Orchestration & Coordination

#### Orchestration MCP Server (Port 5009)

**Workflow Management via MCP Sessions:**
```python
class TradingWorkflowSession:
    """Orchestrates complete trading workflow via MCP"""
    
    async def run_trading_cycle(self):
        async with MCPSession("orchestrator") as session:
            # 1. Start cycle
            cycle = await session.tool("start_trading_cycle", {
                "mode": self._get_market_mode()
            })
            
            # 2. Collect news
            news_result = await session.tool("news/collect_news", {
                "sources": "all"
            })
            
            # 3. Run scanner
            scan_result = await session.tool("scanner/scan_market", {
                "mode": cycle.mode,
                "news_context": news_result.summary
            })
            
            # 4. Analyze patterns (TOP 5 only)
            for symbol in scan_result.top_5:
                patterns = await session.tool("patterns/detect_patterns", {
                    "symbol": symbol,
                    "catalyst_context": scan_result.catalysts[symbol]
                })
                
                # 5. Generate signals
                if patterns.has_valid_patterns:
                    signal = await session.tool("technical/generate_signal", {
                        "symbol": symbol,
                        "patterns": patterns.data
                    })
                    
                    # 6. Execute trades
                    if signal.confidence > 0.75:
                        trade = await session.tool("trading/execute_trade", {
                            "signal_id": signal.signal_id
                        })
            
            # 7. Complete cycle
            await session.tool("complete_cycle", {
                "cycle_id": cycle.cycle_id
            })
```

## Complete MCP Data Flow Diagram

```
External Sources          MCP Resources            MCP Tools              MCP Events
     │                         │                        │                      │
     ▼                         ▼                        ▼                      ▼
┌─────────┐            ┌──────────────┐        ┌──────────────┐      ┌──────────────┐
│ NewsAPI │───────────▶│ news/raw     │        │ collect_news │      │news.realtime │
│ yfinance│            │ news/by-     │        │ analyze_     │      │news.alert    │
│ Alpaca  │            │   symbol     │        │   sentiment  │      │              │
└─────────┘            └──────┬───────┘        └──────┬───────┘      └──────┬───────┘
                              │                        │                      │
                              ▼                        ▼                      │
                       ┌──────────────┐        ┌──────────────┐              │
                       │ candidates/  │◀───────│ scan_market  │              │
                       │   active     │        │ scan_pre-    │              │
                       │ market/      │        │   market     │              ▼
                       │   universe   │        └──────┬───────┘      ┌──────────────┐
                       └──────┬───────┘               │              │ Event Stream │
                              │                        ▼              │   Handler    │
                              ▼                ┌──────────────┐      └──────┬───────┘
                       ┌──────────────┐        │ detect_      │              │
                       │ patterns/    │◀───────│   patterns   │              │
                       │   detected   │        │ analyze_     │              ▼
                       │ patterns/    │        │   pattern    │      ┌──────────────┐
                       │   statistics │        └──────┬───────┘      │ Claude/Client│
                       └──────┬───────┘               │              │  Subscribe   │
                              │                        ▼              │  & React    │
                              ▼                ┌──────────────┐      └──────────────┘
                       ┌──────────────┐        │ generate_    │
                       │ signals/     │◀───────│   signal     │
                       │   pending    │        │ validate_    │
                       │ indicators/  │        │   signal     │
                       │   current    │        └──────┬───────┘
                       └──────┬───────┘               │
                              │                        ▼
                              ▼                ┌──────────────┐
                       ┌──────────────┐        │ execute_     │
                       │ positions/   │◀───────│   trade      │
                       │   open       │        │ close_       │
                       │ trades/      │        │   position   │
                       │   history    │        └──────────────┘
                       └──────────────┘
```

## MCP Session State Management

### Stateful Workflows
```python
class MCPStatefulSession:
    """Maintains context across multiple MCP calls"""
    
    def __init__(self, server_id: str):
        self.session_id = generate_session_id()
        self.context = {}
        self.history = []
    
    async def execute_workflow(self, workflow_def: dict):
        """Execute multi-step workflow with state preservation"""
        
        for step in workflow_def['steps']:
            # Access previous step results
            if step.get('depends_on'):
                step['params'].update(
                    self._resolve_dependencies(step['depends_on'])
                )
            
            # Execute step
            if step['type'] == 'resource':
                result = await self.resource(step['target'], step['params'])
            else:  # tool
                result = await self.tool(step['target'], step['params'])
            
            # Store result in context
            self.context[step['id']] = result
            self.history.append({
                'step': step['id'],
                'timestamp': datetime.now(),
                'result': result
            })
```

## MCP Resource Caching

### Resource Cache Patterns
```yaml
Cache Strategy:
  # Frequently accessed, slow changing
  - resource: patterns/statistics
    ttl: 3600  # 1 hour
    
  # Real-time data
  - resource: positions/open
    ttl: 0  # No cache
    
  # Market data
  - resource: indicators/*/current
    ttl: 300  # 5 minutes
    
  # Historical data
  - resource: trades/history
    ttl: 86400  # 24 hours
```

## Error Handling in MCP

### MCP Error Responses
```python
class MCPError:
    """Standardized MCP error handling"""
    
    ERROR_TYPES = {
        'resource_not_found': 404,
        'tool_execution_failed': 500,
        'invalid_parameters': 400,
        'unauthorized': 401,
        'rate_limited': 429
    }
    
    @staticmethod
    def handle_error(error_type: str, details: dict) -> MCPErrorResponse:
        return MCPErrorResponse(
            error_type=error_type,
            error_code=MCPError.ERROR_TYPES[error_type],
            message=details.get('message'),
            retry_after=details.get('retry_after'),
            context=details.get('context')
        )
```

## Performance Optimization

### MCP Request Batching
```python
# Batch multiple resource requests
batch_request = MCPBatchRequest([
    ResourceRequest("candidates/active"),
    ResourceRequest("news/by-symbol/SYMBOL_A"),
    ResourceRequest("patterns/by-symbol/SYMBOL_A")
])

# Single round trip
batch_response = await session.batch(batch_request)
```

### Streaming Responses
```python
# Stream large datasets
async for chunk in session.stream_resource("trades/history", {"date": "2024-12-30"}):
    process_trades(chunk.data)
```

## Monitoring MCP Data Flows

### Flow Metrics
```yaml
MCP Metrics:
  - mcp.resource.latency
  - mcp.tool.execution_time
  - mcp.session.duration
  - mcp.error.rate
  - mcp.cache.hit_rate
  
Per-Flow Tracking:
  - flow.news_to_trade.duration
  - flow.scan_to_signal.conversion_rate
  - flow.signal_to_execution.latency
```

### Claude Interaction Tracking
```python
class ClaudeInteractionLogger:
    """Track Claude's MCP usage patterns"""
    
    def log_interaction(self, interaction: MCPInteraction):
        self.metrics.track({
            'session_id': interaction.session_id,
            'resources_accessed': len(interaction.resources),
            'tools_invoked': len(interaction.tools),
            'total_duration': interaction.duration,
            'workflow_completed': interaction.workflow_success
        })
```

## Summary

The MCP Data Flow architecture transforms the Catalyst Trading System from REST-based service communication to a unified MCP protocol that:

1. **Resources** replace GET endpoints for data access
2. **Tools** replace POST/PUT/DELETE for actions
3. **Sessions** enable stateful multi-step workflows
4. **Events** provide real-time data streams
5. **Claude Integration** allows natural language interaction with all data flows

This architecture maintains all existing functionality while enabling AI-native interactions and preparing for advanced autonomous trading workflows.