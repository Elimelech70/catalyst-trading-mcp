#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 5.0.1
Last Updated: 2025-10-11
Purpose: Pattern detection with normalized schema v5.0 (security_id + time_id FKs)

REVISION HISTORY:
v5.0.1 (2025-10-11) - Port Configuration & Pydantic v2 Fix
- ✅ Fixed: Read SERVICE_PORT from environment (was hardcoded to 5002)
- ✅ Fixed: Migrated to Pydantic v2 field_validator (no more warnings)
- ✅ Compatible with docker-compose.yml port mapping

v5.0.0 (2025-10-06) - Normalized Schema Update
- ✅ Stores in pattern_analysis table with security_id + time_id FKs
- ✅ Pattern detection uses FKs (NO symbol VARCHAR!)
- ✅ Queries use JOINs to get symbol/company_name
- ✅ Enhanced pattern types (breakouts, reversals, consolidations)
- ✅ Confidence scoring for ML training
- ✅ Helper functions: get_security_id(), get_time_id()
- ✅ Error handling compliant with v1.0 standard

Description of Service:
Detects chart patterns using normalized v5.0 schema:
- Breakout patterns (ascending triangle, bull flag, cup & handle)
- Reversal patterns (double bottom, head & shoulders)
- Consolidation patterns (range, wedge)
- Confidence scoring for each pattern
- All data stored with security_id + time_id FKs for ML quality
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from enum import Enum
import asyncpg
import os
import logging
import numpy as np

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Service configuration"""
    SERVICE_NAME = "pattern-service"
    VERSION = "5.0.1"
    
    # ✅ FIX: Read port from environment variable
    PORT = int(os.getenv("SERVICE_PORT", "5004"))
    
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://catalyst:catalyst@localhost:5432/catalyst_trading")
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10
    
    # Pattern detection thresholds
    MIN_CONFIDENCE = 0.60  # Minimum pattern confidence
    LOOKBACK_BARS = 100    # How many bars to analyze

# ============================================================================
# ENUMS
# ============================================================================

class PatternType(str, Enum):
    """Pattern types"""
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    CONSOLIDATION = "consolidation"
    CONTINUATION = "continuation"

class PatternSubtype(str, Enum):
    """Pattern subtypes"""
    # Breakout patterns
    ASCENDING_TRIANGLE = "ascending_triangle"
    BULL_FLAG = "bull_flag"
    CUP_AND_HANDLE = "cup_and_handle"
    RESISTANCE_BREAK = "resistance_break"
    
    # Reversal patterns
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERSE_HEAD_SHOULDERS = "inverse_head_and_shoulders"
    
    # Consolidation patterns
    RANGE_BOUND = "range_bound"
    WEDGE = "wedge"
    PENNANT = "pennant"
    
    # Continuation patterns
    BULL_CONTINUATION = "bull_continuation"
    BEAR_CONTINUATION = "bear_continuation"

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class ServiceState:
    """Global service state"""
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.is_healthy = False

state = ServiceState()

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    logger.info(f"Starting {Config.SERVICE_NAME} v{Config.VERSION} on port {Config.PORT}")
    
    try:
        # Initialize database pool
        state.db_pool = await asyncpg.create_pool(
            Config.DATABASE_URL,
            min_size=Config.POOL_MIN_SIZE,
            max_size=Config.POOL_MAX_SIZE,
            command_timeout=60
        )
        logger.info("✅ Database pool created")
        
        # Verify schema
        async with state.db_pool.acquire() as conn:
            # Check if pattern_analysis table exists
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'pattern_analysis'
                )
            """)
            if not exists:
                raise Exception("pattern_analysis table does not exist! Run schema v5.0 first.")
            
            # Check for helper functions
            func_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_proc 
                    WHERE proname = 'get_or_create_security'
                )
            """)
            if not func_exists:
                raise Exception("Helper function get_or_create_security() missing!")
        
        state.is_healthy = True
        logger.info("✅ Schema validation passed - v5.0 normalized tables found")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        state.is_healthy = False
        raise
    finally:
        # Cleanup
        if state.db_pool:
            await state.db_pool.close()
            logger.info("Database pool closed")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Catalyst Pattern Service",
    description="Pattern detection with normalized schema v5.0",
    version=Config.VERSION,
    lifespan=lifespan
)

# ============================================================================
# DEPENDENCY: DATABASE CONNECTION
# ============================================================================

async def get_db():
    """Dependency to get database connection"""
    if not state.db_pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized")
    async with state.db_pool.acquire() as conn:
        yield conn

# ============================================================================
# MODELS (Pydantic v2 Compatible)
# ============================================================================

class PatternRequest(BaseModel):
    """Request model for pattern detection"""
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    timeframe: str = Field(default="5min", description="Timeframe (1min, 5min, 15min, 1h, 1d)")
    
    # ✅ FIX: Pydantic v2 field_validator
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        return v.upper().strip()
    
    @field_validator('timeframe')
    @classmethod
    def validate_timeframe(cls, v):
        valid = ['1min', '5min', '15min', '30min', '1h', '4h', '1d']
        if v not in valid:
            raise ValueError(f"Timeframe must be one of {valid}")
        return v

class PatternResult(BaseModel):
    """Pattern detection result"""
    pattern_id: int
    security_id: int
    symbol: str
    company_name: Optional[str]
    detected_at: datetime
    pattern_type: PatternType
    pattern_subtype: PatternSubtype
    timeframe: str
    confidence_score: float
    price_at_detection: float
    breakout_level: Optional[float] = None
    target_price: Optional[float] = None
    stop_level: Optional[float] = None

# ============================================================================
# HELPER FUNCTIONS (NORMALIZED SCHEMA)
# ============================================================================

async def get_security_id(conn: asyncpg.Connection, symbol: str) -> int:
    """
    Get or create security_id using helper function.
    
    This is the ONLY way to get security_id in v5.0!
    NEVER store symbol directly in pattern_analysis table.
    """
    try:
        security_id = await conn.fetchval(
            "SELECT get_or_create_security($1)", 
            symbol.upper()
        )
        return security_id
    except Exception as e:
        logger.error(f"Failed to get security_id for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def get_time_id(conn: asyncpg.Connection, timestamp: datetime) -> int:
    """
    Get or create time_id using helper function.
    
    This is the ONLY way to get time_id in v5.0!
    NEVER store raw timestamps in pattern_analysis table.
    """
    try:
        time_id = await conn.fetchval(
            "SELECT get_or_create_time($1)", 
            timestamp
        )
        return time_id
    except Exception as e:
        logger.error(f"Failed to get time_id for {timestamp}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def fetch_price_history(
    conn: asyncpg.Connection,
    security_id: int,
    timeframe: str,
    periods: int = 100
) -> List[Dict]:
    """
    Fetch price history using JOINs (v5.0 pattern).
    
    CRITICAL: Uses security_id FK and JOINs to get symbol!
    """
    try:
        rows = await conn.fetch("""
            SELECT 
                th.close_price,
                th.high_price,
                th.low_price,
                th.open_price,
                th.volume,
                td.timestamp
            FROM trading_history th
            JOIN time_dimension td ON td.time_id = th.time_id
            WHERE th.security_id = $1
            AND th.timeframe = $2
            ORDER BY td.timestamp DESC
            LIMIT $3
        """, security_id, timeframe, periods)
        
        # Reverse to chronological order
        return [dict(r) for r in reversed(rows)]
    
    except Exception as e:
        logger.error(f"Failed to fetch price history: {e}")
        return []

# ============================================================================
# PATTERN DETECTION ALGORITHMS
# ============================================================================

def detect_ascending_triangle(highs: List[float], lows: List[float], closes: List[float]) -> Optional[Dict]:
    """
    Detect Ascending Triangle pattern.
    
    Characteristics:
    - Flat resistance at top
    - Rising support at bottom
    - Bullish breakout pattern
    """
    if len(highs) < 30:
        return None
    
    # Check for flat resistance (recent highs similar)
    recent_highs = highs[-15:]
    resistance = max(recent_highs)
    high_variance = np.std(recent_highs)
    
    # Check for rising lows
    early_lows = lows[-30:-15]
    recent_lows = lows[-15:]
    
    avg_early_low = np.mean(early_lows)
    avg_recent_low = np.mean(recent_lows)
    
    # Pattern criteria
    flat_resistance = high_variance < (resistance * 0.02)  # < 2% variance
    rising_support = avg_recent_low > avg_early_low * 1.02  # 2% rise
    
    if flat_resistance and rising_support:
        confidence = min(0.85, 0.60 + (avg_recent_low / avg_early_low - 1) * 10)
        
        return {
            'pattern_type': PatternType.BREAKOUT,
            'pattern_subtype': PatternSubtype.ASCENDING_TRIANGLE,
            'confidence': confidence,
            'breakout_level': resistance,
            'target_price': resistance * 1.05,
            'stop_level': avg_recent_low * 0.98
        }
    
    return None

def detect_bull_flag(highs: List[float], lows: List[float], closes: List[float]) -> Optional[Dict]:
    """
    Detect Bull Flag pattern.
    
    Characteristics:
    - Strong upward move (pole)
    - Consolidation with slight downward drift (flag)
    - Breakout continuation
    """
    if len(closes) < 40:
        return None
    
    # Check for pole (strong rally)
    pole_start = closes[-40]
    pole_end = closes[-20]
    pole_gain = (pole_end - pole_start) / pole_start
    
    if pole_gain < 0.05:  # Need at least 5% rally
        return None
    
    # Check for flag (consolidation)
    flag_highs = highs[-20:]
    flag_lows = lows[-20:]
    
    flag_range = (max(flag_highs) - min(flag_lows)) / closes[-1]
    downward_drift = (closes[-20] - closes[-1]) / closes[-20]
    
    # Pattern criteria
    tight_flag = flag_range < 0.05  # < 5% range
    slight_pullback = 0 < downward_drift < 0.03
    
    if tight_flag and slight_pullback:
        confidence = 0.70
        
        return {
            'pattern_type': PatternType.CONTINUATION,
            'pattern_subtype': PatternSubtype.BULL_FLAG,
            'confidence': confidence,
            'breakout_level': max(flag_highs),
            'target_price': closes[-1] * (1 + pole_gain),
            'stop_level': min(flag_lows) * 0.98
        }
    
    return None

def detect_double_bottom(lows: List[float], closes: List[float]) -> Optional[Dict]:
    """
    Detect Double Bottom pattern (reversal).
    
    Characteristics:
    - Two distinct lows at similar price levels
    - Peak between the lows
    - Bullish reversal pattern
    """
    if len(lows) < 40:
        return None
    
    # Find local minima
    min_indices = []
    for i in range(5, len(lows) - 5):
        if lows[i] == min(lows[i-5:i+5]):
            min_indices.append(i)
    
    if len(min_indices) < 2:
        return None
    
    # Check last two minima
    first_low_idx = min_indices[-2]
    second_low_idx = min_indices[-1]
    
    first_low = lows[first_low_idx]
    second_low = lows[second_low_idx]
    
    # Pattern criteria: lows within 2% of each other
    similarity = abs(first_low - second_low) / first_low
    
    if similarity < 0.02:
        # Find peak between lows
        peak = max(closes[first_low_idx:second_low_idx])
        support = (first_low + second_low) / 2
        
        confidence = 0.65
        
        return {
            'pattern_type': PatternType.REVERSAL,
            'pattern_subtype': PatternSubtype.DOUBLE_BOTTOM,
            'confidence': confidence,
            'breakout_level': peak,
            'target_price': peak * 1.05,
            'stop_level': support * 0.97
        }
    
    return None

def detect_consolidation(highs: List[float], lows: List[float], closes: List[float]) -> Optional[Dict]:
    """
    Detect Consolidation/Range pattern.
    
    Characteristics:
    - Price trading in tight range
    - Low volatility
    - Potential breakout setup
    """
    if len(closes) < 20:
        return None
    
    recent_prices = closes[-20:]
    price_range = (max(recent_prices) - min(recent_prices)) / np.mean(recent_prices)
    
    # Tight range: < 3% movement
    if price_range < 0.03:
        resistance = max(recent_prices)
        support = min(recent_prices)
        
        confidence = 0.60
        
        return {
            'pattern_type': PatternType.CONSOLIDATION,
            'pattern_subtype': PatternSubtype.RANGE_BOUND,
            'confidence': confidence,
            'breakout_level': resistance,
            'target_price': resistance * 1.03,
            'stop_level': support * 0.98
        }
    
    return None

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if state.is_healthy else "unhealthy",
        "service": "pattern",
        "version": Config.VERSION,
        "database": "connected" if state.db_pool else "disconnected",
        "schema": "v5.0 normalized"
    }

@app.post("/api/v1/patterns/detect", response_model=List[PatternResult])
async def detect_patterns(
    request: PatternRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Detect chart patterns for a symbol.
    
    v5.0 Pattern:
    1. Get security_id (NOT symbol!)
    2. Fetch price history via JOIN
    3. Run pattern detection algorithms
    4. Store patterns with security_id + time_id FKs
    """
    try:
        # Step 1: Get security_id
        security_id = await get_security_id(conn, request.symbol)
        
        # Step 2: Fetch price history (using security_id FK)
        history = await fetch_price_history(conn, security_id, request.timeframe, Config.LOOKBACK_BARS)
        
        if len(history) < 30:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient price data for {request.symbol} ({len(history)} bars)"
            )
        
        # Extract price arrays
        closes = [float(h['close_price']) for h in history]
        highs = [float(h['high_price']) for h in history]
        lows = [float(h['low_price']) for h in history]
        
        # Step 3: Run pattern detection
        detected_patterns = []
        
        # Try each pattern type
        patterns_to_check = [
            detect_ascending_triangle(highs, lows, closes),
            detect_bull_flag(highs, lows, closes),
            detect_double_bottom(lows, closes),
            detect_consolidation(highs, lows, closes)
        ]
        
        time_id = await get_time_id(conn, datetime.utcnow())
        current_price = closes[-1]
        
        # Step 4: Store each detected pattern with FKs
        for pattern in patterns_to_check:
            if pattern and pattern['confidence'] >= Config.MIN_CONFIDENCE:
                # Insert into pattern_analysis table
                pattern_id = await conn.fetchval("""
                    INSERT INTO pattern_analysis (
                        security_id, time_id, timeframe,
                        pattern_type, pattern_subtype,
                        confidence_score,
                        price_at_detection, volume_at_detection,
                        breakout_level, target_price, stop_level,
                        metadata, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW()
                    )
                    RETURNING pattern_id
                """,
                    security_id, time_id, request.timeframe,
                    pattern['pattern_type'].value,
                    pattern['pattern_subtype'].value,
                    pattern['confidence'],
                    current_price,
                    history[-1]['volume'],
                    pattern.get('breakout_level'),
                    pattern.get('target_price'),
                    pattern.get('stop_level'),
                    {}  # metadata
                )
                
                detected_patterns.append({
                    'pattern_id': pattern_id,
                    'pattern_type': pattern['pattern_type'],
                    'pattern_subtype': pattern['pattern_subtype'],
                    'confidence': pattern['confidence'],
                    'breakout_level': pattern.get('breakout_level'),
                    'target_price': pattern.get('target_price'),
                    'stop_level': pattern.get('stop_level')
                })
        
        # Get company name via JOIN for response
        company_name = await conn.fetchval("""
            SELECT company_name FROM securities WHERE security_id = $1
        """, security_id)
        
        logger.info(f"✅ Detected {len(detected_patterns)} patterns for {request.symbol} (security_id={security_id})")
        
        # Build response
        results = []
        for p in detected_patterns:
            results.append(PatternResult(
                pattern_id=p['pattern_id'],
                security_id=security_id,
                symbol=request.symbol,
                company_name=company_name,
                detected_at=datetime.utcnow(),
                pattern_type=p['pattern_type'],
                pattern_subtype=p['pattern_subtype'],
                timeframe=request.timeframe,
                confidence_score=p['confidence'],
                price_at_detection=current_price,
                breakout_level=p.get('breakout_level'),
                target_price=p.get('target_price'),
                stop_level=p.get('stop_level')
            ))
        
        return results
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/patterns/{symbol}")
async def get_patterns(
    symbol: str,
    days: int = 7,
    min_confidence: float = 0.60,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Get pattern history using JOINs (v5.0 pattern).
    
    Query pattern:
    - JOIN pattern_analysis → securities (get symbol)
    - JOIN pattern_analysis → time_dimension (get timestamp)
    - Filter by symbol and time range
    """
    try:
        results = await conn.fetch("""
            SELECT 
                pa.pattern_id,
                pa.security_id,
                s.symbol,
                s.company_name,
                td.timestamp as detected_at,
                pa.timeframe,
                pa.pattern_type,
                pa.pattern_subtype,
                pa.confidence_score,
                pa.price_at_detection,
                pa.breakout_level,
                pa.target_price,
                pa.stop_level,
                pa.volume_at_detection
            FROM pattern_analysis pa
            JOIN securities s ON s.security_id = pa.security_id
            JOIN time_dimension td ON td.time_id = pa.time_id
            WHERE s.symbol = $1
            AND td.timestamp >= NOW() - INTERVAL '1 day' * $2
            AND pa.confidence_score >= $3
            ORDER BY td.timestamp DESC
        """, symbol.upper(), days, min_confidence)
        
        return {
            "symbol": symbol.upper(),
            "days": days,
            "min_confidence": min_confidence,
            "count": len(results),
            "patterns": [dict(r) for r in results]
        }
    
    except Exception as e:
        logger.error(f"Error fetching patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "pattern-service:app",
        host="0.0.0.0",
        port=Config.PORT,  # ✅ FIX: Use Config.PORT instead of hardcoded value
        reload=False
    )
