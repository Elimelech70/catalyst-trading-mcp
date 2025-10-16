#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 5.3.0
Last Updated: 2025-10-16
Purpose: Technical analysis service using pandas-ta for accurate indicators

REVISION HISTORY:
v5.3.0 (2025-10-16) - Switched to pandas-ta for accuracy
- Replaced custom indicators with pandas-ta
- Added 20+ additional indicators
- Improved accuracy to match TradingView/industry standards
- Enhanced signal generation with more indicators
- Added indicator caching for performance

v5.2.0 (2025-10-16) - Critical production fixes
- Added missing CORSMiddleware import
- Fixed SERVICE_NAME constant definition

v5.0.0 (2025-10-11) - Normalized schema implementation
- Uses security_id FK (NOT symbol VARCHAR)
- All queries use JOINs on FKs

Description of Service:
Technical analysis service that calculates indicators using pandas-ta library
for industry-standard accuracy. Provides RSI, MACD, Bollinger Bands, ATR,
Stochastic, OBV, VWAP and 20+ other indicators with proper calculations
matching TradingView and professional platforms.
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from decimal import Decimal

import asyncpg
import numpy as np
import pandas as pd
import pandas_ta as ta  # Industry-standard technical analysis
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import aiohttp
import redis.asyncio as redis
import yfinance as yf

# ============================================================================
# SERVICE CONFIGURATION
# ============================================================================

SERVICE_NAME = "Technical Analysis Service"
SERVICE_VERSION = "5.3.0"
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
# CONFIGURATION CONSTANTS
# ============================================================================

class Config:
    """Technical analysis configuration"""
    # Indicator periods
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    
    BB_PERIOD = 20
    BB_STD = 2.0
    
    ATR_PERIOD = 14
    STOCH_PERIOD = 14
    
    # Signal thresholds
    STRONG_BUY_SCORE = 80
    BUY_SCORE = 60
    SELL_SCORE = 40
    STRONG_SELL_SCORE = 20
    
    # Cache settings
    CACHE_TTL = 60  # seconds

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TechnicalRequest(BaseModel):
    """Request for technical analysis"""
    symbol: str
    timeframe: str = Field(default="5m", description="1m, 5m, 15m, 1h, 1d")
    period: int = Field(default=100, ge=50, le=500)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        return v.upper().strip()

class IndicatorValues(BaseModel):
    """Complete set of technical indicators"""
    # Price & Volume
    close: float
    volume: int
    
    # Trend Indicators
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    
    # MACD
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # Momentum
    rsi: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    williams_r: Optional[float] = None
    cci: Optional[float] = None
    
    # Volatility
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    bb_percent: Optional[float] = None
    atr: Optional[float] = None
    
    # Volume Indicators
    obv: Optional[float] = None
    vwap: Optional[float] = None
    volume_sma: Optional[float] = None
    
    # Advanced
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None

class TechnicalSignals(BaseModel):
    """Trading signals based on indicators"""
    trend_signal: str  # BULLISH, BEARISH, NEUTRAL
    momentum_signal: str
    volume_signal: str
    overall_signal: str  # BUY, SELL, HOLD
    signal_strength: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reasons: List[str] = []

class TechnicalResponse(BaseModel):
    """Complete technical analysis response"""
    symbol: str
    security_id: int
    timestamp: datetime
    timeframe: str
    indicators: IndicatorValues
    signals: TechnicalSignals
    support_levels: List[float] = []
    resistance_levels: List[float] = []
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

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
    """Manage application lifecycle"""
    global db_pool, redis_client, http_session
    
    try:
        # Initialize database pool
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=10
        )
        logger.info("Database pool created successfully")
        
        # Initialize Redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected successfully")
        
        # Initialize HTTP session
        http_session = aiohttp.ClientSession()
        logger.info("HTTP session created")
        
        logger.info(f"{SERVICE_NAME} v{SERVICE_VERSION} started on port {SERVICE_PORT}")
        
        yield
        
    finally:
        # Cleanup
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")
        
        if redis_client:
            await redis_client.close()
            logger.info("Redis connection closed")
            
        if http_session:
            await http_session.close()
            logger.info("HTTP session closed")
        
        logger.info(f"{SERVICE_NAME} shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================================
# INDICATOR CALCULATIONS WITH PANDAS-TA
# ============================================================================

def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate all technical indicators using pandas-ta
    Returns dict with all indicator values
    """
    indicators = {}
    
    try:
        # Ensure we have OHLCV columns with correct names
        df.columns = [col.lower() for col in df.columns]
        
        # Add all indicators to dataframe
        # This is more efficient than calculating individually
        
        # Trend Indicators
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.ema(length=12, append=True)
        df.ta.ema(length=26, append=True)
        
        # MACD
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        
        # RSI
        df.ta.rsi(length=Config.RSI_PERIOD, append=True)
        
        # Stochastic
        df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        
        # Williams %R
        df.ta.willr(length=14, append=True)
        
        # CCI
        df.ta.cci(length=20, append=True)
        
        # Bollinger Bands
        df.ta.bbands(length=Config.BB_PERIOD, std=Config.BB_STD, append=True)
        
        # ATR
        df.ta.atr(length=Config.ATR_PERIOD, append=True)
        
        # Volume Indicators
        df.ta.obv(append=True)
        df.ta.vwap(append=True)
        
        # ADX
        df.ta.adx(length=14, append=True)
        
        # Get the last row with all indicators
        last_row = df.iloc[-1]
        
        # Extract values (handle NaN gracefully)
        indicators['close'] = float(last_row['close'])
        indicators['volume'] = int(last_row['volume'])
        
        # Moving Averages
        indicators['sma_20'] = _safe_float(last_row.get('SMA_20'))
        indicators['sma_50'] = _safe_float(last_row.get('SMA_50'))
        indicators['sma_200'] = _safe_float(last_row.get('SMA_200'))
        indicators['ema_12'] = _safe_float(last_row.get('EMA_12'))
        indicators['ema_26'] = _safe_float(last_row.get('EMA_26'))
        
        # MACD
        indicators['macd'] = _safe_float(last_row.get('MACD_12_26_9'))
        indicators['macd_signal'] = _safe_float(last_row.get('MACDs_12_26_9'))
        indicators['macd_histogram'] = _safe_float(last_row.get('MACDh_12_26_9'))
        
        # RSI
        indicators['rsi'] = _safe_float(last_row.get(f'RSI_{Config.RSI_PERIOD}'))
        
        # Stochastic
        indicators['stoch_k'] = _safe_float(last_row.get('STOCHk_14_3_3'))
        indicators['stoch_d'] = _safe_float(last_row.get('STOCHd_14_3_3'))
        
        # Williams %R
        indicators['williams_r'] = _safe_float(last_row.get('WILLR_14'))
        
        # CCI
        indicators['cci'] = _safe_float(last_row.get('CCI_20_0.015'))
        
        # Bollinger Bands
        indicators['bb_lower'] = _safe_float(last_row.get(f'BBL_{Config.BB_PERIOD}_{Config.BB_STD}'))
        indicators['bb_middle'] = _safe_float(last_row.get(f'BBM_{Config.BB_PERIOD}_{Config.BB_STD}'))
        indicators['bb_upper'] = _safe_float(last_row.get(f'BBU_{Config.BB_PERIOD}_{Config.BB_STD}'))
        indicators['bb_width'] = _safe_float(last_row.get(f'BBB_{Config.BB_PERIOD}_{Config.BB_STD}'))
        indicators['bb_percent'] = _safe_float(last_row.get(f'BBP_{Config.BB_PERIOD}_{Config.BB_STD}'))
        
        # ATR
        indicators['atr'] = _safe_float(last_row.get(f'ATRr_{Config.ATR_PERIOD}'))
        
        # Volume
        indicators['obv'] = _safe_float(last_row.get('OBV'))
        indicators['vwap'] = _safe_float(last_row.get('VWAP_D'))
        
        # Calculate volume SMA manually if needed
        if 'volume' in df.columns:
            indicators['volume_sma'] = float(df['volume'].rolling(20).mean().iloc[-1])
        
        # ADX
        indicators['adx'] = _safe_float(last_row.get('ADX_14'))
        indicators['plus_di'] = _safe_float(last_row.get('DMP_14'))
        indicators['minus_di'] = _safe_float(last_row.get('DMN_14'))
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        raise
    
    return indicators

def _safe_float(value) -> Optional[float]:
    """Safely convert to float, handling NaN and None"""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except:
        return None

def calculate_support_resistance(df: pd.DataFrame, num_levels: int = 3) -> Tuple[List[float], List[float]]:
    """Calculate support and resistance levels using pandas-ta"""
    support_levels = []
    resistance_levels = []
    
    try:
        # Use pandas-ta pivot points
        df.ta.pivot_points(anchor='D', append=True)
        
        last_row = df.iloc[-1]
        
        # Extract pivot point levels
        if 'PP_D' in last_row:
            pivot = _safe_float(last_row.get('PP_D'))
            
            # Resistance levels
            r1 = _safe_float(last_row.get('R1_D'))
            r2 = _safe_float(last_row.get('R2_D'))
            r3 = _safe_float(last_row.get('R3_D'))
            
            # Support levels
            s1 = _safe_float(last_row.get('S1_D'))
            s2 = _safe_float(last_row.get('S2_D'))
            s3 = _safe_float(last_row.get('S3_D'))
            
            resistance_levels = [r for r in [r1, r2, r3] if r is not None]
            support_levels = [s for s in [s1, s2, s3] if s is not None]
        
        # Alternative: Find local highs/lows if pivot points not available
        if not resistance_levels or not support_levels:
            high = df['high'].rolling(window=20).max()
            low = df['low'].rolling(window=20).min()
            
            # Recent highs as resistance
            recent_highs = df['high'].nlargest(num_levels).tolist()
            resistance_levels = sorted(recent_highs, reverse=True)[:num_levels]
            
            # Recent lows as support
            recent_lows = df['low'].nsmallest(num_levels).tolist()
            support_levels = sorted(recent_lows)[:num_levels]
    
    except Exception as e:
        logger.warning(f"Error calculating support/resistance: {e}")
    
    return support_levels, resistance_levels

def generate_signals(indicators: Dict[str, Any], df: pd.DataFrame) -> TechnicalSignals:
    """Generate trading signals from indicators with detailed reasoning"""
    
    signals = TechnicalSignals(
        trend_signal="NEUTRAL",
        momentum_signal="NEUTRAL",
        volume_signal="NEUTRAL",
        overall_signal="HOLD",
        signal_strength=0.5,
        confidence=0.5,
        reasons=[]
    )
    
    try:
        score = 50  # Start neutral
        confidence_factors = []
        reasons = []
        
        current_price = indicators['close']
        
        # ========== TREND ANALYSIS ==========
        trend_score = 0
        trend_count = 0
        
        # Moving Average Analysis
        if indicators.get('sma_20') and indicators.get('sma_50'):
            if current_price > indicators['sma_20'] > indicators['sma_50']:
                trend_score += 30
                reasons.append("Price above SMA20 > SMA50 (Bullish trend)")
            elif current_price < indicators['sma_20'] < indicators['sma_50']:
                trend_score -= 30
                reasons.append("Price below SMA20 < SMA50 (Bearish trend)")
            trend_count += 1
        
        # MACD Analysis
        if indicators.get('macd') and indicators.get('macd_signal'):
            if indicators['macd'] > indicators['macd_signal'] and indicators['macd'] > 0:
                trend_score += 20
                reasons.append("MACD above signal and positive")
            elif indicators['macd'] < indicators['macd_signal'] and indicators['macd'] < 0:
                trend_score -= 20
                reasons.append("MACD below signal and negative")
            trend_count += 1
            confidence_factors.append(abs(indicators['macd']))
        
        # ADX Trend Strength
        if indicators.get('adx'):
            if indicators['adx'] > 25:
                confidence_factors.append(indicators['adx'] / 100)
                if indicators.get('plus_di') and indicators.get('minus_di'):
                    if indicators['plus_di'] > indicators['minus_di']:
                        trend_score += 10
                        reasons.append(f"Strong trend: ADX={indicators['adx']:.1f}, +DI > -DI")
                    else:
                        trend_score -= 10
                        reasons.append(f"Strong trend: ADX={indicators['adx']:.1f}, -DI > +DI")
            trend_count += 1
        
        # Set trend signal
        avg_trend = trend_score / max(trend_count, 1)
        if avg_trend > 15:
            signals.trend_signal = "BULLISH"
        elif avg_trend < -15:
            signals.trend_signal = "BEARISH"
        
        score += trend_score
        
        # ========== MOMENTUM ANALYSIS ==========
        momentum_score = 0
        momentum_count = 0
        
        # RSI Analysis
        if indicators.get('rsi'):
            rsi = indicators['rsi']
            if rsi < Config.RSI_OVERSOLD:
                momentum_score += 25
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > Config.RSI_OVERBOUGHT:
                momentum_score -= 25
                reasons.append(f"RSI overbought ({rsi:.1f})")
            elif 45 <= rsi <= 55:
                reasons.append(f"RSI neutral ({rsi:.1f})")
            momentum_count += 1
            # RSI confidence higher at extremes
            confidence_factors.append(abs(50 - rsi) / 50)
        
        # Stochastic Analysis
        if indicators.get('stoch_k') and indicators.get('stoch_d'):
            if indicators['stoch_k'] < 20 and indicators['stoch_k'] > indicators['stoch_d']:
                momentum_score += 15
                reasons.append("Stochastic oversold with bullish crossover")
            elif indicators['stoch_k'] > 80 and indicators['stoch_k'] < indicators['stoch_d']:
                momentum_score -= 15
                reasons.append("Stochastic overbought with bearish crossover")
            momentum_count += 1
        
        # CCI Analysis
        if indicators.get('cci'):
            if indicators['cci'] < -100:
                momentum_score += 10
                reasons.append("CCI oversold")
            elif indicators['cci'] > 100:
                momentum_score -= 10
                reasons.append("CCI overbought")
            momentum_count += 1
        
        # Williams %R
        if indicators.get('williams_r'):
            if indicators['williams_r'] < -80:
                momentum_score += 10
                reasons.append("Williams %R oversold")
            elif indicators['williams_r'] > -20:
                momentum_score -= 10
                reasons.append("Williams %R overbought")
            momentum_count += 1
        
        # Set momentum signal
        avg_momentum = momentum_score / max(momentum_count, 1)
        if avg_momentum > 10:
            signals.momentum_signal = "OVERSOLD"
        elif avg_momentum < -10:
            signals.momentum_signal = "OVERBOUGHT"
        else:
            signals.momentum_signal = "NEUTRAL"
        
        score += momentum_score
        
        # ========== VOLATILITY ANALYSIS ==========
        
        # Bollinger Bands
        if indicators.get('bb_percent') is not None:
            bb_pct = indicators['bb_percent']
            if bb_pct < 0:
                score += 10
                reasons.append(f"Price below BB lower band ({bb_pct:.1%})")
            elif bb_pct > 1:
                score -= 10
                reasons.append(f"Price above BB upper band ({bb_pct:.1%})")
            
            # BB squeeze detection
            if indicators.get('bb_width') and indicators.get('atr'):
                bb_squeeze = indicators['bb_width'] / indicators['atr']
                if bb_squeeze < 1.5:
                    reasons.append("Bollinger Band squeeze detected (volatility expansion coming)")
                    confidence_factors.append(0.3)  # Lower confidence during squeeze
        
        # ========== VOLUME ANALYSIS ==========
        volume_score = 0
        
        if indicators.get('obv'):
            # Calculate OBV trend (would need historical OBV)
            reasons.append(f"OBV: {indicators['obv']:,.0f}")
        
        if indicators.get('volume_sma') and indicators.get('volume'):
            volume_ratio = indicators['volume'] / indicators['volume_sma']
            if volume_ratio > 1.5:
                reasons.append(f"High volume ({volume_ratio:.1f}x average)")
                confidence_factors.append(min(volume_ratio / 3, 1.0))
            elif volume_ratio < 0.5:
                reasons.append(f"Low volume ({volume_ratio:.1f}x average)")
                confidence_factors.append(0.5)
        
        # VWAP Analysis
        if indicators.get('vwap'):
            if current_price > indicators['vwap']:
                volume_score += 5
                reasons.append("Price above VWAP")
            else:
                volume_score -= 5
                reasons.append("Price below VWAP")
        
        signals.volume_signal = "HIGH" if volume_score > 5 else "LOW" if volume_score < -5 else "NORMAL"
        score += volume_score
        
        # ========== FINAL SIGNAL GENERATION ==========
        
        # Normalize score to 0-100
        score = max(0, min(100, score))
        
        # Determine overall signal
        if score >= Config.STRONG_BUY_SCORE:
            signals.overall_signal = "STRONG_BUY"
        elif score >= Config.BUY_SCORE:
            signals.overall_signal = "BUY"
        elif score <= Config.STRONG_SELL_SCORE:
            signals.overall_signal = "STRONG_SELL"
        elif score <= Config.SELL_SCORE:
            signals.overall_signal = "SELL"
        else:
            signals.overall_signal = "HOLD"
        
        # Calculate confidence
        if confidence_factors:
            signals.confidence = min(sum(confidence_factors) / len(confidence_factors), 1.0)
        else:
            signals.confidence = 0.5
        
        # Signal strength
        signals.signal_strength = score / 100
        
        # Add reasons
        signals.reasons = reasons[:10]  # Limit to top 10 reasons
        
    except Exception as e:
        logger.error(f"Error generating signals: {e}")
    
    return signals

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

async def get_time_id() -> int:
    """Get or create time_id for current timestamp"""
    now = datetime.now()
    async with db_pool.acquire() as conn:
        result = await conn.fetchval(
            """
            INSERT INTO time_dimension (timestamp, year, quarter, month, week, day_of_week, hour, minute)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (timestamp) DO UPDATE SET timestamp = EXCLUDED.timestamp
            RETURNING time_id
            """,
            now, now.year, (now.month-1)//3 + 1, now.month,
            now.isocalendar()[1], now.weekday(), now.hour, now.minute
        )
        return result

async def fetch_price_history(
    security_id: int, 
    timeframe: str, 
    limit: int = 200
) -> pd.DataFrame:
    """Fetch price history from database"""
    
    async with db_pool.acquire() as conn:
        # Determine interval based on timeframe
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes",
            "15m": "15 minutes",
            "1h": "1 hour",
            "1d": "1 day"
        }
        interval = interval_map.get(timeframe, "5 minutes")
        
        rows = await conn.fetch(
            f"""
            SELECT 
                td.timestamp,
                th.open_price as open,
                th.high_price as high,
                th.low_price as low,
                th.close_price as close,
                th.volume
            FROM trading_history th
            JOIN time_dimension td ON td.time_id = th.time_id
            WHERE th.security_id = $1
                AND td.timestamp >= NOW() - INTERVAL '{limit} {interval}'
            ORDER BY td.timestamp ASC
            """,
            security_id
        )
        
        if not rows:
            # Fallback to yfinance if no data
            return await fetch_from_yfinance(security_id, timeframe, limit)
        
        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df.set_index('timestamp', inplace=True)
        return df

async def fetch_from_yfinance(security_id: int, timeframe: str, limit: int) -> pd.DataFrame:
    """Fallback to fetch data from yfinance"""
    
    # Get symbol from security_id
    async with db_pool.acquire() as conn:
        symbol = await conn.fetchval(
            "SELECT symbol FROM security_dimension WHERE security_id = $1",
            security_id
        )
    
    if not symbol:
        raise ValueError(f"Security {security_id} not found")
    
    # Map timeframe to yfinance period/interval
    period_map = {
        "1m": "1d",
        "5m": "5d",
        "15m": "5d",
        "1h": "1mo",
        "1d": "3mo"
    }
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period_map.get(timeframe, "1mo"), interval=timeframe)
    
    if df.empty:
        raise ValueError(f"No data available for {symbol}")
    
    # Standardize column names
    df.columns = [col.lower() for col in df.columns]
    
    return df

async def store_indicators(security_id: int, timeframe: str, indicators: Dict):
    """Store calculated indicators in database"""
    
    time_id = await get_time_id()
    
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO technical_indicators (
                security_id, time_id, timeframe,
                rsi_14, macd, macd_signal, macd_histogram,
                bollinger_upper, bollinger_middle, bollinger_lower,
                sma_20, sma_50, sma_200,
                ema_12, ema_26,
                atr_14, obv, vwap,
                stochastic_k, stochastic_d,
                williams_r, cci,
                calculated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                     $11, $12, $13, $14, $15, $16, $17, $18, $19, 
                     $20, $21, $22, NOW())
            ON CONFLICT (security_id, time_id, timeframe) 
            DO UPDATE SET
                rsi_14 = EXCLUDED.rsi_14,
                macd = EXCLUDED.macd,
                macd_signal = EXCLUDED.macd_signal,
                macd_histogram = EXCLUDED.macd_histogram,
                bollinger_upper = EXCLUDED.bollinger_upper,
                bollinger_middle = EXCLUDED.bollinger_middle,
                bollinger_lower = EXCLUDED.bollinger_lower,
                sma_20 = EXCLUDED.sma_20,
                sma_50 = EXCLUDED.sma_50,
                sma_200 = EXCLUDED.sma_200,
                ema_12 = EXCLUDED.ema_12,
                ema_26 = EXCLUDED.ema_26,
                atr_14 = EXCLUDED.atr_14,
                obv = EXCLUDED.obv,
                vwap = EXCLUDED.vwap,
                stochastic_k = EXCLUDED.stochastic_k,
                stochastic_d = EXCLUDED.stochastic_d,
                williams_r = EXCLUDED.williams_r,
                cci = EXCLUDED.cci,
                calculated_at = NOW()
            """,
            security_id, time_id, timeframe,
            indicators.get('rsi'),
            indicators.get('macd'),
            indicators.get('macd_signal'),
            indicators.get('macd_histogram'),
            indicators.get('bb_upper'),
            indicators.get('bb_middle'),
            indicators.get('bb_lower'),
            indicators.get('sma_20'),
            indicators.get('sma_50'),
            indicators.get('sma_200'),
            indicators.get('ema_12'),
            indicators.get('ema_26'),
            indicators.get('atr'),
            indicators.get('obv'),
            indicators.get('vwap'),
            indicators.get('stoch_k'),
            indicators.get('stoch_d'),
            indicators.get('williams_r'),
            indicators.get('cci')
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
    except:
        pass
    
    try:
        if redis_client:
            await redis_client.ping()
            redis_status = "healthy"
    except:
        pass
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        timestamp=datetime.now(),
        database=db_status,
        redis=redis_status
    )

@app.post("/api/v1/indicators/calculate", response_model=TechnicalResponse)
async def calculate_indicators(request: TechnicalRequest):
    """Calculate technical indicators for a symbol"""
    
    try:
        # Check cache first
        cache_key = f"indicators:{request.symbol}:{request.timeframe}"
        if redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                return TechnicalResponse(**json.loads(cached))
        
        # Get security_id
        security_id = await get_security_id(request.symbol)
        
        # Fetch price history
        df = await fetch_price_history(security_id, request.timeframe, request.period)
        
        if len(df) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for {request.symbol} (need at least 50 periods)"
            )
        
        # Calculate all indicators
        indicators_dict = calculate_all_indicators(df)
        
        # Calculate support/resistance
        support, resistance = calculate_support_resistance(df)
        
        # Generate signals
        signals = generate_signals(indicators_dict, df)
        
        # Create indicator values model
        indicator_values = IndicatorValues(**indicators_dict)
        
        # Calculate entry, stop loss, take profit
        current_price = indicators_dict['close']
        atr = indicators_dict.get('atr', current_price * 0.02)
        
        entry_price = current_price
        if signals.overall_signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)
        elif signals.overall_signal in ["SELL", "STRONG_SELL"]:
            stop_loss = current_price + (2 * atr)
            take_profit = current_price - (3 * atr)
        else:
            stop_loss = None
            take_profit = None
        
        # Store indicators in database
        await store_indicators(security_id, request.timeframe, indicators_dict)
        
        # Create response
        response = TechnicalResponse(
            symbol=request.symbol,
            security_id=security_id,
            timestamp=datetime.now(),
            timeframe=request.timeframe,
            indicators=indicator_values,
            signals=signals,
            support_levels=support,
            resistance_levels=resistance,
            entry_price=entry_price if stop_loss else None,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Cache the result
        if redis_client:
            await redis_client.setex(
                cache_key,
                Config.CACHE_TTL,
                response.model_dump_json()
            )
        
        logger.info(f"Calculated indicators for {request.symbol}: {signals.overall_signal}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating indicators for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/indicators/{symbol}/latest", response_model=TechnicalResponse)
async def get_latest_indicators(symbol: str, timeframe: str = "5m"):
    """Get latest indicators for a symbol"""
    
    request = TechnicalRequest(symbol=symbol, timeframe=timeframe)
    return await calculate_indicators(request)

@app.post("/api/v1/indicators/batch")
async def calculate_batch(symbols: List[str], timeframe: str = "5m"):
    """Calculate indicators for multiple symbols"""
    
    results = []
    for symbol in symbols[:20]:  # Limit to 20 symbols
        try:
            request = TechnicalRequest(symbol=symbol, timeframe=timeframe)
            result = await calculate_indicators(request)
            results.append(result.model_dump())
        except Exception as e:
            logger.warning(f"Failed to calculate indicators for {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "error": str(e)
            })
    
    return {"results": results}

@app.get("/api/v1/support-resistance/{symbol}")
async def get_support_resistance(symbol: str, timeframe: str = "1d"):
    """Get support and resistance levels"""
    
    try:
        security_id = await get_security_id(symbol)
        df = await fetch_price_history(security_id, timeframe, 100)
        
        support, resistance = calculate_support_resistance(df, num_levels=5)
        
        return {
            "symbol": symbol,
            "support_levels": support,
            "resistance_levels": resistance,
            "current_price": float(df['close'].iloc[-1]),
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error getting support/resistance for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/signals/screen")
async def screen_signals(
    min_volume: int = 1000000,
    signal_types: List[str] = ["BUY", "STRONG_BUY"],
    min_confidence: float = 0.6
):
    """Screen for stocks matching signal criteria"""
    
    try:
        # Get active securities
        async with db_pool.acquire() as conn:
            securities = await conn.fetch(
                """
                SELECT symbol FROM security_dimension 
                WHERE is_active = true 
                AND exchange IN ('NYSE', 'NASDAQ')
                LIMIT 100
                """
            )
        
        matches = []
        for row in securities:
            try:
                request = TechnicalRequest(symbol=row['symbol'])
                result = await calculate_indicators(request)
                
                if (result.signals.overall_signal in signal_types and
                    result.signals.confidence >= min_confidence and
                    result.indicators.volume >= min_volume):
                    
                    matches.append({
                        "symbol": row['symbol'],
                        "signal": result.signals.overall_signal,
                        "confidence": result.signals.confidence,
                        "strength": result.signals.signal_strength,
                        "price": result.indicators.close,
                        "volume": result.indicators.volume,
                        "reasons": result.signals.reasons[:3]
                    })
            except:
                continue
        
        # Sort by confidence
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            "timestamp": datetime.now(),
            "criteria": {
                "min_volume": min_volume,
                "signals": signal_types,
                "min_confidence": min_confidence
            },
            "matches": matches[:20],  # Top 20
            "total_screened": len(securities)
        }
        
    except Exception as e:
        logger.error(f"Error in signal screening: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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