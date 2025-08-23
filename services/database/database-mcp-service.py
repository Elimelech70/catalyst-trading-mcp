#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: database-mcp-service.py
Version: 1.0.0
Last Updated: 2025-08-23
Purpose: MCP-enabled database service replacing direct database access

REVISION HISTORY:
v1.0.0 (2025-08-23) - Initial implementation
- Centralized database operations via MCP
- Connection pool management
- Transaction support
- Query and persistence tools
- Cache management integration
- Replaces database_utils.py for all services

Description of Service:
This MCP server provides centralized database access for all services
in the Catalyst Trading System. It manages PostgreSQL connections,
handles transactions, and provides both read (resources) and write (tools)
operations through the MCP protocol.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncpg
import redis.asyncio as redis
from structlog import get_logger

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport


class DatabaseMCPServer:
    """MCP Server for centralized database operations"""
    
    def __init__(self):
        # Initialize MCP server
        self.server = MCPServer("database-service")
        self.setup_logging()
        
        # Database configuration
        self.db_url = os.getenv('DATABASE_URL')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        
        # Connection pools
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        
        # Service configuration
        self.service_name = 'database-mcp'
        self.port = int(os.getenv('PORT', '5010'))
        
        # Register MCP endpoints
        self._register_resources()
        self._register_tools()
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    async def initialize_connections(self):
        """Initialize database and cache connections"""
        try:
            # Create PostgreSQL connection pool
            self.db_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=5,
                max_size=20,
                max_queries=50000,
                max_inactive_connection_lifetime=300
            )
            
            # Create Redis connection
            self.redis_client = await redis.from_url(
                self.redis_url,
                decode_responses=True
            )
            
            self.logger.info("Database connections initialized",
                           pg_pool_size=20,
                           redis_connected=True)
            
        except Exception as e:
            self.logger.error("Failed to initialize database connections",
                            error=str(e))
            raise
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("db/status")
        async def get_database_status(params: ResourceParams) -> ResourceResponse:
            """Get database health and connection status"""
            status = {
                "postgresql": {
                    "status": "healthy" if self.db_pool else "unhealthy",
                    "pool_size": self.db_pool._size if self.db_pool else 0,
                    "pool_free": self.db_pool._free_count if self.db_pool else 0,
                    "pool_used": self.db_pool._used_count if self.db_pool else 0
                },
                "redis": {
                    "status": "healthy" if self.redis_client else "unhealthy",
                    "ping": await self.redis_client.ping() if self.redis_client else False
                }
            }
            
            return ResourceResponse(
                type="database_status",
                data=status,
                metadata={"timestamp": datetime.now().isoformat()}
            )
        
        @self.server.resource("db/metrics")
        async def get_database_metrics(params: ResourceParams) -> ResourceResponse:
            """Get database performance metrics"""
            timeframe = params.get("timeframe", "1h")
            
            # Get metrics from cache or calculate
            cache_key = f"db:metrics:{timeframe}"
            cached = await self.redis_client.get(cache_key) if self.redis_client else None
            
            if cached:
                metrics = json.loads(cached)
            else:
                metrics = await self._calculate_metrics(timeframe)
                if self.redis_client:
                    await self.redis_client.setex(
                        cache_key, 300, json.dumps(metrics)
                    )
            
            return ResourceResponse(
                type="database_metrics",
                data=metrics
            )
        
        @self.server.resource("cache/status")
        async def get_cache_status(params: ResourceParams) -> ResourceResponse:
            """Get Redis cache status and statistics"""
            if not self.redis_client:
                return ResourceResponse(
                    type="cache_status",
                    data={"status": "disconnected"}
                )
            
            info = await self.redis_client.info()
            memory_info = await self.redis_client.info("memory")
            
            status = {
                "connected": True,
                "used_memory": memory_info.get("used_memory_human", "0"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
            
            return ResourceResponse(
                type="cache_status",
                data=status
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("persist_trading_signal")
        async def persist_trading_signal(params: ToolParams) -> ToolResponse:
            """Persist a trading signal to database"""
            signal_data = params["signal_data"]
            
            async with self.db_pool.acquire() as conn:
                try:
                    signal_id = await conn.fetchval("""
                        INSERT INTO trading_signals (
                            symbol, signal_type, action, confidence,
                            entry_price, stop_loss, take_profit,
                            metadata, created_at, expires_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        RETURNING signal_id
                    """,
                        signal_data["symbol"],
                        signal_data["signal_type"],
                        signal_data["action"],
                        signal_data["confidence"],
                        signal_data.get("entry_price"),
                        signal_data.get("stop_loss"),
                        signal_data.get("take_profit"),
                        json.dumps(signal_data.get("metadata", {})),
                        datetime.now(),
                        signal_data.get("expires_at")
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "signal_id": signal_id,
                            "created": True
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to persist trading signal",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("persist_trade_record")
        async def persist_trade_record(params: ToolParams) -> ToolResponse:
            """Persist a trade record to database"""
            trade_data = params["trade_data"]
            
            async with self.db_pool.acquire() as conn:
                try:
                    trade_id = await conn.fetchval("""
                        INSERT INTO trade_records (
                            signal_id, symbol, side, quantity,
                            entry_price, entry_time, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING trade_id
                    """,
                        trade_data.get("signal_id"),
                        trade_data["symbol"],
                        trade_data["side"],
                        trade_data["quantity"],
                        trade_data["entry_price"],
                        datetime.now(),
                        json.dumps(trade_data.get("metadata", {}))
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "trade_id": trade_id,
                            "created": True
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to persist trade record",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("persist_news_article")
        async def persist_news_article(params: ToolParams) -> ToolResponse:
            """Persist a news article to database"""
            article_data = params["article_data"]
            
            # Generate news ID
            news_id = self._generate_news_id(
                article_data["headline"],
                article_data["source"],
                article_data["published_timestamp"]
            )
            
            async with self.db_pool.acquire() as conn:
                try:
                    await conn.execute("""
                        INSERT INTO news_raw (
                            news_id, symbol, headline, source,
                            published_timestamp, content_snippet,
                            metadata, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (news_id) DO NOTHING
                    """,
                        news_id,
                        article_data.get("symbol"),
                        article_data["headline"],
                        article_data["source"],
                        article_data["published_timestamp"],
                        article_data.get("content_snippet"),
                        json.dumps(article_data.get("metadata", {})),
                        datetime.now()
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "news_id": news_id,
                            "created": True
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to persist news article",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("persist_pattern_detection")
        async def persist_pattern_detection(params: ToolParams) -> ToolResponse:
            """Persist a pattern detection to database"""
            pattern_data = params["pattern_data"]
            
            async with self.db_pool.acquire() as conn:
                try:
                    pattern_id = await conn.fetchval("""
                        INSERT INTO pattern_analysis (
                            symbol, pattern_name, pattern_type,
                            base_confidence, final_confidence,
                            timeframe, metadata, detected_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING pattern_id
                    """,
                        pattern_data["symbol"],
                        pattern_data["pattern_type"],
                        pattern_data.get("pattern_category", "unknown"),
                        pattern_data.get("base_confidence", pattern_data["confidence"]),
                        pattern_data["confidence"],
                        pattern_data["timeframe"],
                        json.dumps({
                            "pattern_data": pattern_data.get("pattern_data", {}),
                            "catalyst_context": pattern_data.get("catalyst_context", {})
                        }),
                        datetime.now()
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "pattern_id": pattern_id,
                            "created": True
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to persist pattern detection",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("persist_scan_results")
        async def persist_scan_results(params: ToolParams) -> ToolResponse:
            """Persist market scan results"""
            scan_data = params["scan_data"]
            
            async with self.db_pool.acquire() as conn:
                try:
                    # Store scan metadata
                    scan_record_id = await conn.fetchval("""
                        INSERT INTO market_scans (
                            scan_id, scan_time, candidates_count,
                            metadata
                        ) VALUES ($1, $2, $3, $4)
                        RETURNING id
                    """,
                        scan_data["scan_id"],
                        scan_data["timestamp"],
                        len(scan_data.get("candidates", [])),
                        json.dumps(scan_data.get("metadata", {}))
                    )
                    
                    # Store individual candidates
                    for candidate in scan_data.get("candidates", []):
                        await conn.execute("""
                            INSERT INTO scan_candidates (
                                scan_id, symbol, score, rank,
                                metadata
                            ) VALUES ($1, $2, $3, $4, $5)
                        """,
                            scan_data["scan_id"],
                            candidate["symbol"],
                            candidate.get("score", 0),
                            candidate.get("rank", 999),
                            json.dumps(candidate)
                        )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "scan_record_id": scan_record_id,
                            "candidates_stored": len(scan_data.get("candidates", []))
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to persist scan results",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("get_pending_signals")
        async def get_pending_signals(params: ToolParams) -> ToolResponse:
            """Get pending trading signals"""
            limit = params.get("limit", 10)
            min_confidence = params.get("min_confidence", 0.7)
            
            async with self.db_pool.acquire() as conn:
                try:
                    rows = await conn.fetch("""
                        SELECT * FROM trading_signals
                        WHERE status = 'pending'
                        AND confidence >= $1
                        AND (expires_at IS NULL OR expires_at > NOW())
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, min_confidence, limit)
                    
                    signals = [dict(row) for row in rows]
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "signals": signals,
                            "count": len(signals)
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to get pending signals",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("get_open_positions")
        async def get_open_positions(params: ToolParams) -> ToolResponse:
            """Get all open trading positions"""
            async with self.db_pool.acquire() as conn:
                try:
                    rows = await conn.fetch("""
                        SELECT * FROM trade_records
                        WHERE exit_time IS NULL
                        ORDER BY entry_time DESC
                    """)
                    
                    positions = [dict(row) for row in rows]
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "positions": positions,
                            "count": len(positions)
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to get open positions",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("get_recent_news")
        async def get_recent_news(params: ToolParams) -> ToolResponse:
            """Get recent news articles"""
            hours = params.get("hours", 24)
            symbol = params.get("symbol")
            
            async with self.db_pool.acquire() as conn:
                try:
                    query = """
                        SELECT * FROM news_raw
                        WHERE published_timestamp > NOW() - INTERVAL '%s hours'
                    """
                    query_params = [hours]
                    
                    if symbol:
                        query += " AND symbol = $2"
                        query_params.append(symbol)
                    
                    query += " ORDER BY published_timestamp DESC"
                    
                    rows = await conn.fetch(query, *query_params)
                    articles = [dict(row) for row in rows]
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "articles": articles,
                            "count": len(articles)
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to get recent news",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("create_trading_cycle")
        async def create_trading_cycle(params: ToolParams) -> ToolResponse:
            """Create a new trading cycle"""
            cycle_data = params["cycle_data"]
            
            async with self.db_pool.acquire() as conn:
                try:
                    cycle_id = await conn.fetchval("""
                        INSERT INTO trading_cycles (
                            cycle_type, status, start_time,
                            metadata, created_at
                        ) VALUES ($1, $2, $3, $4, $5)
                        RETURNING cycle_id
                    """,
                        cycle_data["cycle_type"],
                        "running",
                        datetime.now(),
                        json.dumps(cycle_data.get("metadata", {})),
                        datetime.now()
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "cycle_id": str(cycle_id),
                            "status": "running"
                        }
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to create trading cycle",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("update_trading_cycle")
        async def update_trading_cycle(params: ToolParams) -> ToolResponse:
            """Update trading cycle status"""
            cycle_id = params["cycle_id"]
            status = params["status"]
            metadata = params.get("metadata", {})
            
            async with self.db_pool.acquire() as conn:
                try:
                    await conn.execute("""
                        UPDATE trading_cycles
                        SET status = $2,
                            end_time = CASE WHEN $2 IN ('completed', 'failed') 
                                      THEN NOW() ELSE end_time END,
                            metadata = metadata || $3,
                            updated_at = NOW()
                        WHERE cycle_id = $1
                    """,
                        cycle_id,
                        status,
                        json.dumps(metadata)
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={"updated": True}
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to update trading cycle",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("log_workflow_step")
        async def log_workflow_step(params: ToolParams) -> ToolResponse:
            """Log a workflow step"""
            cycle_id = params["cycle_id"]
            step_name = params["step_name"]
            status = params["status"]
            details = params.get("details", {})
            
            async with self.db_pool.acquire() as conn:
                try:
                    await conn.execute("""
                        INSERT INTO workflow_logs (
                            cycle_id, step_name, status,
                            details, timestamp
                        ) VALUES ($1, $2, $3, $4, $5)
                    """,
                        cycle_id,
                        step_name,
                        status,
                        json.dumps(details),
                        datetime.now()
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={"logged": True}
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to log workflow step",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
        
        @self.server.tool("update_service_health")
        async def update_service_health(params: ToolParams) -> ToolResponse:
            """Update service health status"""
            service_name = params["service_name"]
            status = params["status"]
            details = params.get("details", {})
            
            async with self.db_pool.acquire() as conn:
                try:
                    await conn.execute("""
                        INSERT INTO service_health (
                            service_name, status, last_check,
                            details
                        ) VALUES ($1, $2, $3, $4)
                        ON CONFLICT (service_name) DO UPDATE
                        SET status = $2,
                            last_check = $3,
                            details = $4
                    """,
                        service_name,
                        status,
                        datetime.now(),
                        json.dumps(details)
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={"updated": True}
                    )
                    
                except Exception as e:
                    self.logger.error("Failed to update service health",
                                    error=str(e))
                    return ToolResponse(
                        success=False,
                        error=str(e)
                    )
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
    
    def _generate_news_id(self, headline: str, source: str, timestamp: str) -> str:
        """Generate unique news ID"""
        import hashlib
        content = f"{headline}:{source}:{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def _calculate_metrics(self, timeframe: str) -> Dict:
        """Calculate database performance metrics"""
        # This would implement actual metrics calculation
        # For now, return mock data
        return {
            "avg_query_time_ms": 23.5,
            "queries_per_second": 145,
            "slow_queries": 3,
            "connection_pool_efficiency": 0.85,
            "cache_hit_rate": 0.78,
            "timeframe": timeframe,
            "calculated_at": datetime.now().isoformat()
        }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Database MCP Server",
                        version="1.0.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Initialize connections
        await self.initialize_connections()
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


if __name__ == "__main__":
    # Run the MCP server
    server = DatabaseMCPServer()
    asyncio.run(server.run())