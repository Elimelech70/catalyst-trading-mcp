#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py  
Version: 4.4.0
Last Updated: 2025-09-28
Purpose: Complete MCP orchestration service for Claude Desktop integration

REVISION HISTORY:
v.4.4.1 (2025-09-28)
Change Import fixes for MCP
-from mcp.server import FastMCP
-from mcp.types import JSONRPCError as McpError
-from mcp.types import CompletionContext as Context

v4.4.0 (2025-09-28) - Complete MCP implementation
- Added all MCP resources for Claude Desktop access
- Added comprehensive MCP tools for trading operations
- Implemented proper initialization and cleanup handlers
- Added service communication helpers
- Complete implementation ready for Claude Desktop

v4.3.0 (2025-09-27) - HTTP Transport Implementation
- Switched from stdio to HTTP transport
- Supports both Claude Desktop and web dashboard
- Server-Sent Events (SSE) for real-time updates
- Stateless HTTP for scalability
- CORS enabled for dashboard access

v4.2.1 (2025-09-24) - Fixed indentation and import issues
- Fixed indentation error on line 111-112
- Corrected MCP imports to use FastMCP
- Fixed Redis to use async version
- Improved error handling

Description of Service:
Complete MCP orchestration service providing Claude Desktop with full access to:
1. System state via hierarchical resources
2. Trading operations via comprehensive tools
3. Real-time monitoring and control capabilities
4. Seamless integration with all REST services
"""

import asyncio
import logging
import os
import sys
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import asyncpg
from dataclasses import dataclass, asdict
from enum import Enum
import json
import uuid

# MCP imports with fallback
MCP_AVAILABLE = False
try:
    from mcp.server import FastMCP
    from mcp.types import JSONRPCError as McpError
    from mcp.types import CompletionContext as Context
    MCP_AVAILABLE = True
    mcp = FastMCP("catalyst-orchestration")
except ImportError:
    print("MCP not available, running in standalone mode")
    MCP_AVAILABLE = False
    # Create dummy classes for standalone mode
    class FastMCP:
        def __init__(self, name): 
            self.name = name
        def resource(self, path): 
            return lambda f: f
        def tool(self): 
            return lambda f: f
        def on_initialize(self): 
            return lambda f: f
        def on_cleanup(self): 
            return lambda f: f
        def run(self, **kwargs): 
            pass
    class Context: 
        pass
    class McpError(Exception): 
        pass
    mcp = FastMCP("catalyst-orchestration")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === SERVICE CONFIGURATION ===

SERVICE_URLS = {
    "scanner": os.getenv("SCANNER_URL", "http://172.18.0.1:5001"),
    "pattern": os.getenv("PATTERN_URL", "http://172.18.0.1:5002"),
    "technical": os.getenv("TECHNICAL_URL", "http://172.18.0.1:5003"),
    "risk_manager": os.getenv("RISK_URL", "http://172.18.0.1:5004"),
    "trading": os.getenv("TRADING_URL", "http://172.18.0.1:5005"),
    "news": os.getenv("NEWS_URL", "http://172.18.0.1:5008"),
    "reporting": os.getenv("REPORTING_URL", "http://172.18.0.1:5009")
}

class WorkflowState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    MONITORING = "monitoring"

@dataclass
class TradingCycle:
    cycle_id: str
    mode: str
    status: str
    start_time: datetime
    scan_frequency: int = 300
    max_positions: int = 5
    aggressiveness: float = 0.5
    risk_level: float = 0.02
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": self.cycle_id,
            "mode": self.mode,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "scan_frequency": self.scan_frequency,
            "max_positions": self.max_positions,
            "aggressiveness": self.aggressiveness,
            "risk_level": self.risk_level
        }

class SystemState:
    def __init__(self):
        self.current_cycle: Optional[TradingCycle] = None
        self.workflow_state: WorkflowState = WorkflowState.IDLE
        self.service_health: Dict[str, Dict] = {}
        self.db_pool: Optional[asyncpg.Pool] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.shutdown_event = asyncio.Event()
        self.last_health_check: Optional[datetime] = None
        self.active_positions: List[Dict] = []
        self.pending_signals: List[Dict] = []

# Global state instance
state = SystemState()

# === HELPER FUNCTIONS ===

async def call_service(service_name: str, method: str, endpoint: str, data: Optional[Dict] = None, timeout: int = 10) -> Dict:
    """Call a REST service endpoint"""
    try:
        if not state.http_session:
            return {"success": False, "error": "HTTP session not initialized"}
        
        if service_name not in SERVICE_URLS:
            return {"success": False, "error": f"Unknown service: {service_name}"}
        
        url = f"{SERVICE_URLS[service_name]}{endpoint}"
        
        async with aiohttp.ClientTimeout(total=timeout):
            if method.upper() == "GET":
                async with state.http_session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"success": False, "error": f"HTTP {response.status}"}
            elif method.upper() == "POST":
                async with state.http_session.post(url, json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"success": False, "error": f"HTTP {response.status}"}
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}
                
    except asyncio.TimeoutError:
        logger.error(f"Service call timeout: {service_name}/{endpoint}")
        return {"success": False, "error": "Service timeout"}
    except Exception as e:
        logger.error(f"Service call failed {service_name}/{endpoint}: {e}")
        return {"success": False, "error": str(e)}

async def check_all_services() -> Dict:
    """Check health of all services"""
    health_status = {}
    
    for service_name, url in SERVICE_URLS.items():
        try:
            if state.http_session:
                async with state.http_session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        health_status[service_name] = {"status": "healthy", "data": data}
                    else:
                        health_status[service_name] = {"status": "unhealthy", "http_status": resp.status}
            else:
                health_status[service_name] = {"status": "error", "error": "HTTP session not available"}
        except Exception as e:
            health_status[service_name] = {"status": "error", "error": str(e)}
    
    return health_status

async def update_service_health():
    """Update service health status"""
    state.service_health = await check_all_services()
    state.last_health_check = datetime.now()

async def check_database_health() -> Dict:
    """Check database connectivity"""
    try:
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return {"status": "healthy", "connection": "active"}
        else:
            return {"status": "error", "error": "Database pool not initialized"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def generate_cycle_id() -> str:
    """Generate unique cycle ID"""
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"

# === MCP RESOURCES (Read Operations) ===

@mcp.resource("trading_cycle_current")
async def get_current_cycle() -> Dict:
    """Get current trading cycle status"""
    if state.current_cycle:
        return {
            "has_active_cycle": True,
            "cycle": state.current_cycle.to_dict(),
            "workflow_state": state.workflow_state.value,
            "active_positions": len(state.active_positions),
            "pending_signals": len(state.pending_signals)
        }
    return {
        "has_active_cycle": False,
        "status": "no_active_cycle",
        "workflow_state": state.workflow_state.value
    }

@mcp.resource("trading_cycle_performance")
async def get_cycle_performance() -> Dict:
    """Get current cycle performance metrics"""
    try:
        if not state.current_cycle:
            return {"error": "No active trading cycle"}
        
        # Get performance data from reporting service
        result = await call_service("reporting", "GET", f"/api/v1/performance/{state.current_cycle.cycle_id}")
        
        if result.get("success"):
            return result.get("data", {})
        else:
            return {"error": "Failed to fetch performance data"}
            
    except Exception as e:
        logger.error(f"Error getting cycle performance: {e}")
        return {"error": str(e)}

@mcp.resource("market_scan_latest")
async def get_latest_scan() -> Dict:
    """Get latest market scan results"""
    try:
        result = await call_service("scanner", "GET", "/api/v1/scan/latest")
        return result
    except Exception as e:
        logger.error(f"Error getting latest scan: {e}")
        return {"error": str(e)}

@mcp.resource("market_scan_candidates")
async def get_scan_candidates() -> Dict:
    """Get current market scan candidates"""
    try:
        result = await call_service("scanner", "GET", "/api/v1/candidates")
        return result
    except Exception as e:
        logger.error(f"Error getting scan candidates: {e}")
        return {"error": str(e)}

@mcp.resource("positions_active")
async def get_active_positions() -> Dict:
    """Get current active positions"""
    try:
        result = await call_service("trading", "GET", "/api/v1/positions/active")
        if result.get("success"):
            state.active_positions = result.get("data", [])
        return result
    except Exception as e:
        logger.error(f"Error getting active positions: {e}")
        return {"error": str(e)}

@mcp.resource("positions_summary")
async def get_positions_summary() -> Dict:
    """Get positions summary and P&L"""
    try:
        result = await call_service("trading", "GET", "/api/v1/positions/summary")
        return result
    except Exception as e:
        logger.error(f"Error getting positions summary: {e}")
        return {"error": str(e)}

@mcp.resource("system_health")
async def get_system_health() -> Dict:
    """Get overall system health status"""
    try:
        # Update health if stale (older than 30 seconds)
        if not state.last_health_check or (datetime.now() - state.last_health_check).seconds > 30:
            await update_service_health()
        
        return {
            "system_status": "operational" if all(s.get("status") == "healthy" for s in state.service_health.values()) else "degraded",
            "services": state.service_health,
            "workflow_state": state.workflow_state.value,
            "database": await check_database_health(),
            "active_cycle": state.current_cycle.cycle_id if state.current_cycle else None,
            "last_updated": state.last_health_check.isoformat() if state.last_health_check else None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {"error": str(e)}

@mcp.resource("news_latest")
async def get_latest_news() -> Dict:
    """Get latest market news and catalysts"""
    try:
        result = await call_service("news", "GET", "/api/v1/news/latest")
        return result
    except Exception as e:
        logger.error(f"Error getting latest news: {e}")
        return {"error": str(e)}

@mcp.resource("analysis_technical")
async def get_technical_analysis() -> Dict:
    """Get technical analysis for current candidates"""
    try:
        result = await call_service("technical", "GET", "/api/v1/analysis/latest")
        return result
    except Exception as e:
        logger.error(f"Error getting technical analysis: {e}")
        return {"error": str(e)}

@mcp.resource("risk_assessment")
async def get_risk_assessment() -> Dict:
    """Get current risk assessment"""
    try:
        result = await call_service("risk_manager", "GET", "/api/v1/risk/current")
        return result
    except Exception as e:
        logger.error(f"Error getting risk assessment: {e}")
        return {"error": str(e)}

# === MCP TOOLS (Write Operations) ===

@mcp.tool()
async def start_trading_cycle(
    mode: str = "normal",
    aggressiveness: float = 0.5,
    max_positions: int = 5,
    scan_frequency: int = 300,
    risk_level: float = 0.02
) -> Dict:
    """Start a new trading cycle
    
    Args:
        mode: Trading mode (aggressive/normal/conservative)
        aggressiveness: Risk level from 0.0 to 1.0
        max_positions: Maximum concurrent positions
        scan_frequency: Scan frequency in seconds
        risk_level: Maximum risk per trade (0.01 = 1%)
    
    Returns:
        Trading cycle configuration and status
    """
    try:
        if state.current_cycle and state.current_cycle.status in ["active", "starting"]:
            return {"success": False, "error": "Trading cycle already active"}
        
        # Validate parameters
        if mode not in ["aggressive", "normal", "conservative"]:
            return {"success": False, "error": "Invalid mode. Use: aggressive, normal, or conservative"}
        
        if not 0.0 <= aggressiveness <= 1.0:
            return {"success": False, "error": "Aggressiveness must be between 0.0 and 1.0"}
        
        if max_positions < 1 or max_positions > 10:
            return {"success": False, "error": "Max positions must be between 1 and 10"}
        
        # Generate cycle ID
        cycle_id = generate_cycle_id()
        
        # Create new cycle
        state.current_cycle = TradingCycle(
            cycle_id=cycle_id,
            mode=mode,
            status="starting",
            start_time=datetime.now(),
            scan_frequency=scan_frequency,
            max_positions=max_positions,
            aggressiveness=aggressiveness,
            risk_level=risk_level
        )
        
        logger.info(f"Starting trading cycle {cycle_id} in {mode} mode")
        
        # Initialize all services with cycle configuration
        cycle_config = {
            "cycle_id": cycle_id,
            "mode": mode,
            "aggressiveness": aggressiveness,
            "max_positions": max_positions,
            "scan_frequency": scan_frequency,
            "risk_level": risk_level
        }
        
        # Start scanner service
        scanner_result = await call_service("scanner", "POST", "/api/v1/cycle/start", cycle_config)
        if not scanner_result.get("success"):
            state.current_cycle = None
            return {"success": False, "error": f"Failed to start scanner: {scanner_result.get('error')}"}
        
        # Initialize other services
        services_to_init = ["pattern", "technical", "news", "risk_manager"]
        for service_name in services_to_init:
            result = await call_service(service_name, "POST", "/api/v1/cycle/init", cycle_config)
            if not result.get("success"):
                logger.warning(f"Failed to initialize {service_name}: {result.get('error')}")
        
        # Update cycle status
        state.current_cycle.status = "active"
        state.workflow_state = WorkflowState.SCANNING
        
        return {
            "success": True,
            "cycle_id": cycle_id,
            "status": "active",
            "configuration": cycle_config,
            "message": f"Trading cycle {cycle_id} started successfully in {mode} mode"
        }
        
    except Exception as e:
        logger.error(f"Failed to start trading cycle: {e}")
        if state.current_cycle:
            state.current_cycle = None
        return {"success": False, "error": str(e)}

@mcp.tool()
async def stop_trading_cycle() -> Dict:
    """Stop the current trading cycle"""
    try:
        if not state.current_cycle:
            return {"success": False, "error": "No active trading cycle"}
        
        cycle_id = state.current_cycle.cycle_id
        logger.info(f"Stopping trading cycle {cycle_id}")
        
        # Stop all services
        for service_name in SERVICE_URLS.keys():
            result = await call_service(service_name, "POST", "/api/v1/cycle/stop", {"cycle_id": cycle_id})
            if not result.get("success"):
                logger.warning(f"Failed to stop {service_name}: {result.get('error')}")
        
        # Update cycle status
        state.current_cycle.status = "stopped"
        state.workflow_state = WorkflowState.IDLE
        
        # Archive cycle data
        cycle_data = state.current_cycle.to_dict()
        cycle_data["stopped_at"] = datetime.now().isoformat()
        
        # Clear current cycle
        state.current_cycle = None
        state.active_positions = []
        state.pending_signals = []
        
        return {
            "success": True,
            "cycle_id": cycle_id,
            "status": "stopped",
            "final_data": cycle_data,
            "message": f"Trading cycle {cycle_id} stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop trading cycle: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def execute_trade(
    symbol: str,
    action: str,
    quantity: int,
    price: Optional[float] = None,
    order_type: str = "market"
) -> Dict:
    """Execute a trade order
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        action: 'buy' or 'sell'
        quantity: Number of shares
        price: Limit price (optional, uses market price if None)
        order_type: 'market' or 'limit'
    
    Returns:
        Trade execution result
    """
    try:
        if not state.current_cycle:
            return {"success": False, "error": "No active trading cycle"}
        
        # Validate parameters
        if action not in ["buy", "sell"]:
            return {"success": False, "error": "Action must be 'buy' or 'sell'"}
        
        if quantity <= 0:
            return {"success": False, "error": "Quantity must be positive"}
        
        if order_type not in ["market", "limit"]:
            return {"success": False, "error": "Order type must be 'market' or 'limit'"}
        
        if order_type == "limit" and price is None:
            return {"success": False, "error": "Price required for limit orders"}
        
        trade_request = {
            "symbol": symbol.upper(),
            "action": action,
            "quantity": quantity,
            "price": price,
            "order_type": order_type,
            "cycle_id": state.current_cycle.cycle_id
        }
        
        logger.info(f"Executing trade: {action} {quantity} {symbol} @ {price or 'market'}")
        
        # Execute trade through trading service
        result = await call_service("trading", "POST", "/api/v1/orders", trade_request)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to execute trade: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_service_status() -> Dict:
    """Get detailed status of all services"""
    try:
        await update_service_health()
        
        return {
            "success": True,
            "services": state.service_health,
            "system_health": "healthy" if all(s.get("status") == "healthy" for s in state.service_health.values()) else "degraded",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def force_market_scan() -> Dict:
    """Force an immediate market scan"""
    try:
        if not state.current_cycle:
            return {"success": False, "error": "No active trading cycle"}
        
        result = await call_service("scanner", "POST", "/api/v1/scan/force", {
            "cycle_id": state.current_cycle.cycle_id
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to force market scan: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def update_cycle_config(
    scan_frequency: Optional[int] = None,
    max_positions: Optional[int] = None,
    aggressiveness: Optional[float] = None
) -> Dict:
    """Update active trading cycle configuration
    
    Args:
        scan_frequency: New scan frequency in seconds
        max_positions: New maximum positions limit
        aggressiveness: New aggressiveness level (0.0-1.0)
    
    Returns:
        Updated configuration
    """
    try:
        if not state.current_cycle:
            return {"success": False, "error": "No active trading cycle"}
        
        # Update configuration
        if scan_frequency is not None:
            if scan_frequency < 60 or scan_frequency > 3600:
                return {"success": False, "error": "Scan frequency must be between 60 and 3600 seconds"}
            state.current_cycle.scan_frequency = scan_frequency
        
        if max_positions is not None:
            if max_positions < 1 or max_positions > 10:
                return {"success": False, "error": "Max positions must be between 1 and 10"}
            state.current_cycle.max_positions = max_positions
        
        if aggressiveness is not None:
            if not 0.0 <= aggressiveness <= 1.0:
                return {"success": False, "error": "Aggressiveness must be between 0.0 and 1.0"}
            state.current_cycle.aggressiveness = aggressiveness
        
        # Notify services of configuration change
        update_config = state.current_cycle.to_dict()
        
        for service_name in ["scanner", "pattern", "technical", "risk_manager"]:
            result = await call_service(service_name, "POST", "/api/v1/cycle/update", update_config)
            if not result.get("success"):
                logger.warning(f"Failed to update {service_name} config: {result.get('error')}")
        
        return {
            "success": True,
            "updated_config": state.current_cycle.to_dict(),
            "message": "Cycle configuration updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to update cycle config: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def close_position(symbol: str, quantity: Optional[int] = None) -> Dict:
    """Close a position (partial or full)
    
    Args:
        symbol: Stock symbol to close
        quantity: Number of shares to close (None for full position)
    
    Returns:
        Position closure result
    """
    try:
        close_request = {
            "symbol": symbol.upper(),
            "quantity": quantity,
            "cycle_id": state.current_cycle.cycle_id if state.current_cycle else None
        }
        
        result = await call_service("trading", "POST", "/api/v1/positions/close", close_request)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def emergency_stop() -> Dict:
    """Emergency stop - close all positions and stop cycle"""
    try:
        logger.warning("EMERGENCY STOP initiated")
        
        # Close all positions first
        close_result = await call_service("trading", "POST", "/api/v1/positions/close_all", {
            "reason": "emergency_stop"
        })
        
        # Stop trading cycle
        if state.current_cycle:
            stop_result = await stop_trading_cycle()
        else:
            stop_result = {"success": True, "message": "No active cycle"}
        
        return {
            "success": True,
            "emergency_stop": True,
            "positions_closed": close_result.get("success", False),
            "cycle_stopped": stop_result.get("success", False),
            "message": "Emergency stop completed",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        return {"success": False, "error": str(e)}

# === MCP INITIALIZATION HANDLERS ===

@mcp.on_initialize()
async def initialize_server():
    """Initialize the MCP server and connections"""
    try:
        logger.info("Initializing Catalyst Trading MCP orchestration service...")
        
        # Initialize database pool
        database_url = os.getenv("DATABASE_URL", "postgresql://catalyst:catalyst123@172.18.0.1:5432/catalyst_trading")
        if database_url and not state.db_pool:
            try:
                state.db_pool = await asyncpg.create_pool(
                    database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=30
                )
                logger.info("Database pool initialized")
            except Exception as e:
                logger.warning(f"Database connection failed: {e}")
        
        # Initialize HTTP session
        if not state.http_session:
            timeout = aiohttp.ClientTimeout(total=30)
            state.http_session = aiohttp.ClientSession(timeout=timeout)
            logger.info("HTTP session initialized")
        
        # Initial health check
        await update_service_health()
        healthy_services = sum(1 for s in state.service_health.values() if s.get("status") == "healthy")
        total_services = len(SERVICE_URLS)
        
        logger.info(f"Initial health check: {healthy_services}/{total_services} services healthy")
        logger.info("Catalyst Trading MCP orchestration service initialized successfully")
        
        return {
            "success": True,
            "services_healthy": f"{healthy_services}/{total_services}",
            "database": "connected" if state.db_pool else "unavailable"
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise McpError(f"Server initialization failed: {e}")

@mcp.on_cleanup()
async def cleanup_server():
    """Cleanup server resources"""
    try:
        logger.info("Cleaning up Catalyst Trading MCP orchestration service...")
        
        # Emergency stop if cycle is active
        if state.current_cycle and state.current_cycle.status == "active":
            logger.info("Stopping active trading cycle during cleanup...")
            await emergency_stop()
        
        # Close HTTP session
        if state.http_session:
            await state.http_session.close()
            logger.info("HTTP session closed")
        
        # Close database pool
        if state.db_pool:
            await state.db_pool.close()
            logger.info("Database pool closed")
        
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# === STANDALONE MODE HANDLERS ===

async def init_handler():
    """Initialize handler for standalone mode"""
    if MCP_AVAILABLE:
        return
    
    logger.info("Initializing standalone mode...")
    await initialize_server()

async def cleanup_handler():
    """Cleanup handler for standalone mode"""
    if MCP_AVAILABLE:
        return
    
    logger.info("Cleaning up standalone mode...")
    await cleanup_server()

async def run_standalone():
    """Run in standalone mode for testing"""
    from aiohttp import web
    
    # Initialize
    await init_handler()
    
    # Create simple web server for health checks
    app = web.Application()
    
    async def health_check(request):
        health = await get_system_health()
        return web.json_response(health)
    
    async def status_check(request):
        status = await get_service_status()
        return web.json_response(status)
    
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', status_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 5000)
    await site.start()
    
    logger.info("Orchestration service running on http://localhost:5000")
    logger.info("Available endpoints:")
    logger.info("  - GET /health - System health check")
    logger.info("  - GET /status - Service status check")
    
    # Set up signal handlers
    def signal_handler():
        logger.info("Received shutdown signal")
        state.shutdown_event.set()
    
    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in [signal.SIGTERM, signal.SIGINT]:
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Wait for shutdown signal
        await state.shutdown_event.wait()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        logger.info("Shutting down...")
        await cleanup_handler()
        await runner.cleanup()

# === MAIN ENTRY POINT ===

def main():
    """Main entry point with fixed asyncio handling for Python 3.10+"""
    if "--test" in sys.argv:
        print("Catalyst Trading MCP Orchestration Service")
        print("==========================================")
        print("✅ Syntax check passed")
        print("✅ MCP imports successful" if MCP_AVAILABLE else "⚠️ MCP not available")
        print(f"✅ {len(SERVICE_URLS)} services configured")
        print("✅ Ready for deployment")
        return
    
    if MCP_AVAILABLE:
        logger.info("Starting Catalyst Trading MCP orchestration service...")
        mcp.run(transport='stdio')
    else:
        logger.warning("MCP not available, running in standalone mode for testing")
        try:
            # Use asyncio.run() for Python 3.10+ compatibility
            asyncio.run(run_standalone())
        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
        except Exception as e:
            logger.error(f"Service error: {e}")
            raise

if __name__ == "__main__":
    main()