#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trading-service.py
Version: 4.2.1
Last Updated: 2025-09-20
Purpose: Trading execution service with schema-compliant database queries

REVISION HISTORY:
v4.2.1 (2025-09-20) - Fixed database column mismatch errors
- Fixed "id" column references to use "position_id" (schema compliant)
- Added proper database error handling
- Removed non-existent column queries
- Added paper trading mode for testing
- Schema-compliant with database-schema-mcp-v41.md

Description of Service:
Trading execution service that handles order placement, position management,
and portfolio tracking using proper database schema column names.
"""

from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional
import asyncpg
import asyncio
import logging
from datetime import datetime
import os
import json
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

app = FastAPI(title="Trading Service", version="4.2.1")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global db_pool
    
    # Startup
    logger.info("💰 Starting Trading Service v4.2.1")
    
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL)
            logger.info("✅ Database pool created successfully")
            
            # Load initial positions (with correct column names)
            positions = await get_positions_from_db()
            logger.info(f"📊 Loaded {len(positions)} existing positions")
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            db_pool = None
    
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")

app.router.lifespan_context = lifespan

async def get_positions_from_db() -> List[Dict]:
    """Get all positions from database using correct schema"""
    try:
        if not db_pool:
            return []
        
        async with db_pool.acquire() as conn:
            # FIXED: Use position_id instead of id (schema compliant)
            positions = await conn.fetch("""
                SELECT 
                    position_id,
                    cycle_id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    exit_price,
                    stop_loss,
                    take_profit,
                    status,
                    opened_at,
                    closed_at,
                    unrealized_pnl,
                    realized_pnl,
                    pnl_percent,
                    metadata
                FROM positions 
                WHERE status IN ('open', 'partial')
                ORDER BY opened_at DESC
            """)
            
            return [dict(pos) for pos in positions]
            
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        # Don't raise HTTPException during startup - just return empty list
        return []

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "trading",
        "version": "4.2.1",
        "database": "connected" if db_pool else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/positions")
async def get_positions():
    """Get all active positions"""
    try:
        positions = await get_positions_from_db()
        return {
            "positions": positions,
            "count": len(positions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/positions/{position_id}")
async def get_position(position_id: int):
    """Get specific position by ID"""
    try:
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")
        
        async with db_pool.acquire() as conn:
            # FIXED: Use position_id in WHERE clause
            position = await conn.fetchrow("""
                SELECT 
                    position_id,
                    cycle_id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    exit_price,
                    stop_loss,
                    take_profit,
                    status,
                    opened_at,
                    closed_at,
                    unrealized_pnl,
                    realized_pnl,
                    pnl_percent,
                    metadata
                FROM positions 
                WHERE position_id = $1
            """, position_id)
            
            if not position:
                raise HTTPException(status_code=404, detail="Position not found")
            
            return dict(position)
            
    except Exception as e:
        logger.error(f"Error getting position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/orders")
async def create_order(order_data: dict):
    """Create a new order (paper trading mode for testing)"""
    try:
        symbol = order_data.get('symbol')
        side = order_data.get('side', 'buy')  # buy or sell
        quantity = order_data.get('quantity', 0)
        order_type = order_data.get('order_type', 'market')
        paper = order_data.get('paper', True)  # Default to paper trading
        
        if not symbol or quantity <= 0:
            raise HTTPException(status_code=400, detail="Invalid order parameters")
        
        # Generate order ID
        order_id = f"ord_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}"
        
        if paper:
            # Paper trading simulation
            executed_price = 100.0  # Placeholder price
            
            # For paper trading, we simulate immediate fill
            order_result = {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "status": "filled",
                "executed_price": executed_price,
                "executed_quantity": quantity,
                "paper_trade": True,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store order in database if available
            if db_pool:
                try:
                    async with db_pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO orders (
                                order_id, cycle_id, symbol, direction, order_type,
                                quantity, status, executed_price, executed_quantity,
                                filled_at, metadata, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        """, 
                        order_id, "paper-cycle", symbol, side, order_type,
                        quantity, "filled", executed_price, quantity,
                        datetime.now(), json.dumps({"paper_trade": True}), datetime.now())
                        
                except Exception as db_error:
                    logger.warning(f"Failed to store order in database: {db_error}")
            
            return order_result
        else:
            # Live trading would go here (requires Alpaca/broker integration)
            raise HTTPException(
                status_code=501, 
                detail="Live trading not implemented - use paper=true for testing"
            )
            
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/positions/{position_id}/close")
async def close_position(position_id: int, close_data: dict = None):
    """Close a specific position"""
    try:
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")
        
        close_reason = close_data.get('reason', 'manual_close') if close_data else 'manual_close'
        
        async with db_pool.acquire() as conn:
            # FIXED: Use position_id in WHERE clause
            position = await conn.fetchrow("""
                SELECT position_id, symbol, status FROM positions 
                WHERE position_id = $1 AND status = 'open'
            """, position_id)
            
            if not position:
                raise HTTPException(status_code=404, detail="Open position not found")
            
            # Update position status (simplified for testing)
            await conn.execute("""
                UPDATE positions 
                SET status = 'closed', 
                    closed_at = NOW(),
                    close_reason = $2,
                    updated_at = NOW()
                WHERE position_id = $1
            """, position_id, close_reason)
            
            return {
                "success": True,
                "position_id": position_id,
                "status": "closed",
                "close_reason": close_reason,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error closing position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/positions/{position_id}/stop_loss")
async def update_stop_loss(position_id: int, stop_data: dict):
    """Update stop loss for a position"""
    try:
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")
        
        new_stop_price = stop_data.get('stop_price')
        if not new_stop_price or new_stop_price <= 0:
            raise HTTPException(status_code=400, detail="Invalid stop price")
        
        async with db_pool.acquire() as conn:
            # FIXED: Use position_id in WHERE clause
            result = await conn.execute("""
                UPDATE positions 
                SET stop_loss = $2, updated_at = NOW()
                WHERE position_id = $1 AND status = 'open'
            """, position_id, new_stop_price)
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Open position not found")
            
            return {
                "success": True,
                "position_id": position_id,
                "new_stop_loss": new_stop_price,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error updating stop loss for position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/orders")
async def get_orders(limit: int = 10):
    """Get recent orders"""
    try:
        if not db_pool:
            return {"orders": [], "count": 0}
        
        async with db_pool.acquire() as conn:
            orders = await conn.fetch("""
                SELECT 
                    order_id,
                    symbol,
                    direction,
                    order_type,
                    quantity,
                    status,
                    executed_price,
                    executed_quantity,
                    created_at,
                    filled_at
                FROM orders 
                ORDER BY created_at DESC 
                LIMIT $1
            """, limit)
            
            return {
                "orders": [dict(order) for order in orders],
                "count": len(orders),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary"""
    try:
        positions = await get_positions_from_db()
        
        total_positions = len(positions)
        total_unrealized_pnl = sum(float(pos.get('unrealized_pnl', 0) or 0) for pos in positions)
        
        return {
            "total_positions": total_positions,
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "positions_summary": [
                {
                    "position_id": pos['position_id'],
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "quantity": pos['quantity'],
                    "unrealized_pnl": float(pos.get('unrealized_pnl', 0) or 0)
                }
                for pos in positions
            ],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5005)