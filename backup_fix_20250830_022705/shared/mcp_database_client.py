#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: mcp_database_client.py
Version: 1.0.0
Last Updated: 2025-08-23
Purpose: MCP client library for database operations

REVISION HISTORY:
v1.0.0 (2025-08-23) - Initial implementation
- MCP client for Database Service communication
- Async/await support throughout
- Connection pooling and retry logic
- Type hints for all methods
- Error handling and logging

Description of Service:
This library provides a client interface for all services to communicate
with the Database MCP Service. It replaces direct database_utils.py usage
and ensures all database operations go through the centralized MCP service.
"""

import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import aiohttp
from dataclasses import dataclass, asdict


@dataclass
class MCPRequest:
    """MCP request structure"""
    type: str  # "resource" or "tool"
    resource: Optional[str] = None
    tool: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MCPResponse:
    """MCP response structure"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MCPResponse':
        return cls(**data)


class MCPDatabaseClient:
    """Client for interacting with the Database MCP Service"""
    
    def __init__(self, mcp_url: str = "ws://database-service:5010"):
        """
        Initialize MCP Database Client
        
        Args:
            mcp_url: WebSocket URL of the Database MCP Service
        """
        self.mcp_url = mcp_url
        self.logger = logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connected = False
        self._retry_count = 0
        self._max_retries = 3
        
    async def connect(self):
        """Establish connection to Database MCP Service"""
        if self._connected:
            return
            
        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(self.mcp_url)
            self._connected = True
            self._retry_count = 0
            self.logger.info(f"Connected to Database MCP Service at {self.mcp_url}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Database MCP Service: {str(e)}")
            await self._handle_connection_error()
            raise
    
    async def disconnect(self):
        """Close connection to Database MCP Service"""
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        self._connected = False
        self.logger.info("Disconnected from Database MCP Service")
    
    async def _ensure_connected(self):
        """Ensure connection is established"""
        if not self._connected:
            await self.connect()
    
    async def _handle_connection_error(self):
        """Handle connection errors with retry logic"""
        self._retry_count += 1
        if self._retry_count <= self._max_retries:
            wait_time = 2 ** self._retry_count  # Exponential backoff
            self.logger.warning(f"Retrying connection in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            await self.connect()
        else:
            self.logger.error("Max retries exceeded. Could not connect to Database MCP Service")
    
    async def _send_request(self, request: MCPRequest) -> MCPResponse:
        """Send request to Database MCP Service and get response"""
        await self._ensure_connected()
        
        try:
            # Send request
            await self._ws.send_json(request.to_dict())
            
            # Wait for response
            response_data = await self._ws.receive_json()
            return MCPResponse.from_dict(response_data)
            
        except Exception as e:
            self.logger.error(f"Error communicating with Database MCP Service: {str(e)}")
            return MCPResponse(success=False, error=str(e))
    
    # Resource Methods (Read Operations)
    
    async def get_database_status(self) -> Dict[str, Any]:
        """Get database health and connection status"""
        request = MCPRequest(
            type="resource",
            resource="db/status"
        )
        response = await self._send_request(request)
        return response.data if response.success else {}
    
    async def get_database_metrics(self, timeframe: str = "1h") -> Dict[str, Any]:
        """Get database performance metrics"""
        request = MCPRequest(
            type="resource",
            resource="db/metrics",
            params={"timeframe": timeframe}
        )
        response = await self._send_request(request)
        return response.data if response.success else {}
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """Get Redis cache status and statistics"""
        request = MCPRequest(
            type="resource",
            resource="cache/status"
        )
        response = await self._send_request(request)
        return response.data if response.success else {}
    
    # Tool Methods (Write Operations)
    
    async def persist_trading_signal(self, signal_data: Dict[str, Any]) -> Optional[int]:
        """
        Persist a trading signal to database
        
        Args:
            signal_data: Dictionary containing signal information
                - symbol: str
                - signal_type: str
                - action: str (BUY/SELL)
                - confidence: float
                - entry_price: Optional[float]
                - stop_loss: Optional[float]
                - take_profit: Optional[float]
                - metadata: Optional[Dict]
                - expires_at: Optional[datetime]
        
        Returns:
            signal_id if successful, None otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="persist_trading_signal",
            params={"signal_data": signal_data}
        )
        response = await self._send_request(request)
        return response.data.get("signal_id") if response.success else None
    
    async def persist_trade_record(self, trade_data: Dict[str, Any]) -> Optional[int]:
        """
        Persist a trade record to database
        
        Args:
            trade_data: Dictionary containing trade information
                - signal_id: Optional[int]
                - symbol: str
                - side: str (buy/sell)
                - quantity: int
                - entry_price: float
                - metadata: Optional[Dict]
        
        Returns:
            trade_id if successful, None otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="persist_trade_record",
            params={"trade_data": trade_data}
        )
        response = await self._send_request(request)
        return response.data.get("trade_id") if response.success else None
    
    async def persist_news_article(self, article_data: Dict[str, Any]) -> Optional[str]:
        """
        Persist a news article to database
        
        Args:
            article_data: Dictionary containing article information
                - headline: str
                - source: str
                - published_timestamp: str
                - symbol: Optional[str]
                - content_snippet: Optional[str]
                - metadata: Optional[Dict]
        
        Returns:
            news_id if successful, None otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="persist_news_article",
            params={"article_data": article_data}
        )
        response = await self._send_request(request)
        return response.data.get("news_id") if response.success else None
    
    async def persist_pattern_detection(self, pattern_data: Dict[str, Any]) -> Optional[int]:
        """
        Persist a pattern detection to database
        
        Args:
            pattern_data: Dictionary containing pattern information
                - symbol: str
                - pattern_type: str
                - confidence: float
                - timeframe: str
                - pattern_data: Dict
                - catalyst_context: Optional[Dict]
        
        Returns:
            pattern_id if successful, None otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="persist_pattern_detection",
            params={"pattern_data": pattern_data}
        )
        response = await self._send_request(request)
        return response.data.get("pattern_id") if response.success else None
    
    async def persist_scan_results(self, scan_data: Dict[str, Any]) -> Optional[int]:
        """
        Persist market scan results to database
        
        Args:
            scan_data: Dictionary containing scan results
                - scan_id: str
                - timestamp: datetime
                - candidates: List[Dict]
                - metadata: Optional[Dict]
        
        Returns:
            scan_record_id if successful, None otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="persist_scan_results",
            params={"scan_data": scan_data}
        )
        response = await self._send_request(request)
        return response.data.get("scan_record_id") if response.success else None
    
    # Query Operations
    
    async def get_pending_signals(self, limit: int = 10, 
                                 min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """
        Get pending trading signals
        
        Args:
            limit: Maximum number of signals to return
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of pending signals
        """
        request = MCPRequest(
            type="tool",
            tool="get_pending_signals",
            params={
                "limit": limit,
                "min_confidence": min_confidence
            }
        )
        response = await self._send_request(request)
        return response.data.get("signals", []) if response.success else []
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open trading positions"""
        request = MCPRequest(
            type="tool",
            tool="get_open_positions"
        )
        response = await self._send_request(request)
        return response.data.get("positions", []) if response.success else []
    
    async def get_recent_news(self, hours: int = 24, 
                             symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent news articles
        
        Args:
            hours: Look back period in hours
            symbol: Optional symbol filter
        
        Returns:
            List of news articles
        """
        request = MCPRequest(
            type="tool",
            tool="get_recent_news",
            params={
                "hours": hours,
                "symbol": symbol
            }
        )
        response = await self._send_request(request)
        return response.data.get("articles", []) if response.success else []
    
    async def get_trading_history(self, days: int = 7, 
                                 symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get trading history
        
        Args:
            days: Look back period in days
            symbol: Optional symbol filter
        
        Returns:
            List of historical trades
        """
        request = MCPRequest(
            type="tool",
            tool="get_trading_history",
            params={
                "days": days,
                "symbol": symbol
            }
        )
        response = await self._send_request(request)
        return response.data.get("trades", []) if response.success else []
    
    # Workflow Operations
    
    async def create_trading_cycle(self, cycle_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new trading cycle
        
        Args:
            cycle_data: Dictionary containing cycle information
                - cycle_type: str
                - metadata: Optional[Dict]
        
        Returns:
            cycle_id if successful, None otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="create_trading_cycle",
            params={"cycle_data": cycle_data}
        )
        response = await self._send_request(request)
        return response.data.get("cycle_id") if response.success else None
    
    async def update_trading_cycle(self, cycle_id: str, status: str, 
                                  metadata: Optional[Dict] = None) -> bool:
        """
        Update trading cycle status
        
        Args:
            cycle_id: ID of the trading cycle
            status: New status
            metadata: Optional metadata to update
        
        Returns:
            True if successful, False otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="update_trading_cycle",
            params={
                "cycle_id": cycle_id,
                "status": status,
                "metadata": metadata
            }
        )
        response = await self._send_request(request)
        return response.success
    
    async def log_workflow_step(self, cycle_id: str, step_name: str, 
                               status: str, details: Optional[Dict] = None) -> bool:
        """
        Log a workflow step
        
        Args:
            cycle_id: ID of the trading cycle
            step_name: Name of the workflow step
            status: Step status (started/completed/failed)
            details: Optional details dictionary
        
        Returns:
            True if successful, False otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="log_workflow_step",
            params={
                "cycle_id": cycle_id,
                "step_name": step_name,
                "status": status,
                "details": details or {}
            }
        )
        response = await self._send_request(request)
        return response.success
    
    async def update_service_health(self, service_name: str, status: str,
                                   details: Optional[Dict] = None) -> bool:
        """
        Update service health status
        
        Args:
            service_name: Name of the service
            status: Health status (healthy/degraded/unhealthy)
            details: Optional health details
        
        Returns:
            True if successful, False otherwise
        """
        request = MCPRequest(
            type="tool",
            tool="update_service_health",
            params={
                "service_name": service_name,
                "status": status,
                "details": details or {}
            }
        )
        response = await self._send_request(request)
        return response.success
    
    async def get_service_health(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get service health status
        
        Args:
            service_name: Optional specific service name
        
        Returns:
            Health status dictionary
        """
        request = MCPRequest(
            type="tool",
            tool="get_service_health",
            params={"service_name": service_name} if service_name else {}
        )
        response = await self._send_request(request)
        return response.data if response.success else {}
    
    # Context Manager Support
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


# Convenience functions for backward compatibility during migration
async def get_db_client() -> MCPDatabaseClient:
    """Get a connected database client instance"""
    client = MCPDatabaseClient()
    await client.connect()
    return client


# Example usage
async def example_usage():
    """Example of how to use the MCP Database Client"""
    
    # Using context manager (recommended)
    async with MCPDatabaseClient() as db_client:
        
        # Get database status
        status = await db_client.get_database_status()
        print(f"Database Status: {status}")
        
        # Persist a trading signal
        signal_data = {
            "symbol": "AAPL",
            "signal_type": "momentum",
            "action": "BUY",
            "confidence": 0.85,
            "entry_price": 175.50,
            "stop_loss": 172.00,
            "take_profit": 180.00,
            "metadata": {
                "catalyst": "earnings_beat",
                "pattern": "bull_flag"
            }
        }
        signal_id = await db_client.persist_trading_signal(signal_data)
        print(f"Created signal: {signal_id}")
        
        # Get pending signals
        signals = await db_client.get_pending_signals(limit=5, min_confidence=0.8)
        print(f"Found {len(signals)} pending signals")
        
        # Create and update a trading cycle
        cycle_id = await db_client.create_trading_cycle({
            "cycle_type": "regular",
            "metadata": {"mode": "aggressive"}
        })
        
        await db_client.log_workflow_step(
            cycle_id, "news_collection", "started"
        )
        
        # ... do work ...
        
        await db_client.log_workflow_step(
            cycle_id, "news_collection", "completed",
            {"articles_collected": 42}
        )
        
        # Update service health
        await db_client.update_service_health(
            "news-service", "healthy", 
            {"uptime": "24h", "processed": 1000}
        )


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())