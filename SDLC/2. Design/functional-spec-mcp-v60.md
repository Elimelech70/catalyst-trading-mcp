# Catalyst Trading System - Functional Specification v6.0

**Name of Application**: Catalyst Trading System  
**Name of file**: functional-spec-mcp-v60.md  
**Version**: 6.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: Production trading system specification - 9 services, US markets, Stage 1
**Scope**: PRODUCTION TRADING ONLY

---

## REVISION HISTORY

**v6.0.0 (2025-10-25)** - PRODUCTION SYSTEM CLEAN SEPARATION
- ✅ **MAJOR CHANGE**: Research features removed entirely
- ✅ Production focus: 9 services, US markets only, Stage 1 trading
- ✅ Clean specification for immediate implementation
- ✅ Single instance deployment (DigitalOcean droplet)
- ✅ No ML training, no multi-agent AI, no Chinese/Japanese markets
- ⚠️ **BREAKING**: Research moved to separate spec (future: research-functional-spec-v10.md)

**v5.0.0 (2025-10-22)** - 9-Service Architecture (superseded)
- Mixed Production + Research features (caused implementation confusion)

**v4.1.0 (2025-08-31)** - 7-Service Architecture (superseded)
- Combined Orchestration + Workflow

---

## ⚠️ CRITICAL: SCOPE DEFINITION

### **IN SCOPE (Production System)**
✅ 9 microservices for day trading  
✅ US markets (NYSE, NASDAQ)  
✅ Stage 1: Rule-based trading with data collection  
✅ Claude Desktop MCP integration (trading assistance)  
✅ Single DigitalOcean droplet deployment  
✅ PostgreSQL normalized schema (production data)  
✅ Ross Cameron momentum trading methodology  
✅ Alpaca Markets execution (live or paper)  

### **OUT OF SCOPE (Future Research System)**
❌ ML training services (see research-functional-spec-v10.md when created)  
❌ Pattern discovery service (future)  
❌ Backtest engine (future)  
❌ Multi-agent AI coordinator (Claude + GPT-4 + Perplexity + Gemini)  
❌ Chinese markets (A-shares, H-shares)  
❌ Japanese markets (TSE, Nikkei)  
❌ Stage 2-5 AI features (context-aware, recommendations, autonomous)  
❌ Paper trading sandbox (Research instance handles this)  

**REASON**: Clean separation ensures fast Production completion without scope creep.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Service Matrix](#2-service-matrix)
3. [MCP Resource Hierarchy](#3-mcp-resource-hierarchy)
4. [MCP Tools Specification](#4-mcp-tools-specification)
5. [REST API Specifications](#5-rest-api-specifications)
6. [Data Flow Specifications](#6-data-flow-specifications)
7. [Claude Interaction Patterns](#7-claude-interaction-patterns)
8. [Error Handling](#8-error-handling)
9. [Performance Requirements](#9-performance-requirements)
10. [Security Requirements](#10-security-requirements)

---

## 1. System Overview

### 1.1 Architecture Philosophy

**Production-First Design**:
```yaml
Priority: Complete working trading system FAST
Approach: Single instance, proven technologies, clear scope
Goal: Profitable Stage 1 trading within 8 weeks
Future: Research instance built later when Production succeeds
```

**Hybrid Architecture**:
- **MCP Protocol**: Single Orchestration service (Claude Desktop interface)
- **REST APIs**: 8 internal services (business logic)
- **PostgreSQL**: Normalized database (3NF, production data)
- **Redis**: Pub/sub + caching (single container)
- **Docker Compose**: Service orchestration (single droplet)

### 1.2 Deployment Model

```
┌─────────────────────────────────────────────────────────┐
│           Claude Desktop (Windows/Mac)                  │
│                    MCP Client                           │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS (MCP Protocol)
                        │ Port 443 (Nginx SSL)
            ┌───────────▼──────────────┐
            │ DigitalOcean Droplet     │
            │ sfo3 region              │
            │ 4vCPU, 8GB RAM, 160GB    │
            │ Ubuntu 22.04 LTS         │
            │                          │
            │  ┌────────────────────┐ │
            │  │ Nginx (443)        │ │
            │  │ SSL/TLS Termination│ │
            │  └──────────┬─────────┘ │
            │             │            │
            │  ┌──────────▼─────────┐ │
            │  │ Docker Network     │ │
            │  │ 172.18.0.0/16      │ │
            │  │                    │ │
            │  │ [9 Services]       │ │
            │  │ [Redis]            │ │
            │  └────────────────────┘ │
            └───────────┬──────────────┘
                        │ Private Network
                        │ (Connection String)
            ┌───────────▼──────────────┐
            │ DigitalOcean Cloud       │
            │ PostgreSQL 15 (Managed)  │
            │ 1vCPU, 1GB RAM, 10GB     │
            └──────────────────────────┘
```

**Cost**: $63/month (Production only)

---

## 2. Service Matrix

### 2.1 Production Services (9 Total)

| # | Service | Protocol | Port | Purpose | Priority |
|---|---------|----------|------|---------|----------|
| 1 | **Orchestration** | MCP | 5000 | Claude Desktop interface | Critical |
| 2 | **Scanner** | REST | 5001 | Market scanning (100→35→20→10→5) | Critical |
| 3 | **Pattern** | REST | 5002 | Technical pattern detection | High |
| 4 | **Technical** | REST | 5003 | Technical indicators | High |
| 5 | **Risk Manager** | REST | 5004 | Risk validation & limits | Critical |
| 6 | **Trading** | REST | 5005 | Order execution (Alpaca) | Critical |
| 7 | **Workflow** | REST | 5006 | Trade coordination | Critical |
| 8 | **News** | REST | 5008 | News catalyst intelligence | Critical |
| 9 | **Reporting** | REST | 5009 | Performance analytics | High |

**Service Dependencies**:
```
News (5008) → Scanner (5001) → Pattern (5002) → Technical (5003)
                    ↓                               ↓
              Risk Manager (5004) ← Trading (5005)
                    ↓
              Workflow (5006) → Reporting (5009)
                    ↑
           Orchestration (5000) ← Claude Desktop
```

### 2.2 Service Responsibilities

#### **1. Orchestration Service (Port 5000)**
```yaml
Protocol: MCP (Model Context Protocol)
Purpose: Claude Desktop interface
Technology: FastMCP framework

Responsibilities:
  - Expose MCP resources (hierarchical URIs)
  - Expose MCP tools (trading actions)
  - Route requests to Workflow service
  - Return structured responses to Claude
  - Handle MCP protocol lifecycle
  
Does NOT:
  - ❌ Execute business logic (delegates to Workflow)
  - ❌ Access database directly (calls REST services)
  - ❌ Make trading decisions (presents options to Claude)

Resources Exposed:
  - trading-cycle/* (current workflow state)
  - market-scan/* (candidate stocks)
  - positions/* (open positions)
  - performance/* (trading metrics)
  - alerts/* (risk alerts)

Tools Exposed:
  - start_trading_session()
  - get_scan_results()
  - execute_trade()
  - close_position()
  - get_performance_report()
```

#### **2. Scanner Service (Port 5001)**
```yaml
Protocol: REST
Purpose: Multi-stage market filtering (100→35→20→10→5)

Responsibilities:
  - Universe selection (50-100 stocks with news/volume)
  - News catalyst filtering (35 stocks)
  - Technical filtering (20 stocks)
  - Pattern confirmation (10 stocks)
  - Final ranking (5 stocks delivered to Workflow)
  
Data Sources:
  - Alpaca Markets API (real-time quotes)
  - News Service (catalyst intelligence)
  - Technical Service (indicators)
  - Pattern Service (chart patterns)

Outputs:
  - scan_results table (database persistence)
  - Redis pub/sub (real-time updates)
  - REST API (GET /api/v1/scan/{cycle_id})
```

#### **3. Pattern Service (Port 5002)**
```yaml
Protocol: REST
Purpose: Technical pattern detection (bull flags, cup & handle, etc.)

Responsibilities:
  - Chart pattern recognition
  - Support/resistance identification
  - Breakout detection
  - Volume confirmation
  
Patterns Detected:
  - Bull flag (momentum continuation)
  - Cup and handle (accumulation)
  - Ascending triangle (bullish breakout)
  - ABCD pattern (measured move)
  - Opening range breakout (ORB)

Inputs:
  - OHLCV data (from Scanner/Alpaca)
  - Technical indicators (from Technical Service)

Outputs:
  - Pattern confidence scores (0-1)
  - Entry/exit levels
  - Pattern metadata (for ML training)
```

#### **4. Technical Service (Port 5003)**
```yaml
Protocol: REST
Purpose: Technical indicator calculation

Responsibilities:
  - Moving averages (SMA, EMA)
  - Momentum indicators (RSI, MACD)
  - Volatility (ATR, Bollinger Bands)
  - Volume analysis (OBV, volume ratio)
  - Support/resistance levels

Indicators Calculated:
  - SMA 20, 50, 200
  - EMA 9, 21
  - RSI 14
  - MACD (12, 26, 9)
  - ATR 14
  - Bollinger Bands (20, 2)
  - Volume ratio (vs 20-day average)

Storage:
  - technical_indicators table (database)
  - Redis cache (5-minute TTL)
```

#### **5. Risk Manager Service (Port 5004)**
```yaml
Protocol: REST
Purpose: Risk validation and enforcement

Responsibilities:
  - Pre-trade risk checks
  - Position size calculation (Kelly criterion)
  - Daily loss limit monitoring
  - Correlation checks (avoid overexposure)
  - Emergency stop execution

Risk Rules (Stage 1):
  - Max daily loss: $2,000 (configurable)
  - Max position size: 20% of capital
  - Max positions: 5 concurrent
  - Max correlation: 0.7 between positions
  - Stop loss: 2x ATR or technical support

Configuration:
  - config/risk_parameters.yaml
  - Hot-reload (no restart required)
  - Pydantic validation
```

#### **6. Trading Service (Port 5005)**
```yaml
Protocol: REST
Purpose: Order execution via Alpaca Markets

Responsibilities:
  - Order submission (market, limit, stop)
  - Order status tracking
  - Fill confirmation
  - Position management
  - Alpaca API integration

Alpaca Integration:
  - Live trading: api.alpaca.markets
  - Paper trading: paper-api.alpaca.markets
  - WebSocket: Real-time order updates
  - REST API: Order submission

Order Types:
  - Market orders (immediate execution)
  - Limit orders (price protection)
  - Stop loss orders (risk management)
  - Bracket orders (entry + stop + target)

Database:
  - orders table (all order history)
  - positions table (current positions)
```

#### **7. Workflow Service (Port 5006)**
```yaml
Protocol: REST
Purpose: Trade workflow coordination

Responsibilities:
  - Daily trading cycle orchestration
  - Service coordination (Scanner → Pattern → Technical → Trading)
  - State management (cycle_state)
  - Decision logging (for ML training)
  - Workflow triggers (cron, manual, event-driven)

Workflow Phases:
  1. Pre-market scan (08:00-09:25 ET)
  2. Opening range (09:30-09:45 ET)
  3. Morning session (09:45-11:30 ET)
  4. Midday (11:30-14:00 ET)
  5. Power hour (14:00-15:30 ET)
  6. Close & reconcile (15:30-16:00 ET)

Database:
  - trading_cycles table (workflow state)
  - decision_logs table (ML training data)
```

#### **8. News Service (Port 5008)**
```yaml
Protocol: REST
Purpose: News catalyst detection and sentiment analysis

Responsibilities:
  - News aggregation (Benzinga, NewsAPI, Alpaca News)
  - Sentiment analysis (positive/negative/neutral)
  - Catalyst classification (earnings, FDA, merger, etc.)
  - Source reliability scoring
  - Real-time news monitoring

News Sources:
  - Benzinga News API (primary)
  - NewsAPI (backup)
  - Alpaca News (real-time)
  - SEC EDGAR (filings)

Sentiment Analysis:
  - FinBERT transformer model
  - Keyword-based classification
  - Source reliability weighting

Database:
  - news_sentiment table (all news events)
  - catalyst_events table (trading catalysts)
```

#### **9. Reporting Service (Port 5009)**
```yaml
Protocol: REST
Purpose: Performance analytics and reporting

Responsibilities:
  - Daily P&L calculation
  - Win rate tracking
  - Sharpe ratio calculation
  - Drawdown monitoring
  - Trade journal generation

Reports Generated:
  - Daily summary (end-of-day email)
  - Weekly performance (Sunday email)
  - Monthly review (1st of month)
  - Trade journal (on-demand)

Metrics Tracked:
  - Win rate (target: >60%)
  - Average R:R (target: >1.5)
  - Sharpe ratio (target: >1.0)
  - Max drawdown (target: <10%)
  - Profit factor (target: >1.5)

Database:
  - performance_metrics table
  - trade_journal table
```

---

## 3. MCP Resource Hierarchy

### 3.1 Resource URI Structure

**Convention**: Hierarchical URIs following FastMCP best practices

```
/resource-type/resource-id/sub-resource
```

### 3.2 Trading Cycle Resources

#### **Resource: trading-cycle/current**
```yaml
URI: trading-cycle/current
Type: application/json
Description: Current trading cycle state

Response:
  {
    "cycle_id": "uuid",
    "date": "2025-10-25",
    "market_status": "open|closed|pre-market|after-hours",
    "cycle_state": "scanning|evaluating|trading|monitoring|closed",
    "phase": "pre-market|opening-range|morning|midday|power-hour|closed",
    "candidates_count": 5,
    "positions_count": 3,
    "daily_pnl": -450.25,
    "daily_pnl_pct": -0.45,
    "trades_executed": 8,
    "win_rate": 0.625
  }
```

#### **Resource: trading-cycle/{cycle_id}/timeline**
```yaml
URI: trading-cycle/{cycle_id}/timeline
Type: application/json
Description: Chronological events for a trading cycle

Response:
  [
    {
      "timestamp": "2025-10-25T08:00:00Z",
      "event_type": "scan_started",
      "description": "Pre-market scan initiated",
      "metadata": {"universe_size": 100}
    },
    {
      "timestamp": "2025-10-25T08:15:00Z",
      "event_type": "scan_completed",
      "description": "5 candidates identified",
      "metadata": {"candidates": ["TSLA", "NVDA", ...]}
    }
  ]
```

### 3.3 Market Scan Resources

#### **Resource: market-scan/latest**
```yaml
URI: market-scan/latest
Type: application/json
Description: Latest scan results (top 5 candidates)

Response:
  {
    "cycle_id": "uuid",
    "scan_timestamp": "2025-10-25T08:15:00Z",
    "candidates": [
      {
        "symbol": "TSLA",
        "rank": 1,
        "catalyst_score": 0.92,
        "technical_score": 0.88,
        "pattern_score": 0.85,
        "final_score": 0.883,
        "price": 242.50,
        "volume": 15234567,
        "news_catalyst": "Earnings beat expectations",
        "pattern": "bull_flag",
        "support": 238.00,
        "resistance": 248.00
      },
      // ... 4 more candidates
    ]
  }
```

#### **Resource: market-scan/candidates/{symbol}**
```yaml
URI: market-scan/candidates/{symbol}
Type: application/json
Description: Detailed analysis for a specific candidate

Response:
  {
    "symbol": "TSLA",
    "scan_timestamp": "2025-10-25T08:15:00Z",
    "catalyst": {
      "headline": "Tesla Q3 earnings beat expectations",
      "sentiment": 0.85,
      "catalyst_type": "earnings",
      "catalyst_strength": 0.92
    },
    "technical": {
      "price": 242.50,
      "sma_20": 235.40,
      "sma_50": 228.10,
      "rsi_14": 68.5,
      "atr_14": 4.25,
      "support": 238.00,
      "resistance": 248.00
    },
    "pattern": {
      "type": "bull_flag",
      "confidence": 0.85,
      "entry": 243.00,
      "target": 252.00,
      "stop": 238.00
    },
    "risk_assessment": {
      "position_size": 50,
      "risk_amount": 250.00,
      "reward_potential": 450.00,
      "risk_reward_ratio": 1.8
    }
  }
```

### 3.4 Position Resources

#### **Resource: positions/current**
```yaml
URI: positions/current
Type: application/json
Description: All currently open positions

Response:
  [
    {
      "position_id": "uuid",
      "symbol": "TSLA",
      "side": "long",
      "quantity": 50,
      "entry_price": 243.00,
      "current_price": 241.50,
      "unrealized_pnl": -75.00,
      "unrealized_pnl_pct": -0.62,
      "entry_time": "2025-10-25T09:45:00Z",
      "time_in_position": "2h 30m",
      "stop_loss": 238.00,
      "take_profit": 252.00,
      "risk_amount": 250.00,
      "pattern": "bull_flag"
    }
  ]
```

#### **Resource: positions/{position_id}/status**
```yaml
URI: positions/{position_id}/status
Type: application/json
Description: Real-time status of a specific position

Response:
  {
    "position_id": "uuid",
    "symbol": "TSLA",
    "status": "open|closed|stopped_out",
    "current_price": 241.50,
    "unrealized_pnl": -75.00,
    "distance_to_stop": 3.50,
    "distance_to_target": 10.50,
    "technical_update": {
      "at_support": false,
      "support_level": 238.00,
      "pattern_intact": true
    },
    "recommendation": "Hold - Pattern intact, near support"
  }
```

### 3.5 Performance Resources

#### **Resource: performance/daily**
```yaml
URI: performance/daily
Type: application/json
Description: Today's performance metrics

Response:
  {
    "date": "2025-10-25",
    "daily_pnl": -450.25,
    "daily_pnl_pct": -0.45,
    "trades_executed": 8,
    "trades_won": 5,
    "trades_lost": 3,
    "win_rate": 0.625,
    "avg_win": 225.50,
    "avg_loss": -183.75,
    "largest_win": 420.00,
    "largest_loss": -275.00,
    "profit_factor": 1.23
  }
```

#### **Resource: performance/weekly**
```yaml
URI: performance/weekly
Type: application/json
Description: This week's performance (Monday-Friday)

Response:
  {
    "week_start": "2025-10-21",
    "week_end": "2025-10-25",
    "weekly_pnl": 1250.75,
    "weekly_pnl_pct": 1.25,
    "trades_executed": 42,
    "win_rate": 0.643,
    "sharpe_ratio": 1.15,
    "max_drawdown": -380.00,
    "max_drawdown_pct": -0.38,
    "best_day": {
      "date": "2025-10-23",
      "pnl": 875.50
    },
    "worst_day": {
      "date": "2025-10-24",
      "pnl": -320.25
    }
  }
```

### 3.6 Alert Resources

#### **Resource: alerts/active**
```yaml
URI: alerts/active
Type: application/json
Description: Current active alerts requiring attention

Response:
  [
    {
      "alert_id": "uuid",
      "severity": "critical|warning|info",
      "alert_type": "daily_loss_limit|position_risk|service_health",
      "message": "Daily loss limit approaching: -$1,850 (92.5% of limit)",
      "timestamp": "2025-10-25T14:30:00Z",
      "action_required": true,
      "suggested_action": "Close losing positions or adjust risk limit"
    }
  ]
```

---

## 4. MCP Tools Specification

### 4.1 Tool Naming Convention

```
{action}_{resource}
```

Examples:
- start_trading_session
- get_scan_results
- execute_trade
- close_position

### 4.2 Session Management Tools

#### **Tool: start_trading_session**
```python
@mcp.tool()
async def start_trading_session(
    ctx: Context,
    session_mode: Literal["autonomous", "supervised"] = "supervised"
) -> Dict:
    """
    Start a new trading session for today
    
    Args:
        session_mode: Trading mode
            - "autonomous": System acts immediately on risk limits
            - "supervised": System warns before taking action (5-min window)
    
    Returns:
        {
            "cycle_id": "uuid",
            "status": "started",
            "session_mode": "supervised",
            "message": "Trading session started in supervised mode"
        }
    """
    response = await http_client.post(
        "http://workflow:5006/api/v1/workflow/start",
        json={"session_mode": session_mode}
    )
    return response.json()
```

#### **Tool: stop_trading_session**
```python
@mcp.tool()
async def stop_trading_session(
    ctx: Context,
    reason: str = "Manual stop"
) -> Dict:
    """
    Stop current trading session and close all positions
    
    Args:
        reason: Reason for stopping (logged for analysis)
    
    Returns:
        {
            "status": "stopped",
            "positions_closed": 3,
            "final_pnl": -450.25,
            "message": "Trading session stopped"
        }
    """
    response = await http_client.post(
        "http://workflow:5006/api/v1/workflow/stop",
        json={"reason": reason}
    )
    return response.json()
```

### 4.3 Market Analysis Tools

#### **Tool: get_scan_results**
```python
@mcp.tool()
async def get_scan_results(
    ctx: Context,
    top_n: int = 5
) -> Dict:
    """
    Get latest market scan results (top candidates)
    
    Args:
        top_n: Number of top candidates to return (1-20)
    
    Returns:
        {
            "cycle_id": "uuid",
            "scan_timestamp": "2025-10-25T08:15:00Z",
            "candidates_count": 5,
            "candidates": [...]
        }
    """
    response = await http_client.get(
        f"http://scanner:5001/api/v1/scan/latest?top_n={top_n}"
    )
    return response.json()
```

#### **Tool: get_candidate_analysis**
```python
@mcp.tool()
async def get_candidate_analysis(
    ctx: Context,
    symbol: str
) -> Dict:
    """
    Get detailed analysis for a specific candidate
    
    Args:
        symbol: Stock ticker symbol (e.g., "TSLA")
    
    Returns:
        {
            "symbol": "TSLA",
            "catalyst": {...},
            "technical": {...},
            "pattern": {...},
            "risk_assessment": {...}
        }
    """
    response = await http_client.get(
        f"http://scanner:5001/api/v1/scan/candidates/{symbol}"
    )
    return response.json()
```

### 4.4 Trading Execution Tools

#### **Tool: execute_trade**
```python
@mcp.tool()
async def execute_trade(
    ctx: Context,
    symbol: str,
    side: Literal["buy", "sell"],
    quantity: int,
    order_type: Literal["market", "limit"] = "market",
    limit_price: Optional[float] = None
) -> Dict:
    """
    Execute a trade (requires risk validation)
    
    Args:
        symbol: Stock ticker
        side: "buy" or "sell"
        quantity: Number of shares
        order_type: "market" or "limit"
        limit_price: Price for limit orders (required if order_type="limit")
    
    Returns:
        {
            "order_id": "uuid",
            "status": "submitted|rejected",
            "symbol": "TSLA",
            "quantity": 50,
            "message": "Order submitted successfully"
        }
    
    Raises:
        McpError: If risk validation fails
    """
    # Risk validation first
    risk_check = await http_client.post(
        "http://risk-manager:5004/api/v1/risk/validate",
        json={
            "symbol": symbol,
            "side": side,
            "quantity": quantity
        }
    )
    
    if not risk_check.json()["approved"]:
        raise McpError(
            ErrorCode.INVALID_REQUEST,
            f"Risk validation failed: {risk_check.json()['reason']}"
        )
    
    # Execute trade
    response = await http_client.post(
        "http://trading:5005/api/v1/orders",
        json={
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "limit_price": limit_price
        }
    )
    return response.json()
```

#### **Tool: close_position**
```python
@mcp.tool()
async def close_position(
    ctx: Context,
    symbol: str,
    reason: str = "Manual close"
) -> Dict:
    """
    Close an open position immediately (market order)
    
    Args:
        symbol: Stock ticker
        reason: Reason for closing (logged for analysis)
    
    Returns:
        {
            "position_id": "uuid",
            "symbol": "TSLA",
            "quantity_closed": 50,
            "realized_pnl": -75.00,
            "message": "Position closed"
        }
    """
    response = await http_client.post(
        f"http://trading:5005/api/v1/positions/{symbol}/close",
        json={"reason": reason}
    )
    return response.json()
```

### 4.5 Risk Management Tools

#### **Tool: update_risk_parameter**
```python
@mcp.tool()
async def update_risk_parameter(
    ctx: Context,
    parameter_path: str,
    new_value: float
) -> Dict:
    """
    Update a risk configuration parameter
    
    Args:
        parameter_path: Dot notation (e.g., 'daily_limits.max_daily_loss_usd')
        new_value: New parameter value
    
    Returns:
        {
            "parameter": "daily_limits.max_daily_loss_usd",
            "old_value": 2000.0,
            "new_value": 3000.0,
            "message": "Risk parameter updated"
        }
    
    Examples:
        - "daily_limits.max_daily_loss_usd": 3000.0
        - "position_limits.max_positions": 7
        - "risk_reward_ratio": 2.0
    """
    response = await http_client.post(
        "http://risk-manager:5004/api/v1/config/update",
        json={
            "parameter_path": parameter_path,
            "new_value": new_value
        }
    )
    return response.json()
```

#### **Tool: get_risk_status**
```python
@mcp.tool()
async def get_risk_status(ctx: Context) -> Dict:
    """
    Get current risk status (daily P&L, limits, exposure)
    
    Returns:
        {
            "daily_pnl": -1850.00,
            "daily_pnl_pct": -1.85,
            "max_daily_loss": 2000.0,
            "loss_limit_used_pct": 92.5,
            "positions_count": 3,
            "max_positions": 5,
            "total_exposure": 36450.00,
            "max_exposure": 100000.0,
            "status": "warning",
            "message": "Approaching daily loss limit"
        }
    """
    response = await http_client.get(
        "http://risk-manager:5004/api/v1/risk/status"
    )
    return response.json()
```

### 4.6 Reporting Tools

#### **Tool: get_performance_report**
```python
@mcp.tool()
async def get_performance_report(
    ctx: Context,
    period: Literal["daily", "weekly", "monthly"] = "daily"
) -> Dict:
    """
    Get performance report for specified period
    
    Args:
        period: "daily", "weekly", or "monthly"
    
    Returns:
        {
            "period": "daily",
            "date_start": "2025-10-25",
            "date_end": "2025-10-25",
            "pnl": -450.25,
            "pnl_pct": -0.45,
            "trades": 8,
            "win_rate": 0.625,
            "sharpe_ratio": 1.05,
            "max_drawdown": -275.00
        }
    """
    response = await http_client.get(
        f"http://reporting:5009/api/v1/reports/{period}"
    )
    return response.json()
```

#### **Tool: get_trade_journal**
```python
@mcp.tool()
async def get_trade_journal(
    ctx: Context,
    date: Optional[str] = None,
    symbol: Optional[str] = None
) -> Dict:
    """
    Get detailed trade journal entries
    
    Args:
        date: Specific date (YYYY-MM-DD) or None for today
        symbol: Filter by symbol or None for all
    
    Returns:
        {
            "trades": [
                {
                    "trade_id": "uuid",
                    "symbol": "TSLA",
                    "entry_time": "2025-10-25T09:45:00Z",
                    "exit_time": "2025-10-25T14:30:00Z",
                    "entry_price": 243.00,
                    "exit_price": 241.50,
                    "quantity": 50,
                    "pnl": -75.00,
                    "pnl_pct": -0.62,
                    "pattern": "bull_flag",
                    "catalyst": "Earnings beat",
                    "outcome": "loss",
                    "notes": "Stopped out at support break"
                }
            ]
        }
    """
    params = {}
    if date:
        params["date"] = date
    if symbol:
        params["symbol"] = symbol
        
    response = await http_client.get(
        "http://reporting:5009/api/v1/journal",
        params=params
    )
    return response.json()
```

---

## 5. REST API Specifications

### 5.1 Scanner Service API (Port 5001)

#### **POST /api/v1/scan/start**
```yaml
Description: Start a new market scan
Method: POST
Authentication: API Key (X-API-Key header)

Request Body:
  {
    "cycle_id": "uuid",
    "universe_size": 100,
    "filters": {
      "min_price": 5.0,
      "min_volume": 1000000,
      "news_required": true
    }
  }

Response (200 OK):
  {
    "scan_id": "uuid",
    "status": "started",
    "estimated_completion": "2025-10-25T08:05:00Z"
  }

Errors:
  400: Invalid request parameters
  401: Unauthorized (invalid API key)
  409: Scan already in progress
  500: Internal server error
```

#### **GET /api/v1/scan/latest**
```yaml
Description: Get latest scan results
Method: GET
Authentication: API Key

Query Parameters:
  - top_n: Number of results (default: 5, max: 20)
  - cycle_id: Specific cycle (optional)

Response (200 OK):
  {
    "cycle_id": "uuid",
    "scan_timestamp": "2025-10-25T08:15:00Z",
    "candidates_count": 5,
    "candidates": [
      {
        "symbol": "TSLA",
        "rank": 1,
        "final_score": 0.883,
        "catalyst_score": 0.92,
        "technical_score": 0.88,
        "pattern_score": 0.85,
        "price": 242.50,
        "volume": 15234567
      }
    ]
  }

Errors:
  404: No scan results found
  500: Internal server error
```

#### **GET /api/v1/scan/candidates/{symbol}**
```yaml
Description: Get detailed candidate analysis
Method: GET
Authentication: API Key

Path Parameters:
  - symbol: Stock ticker (e.g., "TSLA")

Response (200 OK):
  {
    "symbol": "TSLA",
    "scan_timestamp": "2025-10-25T08:15:00Z",
    "catalyst": {...},
    "technical": {...},
    "pattern": {...},
    "risk_assessment": {...}
  }

Errors:
  404: Symbol not found in scan results
  500: Internal server error
```

### 5.2 Trading Service API (Port 5005)

#### **POST /api/v1/orders**
```yaml
Description: Submit a new order
Method: POST
Authentication: API Key

Request Body:
  {
    "symbol": "TSLA",
    "side": "buy",
    "quantity": 50,
    "order_type": "market|limit",
    "limit_price": 243.00  # Required if order_type="limit"
  }

Response (201 Created):
  {
    "order_id": "uuid",
    "status": "submitted",
    "symbol": "TSLA",
    "quantity": 50,
    "alpaca_order_id": "alpaca-order-id",
    "submitted_at": "2025-10-25T09:45:00Z"
  }

Errors:
  400: Invalid request parameters
  401: Unauthorized
  403: Risk validation failed
  500: Alpaca API error
```

#### **GET /api/v1/orders/{order_id}/status**
```yaml
Description: Get order status
Method: GET
Authentication: API Key

Path Parameters:
  - order_id: Order UUID

Response (200 OK):
  {
    "order_id": "uuid",
    "status": "submitted|filled|partially_filled|cancelled|rejected",
    "filled_qty": 50,
    "avg_fill_price": 242.75,
    "filled_at": "2025-10-25T09:45:15Z"
  }

Errors:
  404: Order not found
  500: Internal server error
```

#### **POST /api/v1/positions/{symbol}/close**
```yaml
Description: Close an open position
Method: POST
Authentication: API Key

Path Parameters:
  - symbol: Stock ticker

Request Body:
  {
    "reason": "Manual close"
  }

Response (200 OK):
  {
    "position_id": "uuid",
    "symbol": "TSLA",
    "quantity_closed": 50,
    "avg_exit_price": 241.50,
    "realized_pnl": -75.00,
    "realized_pnl_pct": -0.62,
    "closed_at": "2025-10-25T14:30:00Z"
  }

Errors:
  404: Position not found
  500: Alpaca API error
```

### 5.3 Risk Manager API (Port 5004)

#### **POST /api/v1/risk/validate**
```yaml
Description: Validate a proposed trade against risk limits
Method: POST
Authentication: API Key

Request Body:
  {
    "symbol": "TSLA",
    "side": "buy",
    "quantity": 50,
    "price": 242.50  # Optional, uses current if not provided
  }

Response (200 OK):
  {
    "approved": true,
    "position_size": 50,
    "risk_amount": 250.00,
    "max_risk": 2000.00,
    "checks_passed": [
      "daily_loss_limit",
      "position_size_limit",
      "correlation_check",
      "max_positions"
    ]
  }

Response (403 Forbidden - Risk Check Failed):
  {
    "approved": false,
    "reason": "Daily loss limit exceeded",
    "details": {
      "current_loss": -2050.00,
      "max_loss": -2000.00,
      "check_failed": "daily_loss_limit"
    }
  }

Errors:
  400: Invalid request
  500: Internal server error
```

#### **GET /api/v1/risk/status**
```yaml
Description: Get current risk exposure
Method: GET
Authentication: API Key

Response (200 OK):
  {
    "daily_pnl": -1850.00,
    "daily_pnl_pct": -1.85,
    "max_daily_loss": -2000.0,
    "loss_limit_used_pct": 92.5,
    "positions_count": 3,
    "max_positions": 5,
    "total_exposure": 36450.00,
    "capital": 100000.0,
    "status": "warning|healthy|critical"
  }
```

#### **POST /api/v1/config/update**
```yaml
Description: Update risk configuration parameter
Method: POST
Authentication: API Key

Request Body:
  {
    "parameter_path": "daily_limits.max_daily_loss_usd",
    "new_value": 3000.0
  }

Response (200 OK):
  {
    "parameter": "daily_limits.max_daily_loss_usd",
    "old_value": 2000.0,
    "new_value": 3000.0,
    "updated_at": "2025-10-25T15:00:00Z"
  }

Errors:
  400: Invalid parameter or value
  403: Parameter cannot be changed during trading hours
  500: Internal server error
```

### 5.4 Workflow Service API (Port 5006)

#### **POST /api/v1/workflow/start**
```yaml
Description: Start new trading workflow
Method: POST
Authentication: API Key

Request Body:
  {
    "session_mode": "autonomous|supervised"
  }

Response (201 Created):
  {
    "cycle_id": "uuid",
    "date": "2025-10-25",
    "session_mode": "supervised",
    "status": "started",
    "phase": "pre-market"
  }

Errors:
  409: Workflow already running
  500: Internal server error
```

#### **POST /api/v1/workflow/stop**
```yaml
Description: Stop current workflow and close positions
Method: POST
Authentication: API Key

Request Body:
  {
    "reason": "Manual stop"
  }

Response (200 OK):
  {
    "cycle_id": "uuid",
    "status": "stopped",
    "positions_closed": 3,
    "final_pnl": -450.25,
    "stopped_at": "2025-10-25T15:30:00Z"
  }
```

#### **GET /api/v1/workflow/status**
```yaml
Description: Get current workflow status
Method: GET
Authentication: API Key

Response (200 OK):
  {
    "cycle_id": "uuid",
    "date": "2025-10-25",
    "cycle_state": "scanning|evaluating|trading|monitoring|closed",
    "phase": "pre-market|opening-range|morning|midday|power-hour|closed",
    "session_mode": "supervised",
    "started_at": "2025-10-25T08:00:00Z"
  }
```

### 5.5 News Service API (Port 5008)

#### **GET /api/v1/news/recent**
```yaml
Description: Get recent news for symbols
Method: GET
Authentication: API Key

Query Parameters:
  - symbols: Comma-separated list (e.g., "TSLA,NVDA,AAPL")
  - hours: Hours to look back (default: 24)
  - min_sentiment: Minimum sentiment score (default: 0.5)

Response (200 OK):
  {
    "news_count": 15,
    "news_items": [
      {
        "news_id": "uuid",
        "symbol": "TSLA",
        "headline": "Tesla Q3 earnings beat expectations",
        "published_at": "2025-10-25T06:30:00Z",
        "sentiment_score": 0.85,
        "sentiment_label": "positive",
        "catalyst_type": "earnings",
        "catalyst_strength": 0.92,
        "source": "Benzinga",
        "url": "https://..."
      }
    ]
  }
```

#### **GET /api/v1/news/catalyst-scan**
```yaml
Description: Scan for stocks with recent catalysts
Method: GET
Authentication: API Key

Query Parameters:
  - min_catalyst_strength: Minimum catalyst strength (default: 0.7)
  - hours: Hours to look back (default: 12)
  - limit: Max results (default: 50)

Response (200 OK):
  {
    "symbols_with_catalysts": 35,
    "catalysts": [
      {
        "symbol": "TSLA",
        "catalyst_count": 3,
        "strongest_catalyst": {
          "headline": "...",
          "catalyst_type": "earnings",
          "catalyst_strength": 0.92,
          "sentiment_score": 0.85
        }
      }
    ]
  }
```

### 5.6 Reporting Service API (Port 5009)

#### **GET /api/v1/reports/{period}**
```yaml
Description: Get performance report
Method: GET
Authentication: API Key

Path Parameters:
  - period: "daily", "weekly", "monthly"

Response (200 OK):
  {
    "period": "daily",
    "date_start": "2025-10-25",
    "date_end": "2025-10-25",
    "pnl": -450.25,
    "pnl_pct": -0.45,
    "trades_executed": 8,
    "trades_won": 5,
    "trades_lost": 3,
    "win_rate": 0.625,
    "profit_factor": 1.23,
    "sharpe_ratio": 1.05,
    "max_drawdown": -275.00,
    "avg_win": 225.50,
    "avg_loss": -183.75
  }
```

#### **GET /api/v1/journal**
```yaml
Description: Get trade journal entries
Method: GET
Authentication: API Key

Query Parameters:
  - date: YYYY-MM-DD (optional)
  - symbol: Filter by symbol (optional)
  - outcome: "win|loss|scratch" (optional)

Response (200 OK):
  {
    "trades_count": 8,
    "trades": [
      {
        "trade_id": "uuid",
        "symbol": "TSLA",
        "entry_time": "2025-10-25T09:45:00Z",
        "exit_time": "2025-10-25T14:30:00Z",
        "entry_price": 243.00,
        "exit_price": 241.50,
        "quantity": 50,
        "pnl": -75.00,
        "pnl_pct": -0.62,
        "pattern": "bull_flag",
        "catalyst": "Earnings beat",
        "outcome": "loss",
        "hold_time_minutes": 285,
        "notes": "Stopped out at support break"
      }
    ]
  }
```

---

## 6. Data Flow Specifications

### 6.1 Daily Trading Workflow

```
08:00 ET - Pre-Market Scan
  ┌─────────────────────────────────────────────────┐
  │ 1. Workflow Service triggers Scanner Service   │
  │ 2. News Service provides catalyst data         │
  │ 3. Scanner filters 100 → 35 → 20 → 10 → 5     │
  │ 4. Results stored in database                   │
  │ 5. Redis pub/sub notifies Orchestration        │
  └─────────────────────────────────────────────────┘
                        ↓
09:30 ET - Market Open
  ┌─────────────────────────────────────────────────┐
  │ 1. Claude Desktop queries via MCP               │
  │ 2. Orchestration returns top 5 candidates       │
  │ 3. Claude analyzes and selects trades           │
  │ 4. Claude calls execute_trade() tool            │
  └─────────────────────────────────────────────────┘
                        ↓
Trading Hours - Position Monitoring
  ┌─────────────────────────────────────────────────┐
  │ 1. Workflow monitors open positions             │
  │ 2. Risk Manager checks limits continuously      │
  │ 3. Alerts sent to Claude Desktop if needed      │
  │ 4. Claude can query position status via MCP     │
  │ 5. Claude can close positions via MCP tools     │
  └─────────────────────────────────────────────────┘
                        ↓
15:30-16:00 ET - Market Close & Reconciliation
  ┌─────────────────────────────────────────────────┐
  │ 1. Workflow closes all open positions           │
  │ 2. Trading Service reconciles with Alpaca       │
  │ 3. Reporting Service calculates daily metrics   │
  │ 4. Email alert sent to trader                   │
  │ 5. Database updated with final results          │
  └─────────────────────────────────────────────────┘
```

### 6.2 News → Scanner Integration

```
News Service (Port 5008)
  ↓
  1. Polls Benzinga/NewsAPI every 15 minutes
  2. Sentiment analysis via FinBERT
  3. Catalyst classification
  4. Stores in news_sentiment table
  5. Publishes to Redis: "news:new_catalyst"
  ↓
Scanner Service (Port 5001)
  ↓
  1. Subscribes to Redis: "news:new_catalyst"
  2. Queries news_sentiment table for recent catalysts
  3. Filters universe by catalyst_strength > 0.7
  4. Applies technical and pattern filters
  5. Returns top 5 candidates
```

### 6.3 Risk Validation Flow

```
Claude Desktop → execute_trade() MCP Tool
  ↓
Orchestration Service (Port 5000)
  ↓
  Calls Risk Manager API: POST /api/v1/risk/validate
  ↓
Risk Manager Service (Port 5004)
  ↓
  1. Check daily loss limit
  2. Check position size limits
  3. Check max positions
  4. Check correlation with existing positions
  5. Calculate position size (Kelly criterion)
  ↓
  IF approved → Return OK
  IF rejected → Return 403 with reason
  ↓
Orchestration Service
  ↓
  IF approved → Call Trading Service
  IF rejected → Raise McpError to Claude
  ↓
Trading Service (Port 5005)
  ↓
  Submit order to Alpaca API
  ↓
  Store order in database
  ↓
  Return order_id to Claude
```

### 6.4 Database Write Patterns

**All services write to normalized schema using foreign keys:**

```python
# Example: News Service writing news_sentiment

# Step 1: Get security_id (or create if new)
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", symbol
)

# Step 2: Get time_id
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", published_at
)

# Step 3: Insert news with FKs
await db.execute("""
    INSERT INTO news_sentiment (
        security_id, time_id, headline, summary, url,
        sentiment_score, catalyst_type, catalyst_strength
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
""", security_id, time_id, headline, summary, url,
     sentiment, catalyst_type, strength)
```

**NO service stores symbol VARCHAR directly!**

---

## 7. Claude Interaction Patterns

### 7.1 Daily Session Start

**User Intent**: "Start trading session in supervised mode"

**Claude Actions**:
```
1. Call MCP tool: start_trading_session(session_mode="supervised")
2. Receive cycle_id and confirmation
3. Inform user: "Trading session started. Supervising risk actions today."
```

**MCP Request**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "start_trading_session",
    "arguments": {
      "session_mode": "supervised"
    }
  }
}
```

**MCP Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"cycle_id\": \"...\", \"status\": \"started\", \"session_mode\": \"supervised\"}"
    }
  ]
}
```

### 7.2 Review Scan Results

**User Intent**: "What stocks should we trade today?"

**Claude Actions**:
```
1. Call MCP tool: get_scan_results()
2. Read candidates list
3. For top 3, call: get_candidate_analysis(symbol)
4. Synthesize analysis for user
5. Provide recommendation
```

**Example Response to User**:
```
Here are today's top candidates:

1. **TSLA** (Rank #1, Score: 0.88)
   - Catalyst: Q3 earnings beat expectations (sentiment: 0.85)
   - Pattern: Bull flag breakout
   - Entry: $243.00, Target: $252.00, Stop: $238.00
   - Risk/Reward: 1.8:1
   - Position size: 50 shares ($250 risk)

2. **NVDA** (Rank #2, Score: 0.85)
   - Catalyst: New AI chip announcement (sentiment: 0.82)
   - Pattern: Cup and handle
   - Entry: $485.00, Target: $498.00, Stop: $478.00
   - Risk/Reward: 1.9:1
   - Position size: 25 shares ($175 risk)

Would you like me to execute any of these trades?
```

### 7.3 Execute Trade

**User Intent**: "Yes, buy TSLA with the recommended position size"

**Claude Actions**:
```
1. Extract: symbol=TSLA, quantity=50, side=buy
2. Call MCP tool: execute_trade(symbol="TSLA", side="buy", quantity=50)
3. Wait for order confirmation
4. Inform user of execution
```

**Example Response to User**:
```
✅ Order executed successfully!

Order Details:
- Symbol: TSLA
- Side: BUY
- Quantity: 50 shares
- Order Type: Market
- Status: Filled
- Avg Fill Price: $242.75
- Total Cost: $12,137.50
- Stop Loss: $238.00 (automatic)
- Take Profit: $252.00 (automatic)

Position now open. I'll monitor it for you.
```

### 7.4 Risk Alert Handling (Supervised Mode)

**System Trigger**: Daily P&L reaches -$1,900 (95% of $2,000 limit)

**Claude Notification** (via MCP resource update):
```
🟡 RISK ALERT: Daily loss limit approaching

Current Status:
- Daily P&L: -$1,900 (-1.9%)
- Loss Limit: $2,000
- Limit Used: 95%
- Positions: 3 open
  - TSLA: -$450 (at support)
  - NVDA: -$825 (breaking down)
  - AAPL: +$125 (holding well)

Supervised Mode: I need your decision within 5 minutes.

Options:
1. Close all positions (lock in -$1,900 loss)
2. Close NVDA only (high-confidence loser)
3. Keep TSLA (at strong support, 70% bounce probability)
4. Update loss limit to $3,000 (give more room)

What would you like me to do?
```

**User Intent**: "Close NVDA, keep the others"

**Claude Actions**:
```
1. Call MCP tool: close_position(symbol="NVDA", reason="Breaking support")
2. Confirm closure
3. Update risk status
4. Inform user
```

**Example Response to User**:
```
✅ NVDA position closed

Closed Position:
- Symbol: NVDA
- Quantity: 25 shares
- Avg Exit: $478.50
- Realized P&L: -$825.00 (-1.68%)

Updated Status:
- Daily P&L: -$1,075 (-1.08%)
- Loss Limit Used: 53.8%
- Open Positions: 2 (TSLA, AAPL)

We're now safely below the warning threshold. I'll continue monitoring.
```

### 7.5 End of Day Summary

**System Trigger**: 16:00 ET (market close)

**Claude Notification**:
```
📊 Daily Trading Summary - October 25, 2025

Performance:
- Daily P&L: -$450.25 (-0.45%)
- Trades: 8 executed
- Win Rate: 62.5% (5 wins, 3 losses)
- Profit Factor: 1.23
- Largest Win: $420 (AAPL)
- Largest Loss: -$275 (NVDA)

Top Performers:
1. ✅ AAPL: +$420 (bull flag worked perfectly)
2. ✅ AMD: +$315 (earnings catalyst)
3. ❌ NVDA: -$275 (support broke, stopped out)

Lessons Learned:
- TSLA support bounce validated (saved $575 by keeping position)
- NVDA breakdown was correct call (closed at -$825, avoided -$1,200)

View full trade journal: [Link]

Same time tomorrow?
```

---

## 8. Error Handling

### 8.1 MCP Error Codes

**Standard McpError codes used:**

```python
from mcp.types import ErrorCode

# Invalid request parameters
ErrorCode.INVALID_REQUEST  # -32602

# Resource not found
ErrorCode.RESOURCE_NOT_FOUND  # -32002

# Internal server error
ErrorCode.INTERNAL_ERROR  # -32603
```

### 8.2 Error Response Format

```python
raise McpError(
    ErrorCode.INVALID_REQUEST,
    "Risk validation failed: Daily loss limit exceeded",
    {
        "current_loss": -2050.00,
        "max_loss": -2000.00,
        "check_failed": "daily_loss_limit"
    }
)
```

**MCP Error Response**:
```json
{
  "error": {
    "code": -32602,
    "message": "Risk validation failed: Daily loss limit exceeded",
    "data": {
      "current_loss": -2050.00,
      "max_loss": -2000.00,
      "check_failed": "daily_loss_limit"
    }
  }
}
```

### 8.3 Service Error Handling

**All REST services return standardized error responses:**

```json
{
  "error": {
    "code": "RISK_VALIDATION_FAILED",
    "message": "Daily loss limit exceeded",
    "details": {
      "current_loss": -2050.00,
      "max_loss": -2000.00
    },
    "timestamp": "2025-10-25T14:30:00Z",
    "request_id": "uuid"
  }
}
```

**HTTP Status Codes**:
- 400: Bad Request (invalid parameters)
- 401: Unauthorized (missing/invalid API key)
- 403: Forbidden (risk check failed, insufficient permissions)
- 404: Not Found (resource doesn't exist)
- 409: Conflict (duplicate resource, workflow already running)
- 500: Internal Server Error (unexpected failure)
- 503: Service Unavailable (database down, external API timeout)

### 8.4 Database Error Handling

**Connection pool exhaustion**:
```python
try:
    async with db.acquire() as conn:
        result = await conn.fetchrow(query)
except asyncpg.TooManyConnectionsError:
    logger.error("Database connection pool exhausted")
    raise HTTPException(
        status_code=503,
        detail="Database temporarily unavailable"
    )
```

**Constraint violations**:
```python
try:
    await db.execute(insert_query, ...)
except asyncpg.ForeignKeyViolationError as e:
    logger.error(f"Foreign key violation: {e}")
    raise HTTPException(
        status_code=400,
        detail="Invalid security_id reference"
    )
```

### 8.5 External API Error Handling

**Alpaca API errors**:
```python
try:
    response = await alpaca_client.submit_order(...)
except AlpacaAPIError as e:
    logger.error(f"Alpaca API error: {e}")
    
    if e.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="Insufficient buying power"
        )
    elif e.status_code == 429:
        raise HTTPException(
            status_code=503,
            detail="Rate limit exceeded, retry in 60 seconds"
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Order execution failed"
        )
```

**News API timeout**:
```python
try:
    response = await http_client.get(
        news_api_url,
        timeout=10.0
    )
except asyncio.TimeoutError:
    logger.warning("News API timeout, using cached data")
    return await get_cached_news()
```

---

## 9. Performance Requirements

### 9.1 Response Time Targets

| Endpoint Type | Target | Maximum |
|---------------|--------|---------|
| MCP Tool Calls | <500ms | <2s |
| REST API (Simple) | <100ms | <500ms |
| REST API (Complex) | <500ms | <2s |
| Market Scan | <30s | <60s |
| Database Queries | <50ms | <200ms |
| Redis Operations | <10ms | <50ms |

### 9.2 Throughput Requirements

| Operation | Target TPS | Peak TPS |
|-----------|------------|----------|
| MCP Requests | 10 | 50 |
| REST API Calls | 100 | 500 |
| Database Writes | 50 | 200 |
| Redis Pub/Sub | 1000 | 5000 |

### 9.3 Resource Utilization

**Per Service Limits**:
```yaml
CPU: 
  Reservation: 0.25 cores
  Limit: 1.0 core

Memory:
  Reservation: 256MB
  Limit: 1GB

Connections:
  Database: 5 per service (45 total)
  Redis: 10 per service
```

**Total System**:
```yaml
Droplet: 4vCPU, 8GB RAM
Expected Utilization:
  - CPU: 50-70% during market hours
  - Memory: 60-75% (leaves headroom)
  - Database connections: 45/100 (safe margin)
  - Network: <1GB/day
```

### 9.4 Data Volume Estimates

**Daily Data Generation**:
```yaml
Trading Days: ~252 per year
Daily Records:
  - trading_history: ~500 records (OHLCV per symbol)
  - news_sentiment: ~200 records
  - scan_results: ~5 records
  - orders: ~10 records
  - positions: ~10 records
  - technical_indicators: ~100 records

Annual Growth: ~500MB/year
Storage Requirements: 10GB database (20 years capacity)
```

---

## 10. Security Requirements

### 10.1 Authentication

**API Key Authentication**:
```yaml
All REST endpoints require:
  Header: X-API-Key: <api-key>
  
API Keys:
  - Generated per service
  - Stored in environment variables
  - Rotated quarterly
  - Never logged or exposed
```

**MCP Authentication**:
```yaml
Claude Desktop → Nginx:
  - TLS 1.3 required
  - Certificate pinning
  - API key in custom header

Nginx → Orchestration:
  - Internal Docker network
  - No external exposure
  - API key validation
```

### 10.2 Network Security

**Firewall Rules**:
```bash
# Only allow SSH and HTTPS
ufw allow 22/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw default allow outgoing
ufw enable
```

**Docker Network Isolation**:
```yaml
networks:
  catalyst-network:
    driver: bridge
    internal: false  # Allows external API calls
    ipam:
      config:
        - subnet: 172.18.0.0/16
```

### 10.3 Data Protection

**Environment Variables**:
```bash
# Never commit to Git
.env files in .gitignore

# Secrets management
ALPACA_API_KEY=<encrypted>
ALPACA_SECRET_KEY=<encrypted>
DATABASE_URL=<encrypted>
NEWS_API_KEY=<encrypted>
```

**Database Security**:
```yaml
PostgreSQL (Managed):
  - SSL/TLS required
  - Firewall: Only droplet IP allowed
  - Credentials: Rotated monthly
  - Backups: Encrypted at rest
  - Connection string: Not in code
```

### 10.4 Audit Logging

**All critical actions logged**:
```python
logger.info(
    "Order executed",
    extra={
        "user": "claude_desktop",
        "symbol": "TSLA",
        "quantity": 50,
        "order_id": order_id,
        "risk_validated": True,
        "timestamp": datetime.now(timezone.utc)
    }
)
```

**Log Retention**:
- Application logs: 90 days
- Audit logs: 7 years (regulatory compliance)
- Database backups: 30 days

---

## 11. Deployment Checklist

### 11.1 Pre-Deployment

- [ ] All services pass health checks locally
- [ ] Database schema v6.0 deployed and validated
- [ ] Environment variables configured (.env.prod)
- [ ] API keys generated and stored securely
- [ ] SSL certificate obtained (Let's Encrypt)
- [ ] Firewall configured (ports 22, 443 only)
- [ ] Docker images built and tagged
- [ ] docker-compose.yml validated

### 11.2 Deployment

- [ ] DigitalOcean droplet provisioned (4vCPU, 8GB)
- [ ] PostgreSQL managed database created
- [ ] Connection string tested
- [ ] Services deployed via docker-compose
- [ ] Health checks passing for all 9 services
- [ ] Redis pub/sub working
- [ ] Nginx reverse proxy configured
- [ ] Claude Desktop MCP connection tested

### 11.3 Post-Deployment

- [ ] Alpaca API integration tested (paper trading)
- [ ] News feeds operational (Benzinga, NewsAPI)
- [ ] Market scan executed successfully
- [ ] Risk validation working
- [ ] Order execution tested (paper)
- [ ] Email alerts configured
- [ ] Monitoring dashboards operational
- [ ] Backup procedures verified

### 11.4 Production Validation

- [ ] Paper trading for 1 week (validate all workflows)
- [ ] Review logs for errors
- [ ] Performance metrics within targets
- [ ] No database connection issues
- [ ] No API rate limit violations
- [ ] Risk management working correctly
- [ ] Claude Desktop interaction smooth
- [ ] **THEN**: Enable live trading

---

## 12. Success Criteria

**Production system considered complete when:**

✅ **Infrastructure**: All 9 services deployed and healthy  
✅ **Database**: Schema v6.0 with normalized structure  
✅ **Integration**: Claude Desktop MCP connection stable  
✅ **Execution**: Alpaca orders executing reliably  
✅ **Intelligence**: News catalyst detection operational  
✅ **Risk**: Risk management enforcing limits  
✅ **Performance**: All response time targets met  
✅ **Reliability**: 99% uptime during market hours  
✅ **Trading**: Paper trading profitable for 1 week  

**Stage 1 trading considered successful when:**

✅ **Profitability**: Consistent gains over 4 consecutive weeks  
✅ **Win Rate**: ≥60% achieved  
✅ **Risk Management**: No daily loss limit breaches  
✅ **Data Collection**: 500+ trades logged with full context  
✅ **System Stability**: No critical failures for 30 days  

**Ready for Research Instance when:**

✅ **Production Profitable**: 2+ months of consistent gains  
✅ **Data Volume**: 1000+ trades collected  
✅ **Pattern Recognition**: High-quality labeled dataset  
✅ **Capital Growth**: Portfolio up 10%+ from start  

---

## Appendix A: Glossary

**Catalyst**: News event driving significant price movement (earnings, FDA, merger)  
**Candidate**: Stock passing initial filtering criteria  
**Cycle**: Complete trading workflow (pre-market → close)  
**MCP**: Model Context Protocol (Claude communication)  
**Stage 1**: Rule-based trading with data collection  
**Supervised Mode**: System warns before taking action (5-min window)  
**Autonomous Mode**: System acts immediately on risk limits  
**3NF**: Third Normal Form (database normalization)  
**FK**: Foreign Key (database relationship)  
**OHLCV**: Open, High, Low, Close, Volume  
**R:R**: Risk-to-Reward ratio  

---

## Appendix B: Related Documents

**Current Documents**:
- database-schema-mcp-v60.md (Production database)
- architecture-mcp-v60.md (System architecture)
- deployment-architecture-v30.md (Infrastructure)
- strategy-ml-roadmap-v44.md (Strategic vision)

**Future Documents** (Month 6+):
- research-functional-spec-v10.md (Research system)
- research-database-schema-v10.md (Research database)
- research-architecture-v10.md (Research architecture)
- research-deployment-v10.md (Research infrastructure)

---

**END OF FUNCTIONAL SPECIFICATION v6.0**

*Clean Production system specification. No Research contamination. Ready for immediate implementation.*

🎩 **DevGenius Status**: PRODUCTION SYSTEM LOCKED AND LOADED! 🚀
