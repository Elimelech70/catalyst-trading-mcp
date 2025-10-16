#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 5.4.0
Last Updated: 2025-10-16
Purpose: News catalyst detection with modern FastAPI and fixed processing

REVISION HISTORY:
v5.4.0 (2025-10-16) - Modern FastAPI & Processing Fixes
- FIXED: Price impact calculation stuck at 4/100 events
- ADDED: Modern lifespan context manager (no deprecation)
- IMPROVED: Background job error recovery
- ENHANCED: Processing rate limiting and monitoring
- BETTER: Database query optimization
- CLEANER: Startup/shutdown sequence

v5.3.2 (2025-10-16) - Fix DATABASE_URL
v5.3.1 (2025-10-13) - SQL Syntax Fix

Description of Service:
Intelligence foundation for Catalyst Trading System.
Uses normalized v5.0 schema with proper FKs (security_id + time_id).
Tracks news price impact and source reliability for ML.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import redis.asyncio as redis
import aiohttp
import os
import logging
import asyncio
import json
import traceback
from dataclasses import dataclass

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("news")

# ============================================================================
# CONFIGURATION
# ============================================================================
@dataclass
class Config:
    SERVICE_NAME: str = "news-service"
    SERVICE_VERSION: str = "5.4.0"
    SERVICE_PORT: int = 5008
    SCHEMA_VERSION: str = "v5.0 normalized"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DB_POOL_MIN: int = 5
    DB_POOL_MAX: int = 20
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")
    
    # Processing
    PRICE_IMPACT_BATCH_SIZE: int = 20  # Reduced from 100 to avoid timeouts
    PRICE_IMPACT_INTERVAL: int = 60    # Check every minute
    SOURCE_RELIABILITY_INTERVAL: int = 3600  # Update hourly
    MIN_EVENTS_FOR_RELIABILITY: int = 10
    
    # API Keys
    ALPHA_VANTAGE_KEY: str = os.getenv("ALPHA_VANTAGE_KEY", "")
    FINNHUB_KEY: str = os.getenv("FINNHUB_KEY", "")

config = Config()

# ============================================================================
# GLOBAL STATE
# ============================================================================
class ServiceState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.background_tasks: List[asyncio.Task] = []
        self.processing_stats = {
            "price_impacts_calculated": 0,
            "price_impacts_failed": 0,
            "last_processing_time": None,
            "current_backlog": 0
        }

state = ServiceState()

# ============================================================================
# LIFESPAN CONTEXT MANAGER
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern lifespan management for FastAPI.
    Handles startup, background tasks, and shutdown properly.
    """
    # === STARTUP ===
    print(f"""
======================================================================
Catalyst Trading System - News Service v{config.SERVICE_VERSION}
======================================================================
[OK] {config.SCHEMA_VERSION} with security_id + time_id FKs
[OK] Price impact tracking (5min, 15min, 30min)
[OK] Source reliability scoring
[OK] RIGOROUS error handling - NO silent failures
[OK] FastAPI lifespan (no deprecation warnings)
[OK] Optimized batch processing
Port: {config.SERVICE_PORT}
======================================================================
    """)
    
    logger.info(f"Starting News Service v{config.SERVICE_VERSION}")
    
    # Initialize database
    try:
        if not config.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
        
        state.db_pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=config.DB_POOL_MIN,
            max_size=config.DB_POOL_MAX,
            command_timeout=60
        )
        logger.info("Database pool initialized")
        
        # Verify schema
        await verify_schema()
        
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise
    
    # Initialize Redis (optional)
    try:
        state.redis_client = await redis.from_url(config.REDIS_URL)
        await state.redis_client.ping()
        logger.info("Redis client initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed (non-critical): {e}")
        state.redis_client = None
    
    # Initialize HTTP session
    state.http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30)
    )
    logger.info("HTTP session initialized")
    
    # Start background tasks
    state.background_tasks = [
        asyncio.create_task(calculate_news_price_impact()),
        asyncio.create_task(update_source_reliability())
    ]
    logger.info("Background tasks started")
    
    logger.info(f"News Service v{config.SERVICE_VERSION} ready on port {config.SERVICE_PORT}")
    
    # === YIELD TO APP ===
    yield
    
    # === SHUTDOWN ===
    logger.info("Shutting down News Service...")
    
    # Cancel background tasks
    for task in state.background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Background tasks stopped")
    
    # Close connections
    if state.http_session:
        await state.http_session.close()
        logger.info("HTTP session closed")
    
    if state.db_pool:
        await state.db_pool.close()
        logger.info("Database pool closed")
    
    if state.redis_client:
        await state.redis_client.close()
        logger.info("Redis connection closed")
    
    logger.info("News Service shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title="News Service",
    version=config.SERVICE_VERSION,
    description="News catalyst detection with price impact tracking",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
async def verify_schema():
    """Verify normalized schema v5.0 is deployed"""
    try:
        # Check for security_id FK in news_sentiment
        has_security_id = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'news_sentiment' 
                AND column_name = 'security_id'
            )
        """)
        
        if not has_security_id:
            raise ValueError("news_sentiment missing security_id - schema v5.0 not deployed!")
        
        logger.info("Schema v5.0 verified - news_sentiment uses security_id FK")
        
    except Exception as e:
        logger.critical(f"Schema verification failed: {e}", exc_info=True)
        raise

async def get_security_id(symbol: str) -> Optional[int]:
    """Get or create security_id for symbol"""
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT security_id FROM securities WHERE symbol = $1",
            symbol.upper()
        )
        
        if not security_id:
            security_id = await state.db_pool.fetchval("""
                INSERT INTO securities (symbol, company_name, active)
                VALUES ($1, $2, TRUE)
                ON CONFLICT (symbol) DO UPDATE SET symbol = EXCLUDED.symbol
                RETURNING security_id
            """, symbol.upper(), f"{symbol.upper()} Corp")
        
        return security_id
        
    except Exception as e:
        logger.error(f"Failed to get/create security_id for {symbol}: {e}")
        raise

async def get_time_id(timestamp: datetime) -> int:
    """Get or create time_id for timestamp"""
    try:
        time_id = await state.db_pool.fetchval(
            "SELECT get_or_create_time($1)",
            timestamp
        )
        return time_id
    except Exception as e:
        logger.error(f"Failed to get time_id: {e}")
        raise

# ============================================================================
# SENTIMENT ANALYSIS
# ============================================================================
class SentimentAnalyzer:
    """Simple sentiment analysis (can be replaced with ML model)"""
    
    POSITIVE_WORDS = {
        'upgrade', 'beat', 'positive', 'strong', 'growth', 'surge',
        'rally', 'gain', 'profit', 'revenue', 'breakthrough', 'innovation'
    }
    
    NEGATIVE_WORDS = {
        'downgrade', 'miss', 'negative', 'weak', 'decline', 'fall',
        'loss', 'concern', 'warning', 'risk', 'lawsuit', 'investigation'
    }
    
    CATALYST_WORDS = {
        'fda', 'approval', 'merger', 'acquisition', 'earnings', 'guidance',
        'partnership', 'contract', 'breakthrough', 'launch', 'ipo'
    }
    
    @classmethod
    def analyze(cls, title: str, summary: str) -> Dict[str, float]:
        """Analyze sentiment and catalyst strength"""
        text = f"{title} {summary}".lower()
        
        # Count sentiment words
        positive_count = sum(1 for word in cls.POSITIVE_WORDS if word in text)
        negative_count = sum(1 for word in cls.NEGATIVE_WORDS if word in text)
        catalyst_count = sum(1 for word in cls.CATALYST_WORDS if word in text)
        
        # Calculate scores
        total_words = positive_count + negative_count + 1
        sentiment_score = (positive_count - negative_count) / total_words
        
        # Normalize to [-1, 1]
        sentiment_score = max(-1, min(1, sentiment_score))
        
        # Catalyst strength [0, 1]
        catalyst_strength = min(1.0, catalyst_count / 3)
        
        # Magnitude [0, 1]
        magnitude = min(1.0, (positive_count + negative_count + catalyst_count) / 5)
        
        return {
            'sentiment_score': sentiment_score,
            'catalyst_strength': catalyst_strength,
            'magnitude': magnitude
        }

# ============================================================================
# BACKGROUND JOBS
# ============================================================================
async def calculate_news_price_impact():
    """
    Background job: Calculate actual price impact after news events.
    FIXED: Now processes in smaller batches and handles errors better.
    """
    logger.info("Starting price impact calculation job")
    
    while True:
        try:
            # Get backlog count first
            backlog_count = await state.db_pool.fetchval("""
                SELECT COUNT(*) 
                FROM news_sentiment ns
                JOIN time_dimension td ON td.time_id = ns.time_id
                WHERE ns.price_impact_5min IS NULL
                AND td.timestamp < NOW() - INTERVAL '5 minutes'
            """)
            
            state.processing_stats["current_backlog"] = backlog_count
            
            if backlog_count > 0:
                logger.info(f"Price impact backlog: {backlog_count} events to process")
            
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
                    SELECT close FROM trading_history
                    WHERE security_id = ns.security_id
                    AND time_id <= ns.time_id
                    ORDER BY time_id DESC LIMIT 1
                ) th_before ON TRUE
                WHERE ns.price_impact_5min IS NULL
                AND td.timestamp < NOW() - INTERVAL '5 minutes'
                AND th_before.close IS NOT NULL  -- Must have price before
                ORDER BY td.timestamp DESC
                LIMIT $1
            """, config.PRICE_IMPACT_BATCH_SIZE)
            
            processed = 0
            failed = 0
            
            for event in news_events:
                try:
                    # Get prices at different intervals after news
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
                    price_before = float(event['price_before'])
                    
                    impact_5min = None
                    impact_15min = None
                    impact_30min = None
                    
                    if prices['price_5min']:
                        impact_5min = ((float(prices['price_5min']) - price_before) / 
                                      price_before * 100)
                    
                    if prices['price_15min']:
                        impact_15min = ((float(prices['price_15min']) - price_before) / 
                                       price_before * 100)
                    
                    if prices['price_30min']:
                        impact_30min = ((float(prices['price_30min']) - price_before) / 
                                       price_before * 100)
                    
                    # Update news_sentiment with impacts
                    await state.db_pool.execute("""
                        UPDATE news_sentiment
                        SET price_impact_5min = $1,
                            price_impact_15min = $2,
                            price_impact_30min = $3
                        WHERE news_id = $4
                    """, impact_5min, impact_15min, impact_30min, event['news_id'])
                    
                    processed += 1
                    state.processing_stats["price_impacts_calculated"] += 1
                    
                    if impact_5min is not None:
                        logger.debug(f"Updated price impact for news {event['news_id']}: "
                                   f"5min={impact_5min:.2f}%")
                    
                except Exception as e:
                    logger.error(f"Failed to process news {event.get('news_id')}: {e}")
                    failed += 1
                    state.processing_stats["price_impacts_failed"] += 1
                    continue
            
            if processed > 0 or failed > 0:
                logger.info(f"Price impact job: processed {processed}/{len(news_events)} events"
                          f" (failed: {failed}, backlog: {backlog_count})")
            
            state.processing_stats["last_processing_time"] = datetime.utcnow()
            
            # Wait before next check
            await asyncio.sleep(config.PRICE_IMPACT_INTERVAL)
            
        except asyncio.CancelledError:
            logger.info("Price impact calculation job cancelled")
            break
        except Exception as e:
            logger.error(f"Price impact calculation error: {e}", exc_info=True)
            await asyncio.sleep(config.PRICE_IMPACT_INTERVAL)

async def update_source_reliability():
    """Track which news sources accurately predict price moves"""
    logger.info("Starting source reliability update job")
    
    while True:
        try:
            await asyncio.sleep(config.SOURCE_RELIABILITY_INTERVAL)
            
            # Get sources with enough data
            sources = await state.db_pool.fetch("""
                SELECT 
                    source,
                    COUNT(*) as total_articles,
                    AVG(CASE 
                        WHEN (catalyst_strength >= 0.5 AND ABS(price_impact_15min) >= 1.0)
                        OR (catalyst_strength < 0.5 AND ABS(price_impact_15min) < 1.0)
                        THEN 1.0 ELSE 0.0 
                    END) as accuracy
                FROM news_sentiment
                WHERE price_impact_15min IS NOT NULL
                AND catalyst_strength IS NOT NULL
                GROUP BY source
                HAVING COUNT(*) >= $1
            """, config.MIN_EVENTS_FOR_RELIABILITY)
            
            for row in sources:
                reliability = float(row['accuracy'])
                
                await state.db_pool.execute("""
                    UPDATE news_sentiment
                    SET source_reliability_score = $1
                    WHERE source = $2
                    AND source_reliability_score IS DISTINCT FROM $1
                """, reliability, row['source'])
                
                logger.info(f"Updated {row['source']} reliability: {reliability:.3f} "
                          f"({row['total_articles']} articles)")
            
        except asyncio.CancelledError:
            logger.info("Source reliability job cancelled")
            break
        except Exception as e:
            logger.error(f"Source reliability error: {e}", exc_info=True)

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.get("/health")
async def health_check():
    """Health check with detailed status"""
    try:
        db_healthy = False
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_healthy = True
        
        redis_healthy = False
        if state.redis_client:
            await state.redis_client.ping()
            redis_healthy = True
        
        return {
            "status": "healthy",
            "service": config.SERVICE_NAME,
            "version": config.SERVICE_VERSION,
            "schema": config.SCHEMA_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected" if db_healthy else "disconnected",
            "redis": "connected" if redis_healthy else "disconnected",
            "processing_stats": state.processing_stats
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/api/v1/news/{symbol}")
async def get_symbol_news(symbol: str, limit: int = 10):
    """Get recent news for a symbol"""
    try:
        security_id = await get_security_id(symbol)
        
        news = await state.db_pool.fetch("""
            SELECT 
                ns.news_id,
                s.symbol,
                ns.headline,
                ns.summary,
                ns.source,
                ns.url,
                ns.sentiment_score,
                ns.catalyst_strength,
                ns.magnitude,
                ns.price_impact_5min,
                ns.price_impact_15min,
                ns.price_impact_30min,
                td.timestamp as published_at
            FROM news_sentiment ns
            JOIN securities s ON s.security_id = ns.security_id
            JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE ns.security_id = $1
            ORDER BY td.timestamp DESC
            LIMIT $2
        """, security_id, limit)
        
        return {
            "success": True,
            "symbol": symbol,
            "count": len(news),
            "news": [dict(n) for n in news]
        }
        
    except Exception as e:
        logger.error(f"Failed to get news for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/news/ingest")
async def ingest_news(
    symbol: str,
    headline: str,
    summary: str = "",
    source: str = "manual",
    url: str = ""
):
    """Manually ingest news for testing"""
    try:
        # Get IDs
        security_id = await get_security_id(symbol)
        time_id = await get_time_id(datetime.utcnow())
        
        # Analyze sentiment
        analysis = SentimentAnalyzer.analyze(headline, summary)
        
        # Store news
        news_id = await state.db_pool.fetchval("""
            INSERT INTO news_sentiment (
                security_id, time_id, headline, summary,
                source, url, sentiment_score, catalyst_strength,
                magnitude, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            RETURNING news_id
        """,
            security_id, time_id, headline, summary,
            source, url, analysis['sentiment_score'],
            analysis['catalyst_strength'], analysis['magnitude']
        )
        
        logger.info(f"Ingested news {news_id} for {symbol}")
        
        return {
            "success": True,
            "news_id": news_id,
            "symbol": symbol,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Failed to ingest news: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/catalysts")
async def get_top_catalysts(limit: int = 20):
    """Get top catalyst events across all symbols"""
    try:
        catalysts = await state.db_pool.fetch("""
            SELECT 
                s.symbol,
                ns.headline,
                ns.catalyst_strength,
                ns.sentiment_score,
                ns.price_impact_15min,
                td.timestamp as published_at
            FROM news_sentiment ns
            JOIN securities s ON s.security_id = ns.security_id
            JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE ns.catalyst_strength >= 0.5
            AND td.timestamp > NOW() - INTERVAL '24 hours'
            ORDER BY ns.catalyst_strength DESC, td.timestamp DESC
            LIMIT $1
        """, limit)
        
        return {
            "success": True,
            "count": len(catalysts),
            "catalysts": [dict(c) for c in catalysts]
        }
        
    except Exception as e:
        logger.error(f"Failed to get catalysts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/stats")
async def get_processing_stats():
    """Get detailed processing statistics"""
    try:
        # Get database stats
        db_stats = await state.db_pool.fetchrow("""
            SELECT 
                COUNT(*) as total_news,
                COUNT(CASE WHEN price_impact_5min IS NOT NULL THEN 1 END) as with_impact,
                COUNT(CASE WHEN price_impact_5min IS NULL 
                      AND created_at < NOW() - INTERVAL '5 minutes' THEN 1 END) as pending_impact,
                COUNT(DISTINCT security_id) as unique_symbols,
                COUNT(DISTINCT source) as unique_sources
            FROM news_sentiment
        """)
        
        return {
            "success": True,
            "database_stats": dict(db_stats),
            "processing_stats": state.processing_stats,
            "service_info": {
                "version": config.SERVICE_VERSION,
                "uptime": "running",
                "batch_size": config.PRICE_IMPACT_BATCH_SIZE
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "news-service:app",
        host="0.0.0.0",
        port=config.SERVICE_PORT,
        reload=False,
        log_level="info"
    )
