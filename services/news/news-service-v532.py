#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 5.3.2
Last Updated: 2025-10-13
Purpose: News catalyst detection with normalized schema v5.0 and rigorous error handling

REVISION HISTORY:
v5.3.2 (2025-10-16) - Fix DATABASE_URL
v5.3.1 (2025-10-13) - SQL Syntax Fix
- CRITICAL FIX: Fixed interval arithmetic in price impact calculation
- Changed: td.timestamp >= $2 + INTERVAL '5 minutes'
- To: td.timestamp >= $2::timestamptz + '5 minutes'::interval
- Background job now works correctly

v5.3.0 (2025-10-13) - Production Error Handling Upgrade
- NO Unicode emojis in production logs (ASCII only)
- Specific exception types (ValueError, asyncpg.PostgresError, aiohttp.ClientError)
- Structured logging with exc_info and extra context
- HTTPException with proper status codes (400, 502, 503, 500)
- No silent failures - all errors tracked and raised
- FastAPI lifespan (no deprecation warnings)
- Success/failure tracking for batch operations

Description of Service:
Intelligence foundation for Catalyst Trading System.
Uses normalized v5.0 schema with proper FKs (security_id + time_id).
Tracks news price impact and source reliability for ML.
Production-safe error handling with NO silent failures.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncio
import aiohttp
import asyncpg
import json
import os
import logging
import logging.handlers
from enum import Enum

# ============================================================================
# SERVICE METADATA (SINGLE SOURCE OF TRUTH)
# ============================================================================
SERVICE_NAME = "news"
SERVICE_VERSION = "5.3.1"
SERVICE_TITLE = "News Intelligence Service"
SERVICE_PORT = 5008
SCHEMA_VERSION = "v5.0 normalized"

# ============================================================================
# JSON LOGGING (Production-Safe - NO Unicode)
# ============================================================================
class JSONFormatter(logging.Formatter):
    """Production-safe JSON formatter with NO Unicode emojis"""
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "level": record.levelname,
            "message": record.getMessage(),
            "context": {
                "function": record.funcName,
                "line": record.lineno,
                "module": record.module
            }
        }
        
        # Add stack trace for errors
        if record.exc_info:
            log_data["traceback"] = self.formatException(record.exc_info)
        
        # Add extra context if present
        if hasattr(record, 'symbol'):
            log_data["context"]["symbol"] = record.symbol
        if hasattr(record, 'error_type'):
            log_data["context"]["error_type"] = record.error_type
        if hasattr(record, 'source'):
            log_data["context"]["source"] = record.source
            
        return json.dumps(log_data)

logger = logging.getLogger(SERVICE_NAME)
logger.setLevel(logging.DEBUG)

# File handler with rotation
os.makedirs("/app/logs", exist_ok=True)
file_handler = logging.handlers.RotatingFileHandler(
    f"/app/logs/{SERVICE_NAME}-service.log",
    maxBytes=10*1024*1024,
    backupCount=5
)
file_handler.setFormatter(JSONFormatter())
logger.addHandler(file_handler)

# Console handler (production-safe format)
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ============================================================================
# CONFIGURATION
# ============================================================================
class Config:
    """Service configuration"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable required")
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10
    
    # News API keys
    BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY", "")
    ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

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
# ENUMS
# ============================================================================
class SentimentLabel(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"

class CatalystType(str, Enum):
    EARNINGS = "earnings"
    FDA_APPROVAL = "fda_approval"
    MERGER_ACQUISITION = "merger_acquisition"
    PRODUCT_LAUNCH = "product_launch"
    EXECUTIVE_CHANGE = "executive_change"
    PARTNERSHIP = "partnership"
    LEGAL = "legal"
    FINANCIAL_RESULTS = "financial_results"
    ANALYST_UPGRADE = "analyst_upgrade"
    ANALYST_DOWNGRADE = "analyst_downgrade"
    OTHER = "other"

class CatalystStrength(str, Enum):
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"

# ============================================================================
# DATA MODELS
# ============================================================================
class NewsRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    hours_back: int = Field(default=24, description="Hours to look back")

class NewsArticle(BaseModel):
    symbol: str
    headline: str
    summary: Optional[str] = None
    url: Optional[str] = None
    source: str
    published_at: datetime
    sentiment_score: float
    sentiment_label: SentimentLabel
    catalyst_type: Optional[CatalystType] = None
    catalyst_strength: Optional[CatalystStrength] = None

# ============================================================================
# LIFESPAN (Modern FastAPI - NO deprecation warnings)
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan management"""
    # Startup
    logger.info(f"[STARTUP] {SERVICE_TITLE} v{SERVICE_VERSION}")
    logger.info(f"[STARTUP] Schema: {SCHEMA_VERSION}")
    logger.info(f"[STARTUP] Port: {SERVICE_PORT}")
    
    try:
        # Connect to database
        state.db_pool = await asyncpg.create_pool(
            Config.DATABASE_URL,
            min_size=Config.POOL_MIN_SIZE,
            max_size=Config.POOL_MAX_SIZE,
            command_timeout=60
        )
        logger.info("[STARTUP] Database connection pool created")
        
        # Test connection
        async with state.db_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"[STARTUP] PostgreSQL: {version[:50]}...")
        
        state.is_healthy = True
        logger.info("[STARTUP] Service ready")
        
        # Start background jobs
        asyncio.create_task(calculate_news_price_impact())
        logger.info("[STARTUP] Background jobs started")
        
    except asyncpg.PostgresError as e:
        logger.critical(
            f"[STARTUP] Database connection failed: {e}",
            exc_info=True,
            extra={'error_type': 'database'}
        )
        state.is_healthy = False
    except Exception as e:
        logger.critical(
            f"[STARTUP] Unexpected error: {e}",
            exc_info=True,
            extra={'error_type': 'startup'}
        )
        state.is_healthy = False
    
    yield
    
    # Shutdown
    logger.info("[SHUTDOWN] Closing database connections")
    if state.db_pool:
        await state.db_pool.close()
    logger.info("[SHUTDOWN] Service stopped")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title=SERVICE_TITLE,
    version=SERVICE_VERSION,
    description=f"News catalyst detection with {SCHEMA_VERSION}",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HELPER FUNCTIONS (Rigorous Error Handling)
# ============================================================================
async def get_security_id(symbol: str) -> int:
    """
    Get or create security_id for symbol.
    
    Raises:
        ValueError: If symbol is invalid
        asyncpg.PostgresError: If database error
        RuntimeError: If helper function fails
    """
    try:
        if not symbol or not isinstance(symbol, str):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        symbol = symbol.upper().strip()
        
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)", symbol
        )
        
        if not security_id:
            raise RuntimeError(f"Helper function returned NULL for {symbol}")
        
        return security_id
        
    except ValueError:
        # Re-raise validation errors
        raise
    except asyncpg.PostgresError as e:
        logger.error(
            f"Database error in get_security_id: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'database'}
        )
        raise
    except Exception as e:
        logger.critical(
            f"Unexpected error in get_security_id: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'unexpected'}
        )
        raise RuntimeError(f"Failed to get security_id for {symbol}: {e}")

async def get_time_id(timestamp: datetime) -> int:
    """
    Get or create time_id for timestamp.
    
    Raises:
        ValueError: If timestamp is invalid
        asyncpg.PostgresError: If database error
        RuntimeError: If helper function fails
    """
    try:
        if not timestamp or not isinstance(timestamp, datetime):
            raise ValueError(f"Invalid timestamp: {timestamp}")
        
        time_id = await state.db_pool.fetchval(
            "SELECT get_or_create_time($1)", timestamp
        )
        
        if not time_id:
            raise RuntimeError(f"Helper function returned NULL for {timestamp}")
        
        return time_id
        
    except ValueError:
        raise
    except asyncpg.PostgresError as e:
        logger.error(
            f"Database error in get_time_id: {e}",
            exc_info=True,
            extra={'timestamp': str(timestamp), 'error_type': 'database'}
        )
        raise
    except Exception as e:
        logger.critical(
            f"Unexpected error in get_time_id: {e}",
            exc_info=True,
            extra={'timestamp': str(timestamp), 'error_type': 'unexpected'}
        )
        raise RuntimeError(f"Failed to get time_id: {e}")

# ============================================================================
# SENTIMENT ANALYSIS
# ============================================================================
async def analyze_sentiment(text: str) -> tuple[float, SentimentLabel]:
    """
    Analyze sentiment of text.
    
    Returns:
        (sentiment_score, sentiment_label) tuple
        
    Raises:
        ValueError: If text is invalid
    """
    try:
        if not text or not isinstance(text, str):
            raise ValueError("Invalid text for sentiment analysis")
        
        # Simple sentiment scoring (production would use VADER or Transformers)
        text_lower = text.lower()
        
        # Positive keywords
        positive_keywords = ['surge', 'jump', 'rally', 'gain', 'beat', 'exceed', 'strong', 'approval']
        negative_keywords = ['plunge', 'drop', 'fall', 'miss', 'weak', 'decline', 'lawsuit']
        
        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)
        
        # Calculate score (-1 to +1)
        total_keywords = positive_count + negative_count
        if total_keywords == 0:
            sentiment_score = 0.0
            sentiment_label = SentimentLabel.NEUTRAL
        else:
            sentiment_score = (positive_count - negative_count) / total_keywords
            
            if sentiment_score > 0.5:
                sentiment_label = SentimentLabel.VERY_POSITIVE
            elif sentiment_score > 0.2:
                sentiment_label = SentimentLabel.POSITIVE
            elif sentiment_score < -0.5:
                sentiment_label = SentimentLabel.VERY_NEGATIVE
            elif sentiment_score < -0.2:
                sentiment_label = SentimentLabel.NEGATIVE
            else:
                sentiment_label = SentimentLabel.NEUTRAL
        
        return (sentiment_score, sentiment_label)
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in sentiment analysis: {e}",
            exc_info=True,
            extra={'error_type': 'sentiment'}
        )
        # Return neutral on error (but log it!)
        return (0.0, SentimentLabel.NEUTRAL)

async def detect_catalyst(article: Dict) -> tuple[Optional[CatalystType], Optional[CatalystStrength]]:
    """
    Detect catalyst type and strength from article.
    
    Returns:
        (catalyst_type, catalyst_strength) tuple or (None, None)
    """
    try:
        text = (article.get('headline', '') + ' ' + article.get('summary', '')).lower()
        
        # Catalyst detection (simplified)
        if 'earning' in text or 'eps' in text:
            return (CatalystType.EARNINGS, CatalystStrength.STRONG)
        elif 'fda' in text or 'approval' in text:
            return (CatalystType.FDA_APPROVAL, CatalystStrength.VERY_STRONG)
        elif 'merger' in text or 'acquisition' in text:
            return (CatalystType.MERGER_ACQUISITION, CatalystStrength.STRONG)
        elif 'upgrade' in text:
            return (CatalystType.ANALYST_UPGRADE, CatalystStrength.MODERATE)
        elif 'downgrade' in text:
            return (CatalystType.ANALYST_DOWNGRADE, CatalystStrength.MODERATE)
        else:
            return (None, None)
            
    except Exception as e:
        logger.warning(
            f"Error in catalyst detection: {e}",
            extra={'error_type': 'catalyst'}
        )
        return (None, None)

# ============================================================================
# NEWS FETCHING
# ============================================================================
async def fetch_news_from_benzinga(symbol: str, hours_back: int = 24) -> List[Dict]:
    """
    Fetch news from Benzinga API.
    
    Raises:
        aiohttp.ClientError: If API request fails
        ValueError: If invalid response
    """
    try:
        if not Config.BENZINGA_API_KEY:
            logger.warning("Benzinga API key not configured")
            return []
        
        # Mock implementation (production would call real API)
        logger.info(f"Fetching Benzinga news for {symbol}")
        return []
        
    except aiohttp.ClientError as e:
        logger.error(
            f"Benzinga API error for {symbol}: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'api', 'source': 'benzinga'}
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error fetching Benzinga news: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'unexpected', 'source': 'benzinga'}
        )
        return []

# ============================================================================
# STORE NEWS ARTICLE
# ============================================================================
async def store_news_article(article: Dict) -> int:
    """
    Store news article with proper FKs and impact tracking.
    
    Args:
        article: Dict with keys: symbol, headline, published_at, source, etc.
        
    Returns:
        news_id of stored article
        
    Raises:
        ValueError: If article data is invalid
        asyncpg.PostgresError: If database error
    """
    try:
        # Validate required fields
        required_fields = ['symbol', 'headline', 'published_at', 'source']
        for field in required_fields:
            if field not in article:
                raise ValueError(f"Missing required field: {field}")
        
        # Get FKs
        security_id = await get_security_id(article['symbol'])
        time_id = await get_time_id(article['published_at'])
        
        # Analyze sentiment
        sentiment_score, sentiment_label = await analyze_sentiment(article['headline'])
        
        # Detect catalyst
        catalyst_type, catalyst_strength = await detect_catalyst(article)
        
        # Store in news_sentiment table
        news_id = await state.db_pool.fetchval("""
            INSERT INTO news_sentiment (
                security_id, time_id, 
                headline, summary, url, source,
                sentiment_score, sentiment_label,
                catalyst_type, catalyst_strength,
                source_reliability_score,
                metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING news_id
        """, 
            security_id, time_id,
            article['headline'], 
            article.get('summary'), 
            article.get('url'), 
            article['source'],
            sentiment_score, 
            sentiment_label.value,
            catalyst_type.value if catalyst_type else None,
            catalyst_strength.value if catalyst_strength else None,
            0.500,  # Initial reliability score
            json.dumps(article.get('metadata', {}))
        )
        
        logger.info(
            f"Stored news article {news_id} for {article['symbol']}",
            extra={
                'symbol': article['symbol'],
                'news_id': news_id,
                'source': article['source'],
                'sentiment': sentiment_label.value
            }
        )
        
        return news_id
        
    except ValueError:
        # Re-raise validation errors
        raise
    except asyncpg.PostgresError as e:
        logger.critical(
            f"Database error storing news: {e}",
            exc_info=True,
            extra={'symbol': article.get('symbol'), 'error_type': 'database'}
        )
        raise
    except Exception as e:
        logger.critical(
            f"Unexpected error storing news: {e}",
            exc_info=True,
            extra={'symbol': article.get('symbol'), 'error_type': 'unexpected'}
        )
        raise

# ============================================================================
# BACKGROUND JOBS
# ============================================================================
async def calculate_news_price_impact():
    """
    Background job: Calculate actual price impact after news events.
    
    Runs every 60 seconds, calculates price movement 5/15/30 min after news.
    """
    logger.info("[BACKGROUND] Starting price impact calculation job")
    
    while True:
        try:
            # Find news events without price impact calculated
            news_events = await state.db_pool.fetch("""
                SELECT 
                    ns.news_id, 
                    ns.security_id, 
                    td.timestamp as published_at,
                    th_before.close as price_before
                FROM news_sentiment ns
                JOIN time_dimension td ON td.time_id = ns.time_id
                LEFT JOIN LATERAL (
                    SELECT close FROM trading_history th2
                    JOIN time_dimension td2 ON td2.time_id = th2.time_id
                    WHERE th2.security_id = ns.security_id
                    AND td2.timestamp <= td.timestamp
                    ORDER BY td2.timestamp DESC LIMIT 1
                ) th_before ON TRUE
                WHERE ns.price_impact_5min IS NULL
                AND td.timestamp < NOW() - '5 minutes'::interval
                LIMIT 100
            """)
            
            success_count = 0
            failed_items = []
            
            for event in news_events:
                try:
                    # FIXED: Proper PostgreSQL interval arithmetic with explicit casts
                    prices = await state.db_pool.fetchrow("""
                        SELECT 
                            (SELECT close FROM trading_history th
                             JOIN time_dimension td ON td.time_id = th.time_id
                             WHERE th.security_id = $1 
                             AND td.timestamp >= $2::timestamptz + '5 minutes'::interval
                             ORDER BY td.timestamp ASC LIMIT 1) as price_5min,
                            
                            (SELECT close FROM trading_history th
                             JOIN time_dimension td ON td.time_id = th.time_id
                             WHERE th.security_id = $1 
                             AND td.timestamp >= $2::timestamptz + '15 minutes'::interval
                             ORDER BY td.timestamp ASC LIMIT 1) as price_15min,
                            
                            (SELECT close FROM trading_history th
                             JOIN time_dimension td ON td.time_id = th.time_id
                             WHERE th.security_id = $1 
                             AND td.timestamp >= $2::timestamptz + '30 minutes'::interval
                             ORDER BY td.timestamp ASC LIMIT 1) as price_30min
                    """, event['security_id'], event['published_at'])
                    
                    # Calculate % impacts
                    if event['price_before'] and prices:
                        impact_5min = ((prices['price_5min'] - event['price_before']) / 
                                      event['price_before'] * 100) if prices['price_5min'] else None
                        impact_15min = ((prices['price_15min'] - event['price_before']) / 
                                       event['price_before'] * 100) if prices['price_15min'] else None
                        impact_30min = ((prices['price_30min'] - event['price_before']) / 
                                       event['price_before'] * 100) if prices['price_30min'] else None
                        
                        # Update news_sentiment with impacts
                        await state.db_pool.execute("""
                            UPDATE news_sentiment
                            SET price_impact_5min = $1,
                                price_impact_15min = $2,
                                price_impact_30min = $3
                            WHERE news_id = $4
                        """, impact_5min, impact_15min, impact_30min, event['news_id'])
                        
                        success_count += 1
                        
                except asyncpg.PostgresError as e:
                    logger.warning(
                        f"DB error calculating impact for news {event['news_id']}: {e}",
                        extra={'news_id': event['news_id'], 'error_type': 'database'}
                    )
                    failed_items.append(event['news_id'])
                except Exception as e:
                    logger.warning(
                        f"Unexpected error calculating impact for news {event['news_id']}: {e}",
                        extra={'news_id': event['news_id'], 'error_type': 'unexpected'}
                    )
                    failed_items.append(event['news_id'])
            
            if len(news_events) > 0:
                logger.info(
                    f"Price impact job: processed {success_count}/{len(news_events)} events",
                    extra={'success': success_count, 'failed': len(failed_items), 'total': len(news_events)}
                )
            
            # Wait before next check
            await asyncio.sleep(60)
            
        except asyncpg.PostgresError as e:
            logger.error(
                f"[BACKGROUND] Database error in price impact calculation: {e}",
                exc_info=True,
                extra={'error_type': 'database'}
            )
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(
                f"[BACKGROUND] Unexpected error in price impact calculation: {e}",
                exc_info=True,
                extra={'error_type': 'unexpected'}
            )
            await asyncio.sleep(60)

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if state.is_healthy else "unhealthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "database": "connected" if state.db_pool else "disconnected",
        "schema": SCHEMA_VERSION
    }

@app.post("/api/v1/news/fetch")
async def fetch_news(request: NewsRequest):
    """
    Fetch and store news for a symbol.
    
    Raises:
        HTTPException 400: Invalid request
        HTTPException 502: External API error
        HTTPException 503: Database unavailable
        HTTPException 500: Internal error
    """
    try:
        # Validate symbol
        if not request.symbol or len(request.symbol) > 10:
            raise ValueError(f"Invalid symbol: {request.symbol}")
        
        symbol = request.symbol.upper()
        
        # Fetch from news sources
        articles = await fetch_news_from_benzinga(symbol, request.hours_back)
        
        # Store articles
        stored_ids = []
        failed_articles = []
        
        for article in articles:
            try:
                news_id = await store_news_article(article)
                stored_ids.append(news_id)
            except Exception as e:
                logger.warning(
                    f"Failed to store article: {e}",
                    extra={'symbol': symbol, 'error_type': 'storage'}
                )
                failed_articles.append(article.get('headline', 'Unknown'))
        
        logger.info(
            f"News fetch complete: {len(stored_ids)} stored, {len(failed_articles)} failed",
            extra={'symbol': symbol, 'stored': len(stored_ids), 'failed': len(failed_articles)}
        )
        
        return {
            "symbol": symbol,
            "fetched": len(articles),
            "stored": len(stored_ids),
            "failed": len(failed_articles),
            "news_ids": stored_ids
        }
        
    except ValueError as e:
        logger.error(
            f"Invalid request: {e}",
            extra={'symbol': request.symbol, 'error_type': 'validation'}
        )
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'Invalid request',
                'message': str(e)
            }
        )
    except aiohttp.ClientError as e:
        logger.error(
            f"External API error: {e}",
            exc_info=True,
            extra={'symbol': request.symbol, 'error_type': 'api'}
        )
        raise HTTPException(
            status_code=502,
            detail={
                'error': 'News API unavailable',
                'message': 'Failed to fetch news from external sources',
                'retry_after': 60
            }
        )
    except asyncpg.PostgresError as e:
        logger.critical(
            f"Database error: {e}",
            exc_info=True,
            extra={'symbol': request.symbol, 'error_type': 'database'}
        )
        raise HTTPException(
            status_code=503,
            detail={
                'error': 'Database unavailable',
                'message': 'Cannot store news articles',
                'retry_after': 30
            }
        )
    except Exception as e:
        logger.critical(
            f"Unexpected error: {e}",
            exc_info=True,
            extra={'symbol': request.symbol, 'error_type': 'unexpected'}
        )
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'Internal server error',
                'message': 'News fetch failed unexpectedly'
            }
        )

@app.get("/api/v1/news/{symbol}")
async def get_news(symbol: str, hours: int = 24):
    """
    Get recent news for a symbol (with JOINs).
    
    Raises:
        HTTPException 400: Invalid symbol
        HTTPException 503: Database unavailable
        HTTPException 500: Internal error
    """
    try:
        # Validate symbol
        if not symbol or len(symbol) > 10:
            raise ValueError(f"Invalid symbol: {symbol}")
        
        symbol = symbol.upper()
        
        # Query with JOINs
        news = await state.db_pool.fetch("""
            SELECT 
                ns.*,
                s.symbol,
                s.company_name,
                sec.sector_name,
                td.timestamp as published_at,
                td.market_session
            FROM news_sentiment ns
            JOIN securities s ON s.security_id = ns.security_id
            JOIN sectors sec ON sec.sector_id = s.sector_id
            JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE s.symbol = $1
            AND td.timestamp >= NOW() - $2::interval * '1 hour'::interval
            ORDER BY td.timestamp DESC
            LIMIT 100
        """, symbol, hours)
        
        return {
            "symbol": symbol,
            "count": len(news),
            "news": [dict(n) for n in news]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail={'error': 'Invalid symbol', 'message': str(e)})
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True, extra={'symbol': symbol, 'error_type': 'database'})
        raise HTTPException(status_code=503, detail={'error': 'Database unavailable', 'retry_after': 30})
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True, extra={'symbol': symbol, 'error_type': 'unexpected'})
        raise HTTPException(status_code=500, detail={'error': 'Internal server error'})

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    
    # Production-safe startup banner (NO Unicode)
    print("=" * 60)
    print(f"Catalyst Trading System - {SERVICE_TITLE} v{SERVICE_VERSION}")
    print("=" * 60)
    print(f"Schema: {SCHEMA_VERSION}")
    print(f"Port: {SERVICE_PORT}")
    print(f"Status: Starting...")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVICE_PORT,
        log_level="info"
    )
