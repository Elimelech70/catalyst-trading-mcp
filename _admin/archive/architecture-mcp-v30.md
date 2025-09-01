# Catalyst Trading System - MCP Architecture v3.0.0

**Repository**: catalyst-trading-mcp  
**Version**: 3.0.0  
**Date**: Aug 01, 2025  
**Status**: MCP Migration Architecture  
**Previous Version**: 2.1.0 (July 8, 2025)

## Revision History

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

### Core Innovation with MCP

1. **AI-Native Architecture**: Services designed for AI interaction first
2. **Unified Protocol**: All communication through MCP instead of REST/HTTP
3. **Resource-Oriented**: Data exposed as queryable MCP resources
4. **Tool-Based Actions**: Trading operations as invocable MCP tools
5. **Context Preservation**: Stateful sessions for complex workflows

## System Architecture

### High-Level MCP Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 CATALYST TRADING SYSTEM v3.0.0                  │
│                      MCP Architecture                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    MCP Client Layer                     │    │
│  │                                                         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │    │
│  │  │   Claude    │  │   Custom    │  │   Web UI    │      │    │
│  │  │   Desktop   │  │   Client    │  │   Client    │      │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │    │
│  │         │                │                │             │    │
│  │         └────────────────┴────────────────┘             │    │
│  │                          │                              │    │
│  │                    MCP Transport Layer                  │    │
│  │              (WebSocket / stdio / HTTP)                 │    │
│  └───────────────────────────┬─────────────────────────────┘    │
│                              │                                  │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                    MCP Server Layer                       │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │              News Intelligence MCP Server           │  │  │
│  │  │                    (Port 5008)                      │  │  │
│  │  │                                                     │  │  │
│  │  │  Resources:                Tools:                   │  │  │
│  │  │  • news/raw               • collect_news            │  │  │
│  │  │  • news/by-symbol         • search_news             │  │  │
│  │  │  • source/metrics         • analyze_sentiment       │  │  │
│  │  │  • narrative/clusters     • track_narrative         │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │            Security Scanner MCP Server              │  │  │
│  │  │                    (Port 5001)                      │  │  │
│  │  │                                                     │  │  │
│  │  │  Resources:                Tools:                   │  │  │
│  │  │  • candidates/active      • scan_market             │  │  │
│  │  │  • candidates/history     • scan_premarket          │  │  │
│  │  │  • market/universe        • analyze_catalyst        │  │  │
│  │  │                           • select_candidates       │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │           Pattern Analysis MCP Server               │  │  │
│  │  │                    (Port 5002)                      │  │  │
│  │  │                                                     │  │  │
│  │  │  Resources:                Tools:                   │  │  │
│  │  │  • patterns/detected      • detect_patterns         │  │  │
│  │  │  • patterns/by-symbol     • analyze_pattern         │  │  │
│  │  │  • patterns/success-rate  • validate_pattern        │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │          Technical Analysis MCP Server              │  │  │
│  │  │                    (Port 5003)                      │  │  │
│  │  │                                                     │  │  │
│  │  │  Resources:                Tools:                   │  │  │
│  │  │  • indicators/current     • calculate_indicators    │  │  │
│  │  │  • signals/pending        • generate_signal         │  │  │
│  │  │  • signals/history        • validate_signal         │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │             Trading Execution MCP Server            │  │  │
│  │  │                    (Port 5005)                      │  │  │
│  │  │                                                     │  │  │
│  │  │  Resources:                Tools:                   │  │  │
│  │  │  • positions/open         • execute_trade           │  │  │
│  │  │  • trades/history         • close_position          │  │  │
│  │  │  • account/status         • update_stop_loss        │  │  │
│  │  │                           • get_pnl                 │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │           Orchestration MCP Server                  │  │  │
│  │  │                    (Port 5009)                      │  │  │
│  │  │                                                     │  │  │
│  │  │  Resources:                Tools:                   │  │  │
│  │  │  • workflow/status        • start_trading_cycle     │  │  │
│  │  │  • health/services        • stop_trading            │  │  │
│  │  │  • config/trading         • run_backtest            │  │  │
│  │  │                           • update_config           │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Data & Infrastructure Layer             │    │
│  │     (PostgreSQL, Redis, DigitalOcean - Unchanged)       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### MCP Server Architecture Pattern

Each service follows this MCP server pattern:

```python
# Example: News Intelligence MCP Server
class NewsIntelligenceMCPServer:
    """MCP Server for news collection and intelligence"""
    
    def __init__(self):
        self.server = MCPServer("news-intelligence")
        self._register_resources()
        self._register_tools()
    
    def _register_resources(self):
        """Register data resources"""
        
        @self.server.resource("news/raw")
        async def get_raw_news(params: ResourceParams) -> ResourceResponse:
            """Access raw news data"""
            filters = params.get("filters", {})
            return ResourceResponse(
                resource_type="news_collection",
                data=await self._fetch_news(filters),
                metadata={"count": len(data), "last_updated": datetime.now()}
            )
        
        @self.server.resource("news/by-symbol/{symbol}")
        async def get_news_by_symbol(params: ResourceParams) -> ResourceResponse:
            """Get news for specific symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "24h")
            return ResourceResponse(
                resource_type="symbol_news",
                data=await self._fetch_symbol_news(symbol, timeframe)
            )
    
    def _register_tools(self):
        """Register callable tools"""
        
        @self.server.tool("collect_news")
        async def collect_news(params: ToolParams) -> ToolResponse:
            """Trigger news collection"""
            sources = params.get("sources", ["all"])
            results = await self._collect_from_sources(sources)
            return ToolResponse(
                success=True,
                data={"collected": results["count"], "new": results["new"]},
                metadata={"duration": results["duration"]}
            )
        
        @self.server.tool("analyze_sentiment")
        async def analyze_sentiment(params: ToolParams) -> ToolResponse:
            """Analyze news sentiment for symbol"""
            symbol = params["symbol"]
            sentiment = await self._analyze_sentiment(symbol)
            return ToolResponse(
                success=True,
                data=sentiment,
                confidence=sentiment["confidence"]
            )
```

## MCP Protocol Implementation

### 1. Resource Model

Resources provide read access to system data:

```yaml
Resource URI Patterns:
  # News Resources
  - news/raw?since={timestamp}&limit={n}
  - news/by-symbol/{symbol}?timeframe={period}
  - news/catalysts/active
  
  # Trading Resources  
  - candidates/active
  - positions/open
  - trades/history?date={date}
  - signals/pending
  
  # Analysis Resources
  - patterns/by-symbol/{symbol}
  - indicators/{symbol}/{timeframe}
  - performance/daily
```

### 2. Tool Model

Tools provide callable actions:

```yaml
Tool Definitions:
  # Market Operations
  - scan_market:
      params: {mode: aggressive|normal|light}
      returns: {candidates: [...], scan_id: string}
  
  # Trading Operations
  - execute_trade:
      params: {signal_id: string, size_override?: number}
      returns: {trade_id: string, status: string}
  
  # Analysis Operations
  - detect_patterns:
      params: {symbols: string[], timeframes: string[]}
      returns: {patterns: [...], confidence: number}
```

### 3. Transport Layer

MCP supports multiple transport mechanisms:

```python
# WebSocket Transport (Primary)
class WebSocketTransport:
    """For real-time bidirectional communication"""
    
    async def connect(self, url: str):
        self.ws = await websockets.connect(url)
        await self._handshake()
    
    async def send_message(self, message: MCPMessage):
        await self.ws.send(message.to_json())

# stdio Transport (Claude Desktop)
class StdioTransport:
    """For local Claude Desktop integration"""
    
    def send_message(self, message: MCPMessage):
        sys.stdout.write(message.to_json() + "\n")
        sys.stdout.flush()

# HTTP Transport (Legacy compatibility)
class HTTPTransport:
    """Wraps REST APIs in MCP protocol"""
    
    async def send_request(self, request: MCPRequest):
        # Transform MCP to HTTP
        http_response = await self._http_client.post(url, json=request.params)
        # Transform HTTP to MCP
        return MCPResponse.from_http(http_response)
```

## Claude Integration

### 1. Claude Desktop Configuration

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": ["/app/mcp_servers/orchestrator.py"],
      "transport": "stdio",
      "resources": {
        "news/*": "Read news and intelligence data",
        "candidates/*": "View trading candidates",
        "positions/*": "Monitor open positions"
      },
      "tools": {
        "scan_market": "Scan for trading opportunities",
        "execute_trade": "Execute trading signals",
        "analyze_pattern": "Detect chart patterns"
      }
    }
  }
}
```

### 2. Claude Interaction Examples

```
User: "What are the current trading candidates?"

Claude: I'll check the current trading candidates for you.

[Invokes MCP resource: candidates/active]

Based on the scan completed 3 minutes ago, here are the top 5 trading candidates:

1. **NVDA** - Catalyst Score: 85.2
   - Catalyst: Earnings beat + AI guidance raise
   - Pattern: Bull flag on 15-min chart
   - Entry: $485.50, Stop: $478.00

[... continues with formatted analysis ...]
```

### 3. Complex Workflow Support

MCP enables stateful multi-step workflows:

```python
# Claude can maintain context across multiple MCP calls
workflow_session = MCPSession()

# Step 1: Check market conditions
market_status = await workflow_session.resource("market/status")

# Step 2: Run appropriate scan based on conditions
if market_status.is_premarket:
    candidates = await workflow_session.tool("scan_premarket")
else:
    candidates = await workflow_session.tool("scan_market")

# Step 3: Analyze top candidates
for symbol in candidates.top_5:
    patterns = await workflow_session.tool("detect_patterns", {"symbol": symbol})
    
# Step 4: Generate and execute signals
signals = await workflow_session.tool("generate_signals", {"candidates": candidates})
```

## Migration from REST to MCP

### 1. Service Wrapper Pattern

Existing REST services are wrapped in MCP:

```python
class MCPServiceWrapper:
    """Wraps existing REST service in MCP protocol"""
    
    def __init__(self, rest_service):
        self.rest_service = rest_service
        self.mcp_server = MCPServer(rest_service.name)
        self._wrap_endpoints()
    
    def _wrap_endpoints(self):
        """Convert REST endpoints to MCP resources/tools"""
        
        # GET endpoints become resources
        for endpoint in self.rest_service.get_endpoints:
            self._create_resource(endpoint)
            
        # POST/PUT/DELETE become tools
        for endpoint in self.rest_service.action_endpoints:
            self._create_tool(endpoint)
```

### 2. Backwards Compatibility

REST APIs remain available during transition:

```python
# Dual-mode service
class DualModeService:
    def __init__(self):
        self.rest_api = FlaskApp()
        self.mcp_server = MCPServer()
        
    def start(self):
        # Run both REST and MCP in parallel
        threading.Thread(target=self.rest_api.run).start()
        self.mcp_server.run()
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

## Implementation Phases

### Phase 1: MCP Wrapper Layer (Weeks 1-2)
- Wrap existing REST services in MCP
- Deploy stdio transport for Claude Desktop
- Test basic resource/tool access

### Phase 2: Native MCP Services (Weeks 3-4)
- Rewrite core services as MCP-native
- Implement WebSocket transport
- Add stateful session support

### Phase 3: Advanced Features (Weeks 5-6)
- Multi-step workflow support
- Streaming responses for real-time data
- MCP-based service discovery

### Phase 4: Full Migration (Weeks 7-8)
- Deprecate REST endpoints
- Claude-first UI development
- Performance optimization

## Security in MCP Architecture

### 1. Authentication
```python
class MCPAuthenticator:
    async def authenticate(self, request: MCPRequest) -> bool:
        # API key validation
        if not self._validate_api_key(request.auth):
            return False
        
        # Role-based access control
        return self._check_permissions(request.auth.role, request.tool)
```

### 2. Transport Security
- TLS for WebSocket connections
- Signed messages for integrity
- Rate limiting per client

### 3. Resource Access Control
```yaml
Access Control Rules:
  - news/*: public read
  - candidates/*: authenticated read
  - positions/*: owner only
  - execute_trade: trading role required
```

## Monitoring & Observability

### 1. MCP Metrics
```python
class MCPMetrics:
    def track_request(self, request: MCPRequest):
        self.metrics.increment(f"mcp.{request.type}.{request.target}")
        self.metrics.timing(f"mcp.latency", request.duration)
```

### 2. Claude Interaction Tracking
- Log all Claude requests
- Track tool usage patterns
- Monitor resource access frequency

### 3. Performance Monitoring
- Transport latency
- Tool execution time
- Resource query performance

## Conclusion

The migration to MCP architecture transforms the Catalyst Trading System into an AI-native platform, enabling seamless integration with Claude and future AI assistants. This architecture maintains all existing functionality while providing a foundation for advanced AI-driven trading strategies.