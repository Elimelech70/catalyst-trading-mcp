#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: database-mcp-service.py
Version: 3.0.0
Last Updated: 2025-09-18
Purpose: Database MCP service with actual persistence implementation

REVISION HISTORY:
v3.0.0 (2025-09-18) - Fixed missing database persistence
- Implemented actual database operations for persist_scan_results
- Added proper PostgreSQL connection handling
- Fixed data pipeline broken at scanner->database step
- Added cycle_id retrieval for scan results
- Implemented proper error handling

v2.1.0 (2025-08-30) - Auto-converted to FastMCP (stub only)

Description of Service:
MCP database service that handles all database operations for the Catalyst
Trading System. Provides tools for persisting trading data including scan
results, trading signals, positions, and audit logs.
"""

from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import asyncpg
import json
import os
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("database-mcp")

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'catalyst'),
            password=os.getenv('DB_PASSWORD', 'catalyst'),
            database=os.getenv('DB_NAME', 'catalyst_trading'),
            min_size=5,
            max_size=20
        )
    return db_pool


@asynccontextmanager
async def get_db_connection():
    """Get database connection from pool"""
    pool = await get_db_pool()
    async with pool.acquire() as connection:
        yield connection


async def get_active_cycle_id() -> Optional[str]:
    """Get the current active trading cycle ID"""
    async with get_db_connection() as conn:
        result = await conn.fetchrow("""
            SELECT cycle_id FROM trading_cycles 
            WHERE status = 'active' 
            ORDER BY started_at DESC 
            LIMIT 1
        """)
        return result['cycle_id'] if result else None


@mcp.resource("db/status")
async def get_database_status() -> Dict:
    """Get database connection and health status"""
    try:
        async with get_db_connection() as conn:
            # Test database connection
            version = await conn.fetchval("SELECT version()")
            
            # Get basic statistics
            stats = await conn.fetchrow("""
                SELECT 
                    (SELECT COUNT(*) FROM scan_results WHERE scan_time > NOW() - INTERVAL '1 hour') as recent_scans,
                    (SELECT COUNT(*) FROM positions WHERE status = 'open') as open_positions,
                    (SELECT COUNT(*) FROM trading_cycles WHERE status = 'active') as active_cycles
            """)
            
            return {
                "postgresql": {
                    "status": "healthy",
                    "version": version,
                    "connected": True
                },
                "statistics": dict(stats) if stats else {},
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Database status check failed: {str(e)}")
        return {
            "postgresql": {
                "status": "unhealthy",
                "error": str(e),
                "connected": False
            },
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
async def persist_scan_results(scan_data: Dict[str, Any]) -> Dict:
    """
    Persist scan results to database
    
    Args:
        scan_data: Dictionary containing:
            - scan_id: Unique scan identifier
            - timestamp: Scan timestamp
            - candidates: List of candidate dictionaries
            - metadata: Optional scan metadata
    
    Returns:
        Success status and number of records inserted
    """
    try:
        scan_id = scan_data['scan_id']
        timestamp = scan_data['timestamp']
        candidates = scan_data.get('candidates', [])
        metadata = scan_data.get('metadata', {})
        
        # Get active cycle ID
        cycle_id = await get_active_cycle_id()
        if not cycle_id:
            # Create new cycle if none active
            cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            async with get_db_connection() as conn:
                await conn.execute("""
                    INSERT INTO trading_cycles (cycle_id, status, started_at)
                    VALUES ($1, 'active', NOW())
                """, cycle_id)
                logger.info(f"Created new trading cycle: {cycle_id}")
        
        # Prepare batch insert data
        records = []
        for candidate in candidates:
            records.append((
                scan_id,
                cycle_id,
                candidate['symbol'],
                timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp),
                candidate.get('price', 0),
                candidate.get('volume', 0),
                candidate.get('change_percent', 0),
                candidate.get('momentum_score', 0),
                candidate.get('catalyst_score', 0),
                candidate.get('pattern_score', 0),
                candidate.get('technical_score', 0),
                json.dumps(candidate.get('catalysts', [])),
                json.dumps(candidate.get('patterns', [])),
                json.dumps(candidate.get('signals', {})),
                candidate.get('rank', 0) <= 5,  # Top 5 are selected
                candidate.get('rank', 999)
            ))
        
        # Insert scan results
        inserted_count = 0
        if records:
            async with get_db_connection() as conn:
                # Use INSERT ... ON CONFLICT to handle duplicates
                result = await conn.executemany("""
                    INSERT INTO scan_results (
                        scan_id, cycle_id, symbol, scan_time, price, volume,
                        change_percent, momentum_score, catalyst_score,
                        pattern_score, technical_score, catalysts, patterns,
                        signals, is_selected, selection_rank
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 
                        $12::jsonb, $13::jsonb, $14::jsonb, $15, $16
                    )
                    ON CONFLICT (scan_time, scan_id, symbol) 
                    DO UPDATE SET
                        price = EXCLUDED.price,
                        volume = EXCLUDED.volume,
                        change_percent = EXCLUDED.change_percent,
                        momentum_score = EXCLUDED.momentum_score,
                        catalyst_score = EXCLUDED.catalyst_score,
                        pattern_score = EXCLUDED.pattern_score,
                        technical_score = EXCLUDED.technical_score,
                        catalysts = EXCLUDED.catalysts,
                        patterns = EXCLUDED.patterns,
                        signals = EXCLUDED.signals,
                        is_selected = EXCLUDED.is_selected,
                        selection_rank = EXCLUDED.selection_rank
                """, records)
                
                # Get actual insert count (executemany doesn't return count)
                inserted_count = len(records)
                
                # Log audit entry
                await conn.execute("""
                    INSERT INTO audit_log (
                        cycle_id, event_type, event_category, 
                        entity_type, entity_id, details
                    ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """, 
                    cycle_id, 
                    'scan_completed', 
                    'scanner',
                    'scan', 
                    scan_id,
                    json.dumps({
                        'candidates_found': len(candidates),
                        'symbols_scanned': metadata.get('symbols_scanned', 0),
                        'duration': metadata.get('duration', 0),
                        'selected_count': sum(1 for c in candidates if c.get('rank', 999) <= 5)
                    })
                )
        
        logger.info(f"Persisted {inserted_count} scan results for scan_id: {scan_id}")
        
        return {
            "success": True,
            "scan_record_id": scan_id,
            "cycle_id": cycle_id,
            "records_inserted": inserted_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to persist scan results: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
async def get_pending_signals(limit: int = 10, min_confidence: float = 0.7) -> Dict:
    """Get pending trading signals from database"""
    try:
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM trading_signals
                WHERE active = true 
                AND confidence >= $1
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY confidence DESC, created_at DESC
                LIMIT $2
            """, min_confidence, limit)
            
            signals = [dict(row) for row in rows]
            
            return {
                "success": True,
                "signals": signals,
                "count": len(signals)
            }
    except Exception as e:
        logger.error(f"Failed to get pending signals: {str(e)}")
        return {
            "success": False,
            "signals": [],
            "error": str(e)
        }


@mcp.tool()
async def get_open_positions() -> Dict:
    """Get all open trading positions"""
    try:
        cycle_id = await get_active_cycle_id()
        if not cycle_id:
            return {
                "success": True,
                "positions": [],
                "message": "No active trading cycle"
            }
        
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM positions
                WHERE status = 'open'
                AND cycle_id = $1
                ORDER BY opened_at DESC
            """, cycle_id)
            
            positions = [dict(row) for row in rows]
            
            return {
                "success": True,
                "positions": positions,
                "count": len(positions)
            }
    except Exception as e:
        logger.error(f"Failed to get open positions: {str(e)}")
        return {
            "success": False,
            "positions": [],
            "error": str(e)
        }


@mcp.tool()
async def persist_trading_signal(signal_data: Dict[str, Any]) -> Dict:
    """Persist a new trading signal"""
    try:
        cycle_id = await get_active_cycle_id()
        if not cycle_id:
            return {
                "success": False,
                "error": "No active trading cycle"
            }
        
        async with get_db_connection() as conn:
            signal_id = await conn.fetchval("""
                INSERT INTO trading_signals (
                    cycle_id, symbol, signal_type, action, confidence,
                    entry_price, stop_loss, take_profit, metadata, expires_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
                RETURNING signal_id
            """,
                cycle_id,
                signal_data['symbol'],
                signal_data.get('signal_type', 'technical'),
                signal_data['action'],
                signal_data['confidence'],
                signal_data.get('entry_price'),
                signal_data.get('stop_loss'),
                signal_data.get('take_profit'),
                json.dumps(signal_data.get('metadata', {})),
                signal_data.get('expires_at')
            )
            
            logger.info(f"Created trading signal {signal_id} for {signal_data['symbol']}")
            
            return {
                "success": True,
                "signal_id": signal_id
            }
    except Exception as e:
        logger.error(f"Failed to persist trading signal: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.resource("db/metrics")
async def get_database_metrics(timeframe: str = "1h") -> Dict:
    """Get database performance metrics"""
    try:
        async with get_db_connection() as conn:
            # Parse timeframe
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


async def initialize():
    """Initialize database connections and ensure schema"""
    try:
        # Create connection pool
        await get_db_pool()
        
        # Ensure critical tables exist
        async with get_db_connection() as conn:
            # Check if tables exist
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            
            table_names = [t['tablename'] for t in tables]
            logger.info(f"Found {len(table_names)} tables in database")
            
            # Verify critical tables
            required_tables = ['trading_cycles', 'scan_results', 'positions', 
                             'trading_signals', 'audit_log']
            missing = [t for t in required_tables if t not in table_names]
            
            if missing:
                logger.warning(f"Missing tables: {missing}")
                logger.warning("Please run database migrations to create required tables")
            else:
                logger.info("All required tables present")
        
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
