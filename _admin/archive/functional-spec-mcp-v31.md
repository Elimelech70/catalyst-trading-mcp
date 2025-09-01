# Catalyst Trading System - MCP Functional Specification v3.1.0 (CORRECTED)

**Version**: 3.1.0  
**Date**: August 22, 2025  
**Platform**: DigitalOcean with MCP Architecture  
**Status**: MCP Implementation Ready - CORRECTED PORT ASSIGNMENTS  
**Previous Version**: 2.1.0 (July 9, 2025)

## Revision History

### v3.0.0 (August 22, 2025) - CORRECTED
- **Port Assignments**: Orchestration correctly assigned to port 5000
- **Database Architecture**: New Database MCP Service on port 5010
- **Service Dependencies**: All services use MCP Database Client
- **Implementation Reality**: Reflects actual service configurations
- **Migration Strategy**: Phased approach from database_utils.py

### v3.0.0 (December 30, 2024)
- **MCP Architecture**: All services exposed via MCP protocol
- **AI-Native Operations**: Business logic accessible to Claude
- **Resource/Tool Model**: Endpoints replaced with MCP resources and tools
- **Session Workflows**: Complex operations via MCP sessions
- **Natural Language**: Business rules interpretable by AI
- **Maintained Core Logic**: 50 securities scanned, top 5 traded

## Table of Contents

1. [System Overview](#1-system-overview)
2. [CORRECTED MCP Service Specifications](#2-corrected-mcp-service-specifications)
3. [Core Business Logic in MCP](#3-core-business-logic-in-mcp)
4. [CORRECTED Data Flow Specifications](#4-corrected-data-flow-specifications)
5. [Database Operations via MCP](#5-database-operations-via-mcp)
6. [Performance Requirements](#6-performance-requirements)
7. [Security Requirements](#7-security-requirements)
8. [Implementation Phases](#8-implementation-phases)

---

## 1. System Overview

### 1.1 Purpose
The Catalyst Trading System is an AI-native, news-driven algorithmic trading platform where Claude and other AI assistants can discover and execute day trading opportunities through natural language interaction with MCP services.

### 1.2 CORRECTED Service Architecture

```yaml
CORRECTED Port Assignments:
  Orchestration MCP Server:     5000  # ← CORRECTED: Primary Claude endpoint
  Scanner MCP Server:          5001  
  Pattern Analysis MCP Server: 5002  
  Technical Analysis MCP Server: 5003  
  Trading Execution MCP Server: 5005  
  News Intelligence MCP Server: 5008  
  Reporting MCP Server:        5009  
  Database MCP Server:         5010  # ← NEW: Replaces database_utils.py
  Redis Cache:                 6379  

Claude Desktop Connection:
  Primary Endpoint: ws://localhost:5000/mcp  # ← CORRECTED
  Orchestration Service: Port 5000
```

### 1.3 Key Differentiators with MCP
- **AI-First Design**: Business logic exposed as MCP resources and tools
- **Natural Language Trading**: Claude interprets market conditions and executes trades
- **Comprehensive Monitoring**: ALL 50 scanned securities recorded via Database MCP Service
- **Focused Execution**: Only TOP 5 proceed to trading
- **Stateful Workflows**: Complex trading strategies via MCP sessions
- **Centralized Data**: All database operations through Database MCP Service

### 1.4 Operating Modes via MCP

```yaml
# Get current market mode - CORRECTED endpoint
resource: trading/mode/current
service: orchestration (port 5000)
returns:
  mode: pre-market|normal|after-hours|weekend
  scan_frequency: 5min|30min|60min
  aggressiveness: high|medium|low

# Set operating mode - CORRECTED endpoint
tool: set_trading_mode
service: orchestration (port 5000)
params:
  mode: aggressive|normal|light|maintenance
  reason?: string
returns:
  mode_changed: boolean
  next_scan: timestamp
```

---

## 2. CORRECTED MCP Service Specifications

### 2.1 Orchestration MCP Server (Port 5000) - CORRECTED

**Claude's Primary Connection Point**

#### Resources (Read Operations)
```yaml
# Get workflow status
resource: workflow/status
returns:
  current_cycle:
    cycle_id: string
    status: running|stopped|paused
    start_time: timestamp
  recent_cycles: array
  performance_summary: object

# Get service health
resource: health/services
returns:
  services:
    database: {status: healthy, port: 5010}  # ← NEW
    news: {status: healthy, port: 5008}
    scanner: {status: healthy, port: 5001}
    pattern: {status: healthy, port: 5002}
    technical: {status: healthy, port: 5003}
    trading: {status: healthy, port: 5005}
    reporting: {status: healthy, port: 5009}

# Get trading configuration
resource: config/trading
returns:
  trading_enabled: boolean
  max_positions: number
  position_size_pct: number
  risk_limits: object
```

#### Tools (Write Operations)
```yaml
# Start trading cycle
tool: start_trading_cycle
params:
  mode: aggressive|normal|light
  target_securities?: number
returns:
  cycle_id: string
  estimated_duration: string
  services_activated: array

# Stop trading
tool: stop_trading
params:
  reason: string
  emergency?: boolean
returns:
  cycle_stopped: boolean
  positions_closed: number
  final_pnl: number

# Update configuration
tool: update_config
params:
  config_key: string
  config_value: any
returns:
  updated: boolean
  requires_restart: boolean
```

### 2.2 Database MCP Server (Port 5010) - NEW SERVICE

**Replaces database_utils.py for all services**

#### Resources (Read Operations)
```yaml
# Database health status
resource: db/status
returns:
  postgresql:
    status: healthy|degraded|unhealthy
    active_connections: number
    connection_pool_size: number
  redis:
    status: healthy|degraded|unhealthy
    memory_usage: string
    hit_rate: number

# Database performance metrics
resource: db/metrics
params:
  timeframe?: 1h|6h|24h
returns:
  query_performance:
    avg_query_time: number
    slow_queries: number
  connection_metrics:
    pool_efficiency: number
    connection_errors: number
```

#### Tools (Write Operations)
```yaml
# Persist trading signal
tool: persist_trading_signal
params:
  signal_data:
    symbol: string
    signal_type: string
    confidence: number
    entry_price?: number
    stop_loss?: number
    take_profit?: number
    metadata?: object
returns:
  signal_id: string
  success: boolean

# Persist trade record
tool: persist_trade_record
params:
  trade_data:
    signal_id?: string
    symbol: string
    side: buy|sell
    quantity: number
    entry_price: number
    metadata?: object
returns:
  trade_id: string
  success: boolean

# Get pending signals
tool: get_pending_signals
params:
  limit?: number
  min_confidence?: number
returns:
  signals: array

# Create trading cycle
tool: create_trading_cycle
params:
  cycle_data:
    scan_type: string
    target_securities: number
    config: object
returns:
  cycle_id: string

# Log workflow step
tool: log_workflow_step
params:
  cycle_id: string
  step: string
  status: string
  details?: object
returns:
  logged: boolean
```

### 2.3 News Intelligence MCP Server (Port 5008)

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

# Get trending news
resource: news/trending
params:
  hours?: number
  limit?: number
returns:
  trending_symbols: array
  news_volume: object
```

#### Tools (Write Operations)
```yaml
# Collect news from all sources
tool: collect_news_all_sources
params:
  mode: aggressive|normal|light
  sources?: array
returns:
  articles_collected: number
  new_articles: number
  duplicates: number
  execution_time: number

# Analyze sentiment
tool: analyze_sentiment
params:
  symbol: string
  timeframe?: string
returns:
  sentiment_score: number
  confidence: number
  key_factors: array
```

### 2.4 Security Scanner MCP Server (Port 5001)

#### Resources (Read Operations)
```yaml
# Get active trading candidates
resource: candidates/active
params:
  min_score?: number
  scan_id?: string
returns:
  candidates: array  # Top 5 for trading
  scan_metadata: object

# Get scanning universe
resource: market/universe
params:
  include_metrics?: boolean
returns:
  tracked_securities: array  # Up to 100 tracked
  universe_size: number
  last_updated: timestamp

# Get market status
resource: market/status
returns:
  is_open: boolean
  current_session: pre-market|regular|after-hours|closed
  next_open: timestamp
```

#### Tools (Write Operations)
```yaml
# Run market scan
tool: scan_market
params:
  mode: normal|aggressive|light
  universe_size?: number
  catalyst_required?: boolean
returns:
  scan_id: string
  candidates_found: number
  top_candidates: array  # Top 5
  execution_time: number

# Pre-market scan
tool: scan_premarket
params:
  symbols?: array
returns:
  premarket_movers: array
  scan_id: string
```

### 2.5 Pattern Analysis MCP Server (Port 5002)

#### Resources (Read Operations)
```yaml
# Get detected patterns
resource: patterns/detected
params:
  symbol?: string
  timeframe?: string
  min_confidence?: number
returns:
  patterns: array
  pattern_summary: object

# Get pattern statistics
resource: patterns/statistics
params:
  pattern_types?: array
  timeframe?: string
returns:
  pattern_effectiveness: object
  success_rates: object
```

#### Tools (Write Operations)
```yaml
# Detect patterns for candidates
tool: detect_patterns_for_candidates
params:
  candidates: array  # Top 5 from scanner
  catalyst_context?: object
returns:
  patterns_detected: object
  analyzed_symbols: number

# Validate pattern
tool: validate_pattern
params:
  pattern_type: string
  symbol: string
  historical_data?: boolean
returns:
  validation_score: number
  recommendation: proceed|skip|wait
```

### 2.6 Technical Analysis MCP Server (Port 5003)

#### Resources (Read Operations)
```yaml
# Get current indicators
resource: indicators/current/{symbol}
params:
  timeframe?: string
  indicators?: array
returns:
  indicators: object
  trend_analysis: object
  support_resistance: object

# Get pending signals
resource: signals/pending
params:
  min_confidence?: number
returns:
  signals: array
  signal_summary: object
```

#### Tools (Write Operations)
```yaml
# Generate trading signals
tool: generate_trading_signals
params:
  candidates: array  # Top 5 from scanner
  pattern_data?: object
  catalyst_data?: object
returns:
  signals_generated: number
  signals: array

# Calculate risk levels
tool: calculate_risk_levels
params:
  symbol: string
  entry_price: number
  position_size: number
returns:
  stop_loss: number
  take_profit: number
  risk_reward_ratio: number
```

### 2.7 Trading Execution MCP Server (Port 5005)

#### Resources (Read Operations)
```yaml
# Get open positions
resource: positions/open
returns:
  positions: array
  total_exposure: number
  unrealized_pnl: number

# Get account status
resource: account/status
returns:
  buying_power: number
  portfolio_value: number
  day_trades_remaining: number
```

#### Tools (Write Operations)
```yaml
# Execute signals batch
tool: execute_signals_batch
params:
  cycle_id?: string
  limit?: number
returns:
  trades_executed: number
  successful_trades: number
  failed_trades: number
  results: array

# Close position
tool: close_position
params:
  symbol: string
  reason: string
returns:
  closed: boolean
  exit_price: number
  realized_pnl: number
```

### 2.8 Reporting MCP Server (Port 5009)

#### Resources (Read Operations)
```yaml
# Get daily summary
resource: reporting/summary/daily
params:
  date?: string
returns:
  trading_summary: object
  performance_metrics: object
  top_performers: array

# Get system health report
resource: reporting/health/system
returns:
  overall_status: healthy|degraded|critical
  service_status: object
  alerts: array
```

#### Tools (Write Operations)
```yaml
# Generate report
tool: generate_custom_report
params:
  report_type: performance|risk|patterns
  timeframe: string
  parameters?: object
returns:
  report_id: string
  report_data: object

# Export data
tool: export_data
params:
  data_type: trades|signals|patterns
  format: json|csv|excel
  timeframe: string
returns:
  export_id: string
  download_url: string
```

---

## 3. Core Business Logic in MCP

### 3.1 Trading Workflow via MCP (CORRECTED)

```yaml
# Complete trading workflow through orchestration service (port 5000)
1. Claude → Orchestration (5000): start_trading_cycle
2. Orchestration → News (5008): collect_news_all_sources  
3. Orchestration → Scanner (5001): scan_market
4. Scanner → Database (5010): persist scan results (up to 100 securities)
5. Orchestration → Pattern (5002): detect_patterns_for_candidates (top 5)
6. Orchestration → Technical (5003): generate_trading_signals (top 5)
7. Technical → Database (5010): persist_trading_signal (for each signal)
8. Orchestration → Trading (5005): execute_signals_batch
9. Trading → Database (5010): persist_trade_record (for each trade)
10. Claude ← Orchestration (5000): workflow completion summary

Data Persistence Model:
- ALL scanned securities (up to 100) → Database MCP Service
- TOP 5 candidates → Pattern analysis → Technical signals → Trading
- ALL trading activity → Database MCP Service
- NO direct database connections by services
```

### 3.2 Core Business Rules in MCP

```yaml
# Market scanning rules
Market Universe:
  - Scan up to 100 securities per cycle
  - Store ALL scan results in database
  - Track universe changes over time
  - Focus analysis on TOP 5 candidates

# Signal generation rules  
Signal Requirements:
  - Minimum confidence: 60%
  - Maximum positions: 5 concurrent
  - Required catalyst support
  - Technical pattern confirmation

# Risk management rules
Risk Limits:
  - Maximum position size: 2% of portfolio
  - Stop loss: Automatically set
  - Take profit: 2:1 risk/reward minimum
  - Daily loss limit: 4% of portfolio

# Data persistence rules
Database Operations:
  - All operations through Database MCP Service (port 5010)
  - No direct database connections
  - Centralized transaction management
  - Audit trail for all operations
```

---

## 4. CORRECTED Data Flow Specifications

### 4.1 MCP Data Flow with Database Service

```yaml
# News Collection Flow
News Service (5008) → Database Service (5010):
  tool: persist_news_article
  data: {headline, source, symbol, catalyst_data}

# Market Scanning Flow  
Scanner Service (5001) → Database Service (5010):
  tool: persist_scan_results  
  data: {scan_id, securities_data[100], top_candidates[5]}

# Pattern Analysis Flow
Pattern Service (5002) → Database Service (5010):
  tool: persist_pattern_detection
  data: {symbol, pattern_type, confidence, catalyst_alignment}

# Signal Generation Flow
Technical Service (5003) → Database Service (5010):
  tool: persist_trading_signal
  data: {symbol, signal_type, confidence, risk_levels}

# Trade Execution Flow
Trading Service (5005) → Database Service (5010):
  tool: persist_trade_record
  data: {signal_id, execution_details, position_data}

# Reporting Flow
Reporting Service (5009) → Database Service (5010):
  tool: get_performance_data
  returns: {aggregated_metrics, trade_history, pattern_results}
```

### 4.2 Claude Interaction Patterns (CORRECTED)

```yaml
# Claude connects to orchestration service
Claude Desktop → Orchestration Service (ws://localhost:5000/mcp)

# Natural language examples
"Start an aggressive trading cycle":
  → tool: start_trading_cycle {mode: "aggressive"}
  
"What are today's trading candidates?":
  → resource: workflow/status
  → resource: candidates/active
  
"Show me the current portfolio":
  → resource: positions/open
  → resource: account/status
  
"How is the system performing?":
  → resource: health/services  
  → resource: reporting/summary/daily
```

---

## 5. Database Operations via MCP

### 5.1 CORRECTED Database Architecture

```yaml
# OLD Architecture (being phased out)
All Services → database_utils.py → Direct PostgreSQL/Redis

# NEW Architecture (target)
All Services → MCPDatabaseClient → Database MCP Service (5010) → PostgreSQL/Redis

Benefits:
- Centralized connection management
- Consistent error handling
- Transaction management
- Audit logging
- Performance monitoring
- No direct database credentials in services
```

### 5.2 Database MCP Client Usage Pattern

```python
# How services now access database (CORRECTED pattern)
from mcp_database_client import MCPDatabaseClient

class TradingService:
    def __init__(self):
        # Connect to Database MCP Service on port 5010
        self.db_client = MCPDatabaseClient("ws://localhost:5010")
    
    async def save_trade(self, trade_data):
        # Use MCP tool instead of direct SQL
        trade_id = await self.db_client.persist_trade_record(trade_data)
        return trade_id
    
    async def get_open_positions(self):
        # Use MCP tool instead of direct query
        positions = await self.db_client.get_open_positions()
        return positions
```

### 5.3 Database Service Capabilities

```yaml
# Data persistence tools (replacing database_utils functions)
Persistence Operations:
  persist_trading_signal    # Replaces insert_trading_signal()
  persist_trade_record      # Replaces insert_trade_record()  
  persist_news_article      # Replaces insert_news_article()
  persist_pattern_detection # Replaces pattern insertion
  persist_scan_results      # New: comprehensive scan storage
  
# Query operations (replacing direct queries)
Query Operations:
  get_pending_signals       # Replaces get_pending_signals()
  get_open_positions        # Replaces position queries
  get_recent_news           # Replaces news queries
  get_trading_history       # Replaces trade history queries
  
# Workflow operations (replacing utility functions)
Workflow Operations:
  create_trading_cycle      # Replaces create_trading_cycle()
  update_trading_cycle      # Replaces update_trading_cycle()
  log_workflow_step         # Replaces log_workflow_step()
```

---

## 6. Performance Requirements

### 6.1 MCP Response Times (CORRECTED)

```yaml
Resource Response Times:
  Orchestration (5000): < 100ms (Claude's primary connection)
  Database (5010): < 50ms (critical path)
  Scanner (5001): < 500ms (market data)
  Pattern (5002): < 200ms (analysis)
  Technical (5003): < 100ms (signals)
  Trading (5005): < 1000ms (execution)
  News (5008): < 200ms (collection)
  Reporting (5009): < 500ms (analytics)

Tool Execution Times:
  start_trading_cycle: < 2 seconds
  scan_market: < 30 seconds
  detect_patterns: < 10 seconds  
  generate_signals: < 5 seconds
  execute_trades: < 2 seconds per trade
  persist_data: < 100ms (database operations)
```

### 6.2 Throughput Requirements (CORRECTED)

```yaml
System Capacity:
  Concurrent Claude sessions: 10+
  Database operations/second: 1000+ (via MCP)
  Market data processing: 100 securities in 30s
  Pattern analysis: 5 symbols in 10s
  Signal generation: 5 signals in 5s
  Trade execution: 5 trades in 10s
  News processing: 100 articles in 60s
```

---

## 7. Security Requirements

### 7.1 MCP Authentication (CORRECTED)

```yaml
Service Authentication:
  Claude → Orchestration (5000): Session token
  Services → Database (5010): Service credentials
  Inter-service: mTLS certificates
  External APIs: Encrypted API keys

Database Security:
  - No direct database credentials in services
  - All database access through MCP Database Service
  - Centralized credential management
  - Audit logging of all operations
```

### 7.2 Trading Security via MCP

```yaml
Trading Safeguards:
  - execute_trade tool requires "trader" role
  - Position limits enforced at Database MCP Service level
  - Stop losses validated before persistence
  - Manual override through orchestration service
  - All trades logged with full audit trail
```

---

## 8. Implementation Phases

### 8.1 Phase 1: Database MCP Service Deployment (Week 1)

```yaml
Deploy Database MCP Service:
  - New service on port 5010
  - Implement all persistence tools
  - Implement all query tools  
  - Test with existing database_utils in
