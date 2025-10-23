# Catalyst Trading System - Functional Specification v5.0

**Name of Application**: Catalyst Trading System  
**Name of file**: functional-spec-mcp-v50.md  
**Version**: 5.0.0  
**Last Updated**: 2025-10-22  
**Purpose**: Complete functional specification for 9-service architecture with separated Orchestration and Workflow

---

## REVISION HISTORY

**v5.0.0 (2025-10-22)** - 9-Service Architecture
- Added Workflow service (port 5006) for trade coordination
- Updated Orchestration service to MCP-only (no business logic)
- Separated concerns: Claude interface vs trade execution
- MCP tools now call Workflow service via REST
- Updated service matrix from 7 to 9 services
- Maintained hierarchical URI structure
- Maintained context parameters and error handling

**v4.1.0 (2025-08-31)** - Production-ready specification (superseded)
- 7-service architecture
- Orchestration handled both MCP and workflow

---

## Description

Comprehensive functional specification defining all MCP resources, tools, REST endpoints, and data flows for the 9-service architecture using Anthropic FastMCP best practices and hierarchical URI conventions.

**Key Architecture Change**: Orchestration service now focuses solely on MCP protocol communication with Claude, while the new Workflow service handles all trade coordination logic.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [MCP Resource Hierarchy](#2-mcp-resource-hierarchy)
3. [MCP Tools Specification](#3-mcp-tools-specification)
4. [REST API Specifications](#4-rest-api-specifications)
5. [Data Flow Specifications](#5-data-flow-specifications)
6. [Claude Interaction Patterns](#6-claude-interaction-patterns)
7. [Error Handling](#7-error-handling)
8. [Performance Requirements](#8-performance-requirements)

---

## 1. System Overview

### 1.1 Architecture Summary

The Catalyst Trading System uses a hybrid architecture with clear separation of concerns:
- **MCP Protocol**: Orchestration service for Claude Desktop communication
- **REST APIs**: Internal services for business logic and coordination
- **Direct Database**: PostgreSQL with connection pooling
- **Redis Cache**: Pub/sub and caching layer

### 1.2 Service Matrix

| Service | Protocol | Port | Responsibilities |
|---------|----------|------|------------------|
| **Orchestration** | **MCP** | **5000** | **Claude interface only (no business logic)** |
| **Workflow** | **REST** | **5006** | **Trade coordination, cycle management, signal routing** |
| Scanner | REST | 5001 | Market scanning (100 securities → 5 final) |
| Pattern | REST | 5002 | Pattern detection on candidates |
| Technical | REST | 5003 | Technical indicators and signals |
| Risk Manager | REST | 5004 | Position sizing, risk validation, safety controls |
| Trading | REST | 5005 | Order execution (risk-approved trades only) |
| News | REST | 5008 | Catalyst detection and sentiment |
| Reporting | REST | 5009 | Performance analytics |

### 1.3 Key Architecture Changes from v4.1

**Orchestration Service** (v4.1 → v5.0):
- ❌ **REMOVED**: Trade coordination logic
- ❌ **REMOVED**: Cycle management implementation
- ❌ **REMOVED**: Direct service orchestration
- ✅ **RETAINED**: MCP resources (read-only data access)
- ✅ **RETAINED**: MCP tools (command interface)
- ✅ **NEW**: All tool actions call Workflow service via REST

**Workflow Service** (NEW in v5.0):
- ✅ Receives commands from Orchestration via REST
- ✅ Coordinates all internal services
- ✅ Manages trading cycles
- ✅ Routes trade signals
- ✅ Handles emergency stops

### 1.4 Communication Flow

```
Claude Desktop
    ↓ MCP Protocol
Orchestration (Port 5000)
    ↓ HTTP/REST
Workflow (Port 5006)
    ↓ HTTP/REST
Scanner, Pattern, Technical, Risk, Trading, News, Reporting
    ↓ SQL
PostgreSQL Database
```

---

## 2. MCP Resource Hierarchy

**Implementation Note**: All resources are READ-ONLY. They provide Claude with system state information but do NOT modify state.

### 2.1 Complete Resource Tree

```
catalyst-orchestration/
├── trading-cycle/
│   ├── current                 # Current cycle configuration
│   ├── status                  # Detailed cycle status
│   └── history                 # Historical cycles
├── market-scan/
│   ├── results                 # Latest scan results
│   ├── candidates              # All candidates (50-100)
│   └── candidates/active       # Top 5 for trading
├── portfolio/
│   ├── positions               # All positions
│   ├── positions/open          # Currently open
│   ├── positions/closed        # Recently closed
│   └── performance             # Portfolio metrics
├── risk/
│   ├── current                 # Current risk metrics
│   ├── limits                  # Risk limits and usage
│   └── exposures               # Position exposures
├── analytics/
│   ├── daily-summary           # Today's performance
│   ├── weekly-summary          # Week performance
│   ├── performance             # Overall metrics
│   └── reports/custom          # Custom reports
└── system/
    ├── health                  # System health
    ├── health/services         # Individual service status
    ├── config                  # Configuration
    └── logs/recent             # Recent activity
```

### 2.2 Resource Implementation Pattern

**All resources query data but do NOT modify state**:

```python
from mcp import Context
from fastmcp import FastMCP

mcp = FastMCP("catalyst-orchestration")

@mcp.resource("trading-cycle/current")
async def get_current_cycle(ctx: Context) -> str:
    """
    Get current trading cycle information
    
    Returns:
        JSON string with cycle configuration:
        {
            "cycle_id": "20251022-001",
            "mode": "normal",
            "status": "active",
            "configuration": {
                "scan_frequency": 300,
                "max_positions": 5,
                "risk_level": 0.5
            },
            "started_at": "2025-10-22T09:30:00Z",
            "runtime": "2h 15m"
        }
    """
    # Query Workflow service for current cycle
    async with state.http_session.get(
        f"{WORKFLOW_URL}/api/v1/cycle/current"
    ) as resp:
        data = await resp.json()
        return json.dumps(data, indent=2)

@mcp.resource("market-scan/candidates/active")
async def get_active_candidates(ctx: Context) -> str:
    """
    Get top 5 active trading candidates
    
    Returns:
        JSON string with candidate list
    """
    # Query Scanner service for active candidates
    async with state.http_session.get(
        f"{SCANNER_URL}/api/v1/candidates/active"
    ) as resp:
        data = await resp.json()
        return json.dumps(data, indent=2)
```

### 2.3 Risk Resources (NEW in v5.0)

```python
@mcp.resource("risk/current")
async def get_current_risk(ctx: Context) -> str:
    """
    Get current portfolio risk metrics
    
    Returns:
        {
            "total_exposure": 25000.00,
            "position_count": 3,
            "largest_position_pct": 0.45,
            "var_1day_95": -450.00,
            "sharpe_ratio": 1.85,
            "available_buying_power": 75000.00
        }
    """
    async with state.http_session.get(
        f"{RISK_URL}/api/v1/metrics/current"
    ) as resp:
        data = await resp.json()
        return json.dumps(data, indent=2)

@mcp.resource("risk/limits")
async def get_risk_limits(ctx: Context) -> str:
    """
    Get risk limits and current usage
    
    Returns:
        {
            "max_position_size": {
                "limit": 10000.00,
                "used": 8500.00,
                "available": 1500.00
            },
            "max_portfolio_risk": {
                "limit": 0.02,
                "current": 0.0125
            },
            "max_positions": {
                "limit": 5,
                "open": 3,
                "available": 2
            }
        }
    """
    async with state.http_session.get(
        f"{RISK_URL}/api/v1/limits"
    ) as resp:
        data = await resp.json()
        return json.dumps(data, indent=2)
```

---

## 3. MCP Tools Specification

**Implementation Note**: All tools are ACTION triggers. They call the Workflow service via REST to execute commands.

### 3.1 Trading Cycle Tools

#### start_trading_cycle

```python
@mcp.tool()
async def start_trading_cycle(
    ctx: Context,
    mode: str = "normal",
    scan_frequency: int = 300,
    max_positions: int = 5,
    risk_level: float = 0.5,
    start_time: Optional[str] = None
) -> Dict:
    """
    Start a new trading cycle
    
    Args:
        mode: Trading mode (aggressive|normal|conservative)
        scan_frequency: Seconds between scans (60-3600)
        max_positions: Maximum concurrent positions (1-10)
        risk_level: Risk level (0.0-1.0)
        start_time: Optional scheduled start (ISO 8601)
    
    Returns:
        {
            "success": true,
            "cycle_id": "20251022-001",
            "message": "Trading cycle started",
            "configuration": {...}
        }
    
    Raises:
        McpError: If cycle cannot be started
    """
    # Validate parameters
    if mode not in ["aggressive", "normal", "conservative"]:
        raise McpError(
            "INVALID_PARAMETER",
            f"Invalid mode: {mode}. Must be aggressive|normal|conservative"
        )
    
    if not 60 <= scan_frequency <= 3600:
        raise McpError(
            "INVALID_PARAMETER",
            f"Scan frequency {scan_frequency} out of range (60-3600)"
        )
    
    if not 1 <= max_positions <= 10:
        raise McpError(
            "INVALID_PARAMETER",
            f"Max positions {max_positions} out of range (1-10)"
        )
    
    if not 0.0 <= risk_level <= 1.0:
        raise McpError(
            "INVALID_PARAMETER",
            f"Risk level {risk_level} out of range (0.0-1.0)"
        )
    
    # Call Workflow service to start cycle
    try:
        async with state.http_session.post(
            f"{WORKFLOW_URL}/api/v1/cycle/start",
            json={
                "mode": mode,
                "scan_frequency": scan_frequency,
                "max_positions": max_positions,
                "risk_level": risk_level,
                "start_time": start_time
            }
        ) as resp:
            if resp.status != 200:
                error_data = await resp.json()
                raise McpError(
                    "WORKFLOW_ERROR",
                    error_data.get("detail", "Failed to start cycle")
                )
            
            return await resp.json()
            
    except aiohttp.ClientError as e:
        raise McpError(
            "SERVICE_UNAVAILABLE",
            f"Workflow service unavailable: {str(e)}"
        )
```

#### stop_trading

```python
@mcp.tool()
async def stop_trading(
    ctx: Context,
    close_positions: bool = False,
    reason: str = "manual",
    grace_period: int = 0
) -> Dict:
    """
    Stop all trading activities
    
    Args:
        close_positions: Close all open positions immediately
        reason: Reason for stopping (manual|scheduled|emergency)
        grace_period: Seconds to wait before stopping (0-300)
    
    Returns:
        {
            "success": true,
            "message": "Trading stopped",
            "positions_closed": 2,
            "final_pnl": 234.56
        }
    
    Raises:
        McpError: If stop fails
    """
    # Call Workflow service to stop trading
    try:
        async with state.http_session.post(
            f"{WORKFLOW_URL}/api/v1/cycle/stop",
            json={
                "close_positions": close_positions,
                "reason": reason,
                "grace_period": grace_period
            }
        ) as resp:
            if resp.status != 200:
                error_data = await resp.json()
                raise McpError(
                    "WORKFLOW_ERROR",
                    error_data.get("detail", "Failed to stop trading")
                )
            
            return await resp.json()
            
    except aiohttp.ClientError as e:
        raise McpError(
            "SERVICE_UNAVAILABLE",
            f"Workflow service unavailable: {str(e)}"
        )
```

#### emergency_stop_trading

```python
@mcp.tool()
async def emergency_stop_trading(
    ctx: Context,
    reason: str
) -> Dict:
    """
    EMERGENCY STOP - Immediately halt all trading and close positions
    
    Args:
        reason: Emergency reason (required)
    
    Returns:
        {
            "success": true,
            "message": "Emergency stop executed",
            "positions_closed": 3,
            "orders_cancelled": 2
        }
    
    Raises:
        McpError: If emergency stop fails
    """
    if not reason or len(reason) < 10:
        raise McpError(
            "INVALID_PARAMETER",
            "Emergency reason required (min 10 characters)"
        )
    
    # Call Workflow service emergency endpoint
    try:
        async with state.http_session.post(
            f"{WORKFLOW_URL}/api/v1/cycle/emergency-stop",
            json={"reason": reason}
        ) as resp:
            if resp.status != 200:
                error_data = await resp.json()
                raise McpError(
                    "WORKFLOW_ERROR",
                    error_data.get("detail", "Emergency stop failed")
                )
            
            return await resp.json()
            
    except aiohttp.ClientError as e:
        raise McpError(
            "SERVICE_UNAVAILABLE",
            f"Workflow service unavailable: {str(e)}"
        )
```

### 3.2 Trade Execution Tools

#### execute_trade

```python
@mcp.tool()
async def execute_trade(
    ctx: Context,
    symbol: str,
    side: str,
    quantity: int,
    entry_price: float,
    stop_price: float,
    target_price: float,
    confidence: float = 0.7
) -> Dict:
    """
    Execute a trade with risk validation
    
    Args:
        symbol: Stock symbol
        side: Trade direction (long|short)
        quantity: Number of shares
        entry_price: Entry price
        stop_price: Stop loss price
        target_price: Take profit price
        confidence: Trade confidence (0.0-1.0)
    
    Returns:
        {
            "success": true,
            "order_id": "ORD-20251022-001",
            "message": "Trade executed",
            "risk_assessment": {...}
        }
    
    Raises:
        McpError: If trade rejected or fails
    """
    # Validate parameters
    if side not in ["long", "short"]:
        raise McpError(
            "INVALID_PARAMETER",
            f"Invalid side: {side}. Must be long|short"
        )
    
    if quantity <= 0:
        raise McpError(
            "INVALID_PARAMETER",
            f"Invalid quantity: {quantity}. Must be positive"
        )
    
    if not 0.0 <= confidence <= 1.0:
        raise McpError(
            "INVALID_PARAMETER",
            f"Invalid confidence: {confidence}. Must be 0.0-1.0"
        )
    
    # Call Workflow service to execute trade
    try:
        async with state.http_session.post(
            f"{WORKFLOW_URL}/api/v1/trade/execute",
            json={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "confidence": confidence
            }
        ) as resp:
            if resp.status == 403:
                # Trade rejected by risk manager
                error_data = await resp.json()
                raise McpError(
                    "TRADE_REJECTED",
                    error_data.get("detail", "Trade rejected by risk manager")
                )
            
            if resp.status != 200:
                error_data = await resp.json()
                raise McpError(
                    "WORKFLOW_ERROR",
                    error_data.get("detail", "Trade execution failed")
                )
            
            return await resp.json()
            
    except aiohttp.ClientError as e:
        raise McpError(
            "SERVICE_UNAVAILABLE",
            f"Workflow service unavailable: {str(e)}"
        )
```

### 3.3 Risk Management Tools

#### update_risk_parameters

```python
@mcp.tool()
async def update_risk_parameters(
    ctx: Context,
    max_position_size: Optional[float] = None,
    max_daily_loss: Optional[float] = None,
    max_portfolio_risk: Optional[float] = None,
    max_position_correlation: Optional[float] = None
) -> Dict:
    """
    Update risk management parameters
    
    Args:
        max_position_size: Maximum position size in USD
        max_daily_loss: Maximum daily loss in USD
        max_portfolio_risk: Maximum portfolio risk (0.0-1.0)
        max_position_correlation: Maximum correlation between positions
    
    Returns:
        {
            "success": true,
            "message": "Risk parameters updated",
            "updated_parameters": {...}
        }
    
    Raises:
        McpError: If update fails
    """
    # Call Workflow service to update risk params
    try:
        async with state.http_session.post(
            f"{WORKFLOW_URL}/api/v1/risk/update-parameters",
            json={
                "max_position_size": max_position_size,
                "max_daily_loss": max_daily_loss,
                "max_portfolio_risk": max_portfolio_risk,
                "max_position_correlation": max_position_correlation
            }
        ) as resp:
            if resp.status != 200:
                error_data = await resp.json()
                raise McpError(
                    "WORKFLOW_ERROR",
                    error_data.get("detail", "Failed to update risk parameters")
                )
            
            return await resp.json()
            
    except aiohttp.ClientError as e:
        raise McpError(
            "SERVICE_UNAVAILABLE",
            f"Workflow service unavailable: {str(e)}"
        )
```

---

## 4. REST API Specifications

### 4.1 Workflow Service API (NEW in v5.0)

**Base URL**: `http://workflow:5006/api/v1`

#### Trading Cycle Endpoints

```yaml
POST /cycle/start
  Summary: Start a new trading cycle
  Request Body:
    {
      "mode": "normal|aggressive|conservative",
      "scan_frequency": 300,
      "max_positions": 5,
      "risk_level": 0.5,
      "start_time": "2025-10-22T09:30:00Z" (optional)
    }
  Response 200:
    {
      "success": true,
      "cycle_id": "20251022-001",
      "message": "Trading cycle started",
      "configuration": {...}
    }
  Response 400:
    {
      "detail": "Invalid parameters"
    }
  Response 409:
    {
      "detail": "Cycle already active"
    }

POST /cycle/stop
  Summary: Stop current trading cycle
  Request Body:
    {
      "close_positions": false,
      "reason": "manual|scheduled|emergency",
      "grace_period": 0
    }
  Response 200:
    {
      "success": true,
      "message": "Trading stopped",
      "positions_closed": 2,
      "final_pnl": 234.56
    }

POST /cycle/emergency-stop
  Summary: Emergency stop all trading
  Request Body:
    {
      "reason": "Emergency description (min 10 chars)"
    }
  Response 200:
    {
      "success": true,
      "message": "Emergency stop executed",
      "positions_closed": 3,
      "orders_cancelled": 2,
      "timestamp": "2025-10-22T14:30:00Z"
    }

GET /cycle/current
  Summary: Get current cycle information
  Response 200:
    {
      "cycle_id": "20251022-001",
      "mode": "normal",
      "status": "active|paused|stopped",
      "configuration": {...},
      "started_at": "2025-10-22T09:30:00Z",
      "runtime": "2h 15m"
    }

GET /cycle/status
  Summary: Get detailed cycle status
  Response 200:
    {
      "running": true,
      "cycle_id": "20251022-001",
      "phase": "active_trading",
      "metrics": {
        "scans_completed": 48,
        "candidates_evaluated": 4800,
        "positions_opened": 12,
        "positions_closed": 9,
        "win_rate": 0.67,
        "current_pnl": 345.67
      }
    }
```

#### Trade Execution Endpoints

```yaml
POST /trade/execute
  Summary: Execute a trade with risk validation
  Request Body:
    {
      "symbol": "AAPL",
      "side": "long|short",
      "quantity": 100,
      "entry_price": 175.50,
      "stop_price": 173.00,
      "target_price": 180.00,
      "confidence": 0.85
    }
  Response 200:
    {
      "success": true,
      "order_id": "ORD-20251022-001",
      "message": "Trade executed",
      "risk_assessment": {
        "approved": true,
        "risk_score": 0.35,
        "position_size": 100,
        "capital_at_risk": 250.00
      }
    }
  Response 403:
    {
      "detail": "Trade rejected by risk manager",
      "reason": "Exceeds max position size"
    }

POST /trade/close
  Summary: Close a position
  Request Body:
    {
      "position_id": "POS-20251022-001",
      "reason": "manual|stop_loss|take_profit|emergency"
    }
  Response 200:
    {
      "success": true,
      "order_id": "ORD-20251022-002",
      "realized_pnl": 234.56,
      "holding_time": "45m"
    }
```

#### Risk Management Endpoints

```yaml
POST /risk/update-parameters
  Summary: Update risk management parameters
  Request Body:
    {
      "max_position_size": 10000.00,
      "max_daily_loss": 1000.00,
      "max_portfolio_risk": 0.02,
      "max_position_correlation": 0.7
    }
  Response 200:
    {
      "success": true,
      "message": "Risk parameters updated",
      "updated_parameters": {...}
    }

GET /risk/status
  Summary: Get current risk status
  Response 200:
    {
      "total_exposure": 25000.00,
      "position_count": 3,
      "var_1day_95": -450.00,
      "limits": {...},
      "violations": []
    }
```

### 4.2 Scanner Service API

```yaml
POST /api/v1/scan/start
  Summary: Start market scanning
  Request Body:
    {
      "cycle_id": "20251022-001",
      "mode": "normal|aggressive|conservative",
      "frequency": 300
    }
  Response 200:
    {
      "scan_id": "SCAN-20251022-001",
      "total_scanned": 100,
      "with_catalysts": 35,
      "selected": 5
    }

GET /api/v1/candidates
  Summary: Get all scanned candidates
  Response 200:
    {
      "candidates": [
        {
          "symbol": "AAPL",
          "score": 0.85,
          "price": 175.50,
          "catalyst": "Earnings beat",
          "patterns": ["bull_flag", "volume_breakout"]
        }
      ]
    }

GET /api/v1/candidates/active
  Summary: Get top 5 active candidates
  Response 200:
    {
      "active_candidates": [...]
    }
```

### 4.3 Risk Manager Service API

```yaml
POST /api/v1/validate-position
  Summary: Validate a trade before execution
  Request Body:
    {
      "symbol": "AAPL",
      "side": "long",
      "quantity": 100,
      "entry_price": 175.50,
      "stop_price": 173.00,
      "target_price": 180.00
    }
  Response 200:
    {
      "approved": true,
      "risk_score": 0.35,
      "position_size": 100,
      "capital_at_risk": 250.00,
      "reason": "Within risk limits"
    }
  Response 403:
    {
      "approved": false,
      "reason": "Exceeds max position size",
      "max_allowed": 50
    }

GET /api/v1/metrics/current
  Summary: Get current risk metrics
  Response 200:
    {
      "total_exposure": 25000.00,
      "position_count": 3,
      "var_1day_95": -450.00,
      "sharpe_ratio": 1.85
    }

GET /api/v1/limits
  Summary: Get risk limits and usage
  Response 200:
    {
      "max_position_size": {...},
      "max_portfolio_risk": {...},
      "max_positions": {...}
    }
```

### 4.4 Other Services

**Pattern Service (Port 5002)**: Pattern detection on candidates  
**Technical Service (Port 5003)**: Technical indicators and signals  
**Trading Service (Port 5005)**: Order execution (called by Workflow)  
**News Service (Port 5008)**: Catalyst detection and sentiment  
**Reporting Service (Port 5009)**: Performance analytics

*API specifications unchanged from v4.1*

---

## 5. Data Flow Specifications

### 5.1 Trading Cycle Start Flow

```
1. Claude → Orchestration.start_trading_cycle()
2. Orchestration → POST Workflow:/api/v1/cycle/start
3. Workflow → Validates parameters
4. Workflow → Creates trading_cycles record in DB
5. Workflow → POST Scanner:/api/v1/scan/start
6. Scanner → Begins scanning market
7. Workflow ← Response from Scanner
8. Orchestration ← Response from Workflow
9. Claude ← Success message with cycle_id
```

### 5.2 Trade Signal Flow

```
1. Scanner → Identifies candidate
2. Scanner → POST Pattern:/api/v1/detect
3. Pattern → Analyzes patterns
4. Scanner → POST Technical:/api/v1/analyze
5. Technical → Calculates indicators
6. Scanner → Stores in scan_results
7. Scanner → POST Workflow:/api/v1/trade/signal
8. Workflow → POST Risk:/api/v1/validate-position
9. Risk → Validates against limits
10. If approved:
    Workflow → POST Trading:/api/v1/orders/execute
    Trading → Executes order
    Trading → Updates positions table
11. Workflow → Returns result
```

### 5.3 Emergency Stop Flow

```
1. Claude → Orchestration.emergency_stop_trading()
2. Orchestration → POST Workflow:/api/v1/cycle/emergency-stop
3. Workflow → Broadcasts STOP to all services
4. Workflow → POST Trading:/api/v1/orders/cancel-all
5. Trading → Cancels all pending orders
6. Workflow → POST Trading:/api/v1/positions/close-all
7. Trading → Closes all open positions
8. Workflow → Updates trading_cycles status=stopped
9. Orchestration ← Response with positions closed
10. Claude ← Emergency stop confirmation
```

---

## 6. Claude Interaction Patterns

### 6.1 Starting a Trading Day

**User**: "Start trading in normal mode"

**Claude's Process**:
1. Check system health: Read resource `system/health`
2. Verify no active cycle: Read resource `trading-cycle/current`
3. Start cycle: Call tool `start_trading_cycle(mode="normal")`
4. Confirm: Report cycle_id and configuration

### 6.2 Monitoring Active Trading

**User**: "How's trading going?"

**Claude's Process**:
1. Read resource `trading-cycle/status` for metrics
2. Read resource `portfolio/positions/open` for positions
3. Read resource `analytics/daily-summary` for P&L
4. Synthesize report with:
   - Current phase
   - Open positions
   - Win rate
   - Current P&L

### 6.3 Emergency Intervention

**User**: "Stop everything immediately, market is crashing"

**Claude's Process**:
1. Call tool `emergency_stop_trading(reason="Market crash - user initiated")`
2. Read resource `portfolio/positions/closed` to confirm
3. Read resource `analytics/daily-summary` for final P&L
4. Report positions closed and final results

### 6.4 Risk Adjustment

**User**: "Reduce position sizes, market is volatile"

**Claude's Process**:
1. Read resource `risk/current` to see current limits
2. Calculate new limits (e.g., reduce by 50%)
3. Call tool `update_risk_parameters(max_position_size=5000)`
4. Confirm new limits active

---

## 7. Error Handling

### 7.1 McpError Types

```python
from mcp import McpError

# Parameter validation errors
McpError("INVALID_PARAMETER", "Detailed message")

# Service communication errors
McpError("SERVICE_UNAVAILABLE", "Service name unavailable")

# Business logic errors
McpError("WORKFLOW_ERROR", "Workflow operation failed")
McpError("TRADE_REJECTED", "Trade rejected by risk manager")

# Resource not found
McpError("NOT_FOUND", "Resource not found")

# Internal errors
McpError("INTERNAL_ERROR", "Unexpected error occurred")
```

### 7.2 Error Response Pattern

```python
try:
    # Validate parameters
    if invalid:
        raise McpError("INVALID_PARAMETER", "Specific reason")
    
    # Call Workflow service
    async with state.http_session.post(url, json=data) as resp:
        if resp.status == 403:
            raise McpError("TRADE_REJECTED", "Risk rejection reason")
        
        if resp.status != 200:
            error_data = await resp.json()
            raise McpError("WORKFLOW_ERROR", error_data.get("detail"))
        
        return await resp.json()
        
except aiohttp.ClientError as e:
    raise McpError("SERVICE_UNAVAILABLE", f"Workflow service unavailable: {e}")

except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise McpError("INTERNAL_ERROR", "Unexpected error occurred")
```

### 7.3 Service Health Monitoring

```python
async def check_workflow_health() -> bool:
    """Check if Workflow service is responding"""
    try:
        async with state.http_session.get(
            f"{WORKFLOW_URL}/health",
            timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            return resp.status == 200
    except:
        return False
```

---

## 8. Performance Requirements

### 8.1 Service Level Objectives

| Operation | Target | Maximum |
|-----------|--------|---------|
| **MCP Resource Read** | < 100ms | < 500ms |
| **MCP Tool Execution** | < 1s | < 5s |
| **Workflow API Call** | < 500ms | < 2s |
| **Trade Execution** | < 2s | < 10s |
| **Emergency Stop** | < 5s | < 15s |

### 8.2 Resource Access Patterns

**High Frequency** (cacheable):
- `trading-cycle/status` - Read every 30s by Claude
- `portfolio/positions/open` - Read every 60s
- `market-scan/candidates/active` - Read every 60s

**Medium Frequency**:
- `system/health` - Read every 5m
- `analytics/daily-summary` - Read every 15m

**Low Frequency**:
- `analytics/weekly-summary` - Read on demand
- `system/config` - Read rarely

### 8.3 Caching Strategy

```python
# In Orchestration service
from functools import lru_cache
import asyncio

# Cache frequently accessed resources
@lru_cache(maxsize=128)
def cache_key(resource_uri: str, timestamp: int) -> str:
    return f"{resource_uri}:{timestamp}"

async def get_cached_resource(uri: str, ttl: int = 30) -> str:
    """Get resource with caching"""
    current_time = int(time.time())
    bucket = current_time // ttl
    key = cache_key(uri, bucket)
    
    # Cache hit
    if key in cache:
        return cache[key]
    
    # Cache miss - fetch and cache
    data = await fetch_resource(uri)
    cache[key] = data
    return data
```

---

## Conclusion

This v5.0 functional specification provides:

- ✅ **9-Service Architecture** with clear separation of concerns
- ✅ **Workflow Service** specification for trade coordination
- ✅ **Updated Orchestration** service (MCP-only interface)
- ✅ **Hierarchical URI structure** for all resources
- ✅ **Complete tool specifications** calling Workflow service
- ✅ **REST API definitions** for all internal services
- ✅ **Error handling patterns** with McpError
- ✅ **Performance requirements** and caching strategy
- ✅ **Working code examples** throughout

**Key Improvement**: The separation of Orchestration (MCP interface) and Workflow (trade coordination) provides:
- **Better scalability**: Orchestration can handle multiple Claude connections
- **Cleaner architecture**: Each service has single responsibility
- **Easier testing**: Business logic isolated in Workflow
- **Better reliability**: MCP protocol issues don't affect trading logic

---

**DevGenius Hat Status**: Functionally specified for 9-service architecture 🎩
