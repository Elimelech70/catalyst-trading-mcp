#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 5.2.0
Last Updated: 2025-10-16
Purpose: Technical analysis service with indicators and signals

REVISION HISTORY:
v5.2.0 (2025-10-16) - Critical production fixes
- Added missing CORSMiddleware import
- Fixed SERVICE_NAME constant definition
- Corrected FastAPI initialization parameters
- Fixed SERVICE_TITLE -> SERVICE_NAME error
- Fixed SERVICE_VERSION reference

v5.1.0 (2025-10-15) - Performance optimizations
- Improved query efficiency
- Added connection pooling optimization

v5.0.3 (2025-10-13) - Database query fixes
- Fixed boolean parameter handling
- Fixed INTERVAL parameterization

v5.0.2 (2025-10-13) - Endpoint compatibility
- Added orchestration expected endpoints

v5.0.1 (2025-10-13) - Pydantic V2 migration

v5.0.0 (2025-10-11) - Normalized schema implementation
- Uses security_id FK (NOT symbol VARCHAR)
- All queries use JOINs on FKs
- Direct asyncpg database connection
- FastAPI REST endpoints

Description of Service:
Technical analysis service that calculates indicators (RSI, MACD, Bollinger Bands, etc.)
and generates trading signals for scanned securities. Fully normalized with v5.0 schema.
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import asyncpg
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import aiohttp
import redis.asyncio as redis

# Service Configuration
SERVICE_NAME = "Technical Analysis Service"
SERVICE_VERSION = "5.2.0"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "5003"))

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Global connections
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
http_session: Optional[aiohttp.ClientSession] = None

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TechnicalRequest(BaseModel):
    """Request for technical analysis"""
    symbol: str
    timeframe: str = Field(default="1d", description="Timeframe: 1m, 5m, 15m, 1h, 1d")
    period: int = Field(default=20, description="Number of periods for indicators")

class TechnicalIndicators(BaseModel):
    """Technical indicators response"""
    symbol: str
    security_id: int
    timestamp: datetime
    price: float
    volume: int
    rsi: Optional[float] = None
    macd: Optional[Dict[str, float]] = None
    bollinger: Optional[Dict[str, float]] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    atr: Optional[float] = None
    obv: Optional[float] = None
    signal: str  # BUY, SELL, HOLD
    signal_strength: float  # 0.0 to 1.0

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str = "technical"
    version: str = SERVICE_VERSION
    timestamp: datetime
    database: str
    redis: str

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global db_pool, redis_client, http_session
    
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    
    # Initialize database pool
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60,
            pool_recycle_time=3600
        )
        logger.info("Database pool initialized")
        
        # Verify normalized schema
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'technical_indicators' 
                AND column_name = 'security_id'
            """)
            if result > 0:
                logger.info("✅ Normalized schema v5.0 verified")
            else:
                logger.warning("⚠️ Schema may not be normalized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    # Initialize Redis
    try:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis client initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed (non-critical): {e}")
        redis_client = None
    
    # Initialize HTTP session
    http_session = aiohttp.ClientSession()
    logger.info("HTTP session initialized")
    
    logger.info(f"{SERVICE_NAME} ready on port {SERVICE_PORT}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Technical Service...")
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    if http_session:
        await http_session.close()

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ============================================================================
# TECHNICAL INDICATORS CALCULATION
# ============================================================================

async def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return None
    
    deltas = np.diff(prices)
    gains = deltas.copy()
    gains[gains < 0] = 0
    losses = -deltas.copy()
    losses[losses < 0] = 0
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi)

async def calculate_macd(prices: List[float]) -> Optional[Dict[str, float]]:
    """Calculate MACD"""
    if len(prices) < 26:
        return None
    
    exp1 = pd.Series(prices).ewm(span=12, adjust=False).mean()
    exp2 = pd.Series(prices).ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1])
    }

async def calculate_bollinger_bands(prices: List[float], period: int = 20) -> Optional[Dict[str, float]]:
    """Calculate Bollinger Bands"""
    if len(prices) < period:
        return None
    
    sma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    
    return {
        "upper": float(sma + (2 * std)),
        "middle": float(sma),
        "lower": float(sma - (2 * std))
    }

async def generate_signal(indicators: Dict) -> tuple[str, float]:
    """Generate trading signal based on indicators"""
    signals = []
    
    # RSI signals
    if indicators.get("rsi"):
        if indicators["rsi"] < 30:
            signals.append(("BUY", 0.7))
        elif indicators["rsi"] > 70:
            signals.append(("SELL", 0.7))
        else:
            signals.append(("HOLD", 0.3))
    
    # MACD signals
    if indicators.get("macd"):
        if indicators["macd"]["histogram"] > 0:
            signals.append(("BUY", 0.6))
        else:
            signals.append(("SELL", 0.6))
    
    # Bollinger Band signals
    if indicators.get("bollinger"):
        price = indicators.get("price", 0)
        if price <= indicators["bollinger"]["lower"]:
            signals.append(("BUY", 0.8))
        elif price >= indicators["bollinger"]["upper"]:
            signals.append(("SELL", 0.8))
        else:
            signals.append(("HOLD", 0.4))
    
    # Aggregate signals
    if not signals:
        return "HOLD", 0.0
    
    buy_strength = sum(s[1] for s in signals if s[0] == "BUY")
    sell_strength = sum(s[1] for s in signals if s[0] == "SELL")
    
    if buy_strength > sell_strength:
        return "BUY", min(buy_strength / len(signals), 1.0)
    elif sell_strength > buy_strength:
        return "SELL", min(sell_strength / len(signals), 1.0)
    else:
        return "HOLD", 0.5

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "disconnected"
    redis_status = "connected" if redis_client else "disconnected"
    
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        database=db_status,
        redis=redis_status
    )

@app.post("/api/v1/analyze", response_model=TechnicalIndicators)
async def analyze_technical(request: TechnicalRequest):
    """Analyze technical indicators for a symbol"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with db_pool.acquire() as conn:
            # Get security_id from symbol (v5.0 normalized)
            security = await conn.fetchrow("""
                SELECT security_id, symbol, name
                FROM securities
                WHERE symbol = $1
            """, request.symbol.upper())
            
            if not security:
                raise HTTPException(status_code=404, detail=f"Symbol {request.symbol} not found")
            
            # Get price history (using normalized schema)
            prices = await conn.fetch("""
                SELECT p.price, p.volume, t.timestamp
                FROM prices p
                JOIN time_dimension t ON p.time_id = t.time_id
                WHERE p.security_id = $1
                ORDER BY t.timestamp DESC
                LIMIT $2
            """, security['security_id'], request.period * 2)
            
            if not prices:
                raise HTTPException(status_code=404, detail="No price data available")
            
            price_list = [float(p['price']) for p in prices]
            current_price = price_list[0]
            current_volume = prices[0]['volume']
            
            # Calculate indicators
            rsi = await calculate_rsi(price_list, request.period)
            macd = await calculate_macd(price_list)
            bollinger = await calculate_bollinger_bands(price_list, request.period)
            
            # Generate signal
            signal, strength = await generate_signal({
                "rsi": rsi,
                "macd": macd,
                "bollinger": bollinger,
                "price": current_price
            })
            
            # Store in database (v5.0 normalized)
            await conn.execute("""
                INSERT INTO technical_indicators (
                    security_id, time_id, rsi, macd_value, macd_signal,
                    bb_upper, bb_middle, bb_lower, signal_type, signal_strength
                ) VALUES (
                    $1, 
                    (SELECT time_id FROM time_dimension WHERE DATE(timestamp) = CURRENT_DATE LIMIT 1),
                    $2, $3, $4, $5, $6, $7, $8, $9
                )
                ON CONFLICT (security_id, time_id) DO UPDATE SET
                    rsi = EXCLUDED.rsi,
                    macd_value = EXCLUDED.macd_value,
                    macd_signal = EXCLUDED.macd_signal,
                    bb_upper = EXCLUDED.bb_upper,
                    bb_middle = EXCLUDED.bb_middle,
                    bb_lower = EXCLUDED.bb_lower,
                    signal_type = EXCLUDED.signal_type,
                    signal_strength = EXCLUDED.signal_strength,
                    updated_at = NOW()
            """, 
            security['security_id'], rsi, 
            macd["macd"] if macd else None,
            macd["signal"] if macd else None,
            bollinger["upper"] if bollinger else None,
            bollinger["middle"] if bollinger else None,
            bollinger["lower"] if bollinger else None,
            signal, strength)
            
            return TechnicalIndicators(
                symbol=request.symbol.upper(),
                security_id=security['security_id'],
                timestamp=datetime.utcnow(),
                price=current_price,
                volume=current_volume,
                rsi=rsi,
                macd=macd,
                bollinger=bollinger,
                signal=signal,
                signal_strength=strength
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Technical analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")

@app.get("/api/v1/indicators/{symbol}", response_model=TechnicalIndicators)
async def get_latest_indicators(symbol: str):
    """Get latest technical indicators for a symbol"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with db_pool.acquire() as conn:
            # Get security_id (v5.0 normalized)
            security = await conn.fetchrow("""
                SELECT security_id FROM securities WHERE symbol = $1
            """, symbol.upper())
            
            if not security:
                raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
            
            # Get latest indicators
            result = await conn.fetchrow("""
                SELECT 
                    ti.*,
                    s.symbol,
                    t.timestamp
                FROM technical_indicators ti
                JOIN securities s ON ti.security_id = s.security_id
                JOIN time_dimension t ON ti.time_id = t.time_id
                WHERE ti.security_id = $1
                ORDER BY t.timestamp DESC
                LIMIT 1
            """, security['security_id'])
            
            if not result:
                # No stored indicators, calculate fresh
                request = TechnicalRequest(symbol=symbol)
                return await analyze_technical(request)
            
            return TechnicalIndicators(
                symbol=symbol.upper(),
                security_id=security['security_id'],
                timestamp=result['timestamp'],
                price=0,  # Would need to fetch from prices table
                volume=0,
                rsi=result['rsi'],
                macd={
                    "macd": result['macd_value'],
                    "signal": result['macd_signal'],
                    "histogram": result['macd_value'] - result['macd_signal'] if result['macd_value'] and result['macd_signal'] else None
                } if result['macd_value'] else None,
                bollinger={
                    "upper": result['bb_upper'],
                    "middle": result['bb_middle'],
                    "lower": result['bb_lower']
                } if result['bb_upper'] else None,
                signal=result['signal_type'],
                signal_strength=result['signal_strength']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get indicators error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get indicators")

@app.post("/api/v1/batch-analyze", response_model=List[TechnicalIndicators])
async def batch_analyze(symbols: List[str]):
    """Analyze multiple symbols at once"""
    if not symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")
    
    if len(symbols) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols per request")
    
    results = []
    errors = []
    
    for symbol in symbols:
        try:
            request = TechnicalRequest(symbol=symbol)
            result = await analyze_technical(request)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to analyze {symbol}: {e}")
            errors.append(symbol)
    
    if errors:
        logger.warning(f"Failed symbols: {errors}")
    
    return results

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print(f"🎩 Catalyst Trading System - {SERVICE_NAME} v{SERVICE_VERSION}")
    print("=" * 60)
    print("✅ Fixed import issues")
    print("✅ v5.0 normalized with security_id FKs")
    print("✅ FastAPI REST endpoints")
    print("✅ Technical indicators calculation")
    print(f"Port: {SERVICE_PORT}")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)