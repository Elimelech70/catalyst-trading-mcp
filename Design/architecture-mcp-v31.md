# Catalyst Trading System - MCP Architecture v3.1.0 (CORRECTED)

**Repository**: catalyst-trading-mcp  
**Version**: 3.0.0  
**Date**: Aug 22, 2025  
**Status**: MCP Migration Architecture - CORRECTED PORT ASSIGNMENTS  
**Previous Version**: 2.1.0 (July 8, 2025)

## Revision History

### v3.0.0 (August 22, 2025) - CORRECTED
- **Port Assignment Fix**: Orchestration service correctly assigned to port 5000
- **Removed Conflict**: Reporting service remains at 5009, no conflict
- **Docker Compose Alignment**: Matches actual docker-compose.yml configuration
- **Script Alignment**: Matches management script configurations

### v3.0.0 (December 30, 2024)
- **MCP Migration**: Complete architectural shift to Anthropic MCP
- **Server Architecture**: Each service becomes an MCP server
- **Resource Model**: Data access through MCP resources
- **Tool Model**: Actions exposed as MCP tools
- **Transport Layer**: WebSocket and stdio transports
- **Claude Integration**: Native integration with Claude Desktop
- **Backwards Compatibility**: Legacy REST APIs wrapped in MCP

## Executive Summary

The Catalyst Trading System has been re-architected to use Anthropic's Model Context Protocol (MCP), transforming it from a traditional microservice architecture to an AI-native system. Each service is now an MCP server exposing resources (data) and tools (actions), enabling Claude and other AI assistants to directly interact with the trading system.

## CORRECTED Port Assignments

```yaml
Service Port Assignments (CORRECTED):
  Orchestration:     5000  # ← CORRECTED: Was incorrectly 5009
  Scanner:          5001
  Pattern:          5002  
  Technical:        5003
  Trading:          5005
  News:             5008
  Reporting:        5009  # ← No conflict now
  Database MCP:     5010  # ← New service
  Redis:            6379
```

## MCP Service Architecture (CORRECTED)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Desktop                           │
│               MCP Client (stdio & websocket)                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ MCP Protocol
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                     MCP Service Layer                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Orchestration MCP Server                      │    │
│  │                    (Port 5000) ← CORRECTED             │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • workflow/status        • start_trading_cycle         │    │
│  │  • health/services        • stop_trading               │    │
│  │  • config/trading         • run_backtest               │    │
│  │                           • update_config              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            News Intelligence MCP Server                  │    │
│  │                    (Port 5008)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • news/raw               • collect_news                │    │
│  │  • news/by-symbol         • analyze_sentiment           │    │
│  │  • news/catalysts         • track_narrative             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            Security Scanner MCP Server                   │    │
│  │                    (Port 5001)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • candidates/active      • scan_market                 │    │
│  │  • candidates/history     • scan_premarket              │    │
│  │  • market/universe        • analyze_catalyst            │    │
│  │                           • select_candidates           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Pattern Analysis MCP Server                    │    │
│  │                    (Port 5002)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • patterns/detected      • detect_patterns             │    │
│  │  • patterns/by-symbol     • analyze_pattern             │    │
│  │  • patterns/success-rate  • validate_pattern            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │          Technical Analysis MCP Server                   │    │
│  │                    (Port 5003)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • indicators/current     • calculate_indicators        │    │
│  │  • signals/pending        • generate_signal             │    │
│  │  • signals/history        • validate_signal             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             Trading Execution MCP Server                │    │
│  │                    (Port 5005)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • positions/open         • execute_trade               │    │
│  │  • trades/history         • close_position              │    │
│  │  • account/status         • update_stop_loss            │    │
│  │                           • get_pnl                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Reporting & Analytics MCP Server               │    │
│  │                    (Port 5009)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • reporting/performance  • generate_report             │    │
│  │  • reporting/health       • export_data                 │    │
│  │  • analytics/patterns     • clear_cache                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Database MCP Server (NEW)                   │    │
│  │                    (Port 5010)                          │    │
│  │                                                         │    │
│  │  Resources:                Tools:                       │    │
│  │  • db/status              • persist_trade_record        │    │
│  │  • db/metrics             • persist_trading_signal      │    │
│  │  • cache/status           • create_trading_cycle        │    │
│  │                           • log_workflow_step           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                 Data & Infrastructure Layer                     │
│     (PostgreSQL, Redis, DigitalOcean - Unchanged)               │
└─────────────────────────────────────────────────────────────────┘
```

## Service Connection Points

### Claude Desktop Connection
```yaml
Primary MCP Endpoint:
  Protocol: WebSocket
  URL: ws://localhost:5000/mcp
  Service: Orchestration (CORRECTED PORT)
  
Alternative Development:
  Protocol: stdio
  Command: python orchestration-service.py --transport=stdio
```

### Inter-Service Communication
```yaml
Service Discovery:
  Orchestration → All Services (via WebSocket MCP)
  Database Service → PostgreSQL/Redis (direct)
  All Services → Database Service (via MCP)
```

## Deployment Configuration (CORRECTED)

### Docker Compose Ports (MATCHES IMPLEMENTATION)
```yaml
services:
  orchestration-service:
    ports: ["5000:5000"]  # ← CORRECTED
    
  news-service:
    ports: ["5008:5008"]
    
  scanner-service:
    ports: ["5001:5001"]
    
  pattern-service:
    ports: ["5002:5002"]
    
  technical-service:
    ports: ["5003:5003"]
    
  trading-service:
    ports: ["5005:5005"]
    
  reporting-service:
    ports: ["5009:5009"]  # ← No conflict now
    
  database-service:
    ports: ["5010:5010"]  # ← New
    
  redis:
    ports: ["6379:6379"]
```

### Environment Variables (CORRECTED)
```bash
# Service Ports (CORRECTED)
ORCHESTRATION_PORT=5000
NEWS_SERVICE_PORT=5008
SCANNER_SERVICE_PORT=5001
PATTERN_SERVICE_PORT=5002
TECHNICAL_SERVICE_PORT=5003
TRADING_SERVICE_PORT=5005
REPORTING_SERVICE_PORT=5009
DATABASE_SERVICE_PORT=5010

# MCP Configuration
MCP_TRANSPORT=websocket
CLAUDE_MCP_ENDPOINT=ws://localhost:5000/mcp

# Database (DigitalOcean Managed)
DATABASE_URL=postgresql://user:pass@host:25060/catalyst_trading
REDIS_URL=redis://localhost:6379/0
```

## Claude Integration Examples (CORRECTED ENDPOINT)

```bash
# Claude Desktop MCP Configuration
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": ["/path/to/orchestration-service.py"],
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}

# Or via WebSocket
{
  "mcpServers": {
    "catalyst-trading": {
      "url": "ws://localhost:5000/mcp"
    }
  }
}
```

## Benefits of MCP Architecture

### 1. AI-Native Design
- Services designed for AI interaction
- Natural language to action mapping
- Context preservation across interactions

### 2. Unified Protocol
- Single protocol for all communication
- Standardized error handling
- Built-in versioning and compatibility

### 3. Enhanced Observability
- All interactions logged in MCP format
- AI decision tracking
- Performance metrics per tool/resource

### 4. Improved Developer Experience
- Self-documenting resources and tools
- Interactive exploration via Claude
- Automatic client generation

### 5. Future-Proof Architecture
- Ready for advanced AI agents
- Supports multi-modal interactions
- Extensible for new AI capabilities

## Implementation Status

### CORRECTED File Conformance
```yaml
Current Files vs V30 Architecture:
  orchestration-service.py: ✅ Port 5000 (MATCHES)
  news-service.py:         ✅ Port 5008 (MATCHES)
  scanner-service.py:      ✅ Port 5001 (MATCHES)  
  pattern-service.py:      ✅ Port 5002 (MATCHES)
  technical-service.py:    ✅ Port 5003 (MATCHES)
  trading-service.py:      ✅ Port 5005 (MATCHES)
  reporting-service.py:    ✅ Port 5009 (MATCHES)
  database-mcp-service.py: ⚠️ NEW (Port 5010)
  
Docker Configuration:
  docker-compose.yml:      ✅ All ports match
  manage.sh:              ✅ All ports match
```

### Migration Requirements
```yaml
IMMEDIATE (Database Layer):
  - Deploy database-mcp-service.py on port 5010
  - Update all services to use MCP database client
  - Remove direct database connections
  
MEDIUM (Service Completeness):
  - Add missing resources per specification
  - Add missing tools per specification
  - Implement event streams
  
LOW (Optimization):
  - Performance tuning
  - Enhanced error handling
  - Advanced Claude features
```

## Security Considerations

### Port Security (CORRECTED)
```yaml
External Access:
  Port 5000: Orchestration (Claude Desktop access)
  
Internal Only:
  Ports 5001-5003: Analysis services
  Ports 5005,5008-5010: Execution/data services
  Port 6379: Redis cache
```

This corrected architecture document now properly reflects the actual implementation with orchestration on port 5000 and eliminates the port conflict with reporting on 5009.
