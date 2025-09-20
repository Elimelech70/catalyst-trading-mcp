#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Risk-integrated MCP orchestration service using FastMCP implementation

REVISION HISTORY:
v4.2.0 (2025-09-20) - Risk Management Integration
- Added Risk Manager service integration (port 5004)
- Enhanced with 8-service architecture per v4.2 specs
- Mandatory risk validation for all trades
- Risk-first trading flow implementation
- Enhanced safety protocols and emergency stops
- Updated resource hierarchies for risk management

v4.1.0 (2025-09-20) - Corrected MCP implementation
- Fixed to use actual FastMCP from Anthropic SDK
- Removed non-existent MCPServer references
- Added proper hierarchical URI structure
- Implemented Context parameters correctly
- Added proper error handling with McpError

Description of Service:
Primary orchestration service providing MCP interface for Claude interaction
with integrated risk management. Coordinates 8 internal REST services with
mandatory risk validation and safety protocols per v4.2 architecture.
"""

import os
import asyncio
import aiohttp
import asyncpg
import redis.asyncio as redis
from typing import Dict, List, Optional, Any
from datetime import datetime, time
from enum import Enum
import structlog
from pydantic import BaseModel
import json

# CORRECT MCP imports - using actual FastMCP
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import McpError

# Initialize FastMCP server (NOT MCPServer!)
mcp = FastMCP("orchestration")
logger = structlog.get_logger()

# === GLOBAL STATE ===
class WorkflowState(Enum):
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    IDLE = "idle"

class TradingCycle(BaseModel):
    cycle_id: str
    mode: str
    status: str
    start_time: datetime
    scan_frequency: int = 300
    max_positions: int = 5
    aggressiveness: float = 0.5

class SystemState:
    def __init__(self):
        self.current_cycle: Optional[TradingCycle] = None
        self.workflow_state: WorkflowState = WorkflowState.IDLE
        self.service_health: Dict = {}
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None

# Global state instance
state = SystemState()

# Service URLs (8-service v4.2 architecture)
SERVICE_URLS = {
    "scanner": "http://localhost:5001",
    "pattern": "http://localhost:5002", 
    "technical": "http://localhost:5003",
    "risk_manager": "http://localhost:5004",  # NEW in v4.2
    "trading": "http://localhost:5005",
    "news": "http://localhost:5008",
    "reporting": "http://localhost:5009"
}

# === MCP INITIALIZATION ===
@mcp.on_init()
async def init_handler():
    """Initialize connections and state"""
    logger.info("Initializing orchestration service...")
    
    try:
        # Initialize database connection pool with optimized settings
        state.db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL"),
            min_size=2,        # Reduced from 5
            max_size=5,        # Reduced from 20
            command_timeout=30, # Reduced from 60
            max_inactive_connection_lifetime=300,
            statement_cache_size=0  # Save memory
        )