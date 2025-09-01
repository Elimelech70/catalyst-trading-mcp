#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trading-service.py
Version: 4.1.0
Last Updated: 2025-08-31
Purpose: Order execution and position management

REVISION HISTORY:
v4.1.0 (2025-08-31) - Production-ready trading execution
- Alpaca API integration
- Risk management enforcement
- Position sizing algorithms
- Stop loss and take profit management
- Real-time position monitoring

Description of Service:
This service manages all trading operations:
1. Order execution through Alpaca API
2. Position sizing based on risk parameters
3. Stop loss and take profit order management
4. Real-time position monitoring
5. P&L tracking and reporting
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import asyncpg
import aioredis
import alpaca_trade_api as tradeapi
import json
import os
import logging
from enum import Enum
from decimal import Decimal
from dataclasses import dataclass

# Initialize FastAPI app
app = FastAPI(
    title="Trading Execution Service",
    version="4.1.0",
    description="Trading execution service for Catalyst Trading System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("trading")

# === DATA MODELS ===

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"

class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class ExecuteOrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: Optional[int] = None
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    position_size_pct: Optional[float] = Field(None, ge=0.01, le=1.0)
    risk_amount: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class ExecuteSignalRequest(BaseModel):
    signal: Dict[str, Any]
    risk_level: float = Field(default=0.02, ge=0.001, le=0.05)

class PositionUpdate(BaseModel):
    position_id: str
    action: str  # adjust_stop, adjust_target, close
    value: Optional[float] = None

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
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: Optional[float]
    take_profit: Optional[float]

# === SERVICE STATE ===

@dataclass
class TradingConfig:
    """Configuration for trading service"""
    max_position_size: float = 10000  # Maximum position size in dollars
    max_positions: int = 5  # Maximum concurrent positions
    default_stop_loss_pct: float = 0.02  # 2% stop loss
    default_take_profit_pct: float = 0.04  # 4% take profit
    min_order_value: float = 100  # Minimum order value
    use_paper_trading: bool = True  # Use paper trading by default

class TradingState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.alpaca_api: Optional[tradeapi.REST] = None
        self.config = TradingConfig()
        self.active_positions: Dict[str, Dict] = {}
        self.pending_orders: Dict[str, Dict] = {}
        self.position_monitor_task: Optional[asyncio.Task] = None

state = TradingState()

# === STARTUP/SHUTDOWN ===

@app.on_event("startup")
async def startup():
    """Initialize trading service"""
    logger.info("Starting Trading Execution Service v4.1")
    
    try:
        # Initialize database pool
        db_url = os.getenv("DATABASE_URL", "postgresql://catalyst_user:password@localhost:5432/catalyst_trading")
        state.db_pool = await asyncpg.create_pool(
            db_url,
            min_size=5,
            max_size=20
        )
        
        # Initialize Redis client
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        state.redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Initialize Alpaca API
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_SECRET_KEY")
        base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        if api_key and api_secret:
            state.alpaca_api = tradeapi.REST(
                api_key,
                api_secret,
                base_url,
                api_version='v2'
            )
            
            # Verify connection
            account = state.alpaca_api.get_account()
            logger.info(f"Connected to Alpaca. Account status: {account.status}")
            logger.info(f"Buying power: ${account.buying_power}")
        else:
            logger.warning("Alpaca API credentials not configured")
        
        # Load active positions
        await load_active_positions()
        
        # Start position monitor
        state.position_monitor_task = asyncio.create_task(monitor_positions())
        
        logger.info("Trading Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize trading service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Clean up resources"""
    logger.info("Shutting down Trading Service")
    
    if state.position_monitor_task:
        state.position_monitor_task.cancel()
    
    if state.redis_client:
        await state.redis_client.close()
    
    if state.db_pool:
        await state.db_pool.close()

# === REST API ENDPOINTS ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    
    alpaca_status = "not_configured"
    if state.alpaca_api:
        try:
            account = state.alpaca_api.get_account()
            alpaca_status = account.status
        except:
            alpaca_status = "error"
    
    return {
        "status": "healthy",
        "service": "trading",
        "version": "4.1.0",
        "alpaca_status": alpaca_status,
        "active_positions": len(state.active_positions),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/orders/execute", response_model=OrderResponse)
async def execute_order(request: ExecuteOrderRequest, background_tasks: BackgroundTasks):
    """Execute a trading order"""
    
    if not state.alpaca_api:
        raise HTTPException(status_code=503, detail="Trading API not configured")
    
    try:
        # Calculate position size if not provided
        if request.quantity is None:
            quantity = await calculate_position_size(
                request.symbol,
                request.risk_amount or state.config.max_position_size,
                request.stop_loss
            )
        else:
            quantity = request.quantity
        
        # Validate order
        await validate_order(request.symbol, quantity, request.side)
        
        # Submit order to Alpaca
        order = None
        
        if request.order_type == OrderType.MARKET:
            order = state.alpaca_api.submit_order(
                symbol=request.symbol,
                qty=quantity,
                side=request.side.value,
                type='market',
                time_in_force=request.time_in_force.value
            )
            
        elif request.order_type == OrderType.LIMIT:
            if not request.limit_price:
                raise HTTPException(status_code=400, detail="Limit price required for limit orders")
            
            order = state.alpaca_api.submit_order(
                symbol=request.symbol,
                qty=quantity,
                side=request.side.value,
                type='limit',
                limit_price=request.limit_price,
                time_in_force=request.time_in_force.value
            )
            
        elif request.order_type == OrderType.STOP:
            if not request.stop_price:
                raise HTTPException(status_code=400, detail="Stop price required for stop orders")
            
            order = state.alpaca_api.submit_order(
                symbol=request.symbol,
                qty=quantity,
                side=request.side.value,
                type='stop',
                stop_price=request.stop_price,
                time_in_force=request.time_in_force.value
            )
        
        if not order:
            raise HTTPException(status_code=400, detail="Invalid order type")
        
        # Store order in database
        order_data = {
            "order_id": order.id,
            "symbol": request.symbol,
            "side": request.side.value,
            "quantity": quantity,
            "order_type": request.order_type.value,
            "status": order.status,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit
        }
        
        await store_order(order_data)
        
        # Add to pending orders
        state.pending_orders[order.id] = order_data
        
        # Schedule order monitoring
        background_tasks.add_task(monitor_order, order.id)
        
        # If stop loss or take profit specified, create bracket orders
        if request.stop_loss or request.take_profit:
            background_tasks.add_task(
                create_bracket_orders,
                order.id,
                request.symbol,
                quantity,
                request.stop_loss,
                request.take_profit
            )
        
        return OrderResponse(
            order_id=order.id,
            symbol=request.symbol,
            side=request.side.value,
            quantity=quantity,
            order_type=request.order_type.value,
            status=order.status,
            submitted_at=datetime.fromisoformat(order.submitted_at)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Order execution failed: {str(e)}")

@app.post("/api/v1/orders/execute/signal")
async def execute_signal(request: ExecuteSignalRequest, background_tasks: BackgroundTasks):
    """Execute a trading signal"""
    
    signal = request.signal
    
    # Extract signal parameters
    symbol = signal.get("symbol")
    
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol required in signal")
    
    # Determine order side based on signal
    signal_type = signal.get("technical", {}).get("signal", "neutral")
    
    if signal_type in ["buy", "strong_buy"]:
        side = OrderSide.BUY
    elif signal_type in ["sell", "strong_sell"]:
        side = OrderSide.SELL
    else:
        return {"success": False, "message": "Neutral signal, no action taken"}
    
    # Calculate position size based on risk
    account = state.alpaca_api.get_account()
    buying_power = float(account.buying_power)
    risk_amount = buying_power * request.risk_level
    
    # Get stop loss from signal
    stop_loss = signal.get("technical", {}).get("stop_loss")
    take_profit = signal.get("technical", {}).get("take_profit")
    
    # Execute order
    order_request = ExecuteOrderRequest(
        symbol=symbol,
        side=side,
        order_type=OrderType.MARKET,
        risk_amount=risk_amount,
        stop_loss=stop_loss,
        take_profit=take_profit
    )
    
    result = await execute_order(order_request, background_tasks)
    
    return {
        "success": True,
        "order": result.dict(),
        "signal_id": signal.get("id")
    }

@app.get("/api/v1/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get all active positions"""
    
    if not state.alpaca_api:
        return []
    
    try:
        positions = state.alpaca_api.list_positions()
        
        response = []
        for pos in positions:
            response.append(PositionResponse(
                position_id=pos.asset_id,
                symbol=pos.symbol,
                quantity=int(pos.qty),
                entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price or pos.avg_entry_price),
                unrealized_pnl=float(pos.unrealized_pl or 0),
                realized_pnl=float(pos.realized_pl or 0),
                stop_loss=state.active_positions.get(pos.symbol, {}).get("stop_loss"),
                take_profit=state.active_positions.get(pos.symbol, {}).get("take_profit")
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")

@app.get("/api/v1/positions/{position_id}")
async def get_position(position_id: str):
    """Get specific position details"""
    
    if not state.alpaca_api:
        raise HTTPException(status_code=503, detail="Trading API not configured")
    
    try:
        # Get position from Alpaca
        positions = state.alpaca_api.list_positions()
        
        for pos in positions:
            if pos.asset_id == position_id or pos.symbol == position_id:
                return PositionResponse(
                    position_id=pos.asset_id,
                    symbol=pos.symbol,
                    quantity=int(pos.qty),
                    entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price or pos.avg_entry_price),
                    unrealized_pnl=float(pos.unrealized_pl or 0),
                    realized_pnl=float(pos.realized_pl or 0),
                    stop_loss=state.active_positions.get(pos.symbol, {}).get("stop_loss"),
                    take_profit=state.active_positions.get(pos.symbol, {}).get("take_profit")
                )
        
        raise HTTPException(status_code=404, detail="Position not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get position: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get position: {str(e)}")

@app.post("/api/v1/positions/close")
async def close_position(position_id: str):
    """Close a specific position"""
    
    if not state.alpaca_api:
        raise HTTPException(status_code=503, detail="Trading API not configured")
    
    try:
        # Find position
        positions = state.alpaca_api.list_positions()
        position = None
        
        for pos in positions:
            if pos.asset_id == position_id or pos.symbol == position_id:
                position = pos
                break
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        # Close position
        order = state.alpaca_api.submit_order(
            symbol=position.symbol,
            qty=abs(int(position.qty)),
            side='sell' if int(position.qty) > 0 else 'buy',
            type='market',
            time_in_force='day'
        )
        
        # Update database
        await update_position_status(position.symbol, "closing")
        
        # Remove from active positions
        if position.symbol in state.active_positions:
            del state.active_positions[position.symbol]
        
        return {
            "success": True,
            "position_id": position_id,
            "close_order_id": order.id,
            "message": f"Position {position.symbol} closed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")

@app.put("/api/v1/positions/{position_id}/stop_loss")
async def update_stop_loss(position_id: str, stop_price: float):
    """Update stop loss for a position"""
    
    if not state.alpaca_api:
        raise HTTPException(status_code=503, detail="Trading API not configured")
    
    try:
        # Find position
        positions = state.alpaca_api.list_positions()
        position = None
        
        for pos in positions:
            if pos.asset_id == position_id or pos.symbol == position_id:
                position = pos
                break
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        # Cancel existing stop order if any
        orders = state.alpaca_api.list_orders(
            status='open',
            symbols=position.symbol
        )
        
        for order in orders:
            if order.order_type == 'stop' and order.side != position.side:
                state.alpaca_api.cancel_order(order.id)
        
        # Create new stop order
        stop_order = state.alpaca_api.submit_order(
            symbol=position.symbol,
            qty=abs(int(position.qty)),
            side='sell' if int(position.qty) > 0 else 'buy',
            type='stop',
            stop_price=stop_price,
            time_in_force='gtc'
        )
        
        # Update local state
        if position.symbol not in state.active_positions:
            state.active_positions[position.symbol] = {}
        
        state.active_positions[position.symbol]["stop_loss"] = stop_price
        state.active_positions[position.symbol]["stop_order_id"] = stop_order.id
        
        # Update database
        await update_position_stops(position.symbol, stop_price, None)
        
        return {
            "success": True,
            "position_id": position_id,
            "new_stop_loss": stop_price,
            "stop_order_id": stop_order.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update stop loss: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update stop loss: {str(e)}")

@app.get("/api/v1/orders")
async def get_orders(status: Optional[str] = None):
    """Get orders"""
    
    if not state.alpaca_api:
        return []
    
    try:
        orders = state.alpaca_api.list_orders(status=status or 'all')
        
        result = []
        for order in orders:
            result.append({
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.qty,
                "order_type": order.order_type,
                "status": order.status,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at,
                "filled_price": order.filled_avg_price
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")

# === HELPER FUNCTIONS ===

async def calculate_position_size(
    symbol: str,
    risk_amount: float,
    stop_loss: Optional[float] = None
) -> int:
    """Calculate position size based on risk"""
    
    try:
        # Get current price
        ticker = state.alpaca_api.get_latest_trade(symbol)
        current_price = float(ticker.price)
        
        if stop_loss:
            # Risk-based position sizing
            risk_per_share = abs(current_price - stop_loss)
            
            if risk_per_share > 0:
                shares = int(risk_amount / risk_per_share)
            else:
                shares = int(risk_amount / current_price)
        else:
            # Default position sizing
            shares = int(risk_amount / current_price)
        
        # Apply minimum and maximum constraints
        min_shares = max(1, int(state.config.min_order_value / current_price))
        max_shares = int(state.config.max_position_size / current_price)
        
        return max(min_shares, min(shares, max_shares))
        
    except Exception as e:
        logger.error(f"Position size calculation failed: {e}")
        # Return minimum position size as fallback
        return 1

async def validate_order(symbol: str, quantity: int, side: OrderSide):
    """Validate order before execution"""
    
    # Check if we have reached max positions
    if side == OrderSide.BUY:
        positions = state.alpaca_api.list_positions()
        if len(positions) >= state.config.max_positions:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum positions ({state.config.max_positions}) reached"
            )
    
    # Check buying power
    account = state.alpaca_api.get_account()
    
    if side == OrderSide.BUY:
        ticker = state.alpaca_api.get_latest_trade(symbol)
        order_value = float(ticker.price) * quantity
        
        if order_value > float(account.buying_power):
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient buying power. Required: ${order_value:.2f}, Available: ${account.buying_power}"
            )
    
    # Check day trading restrictions
    if account.pattern_day_trader and int(account.daytrade_count) >= 3:
        logger.warning("Approaching day trading limit")

async def create_bracket_orders(
    parent_order_id: str,
    symbol: str,
    quantity: int,
    stop_loss: Optional[float],
    take_profit: Optional[float]
):
    """Create bracket orders for position"""
    
    try:
        # Wait for parent order to fill
        await asyncio.sleep(2)
        
        # Check if parent order is filled
        order = state.alpaca_api.get_order(parent_order_id)
        
        if order.status != 'filled':
            # Retry later
            await asyncio.sleep(5)
            order = state.alpaca_api.get_order(parent_order_id)
        
        if order.status == 'filled':
            filled_price = float(order.filled_avg_price)
            
            # Create stop loss order
            if stop_loss:
                stop_order = state.alpaca_api.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side='sell' if order.side == 'buy' else 'buy',
                    type='stop',
                    stop_price=stop_loss,
                    time_in_force='gtc'
                )
                
                logger.info(f"Created stop loss order {stop_order.id} at {stop_loss}")
            
            # Create take profit order
            if take_profit:
                profit_order = state.alpaca_api.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side='sell' if order.side == 'buy' else 'buy',
                    type='limit',
                    limit_price=take_profit,
                    time_in_force='gtc'
                )
                
                logger.info(f"Created take profit order {profit_order.id} at {take_profit}")
                
    except Exception as e:
        logger.error(f"Failed to create bracket orders: {e}")

async def monitor_order(order_id: str):
    """Monitor order status"""
    
    try:
        max_attempts = 60  # Monitor for up to 5 minutes
        
        for _ in range(max_attempts):
            order = state.alpaca_api.get_order(order_id)
            
            # Update pending orders
            if order_id in state.pending_orders:
                state.pending_orders[order_id]["status"] = order.status
            
            # Check if order is complete
            if order.status in ['filled', 'cancelled', 'rejected']:
                # Update database
                await update_order_status(order_id, order.status)
                
                # Remove from pending
                if order_id in state.pending_orders:
                    del state.pending_orders[order_id]
                
                # If filled, add to positions
                if order.status == 'filled':
                    await add_to_positions(order)
                
                break
            
            await asyncio.sleep(5)
            
    except Exception as e:
        logger.error(f"Order monitoring failed for {order_id}: {e}")

async def monitor_positions():
    """Background task to monitor positions"""
    
    logger.info("Starting position monitor")
    
    while True:
        try:
            if state.alpaca_api:
                positions = state.alpaca_api.list_positions()
                
                for position in positions:
                    symbol = position.symbol
                    current_price = float(position.current_price or position.avg_entry_price)
                    entry_price = float(position.avg_entry_price)
                    unrealized_pnl = float(position.unrealized_pl or 0)
                    
                    # Check for trailing stop adjustments
                    if symbol in state.active_positions:
                        pos_data = state.active_positions[symbol]
                        
                        # Adjust stop loss if position is profitable
                        if unrealized_pnl > 0 and pos_data.get("stop_loss"):
                            new_stop = entry_price  # Move stop to breakeven
                            
                            if new_stop > pos_data["stop_loss"]:
                                await update_stop_loss(symbol, new_stop)
                                logger.info(f"Adjusted stop loss for {symbol} to breakeven")
                    
                    # Update position data in cache
                    await update_position_cache(position)
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Position monitoring error: {e}")
            await asyncio.sleep(60)  # Wait longer on error

async def load_active_positions():
    """Load active positions from database"""
    
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol, stop_loss, take_profit, metadata
                FROM positions
                WHERE status = 'active'
            """)
            
            for row in rows:
                state.active_positions[row['symbol']] = {
                    "stop_loss": row['stop_loss'],
                    "take_profit": row['take_profit'],
                    "metadata": json.loads(row['metadata'] or '{}')
                }
            
            logger.info(f"Loaded {len(state.active_positions)} active positions")
            
    except Exception as e:
        logger.error(f"Failed to load active positions: {e}")

async def store_order(order_data: Dict):
    """Store order in database"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orders (
                    order_id, cycle_id, symbol, direction,
                    order_type, quantity, status, metadata,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                order_data["order_id"],
                "manual",  # Or get from context
                order_data["symbol"],
                order_data["side"],
                order_data["order_type"],
                order_data["quantity"],
                order_data["status"],
                json.dumps(order_data),
                datetime.now()
            )
    except Exception as e:
        logger.error(f"Failed to store order: {e}")

async def update_order_status(order_id: str, status: str):
    """Update order status in database"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE orders
                SET status = $1, updated_at = $2
                WHERE order_id = $3
            """,
                status,
                datetime.now(),
                order_id
            )
    except Exception as e:
        logger.error(f"Failed to update order status: {e}")

async def add_to_positions(order):
    """Add filled order to positions"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO positions (
                    position_id, cycle_id, symbol, quantity,
                    entry_price, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (position_id) DO UPDATE
                SET quantity = positions.quantity + EXCLUDED.quantity,
                    updated_at = EXCLUDED.created_at
            """,
                f"{order.symbol}_{datetime.now().strftime('%Y%m%d')}",
                "manual",
                order.symbol,
                int(order.filled_qty),
                float(order.filled_avg_price),
                "active",
                datetime.now()
            )
    except Exception as e:
        logger.error(f"Failed to add position: {e}")

async def update_position_status(symbol: str, status: str):
    """Update position status"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions
                SET status = $1, updated_at = $2
                WHERE symbol = $3 AND status = 'active'
            """,
                status,
                datetime.now(),
                symbol
            )
    except Exception as e:
        logger.error(f"Failed to update position status: {e}")

async def update_position_stops(symbol: str, stop_loss: Optional[float], take_profit: Optional[float]):
    """Update position stop levels"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions
                SET stop_loss = $1, take_profit = $2, updated_at = $3
                WHERE symbol = $4 AND status = 'active'
            """,
                stop_loss,
                take_profit,
                datetime.now(),
                symbol
            )
    except Exception as e:
        logger.error(f"Failed to update position stops: {e}")

async def update_position_cache(position):
    """Update position data in Redis cache"""
    
    if state.redis_client:
        try:
            position_data = {
                "symbol": position.symbol,
                "quantity": position.qty,
                "entry_price": position.avg_entry_price,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pl,
                "timestamp": datetime.now().isoformat()
            }
            
            await state.redis_client.setex(
                f"position:{position.symbol}",
                60,  # TTL 60 seconds
                json.dumps(position_data, default=str)
            )
        except Exception as e:
            logger.debug(f"Cache update error: {e}")

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎩 Catalyst Trading System - Trading Service v4.1")
    print("=" * 60)
    print("Status: Starting...")
    print("Port: 5005")
    print("Protocol: REST API")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5005,
        log_level="info"
    )
