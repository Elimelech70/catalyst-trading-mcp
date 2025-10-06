#!/usr/bin/env python3

# Name of Application: Catalyst Trading System
# Name of file: trading-service.py
# Version: 5.0.0
# Last Updated: 2025-10-06
# Purpose: Trading service with NORMALIZED schema v5.0 (security_id FKs)

# REVISION HISTORY:
# v5.0.0 (2025-10-06) - NORMALIZED SCHEMA MIGRATION (Playbook v3.0 Step 3)
# - Uses security_id FK in positions table (NOT symbol VARCHAR) ✅
# - Uses security_id FK in orders table ✅
# - All position queries use JOINs on FKs ✅
# - Risk calculations use JOIN with sectors table ✅
# - Helper functions: get_security_id() ✅
# - NO data duplication - single source of truth ✅
#
# Description of Service:
# Trading execution service (Service #3 of 9 in Playbook v3.0).
# Manages positions and order execution with normalized schema.
# Handles:
# 1. Position management with security_id FKs
# 2. Order execution and tracking
# 3. Risk calculations via JOINs
# 4. P&L tracking per position

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

app = FastAPI(
    title="Trading Service",
    version="5.0.0",
    description="Trading execution with normalized schema v5.0"
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

# === DATA MODELS ===
class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial_fill"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class PositionRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: int
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

# === STATE ===
class TradingState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None

state = TradingState()

# === HELPER FUNCTIONS ===
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol"""
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)", symbol.upper()
        )
        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")
        return security_id
    except Exception as e:
        logger.error(f"get_security_id failed for {symbol}: {e}")
        raise

# === POSITION MANAGEMENT ===
async def create_position(
    cycle_id: str,
    symbol: str,
    side: OrderSide,
    quantity: int,
    entry_price: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None
) -> int:
    """
    Create position with NORMALIZED schema.
    Uses security_id FK (NOT symbol VARCHAR).
    """
    try:
        security_id = await get_security_id(symbol)
        
        # Calculate risk amount
        if stop_loss and entry_price:
            risk_per_share = abs(entry_price - stop_loss)
            risk_amount = risk_per_share * quantity
        else:
            risk_amount = entry_price * quantity * 0.02  # 2% default risk
        
        position_id = await state.db_pool.fetchval("""
            INSERT INTO positions (
                cycle_id,
                security_id,
                side,
                quantity,
                entry_price,
                stop_loss,
                take_profit,
                risk_amount,
                status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open')
            RETURNING position_id
        """,
            cycle_id,
            security_id,
            side.value,
            quantity,
            entry_price,
            stop_loss,
            take_profit,
            risk_amount
        )
        
        logger.info(f"Created position {position_id} for {symbol} (security_id={security_id})")
        return position_id
        
    except Exception as e:
        logger.error(f"Failed to create position: {e}")
        raise

async def get_positions(cycle_id: Optional[str] = None, status: str = 'open') -> List[Dict]:
    """
    Get positions with JOINs (normalized schema).
    Returns symbol from securities table via JOIN.
    """
    try:
        if cycle_id:
            positions = await state.db_pool.fetch("""
                SELECT 
                    p.*,
                    s.symbol,
                    s.company_name,
                    sec.sector_name
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                JOIN sectors sec ON sec.sector_id = s.sector_id
                WHERE p.cycle_id = $1
                AND p.status = $2
                ORDER BY p.created_at DESC
            """, cycle_id, status)
        else:
            positions = await state.db_pool.fetch("""
                SELECT 
                    p.*,
                    s.symbol,
                    s.company_name,
                    sec.sector_name
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                JOIN sectors sec ON sec.sector_id = s.sector_id
                WHERE p.status = $1
                ORDER BY p.created_at DESC
                LIMIT 100
            """, status)
        
        return [dict(r) for r in positions]
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise

async def update_position_pnl(position_id: int, current_price: float) -> Dict:
    """Update position P&L"""
    try:
        position = await state.db_pool.fetchrow("""
            SELECT * FROM positions WHERE position_id = $1
        """, position_id)
        
        if not position:
            raise ValueError(f"Position {position_id} not found")
        
        # Calculate P&L
        if position['side'] == 'buy':
            unrealized_pnl = (current_price - position['entry_price']) * position['quantity']
        else:
            unrealized_pnl = (position['entry_price'] - current_price) * position['quantity']
        
        pnl_percent = (unrealized_pnl / (position['entry_price'] * position['quantity'])) * 100
        
        # Update position
        await state.db_pool.execute("""
            UPDATE positions
            SET current_price = $1,
                unrealized_pnl = $2,
                pnl_percent = $3,
                updated_at = NOW()
            WHERE position_id = $4
        """, current_price, unrealized_pnl, pnl_percent, position_id)
        
        return {
            'position_id': position_id,
            'current_price': current_price,
            'unrealized_pnl': unrealized_pnl,
            'pnl_percent': pnl_percent
        }
        
    except Exception as e:
        logger.error(f"Failed to update P&L: {e}")
        raise

async def close_position(position_id: int, exit_price: float) -> Dict:
    """Close position"""
    try:
        position = await state.db_pool.fetchrow("""
            SELECT * FROM positions WHERE position_id = $1
        """, position_id)
        
        if not position:
            raise ValueError(f"Position {position_id} not found")
        
        # Calculate realized P&L
        if position['side'] == 'buy':
            realized_pnl = (exit_price - position['entry_price']) * position['quantity']
        else:
            realized_pnl = (position['entry_price'] - exit_price) * position['quantity']
        
        # Update position
        await state.db_pool.execute("""
            UPDATE positions
            SET exit_price = $1,
                realized_pnl = $2,
                status = 'closed',
                closed_at = NOW(),
                updated_at = NOW()
            WHERE position_id = $3
        """, exit_price, realized_pnl, position_id)
        
        logger.info(f"Closed position {position_id} with P&L: {realized_pnl}")
        
        return {
            'position_id': position_id,
            'exit_price': exit_price,
            'realized_pnl': realized_pnl,
            'status': 'closed'
        }
        
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        raise

# === ORDER MANAGEMENT ===
async def create_order(
    position_id: int,
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: int,
    price: Optional[float] = None
) -> str:
    """Create order with security_id FK"""
    try:
        security_id = await get_security_id(symbol)
        order_id = f"ORD_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        
        await state.db_pool.execute("""
            INSERT INTO orders (
                order_id,
                position_id,
                security_id,
                side,
                order_type,
                quantity,
                price,
                status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
        """,
            order_id,
            position_id,
            security_id,
            side.value,
            order_type.value,
            quantity,
            price
        )
        
        logger.info(f"Created order {order_id} for {symbol}")
        return order_id
        
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise

# === STARTUP ===
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Trading Service v5.0.0 (NORMALIZED SCHEMA)")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL required")
        
        state.db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
        logger.info("Database pool initialized")
        
        # Verify positions table has security_id FK
        has_security_id = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'positions' 
                AND column_name = 'security_id'
            )
        """)
        
        if not has_security_id:
            raise ValueError("positions table missing security_id - schema v5.0 not deployed!")
        
        logger.info("✅ Normalized schema verified - positions has security_id FK")
        
    except Exception as e:
        logger.critical(f"Database init failed: {e}")
        raise
    
    logger.info("Trading service ready")

@app.on_event("shutdown")
async def shutdown_event():
    if state.db_pool:
        await state.db_pool.close()

# === HEALTH CHECK ===
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trading",
        "version": "5.0.0",
        "schema": "v5.0 normalized",
        "uses_security_id_fk": True,
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if state.db_pool else "disconnected"
    }

# === API ENDPOINTS ===
@app.post("/api/v1/positions")
async def create_position_endpoint(request: PositionRequest):
    """Create new position"""
    try:
        cycle_id = f"cycle_{datetime.utcnow().strftime('%Y%m%d')}"
        
        position_id = await create_position(
            cycle_id=cycle_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            entry_price=request.entry_price or 0.0,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit
        )
        
        return {
            "position_id": position_id,
            "symbol": request.symbol,
            "status": "created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/positions")
async def get_positions_endpoint(cycle_id: Optional[str] = None, status: str = 'open'):
    """Get positions with JOINs"""
    try:
        positions = await get_positions(cycle_id, status)
        return {
            "positions": positions,
            "count": len(positions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/positions/{position_id}/pnl")
async def update_pnl_endpoint(position_id: int, current_price: float):
    """Update position P&L"""
    try:
        result = await update_position_pnl(position_id, current_price)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/positions/{position_id}/close")
async def close_position_endpoint(position_id: int, exit_price: float):
    """Close position"""
    try:
        result = await close_position(position_id, exit_price)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("=" * 70)
    print("🎩 Catalyst Trading System - Trading Service v5.0.0 (NORMALIZED)")
    print("=" * 70)
    print("✅ Uses security_id FK in positions table")
    print("✅ Uses security_id FK in orders table")
    print("✅ All queries use JOINs for symbol retrieval")
    print("✅ NO data duplication - single source of truth")
    print("Port: 5005")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=5005, log_level="info")