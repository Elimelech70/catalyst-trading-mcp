# Catalyst Trading System - MCP Database Services & Data Management v3.0.0

**Version**: 3.0.0  
**Date**: December 30, 2024  
**Platform**: DigitalOcean with MCP Service Layer  
**Purpose**: Database services exposed through MCP protocol

## Revision History

### v3.0.0 (December 30, 2024)
- **MCP Service Layer**: All database operations through MCP protocol
- **Session Management**: MCP sessions replace connection pooling
- **Resource-Based Monitoring**: Database metrics as MCP resources
- **Tool-Based Operations**: Migrations, backups as MCP tools
- **Event Streams**: Real-time database events via MCP
- **Claude Integration**: Natural language database operations

## Table of Contents

1. [Overview](#1-overview)
2. [MCP Database Service Architecture](#2-mcp-database-service-architecture)
3. [MCP Session Management](#3-mcp-session-management)
4. [Data Persistence via MCP Tools](#4-data-persistence-via-mcp-tools)
5. [Cache Management Resources](#5-cache-management-resources)
6. [Migration & Schema Tools](#6-migration--schema-tools)
7. [Backup & Recovery Tools](#7-backup--recovery-tools)
8. [Data Synchronization Tools](#8-data-synchronization-tools)
9. [Performance Monitoring Resources](#9-performance-monitoring-resources)
10. [Claude Database Assistant](#10-claude-database-assistant)

---

## 1. Overview

### 1.1 MCP Database Services Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude & MCP Clients                          │
│         Natural Language → MCP Protocol Translation              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                  MCP Database Services Layer                     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Session Management                      │   │
│  │  • Connection pooling abstracted as MCP sessions          │   │
│  │  • Transaction management via session context             │   │
│  │  • Automatic retry and failover                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Database Resources (Read)                 │   │
│  │  • db/status          • cache/stats                      │   │
│  │  • db/metrics         • db/locks                         │   │
│  │  • db/slow-queries    • db/connections                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Database Tools (Write)                   │   │
│  │  • persist_news       • run_migration                    │   │
│  │  • persist_trade      • create_backup                    │   │
│  │  • sync_data          • optimize_tables                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Event Streams                          │   │
│  │  • db.transaction     • cache.invalidation               │   │
│  │  • db.error           • backup.completed                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│         PostgreSQL (Managed) + Redis (Cache) + DO Spaces         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Transformations

| Legacy Service | MCP Equivalent |
|---------------|----------------|
| database_utils.py | MCP Session Manager |
| get_db_connection() | MCP session context |
| Connection pooling | Automatic via MCP |
| Direct SQL | MCP resources/tools |
| Health checks | db/status resource |

---

## 2. MCP Database Service Architecture

### 2.1 Service Registration

```python
class DatabaseMCPServer:
    """MCP server for database services"""
    
    def __init__(self):
        self.server = MCPServer("database-services")
        self._register_resources()
        self._register_tools()
        self._register_events()
    
    def _register_resources(self):
        """Register read-only database resources"""
        
        @self.server.resource("db/status")
        async def get_database_status(params: ResourceParams) -> ResourceResponse:
            """Get overall database health and status"""
            status = await self._check_database_health()
            return ResourceResponse(
                type="database_status",
                data={
                    "postgresql": status.pg_status,
                    "redis": status.redis_status,
                    "connection_pool": status.pool_stats,
                    "replication_lag": status.replication_lag
                }
            )
        
        @self.server.resource("db/metrics")
        async def get_database_metrics(params: ResourceParams) -> ResourceResponse:
            """Get performance metrics"""
            timeframe = params.get("timeframe", "1h")
            metrics = await self._collect_metrics(timeframe)
            return ResourceResponse(
                type="database_metrics",
                data=metrics
            )
```

### 2.2 MCP Service Integration Map

```yaml
Database Services as MCP:
  # Connection Management
  - Legacy: get_db_connection()
    MCP: Automatic session management
    
  # Health Monitoring  
  - Legacy: health_check()
    MCP: resource: db/status
    
  # Performance Metrics
  - Legacy: get_database_metrics()
    MCP: resource: db/metrics
    
  # Data Operations
  - Legacy: insert_*, update_*
    MCP: tool: persist_*, update_*
    
  # Cache Operations
  - Legacy: Redis client calls
    MCP: resource: cache/*, tool: cache_*
```

---

## 3. MCP Session Management

### 3.1 Session-Based Connection Management

```python
class MCPDatabaseSession:
    """Database session management via MCP"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.transaction_active = False
        self.connection = None
        
    async def __aenter__(self):
        """Start database session"""
        self.connection = await self._acquire_connection()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End database session"""
        if exc_type and self.transaction_active:
            await self.connection.rollback()
        elif self.transaction_active:
            await self.connection.commit()
        await self._release_connection()
    
    async def begin_transaction(self):
        """Start a database transaction"""
        await self.connection.execute("BEGIN")
        self.transaction_active = True
        
    async def execute_in_session(self, operation: MCPOperation):
        """Execute operation within session context"""
        if operation.requires_transaction and not self.transaction_active:
            await self.begin_transaction()
        
        return await operation.execute(self.connection)
```

### 3.2 Session Resources

```yaml
# Get active sessions
resource: db/sessions/active
returns:
  sessions:
    - session_id: sess_12345
      started_at: 2024-12-30T10:00:00Z
      transaction_active: true
      operations_count: 15
      
# Get session details
resource: db/sessions/{session_id}
returns:
  session_id: sess_12345
  connection_info:
    pool_id: pool_1
    backend_pid: 12345
  transaction_state: active
  locks_held: []
```

### 3.3 Session Tools

```yaml
# Start a new session
tool: start_db_session
params:
  isolation_level?: read_committed|repeatable_read|serializable
  read_only?: boolean
returns:
  session_id: string
  expires_in: number

# Execute in transaction
tool: execute_transaction
params:
  session_id: string
  operations: MCPOperation[]
returns:
  results: any[]
  transaction_id: string
```

---

## 4. Data Persistence via MCP Tools

### 4.1 News Persistence Tools

```yaml
# Persist news with catalyst tracking
tool: persist_news_catalyst
params:
  headline: string
  source: string
  symbol?: string
  published_timestamp: timestamp
  catalyst_indicators:
    keywords: string[]
    urgency_score: number
    market_state: pre-market|regular|after-hours
returns:
  news_id: string
  catalyst_score: number
  source_metrics_updated: boolean

# Batch persist news
tool: persist_news_batch
params:
  articles: NewsArticle[]
  deduplicate: boolean
returns:
  total_processed: number
  new_articles: number
  duplicates: number
  catalyst_scores: object
```

### 4.2 Trading Data Persistence

```yaml
# Persist trading signal
tool: persist_trading_signal
params:
  symbol: string
  signal_type: BUY|SELL|HOLD
  confidence: number
  catalyst_context:
    news_ids: string[]
    catalyst_type: string
    catalyst_score: number
  technical_context:
    patterns: string[]
    indicators: object
returns:
  signal_id: string
  risk_parameters: object

# Persist trade execution
tool: persist_trade_execution
params:
  signal_id?: string
  symbol: string
  side: buy|sell
  quantity: number
  execution_details:
    order_type: market|limit
    fill_price: number
    fill_time: timestamp
  catalyst_tracking:
    entry_catalyst: string
    entry_news_id: string
returns:
  trade_id: string
  position_updated: boolean
```

### 4.3 Pattern & Analysis Persistence

```yaml
# Persist pattern detection
tool: persist_pattern_detection
params:
  symbol: string
  pattern_type: string
  confidence: number
  catalyst_alignment:
    has_catalyst: boolean
    catalyst_type?: string
    alignment_score: number
returns:
  pattern_id: number
  historical_success_rate: number
```

---

## 5. Cache Management Resources

### 5.1 Cache Status Resources

```yaml
# Get cache statistics
resource: cache/stats
returns:
  redis_info:
    used_memory: 256MB
    hit_rate: 0.92
    evicted_keys: 1234
    connected_clients: 12
    
# Get cached keys by pattern
resource: cache/keys
params:
  pattern: string (e.g., "pattern:*")
  limit?: number
returns:
  keys: string[]
  total_matching: number
```

### 5.2 Cache Management Tools

```yaml
# Cache pattern detection
tool: cache_pattern_result
params:
  symbol: string
  pattern_type: string
  result: object
  ttl?: number (seconds, default: 300)
returns:
  cached: boolean
  key: string

# Invalidate cache
tool: invalidate_cache
params:
  pattern?: string (key pattern)
  symbol?: string (invalidate all for symbol)
  cache_type?: patterns|indicators|sentiment
returns:
  keys_deleted: number

# Warm cache
tool: warm_cache
params:
  symbols: string[]
  cache_types: string[]
returns:
  warmed_entries: number
  duration_ms: number
```

---

## 6. Migration & Schema Tools

### 6.1 Migration Resources

```yaml
# Get migration status
resource: db/migrations/status
returns:
  current_version: 210
  pending_migrations:
    - version: 211
      name: add_ml_tables
      description: Add tables for ML model results
      
# Get migration history
resource: db/migrations/history
params:
  limit?: number
returns:
  migrations:
    - version: 210
      name: schema_v2.1.0_complete
      applied_at: 2024-07-08T10:00:00Z
      duration_ms: 1234
```

### 6.2 Migration Tools

```yaml
# Run pending migrations
tool: run_migrations
params:
  target_version?: number (run up to this version)
  dry_run?: boolean
returns:
  migrations_applied:
    - version: 211
      status: success
      duration_ms: 2345
  new_version: 211

# Create migration
tool: create_migration
params:
  name: string
  up_sql: string
  down_sql: string
returns:
  migration_file: string
  version: number

# Rollback migration
tool: rollback_migration
params:
  target_version: number
returns:
  rolled_back: number[]
  current_version: number
```

---

## 7. Backup & Recovery Tools

### 7.1 Backup Status Resources

```yaml
# Get backup status
resource: db/backups/latest
returns:
  latest_full:
    timestamp: 2024-12-30T03:00:00Z
    size: 1.2GB
    location: s3://catalyst-backups/full_20241230.sql
  latest_incremental:
    timestamp: 2024-12-30T14:00:00Z
    size: 45MB
    base_backup: full_20241230.sql

# Get backup history
resource: db/backups/history
params:
  type?: full|incremental
  days?: number
returns:
  backups: BackupInfo[]
```

### 7.2 Backup & Recovery Tools

```yaml
# Create backup
tool: create_backup
params:
  type: full|incremental
  compress?: boolean
  encrypt?: boolean
returns:
  backup_id: string
  location: string
  size_bytes: number
  duration_ms: number

# Restore from backup
tool: restore_backup
params:
  backup_id: string
  target_time?: timestamp (PITR)
  dry_run?: boolean
returns:
  restore_status: success|failed
  tables_restored: number
  duration_ms: number

# Verify backup
tool: verify_backup
params:
  backup_id: string
returns:
  valid: boolean
  issues: string[]
```

---

## 8. Data Synchronization Tools

### 8.1 Sync Status Resources

```yaml
# Get sync status
resource: db/sync/status
returns:
  catalyst_outcomes:
    pending_updates: 45
    last_sync: 2024-12-30T14:30:00Z
  source_metrics:
    pending_calculations: 12
    last_update: 2024-12-30T14:25:00Z
```

### 8.2 Data Synchronization Tools

```yaml
# Sync catalyst outcomes
tool: sync_catalyst_outcomes
params:
  since?: timestamp
  batch_size?: number
returns:
  trades_processed: number
  news_accuracy_updated: number
  source_metrics_updated: number

# Sync source reliability
tool: sync_source_metrics
params:
  sources?: string[] (specific sources)
  recalculate_all?: boolean
returns:
  sources_updated: number
  accuracy_changes: object

# Sync pattern success rates
tool: sync_pattern_outcomes
params:
  pattern_types?: string[]
  timeframe?: string
returns:
  patterns_updated: number
  success_rate_changes: object
```

---

## 9. Performance Monitoring Resources

### 9.1 Database Performance Resources

```yaml
# Get slow queries
resource: db/performance/slow-queries
params:
  threshold_ms?: number (default: 1000)
  limit?: number
returns:
  queries:
    - query: SELECT * FROM news_raw WHERE...
      avg_time_ms: 1234
      calls: 567
      total_time_ms: 700000

# Get table statistics
resource: db/performance/tables
returns:
  tables:
    - name: news_raw
      size: 2.3GB
      rows: 1234567
      index_hit_rate: 0.98
      cache_hit_rate: 0.95
      
# Get connection pool stats
resource: db/performance/connections
returns:
  pool_stats:
    total: 10
    active: 3
    idle: 7
    waiting: 0
  connection_details: [...]
```

### 9.2 Performance Optimization Tools

```yaml
# Analyze query performance
tool: analyze_query
params:
  query: string
returns:
  execution_plan: object
  suggestions: string[]
  estimated_improvement: string

# Optimize tables
tool: optimize_tables
params:
  tables?: string[] (specific tables)
  operations: [vacuum, analyze, reindex]
returns:
  tables_optimized: number
  space_reclaimed: string
  duration_ms: number

# Update table statistics
tool: update_statistics
params:
  tables?: string[]
returns:
  updated: number
  duration_ms: number
```

---

## 10. Claude Database Assistant

### 10.1 Natural Language Database Operations

Claude can now perform database operations through natural language:

```
User: "How's the database doing today?"

Claude: I'll check the database status for you.

[Invokes resource: db/status]
[Invokes resource: db/performance/slow-queries]

The database is performing well:
- PostgreSQL: Healthy (99.9% uptime)
- Redis Cache: Healthy (92% hit rate)
- Connection Pool: 3/10 active connections
- No replication lag

I noticed 2 slow queries that might need optimization:
1. A news query taking 1.2s on average
2. A pattern analysis query taking 890ms

Would you like me to analyze these queries for optimization opportunities?
```

### 10.2 Intelligent Maintenance Workflows

```python
class ClaudeDatabaseAssistant:
    """Claude's database management capabilities"""
    
    async def daily_maintenance_check(self):
        """Claude's daily database maintenance workflow"""
        
        async with MCPSession("claude-maintenance") as session:
            # 1. Check overall health
            health = await session.resource("db/status")
            
            # 2. Review slow queries
            slow_queries = await session.resource("db/performance/slow-queries")
            
            # 3. Check backup status
            backups = await session.resource("db/backups/latest")
            
            # 4. Run optimizations if needed
            if self._needs_optimization(health, slow_queries):
                await session.tool("optimize_tables", {
                    "operations": ["vacuum", "analyze"]
                })
            
            # 5. Create backup if overdue
            if self._backup_overdue(backups):
                await session.tool("create_backup", {"type": "incremental"})
            
            # 6. Sync data if needed
            sync_status = await session.resource("db/sync/status")
            if sync_status.has_pending:
                await session.tool("sync_catalyst_outcomes")
                
            return self._generate_maintenance_report(
                health, slow_queries, backups, sync_status
            )
```

### 10.3 Proactive Problem Detection

```yaml
# Claude monitors these events
Event Subscriptions:
  - db.error: Database errors requiring attention
  - db.performance.degraded: Performance issues
  - cache.memory.high: Cache memory warnings
  - backup.failed: Backup failures
  - replication.lag: Replication delays

# Claude's automatic responses
Automatic Actions:
  - Slow query detected → Analyze and suggest optimization
  - Cache hit rate low → Recommend cache warming
  - Backup overdue → Create backup
  - Tables bloated → Schedule vacuum
  - Connection pool exhausted → Alert and investigate
```

## Summary

The MCP Database Services v3.0.0 transforms database management by:

1. **Session-Based Access**: Connection management through MCP sessions
2. **Resource-Based Monitoring**: All metrics exposed as MCP resources
3. **Tool-Based Operations**: Database operations as callable tools
4. **Event-Driven**: Real-time database events through MCP
5. **Claude Integration**: Natural language database management
6. **Automated Workflows**: Intelligent maintenance and optimization

This architecture enables Claude to act as an intelligent database administrator, proactively managing performance, backups, and data synchronization while maintaining the robustness of the underlying PostgreSQL and Redis infrastructure.