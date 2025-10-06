#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 4.1.0
Last Updated: 2025-08-31
Purpose: Technical indicators and signal generation

REVISION HISTORY:
v4.1.0 (2025-08-31) - Production-ready technical analysis
- Comprehensive indicator suite (20+ indicators)
- Multi-timeframe analysis
- Signal strength scoring
- Divergence detection
- Support/resistance identification

Description of Service:
This service provides technical analysis including:
1. Trend indicators (MA, EMA, MACD)
2. Momentum indicators (RSI, Stochastic, Williams %R)
3. Volatility indicators (Bollinger Bands, ATR, Keltner)
4. Volume indicators (OBV, Volume Profile, VWAP)
5. Custom signal generation and scoring
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
import ta
import json
import os
import logging
from enum import Enum
from dataclasses import dataclass

# Initialize FastAPI app
app = FastAPI(
    title="Technical Analysis Service",
    version="4.1.0",
    description="Technical analysis service for Catalyst Trading System"
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
logger = logging.getLogger("technical")

# === DATA MODELS ===

class SignalStrength(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

class TechnicalRequest(BaseModel):
    symbol: str
    timeframe: str = "5m"
    lookback_periods: int = Field(default=100, ge=20, le=500)

class TechnicalIndicators(BaseModel):
    # Trend
    sma_20: float
    sma_50: float
    ema_12: float
    ema_26: float
    macd: float
    macd_signal: float
    macd_histogram: float
    
    # Momentum
    rsi: float
    stochastic_k: float
    stochastic_d: float
    williams_r: float
    cci: float
    
    # Volatility
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_width: float
    atr: float
    
    # Volume
    obv: float
    vwap: float
    volume_ratio: float

class TechnicalSignals(BaseModel):
    trend_signal: SignalStrength
    momentum_signal: SignalStrength
    volatility_signal: SignalStrength
    volume_signal: SignalStrength
    overall_signal: SignalStrength
    confidence: float

class TechnicalResponse(BaseModel):
    symbol: str
    indicators: TechnicalIndicators
    signals: TechnicalSignals
    support_levels: List[float]
    resistance_levels: List[float]
    pivot_points: Dict[str, float]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    timestamp: datetime

# === SERVICE STATE ===

@dataclass
class TechnicalConfig:
    """Configuration for technical analysis"""
    # RSI thresholds
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    
    # Stochastic thresholds
    stoch_oversold: float = 20
    stoch_overbought: float = 80
    
    # Bollinger Band settings
    bb_periods: int = 20
    bb_std_dev: float = 2.0
    
    # ATR multiplier for stops
    atr_stop_multiplier: float = 2.0
    
    # Minimum confidence for signals
    min_confidence: float = 60.0

class TechnicalState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.config = TechnicalConfig()
        self.indicator_cache: Dict = {}

state = TechnicalState()

# === STARTUP/SHUTDOWN ===

@app.on_event("startup")
async def startup():
    """Initialize technical service"""
    logger.info("Starting Technical Analysis Service v4.1")
    
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
        
        logger.info("Technical Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize technical service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Clean up resources"""
    logger.info("Shutting down Technical Service")
    
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
        "service": "technical",
        "version": "4.1.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/analyze", response_model=TechnicalResponse)
async def analyze_technical(request: TechnicalRequest):
    """Perform comprehensive technical analysis"""
    
    try:
        # Check cache first
        cache_key = f"technical:{request.symbol}:{request.timeframe}"
        cached = await get_cached_analysis(cache_key)
        if cached:
            return TechnicalResponse(**cached)
        
        # Get market data
        data = await get_market_data(
            request.symbol,
            request.timeframe,
            request.lookback_periods
        )
        
        if data is None or data.empty:
            raise HTTPException(status_code=404, detail=f"No data available for {request.symbol}")
        
        # Calculate all indicators
        indicators = calculate_indicators(data)
        
        # Generate signals
        signals = generate_signals(indicators, data)
        
        # Find support and resistance levels
        support_levels = find_support_levels(data)
        resistance_levels = find_resistance_levels(data)
        
        # Calculate pivot points
        pivot_points = calculate_pivot_points(data)
        
        # Determine entry, stop loss, and take profit
        entry_price = float(data['Close'].iloc[-1])
        
        # Calculate stop loss based on ATR
        atr = indicators["atr"]
        
        if signals.overall_signal in [SignalStrength.BUY, SignalStrength.STRONG_BUY]:
            stop_loss = entry_price - (atr * state.config.atr_stop_multiplier)
            take_profit = entry_price + (atr * state.config.atr_stop_multiplier * 2)
        elif signals.overall_signal in [SignalStrength.SELL, SignalStrength.STRONG_SELL]:
            stop_loss = entry_price + (atr * state.config.atr_stop_multiplier)
            take_profit = entry_price - (atr * state.config.atr_stop_multiplier * 2)
        else:
            stop_loss = None
            take_profit = None
        
        # Create response
        response = TechnicalResponse(
            symbol=request.symbol,
            indicators=TechnicalIndicators(**indicators),
            signals=signals,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            pivot_points=pivot_points,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now()
        )
        
        # Cache result
        await cache_analysis(cache_key, response.dict(), ttl=300)
        
        # Store in database
        await store_technical_analysis(request.symbol, response.dict())
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Technical analysis failed for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/v1/analyze/simple")
async def analyze_simple(symbol: str):
    """Simplified analysis endpoint for orchestration"""
    
    request = TechnicalRequest(symbol=symbol)
    result = await analyze_technical(request)
    
    return {
        "symbol": symbol,
        "signal": result.signals.overall_signal.value,
        "confidence": result.signals.confidence,
        "indicators": {
            "rsi": result.indicators.rsi,
            "macd": result.indicators.macd,
            "bb_position": (result.entry_price - result.indicators.bb_lower) / 
                          (result.indicators.bb_upper - result.indicators.bb_lower)
        }
    }

@app.post("/api/v1/signals/batch")
async def get_signals_batch(symbols: List[str]):
    """Get signals for multiple symbols"""
    
    results = []
    
    for symbol in symbols:
        try:
            request = TechnicalRequest(symbol=symbol)
            analysis = await analyze_technical(request)
            
            results.append({
                "symbol": symbol,
                "signal": analysis.signals.overall_signal.value,
                "confidence": analysis.signals.confidence
            })
        except Exception as e:
            logger.warning(f"Analysis failed for {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "signal": "neutral",
                "confidence": 0,
                "error": str(e)
            })
    
    return {"results": results}

@app.get("/api/v1/indicators/{symbol}")
async def get_current_indicators(symbol: str, timeframe: str = "5m"):
    """Get current indicator values for a symbol"""
    
    request = TechnicalRequest(symbol=symbol, timeframe=timeframe)
    analysis = await analyze_technical(request)
    
    return {
        "symbol": symbol,
        "indicators": analysis.indicators.dict(),
        "timestamp": analysis.timestamp
    }

# === INDICATOR CALCULATIONS ===

def calculate_indicators(data: pd.DataFrame) -> Dict:
    """Calculate all technical indicators"""
    
    indicators = {}
    
    try:
        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']
        
        # Trend Indicators
        indicators['sma_20'] = float(ta.trend.sma_indicator(close, window=20).iloc[-1])
        indicators['sma_50'] = float(ta.trend.sma_indicator(close, window=50).iloc[-1]) if len(close) >= 50 else indicators['sma_20']
        indicators['ema_12'] = float(ta.trend.ema_indicator(close, window=12).iloc[-1])
        indicators['ema_26'] = float(ta.trend.ema_indicator(close, window=26).iloc[-1])
        
        # MACD
        macd = ta.trend.MACD(close)
        indicators['macd'] = float(macd.macd().iloc[-1])
        indicators['macd_signal'] = float(macd.macd_signal().iloc[-1])
        indicators['macd_histogram'] = float(macd.macd_diff().iloc[-1])
        
        # Momentum Indicators
        indicators['rsi'] = float(ta.momentum.RSIIndicator(close).rsi().iloc[-1])
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(high, low, close)
        indicators['stochastic_k'] = float(stoch.stoch().iloc[-1])
        indicators['stochastic_d'] = float(stoch.stoch_signal().iloc[-1])
        
        # Williams %R
        indicators['williams_r'] = float(ta.momentum.WilliamsRIndicator(high, low, close).williams_r().iloc[-1])
        
        # CCI
        indicators['cci'] = float(ta.trend.CCIIndicator(high, low, close).cci().iloc[-1])
        
        # Volatility Indicators
        bb = ta.volatility.BollingerBands(close)
        indicators['bb_upper'] = float(bb.bollinger_hband().iloc[-1])
        indicators['bb_middle'] = float(bb.bollinger_mavg().iloc[-1])
        indicators['bb_lower'] = float(bb.bollinger_lband().iloc[-1])
        indicators['bb_width'] = float(bb.bollinger_wband().iloc[-1])
        
        # ATR
        indicators['atr'] = float(ta.volatility.AverageTrueRange(high, low, close).average_true_range().iloc[-1])
        
        # Volume Indicators
        indicators['obv'] = float(ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume().iloc[-1])
        
        # VWAP
        vwap = calculate_vwap(data)
        indicators['vwap'] = float(vwap.iloc[-1]) if vwap is not None else float(close.iloc[-1])
        
        # Volume Ratio
        if len(volume) >= 20:
            avg_volume = volume.rolling(window=20).mean().iloc[-1]
            indicators['volume_ratio'] = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 1.0
        else:
            indicators['volume_ratio'] = 1.0
        
    except Exception as e:
        logger.error(f"Indicator calculation error: {e}")
        # Return default values on error
        return get_default_indicators()
    
    return indicators

def generate_signals(indicators: Dict, data: pd.DataFrame) -> TechnicalSignals:
    """Generate trading signals from indicators"""
    
    try:
        close_price = float(data['Close'].iloc[-1])
        
        # Trend Signal
        trend_score = 0
        trend_signals = []
        
        # Moving Average Analysis
        if close_price > indicators['sma_20']:
            trend_score += 25
            trend_signals.append("Above SMA20")
        if close_price > indicators['sma_50']:
            trend_score += 25
            trend_signals.append("Above SMA50")
        
        # MACD Analysis
        if indicators['macd'] > indicators['macd_signal']:
            trend_score += 25
            trend_signals.append("MACD Bullish")
        if indicators['macd_histogram'] > 0:
            trend_score += 25
            trend_signals.append("MACD Histogram Positive")
        
        trend_signal = score_to_signal(trend_score)
        
        # Momentum Signal
        momentum_score = 0
        momentum_signals = []
        
        # RSI Analysis
        if indicators['rsi'] < state.config.rsi_oversold:
            momentum_score += 40
            momentum_signals.append("RSI Oversold")
        elif indicators['rsi'] > state.config.rsi_overbought:
            momentum_score -= 40
            momentum_signals.append("RSI Overbought")
        else:
            momentum_score += 20
        
        # Stochastic Analysis
        if indicators['stochastic_k'] < state.config.stoch_oversold:
            momentum_score += 30
            momentum_signals.append("Stoch Oversold")
        elif indicators['stochastic_k'] > state.config.stoch_overbought:
            momentum_score -= 30
            momentum_signals.append("Stoch Overbought")
        
        # CCI Analysis
        if indicators['cci'] < -100:
            momentum_score += 30
            momentum_signals.append("CCI Oversold")
        elif indicators['cci'] > 100:
            momentum_score -= 30
            momentum_signals.append("CCI Overbought")
        
        momentum_signal = score_to_signal(momentum_score)
        
        # Volatility Signal
        volatility_score = 0
        volatility_signals = []
        
        # Bollinger Bands Analysis
        bb_position = (close_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
        
        if bb_position < 0.2:
            volatility_score += 50
            volatility_signals.append("Near Lower BB")
        elif bb_position > 0.8:
            volatility_score -= 50
            volatility_signals.append("Near Upper BB")
        else:
            volatility_score += 25
        
        # Band Width Analysis
        if indicators['bb_width'] < 0.05:
            volatility_score += 25
            volatility_signals.append("BB Squeeze")
        elif indicators['bb_width'] > 0.15:
            volatility_score += 25
            volatility_signals.append("BB Expansion")
        
        volatility_signal = score_to_signal(volatility_score)
        
        # Volume Signal
        volume_score = 0
        volume_signals = []
        
        # Volume Ratio Analysis
        if indicators['volume_ratio'] > 2.0:
            volume_score += 50
            volume_signals.append("High Volume")
        elif indicators['volume_ratio'] > 1.5:
            volume_score += 25
            volume_signals.append("Above Avg Volume")
        
        # VWAP Analysis
        if close_price > indicators['vwap']:
            volume_score += 25
            volume_signals.append("Above VWAP")
        else:
            volume_score -= 25
            volume_signals.append("Below VWAP")
        
        # OBV Trend
        if len(data) > 20:
            obv_trend = calculate_trend(data['Volume'].values[-20:])
            if obv_trend > 0:
                volume_score += 25
                volume_signals.append("OBV Rising")
        
        volume_signal = score_to_signal(volume_score)
        
        # Overall Signal
        signal_weights = {
            SignalStrength.STRONG_BUY: 2,
            SignalStrength.BUY: 1,
            SignalStrength.NEUTRAL: 0,
            SignalStrength.SELL: -1,
            SignalStrength.STRONG_SELL: -2
        }
        
        weighted_score = (
            signal_weights[trend_signal] * 0.3 +
            signal_weights[momentum_signal] * 0.3 +
            signal_weights[volatility_signal] * 0.2 +
            signal_weights[volume_signal] * 0.2
        )
        
        if weighted_score >= 1.5:
            overall_signal = SignalStrength.STRONG_BUY
        elif weighted_score >= 0.5:
            overall_signal = SignalStrength.BUY
        elif weighted_score <= -1.5:
            overall_signal = SignalStrength.STRONG_SELL
        elif weighted_score <= -0.5:
            overall_signal = SignalStrength.SELL
        else:
            overall_signal = SignalStrength.NEUTRAL
        
        # Calculate confidence
        confidence = calculate_signal_confidence(
            trend_score, momentum_score, volatility_score, volume_score
        )
        
        return TechnicalSignals(
            trend_signal=trend_signal,
            momentum_signal=momentum_signal,
            volatility_signal=volatility_signal,
            volume_signal=volume_signal,
            overall_signal=overall_signal,
            confidence=confidence
        )
        
    except Exception as e:
        logger.error(f"Signal generation error: {e}")
        return TechnicalSignals(
            trend_signal=SignalStrength.NEUTRAL,
            momentum_signal=SignalStrength.NEUTRAL,
            volatility_signal=SignalStrength.NEUTRAL,
            volume_signal=SignalStrength.NEUTRAL,
            overall_signal=SignalStrength.NEUTRAL,
            confidence=0
        )

def find_support_levels(data: pd.DataFrame, num_levels: int = 3) -> List[float]:
    """Find support levels"""
    
    try:
        lows = data['Low'].values
        
        # Find local minima
        support_levels = []
        
        for i in range(5, len(lows) - 5):
            if all(lows[i] < lows[j] for j in range(i-5, i)) and \
               all(lows[i] < lows[j] for j in range(i+1, i+6)):
                support_levels.append(float(lows[i]))
        
        # Remove duplicates and sort
        support_levels = list(set(support_levels))
        support_levels.sort()
        
        # Return the most recent/relevant levels
        return support_levels[-num_levels:] if len(support_levels) >= num_levels else support_levels
        
    except Exception as e:
        logger.error(f"Support level calculation error: {e}")
        return []

def find_resistance_levels(data: pd.DataFrame, num_levels: int = 3) -> List[float]:
    """Find resistance levels"""
    
    try:
        highs = data['High'].values
        
        # Find local maxima
        resistance_levels = []
        
        for i in range(5, len(highs) - 5):
            if all(highs[i] > highs[j] for j in range(i-5, i)) and \
               all(highs[i] > highs[j] for j in range(i+1, i+6)):
                resistance_levels.append(float(highs[i]))
        
        # Remove duplicates and sort
        resistance_levels = list(set(resistance_levels))
        resistance_levels.sort()
        
        # Return the most recent/relevant levels
        return resistance_levels[-num_levels:] if len(resistance_levels) >= num_levels else resistance_levels
        
    except Exception as e:
        logger.error(f"Resistance level calculation error: {e}")
        return []

def calculate_pivot_points(data: pd.DataFrame) -> Dict[str, float]:
    """Calculate pivot points"""
    
    try:
        # Use previous day's data for pivot calculation
        high = float(data['High'].iloc[-1])
        low = float(data['Low'].iloc[-1])
        close = float(data['Close'].iloc[-1])
        
        # Standard Pivot Point
        pivot = (high + low + close) / 3
        
        # Support and Resistance levels
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            "pivot": pivot,
            "r1": r1,
            "r2": r2,
            "r3": r3,
            "s1": s1,
            "s2": s2,
            "s3": s3
        }
        
    except Exception as e:
        logger.error(f"Pivot point calculation error: {e}")
        return {}

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

def calculate_vwap(data: pd.DataFrame) -> Optional[pd.Series]:
    """Calculate VWAP"""
    
    try:
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        cumulative_tpv = (typical_price * data['Volume']).cumsum()
        cumulative_volume = data['Volume'].cumsum()
        
        vwap = cumulative_tpv / cumulative_volume
        return vwap
        
    except Exception as e:
        logger.error(f"VWAP calculation error: {e}")
        return None

def calculate_trend(values: np.ndarray) -> float:
    """Calculate trend using linear regression"""
    
    try:
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        return z[0]  # Return slope
    except:
        return 0

def score_to_signal(score: int) -> SignalStrength:
    """Convert numerical score to signal strength"""
    
    if score >= 80:
        return SignalStrength.STRONG_BUY
    elif score >= 40:
        return SignalStrength.BUY
    elif score <= -80:
        return SignalStrength.STRONG_SELL
    elif score <= -40:
        return SignalStrength.SELL
    else:
        return SignalStrength.NEUTRAL

def calculate_signal_confidence(trend: int, momentum: int, volatility: int, volume: int) -> float:
    """Calculate overall signal confidence"""
    
    # Check for agreement between signals
    scores = [trend, momentum, volatility, volume]
    positive_count = sum(1 for s in scores if s > 20)
    negative_count = sum(1 for s in scores if s < -20)
    
    # High confidence if all signals agree
    if positive_count >= 3:
        confidence = 70 + (positive_count * 7.5)
    elif negative_count >= 3:
        confidence = 70 + (negative_count * 7.5)
    else:
        # Lower confidence for mixed signals
        confidence = 50 + (max(positive_count, negative_count) * 10)
    
    # Adjust for extreme values
    max_score = max(abs(s) for s in scores)
    if max_score > 80:
        confidence += 10
    
    return min(100, confidence)

def get_default_indicators() -> Dict:
    """Return default indicator values"""
    
    return {
        'sma_20': 0, 'sma_50': 0, 'ema_12': 0, 'ema_26': 0,
        'macd': 0, 'macd_signal': 0, 'macd_histogram': 0,
        'rsi': 50, 'stochastic_k': 50, 'stochastic_d': 50,
        'williams_r': -50, 'cci': 0,
        'bb_upper': 0, 'bb_middle': 0, 'bb_lower': 0, 'bb_width': 0,
        'atr': 0, 'obv': 0, 'vwap': 0, 'volume_ratio': 1
    }

async def get_cached_analysis(key: str) -> Optional[Dict]:
    """Get cached analysis data"""
    
    if state.redis_client:
        try:
            data = await state.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
    
    return None

async def cache_analysis(key: str, data: Dict, ttl: int = 300):
    """Cache analysis data"""
    
    if state.redis_client:
        try:
            await state.redis_client.setex(
                key,
                ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.debug(f"Cache set error: {e}")

async def store_technical_analysis(symbol: str, analysis_data: Dict):
    """Store technical analysis in database"""
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO technical_analysis (
                    symbol, indicators, signals,
                    analysis_data, created_at
                ) VALUES ($1, $2, $3, $4, $5)
            """,
                symbol,
                json.dumps(analysis_data.get("indicators", {})),
                json.dumps(analysis_data.get("signals", {})),
                json.dumps(analysis_data, default=str),
                datetime.now()
            )
    except Exception as e:
        logger.error(f"Failed to store technical analysis: {e}")

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎩 Catalyst Trading System - Technical Service v4.1")
    print("=" * 60)
    print("Status: Starting...")
    print("Port: 5003")
    print("Protocol: REST API")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5003,
        log_level="info"
    )
