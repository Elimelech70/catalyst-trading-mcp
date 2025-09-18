#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: database-mcp-service.py
Version: 3.1.0
Last Updated: 2025-09-19
Purpose: Database MCP service with FIXED URL validation

REVISION HISTORY:
v3.1.0 (2025-09-19) - Fixed URL validation errors
- Changed all resource URIs to valid URL format (http://...)
- Fixed FastMCP compatibility issues
- Added proper health endpoint

v3.0.0 (2025-09-18) - Fixed missing database persistence
- Implemented actual database operations for persist_scan_results
- Added proper PostgreSQL connection handling

Description of Service:
MCP database service that handles all database operations for the Catalyst
Trading System. Provides tools for persisting trading data including scan
results, trading signals, positions, and audit logs.
"""

import os
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncpg
import redis
import logging
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database-mcp-service")

# Initialize FastMCP server
mcp = FastMCP("database-mcp-service")

# Global connections
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None

# ========== CONNECTION HELPERS ==========

async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global db_pool
    if not db_pool:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        logger.info("Creating database connection pool...")
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            max_queries=50000,
            max_inactive_connection_lifetime=300,
            command_timeout=60
        )
        logger.info("Database pool created successfully")
    return db_pool

def get_db_connection():
    """Context manager for database connections"""
    class DBConnection:
        async def __aenter__(self):
            pool = await get_db_pool()
            self.conn = await pool.acquire()
            return self.conn
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.conn:
                await db_pool.release(self.conn)
    
    return DBConnection()

# ========== RESOURCES (Read Operations) ==========

@mcp.resource("http://db/status")
async def get_database_status() -> Dict:
    """Get database health and connection status"""
    try:
        async with get_db_connection() as conn:
            # Test connection
            version = await conn.fetchval("SELECT version()")
            
            # Get connection stats
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_connections,
                    COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                    COUNT(*) FILTER (WHERE state = 'idle') as idle_connections
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            
            return {
                "postgresql": {
                    "status": "healthy",
                    "version": version.split(',')[0],
                    "connections_active": stats['active_connections'],
                    "connections_idle": stats['idle_connections'],
                    "connections_total": stats['total_connections']
                },
                "redis": {
                    "status": "healthy" if redis_client and await redis_client.ping() else "disconnected"
                },
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get database status: {str(e)}")
        return {
            "postgresql": {"status": "unhealthy", "error": str(e)},
            "redis": {"status": "unknown"},
            "timestamp": datetime.now().isoformat()
        }

@mcp.resource("http://db/metrics")
async def get_database_metrics() -> Dict:
    """Get database performance metrics"""
    try:
        timeframe = "1h"  # Default timeframe
        
        async with get_db_connection() as conn:
            # Map timeframe to PostgreSQL interval
            interval = f"{timeframe} ago"
            
            metrics = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT scan_id) as total_scans,
                    COUNT(*) as total_records,
                    AVG(momentum_score) as avg_momentum,
                    AVG(catalyst_score) as avg_catalyst,
                    COUNT(DISTINCT symbol) as unique_symbols
                FROM scan_results
                WHERE scan_time > NOW() - INTERVAL $1
            """, interval)
            
            return {
                "timeframe": timeframe,
                "metrics": dict(metrics) if metrics else {},
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.resource("http://cache/status")
async def get_cache_status() -> Dict:
    """Get Redis cache status"""
    try:
        if not redis_client:
            return {"status": "disconnected"}
        
        info = await redis_client.info()
        return {
            "status": "healthy",
            "memory_used": info.get('used_memory_human', 'unknown'),
            "connected_clients": info.get('connected_clients', 0),
            "total_commands": info.get('total_commands_processed', 0)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ========== TOOLS (Write Operations) ==========

@mcp.tool()
async def persist_scan_results(scan_data: Dict) -> Dict:
    """Persist scan results to database
    
    Args:
        scan_data: Dictionary containing:
            - scan_id: Unique scan identifier
            - timestamp: Scan timestamp
            - candidates: List of candidate securities
            - metadata: Additional scan metadata
    
    Returns:
        Success status and number of records saved
    """
    try:
        async with get_db_connection() as conn:
            # Get or create trading cycle
            cycle_id = await conn.fetchval("""
                SELECT cycle_id FROM trading_cycles 
                WHERE status = 'active' 
                ORDER BY start_time DESC LIMIT 1
            """)
            
            if not cycle_id:
                cycle_id = await conn.fetchval("""
                    INSERT INTO trading_cycles (scan_type, status, start_time)
                    VALUES ('market_scan', 'active', NOW())
                    RETURNING cycle_id
                """)
                logger.info(f"Created new trading cycle: {cycle_id}")
            
            # Save each candidate
            saved_count = 0
            for candidate in scan_data.get('candidates', []):
                try:
                    await conn.execute("""
                        INSERT INTO scan_results (
                            scan_id, cycle_id, symbol, scan_time,
                            momentum_score, volume_score, catalyst_score,
                            composite_score, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (scan_id, symbol) DO UPDATE SET
                            momentum_score = EXCLUDED.momentum_score,
                            volume_score = EXCLUDED.volume_score,
                            catalyst_score = EXCLUDED.catalyst_score,
                            composite_score = EXCLUDED.composite_score,
                            metadata = EXCLUDED.metadata
                    """, 
                        scan_data['scan_id'],
                        cycle_id,
                        candidate['symbol'],
                        datetime.fromisoformat(scan_data['timestamp']),
                        candidate.get('momentum_score', 0),
                        candidate.get('volume_score', 0),
                        candidate.get('catalyst_score', 0),
                        candidate.get('score', 0),
                        json.dumps(candidate)
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save candidate {candidate.get('symbol')}: {str(e)}")
            
            logger.info(f"Persisted {saved_count}/{len(scan_data.get('candidates', []))} scan results for scan {scan_data['scan_id']}")
            
            return {
                "success": True,
                "scan_record_id": scan_data['scan_id'],
                "cycle_id": cycle_id,
                "candidates_saved": saved_count
            }
    except Exception as e:
        logger.error(f"Failed to persist scan results: {str(e)}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def persist_trading_signal(signal_data: Dict) -> Dict:
    """Persist trading signal to database"""
    try:
        async with get_db_connection() as conn:
            signal_id = await conn.fetchval("""
                INSERT INTO trading_signals (
                    symbol, signal_type, action, confidence,
                    entry_price, stop_loss, take_profit,
                    metadata, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                RETURNING signal_id
            """,
                signal_data['symbol'],
                signal_data['signal_type'],
                signal_data.get('action', 'BUY'),
                signal_data.get('confidence', 0.5),
                signal_data.get('entry_price'),
                signal_data.get('stop_loss'),
                signal_data.get('take_profit'),
                json.dumps(signal_data.get('metadata', {}))
            )
            
            return {"success": True, "signal_id": signal_id}
    except Exception as e:
        logger.error(f"Failed to persist trading signal: {str(e)}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_pending_signals(limit: int = 10, min_confidence: float = 0.6) -> Dict:
    """Get pending trading signals"""
    try:
        async with get_db_connection() as conn:
            signals = await conn.fetch("""
                SELECT * FROM trading_signals
                WHERE status = 'pending'
                AND confidence >= $1
                ORDER BY created_at DESC
                LIMIT $2
            """, min_confidence, limit)
            
            return {
                "success": True,
                "signals": [dict(s) for s in signals]
            }
    except Exception as e:
        return {"success": False, "error": str(e), "signals": []}

# ========== HEALTH CHECK ==========

@mcp.resource("http://health")
async def health_check() -> Dict:
    """Health check endpoint for Docker"""
    return {
        "status": "healthy",
        "service": "database-mcp-service",
        "timestamp": datetime.now().isoformat()
    }

# ========== INITIALIZATION ==========

async def initialize():
    """Initialize database connections and ensure schema"""
    global redis_client
    
    try:
        # Create connection pool
        await get_db_pool()
        
        # Initialize Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = redis.from_url(redis_url)
        
        # Ensure critical tables exist
        async with get_db_connection() as conn:
            # Check if tables exist
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            
            table_names = [t['tablename'] for t in tables]
            logger.info(f"Found {len(table_names)} tables in database")
            
            # Create scan_results table if it doesn't exist
            if 'scan_results' not in table_names:
                logger.warning("Creating scan_results table...")
                await conn.execute("""
                    CREATE TABLE scan_results (
                        scan_id VARCHAR(50),
                        cycle_id INTEGER,
                        symbol VARCHAR(10),
                        scan_time TIMESTAMP,
                        momentum_score FLOAT DEFAULT 0,
                        volume_score FLOAT DEFAULT 0,
                        catalyst_score FLOAT DEFAULT 0,
                        composite_score FLOAT DEFAULT 0,
                        metadata JSONB,
                        PRIMARY KEY (scan_id, symbol)
                    )
                """)
                logger.info("Created scan_results table")
            
            # Create trading_cycles table if it doesn't exist
            if 'trading_cycles' not in table_names:
                logger.warning("Creating trading_cycles table...")
                await conn.execute("""
                    CREATE TABLE trading_cycles (
                        cycle_id SERIAL PRIMARY KEY,
                        scan_type VARCHAR(50),
                        status VARCHAR(20),
                        start_time TIMESTAMP DEFAULT NOW(),
                        end_time TIMESTAMP
                    )
                """)
                logger.info("Created trading_cycles table")
            
            # Create trading_signals table if it doesn't exist
            if 'trading_signals' not in table_names:
                logger.warning("Creating trading_signals table...")
                await conn.execute("""
                    CREATE TABLE trading_signals (
                        signal_id SERIAL PRIMARY KEY,
                        symbol VARCHAR(10),
                        signal_type VARCHAR(50),
                        action VARCHAR(10),
                        confidence FLOAT,
                        entry_price DECIMAL(10,2),
                        stop_loss DECIMAL(10,2),
                        take_profit DECIMAL(10,2),
                        status VARCHAR(20) DEFAULT 'pending',
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                logger.info("Created trading_signals table")
        
        logger.info("Database MCP Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


if __name__ == "__main__":
    # Run initialization
    asyncio.run(initialize())
    
    # Start MCP server
    logger.info("Starting Database MCP Server on port 5010...")
    mcp.run(port=5010)