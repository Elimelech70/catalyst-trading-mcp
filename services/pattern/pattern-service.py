#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 4.1.0
Last Updated: 2025-08-31
Purpose: Pattern detection and recognition for trading signals

REVISION HISTORY:
v4.1.0 (2025-08-31) - Production-ready pattern recognition
- Multiple pattern detection algorithms
- Confidence scoring system
- Real-time pattern validation
- Historical pattern success tracking
- Integration with scanner pipeline

Description of Service:
This service detects trading patterns including:
1. Breakout patterns (flag, pennant, triangle)
2. Reversal patterns (head & shoulders, double top/bottom)
3. Continuation patterns (cup & handle, ascending triangle)
4. Volume patterns (volume breakout, accumulation)
5. Momentum patterns (squeeze, expansion)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import asyncpg
import aioredis
import numpy as np
import pandas as pd
import yfinance as yf
import json
import os
import logging
from enum import Enum
from dataclasses import dataclass

# Initialize FastAPI app
app = FastAPI(
    title="Pattern Recognition Service",
    version="4.1.0",
    description="Pattern detection service for Catalyst Trading System"
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
logger = logging.getLogger("pattern")

# === DATA MODELS ===

class PatternType(str, Enum):
    # Breakout Patterns
    FLAG = "flag"
    PENNANT = "pennant"
    TRIANGLE = "triangle"
    WEDGE = "wedge"
    
    # Reversal Patterns
    HEAD_SHOULDERS = "head_and_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIPLE_TOP = "triple_top"
    TRIPLE_BOTTOM = "triple_bottom"
    
    # Continuation Patterns
    CUP_HANDLE = "cup_and_handle"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    
    # Volume Patterns
    VOLUME_BREAKOUT = "volume_breakout"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    
    # Momentum Patterns
    SQUEEZE = "squeeze"
    EXPANSION = "expansion"
    DIVERGENCE = "divergence"

class PatternRequest(BaseModel):
    symbol: str
    timeframe: str = "5m"
    lookback_periods: int = Field(default=100, ge=20, le=500)

class PatternResponse(BaseModel):
    symbol: str
    pattern_detected: bool
    patterns: List[Dict]
    primary_pattern: Optional[str]
    confidence: float
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    timestamp: datetime

class BatchPatternRequest(BaseModel):
    symbols: List[str]
    timeframe: str = "5m"

# === SERVICE STATE ===

@dataclass
class PatternConfig:
    """Configuration for pattern detection"""
    min_confidence: float = 70.0
    lookback_short: int = 20
    lookback_medium: int = 50
    lookback_long: int = 100
    volume_threshold: float = 1.5
    breakout_threshold: float = 0.02

class PatternState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.config = PatternConfig()
        self.pattern_cache: Dict = {}
        self.pattern_success_rates: Dict = {}

state = PatternState()

# === STARTUP/SHUTDOWN ===

@app.on_event("startup")
async def startup():
    """Initialize pattern service"""
    logger.info("Starting Pattern Recognition Service v4.1")
    
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
        
        # Load pattern success rates from database
        await load_pattern_success_rates()
        
        logger.info("Pattern Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize pattern service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Clean up resources"""
    logger.info("Shutting down Pattern Service")
    
    if state.redis_client:
        await state.redis_client.close()
    
    if state.db_pool:
        await state.db_pool.close()

# === REST API ENDPOINTS ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pattern",
        "version": "4.1.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/detect", response_model=PatternResponse)
async def detect_patterns(request: PatternRequest):
    """Detect patterns for a single symbol"""
    
    try:
        # Check cache first
        cache_key = f"pattern:{request.symbol}:{request.timeframe}"
        cached = await get_cached_pattern(cache_key)
        if cached:
            return PatternResponse(**cached)
        
        # Get market data
        data = await get_market_data(
            request.symbol,
            request.timeframe,
            request.lookback_periods
        )
        
        if data is None or data.empty:
            raise HTTPException(status_code=404, detail=f"No data available for {request.symbol}")
        
        # Detect all patterns
        detected_patterns = []
        
        # Breakout patterns
        breakout_patterns = detect_breakout_patterns(data)
        detected_patterns.extend(breakout_patterns)
        
        # Reversal patterns
        reversal_patterns = detect_reversal_patterns(data)
        detected_patterns.extend(reversal_patterns)
        
        # Volume patterns
        volume_patterns = detect_volume_patterns(data)
        detected_patterns.extend(volume_patterns)
        
        # Momentum patterns
        momentum_patterns = detect_momentum_patterns(data)
        detected_patterns.extend(momentum_patterns)
        
        # Select primary pattern (highest confidence)
        primary_pattern = None
        max_confidence = 0
        
        if detected_patterns:
            primary_pattern = max(detected_patterns, key=lambda x: x["confidence"])
            max_confidence = primary_pattern["confidence"]
        
        # Calculate entry, stop loss, and take profit
        entry_price = None
        stop_loss = None
        take_profit = None
        
        if primary_pattern:
            entry_price = float(data['Close'].iloc[-1])
            
            # Calculate based on pattern type
            if primary_pattern["type"] in ["flag", "pennant", "triangle"]:
                # Breakout patterns
                stop_loss = entry_price * 0.98
                take_profit = entry_price * 1.04
                
            elif primary_pattern["type"] in ["double_bottom", "triple_bottom"]:
                # Bullish reversal
                stop_loss = primary_pattern.get("support", entry_price * 0.97)
                take_profit = entry_price * 1.06
                
            elif primary_pattern["type"] in ["double_top", "triple_top"]:
                # Bearish reversal
                stop_loss = primary_pattern.get("resistance", entry_price * 1.03)
                take_profit = entry_price * 0.96
                
            else:
                # Default
                stop_loss = entry_price * 0.98
                take_profit = entry_price * 1.03
        
        # Prepare response
        response = PatternResponse(
            symbol=request.symbol,
            pattern_detected=len(detected_patterns) > 0,
            patterns=detected_patterns,
            primary_pattern=primary_pattern["type"] if primary_pattern else None,
            confidence=max_confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now()
        )
        
        # Cache result
        await cache_pattern(cache_key, response.dict(), ttl=300)
        
        # Store in database
        await store_pattern_detection(request.symbol, response.dict())
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pattern detection failed for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Pattern detection failed: {str(e)}")

@app.post("/api/v1/detect/batch")
async def detect_patterns_batch(request: BatchPatternRequest):
    """Detect patterns for multiple symbols"""
    
    results = []
    
    for symbol in request.symbols:
        try:
            pattern_req = PatternRequest(symbol=symbol, timeframe=request.timeframe)
            result = await detect_patterns(pattern_req)
            results.append(result.dict())
        except Exception as e:
            logger.warning(f"Pattern detection failed for {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "pattern_detected": False,
                "error": str(e)
            })
    
    return {"results": results, "total": len(results)}

@app.post("/api/v1/analyze")
async def analyze_pattern(symbol: str):
    """Simplified analysis endpoint for orchestration"""
    
    request = PatternRequest(symbol=symbol)
    result = await detect_patterns(request)
    
    return {
        "symbol": symbol,
        "pattern": result.primary_pattern,
        "confidence": result.confidence,
        "signals": {
            "entry": result.entry_price,
            "stop_loss": result.stop_loss,
            "take_profit": result.take_profit
        }
    }

@app.get("/api/v1/patterns/success-rates")
async def get_pattern_success_rates():
    """Get historical success rates for patterns"""
    
    return {
        "success_rates": state.pattern_success_rates,
        "last_updated": datetime.now().isoformat()
    }

# === PATTERN DETECTION ALGORITHMS ===

def detect_breakout_patterns(data: pd.DataFrame) -> List[Dict]:
    """Detect breakout patterns"""
    
    patterns = []
    
    try:
        close_prices = data['Close'].values
        high_prices = data['High'].values
        low_prices = data['Low'].values
        volumes = data['Volume'].values
        
        # Flag pattern
        flag = detect_flag_pattern(close_prices, high_prices, low_prices)
        if flag:
            patterns.append(flag)
        
        # Triangle pattern
        triangle = detect_triangle_pattern(close_prices, high_prices, low_prices)
        if triangle:
            patterns.append(triangle)
        
        # Volume breakout
        if len(volumes) > 20:
            avg_volume = np.mean(volumes[-20:-1])
            current_volume = volumes[-1]
            
            if current_volume > avg_volume * state.config.volume_threshold:
                price_change = (close_prices[-1] - close_prices[-2]) / close_prices[-2]
                
                if abs(price_change) > state.config.breakout_threshold:
                    patterns.append({
                        "type": PatternType.VOLUME_BREAKOUT.value,
                        "confidence": min(95, 70 + (current_volume / avg_volume) * 10),
                        "direction": "bullish" if price_change > 0 else "bearish",
                        "volume_ratio": current_volume / avg_volume
                    })
        
    except Exception as e:
        logger.error(f"Breakout pattern detection error: {e}")
    
    return patterns

def detect_flag_pattern(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> Optional[Dict]:
    """Detect flag pattern"""
    
    if len(close) < 30:
        return None
    
    try:
        # Look for strong move (pole)
        pole_start = -30
        pole_end = -15
        
        pole_move = (close[pole_end] - close[pole_start]) / close[pole_start]
        
        if abs(pole_move) < 0.05:  # Need at least 5% move
            return None
        
        # Look for consolidation (flag)
        flag_highs = high[pole_end:]
        flag_lows = low[pole_end:]
        
        # Check if price is consolidating
        flag_range = np.max(flag_highs) - np.min(flag_lows)
        pole_range = abs(close[pole_end] - close[pole_start])
        
        if flag_range < pole_range * 0.5:  # Flag should be less than 50% of pole
            # Calculate trend of flag
            flag_prices = close[pole_end:]
            flag_slope = np.polyfit(range(len(flag_prices)), flag_prices, 1)[0]
            
            # Flag should be counter to pole direction
            if (pole_move > 0 and flag_slope < 0) or (pole_move < 0 and flag_slope > 0):
                confidence = 80 + min(15, abs(pole_move) * 100)
                
                return {
                    "type": PatternType.FLAG.value,
                    "confidence": confidence,
                    "direction": "bullish" if pole_move > 0 else "bearish",
                    "pole_strength": abs(pole_move),
                    "consolidation_periods": len(flag_prices)
                }
        
    except Exception as e:
        logger.debug(f"Flag pattern detection error: {e}")
    
    return None

def detect_triangle_pattern(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> Optional[Dict]:
    """Detect triangle patterns"""
    
    if len(close) < 20:
        return None
    
    try:
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(high) - 2):
            if high[i] > high[i-1] and high[i] > high[i-2] and high[i] > high[i+1] and high[i] > high[i+2]:
                swing_highs.append((i, high[i]))
            
            if low[i] < low[i-1] and low[i] < low[i-2] and low[i] < low[i+1] and low[i] < low[i+2]:
                swing_lows.append((i, low[i]))
        
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            # Check for converging trendlines
            high_indices = [h[0] for h in swing_highs[-3:]]
            high_values = [h[1] for h in swing_highs[-3:]]
            
            low_indices = [l[0] for l in swing_lows[-3:]]
            low_values = [l[1] for l in swing_lows[-3:]]
            
            if len(high_indices) >= 2 and len(low_indices) >= 2:
                # Calculate slopes
                high_slope = np.polyfit(high_indices, high_values, 1)[0]
                low_slope = np.polyfit(low_indices, low_values, 1)[0]
                
                # Ascending triangle: flat top, rising bottom
                if abs(high_slope) < 0.001 and low_slope > 0.001:
                    return {
                        "type": PatternType.ASCENDING_TRIANGLE.value,
                        "confidence": 75,
                        "direction": "bullish",
                        "resistance": np.mean(high_values),
                        "support_slope": low_slope
                    }
                
                # Descending triangle: falling top, flat bottom
                elif high_slope < -0.001 and abs(low_slope) < 0.001:
                    return {
                        "type": PatternType.DESCENDING_TRIANGLE.value,
                        "confidence": 75,
                        "direction": "bearish",
                        "support": np.mean(low_values),
                        "resistance_slope": high_slope
                    }
                
                # Symmetrical triangle: converging lines
                elif high_slope < -0.0005 and low_slope > 0.0005:
                    return {
                        "type": PatternType.TRIANGLE.value,
                        "confidence": 70,
                        "direction": "neutral",
                        "apex_distance": len(close) - max(high_indices[-1], low_indices[-1])
                    }
        
    except Exception as e:
        logger.debug(f"Triangle pattern detection error: {e}")
    
    return None

def detect_reversal_patterns(data: pd.DataFrame) -> List[Dict]:
    """Detect reversal patterns"""
    
    patterns = []
    
    try:
        close_prices = data['Close'].values
        high_prices = data['High'].values
        low_prices = data['Low'].values
        
        # Double top/bottom
        double_pattern = detect_double_top_bottom(close_prices, high_prices, low_prices)
        if double_pattern:
            patterns.append(double_pattern)
        
        # Head and shoulders
        hs_pattern = detect_head_shoulders(close_prices, high_prices, low_prices)
        if hs_pattern:
            patterns.append(hs_pattern)
        
    except Exception as e:
        logger.error(f"Reversal pattern detection error: {e}")
    
    return patterns

def detect_double_top_bottom(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> Optional[Dict]:
    """Detect double top or double bottom patterns"""
    
    if len(close) < 40:
        return None
    
    try:
        # Find peaks and troughs
        peaks = []
        troughs = []
        
        for i in range(5, len(high) - 5):
            # Peak: higher than 5 bars on each side
            if all(high[i] > high[j] for j in range(i-5, i)) and \
               all(high[i] > high[j] for j in range(i+1, i+6)):
                peaks.append((i, high[i]))
            
            # Trough: lower than 5 bars on each side
            if all(low[i] < low[j] for j in range(i-5, i)) and \
               all(low[i] < low[j] for j in range(i+1, i+6)):
                troughs.append((i, low[i]))
        
        # Check for double top
        if len(peaks) >= 2:
            last_two_peaks = peaks[-2:]
            peak1_price = last_two_peaks[0][1]
            peak2_price = last_two_peaks[1][1]
            
            # Peaks should be similar in height (within 2%)
            if abs(peak1_price - peak2_price) / peak1_price < 0.02:
                # Find trough between peaks
                peak1_idx = last_two_peaks[0][0]
                peak2_idx = last_two_peaks[1][0]
                
                if peak2_idx > peak1_idx:
                    between_low = np.min(low[peak1_idx:peak2_idx])
                    
                    # Trough should be at least 3% below peaks
                    if (peak1_price - between_low) / peak1_price > 0.03:
                        return {
                            "type": PatternType.DOUBLE_TOP.value,
                            "confidence": 80,
                            "direction": "bearish",
                            "resistance": (peak1_price + peak2_price) / 2,
                            "neckline": between_low
                        }
        
        # Check for double bottom
        if len(troughs) >= 2:
            last_two_troughs = troughs[-2:]
            trough1_price = last_two_troughs[0][1]
            trough2_price = last_two_troughs[1][1]
            
            # Troughs should be similar in depth (within 2%)
            if abs(trough1_price - trough2_price) / trough1_price < 0.02:
                # Find peak between troughs
                trough1_idx = last_two_troughs[0][0]
                trough2_idx = last_two_troughs[1][0]
                
                if trough2_idx > trough1_idx:
                    between_high = np.max(high[trough1_idx:trough2_idx])
                    
                    # Peak should be at least 3% above troughs
                    if (between_high - trough1_price) / trough1_price > 0.03:
                        return {
                            "type": PatternType.DOUBLE_BOTTOM.value,
                            "confidence": 80,
                            "direction": "bullish",
                            "support": (trough1_price + trough2_price) / 2,
                            "neckline": between_high
                        }
        
    except Exception as e:
        logger.debug(f"Double top/bottom detection error: {e}")
    
    return None

def detect_head_shoulders(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> Optional[Dict]:
    """Detect head and shoulders pattern"""
    
    if len(close) < 50:
        return None
    
    try:
        # Find peaks for head and shoulders top
        peaks = []
        for i in range(7, len(high) - 7):
            if all(high[i] > high[j] for j in range(i-7, i)) and \
               all(high[i] > high[j] for j in range(i+1, i+8)):
                peaks.append((i, high[i]))
        
        if len(peaks) >= 3:
            # Check last three peaks
            last_three = peaks[-3:]
            left_shoulder = last_three[0][1]
            head = last_three[1][1]
            right_shoulder = last_three[2][1]
            
            # Head should be highest
            if head > left_shoulder and head > right_shoulder:
                # Shoulders should be similar height (within 3%)
                if abs(left_shoulder - right_shoulder) / left_shoulder < 0.03:
                    # Head should be at least 5% higher than shoulders
                    if (head - left_shoulder) / left_shoulder > 0.05:
                        return {
                            "type": PatternType.HEAD_SHOULDERS.value,
                            "confidence": 85,
                            "direction": "bearish",
                            "neckline": min(low[last_three[0][0]:last_three[2][0]]),
                            "head_height": head,
                            "shoulder_height": (left_shoulder + right_shoulder) / 2
                        }
        
    except Exception as e:
        logger.debug(f"Head and shoulders detection error: {e}")
    
    return None

def detect_volume_patterns(data: pd.DataFrame) -> List[Dict]:
    """Detect volume-based patterns"""
    
    patterns = []
    
    try:
        volumes = data['Volume'].values
        close_prices = data['Close'].values
        
        if len(volumes) < 20:
            return patterns
        
        # Calculate volume moving averages
        vol_ma_20 = np.mean(volumes[-20:])
        vol_ma_5 = np.mean(volumes[-5:])
        
        # Accumulation: rising price with rising volume
        if vol_ma_5 > vol_ma_20 * 1.3:
            price_trend = np.polyfit(range(20), close_prices[-20:], 1)[0]
            
            if price_trend > 0:
                patterns.append({
                    "type": PatternType.ACCUMULATION.value,
                    "confidence": 70 + min(20, (vol_ma_5 / vol_ma_20 - 1) * 30),
                    "direction": "bullish",
                    "volume_increase": vol_ma_5 / vol_ma_20
                })
        
        # Distribution: falling price with rising volume
        elif vol_ma_5 > vol_ma_20 * 1.3:
            price_trend = np.polyfit(range(20), close_prices[-20:], 1)[0]
            
            if price_trend < 0:
                patterns.append({
                    "type": PatternType.DISTRIBUTION.value,
                    "confidence": 70 + min(20, (vol_ma_5 / vol_ma_20 - 1) * 30),
                    "direction": "bearish",
                    "volume_increase": vol_ma_5 / vol_ma_20
                })
        
    except Exception as e:
        logger.error(f"Volume pattern detection error: {e}")
    
    return patterns

def detect_momentum_patterns(data: pd.DataFrame) -> List[Dict]:
    """Detect momentum-based patterns"""
    
    patterns = []
    
    try:
        close_prices = data['Close'].values
        high_prices = data['High'].values
        low_prices = data['Low'].values
        
        if len(close_prices) < 20:
            return patterns
        
        # Calculate Bollinger Bands
        sma_20 = np.mean(close_prices[-20:])
        std_20 = np.std(close_prices[-20:])
        
        upper_band = sma_20 + (2 * std_20)
        lower_band = sma_20 - (2 * std_20)
        
        current_price = close_prices[-1]
        band_width = (upper_band - lower_band) / sma_20
        
        # Squeeze: low volatility, potential breakout
        if band_width < 0.05:  # Bands are tight
            patterns.append({
                "type": PatternType.SQUEEZE.value,
                "confidence": 75,
                "direction": "neutral",
                "band_width": band_width,
                "potential_breakout": True
            })
        
        # Expansion: high volatility after squeeze
        elif band_width > 0.15:  # Bands are wide
            # Check if expansion just started
            prev_ranges = [high_prices[i] - low_prices[i] for i in range(-10, -1)]
            current_range = high_prices[-1] - low_prices[-1]
            
            if current_range > np.mean(prev_ranges) * 2:
                patterns.append({
                    "type": PatternType.EXPANSION.value,
                    "confidence": 80,
                    "direction": "bullish" if close_prices[-1] > close_prices[-2] else "bearish",
                    "volatility_increase": current_range / np.mean(prev_ranges)
                })
        
        # RSI Divergence
        rsi = calculate_rsi(close_prices)
        if rsi is not None:
            # Bullish divergence: price making lower lows, RSI making higher lows
            if len(close_prices) > 30:
                price_lows = []
                rsi_lows = []
                
                for i in range(10, 30):
                    if close_prices[-i] < close_prices[-i-1] and close_prices[-i] < close_prices[-i+1]:
                        price_lows.append((i, close_prices[-i]))
                        rsi_lows.append((i, rsi[-i]))
                
                if len(price_lows) >= 2:
                    if price_lows[-1][1] < price_lows[-2][1] and rsi_lows[-1][1] > rsi_lows[-2][1]:
                        patterns.append({
                            "type": PatternType.DIVERGENCE.value,
                            "confidence": 70,
                            "direction": "bullish",
                            "divergence_type": "bullish",
                            "rsi": rsi[-1]
                        })
        
    except Exception as e:
        logger.error(f"Momentum pattern detection error: {e}")
    
    return patterns

# === HELPER FUNCTIONS ===

async def get_market_data(symbol: str, timeframe: str, lookback: int) -> Optional[pd.DataFrame]:
    """Get market data for analysis"""
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Convert timeframe to period
        period_map = {
            "1m": "1d",
            "5m": "5d",
            "15m": "5d",
            "30m": "1mo",
            "1h": "1mo",
            "1d": "6mo"
        }
        
        period = period_map.get(timeframe, "5d")
        
        # Get historical data
        data = ticker.history(period=period, interval=timeframe)
        
        if not data.empty and len(data) >= lookback:
            return data.tail(lookback)
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to get market data for {symbol}: {e}")
        return None

def calculate_rsi(prices: np.ndarray, period: int = 14) -> Optional[np.ndarray]:
    """Calculate RSI indicator"""
    
    if len(prices) < period + 1:
        return None
    
    try:
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        if down == 0:
            return None
        
        rs = up / down
        rsi = np.zeros_like(prices)
        rsi[:period] = np.nan
        rsi[period] = 100 - (100 / (1 + rs))
        
        for i in range(period + 1, len(prices)):
            delta = deltas[i - 1]
            
            if delta > 0:
                up_val = delta
                down_val = 0
            else:
                up_val = 0
                down_val = -delta
            
            up = (up * (period - 1) + up_val) / period
            down = (down * (period - 1) + down_val) / period
            
            if down == 0:
                rsi[i] = 100
            else:
                rs = up / down
                rsi[i] = 100 - (100 / (1 + rs))
        
        return rsi
        
    except Exception as e:
        logger.error(f"RSI calculation error: {e}")
        return None

async def get_cached_pattern(key: str) -> Optional[Dict]:
    """Get cached pattern data"""
    
    if state.redis_client:
        try:
            data = await state.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
    
    return None

async def cache_pattern(key: str, data: Dict, ttl: int = 300):
    """Cache pattern data"""
    
    if state.redis_client:
        try:
            await state.redis_client.setex(
                key,
                ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.debug(f"Cache set error: {e}")

async def store_pattern_detection(symbol: str, pattern_data: Dict):
    """Store pattern detection in database"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pattern_detections (
                    symbol, pattern_type, confidence,
                    pattern_data, created_at
                ) VALUES ($1, $2, $3, $4, $5)
            """,
                symbol,
                pattern_data.get("primary_pattern"),
                pattern_data.get("confidence", 0),
                json.dumps(pattern_data, default=str),
                datetime.now()
            )
    except Exception as e:
        logger.error(f"Failed to store pattern detection: {e}")

async def load_pattern_success_rates():
    """Load historical pattern success rates"""
    
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT pattern_type, 
                       AVG(CASE WHEN profitable THEN 1 ELSE 0 END) * 100 as success_rate,
                       COUNT(*) as total_trades
                FROM pattern_trades
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY pattern_type
            """)
            
            for row in rows:
                state.pattern_success_rates[row['pattern_type']] = {
                    "success_rate": float(row['success_rate']),
                    "total_trades": row['total_trades']
                }
                
            logger.info(f"Loaded success rates for {len(state.pattern_success_rates)} patterns")
            
    except Exception as e:
        logger.error(f"Failed to load pattern success rates: {e}")

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎩 Catalyst Trading System - Pattern Service v4.1")
    print("=" * 60)
    print("Status: Starting...")
    print("Port: 5002")
    print("Protocol: REST API")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5002,
        log_level="info"
    )
