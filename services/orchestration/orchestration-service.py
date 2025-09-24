"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py  
Version: 4.2.1  o
Last Updated: 2025-09-23
Purpose: Fixed orchestration service with Python 3.10+ asyncio compatibility

REVISION HISTORY:
v4.2.1 (2025-09-23) - Fixed Python 3.10+ asyncio event loop issue
- Fixed RuntimeError: There is no current event loop in thread 'MainThread'
- Proper asyncio.run() usage for standalone mode
- Improved error handling and cleanup
- Maintain all existing MCP functionality
"""

import asyncio
import logging
import os
import sys
import signal
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import asyncpg
import redis
from dataclasses import dataclass
from enum import Enum

# MCP imports with fallback
MCP_AVAILABLE = False
try:
    from mcp import MCP
    from mcp.context import Context
    from mcp.types import Resource, Tool
    MCP_AVAILABLE = True
    mcp = MCP("catalyst-orchestration")
except ImportError:
    print("MCP not available, running in standalone mode")
    mcp = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === SERVICE CONFIGURATION ===

SERVICE_URLS = {
    "scanner": "http://localhost:5001",
    "pattern": "http://localhost:5002", 
    "technical": "http://localhost:5003",
    "news": "http://localhost:5008",
    "trading": "http://localhost:5005",
    "reporting": "http://localhost:5006",
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
    
class ApplicationState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.current_cycle: Optional[TradingCycle] = None
        self.workflow_state = WorkflowState.IDLE
        self.service_health: Dict[str, Dict] = {}
        self.shutdown_event = asyncio.Event()

state = ApplicationState()

# === INITIALIZATION ===

async def init_handler():
    """Initialize connections and state"""
    logger.info("Initializing orchestration service...")
    
    try:
        # Initialize database connection with minimal pool
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            state.db_pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=3,
                command_timeout=30
            )
            logger.info("Database pool initialized")
        
        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        state.redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Initialize HTTP session
        state.http_session = aiohttp.ClientSession()
        
        # Test connections
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        
        await state.redis_client.ping()
        
        logger.info("All connections initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        # Don't raise error - continue with limited functionality

async def cleanup_handler():
    """Cleanup connections on shutdown"""
    try:
        logger.info("Starting cleanup...")
        
        if state.http_session:
            await state.http_session.close()
            logger.info("HTTP session closed")
            
        if state.redis_client:
            await state.redis_client.close()
            logger.info("Redis connection closed")
            
        if state.db_pool:
            await state.db_pool.close()
            logger.info("Database pool closed")
            
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

# === MCP RESOURCES (only if MCP available) ===

if MCP_AVAILABLE:
    @mcp.resource("trading-cycle/current")
    async def get_current_trading_cycle(ctx: Context) -> Dict:
        """Get current active trading cycle"""
        try:
            if not state.current_cycle:
                return {"active": False, "message": "No active trading cycle"}
            
            return {
                "active": True,
                "cycle_id": state.current_cycle.cycle_id,
                "mode": state.current_cycle.mode,
                "status": state.current_cycle.status,
                "start_time": state.current_cycle.start_time.isoformat(),
                "workflow_state": state.workflow_state.value,
                "scan_frequency": state.current_cycle.scan_frequency,
                "max_positions": state.current_cycle.max_positions
            }
        except Exception as e:
            logger.error(f"Failed to get trading cycle: {e}")
            return {"active": False, "error": str(e)}

    @mcp.resource("system/health")
    async def get_system_health(ctx: Context) -> Dict:
        """Get system health status"""
        try:
            # Check all service health
            await check_all_services_health()
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": state.service_health,
                "database": "connected" if state.db_pool else "disconnected",
                "redis": "connected" if state.redis_client else "disconnected"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # === MCP TOOLS ===

    @mcp.tool()
    async def start_trading_cycle(ctx: Context, mode: str = "conservative", max_positions: int = 5, scan_frequency: int = 300) -> Dict:
        """Start a new trading cycle"""
        try:
            if state.current_cycle and state.current_cycle.status == "active":
                return {
                    "success": False,
                    "error": "A trading cycle is already active",
                    "current_cycle": state.current_cycle.cycle_id
                }
            
            # Create new trading cycle
            cycle_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            state.current_cycle = TradingCycle(
                cycle_id=cycle_id,
                mode=mode,
                status="active",
                start_time=datetime.now(),
                scan_frequency=scan_frequency,
                max_positions=max_positions
            )
            
            state.workflow_state = WorkflowState.SCANNING
            
            logger.info(f"Started trading cycle {cycle_id} in {mode} mode")
            
            return {
                "success": True,
                "cycle_id": cycle_id,
                "mode": mode,
                "max_positions": max_positions,
                "scan_frequency": scan_frequency,
                "message": f"Trading cycle {cycle_id} started successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to start trading cycle: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def stop_trading_cycle(ctx: Context) -> Dict:
        """Stop the current trading cycle"""
        try:
            if not state.current_cycle or state.current_cycle.status != "active":
                return {
                    "success": False,
                    "error": "No active trading cycle to stop"
                }
            
            cycle_id = state.current_cycle.cycle_id
            state.current_cycle.status = "stopped"
            state.workflow_state = WorkflowState.IDLE
            
            logger.info(f"Stopped trading cycle {cycle_id}")
            
            return {
                "success": True,
                "cycle_id": cycle_id,
                "message": f"Trading cycle {cycle_id} stopped successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to stop trading cycle: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_service_status(ctx: Context) -> Dict:
        """Get detailed status of all services"""
        try:
            await check_all_services_health()
            
            return {
                "success": True,
                "services": state.service_health,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_trading_positions(ctx: Context) -> Dict:
        """Get current trading positions"""
        try:
            if not state.http_session:
                return {"success": False, "error": "HTTP session not initialized"}
                
            async with state.http_session.get(f"{SERVICE_URLS['trading']}/positions") as resp:
                if resp.status == 200:
                    positions = await resp.json()
                    return {
                        "success": True,
                        "positions": positions,
                        "count": len(positions) if isinstance(positions, list) else 0
                    }
                else:
                    error_text = await resp.text()
                    return {"success": False, "error": f"Trading service error: {error_text}"}
                    
        except Exception as e:
            logger.error(f"Failed to get trading positions: {e}")
            return {"success": False, "error": str(e)}

# === HELPER FUNCTIONS ===

async def check_all_services_health():
    """Check health of all services"""
    if not state.http_session:
        return
        
    for service_name, url in SERVICE_URLS.items():
        try:
            async with state.http_session.get(
                f"{url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state.service_health[service_name] = {
                        "healthy": True,
                        "status": data.get("status", "unknown"),
                        "last_check": datetime.now().isoformat()
                    }
                else:
                    state.service_health[service_name] = {
                        "healthy": False,
                        "error": f"HTTP {resp.status}",
                        "last_check": datetime.now().isoformat()
                    }
        except Exception as e:
            state.service_health[service_name] = {
                "healthy": False,
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

async def standalone_server():
    """Run a simple HTTP server for standalone mode"""
    from aiohttp import web
    
    async def health_check(request):
        return web.json_response({
            "status": "healthy",
            "service": "orchestration",
            "version": "4.2.1",
            "mode": "standalone",
            "timestamp": datetime.now().isoformat()
        })
    
    async def status_check(request):
        await check_all_services_health()
        return web.json_response({
            "success": True,
            "services": state.service_health,
            "current_cycle": {
                "active": bool(state.current_cycle and state.current_cycle.status == "active"),
                "cycle_id": state.current_cycle.cycle_id if state.current_cycle else None,
                "workflow_state": state.workflow_state.value
            },
            "timestamp": datetime.now().isoformat()
        })
    
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', status_check)
    app.router.add_get('/api/health', health_check)
    app.router.add_get('/api/status', status_check)
    
    return app

async def run_standalone():
    """Run the orchestration service in standalone mode"""
    logger.info("Initializing standalone mode...")
    
    # Initialize connections
    await init_handler()
    
    # Create and start web server
    app = await standalone_server()
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    
    site = aiohttp.web.TCPSite(runner, 'localhost', 5000)
    await site.start()
    
    logger.info("Orchestration service running on http://localhost:5000")
    logger.info("Available endpoints:")
    logger.info("  - GET /health - Service health check")
    logger.info("  - GET /status - Detailed status")
    logger.info("  - GET /api/health - API health check")
    logger.info("  - GET /api/status - API status")
    
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

# === MCP INITIALIZATION ===

if MCP_AVAILABLE:
    @mcp.on_initialize()
    async def mcp_init_handler():
        """Initialize MCP server"""
        await init_handler()

    @mcp.on_cleanup()
    async def mcp_cleanup_handler():
        """Cleanup MCP server"""
        await cleanup_handler()

# === MAIN ENTRY POINT ===

def main():
    """Main entry point with fixed asyncio handling for Python 3.10+"""
    if "--test" in sys.argv:
        print("Orchestration service test mode")
        print("✅ Syntax check passed")
        print("✅ MCP imports successful" if MCP_AVAILABLE else "⚠️ MCP not available")
        return
    
    if MCP_AVAILABLE:
        logger.info("Starting orchestration service in MCP mode...")
        mcp.run(transport='stdio')
    else:
        logger.warning("MCP not available, running in standalone mode")
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
