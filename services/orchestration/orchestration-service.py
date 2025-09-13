#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 4.1.0
Last Updated: 2025-08-31
Purpose: MCP orchestration service for Claude interface and workflow coordination

REVISION HISTORY:
v4.1.0 (2025-08-31) - Complete rewrite for FastMCP compliance
- Hierarchical URI structure for resources
- Context parameters in all functions
- Proper error handling with McpError
- REST client integration for internal services
- Redis pub/sub for real-time events

Description of Service:
Primary MCP interface coordinating all trading system components through:
1. Hierarchical resource exposure for system state
2. Tool-based workflow orchestration
3. Event streaming for real-time updates
4. REST API integration with internal services
"""

from fastmcp import FastMCP, Context
from fastmcp.exceptions import McpError
import asyncio
import aiohttp
import aioredis
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from enum import Enum

# Initialize FastMCP server
mcp = FastMCP("catalyst-orchestration")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orchestration")

# Service configuration
SERVICE_URLS = {
    "scanner": os.getenv("SCANNER_URL", "http://localhost:5001"),
    "pattern": os.getenv("PATTERN_URL", "http://localhost:5002"),
    "technical": os.getenv("TECHNICAL_URL", "http://localhost:5003"),
    "trading": os.getenv("TRADING_URL", "http://localhost:5005"),
    "news": os.getenv("NEWS_URL", "http://localhost:5008"),
    "reporting": os.getenv("REPORTING_URL", "http://localhost:5009")
}

# Trading modes
class TradingMode(Enum):
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    CONSERVATIVE = "conservative"

# Workflow states
class WorkflowState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    MONITORING = "monitoring"

@dataclass
class TradingCycle:
    """Trading cycle configuration"""
    cycle_id: str
    mode: TradingMode
    status: str
    scan_frequency: int
    max_positions: int
    risk_level: float
    started_at: datetime
    configuration: Dict[str, Any]

# Global state management
class SystemState:
    def __init__(self):
        self.current_cycle: Optional[TradingCycle] = None
        self.workflow_state: WorkflowState = WorkflowState.IDLE
        self.active_positions: List[Dict] = []
        self.pending_signals: List[Dict] = []
        self.service_health: Dict[str, Dict] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None

state = SystemState()

# === INITIALIZATION ===

#@mcp.init()
async def initialize(ctx: Context):
    """Initialize orchestration service"""
    logger.info("Initializing Catalyst Trading Orchestration Service")
    
    try:
        # Initialize HTTP session for REST calls
        state.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=100)
        )
        
        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        state.redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Check service health
        await check_all_services_health()
        
        logger.info("Orchestration service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize orchestration service: {e}")
        raise McpError(f"Initialization failed: {str(e)}")

###@mcp.on_cleanup()
async def cleanup(ctx: Context):
    """Clean up resources"""
    logger.info("Cleaning up orchestration service")
    
    if state.http_session:
        await state.http_session.close()
    
    if state.redis_client:
        await state.redis_client.close()

# === HIERARCHICAL RESOURCES ===

# System Resources
@mcp.resource("http://system/health")
async def get_system_health(ctx: Context) -> Dict:
    """Get overall system health status"""
    return {
        "status": "healthy" if all(s.get("healthy", False) for s in state.service_health.values()) else "degraded",
        "services": state.service_health,
        "timestamp": datetime.now().isoformat()
    }

@mcp.resource("http://system/configuration")
async def get_system_configuration(ctx: Context) -> Dict:
    """Get current system configuration"""
    return {
        "trading_modes": [mode.value for mode in TradingMode],
        "service_urls": SERVICE_URLS,
        "max_positions": 5,
        "default_risk_level": 0.02,
        "scan_frequencies": {
            "aggressive": 60,
            "normal": 300,
            "conservative": 900
        }
    }

# Trading Resources
@mcp.resource("http://trading/cycle/current")
async def get_current_cycle(ctx: Context) -> Dict:
    """Get current trading cycle status"""
    if not state.current_cycle:
        return {"active": False, "message": "No active trading cycle"}
    
    return {
        "active": True,
        "cycle": asdict(state.current_cycle),
        "workflow_state": state.workflow_state.value,
        "positions_count": len(state.active_positions),
        "pending_signals": len(state.pending_signals)
    }

@mcp.resource("trading/positions/active")
async def get_active_positions(ctx: Context) -> Dict:
    """Get all active trading positions"""
    return {
        "positions": state.active_positions,
        "total": len(state.active_positions),
        "timestamp": datetime.now().isoformat()
    }

@mcp.resource("trading/signals/pending")
async def get_pending_signals(ctx: Context) -> Dict:
    """Get pending trading signals awaiting execution"""
    return {
        "signals": state.pending_signals,
        "total": len(state.pending_signals),
        "timestamp": datetime.now().isoformat()
    }

# Market Resources
@mcp.resource("market/scan/latest")
async def get_latest_scan(ctx: Context) -> Dict:
    """Get results from the latest market scan"""
    try:
        async with state.http_session.get(f"{SERVICE_URLS['scanner']}/api/v1/scan/latest") as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise McpError(f"Scanner service error: {resp.status}")
    except Exception as e:
        logger.error(f"Failed to get latest scan: {e}")
        raise McpError(f"Failed to retrieve scan results: {str(e)}")

@mcp.resource("market/news/catalysts")
async def get_news_catalysts(ctx: Context) -> Dict:
    """Get current news catalysts"""
    try:
        async with state.http_session.get(f"{SERVICE_URLS['news']}/api/v1/catalysts") as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise McpError(f"News service error: {resp.status}")
    except Exception as e:
        logger.error(f"Failed to get news catalysts: {e}")
        raise McpError(f"Failed to retrieve catalysts: {str(e)}")

# Performance Resources
@mcp.resource("performance/daily")
async def get_daily_performance(ctx: Context) -> Dict:
    """Get today's trading performance"""
    try:
        async with state.http_session.get(f"{SERVICE_URLS['reporting']}/api/v1/performance/daily") as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise McpError(f"Reporting service error: {resp.status}")
    except Exception as e:
        logger.error(f"Failed to get daily performance: {e}")
        raise McpError(f"Failed to retrieve performance: {str(e)}")

@mcp.resource("performance/cycle/{cycle_id}")
async def get_cycle_performance(ctx: Context, cycle_id: str) -> Dict:
    """Get performance for a specific trading cycle"""
    try:
        async with state.http_session.get(
            f"{SERVICE_URLS['reporting']}/api/v1/performance/cycle/{cycle_id}"
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                raise McpError(f"Cycle {cycle_id} not found")
            else:
                raise McpError(f"Reporting service error: {resp.status}")
    except Exception as e:
        logger.error(f"Failed to get cycle performance: {e}")
        raise McpError(f"Failed to retrieve cycle performance: {str(e)}")

# === TOOLS (ACTIONS) ===

@mcp.tool()
async def start_trading_cycle(
    ctx: Context,
    mode: str = "normal",
    max_positions: int = 5,
    risk_level: float = 0.02
) -> Dict:
    """Start a new trading cycle with specified parameters"""
    
    # Validate inputs
    if mode not in [m.value for m in TradingMode]:
        raise McpError(f"Invalid mode: {mode}. Must be one of {[m.value for m in TradingMode]}")
    
    if not 1 <= max_positions <= 10:
        raise McpError("max_positions must be between 1 and 10")
    
    if not 0.001 <= risk_level <= 0.05:
        raise McpError("risk_level must be between 0.001 and 0.05")
    
    # Check if cycle already active
    if state.current_cycle and state.current_cycle.status == "active":
        raise McpError("A trading cycle is already active. Stop it first.")
    
    # Create new cycle
    cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    scan_frequencies = {
        "aggressive": 60,
        "normal": 300,
        "conservative": 900
    }
    
    state.current_cycle = TradingCycle(
        cycle_id=cycle_id,
        mode=TradingMode(mode),
        status="active",
        scan_frequency=scan_frequencies[mode],
        max_positions=max_positions,
        risk_level=risk_level,
        started_at=datetime.now(),
        configuration={
            "mode": mode,
            "max_positions": max_positions,
            "risk_level": risk_level
        }
    )
    
    state.workflow_state = WorkflowState.SCANNING
    
    # Start workflow orchestration
    asyncio.create_task(orchestrate_workflow())
    
    # Publish event
    await publish_event("cycle.started", asdict(state.current_cycle))
    
    logger.info(f"Started trading cycle: {cycle_id}")
    
    return {
        "success": True,
        "cycle_id": cycle_id,
        "mode": mode,
        "message": f"Trading cycle started successfully"
    }

@mcp.tool()
async def stop_trading_cycle(ctx: Context, close_positions: bool = False) -> Dict:
    """Stop the current trading cycle"""
    
    if not state.current_cycle:
        raise McpError("No active trading cycle to stop")
    
    cycle_id = state.current_cycle.cycle_id
    
    # Update cycle status
    state.current_cycle.status = "stopped"
    state.workflow_state = WorkflowState.IDLE
    
    # Close positions if requested
    positions_closed = []
    if close_positions and state.active_positions:
        for position in state.active_positions:
            try:
                async with state.http_session.post(
                    f"{SERVICE_URLS['trading']}/api/v1/positions/close",
                    json={"position_id": position["id"]}
                ) as resp:
                    if resp.status == 200:
                        positions_closed.append(position["id"])
            except Exception as e:
                logger.error(f"Failed to close position {position['id']}: {e}")
    
    # Publish event
    await publish_event("cycle.stopped", {
        "cycle_id": cycle_id,
        "positions_closed": positions_closed
    })
    
    # Clear state
    state.current_cycle = None
    state.pending_signals = []
    
    logger.info(f"Stopped trading cycle: {cycle_id}")
    
    return {
        "success": True,
        "cycle_id": cycle_id,
        "positions_closed": len(positions_closed),
        "message": "Trading cycle stopped successfully"
    }

@mcp.tool()
async def execute_signal(ctx: Context, signal_id: str) -> Dict:
    """Execute a specific trading signal"""
    
    # Find signal
    signal = next((s for s in state.pending_signals if s["id"] == signal_id), None)
    if not signal:
        raise McpError(f"Signal {signal_id} not found in pending signals")
    
    # Execute via trading service
    try:
        async with state.http_session.post(
            f"{SERVICE_URLS['trading']}/api/v1/orders/execute",
            json=signal
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                
                # Remove from pending
                state.pending_signals = [s for s in state.pending_signals if s["id"] != signal_id]
                
                # Add to active positions
                if result.get("position"):
                    state.active_positions.append(result["position"])
                
                # Publish event
                await publish_event("signal.executed", result)
                
                return {
                    "success": True,
                    "signal_id": signal_id,
                    "order_id": result.get("order_id"),
                    "message": "Signal executed successfully"
                }
            else:
                error_msg = await resp.text()
                raise McpError(f"Trading service error: {error_msg}")
                
    except Exception as e:
        logger.error(f"Failed to execute signal {signal_id}: {e}")
        raise McpError(f"Failed to execute signal: {str(e)}")

@mcp.tool()
async def trigger_market_scan(ctx: Context) -> Dict:
    """Manually trigger a market scan"""
    
    if not state.current_cycle:
        raise McpError("No active trading cycle. Start a cycle first.")
    
    state.workflow_state = WorkflowState.SCANNING
    
    try:
        # Trigger scan via scanner service
        async with state.http_session.post(
            f"{SERVICE_URLS['scanner']}/api/v1/scan/trigger",
            json={
                "cycle_id": state.current_cycle.cycle_id,
                "mode": state.current_cycle.mode.value
            }
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                
                # Publish event
                await publish_event("scan.triggered", result)
                
                return {
                    "success": True,
                    "scan_id": result.get("scan_id"),
                    "candidates_found": result.get("candidates_count", 0),
                    "message": "Market scan triggered successfully"
                }
            else:
                error_msg = await resp.text()
                raise McpError(f"Scanner service error: {error_msg}")
                
    except Exception as e:
        logger.error(f"Failed to trigger scan: {e}")
        raise McpError(f"Failed to trigger scan: {str(e)}")

@mcp.tool()
async def adjust_position_stop_loss(
    ctx: Context,
    position_id: str,
    new_stop_price: float
) -> Dict:
    """Adjust stop loss for an active position"""
    
    # Find position
    position = next((p for p in state.active_positions if p["id"] == position_id), None)
    if not position:
        raise McpError(f"Position {position_id} not found")
    
    try:
        async with state.http_session.put(
            f"{SERVICE_URLS['trading']}/api/v1/positions/{position_id}/stop_loss",
            json={"stop_price": new_stop_price}
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                
                # Update local state
                position["stop_loss"] = new_stop_price
                
                # Publish event
                await publish_event("position.adjusted", {
                    "position_id": position_id,
                    "adjustment": "stop_loss",
                    "new_value": new_stop_price
                })
                
                return {
                    "success": True,
                    "position_id": position_id,
                    "new_stop_loss": new_stop_price,
                    "message": "Stop loss adjusted successfully"
                }
            else:
                error_msg = await resp.text()
                raise McpError(f"Trading service error: {error_msg}")
                
    except Exception as e:
        logger.error(f"Failed to adjust stop loss: {e}")
        raise McpError(f"Failed to adjust stop loss: {str(e)}")

# === HELPER FUNCTIONS ===

async def check_all_services_health():
    """Check health of all services"""
    for service_name, url in SERVICE_URLS.items():
        try:
            async with state.http_session.get(
                f"{url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    state.service_health[service_name] = {
                        "healthy": True,
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

async def orchestrate_workflow():
    """Main workflow orchestration loop"""
    logger.info(f"Starting workflow orchestration for cycle {state.current_cycle.cycle_id}")
    
    while state.current_cycle and state.current_cycle.status == "active":
        try:
            # Execute workflow based on current state
            if state.workflow_state == WorkflowState.SCANNING:
                await execute_scanning_phase()
                
            elif state.workflow_state == WorkflowState.ANALYZING:
                await execute_analysis_phase()
                
            elif state.workflow_state == WorkflowState.EXECUTING:
                await execute_trading_phase()
                
            elif state.workflow_state == WorkflowState.MONITORING:
                await execute_monitoring_phase()
            
            # Wait based on scan frequency
            await asyncio.sleep(state.current_cycle.scan_frequency)
            
        except Exception as e:
            logger.error(f"Workflow orchestration error: {e}")
            await asyncio.sleep(30)  # Wait before retry

async def execute_scanning_phase():
    """Execute the scanning phase of the workflow"""
    logger.info("Executing scanning phase")
    
    try:
        # Trigger market scan
        async with state.http_session.post(
            f"{SERVICE_URLS['scanner']}/api/v1/scan",
            json={
                "cycle_id": state.current_cycle.cycle_id,
                "mode": state.current_cycle.mode.value,
                "limit": 100  # Initial universe
            }
        ) as resp:
            if resp.status == 200:
                scan_result = await resp.json()
                
                # Move to analysis if candidates found
                if scan_result.get("candidates_count", 0) > 0:
                    state.workflow_state = WorkflowState.ANALYZING
                else:
                    state.workflow_state = WorkflowState.MONITORING
                    
    except Exception as e:
        logger.error(f"Scanning phase error: {e}")

async def execute_analysis_phase():
    """Execute the analysis phase of the workflow"""
    logger.info("Executing analysis phase")
    
    try:
        # Get scan results
        async with state.http_session.get(
            f"{SERVICE_URLS['scanner']}/api/v1/scan/latest"
        ) as resp:
            if resp.status == 200:
                scan_data = await resp.json()
                candidates = scan_data.get("candidates", [])[:20]  # Top 20
                
                # Analyze each candidate
                signals = []
                for candidate in candidates:
                    # Pattern detection
                    pattern_signal = await analyze_patterns(candidate["symbol"])
                    
                    # Technical analysis
                    technical_signal = await analyze_technicals(candidate["symbol"])
                    
                    # Combine signals
                    if pattern_signal and technical_signal:
                        signals.append({
                            "id": f"sig_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{candidate['symbol']}",
                            "symbol": candidate["symbol"],
                            "pattern": pattern_signal,
                            "technical": technical_signal,
                            "confidence": (pattern_signal["confidence"] + technical_signal["confidence"]) / 2,
                            "timestamp": datetime.now().isoformat()
                        })
                
                # Update pending signals (top 5)
                state.pending_signals = sorted(
                    signals,
                    key=lambda x: x["confidence"],
                    reverse=True
                )[:5]
                
                # Move to execution if signals found
                if state.pending_signals:
                    state.workflow_state = WorkflowState.EXECUTING
                else:
                    state.workflow_state = WorkflowState.MONITORING
                    
    except Exception as e:
        logger.error(f"Analysis phase error: {e}")

async def execute_trading_phase():
    """Execute the trading phase of the workflow"""
    logger.info("Executing trading phase")
    
    try:
        # Check position limits
        if len(state.active_positions) >= state.current_cycle.max_positions:
            logger.info("Max positions reached, skipping execution")
            state.workflow_state = WorkflowState.MONITORING
            return
        
        # Execute top signals
        for signal in state.pending_signals[:state.current_cycle.max_positions - len(state.active_positions)]:
            try:
                # Execute signal
                async with state.http_session.post(
                    f"{SERVICE_URLS['trading']}/api/v1/orders/execute",
                    json={
                        "signal": signal,
                        "risk_level": state.current_cycle.risk_level
                    }
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        
                        # Add to active positions
                        if result.get("position"):
                            state.active_positions.append(result["position"])
                            
                        # Remove from pending
                        state.pending_signals.remove(signal)
                        
            except Exception as e:
                logger.error(f"Failed to execute signal {signal['id']}: {e}")
        
        state.workflow_state = WorkflowState.MONITORING
        
    except Exception as e:
        logger.error(f"Trading phase error: {e}")

async def execute_monitoring_phase():
    """Execute the monitoring phase of the workflow"""
    logger.info("Executing monitoring phase")
    
    try:
        # Monitor active positions
        for position in state.active_positions[:]:  # Copy to allow modification
            try:
                # Check position status
                async with state.http_session.get(
                    f"{SERVICE_URLS['trading']}/api/v1/positions/{position['id']}"
                ) as resp:
                    if resp.status == 200:
                        position_data = await resp.json()
                        
                        # Update local state
                        position.update(position_data)
                        
                        # Remove if closed
                        if position_data.get("status") == "closed":
                            state.active_positions.remove(position)
                            
            except Exception as e:
                logger.error(f"Failed to monitor position {position['id']}: {e}")
        
        # Return to scanning
        state.workflow_state = WorkflowState.SCANNING
        
    except Exception as e:
        logger.error(f"Monitoring phase error: {e}")

async def analyze_patterns(symbol: str) -> Optional[Dict]:
    """Analyze patterns for a symbol"""
    try:
        async with state.http_session.post(
            f"{SERVICE_URLS['pattern']}/api/v1/analyze",
            json={"symbol": symbol}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        logger.error(f"Pattern analysis failed for {symbol}: {e}")
    return None

async def analyze_technicals(symbol: str) -> Optional[Dict]:
    """Analyze technical indicators for a symbol"""
    try:
        async with state.http_session.post(
            f"{SERVICE_URLS['technical']}/api/v1/analyze",
            json={"symbol": symbol}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        logger.error(f"Technical analysis failed for {symbol}: {e}")
    return None

async def publish_event(event_type: str, data: Dict):
    """Publish event to Redis pub/sub"""
    if state.redis_client:
        try:
            await state.redis_client.publish(
                f"catalyst.events.{event_type}",
                json.dumps({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
            )
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    print("=" * 60)
    print("🎩 Catalyst Trading MCP - Orchestration Service v4.1")
    print("=" * 60)
    print("Status: Starting...")
    print(f"Port: 5000")
    print(f"Protocol: MCP (Model Context Protocol)")
    print("=" * 60)
    
    try:
        mcp.run(port=5000)
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("Service stopped by user")
        print("=" * 60)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
