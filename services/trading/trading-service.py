#!/usr/bin/env python3

# Name of Application: Catalyst Trading System
# Name of file: trading-service.py
# Version: 5.0.1
# Last Updated: 2025-10-07
# Purpose: Trading service with CORRECT v5.0 normalized schema

# REVISION HISTORY:
# v5.0.1 (2025-10-07) - FIXED to match actual v5.0 schema
# - Uses correct trading_cycles columns (mode, total_risk_budget, etc.)
# - Removed references to non-existent columns (cycle_name, initial_capital)
# - Mode values: aggressive/normal/conservative (not paper/live)
# - Stores additional data in configuration JSONB
# 
# v5.0.0 (2025-10-06) - Original (had schema mismatches)

# Description of Service:
# Trading execution service that correctly uses v5.0 normalized schema.
# Manages positions and orders with security_id FKs.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import asyncpg
import json
import os
import logging
import uvicorn
from enum import Enum
from decimal import Decimal

app = FastAPI(
    title="Trading Service",
    version="5.0.1",
    description="Trading execution with CORRECT v5.0 schema"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trading")

# === ENUMS (Match v5.0 Schema) ===
class CycleMode(str, Enum):
    """v5.0 schema modes - NOT paper/live!"""
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    CONSERVATIVE = "conservative"

class CycleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"
    RISK_REDUCED = "risk_reduced"

# === DATA MODELS ===
class CreateCycleRequest(BaseModel):
    """Create cycle matching v5.0 schema"""
    mode: CycleMode = CycleMode.NORMAL
    max_positions: int = 5
    max_daily_loss: float = 2000.00
    position_size_multiplier: float = 1.0
    risk_level: float = 0.02
    total_risk_budget: float = 10000.00  # NOT initial_capital!
    # Additional config goes in JSONB
    config: Dict = {}

class PositionRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

# === STATE ===
class TradingState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None

state = TradingState()

# === STARTUP/SHUTDOWN ===
@app.on_event("startup")
async def startup():
    """Initialize database connection pool"""
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        logger.info("Database pool initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Clean up database connections"""
    if state.db_pool:
        await state.db_pool.close()
        logger.info("Database pool closed")

# === HELPER FUNCTIONS ===
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol"""
    try:
        async with state.db_pool.acquire() as conn:
            security_id = await conn.fetchval(
                "SELECT get_or_create_security($1)", 
                symbol.upper()
            )
            if not security_id:
                raise ValueError(f"Failed to get security_id for {symbol}")
            return security_id
    except Exception as e:
        logger.error(f"get_security_id failed for {symbol}: {e}")
        raise

# === ENDPOINTS ===
@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {
                "status": "healthy",
                "service": "trading",
                "version": "5.0.1",
                "database": "connected",
                "schema": "v5.0 normalized"
            }
        else:
            raise Exception("Database pool not initialized")
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# === TRADING CYCLES (Using CORRECT v5.0 Schema) ===
@app.post("/api/v1/cycles")
async def create_cycle(request: CreateCycleRequest):
    """
    Create trading cycle with CORRECT v5.0 schema columns.
    Uses: mode, total_risk_budget, configuration JSONB
    NOT: cycle_name, initial_capital, available_capital
    """
    try:
        cycle_id = f"api-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Build configuration JSONB (store extra data here)
        config = request.config.copy()
        config.update({
            "created_via": "api",
            "timestamp": datetime.now().isoformat(),
            # Can store cycle_name, initial_capital here if needed
            "display_name": config.get("name", f"Cycle {cycle_id}"),
            "capital_info": {
                "initial": request.total_risk_budget,
                "currency": "USD"
            }
        })
        
        async with state.db_pool.acquire() as conn:
            # Use ACTUAL v5.0 columns
            await conn.execute("""
                INSERT INTO trading_cycles (
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    max_daily_loss,
                    position_size_multiplier,
                    risk_level,
                    scan_frequency,
                    started_at,
                    total_risk_budget,
                    used_risk_budget,
                    current_positions,
                    current_exposure,
                    configuration
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
                cycle_id,
                request.mode.value,  # aggressive/normal/conservative
                CycleStatus.ACTIVE.value,
                request.max_positions,
                request.max_daily_loss,
                request.position_size_multiplier,
                request.risk_level,
                300,  # scan_frequency default
                datetime.now(),
                request.total_risk_budget,  # NOT initial_capital
                Decimal('0.00'),  # used_risk_budget starts at 0
                0,  # current_positions
                Decimal('0.00'),  # current_exposure
                json.dumps(config)  # configuration JSONB
            )
            
        return {
            "cycle_id": cycle_id,
            "mode": request.mode.value,
            "status": "active",
            "total_risk_budget": request.total_risk_budget,
            "message": "Cycle created with v5.0 schema"
        }
        
    except Exception as e:
        logger.error(f"Failed to create cycle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/cycles/active")
async def get_active_cycles():
    """
    Get active cycles using CORRECT v5.0 schema.
    Returns actual columns, calculates available_capital if needed.
    """
    try:
        async with state.db_pool.acquire() as conn:
            cycles = await conn.fetch("""
                SELECT 
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    max_daily_loss,
                    position_size_multiplier,
                    risk_level,
                    total_risk_budget,
                    used_risk_budget,
                    current_positions,
                    current_exposure,
                    started_at,
                    configuration
                FROM trading_cycles
                WHERE status = 'active'
                ORDER BY started_at DESC
            """)
            
            result = []
            for row in cycles:
                # Parse configuration JSONB
                config = json.loads(row['configuration']) if row['configuration'] else {}
                
                # Calculate available capital (not stored directly)
                available_capital = float(row['total_risk_budget'] - row['used_risk_budget'])
                
                result.append({
                    "cycle_id": row['cycle_id'],
                    "mode": row['mode'],  # aggressive/normal/conservative
                    "status": row['status'],
                    "total_risk_budget": float(row['total_risk_budget']),
                    "used_risk_budget": float(row['used_risk_budget']),
                    "available_capital": available_capital,  # calculated
                    "current_positions": row['current_positions'],
                    "max_positions": row['max_positions'],
                    "current_exposure": float(row['current_exposure']),
                    "started_at": row['started_at'].isoformat(),
                    # Pull display name from config if available
                    "display_name": config.get('display_name', row['cycle_id']),
                    "config": config
                })
            
            return result
            
    except Exception as e:
        logger.error(f"Failed to get active cycles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === POSITIONS ===
@app.post("/api/v1/positions")
async def create_position(cycle_id: str, request: PositionRequest):
    """Create position with security_id FK"""
    try:
        # Verify cycle exists and is active
        async with state.db_pool.acquire() as conn:
            cycle = await conn.fetchrow("""
                SELECT mode, status, total_risk_budget, used_risk_budget
                FROM trading_cycles
                WHERE cycle_id = $1 AND status = 'active'
            """, cycle_id)
            
            if not cycle:
                raise HTTPException(status_code=404, detail="Active cycle not found")
            
            # Get security_id
            security_id = await get_security_id(request.symbol)
            
            # Calculate risk amount
            if request.stop_loss and request.entry_price:
                risk_per_share = abs(request.entry_price - request.stop_loss)
                risk_amount = risk_per_share * request.quantity
            else:
                risk_amount = request.entry_price * request.quantity * 0.02
            
            # Create position
            position_id = await conn.fetchval("""
                INSERT INTO positions (
                    cycle_id,
                    security_id,
                    side,
                    quantity,
                    entry_price,
                    stop_loss,
                    take_profit,
                    risk_amount,
                    status,
                    opened_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING position_id
            """,
                cycle_id,
                security_id,
                request.side,
                request.quantity,
                request.entry_price,
                request.stop_loss,
                request.take_profit,
                risk_amount,
                PositionStatus.OPEN.value,
                datetime.now()
            )
            
            # Update cycle metrics
            await conn.execute("""
                UPDATE trading_cycles 
                SET 
                    current_positions = current_positions + 1,
                    used_risk_budget = used_risk_budget + $2,
                    current_exposure = current_exposure + $3,
                    updated_at = NOW()
                WHERE cycle_id = $1
            """, 
                cycle_id, 
                risk_amount,
                request.entry_price * request.quantity
            )
            
            return {
                "position_id": position_id,
                "cycle_id": cycle_id,
                "symbol": request.symbol,
                "security_id": security_id,
                "status": "open",
                "message": "Position created successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/positions")
async def get_positions(status: str = "open"):
    """Get positions with JOINs to get symbols"""
    try:
        async with state.db_pool.acquire() as conn:
            positions = await conn.fetch("""
                SELECT 
                    p.position_id,
                    p.cycle_id,
                    p.security_id,
                    s.symbol,
                    s.company_name,
                    p.side,
                    p.quantity,
                    p.entry_price,
                    p.stop_loss,
                    p.take_profit,
                    p.risk_amount,
                    p.status,
                    p.unrealized_pnl,
                    p.realized_pnl,
                    p.opened_at,
                    p.closed_at
                FROM positions p
                JOIN securities s ON p.security_id = s.security_id
                WHERE p.status = $1
                ORDER BY p.opened_at DESC
            """, status)
            
            return [
                {
                    "position_id": row['position_id'],
                    "cycle_id": row['cycle_id'],
                    "security_id": row['security_id'],
                    "symbol": row['symbol'],
                    "company_name": row['company_name'],
                    "side": row['side'],
                    "quantity": row['quantity'],
                    "entry_price": float(row['entry_price']),
                    "stop_loss": float(row['stop_loss']) if row['stop_loss'] else None,
                    "take_profit": float(row['take_profit']) if row['take_profit'] else None,
                    "risk_amount": float(row['risk_amount']),
                    "status": row['status'],
                    "unrealized_pnl": float(row['unrealized_pnl']) if row['unrealized_pnl'] else 0,
                    "realized_pnl": float(row['realized_pnl']) if row['realized_pnl'] else 0,
                    "opened_at": row['opened_at'].isoformat() if row['opened_at'] else None
                }
                for row in positions
            ]
            
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary using v5.0 schema"""
    try:
        async with state.db_pool.acquire() as conn:
            # Get active cycle
            cycle = await conn.fetchrow("""
                SELECT 
                    cycle_id,
                    mode,
                    total_risk_budget,
                    used_risk_budget,
                    current_positions,
                    current_exposure
                FROM trading_cycles
                WHERE status = 'active'
                ORDER BY started_at DESC
                LIMIT 1
            """)
            
            if not cycle:
                return {
                    "has_active_cycle": False,
                    "message": "No active trading cycle"
                }
            
            # Get position summary
            positions_summary = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as open_positions,
                    COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl,
                    COALESCE(SUM(realized_pnl), 0) as total_realized_pnl
                FROM positions
                WHERE cycle_id = $1 AND status = 'open'
            """, cycle['cycle_id'])
            
            # Calculate available capital
            available_capital = float(cycle['total_risk_budget'] - cycle['used_risk_budget'])
            
            return {
                "cycle_id": cycle['cycle_id'],
                "mode": cycle['mode'],
                "total_risk_budget": float(cycle['total_risk_budget']),
                "used_risk_budget": float(cycle['used_risk_budget']),
                "available_capital": available_capital,
                "current_exposure": float(cycle['current_exposure']),
                "open_positions": positions_summary['open_positions'],
                "unrealized_pnl": float(positions_summary['total_unrealized_pnl']),
                "realized_pnl": float(positions_summary['total_realized_pnl']),
                "total_pnl": float(positions_summary['total_unrealized_pnl'] + 
                                  positions_summary['total_realized_pnl'])
            }
            
    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/orders")
async def get_orders(limit: int = 50):
    """Get recent orders"""
    try:
        async with state.db_pool.acquire() as conn:
            orders = await conn.fetch("""
                SELECT 
                    o.order_id,
                    o.position_id,
                    o.cycle_id,
                    o.security_id,
                    s.symbol,
                    o.side,
                    o.order_type,
                    o.quantity,
                    o.limit_price,
                    o.filled_price,
                    o.status,
                    o.submitted_at,
                    o.filled_at
                FROM orders o
                JOIN securities s ON o.security_id = s.security_id
                ORDER BY o.created_at DESC
                LIMIT $1
            """, limit)
            
            return [
                {
                    "order_id": row['order_id'],
                    "symbol": row['symbol'],
                    "side": row['side'],
                    "quantity": row['quantity'],
                    "status": row['status'],
                    "filled_price": float(row['filled_price']) if row['filled_price'] else None,
                    "submitted_at": row['submitted_at'].isoformat() if row['submitted_at'] else None
                }
                for row in orders
            ]
            
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/risk/cycle/{cycle_id}")
async def get_cycle_risk(cycle_id: str):
    """Get risk metrics for cycle"""
    try:
        async with state.db_pool.acquire() as conn:
            cycle = await conn.fetchrow("""
                SELECT 
                    total_risk_budget,
                    used_risk_budget,
                    max_daily_loss,
                    current_exposure,
                    current_positions,
                    max_positions
                FROM trading_cycles
                WHERE cycle_id = $1
            """, cycle_id)
            
            if not cycle:
                raise HTTPException(status_code=404, detail="Cycle not found")
            
            # Calculate risk metrics
            available_risk = float(cycle['total_risk_budget'] - cycle['used_risk_budget'])
            risk_utilization = float(cycle['used_risk_budget'] / cycle['total_risk_budget']) if cycle['total_risk_budget'] > 0 else 0
            
            return {
                "cycle_id": cycle_id,
                "total_risk_budget": float(cycle['total_risk_budget']),
                "used_risk_budget": float(cycle['used_risk_budget']),
                "available_risk": available_risk,
                "risk_utilization_pct": risk_utilization * 100,
                "max_daily_loss": float(cycle['max_daily_loss']),
                "current_exposure": float(cycle['current_exposure']),
                "position_usage": f"{cycle['current_positions']}/{cycle['max_positions']}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cycle risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === MAIN ===
if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 5002))
    uvicorn.run(app, host="0.0.0.0", port=port)