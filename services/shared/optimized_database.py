#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: optimized_database.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Shared optimized database manager for all services

REVISION HISTORY:
v4.2.0 (2025-09-20) - Optimized connection management
- Service-specific connection limits
- DigitalOcean PostgreSQL optimization
- Connection monitoring and health checks
- Memory and timeout optimizations

Description of Service:
Provides optimized database connection management for all Catalyst Trading
services to prevent connection pool exhaustion on DigitalOcean managed PostgreSQL.
"""

import asyncpg
import os
from typing import Optional, Dict
from datetime import datetime
import structlog

logger = structlog.get_logger()

# === OPTIMIZED CONNECTION ALLOCATION ===
# DigitalOcean Professional PostgreSQL: ~100 total connections
# Reserve 20 for superuser/admin operations
# Allocate 80 connections across 8 services

SERVICE_CONNECTION_LIMITS = {
    "orchestration": {"min": 2, "max": 5},   # MCP + workflow coordination
    "scanner": {"min": 2, "max": 8},         # High activity during scans
    "pattern": {"min": 1, "max": 4},         # Moderate usage
    "technical": {"min": 1, "max": 4},       # Moderate usage  
    "risk_manager": {"min": 2, "max": 6},    # Critical safety service
    "trading": {"min": 2, "max": 8},         # High activity during trades
    "news": {"min": 1, "max": 3},            # Low database usage
    "reporting": {"min": 1, "max": 5},       # Periodic batch operations
    
    # Total allocated: min=12, max=43 (well under 80 limit)
}

class OptimizedDatabaseManager:
    """Optimized database manager for DigitalOcean environment"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.pool: Optional[asyncpg.Pool] = None
        
        # Get service-specific limits
        if service_name not in SERVICE_CONNECTION_LIMITS:
            logger.warning(f"Unknown service {service_name}, using default limits")
            self.limits = {"min": 1, "max": 3}
        else:
            self.limits = SERVICE_CONNECTION_LIMITS[service_name]
            
    async def initialize(self, database_url: str = None) -> bool:
        """Initialize optimized connection pool"""
        try:
            url = database_url or os.getenv("DATABASE_URL")
            if not url:
                raise ValueError("DATABASE_URL not provided")
            
            # Create pool with service-specific limits
            self.pool = await asyncpg.create_pool(
                url,
                min_size=self.limits["min"],
                max_size=self.limits["max"],
                max_queries=50000,
                max_inactive_connection_lifetime=300,  # 5 minutes
                command_timeout=30,                     # Reduced timeout
                statement_cache_size=0,                 # Save memory
                setup=self._setup_connection
            )
            
            # Test connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            logger.info(
                "Database pool initialized",
                service=self.service_name,
                min_connections=self.limits["min"],
                max_connections=self.limits["max"]
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database for {self.service_name}: {e}")
            return False
    
    async def _setup_connection(self, conn):
        """Setup each connection with optimizations"""
        # Set connection-specific optimizations
        await conn.execute("SET statement_timeout = '30s'")
        await conn.execute("SET lock_timeout = '10s'")
        await conn.execute("SET idle_in_transaction_session_timeout = '60s'")
    
    async def execute(self, query: str, *args, timeout: float = None):
        """Execute a query"""
        if not self.pool:
            raise RuntimeError(f"Database pool not initialized for {self.service_name}")
        
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
    
    async def fetch(self, query: str, *args, timeout: float = None):
        """Fetch multiple rows"""
        if not self.pool:
            raise RuntimeError(f"Database pool not initialized for {self.service_name}")
        
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
    async def fetchrow(self, query: str, *args, timeout: float = None):
        """Fetch single row"""
        if not self.pool:
            raise RuntimeError(f"Database pool not initialized for {self.service_name}")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
    
    async def fetchval(self, query: str, *args, timeout: float = None):
        """Fetch single value"""
        if not self.pool:
            raise RuntimeError(f"Database pool not initialized for {self.service_name}")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)
    
    async def get_connection_stats(self) -> Dict:
        """Get current connection pool statistics"""
        if not self.pool:
            return {"error": "Pool not initialized"}
        
        return {
            "service": self.service_name,
            "size": self.pool.get_size(),
            "min_size": self.pool.get_min_size(),
            "max_size": self.pool.get_max_size(),
            "idle_size": self.pool.get_idle_size(),
            "limits": self.limits
        }
    
    async def health_check(self) -> Dict:
        """Check database health for this service"""
        try:
            if not self.pool:
                return {"healthy": False, "error": "Pool not initialized"}
            
            start_time = datetime.now()
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "healthy": True,
                "service": self.service_name,
                "response_time_ms": round(response_time, 2),
                "pool_stats": await self.get_connection_stats()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "service": self.service_name,
                "error": str(e)
            }
    
    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info(f"Database pool closed for {self.service_name}")

# === USAGE EXAMPLE ===
"""
# In any service file (scanner-service.py, trading-service.py, etc.):

from services.shared.optimized_database import OptimizedDatabaseManager

# Replace existing database initialization with:
db_manager = OptimizedDatabaseManager("scanner")  # Use your service name
await db_manager.initialize()

# Use instead of direct pool operations:
result = await db_manager.fetchval("SELECT COUNT(*) FROM trading_cycles")
rows = await db_manager.fetch("SELECT * FROM positions WHERE status = 'open'")
await db_manager.execute("INSERT INTO scan_results ...")
"""