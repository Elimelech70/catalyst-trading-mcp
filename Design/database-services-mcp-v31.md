# Catalyst Trading System - MCP Database Services & Data Management v3.1.0

**Version**: 3.1.0  
**Date**: August 23, 2025  
**Platform**: DigitalOcean with MCP Service Layer  
**Purpose**: Database services exposed through MCP protocol

## Revision History

### v3.1.0 (August 23, 2025)
- **Port Corrections**: Updated all service port references to match architecture v3.1.0
- **Database Service Port**: Confirmed Database MCP Service on port 5010
- **Orchestration References**: Corrected from port 5009 to 5000
- **Service Integration**: Updated interaction patterns with corrected ports

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

The Database Services layer provides unified data management through MCP protocol, enabling Claude and other AI assistants to perform complex database operations through natural language.

### Service Port Reference (CORRECTED)

```yaml
Database MCP Service: Port 5010
Connected Services:
  - Orchestration: Port 5000 (CORRECTED - was 5009)
  - Scanner: Port 5001
  - Pattern Recognition: Port 5002
  - Technical Analysis: Port 5003
  - Trading Execution: Port 5005
  - News Intelligence: Port 5008
  - Reporting: Port 5009
```

### Key Benefits with MCP

1. **Natural Language Operations**: Claude can manage data through conversation
2. **Unified Access**: All services use same MCP protocol
3. **Session Context**: Maintains state across complex operations
4. **Real-Time Events**: Database changes stream to subscribers
5. **Intelligent Caching**: Claude optimizes cache strategies

---

## 2. MCP Database Service Architecture

### 2.1 Database MCP Server (Port 5010)

```python
class DatabaseMCPServer:
    """Centralized database operations via MCP"""
    
    # Resources (Read Operations)
    resources = {
        "db/tables/{table}/data": "Query any table",
        "db/performance/metrics": "Database performance stats",
        "db/cache/status": "Cache hit rates and usage",
        "db/migrations/status": "Schema version info",
        "db/backups/latest": "Recent backup status"
    }
    
    # Tools (Write Operations)
    tools = {
        "execute_query": "Run parameterized queries",
        "manage_transaction": "Multi-operation transactions",
        "invalidate_cache": "Clear cache entries",
        "run_migration": "Apply schema changes",
        "create_backup": "Initiate backup process"
    }
    
    # Event Streams
    events = [
        "db.schema_changed",
        "db.performance_degraded",
        "db.backup_completed",
        "db.cache_invalidated"
    ]
```

### 2.2 Service Integration Pattern

```yaml
# Services connect to Database MCP Service
Service Connections:
  News Intelligence (5008) → Database MCP (5010):
    - tool: insert_news
    - resource: news/raw
    
  Scanner (5001) → Database MCP (5010):
    - tool: update_candidates
    - resource: candidates/active
    
  Trading (5005) → Database MCP (5010):
    - tool: execute_trade
    - resource: positions/open
    
  Orchestration (5000) → Database MCP (5010):
    - tool: update_system_state
    - resource: system/health
```

---

## 3. MCP Session Management

### 3.1 Session Lifecycle

```python
class MCPDatabaseSession:
    """Manages stateful database interactions"""
    
    async def __aenter__(self):
        # Initialize MCP session
        self.session_id = await self._init_session()
        # Get database connection from pool
        self.conn = await self._get_connection()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Handle transaction commit/rollback
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        # Return connection to pool
        await self._release_connection()
        # Close MCP session
        await self._close_session()
```

### 3.2 Session Context Management

```yaml
# MCP maintains context across operations
session: trading_workflow_12345
context:
  user: claude_assistant
  operation: morning_trading_cycle
  started_at: 2024-12-30T09:00:00Z
  
operations:
  1. resource: candidates/active
  2. tool: generate_signal
  3. tool: execute_trade
  4. resource: positions/open
  
result: committed
```

---

## 4. Data Persistence via MCP Tools

### 4.1 Core Persistence Tools

```yaml
# Insert operations
tool: insert_record
params:
  table: string
  data: object
  returning?: string[]
returns:
  id: string
  created: timestamp

# Update operations
tool: update_records
params:
  table: string
  filter: object
  updates: object
  returning?: string[]
returns:
  updated_count: number
  records?: object[]

# Delete operations
tool: delete_records
params:
  table: string
  filter: object
  soft_delete?: boolean
returns:
  deleted_count: number
```

### 4.2 Bulk Operations

```yaml
# Bulk insert with conflict handling
tool: bulk_insert
params:
  table: string
  records: object[]
  on_conflict?: {
    columns: string[]
    action: "update" | "ignore"
    update_columns?: string[]
  }
returns:
  inserted: number
  updated: number
  ignored: number
```

---

## 5. Cache Management Resources

### 5.1 Cache Status Resources

```yaml
# Overall cache metrics
resource: db/cache/metrics
returns:
  hit_rate: 0.92
  miss_rate: 0.08
  total_keys: 1234
  memory_used: "45MB"
  evictions_24h: 234

# Pattern-specific cache status
resource: db/cache/patterns/{pattern}
params:
  pattern: "news:*" | "candidates:*" | "signals:*"
returns:
  matching_keys: 45
  total_size: "12MB"
  avg_ttl: 180
  hit_rate: 0.89

# Hot keys analysis
resource: db/cache/hot-keys
params:
  limit?: number
returns:
  keys: string[]
  access_counts: number[]
  last_access: timestamp[]
```

### 5.2 Cache Management Tools

```yaml
# Cache pattern detection results
tool: cache_pattern_result
params:
  symbol: string
  pattern_type: string
  result: object
  ttl?: number (seconds, default: 300)
returns:
  cached: boolean
  key: string

# Invalidate cache entries
tool: invalidate_cache
params:
  pattern?: string (key pattern)
  symbol?: string (invalidate all for symbol)
  cache_type?: patterns|indicators|sentiment
returns:
  keys_deleted: number

# Warm cache for trading day
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
# Get current migration status
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

# Create new migration
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
# Get latest backup information
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

# Verify backup integrity
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
# Get synchronization status
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

# Sync source reliability metrics
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
# Get slow query analysis
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
      
# Get connection pool statistics
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
[Uses resource: db/performance/metrics]
[Uses resource: db/cache/metrics]
[Uses resource: db/backups/latest]

Database Health Report:
- Performance: Excellent (avg query time: 45ms)
- Cache Hit Rate: 92% (very good)
- Last Backup: 2 hours ago (on schedule)
- Active Connections: 3/10 (normal load)
- No slow queries detected
```

### 10.2 Intelligent Optimization

```python
class ClaudeDatabaseOptimizer:
    """Claude actively optimizes database performance"""
    
    async def daily_optimization(self):
        # Analyze usage patterns
        patterns = await self.resource("db/performance/usage-patterns")
        
        # Identify optimization opportunities
        if patterns.cache_hit_rate < 0.8:
            # Warm frequently accessed data
            await self.tool("warm_cache", {
                "symbols": patterns.hot_symbols,
                "cache_types": ["patterns", "indicators"]
            })
        
        # Update statistics on busy tables
        if patterns.table_modifications > 1000:
            await self.tool("update_statistics", {
                "tables": patterns.modified_tables
            })
```

## Integration with Orchestration Service (Port 5000)

The Database MCP Service integrates closely with the Orchestration Service:

```yaml
Orchestration (5000) → Database (5010):
  Morning Startup:
    - tool: warm_cache
    - resource: db/performance/metrics
    - tool: update_statistics
    
  Trading Cycle:
    - resource: db/cache/status
    - tool: execute_query (via services)
    
  End of Day:
    - tool: create_backup
    - tool: sync_catalyst_outcomes
    - resource: db/performance/slow-queries
```

## Summary

The MCP Database Services v3.1.0 provides:

1. **Unified Access**: All database operations through MCP protocol on port 5010
2. **Natural Language**: Claude manages databases conversationally
3. **Performance**: Intelligent caching and optimization
4. **Reliability**: Automated backups and recovery
5. **Observability**: Real-time metrics and monitoring
6. **Port Clarity**: Corrected service interactions with Orchestration on port 5000

This architecture enables sophisticated database management while maintaining simplicity through the MCP protocol.