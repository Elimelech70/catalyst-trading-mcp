#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 5.0.0
Last Updated: 2025-10-06
Purpose: MCP orchestration with normalized schema awareness (security_id + time_id)

REVISION HISTORY:
v5.0.0 (2025-10-06) - Normalized Schema Update
- ✅ Handles security_id in responses from other services
- ✅ Passes security_id between services (not just symbol)
- ✅ No direct database writes (calls other services)
- ✅ MCP resources return security_id + symbol
- ✅ Tools coordinate between normalized services
- ✅ Schema-aware responses (mentions FKs in context)
- ✅ Error handling compliant with v1.0 standard

v4.0.0 (2025-09-15) - DEPRECATED (Symbol-based)
- Only passed symbols between services
- No awareness of security_id FKs

Description of Service:
MCP server that orchestrates all trading services using normalized v5.0 schema:
- Exposes resources for Claude to query system state
- Provides tools for triggering scans, analyzing positions
- Coordinates between services using security_id
- Returns both security_id and symbol in all responses
- Schema-aware: knows data uses FKs not duplicate symbols
"""

from fastmcp import FastMCP, Context
from fastmcp.exceptions import McpError
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import aiohttp
import asyncio
import json
import os
import logging

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Service configuration"""
    SERVICE_NAME = "orchestration-service"
    VERSION = "5.0.0"
    
    # Service URLs
    SCANNER_URL = os.getenv("SCANNER_URL", "http://scanner:5001")
    PATTERN_URL = os.getenv("PATTERN_URL", "http://pattern:5002")
    TECHNICAL_URL = os.getenv("TECHNICAL_URL", "http://technical:5003")
    RISK_MANAGER_URL = os.getenv("RISK_MANAGER_URL", "http://risk-manager:5004")
    NEWS_URL = os.getenv("NEWS_URL", "http://news:5005")
    REPORTING_URL = os.getenv("REPORTING_URL", "http://reporting:5006")
    
    # Timeouts
    REQUEST_TIMEOUT = 30
    LONG_REQUEST_TIMEOUT = 120  # For scans

# ============================================================================
# MCP SERVER
# ============================================================================

mcp = FastMCP(
    "Catalyst Trading MCP",
    version=Config.VERSION
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def make_request(
    method: str,
    url: str,
    timeout: int = Config.REQUEST_TIMEOUT,
    **kwargs
) -> Dict[str, Any]:
    """
    Make HTTP request to a service with error handling.
    
    Returns both security_id and symbol when available.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                **kwargs
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"success": True, "data": data}
                else:
                    error_text = await resp.text()
                    logger.error(f"Request failed: {method} {url} - {resp.status} - {error_text}")
                    return {
                        "success": False,
                        "error": f"HTTP {resp.status}: {error_text}"
                    }
    
    except asyncio.TimeoutError:
        logger.error(f"Request timeout: {method} {url}")
        return {"success": False, "error": "Request timeout"}
    
    except Exception as e:
        logger.error(f"Request error: {method} {url} - {e}")
        return {"success": False, "error": str(e)}

def format_response(data: Any, include_schema_note: bool = False) -> str:
    """
    Format response for Claude with optional schema awareness note.
    """
    response = json.dumps(data, indent=2, default=str)
    
    if include_schema_note:
        response += "\n\n📊 Note: All data uses v5.0 normalized schema with security_id FKs"
    
    return response

# ============================================================================
# RESOURCES (Read-Only Data for Claude)
# ============================================================================

@mcp.resource("market-scan://latest-candidates")
async def get_latest_candidates(ctx: Context) -> str:
    """
    Get latest market scan candidates with security_id + symbol.
    
    Returns candidates from most recent scan with both security_id and symbol
    for proper FK tracking.
    """
    result = await make_request(
        "GET",
        f"{Config.SCANNER_URL}/api/v1/candidates"
    )
    
    if not result['success']:
        raise McpError("SCANNER_ERROR", result.get('error', 'Unknown error'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.resource("positions://open")
async def get_open_positions(ctx: Context, cycle_id: int = 1) -> str:
    """
    Get all open positions with security_id + symbol via JOINs.
    
    Returns position data that includes:
    - security_id (FK to securities table)
    - symbol (from JOIN)
    - sector_name (from JOIN)
    """
    result = await make_request(
        "GET",
        f"{Config.RISK_MANAGER_URL}/api/v1/risk/positions",
        params={"cycle_id": cycle_id}
    )
    
    if not result['success']:
        raise McpError("RISK_MANAGER_ERROR", result.get('error', 'Unknown error'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.resource("risk://sector-exposure")
async def get_sector_exposure(ctx: Context, cycle_id: int = 1) -> str:
    """
    Get sector exposure breakdown via positions → securities → sectors JOINs.
    
    Shows how much capital is allocated to each sector using normalized schema.
    """
    result = await make_request(
        "GET",
        f"{Config.RISK_MANAGER_URL}/api/v1/risk/sector-exposure",
        params={"cycle_id": cycle_id}
    )
    
    if not result['success']:
        raise McpError("RISK_MANAGER_ERROR", result.get('error', 'Unknown error'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.resource("risk://daily-limits")
async def get_daily_limits(ctx: Context, cycle_id: int = 1) -> str:
    """
    Get daily risk limits and current usage.
    
    Shows:
    - Max positions vs current positions
    - Daily loss limit vs current P&L
    - Risk parameters from risk_parameters table
    """
    result = await make_request(
        "GET",
        f"{Config.RISK_MANAGER_URL}/api/v1/risk/daily-limits",
        params={"cycle_id": cycle_id}
    )
    
    if not result['success']:
        raise McpError("RISK_MANAGER_ERROR", result.get('error', 'Unknown error'))
    
    return format_response(result['data'])

@mcp.resource("patterns://high-confidence")
async def get_high_confidence_patterns(
    ctx: Context,
    min_confidence: float = 0.75,
    hours: int = 24
) -> str:
    """
    Get high-confidence patterns across all securities.
    
    Returns patterns from pattern_analysis table with:
    - security_id (FK)
    - symbol (from JOIN)
    - Pattern type, confidence, levels
    """
    result = await make_request(
        "GET",
        f"{Config.PATTERN_URL}/api/v1/patterns/high-confidence",
        params={
            "min_confidence": min_confidence,
            "hours": hours
        }
    )
    
    if not result['success']:
        raise McpError("PATTERN_ERROR", result.get('error', 'Unknown error'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.resource("news://recent-catalysts")
async def get_recent_catalysts(
    ctx: Context,
    hours: int = 24,
    min_catalyst_strength: float = 0.7
) -> str:
    """
    Get recent news catalysts with security_id + symbol.
    
    Returns news from news_sentiment table with:
    - security_id (FK)
    - symbol (from JOIN)
    - Catalyst strength, sentiment, impact
    """
    result = await make_request(
        "GET",
        f"{Config.NEWS_URL}/api/v1/news/catalysts",
        params={
            "hours": hours,
            "min_strength": min_catalyst_strength
        }
    )
    
    if not result['success']:
        raise McpError("NEWS_ERROR", result.get('error', 'Unknown error'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.resource("system://health")
async def get_system_health(ctx: Context) -> str:
    """
    Get health status of all services.
    
    Checks which services are up and their schema versions.
    """
    services = {
        "scanner": Config.SCANNER_URL,
        "pattern": Config.PATTERN_URL,
        "technical": Config.TECHNICAL_URL,
        "risk-manager": Config.RISK_MANAGER_URL,
        "news": Config.NEWS_URL,
        "reporting": Config.REPORTING_URL
    }
    
    health_results = {}
    
    for name, base_url in services.items():
        result = await make_request("GET", f"{base_url}/health", timeout=5)
        
        if result['success']:
            health_results[name] = {
                "status": "healthy",
                "data": result['data']
            }
        else:
            health_results[name] = {
                "status": "unhealthy",
                "error": result.get('error')
            }
    
    return format_response({
        "orchestration_version": Config.VERSION,
        "schema_version": "v5.0 normalized",
        "services": health_results
    })

# ============================================================================
# TOOLS (Actions Claude Can Take)
# ============================================================================

@mcp.tool()
async def trigger_market_scan(ctx: Context) -> str:
    """
    Trigger a market scan to find new candidates.
    
    Returns scan_id and candidate count with security_ids.
    """
    logger.info("Triggering market scan...")
    
    result = await make_request(
        "POST",
        f"{Config.SCANNER_URL}/api/v1/scan",
        timeout=Config.LONG_REQUEST_TIMEOUT
    )
    
    if not result['success']:
        raise McpError("SCAN_FAILED", result.get('error', 'Scan failed'))
    
    logger.info(f"✅ Scan complete: {result['data']}")
    
    return format_response({
        "success": True,
        "message": "Market scan completed",
        "data": result['data']
    }, include_schema_note=True)

@mcp.tool()
async def analyze_symbol(
    ctx: Context,
    symbol: str,
    timeframe: str = "5min"
) -> str:
    """
    Analyze a symbol: patterns + technical indicators.
    
    Args:
        symbol: Stock symbol (e.g., AAPL)
        timeframe: Chart timeframe (1min, 5min, 15min, 1h, 1d)
    
    Returns combined analysis with security_id for tracking.
    """
    logger.info(f"Analyzing {symbol} on {timeframe}...")
    
    # Run pattern detection and technical analysis in parallel
    pattern_task = make_request(
        "POST",
        f"{Config.PATTERN_URL}/api/v1/detect",
        json={"symbol": symbol, "timeframe": timeframe}
    )
    
    technical_task = make_request(
        "POST",
        f"{Config.TECHNICAL_URL}/api/v1/calculate",
        json={"symbol": symbol, "timeframe": timeframe}
    )
    
    pattern_result, technical_result = await asyncio.gather(
        pattern_task,
        technical_task
    )
    
    analysis = {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "timestamp": datetime.utcnow().isoformat(),
        "patterns": pattern_result.get('data') if pattern_result['success'] else None,
        "technical": technical_result.get('data') if technical_result['success'] else None,
        "errors": []
    }
    
    if not pattern_result['success']:
        analysis['errors'].append(f"Pattern analysis failed: {pattern_result.get('error')}")
    
    if not technical_result['success']:
        analysis['errors'].append(f"Technical analysis failed: {technical_result.get('error')}")
    
    return format_response(analysis, include_schema_note=True)

@mcp.tool()
async def check_position_risk(
    ctx: Context,
    symbol: str,
    side: str,
    quantity: int,
    entry_price: float,
    stop_price: float,
    target_price: Optional[float] = None,
    cycle_id: int = 1
) -> str:
    """
    Check if a proposed position passes risk checks.
    
    Args:
        symbol: Stock symbol
        side: "long" or "short"
        quantity: Number of shares
        entry_price: Entry price
        stop_price: Stop loss price
        target_price: Optional target price
        cycle_id: Trading cycle ID
    
    Returns risk check result with violations/warnings.
    """
    logger.info(f"Checking risk for {symbol} position...")
    
    request_data = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price
    }
    
    result = await make_request(
        "POST",
        f"{Config.RISK_MANAGER_URL}/api/v1/risk/check",
        params={"cycle_id": cycle_id},
        json=request_data
    )
    
    if not result['success']:
        raise McpError("RISK_CHECK_FAILED", result.get('error', 'Risk check failed'))
    
    return format_response(result['data'])

@mcp.tool()
async def get_technical_indicators(
    ctx: Context,
    symbol: str,
    hours: int = 24,
    timeframe: str = "5min"
) -> str:
    """
    Get technical indicator history for a symbol.
    
    Returns indicators from technical_indicators table with security_id.
    """
    logger.info(f"Fetching technical indicators for {symbol}...")
    
    result = await make_request(
        "GET",
        f"{Config.TECHNICAL_URL}/api/v1/indicators/{symbol}",
        params={
            "hours": hours,
            "timeframe": timeframe
        }
    )
    
    if not result['success']:
        raise McpError("TECHNICAL_ERROR", result.get('error', 'Failed to fetch indicators'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.tool()
async def get_pattern_history(
    ctx: Context,
    symbol: str,
    days: int = 7,
    min_confidence: float = 0.60
) -> str:
    """
    Get pattern detection history for a symbol.
    
    Returns patterns from pattern_analysis table with security_id.
    """
    logger.info(f"Fetching pattern history for {symbol}...")
    
    result = await make_request(
        "GET",
        f"{Config.PATTERN_URL}/api/v1/patterns/{symbol}",
        params={
            "days": days,
            "min_confidence": min_confidence
        }
    )
    
    if not result['success']:
        raise McpError("PATTERN_ERROR", result.get('error', 'Failed to fetch patterns'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.tool()
async def get_news_for_symbol(
    ctx: Context,
    symbol: str,
    hours: int = 24
) -> str:
    """
    Get recent news for a symbol.
    
    Returns news from news_sentiment table with security_id and impact metrics.
    """
    logger.info(f"Fetching news for {symbol}...")
    
    result = await make_request(
        "GET",
        f"{Config.NEWS_URL}/api/v1/news/{symbol}",
        params={"hours": hours}
    )
    
    if not result['success']:
        raise McpError("NEWS_ERROR", result.get('error', 'Failed to fetch news'))
    
    return format_response(result['data'], include_schema_note=True)

@mcp.tool()
async def generate_daily_report(
    ctx: Context,
    cycle_id: int = 1,
    date: Optional[str] = None
) -> str:
    """
    Generate daily trading report.
    
    Args:
        cycle_id: Trading cycle ID
        date: Date in YYYY-MM-DD format (defaults to today)
    
    Returns comprehensive daily report with P&L, positions, patterns.
    """
    logger.info(f"Generating daily report for cycle {cycle_id}...")
    
    params = {"cycle_id": cycle_id}
    if date:
        params["date"] = date
    
    result = await make_request(
        "GET",
        f"{Config.REPORTING_URL}/api/v1/reports/daily",
        params=params,
        timeout=Config.LONG_REQUEST_TIMEOUT
    )
    
    if not result['success']:
        raise McpError("REPORT_ERROR", result.get('error', 'Failed to generate report'))
    
    return format_response(result['data'])

@mcp.tool()
async def update_daily_risk_metrics(
    ctx: Context,
    cycle_id: int = 1
) -> str:
    """
    Update daily risk metrics in the database.
    
    Recalculates and stores today's risk metrics.
    """
    logger.info(f"Updating daily risk metrics for cycle {cycle_id}...")
    
    result = await make_request(
        "POST",
        f"{Config.RISK_MANAGER_URL}/api/v1/risk/update-daily-metrics",
        params={"cycle_id": cycle_id}
    )
    
    if not result['success']:
        raise McpError("UPDATE_FAILED", result.get('error', 'Failed to update metrics'))
    
    return format_response({
        "success": True,
        "message": "Daily risk metrics updated",
        "data": result['data']
    })

# ============================================================================
# PROMPTS (Pre-defined Workflows)
# ============================================================================

@mcp.prompt()
def morning_briefing() -> str:
    """
    Morning briefing prompt for Claude.
    
    Suggests what to check at market open.
    """
    return """Please provide a morning trading briefing:

1. Check system health
2. Get latest scan candidates
3. Review high-confidence patterns from last 24h
4. Check recent news catalysts
5. Review current risk limits and sector exposure

Summarize key opportunities and risks for today."""

@mcp.prompt()
def analyze_candidate(symbol: str) -> str:
    """
    Deep analysis prompt for a candidate.
    """
    return f"""Please perform a comprehensive analysis of {symbol}:

1. Run technical indicator analysis
2. Detect chart patterns
3. Get recent news and catalysts
4. Review pattern history (last 7 days)
5. Check if this symbol is in any open positions

Provide a trading recommendation with entry/exit levels."""

@mcp.prompt()
def end_of_day_review() -> str:
    """
    End of day review prompt.
    """
    return """Please provide an end-of-day review:

1. Generate daily report
2. Review all open positions with risk metrics
3. Check sector exposure
4. Update daily risk metrics
5. Summarize today's P&L and key learnings

Highlight any risk concerns or opportunities for tomorrow."""

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting {Config.SERVICE_NAME} v{Config.VERSION}")
    logger.info("MCP server with normalized schema v5.0 awareness")
    
    # Run MCP server
    mcp.run()
