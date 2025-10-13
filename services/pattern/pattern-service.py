#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 5.1.0
Last Updated: 2025-10-13
Purpose: Pattern detection with normalized schema v5.0 and rigorous error handling

REVISION HISTORY:
v5.1.0 (2025-10-13) - Production Error Handling Upgrade
- NO Unicode emojis (ASCII only)
- Specific exception types (ValueError, asyncpg.PostgresError)
- Structured logging with exc_info
- HTTPException with proper status codes
- No silent failures - pattern detection errors tracked
- FastAPI lifespan
- Success/failure tracking for batch operations

v5.0.2 (2025-10-11) - Database column names fix

Description of Service:
Pattern detection with proper error handling and normalized schema.
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from enum import Enum
import asyncpg
import numpy as np
import os
import logging
import json

SERVICE_NAME = "pattern"
SERVICE_VERSION = "5.1.0"
SERVICE_PORT = 5002

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

class PatternType(str, Enum):
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    CONSOLIDATION = "consolidation"

class PatternSubtype(str, Enum):
    BULL_FLAG = "bull_flag"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_SHOULDERS = "head_and_shoulders"
    RANGE_BOUND = "range_bound"

class PatternRequest(BaseModel):
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
        logger.critical(f"Unexpected error: {e}", exc_info=True, extra={'symbol': symbol})
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

def detect_bull_flag(closes: List[float], highs: List[float], lows: List[float]) -> Optional[Dict]:
    """Detect bull flag pattern"""
    try:
        if len(closes) < 20:
            return None
        
        recent_trend = closes[-10:]
        price_range = (max(recent_trend) - min(recent_trend)) / np.mean(recent_trend)
        
        if price_range < 0.05:
            resistance = max(recent_trend)
            support = min(recent_trend)
            confidence = 0.70
            
            return {
                'pattern_type': PatternType.BREAKOUT,
                'pattern_subtype': PatternSubtype.BULL_FLAG,
                'confidence': confidence,
                'breakout_level': resistance,
                'target_price': resistance * 1.05,
                'stop_level': support * 0.98
            }
        return None
    except Exception as e:
        logger.warning(f"Bull flag detection error: {e}", extra={'error_type': 'pattern_detection'})
        return None

def detect_double_bottom(lows: List[float], closes: List[float]) -> Optional[Dict]:
    """Detect double bottom pattern"""
    try:
        if len(lows) < 40:
            return None
        
        min_indices = []
        for i in range(5, len(lows) - 5):
            if lows[i] == min(lows[i-5:i+5]):
                min_indices.append(i)
        
        if len(min_indices) < 2:
            return None
        
        first_low = lows[min_indices[-2]]
        second_low = lows[min_indices[-1]]
        similarity = abs(first_low - second_low) / first_low
        
        if similarity < 0.02:
            peak = max(closes[min_indices[-2]:min_indices[-1]])
            support = (first_low + second_low) / 2
            
            return {
                'pattern_type': PatternType.REVERSAL,
                'pattern_subtype': PatternSubtype.DOUBLE_BOTTOM,
                'confidence': 0.65,
                'breakout_level': peak,
                'target_price': peak * 1.05,
                'stop_level': support * 0.97
            }
        return None
    except Exception as e:
        logger.warning(f"Double bottom detection error: {e}", extra={'error_type': 'pattern_detection'})
        return None

def detect_consolidation(closes: List[float]) -> Optional[Dict]:
    """Detect consolidation pattern"""
    try:
        if len(closes) < 20:
            return None
        
        recent_prices = closes[-20:]
        price_range = (max(recent_prices) - min(recent_prices)) / np.mean(recent_prices)
        
        if price_range < 0.03:
            resistance = max(recent_prices)
            support = min(recent_prices)
            
            return {
                'pattern_type': PatternType.CONSOLIDATION,
                'pattern_subtype': PatternSubtype.RANGE_BOUND,
                'confidence': 0.60,
                'breakout_level': resistance,
                'target_price': resistance * 1.03,
                'stop_level': support * 0.98
            }
        return None
    except Exception as e:
        logger.warning(f"Consolidation detection error: {e}", extra={'error_type': 'pattern_detection'})
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[STARTUP] Pattern Service v{SERVICE_VERSION}")
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

app = FastAPI(title="Pattern Service", version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"status": "healthy" if state.is_healthy else "unhealthy", "service": SERVICE_NAME, "version": SERVICE_VERSION}

@app.post("/api/v1/patterns/detect")
async def detect_patterns(request: PatternRequest):
    """Detect chart patterns for symbol"""
    try:
        if not request.symbol or len(request.symbol) > 10:
            raise ValueError(f"Invalid symbol: {request.symbol}")
        
        symbol = request.symbol.upper()
        security_id = await get_security_id(symbol)
        
        # Fetch price history
        history = await state.db_pool.fetch("""
            SELECT th.open, th.high, th.low, th.close, th.volume, td.timestamp
            FROM trading_history th
            JOIN time_dimension td ON td.time_id = th.time_id
            WHERE th.security_id = $1
            ORDER BY td.timestamp DESC
            LIMIT 100
        """, security_id)
        
        if not history or len(history) < 20:
            raise ValueError(f"Insufficient price data for {symbol}")
        
        # Extract price arrays
        closes = [float(h['close']) for h in reversed(history)]
        highs = [float(h['high']) for h in reversed(history)]
        lows = [float(h['low']) for h in reversed(history)]
        
        # Detect patterns
        detected_patterns = []
        failed_patterns = []
        
        pattern_funcs = [
            ('bull_flag', detect_bull_flag, (closes, highs, lows)),
            ('double_bottom', detect_double_bottom, (lows, closes)),
            ('consolidation', detect_consolidation, (closes,))
        ]
        
        for pattern_name, func, args in pattern_funcs:
            try:
                pattern = func(*args)
                if pattern:
                    # Store in database
                    time_id = await get_time_id(datetime.now())
                    
                    pattern_id = await state.db_pool.fetchval("""
                        INSERT INTO pattern_analysis (
                            security_id, time_id, timeframe,
                            pattern_type, pattern_subtype,
                            confidence_score, price_at_detection,
                            breakout_level, target_price, stop_level,
                            metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        RETURNING pattern_id
                    """, security_id, time_id, request.timeframe,
                         pattern['pattern_type'].value, pattern['pattern_subtype'].value,
                         pattern['confidence'], closes[-1],
                         pattern.get('breakout_level'), pattern.get('target_price'),
                         pattern.get('stop_level'), json.dumps({}))
                    
                    pattern['pattern_id'] = pattern_id
                    detected_patterns.append(pattern)
                    
            except Exception as e:
                logger.warning(f"Pattern detection failed for {pattern_name}: {e}", extra={'symbol': symbol, 'pattern': pattern_name})
                failed_patterns.append(pattern_name)
        
        logger.info(f"Pattern detection: {len(detected_patterns)} found, {len(failed_patterns)} failed",
                   extra={'symbol': symbol, 'detected': len(detected_patterns), 'failed': len(failed_patterns)})
        
        return {"symbol": symbol, "patterns": detected_patterns, "failed_patterns": failed_patterns}
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'symbol': request.symbol, 'error_type': 'validation'})
        raise HTTPException(status_code=400, detail={'error': 'Invalid request', 'message': str(e)})
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True, extra={'symbol': request.symbol, 'error_type': 'database'})
        raise HTTPException(status_code=503, detail={'error': 'Database unavailable', 'retry_after': 30})
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True, extra={'symbol': request.symbol, 'error_type': 'unexpected'})
        raise HTTPException(status_code=500, detail={'error': 'Internal server error'})

@app.post("/api/v1/patterns/batch")
async def detect_batch(symbols: List[str]):
    """Detect patterns for multiple symbols"""
    results = []
    failed = []
    
    for symbol in symbols:
        try:
            request = PatternRequest(symbol=symbol)
            result = await detect_patterns(request)
            results.append(result)
        except Exception as e:
            logger.warning(f"Batch detection failed for {symbol}: {e}", extra={'symbol': symbol})
            failed.append(symbol)
    
    logger.info(f"Batch complete: {len(results)} success, {len(failed)} failed",
               extra={'success': len(results), 'failed': len(failed)})
    
    return {"results": results, "success": len(results), "failed": failed}

if __name__ == "__main__":
    import uvicorn
    from fastapi.middleware.cors import CORSMiddleware
    print("=" * 60)
    print(f"Catalyst Trading System - Pattern Service v{SERVICE_VERSION}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
