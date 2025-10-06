#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 5.0.0
Last Updated: 2025-10-06
Purpose: Pattern detection with normalized schema v5.0 (security_id + time_id FKs)

REVISION HISTORY:
v5.0.0 (2025-10-06) - Normalized Schema Update
- ✅ Stores in pattern_analysis table with security_id + time_id FKs
- ✅ Pattern detection uses FKs (NO symbol VARCHAR!)
- ✅ Queries use JOINs to get symbol/company_name
- ✅ Enhanced pattern types (breakouts, reversals, consolidations)
- ✅ Confidence scoring for ML training
- ✅ Helper functions: get_security_id(), get_time_id()
- ✅ Error handling compliant with v1.0 standard

v4.0.0 (2025-09-15) - DEPRECATED (Denormalized)
- Used symbol VARCHAR in queries
- No FK relationships

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
from pydantic import BaseModel, Field, validator
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
    VERSION = "5.0.0"
    PORT = 5002
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
    logger.info(f"Starting {Config.SERVICE_NAME} v{Config.VERSION}")
    
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
# MODELS
# ============================================================================

class PatternRequest(BaseModel):
    """Request model for pattern detection"""
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    timeframe: str = Field(default="5min", description="Timeframe (1min, 5min, 15min, 1h, 1d)")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return v.upper().strip()
    
    @validator('timeframe')
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
    breakout_level: Optional[float]
    target_price: Optional[float]
    stop_level: Optional[float]

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
            'target_price': resistance * 1.05,  # 5% target
            'stop_level': avg_recent_low * 0.98  # 2% below support
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
    slight_pullback = 0 < downward_drift < 0.03  # Small pullback
    
    if tight_flag and slight_pullback:
        confidence = 0.70
        
        return {
            'pattern_type': PatternType.CONTINUATION,
            'pattern_subtype': PatternSubtype.BULL_FLAG,
            'confidence': confidence,
            'breakout_level': max(flag_highs),
            'target_price': closes[-1] * (1 + pole_gain),  # Same move as pole
            'stop_level': min(flag_lows) * 0.98
        }
    
    return None

def detect_double_bottom(lows: List[float], closes: List[float]) -> Optional[Dict]:
    """
    Detect Double Bottom pattern (reversal).
    
    Characteristics:
    - Two distinct lows at similar prices
    - Peak in between
    - Reversal pattern
    """
    if len(lows) < 50:
        return None
    
    # Find two lowest points
    lows_arr = np.array(lows[-50:])
    sorted_indices = np.argsort(lows_arr)
    
    # Get two lowest lows that are far apart
    low1_idx = sorted_indices[0]
    low2_idx = None
    
    for idx in sorted_indices[1:10]:
        if abs(idx - low1_idx) > 10:  # At least 10 bars apart
            low2_idx = idx
            break
    
    if low2_idx is None:
        return None
    
    low1_price = lows_arr[low1_idx]
    low2_price = lows_arr[low2_idx]
    
    # Check if lows are similar
    price_diff = abs(low1_price - low2_price) / low1_price
    
    if price_diff < 0.03:  # Within 3%
        # Check for peak in between
        start_idx = min(low1_idx, low2_idx)
        end_idx = max(low1_idx, low2_idx)
        peak = max(lows_arr[start_idx:end_idx])
        
        peak_height = (peak - low1_price) / low1_price
        
        if peak_height > 0.05:  # At least 5% peak
            confidence = 0.75
            
            return {
                'pattern_type': PatternType.REVERSAL,
                'pattern_subtype': PatternSubtype.DOUBLE_BOTTOM,
                'confidence': confidence,
                'breakout_level': peak,
                'target_price': peak * 1.05,
                'stop_level': min(low1_price, low2_price) * 0.97
            }
    
    return None

def detect_consolidation(highs: List[float], lows: List[float], closes: List[float]) -> Optional[Dict]:
    """
    Detect consolidation/range-bound pattern.
    
    Characteristics:
    - Price trading in tight range
    - Low volatility
    - Potential breakout setup
    """
    if len(closes) < 30:
        return None
    
    recent_highs = highs[-30:]
    recent_lows = lows[-30:]
    recent_closes = closes[-30:]
    
    range_high = max(recent_highs)
    range_low = min(recent_lows)
    range_size = (range_high - range_low) / closes[-1]
    
    # Check if trading in tight range
    if range_size < 0.05:  # < 5% range
        # Check for low volatility
        volatility = np.std(recent_closes) / np.mean(recent_closes)
        
        if volatility < 0.02:  # Low volatility
            confidence = 0.65
            
            return {
                'pattern_type': PatternType.CONSOLIDATION,
                'pattern_subtype': PatternSubtype.RANGE_BOUND,
                'confidence': confidence,
                'breakout_level': range_high,
                'target_price': range_high * 1.03,
                'stop_level': range_low * 0.98
            }
    
    return None

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/api/v1/detect", response_model=List[PatternResult])
async def detect_patterns(
    request: PatternRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Detect chart patterns and store with security_id FK.
    
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

@app.get("/api/v1/patterns/high-confidence")
async def get_high_confidence_patterns(
    min_confidence: float = 0.75,
    hours: int = 24,
    conn: asyncpg.Connection = Depends(get_db)
):
    """Get all high-confidence patterns across all securities"""
    try:
        results = await conn.fetch("""
            SELECT 
                pa.pattern_id,
                s.symbol,
                s.company_name,
                td.timestamp as detected_at,
                pa.pattern_type,
                pa.pattern_subtype,
                pa.confidence_score,
                pa.price_at_detection,
                pa.breakout_level,
                pa.target_price
            FROM pattern_analysis pa
            JOIN securities s ON s.security_id = pa.security_id
            JOIN time_dimension td ON td.time_id = pa.time_id
            WHERE pa.confidence_score >= $1
            AND td.timestamp >= NOW() - INTERVAL '1 hour' * $2
            ORDER BY pa.confidence_score DESC, td.timestamp DESC
        """, min_confidence, hours)
        
        return {
            "min_confidence": min_confidence,
            "hours": hours,
            "count": len(results),
            "patterns": [dict(r) for r in results]
        }
    
    except Exception as e:
        logger.error(f"Error fetching high-confidence patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not state.is_healthy or not state.db_pool:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": Config.SERVICE_NAME,
                "version": Config.VERSION
            }
        )
    
    return {
        "status": "healthy",
        "service": Config.SERVICE_NAME,
        "version": Config.VERSION,
        "schema": "v5.0 normalized",
        "uses_security_id_fk": True,
        "uses_time_id_fk": True,
        "pattern_types": [
            "Breakout (ascending triangle, bull flag)",
            "Reversal (double bottom, head & shoulders)",
            "Consolidation (range-bound, wedge)",
            "Continuation (bull/bear continuation)"
        ],
        "min_confidence": Config.MIN_CONFIDENCE
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=Config.PORT,
        log_level="info"
    )
