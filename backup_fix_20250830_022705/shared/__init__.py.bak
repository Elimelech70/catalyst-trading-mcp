#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: __init__.py
Version: 1.0.0
Last Updated: 2025-01-10
Purpose: Shared utilities package initialization

REVISION HISTORY:
v1.0.0 (2025-01-10) - Clean MCP-compliant version
- Removed placeholder MCP imports
- Only exports legitimate shared utilities
- MCP Database Client for service communication

Description:
Shared utilities for all Catalyst Trading System services.
All database operations go through the MCP Database Service.
"""

# MCP Database Client - Primary database interface for all services
from .mcp_database_client import (
    MCPDatabaseClient,
    MCPRequest,
    MCPResponse
)

# Version info
__version__ = "1.0.0"
__all__ = [
    "MCPDatabaseClient",
    "MCPRequest", 
    "MCPResponse"
]

# Service configuration defaults
DEFAULT_MCP_DATABASE_URL = "ws://database-service:5010"
DEFAULT_REDIS_URL = "redis://redis:6379"

# Logging configuration
import logging

def setup_service_logging(service_name: str, level=logging.INFO):
    """
    Setup standardized logging for services
    
    Args:
        service_name: Name of the service
        level: Logging level
    """
    logging.basicConfig(
        level=level,
        format=f'%(asctime)s - {service_name} - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'/app/logs/{service_name}.log')
        ]
    )
    return logging.getLogger(service_name)