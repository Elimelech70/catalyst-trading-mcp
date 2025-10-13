#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 5.1.0
Last Updated: 2025-10-13
Purpose: MCP orchestration with normalized schema and rigorous error handling

REVISION HISTORY:
v5.1.0 (2025-10-13) - Production Error Handling Upgrade
- NO Unicode emojis (ASCII only)
- Specific exception types (ValueError, aiohttp.ClientError, McpError)
- Structured logging with exc_info
- McpError for MCP tool failures (not generic Exception)
- No silent failures - all errors raised properly
- Success/failure tracking for service calls

v5.0.0 (2025-10-06) - Normalized schema awareness

Description of Service:
MCP server orchestrating all trading services with proper error handling.
Coordinates between normalized services using security_id.
"""

from fastmcp import FastMCP, Context
from fastmcp.exceptions import McpError
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass
import aiohttp
import asyncio
import json
import os
import logging
import signal

SERVICE_NAME = "orchestration"
SERVICE_VERSION = "5.1.0"
SERVICE_PORT = 5000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(SERVICE_NAME)

class Config:
    SCANNER_URL = os.getenv("SCANNER_URL", "http://scanner:5001")
    PATTERN_URL = os.getenv("PATTERN_URL", "http://pattern:5002")
    TECHNICAL_URL = os.getenv("TECHNICAL_URL", "http://technical:5003")
    RISK_URL = os.getenv("RISK_URL", "http://risk-manager:5004")
    TRADING_URL = os.getenv("TRADING_URL", "http://trading:5005")
    NEWS_URL = os.getenv("NEWS_URL", "http://news:5008")
    REPORTING_URL = os.getenv("REPORTING_URL", "http://reporting:5009")

SERVICE_URLS = {
    "scanner": Config.SCANNER_URL,
    "pattern": Config.PATTERN_URL,
    "technical": Config.TECHNICAL_URL,
    "risk_manager": Config.RISK_URL,
    "trading": Config.TRADING_URL,
    "news": Config.NEWS_URL,
    "reporting": Config.REPORTING_URL
}

@dataclass
class TradingCycle:
    cycle_id: str
    status: str
    mode: str
    started_at: datetime
    aggressiveness: float
    max_positions: int

class ServiceState:
    def __init__(self):
        self.current_cycle: Optional[TradingCycle] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.shutdown_event = asyncio.Event()

state = ServiceState()

mcp = FastMCP("catalyst-orchestration")

async def call_service(service: str, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """
    Call internal service with proper error handling.
    
    Raises:
        ValueError: If service name invalid
        aiohttp.ClientError: If network/API error
        RuntimeError: If unexpected error
    """
    try:
        if service not in SERVICE_URLS:
            raise ValueError(f"Unknown service: {service}")
        
        url = f"{SERVICE_URLS[service]}{endpoint}"
        
        if not state.http_session:
            raise RuntimeError("HTTP session not initialized")
        
        if method.upper() == "GET":
            async with state.http_session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                return await resp.json()
        elif method.upper() == "POST":
            async with state.http_session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                return await resp.json()
        else:
            raise ValueError(f"Unsupported method: {method}")
            
    except ValueError:
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Service call failed: {service}{endpoint}: {e}", exc_info=True,
                    extra={'service': service, 'endpoint': endpoint, 'error_type': 'network'})
        raise
    except Exception as e:
        logger.critical(f"Unexpected error calling {service}: {e}", exc_info=True,
                       extra={'service': service, 'error_type': 'unexpected'})
        raise RuntimeError(f"Service call failed: {e}")

@mcp.resource("trading-cycle/current")
async def get_current_cycle(ctx: Context) -> Dict:
    """Get current trading cycle status"""
    try:
        if not state.current_cycle:
            return {"status": "idle", "message": "No active trading cycle"}
        
        return {
            "cycle_id": state.current_cycle.cycle_id,
            "status": state.current_cycle.status,
            "mode": state.current_cycle.mode,
            "started_at": state.current_cycle.started_at.isoformat(),
            "aggressiveness": state.current_cycle.aggressiveness,
            "max_positions": state.current_cycle.max_positions
        }
    except Exception as e:
        logger.error(f"Error getting current cycle: {e}", exc_info=True, extra={'error_type': 'resource'})
        return {"error": str(e)}

@mcp.resource("system/health")
async def get_system_health(ctx: Context) -> Dict:
    """Get system health across all services"""
    try:
        health_checks = {}
        failed_services = []
        
        for service_name, url in SERVICE_URLS.items():
            try:
                result = await call_service(service_name, "GET", "/health")
                health_checks[service_name] = result.get("status", "unknown")
            except Exception as e:
                logger.warning(f"Health check failed for {service_name}: {e}",
                             extra={'service': service_name, 'error_type': 'health_check'})
                health_checks[service_name] = "unhealthy"
                failed_services.append(service_name)
        
        overall_status = "healthy" if len(failed_services) == 0 else "degraded"
        
        return {
            "overall_status": overall_status,
            "services": health_checks,
            "failed_services": failed_services,
            "checked_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking system health: {e}", exc_info=True, extra={'error_type': 'resource'})
        return {"error": str(e)}

@mcp.tool()
async def start_trading_cycle(
    mode: str = "normal",
    aggressiveness: float = 0.5,
    max_positions: int = 5
) -> Dict:
    """
    Start a new trading cycle.
    
    Args:
        mode: Trading mode (aggressive/normal/conservative)
        aggressiveness: Risk level 0.0-1.0
        max_positions: Max concurrent positions
        
    Raises:
        McpError: If validation fails or cycle already active
    """
    try:
        # Validation
        if mode not in ["aggressive", "normal", "conservative"]:
            raise ValueError(f"Invalid mode: {mode}. Must be aggressive/normal/conservative")
        
        if not 0.0 <= aggressiveness <= 1.0:
            raise ValueError(f"Aggressiveness must be 0.0-1.0, got {aggressiveness}")
        
        if max_positions < 1 or max_positions > 10:
            raise ValueError(f"Max positions must be 1-10, got {max_positions}")
        
        # Check if cycle already active
        if state.current_cycle and state.current_cycle.status == "active":
            raise RuntimeError("Trading cycle already active")
        
        # Generate cycle ID
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create cycle in trading service
        result = await call_service("trading", "POST", "/api/v1/cycles", {
            "mode": mode,
            "aggressiveness": aggressiveness,
            "max_positions": max_positions
        })
        
        # Update state
        state.current_cycle = TradingCycle(
            cycle_id=result.get('cycle_id', cycle_id),
            status="active",
            mode=mode,
            started_at=datetime.now(),
            aggressiveness=aggressiveness,
            max_positions=max_positions
        )
        
        logger.info(f"Trading cycle started: {state.current_cycle.cycle_id}",
                   extra={'cycle_id': state.current_cycle.cycle_id, 'mode': mode})
        
        return {
            "success": True,
            "cycle_id": state.current_cycle.cycle_id,
            "mode": mode,
            "status": "active",
            "started_at": state.current_cycle.started_at.isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error starting cycle: {e}",
                    extra={'mode': mode, 'error_type': 'validation'})
        raise McpError("INVALID_PARAMETERS", str(e))
    except aiohttp.ClientError as e:
        logger.error(f"Service unavailable: {e}", exc_info=True,
                    extra={'error_type': 'service_unavailable'})
        raise McpError("SERVICE_UNAVAILABLE", "Cannot start cycle - trading service unavailable")
    except RuntimeError as e:
        logger.warning(f"Runtime error: {e}", extra={'error_type': 'runtime'})
        raise McpError("CYCLE_ALREADY_ACTIVE", str(e))
    except Exception as e:
        logger.critical(f"Unexpected error starting cycle: {e}", exc_info=True,
                       extra={'mode': mode, 'error_type': 'unexpected'})
        raise McpError("INTERNAL_ERROR", f"Failed to start trading cycle: {e}")

@mcp.tool()
async def scan_market(hours_back: int = 1) -> Dict:
    """
    Run market scanner to find trading candidates.
    
    Args:
        hours_back: Hours of data to scan
        
    Raises:
        McpError: If scan fails
    """
    try:
        if hours_back < 1 or hours_back > 24:
            raise ValueError(f"hours_back must be 1-24, got {hours_back}")
        
        # Call scanner service
        result = await call_service("scanner", "POST", "/api/v1/scan", {
            "hours_back": hours_back
        })
        
        candidates = result.get('candidates', [])
        
        logger.info(f"Market scan complete: {len(candidates)} candidates found",
                   extra={'candidates': len(candidates), 'hours_back': hours_back})
        
        return {
            "success": True,
            "candidates": len(candidates),
            "top_candidates": candidates[:5],
            "scanned_at": datetime.now().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'error_type': 'validation'})
        raise McpError("INVALID_PARAMETERS", str(e))
    except aiohttp.ClientError as e:
        logger.error(f"Scanner service unavailable: {e}", exc_info=True,
                    extra={'error_type': 'service_unavailable'})
        raise McpError("SERVICE_UNAVAILABLE", "Scanner service unavailable")
    except Exception as e:
        logger.critical(f"Unexpected error scanning: {e}", exc_info=True,
                       extra={'error_type': 'unexpected'})
        raise McpError("SCAN_FAILED", f"Market scan failed: {e}")

@mcp.tool()
async def analyze_symbol(symbol: str) -> Dict:
    """
    Run complete analysis on a symbol (technical + pattern).
    
    Args:
        symbol: Stock symbol to analyze
        
    Raises:
        McpError: If analysis fails
    """
    try:
        if not symbol or len(symbol) > 10:
            raise ValueError(f"Invalid symbol: {symbol}")
        
        symbol = symbol.upper()
        
        # Parallel calls to technical and pattern services
        technical_task = call_service("technical", "POST", "/api/v1/indicators/calculate", {"symbol": symbol})
        pattern_task = call_service("pattern", "POST", "/api/v1/patterns/detect", {"symbol": symbol})
        
        technical_result, pattern_result = await asyncio.gather(technical_task, pattern_task, return_exceptions=True)
        
        # Check for errors
        technical_failed = isinstance(technical_result, Exception)
        pattern_failed = isinstance(pattern_result, Exception)
        
        if technical_failed:
            logger.warning(f"Technical analysis failed for {symbol}: {technical_result}",
                          extra={'symbol': symbol, 'error_type': 'technical'})
        if pattern_failed:
            logger.warning(f"Pattern detection failed for {symbol}: {pattern_result}",
                          extra={'symbol': symbol, 'error_type': 'pattern'})
        
        return {
            "success": not (technical_failed and pattern_failed),
            "symbol": symbol,
            "technical": technical_result if not technical_failed else {"error": str(technical_result)},
            "patterns": pattern_result if not pattern_failed else {"error": str(pattern_result)},
            "analyzed_at": datetime.now().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'symbol': symbol, 'error_type': 'validation'})
        raise McpError("INVALID_PARAMETERS", str(e))
    except Exception as e:
        logger.critical(f"Unexpected error analyzing {symbol}: {e}", exc_info=True,
                       extra={'symbol': symbol, 'error_type': 'unexpected'})
        raise McpError("ANALYSIS_FAILED", f"Analysis failed: {e}")

@mcp.on_initialize()
async def initialize():
    """Initialize orchestration service"""
    logger.info(f"[INIT] Orchestration Service v{SERVICE_VERSION}")
    
    try:
        # Create HTTP session
        state.http_session = aiohttp.ClientSession()
        logger.info("[INIT] HTTP session created")
        
        # Health check all services
        logger.info("[INIT] Checking service health...")
        health = await get_system_health(None)
        
        failed = health.get('failed_services', [])
        if failed:
            logger.warning(f"[INIT] Some services unhealthy: {failed}",
                          extra={'failed_services': failed})
        else:
            logger.info("[INIT] All services healthy")
        
        logger.info("[INIT] Orchestration ready")
        
    except Exception as e:
        logger.critical(f"[INIT] Initialization failed: {e}", exc_info=True,
                       extra={'error_type': 'initialization'})

@mcp.on_cleanup()
async def cleanup():
    """Cleanup orchestration service"""
    logger.info("[CLEANUP] Shutting down orchestration")
    
    try:
        if state.http_session:
            await state.http_session.close()
            logger.info("[CLEANUP] HTTP session closed")
        
        logger.info("[CLEANUP] Orchestration stopped")
        
    except Exception as e:
        logger.error(f"[CLEANUP] Cleanup error: {e}", exc_info=True,
                    extra={'error_type': 'cleanup'})

if __name__ == "__main__":
    logger.info("Starting Catalyst Trading MCP Orchestration Service...")
    logger.info(f"Version: {SERVICE_VERSION}")
    logger.info(f"Configured services: {len(SERVICE_URLS)}")
    mcp.run(transport='stdio')
