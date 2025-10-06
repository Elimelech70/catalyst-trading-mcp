#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk-manager-service.py
Version: 4.2.1
Last Updated: 2025-09-20
Purpose: Risk management service with live market data integration

REVISION HISTORY:
v4.2.1 (2025-09-20) - Fixed current_price database error
- Removed current_price database queries (column doesn't exist)
- Added live market data integration via yfinance
- Calculate real-time P&L using live prices
- Fixed database schema compliance issues
- Added proper error handling for market data failures

Description of Service:
Risk management service that fetches live market prices from Yahoo Finance
to calculate real-time position risk, P&L, and portfolio metrics.
No longer depends on non-existent database columns.
"""

from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional
import asyncpg
import yfinance as yf
import asyncio
import logging
from datetime import datetime, date
import os
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

app = FastAPI(title="Risk Manager Service", version="4.2.1")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global db_pool
    
    # Startup
    logger.info("🛡️ Starting Risk Manager Service v4.2.1")
    
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL)
            logger.info("✅ Database pool created successfully")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            db_pool = None
    
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")

app.router.lifespan_context = lifespan

async def get_live_price(symbol: str) -> float:
    """Get current market price for symbol"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Try different price fields
        current_price = (
            info.get('currentPrice') or
            info.get('regularMarketPrice') or  
            info.get('previousClose') or
            info.get('open')
        )
        
        if current_price:
            return float(current_price)
        else:
            logger.warning(f"No price data found for {symbol}")
            return 0.0
            
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return 0.0

async def get_live_prices(symbols: List[str]) -> Dict[str, float]:
    """Get current prices for multiple symbols"""
    prices = {}
    
    try:
        # Batch fetch for efficiency
        symbols_str = " ".join(symbols)
        tickers = yf.Tickers(symbols_str)
        
        for symbol in symbols:
            try:
                ticker = tickers.tickers[symbol]
                info = ticker.info
                
                current_price = (
                    info.get('currentPrice') or
                    info.get('regularMarketPrice') or
                    info.get('previousClose') or
                    info.get('open')
                )
                
                prices[symbol] = float(current_price) if current_price else 0.0
                
            except Exception as e:
                logger.warning(f"Failed to get price for {symbol}: {e}")
                prices[symbol] = 0.0
                
    except Exception as e:
        logger.error(f"Batch price fetch failed: {e}")
        # Fallback to individual requests
        for symbol in symbols:
            prices[symbol] = await get_live_price(symbol)
    
    return prices

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "risk-manager",
        "version": "4.2.1",
        "database": "connected" if db_pool else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/metrics")
async def get_risk_metrics():
    """Get current risk metrics with live market data"""
    try:
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")
        
        async with db_pool.acquire() as conn:
            # Get all open positions (fixed query - no current_price column)
            positions = await conn.fetch("""
                SELECT 
                    position_id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    stop_loss,
                    take_profit,
                    opened_at,
                    risk_amount,
                    unrealized_pnl
                FROM positions 
                WHERE status = 'open'
            """)
            
            if not positions:
                return {
                    "total_positions": 0,
                    "total_exposure": 0.0,
                    "total_unrealized_pnl": 0.0,
                    "daily_pnl": 0.0,
                    "risk_budget_used": 0.0,
                    "positions": [],
                    "timestamp": datetime.now().isoformat()
                }
            
            # Get unique symbols for price fetch
            symbols = list(set(pos['symbol'] for pos in positions))
            live_prices = await get_live_prices(symbols)
            
            # Calculate real-time metrics
            total_exposure = 0.0
            total_unrealized_pnl = 0.0
            position_metrics = []
            
            for pos in positions:
                symbol = pos['symbol']
                current_price = live_prices.get(symbol, 0.0)
                
                if current_price > 0:
                    # Calculate real-time P&L
                    if pos['side'] == 'long':
                        unrealized_pnl = (current_price - pos['entry_price']) * pos['quantity']
                    else:  # short
                        unrealized_pnl = (pos['entry_price'] - current_price) * pos['quantity']
                    
                    position_value = current_price * pos['quantity']
                    pnl_percent = (unrealized_pnl / (pos['entry_price'] * pos['quantity'])) * 100
                else:
                    unrealized_pnl = pos.get('unrealized_pnl', 0.0) or 0.0
                    position_value = pos['entry_price'] * pos['quantity']
                    pnl_percent = 0.0
                
                total_exposure += abs(position_value)
                total_unrealized_pnl += unrealized_pnl
                
                position_metrics.append({
                    "position_id": pos['position_id'],
                    "symbol": symbol,
                    "side": pos['side'],
                    "quantity": pos['quantity'],
                    "entry_price": float(pos['entry_price']),
                    "current_price": current_price,
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "pnl_percent": round(pnl_percent, 2),
                    "position_value": round(position_value, 2),
                    "stop_loss": float(pos['stop_loss']) if pos['stop_loss'] else None,
                    "risk_amount": float(pos.get('risk_amount', 0) or 0)
                })
            
            # Get daily P&L from database
            today = date.today()
            daily_metrics = await conn.fetchrow("""
                SELECT daily_pnl, daily_loss_limit 
                FROM daily_risk_metrics 
                WHERE date = $1
            """, today)
            
            daily_pnl = float(daily_metrics['daily_pnl']) if daily_metrics else 0.0
            daily_loss_limit = float(daily_metrics['daily_loss_limit']) if daily_metrics else 2000.0
            
            risk_budget_used = (abs(daily_pnl) / daily_loss_limit) * 100
            
            return {
                "total_positions": len(positions),
                "total_exposure": round(total_exposure, 2),
                "total_unrealized_pnl": round(total_unrealized_pnl, 2),
                "daily_pnl": round(daily_pnl, 2),
                "daily_loss_limit": round(daily_loss_limit, 2),
                "risk_budget_used_pct": round(risk_budget_used, 2),
                "positions": position_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/validate-trade")
async def validate_trade(trade_data: dict):
    """Validate if proposed trade meets risk parameters"""
    try:
        symbol = trade_data.get('symbol')
        quantity = trade_data.get('quantity', 0)
        side = trade_data.get('side', 'long')
        
        if not symbol or quantity <= 0:
            raise HTTPException(status_code=400, detail="Invalid trade data")
        
        # Get current price
        current_price = await get_live_price(symbol)
        if current_price <= 0:
            return {
                "approved": False,
                "reason": f"Unable to get current price for {symbol}"
            }
        
        position_value = current_price * quantity
        
        # Basic validation (can be enhanced)
        max_position_value = 10000  # $10k max position
        
        if position_value > max_position_value:
            return {
                "approved": False,
                "reason": f"Position value ${position_value:.2f} exceeds limit ${max_position_value:.2f}",
                "current_price": current_price
            }
        
        return {
            "approved": True,
            "position_value": round(position_value, 2),
            "current_price": current_price,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error validating trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/position/{position_id}/risk")
async def get_position_risk(position_id: int):
    """Get detailed risk analysis for specific position"""
    try:
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")
        
        async with db_pool.acquire() as conn:
            position = await conn.fetchrow("""
                SELECT * FROM positions WHERE position_id = $1
            """, position_id)
            
            if not position:
                raise HTTPException(status_code=404, detail="Position not found")
            
            # Get live price
            current_price = await get_live_price(position['symbol'])
            
            if current_price > 0:
                # Calculate current metrics
                if position['side'] == 'long':
                    unrealized_pnl = (current_price - position['entry_price']) * position['quantity']
                else:
                    unrealized_pnl = (position['entry_price'] - current_price) * position['quantity']
                
                pnl_percent = (unrealized_pnl / (position['entry_price'] * position['quantity'])) * 100
                position_value = current_price * position['quantity']
            else:
                unrealized_pnl = 0.0
                pnl_percent = 0.0
                position_value = position['entry_price'] * position['quantity']
            
            return {
                "position_id": position_id,
                "symbol": position['symbol'],
                "current_price": current_price,
                "entry_price": float(position['entry_price']),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "position_value": round(position_value, 2),
                "stop_loss": float(position['stop_loss']) if position['stop_loss'] else None,
                "risk_score": float(position.get('position_risk_score', 0) or 0),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting position risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5004)