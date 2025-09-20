#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trading-service.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: FIXED Trading execution service with corrected Position model

REVISION HISTORY:
v4.2.0 (2025-09-20) - CRITICAL BUG FIXES
- Fixed Position model attribute error (realized_pl -> realized_pnl)
- Corrected API endpoints to match specification
- Fixed database field mappings
- Enhanced error handling and validation
- Optimized database connections

Description of Service:
Trading execution service that handles order placement, position management,
and portfolio tracking. Integrates with Alpaca API for live trading.
Fixes critical bugs in position handling and database operations.
"""

import os
import asyncio
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import logging
from enum import Enum
import alpaca_trade_api as tradeapi
from decimal import Decimal
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("trading-service")

# FastAPI app
app = FastAPI(
    title="Trading Execution Service",
    version="4.2.0",
    description="Trading execution service for Catalyst Trading System"
)

# Global connections
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
alpaca_client: Optional[tradeapi.REST] = None

# === PYDANTIC MODELS ===

class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"

class OrderType(str, Enum):
    market = "market"
    limit = "limit"
    stop = "stop"
    stop_limit = "stop_limit"
    trailing_stop = "trailing_stop"

class TimeInForce(str, Enum):
    day = "day"
    gtc = "gtc"
    ioc = "ioc"
    fok = "fok"

class ExecuteOrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: Optional[int] = None
    order_type: OrderType = OrderType.market
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.day
    position_size_pct: Optional[float] = Field(None, ge=0.01, le=1.0)
    risk_amount: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class ExecuteSignalRequest(BaseModel):
    signal: Dict[str, Any]
    risk_level: float = Field(0.02, ge=0.001, le=0.05)

class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    status: str
    submitted_at: datetime
    filled_price: Optional[float] = None
    commission: Optional[float] = None

class PositionResponse(BaseModel):
    position_id: str
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float  # FIXED: was unrealized_pl
    realized_pnl: float    # FIXED: was realized_pl
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

# === DATABASE CONNECTION ===

async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global db_pool
    if not db_pool:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        logger.info("Creating database connection pool...")
        try:
            db_pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=8,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                command_timeout=30
            )
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    return db_pool

async def get_redis_client() -> redis.Redis:
    """Get or create Redis client"""
    global redis_client
    if not redis_client:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = await redis.from_url(
            redis_url,
            encoding='utf-8',
            decode_responses=True
        )
        logger.info("Redis client created")
    
    return redis_client

def get_alpaca_client() -> tradeapi.REST:
    """Get or create Alpaca client"""
    global alpaca_client
    if not alpaca_client:
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        if not api_key or not secret_key:
            raise ValueError("Alpaca API credentials not configured")
        
        alpaca_client = tradeapi.REST(
            api_key,
            secret_key,
            base_url,
            api_version='v2'
        )
        logger.info("Alpaca client created")
    
    return alpaca_client

# === HELPER FUNCTIONS ===

async def get_current_price(symbol: str) -> float:
    """Get current market price for symbol"""
    try:
        alpaca = get_alpaca_client()
        quote = alpaca.get_latest_quote(symbol)
        return float(quote.bid_price + quote.ask_price) / 2  # Mid price
    except Exception as e:
        logger.error(f"Failed to get price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get price for {symbol}")

async def calculate_position_size(
    symbol: str,
    risk_amount: float,
    entry_price: float,
    stop_loss: float,
    position_size_pct: Optional[float] = None
) -> int:
    """Calculate position size based on risk parameters"""
    try:
        alpaca = get_alpaca_client()
        account = alpaca.get_account()
        buying_power = float(account.buying_power)
        
        if position_size_pct:
            # Use percentage of buying power
            position_value = buying_power * position_size_pct
            quantity = int(position_value / entry_price)
        else:
            # Use risk-based sizing
            risk_per_share = abs(entry_price - stop_loss)
            if risk_per_share <= 0:
                raise ValueError("Invalid stop loss price")
            
            quantity = int(risk_amount / risk_per_share)
        
        # Ensure minimum quantity and maximum position size
        quantity = max(1, min(quantity, int(buying_power * 0.1 / entry_price)))
        
        return quantity
        
    except Exception as e:
        logger.error(f"Failed to calculate position size: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate position size")

async def store_order(order_data: Dict[str, Any]) -> str:
    """Store order in database"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            order_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO orders (
                    id, symbol, side, quantity, order_type, status,
                    submitted_at, alpaca_order_id, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
                order_id,
                order_data['symbol'],
                order_data['side'],
                order_data['quantity'],
                order_data['order_type'],
                order_data['status'],
                datetime.now(),
                order_data.get('alpaca_order_id'),
                json.dumps(order_data)
            )
            return order_id
    except Exception as e:
        logger.error(f"Failed to store order: {e}")
        raise

async def get_positions_from_db() -> List[Dict[str, Any]]:
    """Get positions from database with FIXED field names"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id as position_id,
                    symbol,
                    quantity,
                    entry_price,
                    current_price,
                    unrealized_pnl,  -- FIXED: correct field name
                    realized_pnl,    -- FIXED: correct field name
                    stop_loss,
                    take_profit,
                    status,
                    opened_at
                FROM positions 
                WHERE status = 'open'
                ORDER BY opened_at DESC
            """)
            
            positions = []
            for row in rows:
                # Get current price for each position
                try:
                    current_price = await get_current_price(row['symbol'])
                    unrealized_pnl = (current_price - row['entry_price']) * row['quantity']
                except:
                    current_price = row['current_price']
                    unrealized_pnl = row['unrealized_pnl']
                
                positions.append({
                    'position_id': row['position_id'],
                    'symbol': row['symbol'],
                    'quantity': row['quantity'],
                    'entry_price': float(row['entry_price']),
                    'current_price': float(current_price),
                    'unrealized_pnl': float(unrealized_pnl),
                    'realized_pnl': float(row['realized_pnl'] or 0),
                    'stop_loss': float(row['stop_loss']) if row['stop_loss'] else None,
                    'take_profit': float(row['take_profit']) if row['take_profit'] else None
                })
            
            return positions
            
    except Exception as e:
        logger.error(f"Failed to get positions from database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")

# === API ENDPOINTS ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # Test Alpaca connection
        alpaca = get_alpaca_client()
        account = alpaca.get_account()
        
        return {
            "status": "healthy",
            "service": "trading",
            "version": "4.2.0",
            "alpaca_status": account.status,
            "buying_power": float(account.buying_power),
            "active_positions": len(await get_positions_from_db()),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/api/v1/orders/execute", response_model=OrderResponse)
async def execute_order(request: ExecuteOrderRequest):
    """Execute a trading order"""
    try:
        alpaca = get_alpaca_client()
        
        # Get current price
        current_price = await get_current_price(request.symbol)
        
        # Calculate quantity if not provided
        if not request.quantity:
            if not request.position_size_pct and not request.risk_amount:
                raise HTTPException(status_code=400, detail="Must specify quantity, position_size_pct, or risk_amount")
            
            stop_loss = request.stop_loss or (current_price * 0.98 if request.side == OrderSide.buy else current_price * 1.02)
            risk_amount = request.risk_amount or 100  # Default $100 risk
            
            request.quantity = await calculate_position_size(
                request.symbol,
                risk_amount,
                current_price,
                stop_loss,
                request.position_size_pct
            )
        
        # Execute order with Alpaca
        alpaca_order = alpaca.submit_order(
            symbol=request.symbol,
            qty=request.quantity,
            side=request.side.value,
            type=request.order_type.value,
            time_in_force=request.time_in_force.value,
            limit_price=request.limit_price,
            stop_price=request.stop_price
        )
        
        # Store order in database
        order_data = {
            'symbol': request.symbol,
            'side': request.side.value,
            'quantity': request.quantity,
            'order_type': request.order_type.value,
            'status': alpaca_order.status,
            'alpaca_order_id': alpaca_order.id,
            'limit_price': request.limit_price,
            'stop_price': request.stop_price,
            'stop_loss': request.stop_loss,
            'take_profit': request.take_profit
        }
        
        order_id = await store_order(order_data)
        
        return OrderResponse(
            order_id=order_id,
            symbol=request.symbol,
            side=request.side.value,
            quantity=request.quantity,
            order_type=request.order_type.value,
            status=alpaca_order.status,
            submitted_at=alpaca_order.submitted_at,
            filled_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
            commission=None  # Alpaca doesn't charge commissions
        )
        
    except Exception as e:
        logger.error(f"Failed to execute order: {e}")
        raise HTTPException(status_code=500, detail=f"Order execution failed: {str(e)}")

@app.post("/api/v1/orders/execute/signal")
async def execute_signal(request: ExecuteSignalRequest):
    """Execute a trading signal"""
    try:
        signal = request.signal
        
        # Extract signal data
        symbol = signal.get('symbol')
        entry_price = signal.get('entry_price') or signal.get('entry')
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')
        confidence = signal.get('confidence', 0.5)
        
        if not symbol or not entry_price:
            raise HTTPException(status_code=400, detail="Signal must include symbol and entry_price")
        
        # Calculate position size based on risk level and confidence
        account = get_alpaca_client().get_account()
        buying_power = float(account.buying_power)
        risk_amount = buying_power * request.risk_level * confidence
        
        # Create order request
        order_request = ExecuteOrderRequest(
            symbol=symbol,
            side=OrderSide.buy,  # Assuming buy signals for now
            risk_amount=risk_amount,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Execute the order
        return await execute_order(order_request)
        
    except Exception as e:
        logger.error(f"Failed to execute signal: {e}")
        raise HTTPException(status_code=500, detail=f"Signal execution failed: {str(e)}")

@app.get("/api/v1/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get all active positions"""
    try:
        positions = await get_positions_from_db()
        return [PositionResponse(**pos) for pos in positions]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")

@app.get("/api/v1/positions/{position_id}")
async def get_position(position_id: str):
    """Get specific position details"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM positions WHERE id = $1
            """, position_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Position not found")
            
            # Get current price and calculate unrealized P&L
            current_price = await get_current_price(row['symbol'])
            unrealized_pnl = (current_price - row['entry_price']) * row['quantity']
            
            return {
                'position_id': row['id'],
                'symbol': row['symbol'],
                'quantity': row['quantity'],
                'entry_price': float(row['entry_price']),
                'current_price': float(current_price),
                'unrealized_pnl': float(unrealized_pnl),
                'realized_pnl': float(row['realized_pnl'] or 0),
                'stop_loss': float(row['stop_loss']) if row['stop_loss'] else None,
                'take_profit': float(row['take_profit']) if row['take_profit'] else None,
                'status': row['status'],
                'opened_at': row['opened_at'].isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get position: {str(e)}")

@app.post("/api/v1/positions/close")
async def close_position(position_id: str):
    """Close a specific position"""
    try:
        # Get position details
        position = await get_position(position_id)
        
        # Execute closing order
        alpaca = get_alpaca_client()
        side = "sell" if position['quantity'] > 0 else "buy"
        
        alpaca_order = alpaca.submit_order(
            symbol=position['symbol'],
            qty=abs(position['quantity']),
            side=side,
            type='market',
            time_in_force='day'
        )
        
        # Update position in database
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions 
                SET status = 'closed', closed_at = $1, realized_pnl = $2
                WHERE id = $3
            """, datetime.now(), position['unrealized_pnl'], position_id)
        
        return {
            "success": True,
            "message": f"Position {position_id} closed successfully",
            "alpaca_order_id": alpaca_order.id,
            "realized_pnl": position['unrealized_pnl']
        }
        
    except Exception as e:
        logger.error(f"Failed to close position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")

@app.put("/api/v1/positions/{position_id}/stop_loss")
async def update_stop_loss(position_id: str, stop_price: float):
    """Update stop loss for a position"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Update stop loss in database
            await conn.execute("""
                UPDATE positions SET stop_loss = $1 WHERE id = $2
            """, stop_price, position_id)
        
        return {
            "success": True,
            "message": f"Stop loss updated to ${stop_price:.2f}",
            "position_id": position_id,
            "new_stop_loss": stop_price
        }
        
    except Exception as e:
        logger.error(f"Failed to update stop loss: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update stop loss: {str(e)}")

@app.get("/api/v1/orders")
async def get_orders(status: Optional[str] = None):
    """Get orders"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch("""
                    SELECT * FROM orders WHERE status = $1 ORDER BY submitted_at DESC LIMIT 100
                """, status)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM orders ORDER BY submitted_at DESC LIMIT 100
                """)
            
            orders = []
            for row in rows:
                orders.append({
                    'order_id': row['id'],
                    'symbol': row['symbol'],
                    'side': row['side'],
                    'quantity': row['quantity'],
                    'order_type': row['order_type'],
                    'status': row['status'],
                    'submitted_at': row['submitted_at'].isoformat(),
                    'alpaca_order_id': row['alpaca_order_id']
                })
            
            return {"orders": orders, "count": len(orders)}
            
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")

# === STARTUP AND SHUTDOWN ===

@app.on_event("startup")
async def startup_event():
    """Initialize trading service on startup"""
    try:
        logger.info("Starting Trading Execution Service v4.2")
        
        # Initialize database pool
        await get_db_pool()
        
        # Initialize Redis client
        await get_redis_client()
        
        # Initialize Alpaca client and verify connection
        alpaca = get_alpaca_client()
        account = alpaca.get_account()
        logger.info(f"Connected to Alpaca. Account status: {account.status}")
        logger.info(f"Buying power: ${float(account.buying_power):,.2f}")
        
        # Load active positions
        positions = await get_positions_from_db()
        logger.info(f"Loaded {len(positions)} active positions")
        
        logger.info("Trading Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize trading service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global db_pool, redis_client
    
    try:
        if redis_client:
            await redis_client.close()
        if db_pool:
            await db_pool.close()
        logger.info("Trading service shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5005,
        reload=False
    )
