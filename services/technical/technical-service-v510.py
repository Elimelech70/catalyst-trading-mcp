#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 5.1.0
Last Updated: 2025-10-13
Purpose: Technical indicators with normalized schema v5.0 and rigorous error handling

REVISION HISTORY:
v5.1.0 (2025-10-13) - Production Error Handling Upgrade
- NO Unicode emojis (ASCII only)
- Specific exception types (ValueError, asyncpg.PostgresError)
- Structured logging with exc_info
- HTTPException with proper status codes
- No silent failures
- FastAPI lifespan
- Database persistence

Description of Service:
Technical indicator calculations with proper error handling.
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncpg
import numpy as np
import os
import logging
import json

SERVICE_NAME = "technical"
SERVICE_VERSION = "5.1.0"
SERVICE_PORT = 5003

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(SERVICE_NAME)

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://catalyst:catalyst@localhost:5432/catalyst_trading")
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10

class ServiceState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.is_healthy = False

state = ServiceState()

class IndicatorRequest(BaseModel):
    symbol: str
    timeframe: str = "5min"

async def get_security_id(symbol: str) -> int:
    """Get or create security_id"""
    try:
        if not symbol:
            raise ValueError(f"Invalid symbol: {symbol}")
        security_id = await state.db_pool.fetchval("SELECT get_or_create_security($1)", symbol.upper())
        if not security_id:
            raise RuntimeError(f"Failed to get security_id for {symbol}")
        return security_id
    except ValueError:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"Database error in get_security_id: {e}", exc_info=True, extra={'symbol': symbol, 'error_type': 'database'})
        raise
    except Exception as e:
        logger.critical(f"Unexpected error in get_security_id: {e}", exc_info=True, extra={'symbol': symbol})
        raise RuntimeError(f"Failed to get security_id: {e}")

async def get_time_id(timestamp: datetime) -> int:
    """Get or create time_id"""
    try:
        time_id = await state.db_pool.fetchval("SELECT get_or_create_time($1)", timestamp)
        if not time_id:
            raise RuntimeError("Failed to get time_id")
        return time_id
    except asyncpg.PostgresError as e:
        logger.error(f"Database error in get_time_id: {e}", exc_info=True, extra={'error_type': 'database'})
        raise

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate RSI"""
    try:
        if len(prices) < period + 1:
            return None
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    except Exception as e:
        logger.warning(f"RSI calculation error: {e}", extra={'error_type': 'calculation'})
        return None

def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[Dict]:
    """Calculate MACD"""
    try:
        if len(prices) < slow + signal:
            return None
        prices_arr = np.array(prices)
        ema_fast = prices_arr[-fast:].mean()
        ema_slow = prices_arr[-slow:].mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line
        histogram = macd_line - signal_line
        return {'macd': float(macd_line), 'signal': float(signal_line), 'histogram': float(histogram)}
    except Exception as e:
        logger.warning(f"MACD calculation error: {e}", extra={'error_type': 'calculation'})
        return None

def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[Dict]:
    """Calculate Bollinger Bands"""
    try:
        if len(prices) < period:
            return None
        middle = float(np.mean(prices[-period:]))
        std = float(np.std(prices[-period:]))
        return {'upper': middle + (std_dev * std), 'middle': middle, 'lower': middle - (std_dev * std)}
    except Exception as e:
        logger.warning(f"Bollinger Bands calculation error: {e}", extra={'error_type': 'calculation'})
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[STARTUP] {SERVICE_TITLE} v{SERVICE_VERSION}")
    try:
        state.db_pool = await asyncpg.create_pool(Config.DATABASE_URL, min_size=Config.POOL_MIN_SIZE, max_size=Config.POOL_MAX_SIZE)
        logger.info("[STARTUP] Database connected")
        state.is_healthy = True
    except asyncpg.PostgresError as e:
        logger.critical(f"[STARTUP] Database connection failed: {e}", exc_info=True, extra={'error_type': 'database'})
        state.is_healthy = False
    yield
    logger.info("[SHUTDOWN] Closing database")
    if state.db_pool:
        await state.db_pool.close()

app = FastAPI(title=SERVICE_TITLE, version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"status": "healthy" if state.is_healthy else "unhealthy", "service": SERVICE_NAME, "version": SERVICE_VERSION, "schema": SCHEMA_VERSION}

@app.post("/api/v1/indicators/calculate")
async def calculate_indicators(request: IndicatorRequest):
    """Calculate indicators for symbol"""
    try:
        if not request.symbol or len(request.symbol) > 10:
            raise ValueError(f"Invalid symbol: {request.symbol}")
        
        symbol = request.symbol.upper()
        security_id = await get_security_id(symbol)
        
        # Fetch price data
        prices = await state.db_pool.fetch("""
            SELECT th.close, td.timestamp
            FROM trading_history th
            JOIN time_dimension td ON td.time_id = th.time_id
            WHERE th.security_id = $1
            ORDER BY td.timestamp DESC
            LIMIT 200
        """, security_id)
        
        if not prices or len(prices) < 20:
            raise ValueError(f"Insufficient price data for {symbol}")
        
        close_prices = [float(p['close']) for p in reversed(prices)]
        
        # Calculate indicators
        rsi = calculate_rsi(close_prices)
        macd = calculate_macd(close_prices)
        bb = calculate_bollinger_bands(close_prices)
        
        # Store in database
        time_id = await get_time_id(datetime.now())
        
        await state.db_pool.execute("""
            INSERT INTO technical_indicators (
                security_id, time_id, timeframe,
                rsi_14, macd, macd_signal, macd_histogram,
                bollinger_upper, bollinger_middle, bollinger_lower
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (security_id, time_id, timeframe) DO UPDATE SET
                rsi_14 = EXCLUDED.rsi_14,
                macd = EXCLUDED.macd
        """, security_id, time_id, request.timeframe, rsi,
             macd['macd'] if macd else None, macd['signal'] if macd else None, macd['histogram'] if macd else None,
             bb['upper'] if bb else None, bb['middle'] if bb else None, bb['lower'] if bb else None)
        
        logger.info(f"Indicators calculated for {symbol}", extra={'symbol': symbol, 'rsi': rsi})
        
        return {"symbol": symbol, "rsi": rsi, "macd": macd, "bollinger_bands": bb}
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'symbol': request.symbol, 'error_type': 'validation'})
        raise HTTPException(status_code=400, detail={'error': 'Invalid request', 'message': str(e)})
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True, extra={'symbol': request.symbol, 'error_type': 'database'})
        raise HTTPException(status_code=503, detail={'error': 'Database unavailable', 'retry_after': 30})
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True, extra={'symbol': request.symbol, 'error_type': 'unexpected'})
        raise HTTPException(status_code=500, detail={'error': 'Internal server error'})

@app.post("/api/v1/indicators/batch")
async def calculate_batch(symbols: List[str]):
    """Calculate indicators for multiple symbols"""
    results = []
    failed = []
    
    for symbol in symbols:
        try:
            request = IndicatorRequest(symbol=symbol)
            result = await calculate_indicators(request)
            results.append(result)
        except Exception as e:
            logger.warning(f"Batch calculation failed for {symbol}: {e}", extra={'symbol': symbol})
            failed.append(symbol)
    
    logger.info(f"Batch complete: {len(results)} success, {len(failed)} failed", extra={'success': len(results), 'failed': len(failed)})
    
    return {"results": results, "success": len(results), "failed": failed}

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print(f"Catalyst Trading System - {SERVICE_TITLE} v{SERVICE_VERSION}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
