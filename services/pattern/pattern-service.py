#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 5.2.0
Last Updated: 2025-10-16
Purpose: Pattern detection with Redis caching and normalized schema

REVISION HISTORY:
v5.2.0 (2025-10-16) - Redis Integration & Import Fixes
- Added Redis caching support (optional, graceful degradation)
- Fixed missing CORSMiddleware import
- Uses Docker service name 'redis' not 'localhost'
- Fixed aclose() deprecation warning
- Cached pattern results for 60 seconds

v5.1.1 (2025-10-16) - Fix DATABASE_URL only Digital Ocean
v5.1.0 (2025-10-13) - Production Error Handling Upgrade

Description of Service:
Pattern detection with optional Redis caching and proper error handling.
Detects breakout, reversal, and consolidation patterns with confidence scoring.
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
from contextlib import asynccontextmanager
from enum import Enum

import asyncpg
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware  # FIXED: Added missing import
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Optional Redis support
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# ============================================================================
# CONFIGURATION
# ============================================================================

SERVICE_NAME = "Pattern Detection Service"
SERVICE_VERSION = "5.2.0"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "5002"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Redis configuration - use Docker service name
REDIS_HOST = os.getenv("REDIS_HOST", "redis")  # Docker service name, not localhost!
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CACHE_TTL = 60  # seconds

# Global connections
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None

# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class PatternType(str, Enum):
    """Types of patterns we detect"""
    # Breakout patterns
    ASCENDING_TRIANGLE = "ascending_triangle"
    BULL_FLAG = "bull_flag"
    CUP_AND_HANDLE = "cup_and_handle"
    
    # Reversal patterns
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERTED_HEAD_AND_SHOULDERS = "inverted_head_and_shoulders"
    
    # Consolidation patterns
    RANGE_BOUND = "range_bound"
    SYMMETRICAL_TRIANGLE = "symmetrical_triangle"
    WEDGE = "wedge"

class PatternDetectionRequest(BaseModel):
    """Request for pattern detection"""
    symbol: str
    timeframe: str = Field(default="1d", description="Timeframe: 5m, 15m, 1h, 1d")
    lookback_periods: int = Field(default=100, ge=50, le=500)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        return v.upper().strip()

class DetectedPattern(BaseModel):
    """A detected pattern"""
    pattern_type: PatternType
    confidence: float = Field(ge=0.0, le=1.0)
    start_price: float
    current_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    description: str

class PatternResponse(BaseModel):
    """Response with all detected patterns"""
    symbol: str
    security_id: int
    timestamp: datetime
    timeframe: str
    patterns: List[DetectedPattern]
    strongest_pattern: Optional[PatternType] = None
    overall_confidence: float = Field(ge=0.0, le=1.0)

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    timestamp: datetime
    database: str = "disconnected"
    redis: str = "disconnected"

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with optional Redis"""
    global db_pool, redis_client
    
    try:
        # Database pool - REQUIRED
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=10
        )
        logger.info("Database pool created successfully")
        
        # Test database connection
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            logger.info("Database connection verified")
        
        # Redis - OPTIONAL
        if REDIS_AVAILABLE:
            try:
                redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                await redis_client.ping()
                logger.info(f"Redis connected at {REDIS_HOST}:{REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Redis not available: {e}. Continuing without caching.")
                redis_client = None
        else:
            logger.info("Redis library not installed. Running without caching.")
        
        logger.info(f"{SERVICE_NAME} v{SERVICE_VERSION} started on port {SERVICE_PORT}")
        logger.info(f"Status: Database=Connected | Redis={'Connected' if redis_client else 'Not Available'}")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
        
    finally:
        # Cleanup
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")
        
        if redis_client:
            await redis_client.aclose()  # Use aclose() not close()
            logger.info("Redis connection closed")
        
        logger.info(f"{SERVICE_NAME} shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================================
# PATTERN DETECTION LOGIC
# ============================================================================

def detect_ascending_triangle(prices: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Optional[DetectedPattern]:
    """Detect ascending triangle pattern"""
    try:
        if len(prices) < 20:
            return None
        
        # Check for flat resistance line
        recent_highs = highs[-20:]
        resistance_level = np.max(recent_highs)
        resistance_touches = np.sum(np.abs(recent_highs - resistance_level) / resistance_level < 0.01)
        
        if resistance_touches < 3:
            return None
        
        # Check for ascending support line
        recent_lows = lows[-20:]
        if np.polyfit(range(len(recent_lows)), recent_lows, 1)[0] <= 0:
            return None
        
        confidence = min(resistance_touches * 0.25, 0.9)
        
        return DetectedPattern(
            pattern_type=PatternType.ASCENDING_TRIANGLE,
            confidence=confidence,
            start_price=float(prices[0]),
            current_price=float(prices[-1]),
            target_price=float(resistance_level * 1.05),
            stop_loss=float(recent_lows[-1] * 0.98),
            description=f"Ascending triangle with resistance at {resistance_level:.2f}"
        )
    except Exception as e:
        logger.error(f"Error detecting ascending triangle: {e}")
        return None

def detect_bull_flag(prices: np.ndarray, volumes: np.ndarray) -> Optional[DetectedPattern]:
    """Detect bull flag pattern"""
    try:
        if len(prices) < 30:
            return None
        
        # Look for strong uptrend (pole)
        pole_prices = prices[-30:-10]
        pole_return = (pole_prices[-1] - pole_prices[0]) / pole_prices[0]
        
        if pole_return < 0.1:  # Need at least 10% gain for pole
            return None
        
        # Look for consolidation (flag)
        flag_prices = prices[-10:]
        flag_volatility = np.std(flag_prices) / np.mean(flag_prices)
        
        if flag_volatility > 0.03:  # Too volatile for a flag
            return None
        
        # Check volume decline during flag
        flag_volume = np.mean(volumes[-10:])
        pole_volume = np.mean(volumes[-30:-10])
        
        if flag_volume >= pole_volume:
            return None
        
        confidence = min(0.5 + (pole_return * 2), 0.85)
        
        return DetectedPattern(
            pattern_type=PatternType.BULL_FLAG,
            confidence=confidence,
            start_price=float(prices[-30]),
            current_price=float(prices[-1]),
            target_price=float(prices[-1] * (1 + pole_return * 0.7)),
            stop_loss=float(min(flag_prices) * 0.98),
            description=f"Bull flag after {pole_return*100:.1f}% pole move"
        )
    except Exception as e:
        logger.error(f"Error detecting bull flag: {e}")
        return None

def detect_double_bottom(prices: np.ndarray, lows: np.ndarray) -> Optional[DetectedPattern]:
    """Detect double bottom reversal pattern"""
    try:
        if len(prices) < 40:
            return None
        
        # Find two prominent lows
        first_low_idx = np.argmin(lows[-40:-20])
        first_low = lows[-40:-20][first_low_idx]
        
        second_low_idx = np.argmin(lows[-20:])
        second_low = lows[-20:][second_low_idx]
        
        # Check if lows are roughly equal (within 2%)
        if abs(first_low - second_low) / first_low > 0.02:
            return None
        
        # Check for peak between lows
        middle_section = prices[-30:-10]
        peak = np.max(middle_section)
        
        if peak <= first_low * 1.05:  # Need decent peak between bottoms
            return None
        
        # Current price should be breaking above neckline
        neckline = peak
        if prices[-1] < neckline * 0.98:
            return None
        
        confidence = 0.7
        
        return DetectedPattern(
            pattern_type=PatternType.DOUBLE_BOTTOM,
            confidence=confidence,
            start_price=float(first_low),
            current_price=float(prices[-1]),
            target_price=float(neckline + (neckline - first_low)),
            stop_loss=float(min(first_low, second_low) * 0.98),
            description=f"Double bottom at {first_low:.2f} with neckline at {neckline:.2f}"
        )
    except Exception as e:
        logger.error(f"Error detecting double bottom: {e}")
        return None

async def detect_patterns(
    symbol: str,
    timeframe: str,
    lookback_periods: int
) -> List[DetectedPattern]:
    """Detect all patterns for a symbol"""
    
    patterns = []
    
    try:
        # Get security_id
        security_id = await get_security_id(symbol)
        
        # Fetch price data
        data = await fetch_price_history(security_id, timeframe, lookback_periods)
        
        if data is None or len(data) < 20:
            logger.warning(f"Insufficient data for {symbol}")
            return patterns
        
        prices = np.array([float(row['close_price']) for row in data])
        highs = np.array([float(row['high_price']) for row in data])
        lows = np.array([float(row['low_price']) for row in data])
        volumes = np.array([int(row['volume']) for row in data])
        
        # Detect various patterns
        ascending_triangle = detect_ascending_triangle(prices, highs, lows)
        if ascending_triangle:
            patterns.append(ascending_triangle)
        
        bull_flag = detect_bull_flag(prices, volumes)
        if bull_flag:
            patterns.append(bull_flag)
        
        double_bottom = detect_double_bottom(prices, lows)
        if double_bottom:
            patterns.append(double_bottom)
        
        # Add more pattern detectors as needed...
        
    except Exception as e:
        logger.error(f"Error detecting patterns for {symbol}: {e}", exc_info=True)
    
    return patterns

# ============================================================================
# DATABASE HELPERS
# ============================================================================

async def get_security_id(symbol: str) -> int:
    """Get security_id from symbol"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT security_id FROM security_dimension WHERE symbol = $1",
            symbol
        )
        if not result:
            # Create new security if not exists
            result = await conn.fetchval(
                """
                INSERT INTO security_dimension (symbol, company_name, sector, exchange, is_active)
                VALUES ($1, $2, 'UNKNOWN', 'UNKNOWN', true)
                ON CONFLICT (symbol) DO UPDATE SET symbol = EXCLUDED.symbol
                RETURNING security_id
                """,
                symbol, symbol
            )
        return result

async def fetch_price_history(
    security_id: int,
    timeframe: str,
    periods: int
) -> Optional[List[Dict]]:
    """Fetch price history from database"""
    
    # Map timeframe to interval
    interval_map = {
        "5m": "5 minutes",
        "15m": "15 minutes",
        "1h": "1 hour",
        "1d": "1 day"
    }
    interval = interval_map.get(timeframe, "1 day")
    
    async with db_pool.acquire() as conn:
        query = f"""
            SELECT 
                th.open_price,
                th.high_price,
                th.low_price,
                th.close_price,
                th.volume,
                td.timestamp
            FROM trading_history th
            JOIN time_dimension td ON td.time_id = th.time_id
            WHERE th.security_id = $1
                AND td.timestamp >= NOW() - INTERVAL '{periods} {interval}'
            ORDER BY td.timestamp ASC
        """
        
        rows = await conn.fetch(query, security_id)
        return [dict(row) for row in rows] if rows else None

async def store_pattern_detection(
    security_id: int,
    pattern_type: str,
    confidence: float,
    metadata: Dict
):
    """Store detected pattern in database"""
    
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pattern_analysis (
                security_id,
                pattern_type,
                confidence,
                detection_time,
                metadata
            ) VALUES ($1, $2, $3, NOW(), $4)
            """,
            security_id,
            pattern_type,
            confidence,
            json.dumps(metadata)
        )

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    
    db_status = "disconnected"
    redis_status = "disconnected"
    
    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    try:
        if redis_client:
            await redis_client.ping()
            redis_status = "healthy"
    except:
        redis_status = "unavailable"
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        timestamp=datetime.now(),
        database=db_status,
        redis=redis_status
    )

@app.post("/api/v1/patterns/detect", response_model=PatternResponse)
async def detect_patterns_endpoint(request: PatternDetectionRequest):
    """Detect patterns for a symbol"""
    
    try:
        # Try cache first if Redis is available
        cache_key = f"patterns:{request.symbol}:{request.timeframe}:{request.lookback_periods}"
        
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.info(f"Cache hit for {request.symbol} patterns")
                    return PatternResponse(**json.loads(cached))
            except Exception as e:
                logger.debug(f"Cache read failed: {e}")
        
        # Get security_id
        security_id = await get_security_id(request.symbol)
        
        # Detect patterns
        patterns = await detect_patterns(
            request.symbol,
            request.timeframe,
            request.lookback_periods
        )
        
        # Find strongest pattern
        strongest_pattern = None
        overall_confidence = 0.0
        
        if patterns:
            patterns.sort(key=lambda p: p.confidence, reverse=True)
            strongest_pattern = patterns[0].pattern_type
            overall_confidence = patterns[0].confidence
            
            # Store in database
            for pattern in patterns:
                await store_pattern_detection(
                    security_id,
                    pattern.pattern_type.value,
                    pattern.confidence,
                    {
                        "timeframe": request.timeframe,
                        "target_price": pattern.target_price,
                        "stop_loss": pattern.stop_loss
                    }
                )
        
        # Create response
        response = PatternResponse(
            symbol=request.symbol,
            security_id=security_id,
            timestamp=datetime.now(),
            timeframe=request.timeframe,
            patterns=patterns,
            strongest_pattern=strongest_pattern,
            overall_confidence=overall_confidence
        )
        
        # Cache if Redis is available
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key,
                    CACHE_TTL,
                    response.model_dump_json()
                )
            except Exception as e:
                logger.debug(f"Cache write failed: {e}")
        
        logger.info(f"Detected {len(patterns)} patterns for {request.symbol}")
        
        return response
        
    except asyncpg.PostgresError as e:
        logger.error(f"Database error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")
    except ValueError as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/v1/patterns/{symbol}")
async def get_patterns(symbol: str, timeframe: str = "1d"):
    """Get patterns for a symbol (convenience endpoint)"""
    
    request = PatternDetectionRequest(
        symbol=symbol,
        timeframe=timeframe
    )
    return await detect_patterns_endpoint(request)

@app.post("/api/v1/patterns/batch")
async def detect_batch(symbols: List[str], timeframe: str = "1d"):
    """Detect patterns for multiple symbols"""
    
    results = []
    success_count = 0
    failure_count = 0
    
    for symbol in symbols[:20]:  # Limit to 20 symbols
        try:
            request = PatternDetectionRequest(
                symbol=symbol,
                timeframe=timeframe
            )
            result = await detect_patterns_endpoint(request)
            results.append(result.model_dump())
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to detect patterns for {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "error": str(e)
            })
            failure_count += 1
    
    return {
        "results": results,
        "success_count": success_count,
        "failure_count": failure_count,
        "timestamp": datetime.now()
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVICE_PORT,
        log_level="info"
    )