#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: database_utils.py
Version: 1.0.0
Last Updated: 2025-08-18
Purpose: Shared database utilities for all MCP services

REVISION HISTORY:
v1.0.0 (2025-08-18) - Initial implementation
- Database connection pooling
- Health check functions
- Trading cycle management
- Service health tracking
- Workflow logging utilities

Description of Service:
Provides database connection management and common database operations
for all services in the Catalyst Trading System. Uses PostgreSQL connection
pooling for efficient resource usage.
"""

import os
import json
import psycopg2
import psycopg2.extras
from psycopg2 import pool
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

# Set up logging
logger = logging.getLogger(__name__)

# Global connection pool
_db_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None


def init_db_pool(min_connections: int = 1, max_connections: int = 20) -> None:
    """Initialize the database connection pool"""
    global _db_pool
    
    if _db_pool is not None:
        logger.warning("Database pool already initialized")
        return
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    try:
        _db_pool = psycopg2.pool.SimpleConnectionPool(
            min_connections,
            max_connections,
            database_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        logger.info(f"Database connection pool initialized with {min_connections}-{max_connections} connections")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {str(e)}")
        raise


def get_db_pool() -> psycopg2.pool.SimpleConnectionPool:
    """Get the database connection pool, initializing if necessary"""
    global _db_pool
    if _db_pool is None:
        init_db_pool()
    return _db_pool


@contextmanager
def get_db_connection():
    """Get a database connection from the pool (context manager)"""
    pool = get_db_pool()
    conn = None
    try:
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        if conn:
            pool.putconn(conn)


def create_trading_cycle(cycle_data: Dict[str, Any]) -> str:
    """Create a new trading cycle"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trading_cycles 
                (scan_type, target_securities, status, config, start_time)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING cycle_id
            """, (
                cycle_data.get('scan_type', 'regular'),
                cycle_data.get('target_securities', 50),
                'active',
                json.dumps(cycle_data.get('config', {})),
                datetime.utcnow()
            ))
            cycle_id = cur.fetchone()['cycle_id']
            
            logger.info(f"Created trading cycle: {cycle_id}")
            return cycle_id


def update_trading_cycle(cycle_id: str, updates: Dict[str, Any]) -> None:
    """Update trading cycle information"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Build dynamic update query
            update_fields = []
            values = []
            
            if 'status' in updates:
                update_fields.append("status = %s")
                values.append(updates['status'])
                
            if 'end_time' in updates:
                update_fields.append("end_time = %s")
                values.append(updates['end_time'])
                
            if 'candidates_found' in updates:
                update_fields.append("candidates_found = %s")
                values.append(updates['candidates_found'])
                
            if 'trades_executed' in updates:
                update_fields.append("trades_executed = %s")
                values.append(updates['trades_executed'])
                
            if 'total_pnl' in updates:
                update_fields.append("total_pnl = %s")
                values.append(updates['total_pnl'])
                
            if 'errors' in updates:
                update_fields.append("errors = %s")
                values.append(json.dumps(updates['errors']))
            
            if update_fields:
                values.append(cycle_id)
                query = f"UPDATE trading_cycles SET {', '.join(update_fields)} WHERE cycle_id = %s"
                cur.execute(query, values)
                
                logger.info(f"Updated trading cycle {cycle_id}: {updates}")


def update_service_health(service_name: str, status: str, details: Optional[Dict] = None) -> None:
    """Update service health status"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO service_health 
                (service_name, status, last_check, details)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (service_name) 
                DO UPDATE SET 
                    status = EXCLUDED.status,
                    last_check = EXCLUDED.last_check,
                    details = EXCLUDED.details
            """, (
                service_name,
                status,
                datetime.utcnow(),
                json.dumps(details or {})
            ))
            
            logger.debug(f"Updated health for {service_name}: {status}")


def get_service_health(service_name: str) -> Optional[Dict[str, Any]]:
    """Get service health status"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT service_name, status, last_check, details 
                FROM service_health 
                WHERE service_name = %s
            """, (service_name,))
            
            result = cur.fetchone()
            if result:
                return dict(result)
            return None


def health_check() -> Dict[str, Any]:
    """Perform database health check"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Test basic query
                cur.execute("SELECT 1")
                
                # Get database info
                cur.execute("SELECT current_database(), version()")
                db_info = cur.fetchone()
                
                # Get connection stats
                cur.execute("""
                    SELECT count(*) as active_connections 
                    FROM pg_stat_activity 
                    WHERE datname = current_database()
                """)
                conn_stats = cur.fetchone()
                
        return {
            'status': 'healthy',
            'database': db_info['current_database'],
            'active_connections': conn_stats['active_connections'],
            'pool_status': 'active',
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


def log_workflow_step(cycle_id: str, step: str, status: str, **kwargs) -> None:
    """Log workflow step execution"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            details = {
                'timestamp': datetime.utcnow().isoformat(),
                **kwargs
            }
            
            cur.execute("""
                INSERT INTO workflow_logs 
                (cycle_id, step_name, status, timestamp, details)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                cycle_id,
                step,
                status,
                datetime.utcnow(),
                json.dumps(details)
            ))
            
            logger.info(f"Logged workflow step: {cycle_id}/{step} - {status}")


# Additional utility functions that services might need

def get_active_cycles() -> List[Dict[str, Any]]:
    """Get all active trading cycles"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM trading_cycles 
                WHERE status = 'active' 
                ORDER BY start_time DESC
            """)
            return [dict(row) for row in cur.fetchall()]


def get_latest_cycle() -> Optional[Dict[str, Any]]:
    """Get the most recent trading cycle"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM trading_cycles 
                ORDER BY start_time DESC 
                LIMIT 1
            """)
            result = cur.fetchone()
            return dict(result) if result else None


def cleanup_old_logs(days_to_keep: int = 30) -> int:
    """Clean up old workflow logs"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM workflow_logs 
                WHERE timestamp < NOW() - INTERVAL '%s days'
                RETURNING 1
            """, (days_to_keep,))
            
            deleted_count = cur.rowcount
            logger.info(f"Cleaned up {deleted_count} old workflow logs")
            return deleted_count


def execute_query(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Execute a raw query (use with caution)"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []


# Initialize the pool when the module is imported
# (This can be disabled if you want manual initialization)
if os.getenv('AUTO_INIT_DB_POOL', 'true').lower() == 'true':
    try:
        init_db_pool()
    except Exception as e:
        logger.warning(f"Failed to auto-initialize database pool: {str(e)}")