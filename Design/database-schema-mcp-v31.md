# Catalyst Trading System - MCP Database Schema & Access Layer v3.1.0

**Version**: 3.1.0  
**Date**: August 23, 2025  
**Database**: PostgreSQL with MCP Access Layer  
**Previous Version**: 3.0.0 (December 30, 2024)

## Revision History

### v3.1.0 (August 23, 2025)
- **Service Port Updates**: Aligned all references with architecture v3.1.0
- **Database Service Port**: Confirmed on port 5010
- **Access Pattern Updates**: Updated examples to use corrected port assignments
- **Query Pattern Examples**: Fixed service interaction examples

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

### Database Architecture

```yaml
Physical Layer:
  - PostgreSQL 15+ on DigitalOcean
  - 200+ tables across 6 domains
  - Partitioned time-series data
  - Read replicas for analysis

MCP Access Layer (Port 5010):
  - All queries through MCP protocol
  - Resource URIs for reads
  - Tools for writes
  - Event streams for changes
  
Service Connections:
  - Orchestration (5000) → Database (5010)
  - Scanner (5001) → Database (5010)
  - Pattern (5002) → Database (5010)
  - Technical (5003) → Database (5010)
  - Trading (5005) → Database (5010)
  - News (5008) → Database (5010)
  - Reporting (5009) → Database (5010)
```

### Key Design Principles

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
    content_snippet TEXT,
    sentiment_score DECIMAL(3,2),
    sentiment_label VARCHAR(20),
    relevance_score DECIMAL(3,2),
    source_tier INTEGER DEFAULT 3,
    has_catalyst BOOLEAN DEFAULT FALSE,
    catalyst_type VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_published (symbol, published_timestamp DESC),
    INDEX idx_source_tier (source_tier, published_timestamp DESC),
    INDEX idx_catalyst (has_catalyst, published_timestamp DESC)
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
    accuracy_rate?: number
    avg_catalyst_strength?: number
  }
returns:
  updated: boolean
  new_tier?: number
```

---

## 4. Trading Operations Tables

### 4.1 trading_signals Table

**PostgreSQL Schema:**
```sql
CREATE TABLE trading_signals (
    signal_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    signal_strength DECIMAL(3,2),
    entry_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    risk_reward_ratio DECIMAL(4,2),
    confidence_score DECIMAL(3,2),
    news_catalyst_ids TEXT[],
    pattern_ids TEXT[],
    technical_indicators JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    INDEX idx_symbol_created (symbol, created_at DESC),
    INDEX idx_status_expires (status, expires_at)
);
```

**MCP Resource Mappings:**
```yaml
# Get active signals
resource: signals/active
params:
  symbol?: string
  min_strength?: number
  signal_type?: string
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
  symbol?: string
  date?: date
  status?: string
returns:
  type: signal_history
  data: TradingSignal[]
```

**MCP Tool Mappings:**
```yaml
# Generate new signal
tool: generate_signal
params:
  symbol: string
  signal_type: string
  entry_price: number
  stop_loss: number
  take_profit: number
  confidence_score: number
  catalyst_ids?: string[]
returns:
  signal_id: number
  created: boolean

# Update signal status
tool: update_signal_status
params:
  signal_id: number
  status: active|executed|expired|cancelled
  execution_data?: object
returns:
  updated: boolean
```

### 4.2 trades Table

**MCP Resource Mappings:**
```yaml
# Get open positions
resource: trades/positions/open
params:
  symbol?: string
  min_pnl?: number
returns:
  type: position_collection
  data: Position[]

# Get trade history
resource: trades/history
params:
  symbol?: string
  date_from?: date
  date_to?: date
  status?: string
returns:
  type: trade_history
  data: Trade[]
```

**MCP Tool Mappings:**
```yaml
# Execute trade
tool: execute_trade
params:
  signal_id: number
  symbol: string
  side: buy|sell
  quantity: number
  order_type: market|limit
  price?: number
returns:
  trade_id: string
  execution_price: number
  status: string

# Update position
tool: update_position
params:
  trade_id: string
  stop_loss?: number
  take_profit?: number
  trailing_stop?: boolean
returns:
  updated: boolean

# Close position
tool: close_position
params:
  trade_id: string
  quantity?: number (partial close)
  reason?: string
returns:
  closed: boolean
  pnl: number
```

---

## 5. Analysis & Pattern Tables

### 5.1 pattern_recognition Table

**MCP Resource Mappings:**
```yaml
# Get patterns by symbol
resource: patterns/by-symbol/{symbol}
params:
  pattern_type?: string
  timeframe?: string
  min_confidence?: number
returns:
  type: pattern_collection
  data: Pattern[]

# Get pattern statistics
resource: patterns/statistics
params:
  pattern_type?: string
  timeframe?: string
returns:
  type: pattern_stats
  data: {
    pattern_type: string
    occurrence_count: number
    success_rate: number
    avg_return: number
  }[]
```

### 5.2 technical_indicators Table

**MCP Resource Mappings:**
```yaml
# Get current indicators
resource: indicators/{symbol}/current
returns:
  type: indicator_snapshot
  data: {
    rsi: number
    macd: object
    bb: object
    volume_profile: object
    calculated_at: timestamp
  }

# Get indicator history
resource: indicators/{symbol}/history
params:
  indicator?: string
  timeframe?: string
  limit?: number
returns:
  type: indicator_history
  data: IndicatorValue[]
```

---

## 6. System & Coordination Tables

### 6.1 system_health Table

**MCP Resource Mappings:**
```yaml
# Get system health
resource: system/health
returns:
  type: system_health
  data: {
    services: ServiceHealth[]
    database: DatabaseHealth
    cache: CacheHealth
    last_check: timestamp
  }

# Get service-specific health
resource: system/health/{service_name}
returns:
  type: service_health
  data: ServiceHealth
```

### 6.2 coordination_state Table

**MCP Tool Mappings:**
```yaml
# Update workflow state
tool: update_workflow_state
params:
  workflow_id: string
  stage: string
  status: string
  metadata?: object
returns:
  updated: boolean

# Create checkpoint
tool: create_checkpoint
params:
  workflow_id: string
  checkpoint_data: object
returns:
  checkpoint_id: string
  created: boolean
```

---

## 7. MCP Query Patterns

### 7.1 Resource Query Translation

```python
class MCPResourceTranslator:
    """Translates MCP resource requests to SQL"""
    
    def translate_resource(self, resource_uri: str, params: dict) -> str:
        # Parse URI
        parts = resource_uri.split('/')
        domain = parts[0]
        collection = parts[1]
        
        # Build SQL based on pattern
        if domain == "news" and collection == "raw":
            return self._build_news_query(params)
        elif domain == "trades" and collection == "positions":
            return self._build_positions_query(params)
        # ... more patterns
    
    def _build_news_query(self, params: dict) -> str:
        query = "SELECT * FROM news_raw WHERE 1=1"
        
        if params.get('symbol'):
            query += f" AND symbol = '{params['symbol']}'"
        if params.get('since'):
            query += f" AND published_timestamp >= '{params['since']}'"
        
        query += f" ORDER BY published_timestamp DESC"
        query += f" LIMIT {params.get('limit', 100)}"
        
        return query
```

### 7.2 Tool Command Translation

```python
class MCPToolTranslator:
    """Translates MCP tool calls to SQL commands"""
    
    def translate_tool(self, tool_name: str, params: dict) -> str:
        if tool_name == "insert_news":
            return self._build_insert_news(params)
        elif tool_name == "execute_trade":
            return self._build_execute_trade(params)
        # ... more tools
    
    def _build_insert_news(self, params: dict) -> str:
        news_id = f"news_{int(time.time() * 1000)}"
        return f"""
            INSERT INTO news_raw 
            (news_id, symbol, headline, source, published_timestamp, 
             content_snippet, metadata)
            VALUES 
            ('{news_id}', '{params.get('symbol', '')}',
             '{params['headline']}', '{params['source']}',
             '{params['published_timestamp']}',
             '{params.get('content_snippet', '')}',
             '{json.dumps(params.get('metadata', {}))}'::jsonb)
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

## Integration Examples

### Example: Morning Trading Cycle via MCP

```python
# Orchestration Service (Port 5000) coordinating with Database (Port 5010)
async def morning_trading_cycle():
    async with MCPSession("orchestration", "database:5010") as db:
        # 1. Check system health
        health = await db.resource("system/health")
        
        # 2. Warm cache for active symbols
        await db.tool("warm_cache", {
            "symbols": ["SYMBOL_A", "SYMBOL_B", "SYMBOL_C"],
            "cache_types": ["patterns", "indicators", "news"]
        })
        
        # 3. Get market candidates
        candidates = await db.resource("candidates/active")
        
        # 4. Generate signals
        for candidate in candidates:
            signal = await db.tool("generate_signal", {
                "symbol": candidate.symbol,
                "signal_type": "morning_breakout",
                # ... signal parameters
            })
        
        # 5. Update system state
        await db.tool("update_workflow_state", {
            "workflow_id": "morning_cycle",
            "stage": "signals_generated",
            "status": "complete"
        })
```

## Summary

The MCP Database Schema & Access Layer v3.1.0 provides:

1. **Unchanged Schema**: PostgreSQL schema remains stable at v2.1.0
2. **MCP Access Layer**: All database operations through MCP resources and tools via port 5010
3. **Standardized URIs**: Consistent resource naming patterns
4. **Query Translation**: Automatic SQL generation from MCP requests
5. **Access Control**: Fine-grained permissions through MCP
6. **Performance**: Caching and query optimization built into MCP layer
7. **Service Integration**: Clear patterns for all services to interact with database

This architecture allows Claude and other AI assistants to interact with the database through a clean, well-defined protocol while maintaining the robustness and performance of PostgreSQL.