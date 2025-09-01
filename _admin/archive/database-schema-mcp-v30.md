# Catalyst Trading System - MCP Database Schema & Access Layer v3.0.0

**Version**: 3.0.0  
**Date**: December 30, 2024  
**Database**: PostgreSQL with MCP Access Layer  
**Previous Version**: 2.1.0 (July 8, 2025)

## Revision History

### v3.0.0 (December 30, 2024)
- **MCP Access Layer**: Added MCP resource and tool mappings for all tables
- **Resource URIs**: Defined RESTful-style URIs for MCP resources
- **Tool Definitions**: Created MCP tools for all data modifications
- **Query Abstraction**: SQL queries wrapped in MCP protocol
- **Schema Unchanged**: Underlying PostgreSQL schema remains v2.1.0
- **Access Control**: MCP-based permissions layer

## Table of Contents

1. [Schema Overview with MCP](#1-schema-overview-with-mcp)
2. [MCP Resource & Tool Mappings](#2-mcp-resource--tool-mappings)
3. [News & Intelligence Tables](#3-news--intelligence-tables)
4. [Trading Operations Tables](#4-trading-operations-tables)
5. [Analysis & Pattern Tables](#5-analysis--pattern-tables)
6. [System & Coordination Tables](#6-system--coordination-tables)
7. [MCP Query Patterns](#7-mcp-query-patterns)
8. [MCP Access Control](#8-mcp-access-control)

---

## 1. Schema Overview with MCP

### 1.1 MCP Database Access Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Clients                               │
│         (Claude Desktop, Custom Clients, Web UI)                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                    MCP Access Layer                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Resource Handlers                      │   │
│  │                                                           │   │
│  │  • news/*          → SELECT from news tables             │   │
│  │  • trades/*        → SELECT from trading tables          │   │
│  │  • patterns/*      → SELECT from analysis tables         │   │
│  │  • system/*        → SELECT from system tables           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      Tool Handlers                        │   │
│  │                                                           │   │
│  │  • insert_news     → INSERT into news_raw                │   │
│  │  • create_signal   → INSERT into trading_signals         │   │
│  │  • execute_trade   → INSERT into trade_records           │   │
│  │  • update_position → UPDATE trade_records                │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                 PostgreSQL Database (v2.1.0)                     │
│           (Schema structure unchanged from v2.1.0)               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 MCP Access Principles

1. **Resources = Read Operations**: All SELECT queries exposed as MCP resources
2. **Tools = Write Operations**: All INSERT/UPDATE/DELETE exposed as MCP tools
3. **URI Pattern**: `{table_group}/{specific_resource}/{identifier}`
4. **Filtering**: Query parameters in resource requests
5. **Pagination**: Built into all collection resources
6. **Caching**: Resource responses cached based on volatility

---

## 2. MCP Resource & Tool Mappings

### 2.1 Resource Naming Convention

```yaml
Pattern: {domain}/{collection}/{identifier}?{filters}

Examples:
  - news/raw?since=2024-12-30&limit=100
  - news/by-symbol/SYMBOL_A?timeframe=24h
  - trades/open
  - trades/history/2024-12-30
  - patterns/by-symbol/SYMBOL_A
  - system/health/services
```

### 2.2 Tool Naming Convention

```yaml
Pattern: {action}_{entity}

Examples:
  - insert_news
  - create_candidate
  - generate_signal
  - execute_trade
  - update_position
  - close_trade
```

---

## 3. News & Intelligence Tables

### 3.1 news_raw Table

**PostgreSQL Schema (Unchanged):**
```sql
CREATE TABLE news_raw (
    id BIGSERIAL,
    news_id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(10),
    headline TEXT NOT NULL,
    source VARCHAR(200) NOT NULL,
    published_timestamp TIMESTAMPTZ NOT NULL,
    -- ... (rest of schema remains the same)
);
```

**MCP Resource Mappings:**
```yaml
# Get raw news
resource: news/raw
params:
  since?: timestamp
  until?: timestamp
  symbol?: string
  source?: string
  source_tier?: number
  limit?: number (default: 100)
  offset?: number
returns:
  type: news_collection
  data: NewsArticle[]
  metadata: {total_count, has_more}

# Get news by ID
resource: news/raw/{news_id}
returns:
  type: news_article
  data: NewsArticle

# Get news by symbol
resource: news/by-symbol/{symbol}
params:
  timeframe?: string (1h, 24h, 7d, 30d)
  source_tier?: number
returns:
  type: symbol_news
  data: NewsArticle[]
```

**MCP Tool Mappings:**
```yaml
# Insert news article
tool: insert_news
params:
  headline: string
  source: string
  symbol?: string
  published_timestamp: timestamp
  content_snippet?: string
  metadata?: object
returns:
  news_id: string
  created: boolean

# Update news accuracy
tool: update_news_accuracy
params:
  news_id: string
  was_accurate: boolean
  outcome_data?: object
returns:
  updated: boolean
```

### 3.2 source_metrics Table

**MCP Resource Mappings:**
```yaml
# Get all source metrics
resource: news/sources/metrics
params:
  min_tier?: number
  min_accuracy?: number
returns:
  type: source_metrics_collection
  data: SourceMetrics[]

# Get specific source metrics
resource: news/sources/{source_name}/metrics
returns:
  type: source_metrics
  data: SourceMetrics
```

**MCP Tool Mappings:**
```yaml
# Update source metrics
tool: update_source_metrics
params:
  source_name: string
  metrics: {
    total_articles?: number
    accurate_predictions?: number
    false_predictions?: number
  }
returns:
  updated: boolean
```

### 3.3 narrative_clusters Table

**MCP Resource Mappings:**
```yaml
# Get narrative clusters
resource: news/narratives/clusters
params:
  symbol?: string
  cluster_type?: string
  since?: timestamp
returns:
  type: narrative_cluster_collection
  data: NarrativeCluster[]

# Get specific cluster
resource: news/narratives/{cluster_id}
returns:
  type: narrative_cluster
  data: NarrativeCluster
```

---

## 4. Trading Operations Tables

### 4.1 trading_candidates Table

**MCP Resource Mappings:**
```yaml
# Get active candidates
resource: candidates/active
params:
  min_score?: number
  scan_id?: string
returns:
  type: candidate_collection
  data: TradingCandidate[]
  metadata: {scan_id, timestamp}

# Get candidate history
resource: candidates/history
params:
  date?: string
  symbol?: string
  limit?: number
returns:
  type: candidate_history
  data: TradingCandidate[]
```

**MCP Tool Mappings:**
```yaml
# Create trading candidate
tool: create_candidate
params:
  scan_id: string
  symbol: string
  catalyst_score: number
  catalyst_keywords: string[]
  metadata: object
returns:
  candidate_id: number
  created: boolean
```

### 4.2 trading_signals Table

**MCP Resource Mappings:**
```yaml
# Get pending signals
resource: signals/pending
params:
  min_confidence?: number
  symbol?: string
returns:
  type: signal_collection
  data: TradingSignal[]

# Get signal by ID
resource: signals/{signal_id}
returns:
  type: trading_signal
  data: TradingSignal

# Get signal history
resource: signals/history
params:
  date?: string
  symbol?: string
  executed_only?: boolean
returns:
  type: signal_history
  data: TradingSignal[]
```

**MCP Tool Mappings:**
```yaml
# Generate trading signal
tool: generate_signal
params:
  symbol: string
  signal_type: BUY|SELL|HOLD
  confidence: number
  components: {
    catalyst_score: number
    pattern_score: number
    technical_score: number
    volume_score: number
  }
  entry_exit: {
    recommended_entry: number
    stop_loss: number
    target_1: number
    target_2: number
  }
returns:
  signal_id: string
  created: boolean

# Mark signal executed
tool: mark_signal_executed
params:
  signal_id: string
  execution_timestamp: timestamp
  actual_entry: number
returns:
  updated: boolean
```

### 4.3 trade_records Table

**MCP Resource Mappings:**
```yaml
# Get open positions
resource: trades/positions/open
returns:
  type: position_collection
  data: Position[]
  metadata: {total_value, total_pnl}

# Get trade history
resource: trades/history
params:
  date?: string
  symbol?: string
  status?: open|closed|cancelled
  limit?: number
returns:
  type: trade_history
  data: TradeRecord[]

# Get specific trade
resource: trades/{trade_id}
returns:
  type: trade_record
  data: TradeRecord
```

**MCP Tool Mappings:**
```yaml
# Execute trade
tool: execute_trade
params:
  signal_id?: string
  symbol: string
  side: buy|sell
  quantity: number
  order_type: market|limit
  entry_price?: number
  catalyst_info?: {
    entry_catalyst: string
    entry_news_id: string
    catalyst_score: number
  }
returns:
  trade_id: string
  status: string
  fill_price: number

# Update trade exit
tool: close_trade
params:
  trade_id: string
  exit_price: number
  exit_reason: stop_loss|take_profit|signal|manual
returns:
  updated: boolean
  pnl: number
  pnl_percentage: number
```

---

## 5. Analysis & Pattern Tables

### 5.1 pattern_analysis Table

**MCP Resource Mappings:**
```yaml
# Get patterns by symbol
resource: patterns/by-symbol/{symbol}
params:
  timeframe?: string
  pattern_type?: string
  min_confidence?: number
  catalyst_required?: boolean
returns:
  type: pattern_collection
  data: Pattern[]

# Get pattern statistics
resource: patterns/statistics
params:
  pattern_types?: string[]
  with_catalyst?: boolean
  timeframe?: string
returns:
  type: pattern_stats
  data: {
    pattern_type: string
    success_rate: number
    avg_confidence: number
    total_detected: number
  }[]
```

**MCP Tool Mappings:**
```yaml
# Record pattern detection
tool: record_pattern
params:
  symbol: string
  pattern_type: string
  confidence: number
  timeframe: string
  pattern_data: object
  catalyst_context?: {
    has_catalyst: boolean
    catalyst_type: string
    catalyst_aligned: boolean
  }
returns:
  pattern_id: number
  created: boolean

# Update pattern outcome
tool: update_pattern_outcome
params:
  pattern_id: number
  pattern_completed: boolean
  actual_move: number
  success: boolean
returns:
  updated: boolean
```

### 5.2 technical_indicators Table

**MCP Resource Mappings:**
```yaml
# Get current indicators
resource: indicators/{symbol}/current
params:
  timeframe?: string (default: 5min)
  indicators?: string[] (specific indicators)
returns:
  type: indicator_snapshot
  data: TechnicalIndicators

# Get indicator history
resource: indicators/{symbol}/history
params:
  timeframe: string
  start: timestamp
  end: timestamp
  indicators?: string[]
returns:
  type: indicator_history
  data: TechnicalIndicators[]
```

---

## 6. System & Coordination Tables

### 6.1 trading_cycles Table

**MCP Resource Mappings:**
```yaml
# Get current cycle
resource: system/cycles/current
returns:
  type: trading_cycle
  data: TradingCycle

# Get cycle history
resource: system/cycles/history
params:
  date?: string
  status?: running|completed|failed
returns:
  type: cycle_history
  data: TradingCycle[]
```

**MCP Tool Mappings:**
```yaml
# Start trading cycle
tool: start_trading_cycle
params:
  mode: aggressive|normal|light
returns:
  cycle_id: string
  started: boolean

# Update cycle metrics
tool: update_cycle_metrics
params:
  cycle_id: string
  metrics: {
    news_collected?: number
    candidates_selected?: number
    signals_generated?: number
    trades_executed?: number
  }
returns:
  updated: boolean
```

### 6.2 service_health Table

**MCP Resource Mappings:**
```yaml
# Get service health
resource: system/health/services
params:
  service_name?: string
  status?: healthy|degraded|down
returns:
  type: service_health_collection
  data: ServiceHealth[]

# Get specific service health
resource: system/health/services/{service_name}
returns:
  type: service_health
  data: ServiceHealth
```

### 6.3 configuration Table

**MCP Resource Mappings:**
```yaml
# Get configuration
resource: system/config
params:
  category?: trading|risk|schedule|api
  active_only?: boolean
returns:
  type: config_collection
  data: ConfigEntry[]

# Get specific config
resource: system/config/{key}
returns:
  type: config_entry
  data: ConfigEntry
```

**MCP Tool Mappings:**
```yaml
# Update configuration
tool: update_config
params:
  key: string
  value: string
  modified_by: string
returns:
  updated: boolean
  previous_value: string
```

---

## 7. MCP Query Patterns

### 7.1 Resource Query Translation

MCP resources are translated to SQL queries:

```python
class ResourceQueryTranslator:
    """Translates MCP resource requests to SQL"""
    
    def translate_resource(self, resource_uri: str, params: dict) -> str:
        if resource_uri == "news/raw":
            return self._build_news_query(params)
        elif resource_uri.startswith("patterns/by-symbol/"):
            symbol = resource_uri.split("/")[-1]
            return self._build_pattern_query(symbol, params)
        # ... other resource mappings
    
    def _build_news_query(self, params: dict) -> str:
        query = "SELECT * FROM news_raw WHERE 1=1"
        
        if params.get("since"):
            query += f" AND published_timestamp >= '{params['since']}'"
        if params.get("symbol"):
            query += f" AND symbol = '{params['symbol']}'"
        if params.get("source_tier"):
            query += f" AND source_tier <= {params['source_tier']}"
        
        query += f" ORDER BY published_timestamp DESC"
        query += f" LIMIT {params.get('limit', 100)}"
        
        return query
```

### 7.2 Tool Command Translation

MCP tools are translated to SQL commands:

```python
class ToolCommandTranslator:
    """Translates MCP tool invocations to SQL"""
    
    def translate_tool(self, tool_name: str, params: dict) -> str:
        if tool_name == "insert_news":
            return self._build_insert_news(params)
        elif tool_name == "execute_trade":
            return self._build_execute_trade(params)
        # ... other tool mappings
    
    def _build_insert_news(self, params: dict) -> str:
        news_id = generate_news_id(
            params['headline'],
            params['source'],
            params['published_timestamp']
        )
        
        return f"""
            INSERT INTO news_raw (
                news_id, symbol, headline, source,
                published_timestamp, content_snippet, metadata
            ) VALUES (
                '{news_id}', '{params.get('symbol', '')}',
                '{params['headline']}', '{params['source']}',
                '{params['published_timestamp']}',
                '{params.get('content_snippet', '')}',
                '{json.dumps(params.get('metadata', {}))}'::jsonb
            )
        """
```

### 7.3 Transaction Management

```python
class MCPTransactionManager:
    """Manages database transactions for MCP operations"""
    
    async def execute_transaction(self, operations: List[MCPOperation]):
        async with self.get_connection() as conn:
            async with conn.transaction():
                results = []
                for op in operations:
                    if op.type == "tool":
                        result = await self._execute_tool(conn, op)
                    else:  # resource
                        result = await self._execute_resource(conn, op)
                    results.append(result)
                return results
```

---

## 8. MCP Access Control

### 8.1 Resource Permissions

```yaml
Permission Model:
  # Public read access
  - news/raw: public
  - patterns/statistics: public
  - system/health/*: public
  
  # Authenticated read
  - candidates/*: authenticated
  - signals/*: authenticated
  - indicators/*: authenticated
  
  # Owner-only access
  - trades/positions/*: owner
  - trades/history: owner
  
  # Admin only
  - system/config/*: admin
```

### 8.2 Tool Permissions

```yaml
Tool Permissions:
  # News operations
  - insert_news: news_writer
  - update_news_accuracy: system
  
  # Trading operations
  - generate_signal: trader
  - execute_trade: trader
  - close_trade: trader
  
  # System operations
  - update_config: admin
  - start_trading_cycle: system
```

### 8.3 Row-Level Security

```python
class MCPRowLevelSecurity:
    """Implements row-level security for MCP access"""
    
    def apply_rls(self, query: str, user_context: dict) -> str:
        if "trades" in query and user_context.role != "admin":
            # Add user filter
            query += f" AND user_id = '{user_context.user_id}'"
        
        if "positions" in query and user_context.role != "admin":
            # Add account filter
            query += f" AND account_id = '{user_context.account_id}'"
        
        return query
```

## Summary

The MCP Database Schema & Access Layer v3.0.0 provides:

1. **Unchanged Schema**: PostgreSQL schema remains stable at v2.1.0
2. **MCP Access Layer**: All database operations through MCP resources and tools
3. **Standardized URIs**: Consistent resource naming patterns
4. **Query Translation**: Automatic SQL generation from MCP requests
5. **Access Control**: Fine-grained permissions through MCP
6. **Performance**: Caching and query optimization built into MCP layer

This architecture allows Claude and other AI assistants to interact with the database through a clean, well-defined protocol while maintaining the robustness and performance of PostgreSQL.