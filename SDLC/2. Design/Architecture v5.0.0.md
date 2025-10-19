# Catalyst Trading System - MCP Architecture v5.0

**Name of Application**: Catalyst Trading System
**Name of file**: architecture-mcp-v50.md
**Version**: 5.0.0
**Last Updated**: 2025-10-16
**Purpose**: Updated MCP architecture separating Claude interface and trade workflow coordination.

---

## Executive Summary

The Catalyst Trading System v5.0 implements an enhanced MCP architecture with:

1.  **Separation of Concerns**: Dedicated services for Claude interaction and trade workflow coordination.
2.  **9-Service Architecture**: Added a new dedicated workflow service.
3.  **Risk-First Design**: Mandatory risk validation for all trades.
4.  **Hierarchical URI Structure**: Organized resource paths for scalability.
5.  **FastMCP Best Practices**: Context parameters and initialization hooks.
6.  **Safety Protocols**: Multi-layer risk controls and monitoring.

---

## REVISION HISTORY

-   v5.0.0 (2025-10-16) - Separated Workflow from Orchestration
    -   Added a new `Workflow` service to handle all trade coordination logic.
    -   Updated `Orchestration` service to focus solely on the MCP interface with Claude.
    -   Updated service matrix to 9 services.
    -   Refactored data flows and responsibilities to reflect the new architecture.

-   v4.2.0 (2025-09-20) - Added Risk Management Service
    -   Integrated risk-manager service (port 5004).
    -   Updated service matrix to 8 services.
    -   Added risk management data flows.
    -   Enhanced trading safety protocols.
    -   Updated resource hierarchies.

---

## Enhanced Service Matrix

### Service Architecture (9 Services)

| Service | Protocol | Port | Responsibilities |
| :--- | :--- | :--- | :--- |
| Orchestration | MCP | 5000 | Claude interface |
| Workflow | REST | 5006 | Trade workflow coordination |
| Scanner | REST | 5001 | Market scanning (200 securities → 5 final) |
| Pattern | REST | 5002 | Pattern detection on candidates |
| Technical | REST | 5003 | Technical indicators and signals |
| **Risk Manager** | **REST** | **5004** | **Position sizing, risk validation, safety controls** |
| Trading | REST | 5005 | Order execution (risk-approved trades only) |
| News | REST | 5008 | Catalyst detection and sentiment |
| Reporting | REST | 5009 | Performance analytics with risk metrics |

### Enhanced System Architecture

┌─────────────────────────────────────────────────────────────────┐
│                        Claude Desktop                           │
│                    (MCP Client via stdio)                       │
└──────────────────────────┬──────────────────────────────────────┘
                          │
                          │ MCP Protocol (stdio/websocket)
                          ↓
┌───────────────────────────────────────────────────────────────┐
│           Orchestration Service (Port 5000)                   │
│                    FastMCP Server                             │
│                                                               │
│  Resources (Hierarchical):      Tools (Actions):              │
│  ├── trading-cycle/             • start_trading_cycle         │
│  │   ├── current                • stop_trading                │
│  │   └── status                 • update_risk_parameters      │
│  ├── market-scan/               • emergency_stop              │
│  │   └── candidates/                                          │
│  │       ├── active                                           │
│  │       └── rejected                                         │
│  ├── risk-management/                                         │
│  │   ├── parameters                                           │
│  │   ├── metrics                                              │
│  │   └── exposure                                             │
│  └── analytics/                                               │
│      ├── daily-summary                                        │
│      └── performance                                          │
└───────────────────────────────────────────────────────────────┘
                          │
                          │ REST API calls to internal services
                          ↓
┌────────────────────────────────────────────────────────────────┐
│                    Internal REST Services                      │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Scanner   │  │   Pattern   │  │ Technical   │             │
│  │ Port 5001   │  │ Port 5002   │  │ Port 5003   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │Risk Manager │  │   Trading   │  │    News     │             │
│  │ Port 5004   │  │ Port 5005   │  │ Port 5008   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Reporting   │  │  **Workflow**  │             │             │
│  │ Port 5009   │  │ **Port 5006**  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└────────────────────────────────────────────────────────────────┘
                          │
                          │ Direct connections
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                   DigitalOcean Infrastructure                   │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐             │
│  │  Managed PostgreSQL │    │    Redis Cache      │             │
│  │     (Port 25060)    │    │    (Port 6379)      │             │
│  │  - Trading data     │    │  - Session cache    │             │
│  │  - Risk metrics     │    │  - Market data      │             │
│  │  - Position history │    │  - Pattern cache    │             │
│  └─────────────────────┘    └─────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘

---

## Risk-Integrated Data Flow

### Enhanced Trading Flow with Risk Management

```mermaid
sequenceDiagram
    participant C as Claude Desktop
    participant O as Orchestration (MCP)
    participant W as Workflow
    participant S as Scanner (REST)
    participant P as Pattern (REST)
    participant T as Technical (REST)
    participant R as Risk Manager (REST)
    participant TR as Trading (REST)
    participant DB as Database

    Note over C,DB: Risk-First Trading Flow

    C->>O: start_trading_cycle
    O->>W: POST /api/v1/start-cycle
    W->>S: GET /api/v1/scan
    S->>W: candidate symbols

    W->>P: POST /api/v1/analyze (candidates)
    P->>W: pattern confirmations

    W->>T: POST /api/v1/signals (patterns)
    T->>W: technical signals

    Note over W,R: MANDATORY RISK VALIDATION
    W->>R: POST /api/v1/validate (signal)
    R->>R: Check position size, daily limits, exposure
    R->>W: approved/rejected + sizing

    alt Signal Approved
        W->>TR: POST /api/v1/execute (risk-approved signal)
        TR->>DB: Store trade
        TR->>W: execution confirmation
        W->>O: POST /api/v1/notification (trade executed)
        O->>C: Trade executed successfully
    else Signal Rejected
        W->>O: POST /api/v1/notification (trade rejected)
        O->>C: Trade rejected: [risk reason]
    end
Risk Monitoring Flow
Code snippet

sequenceDiagram
    participant R as Risk Manager
    participant TR as Trading
    participant W as Workflow
    participant O as Orchestration
    participant C as Claude Desktop

    Note over R,C: Continuous Risk Monitoring

    loop Every 30 seconds
        R->>TR: GET /api/v1/positions
        TR->>R: current positions + P&L
        R->>R: Calculate exposure, daily loss

        alt Risk Threshold Exceeded
            R->>W: POST /api/v1/alert (risk breach)
            W->>O: POST /api/v1/notification (risk alert)
            O->>C: 🚨 Risk Alert: Daily loss limit approaching
        end

        alt Emergency Stop Required
            R->>W: POST /api/v1/emergency-stop
            W->>TR: POST /api/v1/emergency-stop
            W->>O: POST /api/v1/notification (emergency stop)
            O->>C: 🛑 Emergency stop triggered
        end
    end
Enhanced MCP Resources
The Orchestration Service now serves as the primary Claude interface. The trading workflow logic and tools are now handled by the new Workflow service.

Risk Management Resources
Python

# Orchestration Service MCP Resources

@mcp.resource("risk-management/parameters")
async def get_risk_parameters(ctx: Context) -> Dict:
    """Get current risk management parameters"""
    async with state.http_session.get(f"{RISK_MANAGER_URL}/api/v1/parameters") as resp:
        return await resp.json()

@mcp.resource("risk-management/metrics")
async def get_risk_metrics(ctx: Context) -> Dict:
    """Get real-time risk metrics"""
    async with state.http_session.get(f"{RISK_MANAGER_URL}/api/v1/metrics") as resp:
        metrics = await resp.json()
        return {
            "daily_pnl": metrics.get("daily_pnl", 0),
            "daily_loss_limit": metrics.get("daily_loss_limit", 2000),
            "remaining_risk_budget": metrics.get("remaining_risk_budget", 0),
            "open_exposure": metrics.get("open_exposure", 0),
            "max_exposure_limit": metrics.get("max_exposure_limit", 10000),
            "position_count": metrics.get("position_count", 0),
            "risk_score": metrics.get("risk_score", 0),  # 0-100
            "timestamp": datetime.now().isoformat()
        }

@mcp.resource("risk-management/exposure")
async def get_exposure_breakdown(ctx: Context) -> Dict:
    """Get detailed exposure breakdown"""
    async with state.http_session.get(f"{RISK_MANAGER_URL}/api/v1/exposure") as resp:
        return await resp.json()
Enhanced Trading Tools (Now handled by the Workflow Service)
These tools are no longer implemented in the Orchestration service. Instead, they are called by the Orchestration service on the new Workflow service to initiate trading actions.

Python

@mcp.tool()
async def start_trading_cycle(
    ctx: Context,
    mode: str = "normal",
    scan_frequency: int = 300,
    max_positions: int = 5,
    risk_level: float = 0.5,
    start_time: Optional[str] = None
) -> Dict:
    """Start a new trading cycle with specified parameters"""
    # This tool now sends a request to the Workflow service
    async with state.http_session.post(
        f"{WORKFLOW_URL}/api/v1/start-cycle",
        json={...}
    ) as resp:
        return await resp.json()

@mcp.tool()
async def stop_trading(
    ctx: Context,
    close_positions: bool = False,
    reason: str = "manual",
    grace_period: int = 0
) -> Dict:
    """Stop all trading activities"""
    # This tool now sends a request to the Workflow service
    async with state.http_session.post(
        f"{WORKFLOW_URL}/api/v1/stop-trading",
        json={...}
    ) as resp:
        return await resp.json()
        
@mcp.tool()
async def emergency_stop_trading(ctx: Context, reason: str) -> Dict:
    """Emergency stop all trading activities"""
    # This tool now sends a request to the Workflow service
    async with state.http_session.post(
        f"{WORKFLOW_URL}/api/v1/emergency-stop",
        json={...}
    ) as resp:
        return await resp.json()
Workflow Service Specification
REST API Endpoints
Python

# Workflow Service (Port 5006)

# POST /api/v1/start-cycle
# Initiates a new trading cycle

# POST /api/v1/stop-trading
# Halts the current trading cycle

# POST /api/v1/emergency-stop
# Triggers emergency stop procedures

# POST /api/v1/trade-signal
# Receives a trade signal and coordinates execution

# GET /api/v1/health
# Standard health check endpoint
Conclusion
The enhanced Catalyst Trading System v5.0 provides:

✅ 9-Service Architecture with dedicated workflow service.

✅ Clear Separation of Concerns between Claude interface and trade coordination.

✅ Risk-First Trading with mandatory validation.

✅ Multi-Layer Safety controls and monitoring.

✅ Real-Time Risk Metrics and exposure tracking.

✅ Emergency Protocols for system protection.

✅ Comprehensive Risk Resources via MCP.

The system now has a more robust and scalable architecture, with each service having a clearly defined role. This improves maintainability and allows for independent scaling of the Claude interface and the core trading workflow.