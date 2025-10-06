#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 5.1.0
Last Updated: 2025-10-06
Purpose: News catalyst detection with normalized schema v5.0

REVISION HISTORY:
v5.1.0 (2025-10-06) - Normalized Schema Migration
- Migrated to news_sentiment table with security_id FK
- Added time_dimension integration with time_id FK
- Implemented price impact tracking (5min, 15min, 30min)
- Added source reliability scoring
- Background jobs for impact calculation
- Full JOIN-based queries (no symbol VARCHAR storage)

v5.0.2 (2025-10-04) - Configuration-Based Ticker Mapping
- Moved ticker mappings to external YAML config file
- Hot-reload capability

Description of Service:
Intelligence foundation for Catalyst Trading System.
Uses normalized v5.0 schema with proper FKs.
Tracks news price impact and source reliability for ML.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
import asyncpg
import json
import os
import logging
import logging.handlers
from enum import Enum
from dataclasses import dataclass
import feedparser
from textblob import TextBlob
import yaml
from pathlib import Path

# Initialize FastAPI
app = FastAPI(
    title="News Intelligence Service",
    version="5.1.0",
    description="News catalyst detection with normalized schema v5.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === JSON LOGGING ===
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "news-service",
            "level": record.levelname,
            "message": record.getMessage(),
            "context": {
                "function": record.funcName,
                "line": record.lineno,
                "module": record.module
            }
        }
        
        if record.exc_info:
            log_data["traceback"] = self.formatException(record.exc_info)
        
        if hasattr(record, 'symbol'):
            log_data["context"]["symbol"] = record.symbol
            
        return json.dumps(log_data)

logger = logging.getLogger("news")
logger.setLevel(logging.DEBUG)

os.makedirs("/app/logs", exist_ok=True)
file_handler = logging.handlers.RotatingFileHandler(
    "/app/logs/news-service.log",
    maxBytes=10*1024*1024,
    backupCount=5
)
file_handler.setFormatter(JSONFormatter())
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(console_handler)

# === TICKER MAPPING ===
class TickerMapper:
    def __init__(self, config_path: str = "/app/config/ticker_mappings.yaml"):
        self.config_path = config_path
        self.mappings: Dict[str, str] = {}
        self.load_mappings()
    
    def load_mappings(self):
        try:
            config_file = Path(self.config_path)
            
            if not config_file.exists():
                logger.warning(f"Ticker mapping file not found: {self.config_path}")
                self.mappings = {}
                return
            
            with open(config_file, 'r') as f:
                self.mappings = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded {len(self.mappings)} ticker mappings from config")
            
        except Exception as e:
            logger.error(f"Failed to load ticker mappings: {e}", exc_info=True)
            self.mappings = {}
    
    def get_search_terms(self, symbol: str) -> str:
        symbol_upper = symbol.upper()
        company_name = self.mappings.get(symbol_upper)
        
        if company_name:
            logger.debug(f"Ticker {symbol_upper} mapped to: '{company_name}'")
            return company_name
        else:
            fallback = f"{symbol_upper} stock"
            logger.debug(f"Ticker {symbol_upper} not in config, using fallback: '{fallback}'")
            return fallback
    
    def reload(self):
        logger.info("Reloading ticker mappings from config")
        old_count = len(self.mappings)
        self.load_mappings()
        new_count = len(self.mappings)
        logger.info(f"Mappings reloaded: {old_count} → {new_count}")

ticker_mapper = TickerMapper()

# === DATA MODELS ===
class CatalystType(str, Enum):
    EARNINGS = "earnings"
    FDA_APPROVAL = "fda_approval"
    MERGER_ACQUISITION = "merger_acquisition"
    PRODUCT_LAUNCH = "product_launch"
    PARTNERSHIP = "partnership"
    REGULATORY = "regulatory"
    LAWSUIT = "lawsuit"
    MANAGEMENT_CHANGE = "management_change"
    ANALYST_UPGRADE = "analyst_upgrade"
    ANALYST_DOWNGRADE = "analyst_downgrade"
    INSIDER_TRADING = "insider_trading"
    GENERAL = "general"

class SentimentLabel(str, Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"

# === SERVICE STATE ===
@dataclass
class NewsConfig:
    api_key: str
    catalyst_keywords: Dict[str, List[str]] = None
    
    def __post_init__(self):
        if not self.api_key:
            logger.critical("NewsAPI key not configured")
            raise ValueError("NEWS_API_KEY environment variable required")
        
        if self.catalyst_keywords is None:
            self.catalyst_keywords = {
                CatalystType.EARNINGS: ["earnings", "revenue", "profit", "EPS"],
                CatalystType.FDA_APPROVAL: ["FDA", "approval", "clinical", "trial"],
                CatalystType.MERGER_ACQUISITION: ["merger", "acquisition", "buyout"],
                CatalystType.PRODUCT_LAUNCH: ["launch", "release", "unveil", "announce"],
                CatalystType.PARTNERSHIP: ["partnership", "collaboration", "agreement"],
                CatalystType.REGULATORY: ["SEC", "investigation", "probe", "compliance"],
                CatalystType.LAWSUIT: ["lawsuit", "litigation", "court", "legal"],
                CatalystType.MANAGEMENT_CHANGE: ["CEO", "CFO", "resign", "appoint"],
                CatalystType.ANALYST_UPGRADE: ["upgrade", "buy", "outperform"],
                CatalystType.ANALYST_DOWNGRADE: ["downgrade", "sell", "underperform"],
                CatalystType.INSIDER_TRADING: ["insider", "buying", "selling", "filing"]
            }

class NewsState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.config: Optional[NewsConfig] = None

state = NewsState()

# === HELPER FUNCTIONS (NORMALIZED SCHEMA) ===
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol using helper function"""
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)", symbol.upper()
        )
        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")
        return security_id
    except Exception as e:
        logger.error(f"get_security_id failed for {symbol}: {e}", exc_info=True)
        raise

async def get_time_id(timestamp: datetime) -> int:
    """Get or create time_id for timestamp using helper function"""
    try:
        time_id = await state.db_pool.fetchval(
            "SELECT get_or_create_time($1)", timestamp
        )
        if not time_id:
            raise ValueError(f"Failed to get time_id for {timestamp}")
        return time_id
    except Exception as e:
        logger.error(f"get_time_id failed for {timestamp}: {e}", exc_info=True)
        raise

# === NEWS ANALYSIS ===
def analyze_sentiment(text: str) -> tuple[float, SentimentLabel]:
    """Analyze sentiment using TextBlob"""
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity  # -1 to 1
    
    # Convert to 0-1 scale
    sentiment_score = (polarity + 1) / 2
    
    # Determine label
    if polarity >= 0.5:
        label = SentimentLabel.VERY_BULLISH
    elif polarity >= 0.1:
        label = SentimentLabel.BULLISH
    elif polarity >= -0.1:
        label = SentimentLabel.NEUTRAL
    elif polarity >= -0.5:
        label = SentimentLabel.BEARISH
    else:
        label = SentimentLabel.VERY_BEARISH
    
    return sentiment_score, label

def detect_catalyst(article: Dict, config: NewsConfig) -> tuple[Optional[CatalystType], float]:
    """Detect catalyst type and strength"""
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    
    detected_catalysts = []
    
    for catalyst_type, keywords in config.catalyst_keywords.items():
        keyword_count = sum(1 for keyword in keywords if keyword.lower() in text)
        if keyword_count > 0:
            strength = min(keyword_count / len(keywords), 1.0)
            detected_catalysts.append((catalyst_type, strength))
    
    if detected_catalysts:
        # Return strongest catalyst
        detected_catalysts.sort(key=lambda x: x[1], reverse=True)
        return detected_catalysts[0]
    
    return CatalystType.GENERAL, 0.1

# === NEWS STORAGE (NORMALIZED) ===
async def store_news_article(symbol: str, article: Dict) -> int:
    """Store news in news_sentiment table with security_id and time_id FKs"""
    try:
        # Get FKs
        security_id = await get_security_id(symbol)
        
        published_at = datetime.fromisoformat(
            article.get('publishedAt', datetime.utcnow().isoformat()).replace('Z', '+00:00')
        )
        time_id = await get_time_id(published_at)
        
        # Analyze sentiment
        sentiment_score, sentiment_label = analyze_sentiment(
            f"{article.get('title', '')} {article.get('description', '')}"
        )
        
        # Detect catalyst
        catalyst_type, catalyst_strength = detect_catalyst(article, state.config)
        
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
            article.get('title', ''),
            article.get('description'),
            article.get('url'),
            article.get('source', {}).get('name', 'unknown'),
            sentiment_score,
            sentiment_label.value,
            catalyst_type.value,
            catalyst_strength,
            0.500,  # Initial reliability score
            json.dumps(article.get('metadata', {}))
        )
        
        logger.info(f"Stored news {news_id} for {symbol} (security_id={security_id})")
        return news_id
        
    except Exception as e:
        logger.error(f"Failed to store news for {symbol}: {e}", exc_info=True)
        raise

# === PRICE IMPACT TRACKING (BACKGROUND JOB) ===
async def calculate_news_price_impact():
    """Background job: Calculate actual price impact after news events"""
    logger.info("Starting price impact calculation job")
    
    while True:
        try:
            # Find news events without price impact calculated (>5min old)
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
                LIMIT 100
            """)
            
            for event in news_events:
                if not event['price_before']:
                    continue
                
                # Get prices at different intervals after news
                prices = await state.db_pool.fetchrow("""
                    SELECT 
                        (SELECT close FROM trading_history th
                         JOIN time_dimension td ON td.time_id = th.time_id
                         WHERE th.security_id = $1 
                         AND td.timestamp >= $2 + INTERVAL '5 minutes'
                         ORDER BY td.timestamp ASC LIMIT 1) as price_5min,
                        
                        (SELECT close FROM trading_history th
                         JOIN time_dimension td ON td.time_id = th.time_id
                         WHERE th.security_id = $1 
                         AND td.timestamp >= $2 + INTERVAL '15 minutes'
                         ORDER BY td.timestamp ASC LIMIT 1) as price_15min,
                        
                        (SELECT close FROM trading_history th
                         JOIN time_dimension td ON td.time_id = th.time_id
                         WHERE th.security_id = $1 
                         AND td.timestamp >= $2 + INTERVAL '30 minutes'
                         ORDER BY td.timestamp ASC LIMIT 1) as price_30min
                """, event['security_id'], event['published_at'])
                
                # Calculate % impacts
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
                
                logger.debug(f"Updated price impact for news {event['news_id']}: "
                           f"5min={impact_5min:.2f}% if impact_5min else 'N/A'")
            
            # Wait before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Price impact calculation error: {e}", exc_info=True)
            await asyncio.sleep(60)

# === SOURCE RELIABILITY TRACKING ===
async def update_source_reliability():
    """Track which news sources accurately predict price moves"""
    logger.info("Starting source reliability update job")
    
    while True:
        try:
            await asyncio.sleep(3600)  # Run hourly
            
            # Get news with both catalyst prediction and actual impact
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
                HAVING COUNT(*) >= 10
            """)
            
            for row in sources:
                reliability = row['accuracy']
                
                await state.db_pool.execute("""
                    UPDATE news_sentiment
                    SET source_reliability_score = $1
                    WHERE source = $2
                """, reliability, row['source'])
                
                logger.info(f"Updated {row['source']} reliability: {reliability:.3f} "
                           f"({row['total_articles']} articles)")
            
        except Exception as e:
            logger.error(f"Source reliability update error: {e}", exc_info=True)

# === NEWS FETCHING ===
async def fetch_newsapi(symbol: str, hours: int) -> List[Dict]:
    """Fetch news from NewsAPI with config-based query optimization"""
    
    if not symbol or len(symbol) > 10:
        raise ValueError(f"Invalid symbol: {symbol}")
    
    from_date = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    search_query = ticker_mapper.get_search_terms(symbol)
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": search_query,
        "from": from_date,
        "apiKey": state.config.api_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100
    }
    
    try:
        async with state.http_session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            
            if resp.status == 200:
                data = await resp.json()
                articles = data.get("articles", [])
                logger.info(f"NewsAPI: {len(articles)} articles for {symbol}")
                return articles
            elif resp.status == 401:
                logger.critical("NewsAPI auth failed")
                raise HTTPException(status_code=503, detail="Invalid API key")
            elif resp.status == 429:
                logger.error("NewsAPI rate limit exceeded")
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            else:
                logger.warning(f"NewsAPI status: {resp.status}")
                return []
    
    except asyncio.TimeoutError:
        logger.error(f"NewsAPI timeout for {symbol}")
        raise TimeoutError(f"Timeout for {symbol}")

# === STARTUP ===
@app.on_event("startup")
async def startup_event():
    logger.info("Starting News Intelligence Service v5.1.0 (Normalized Schema)")
    
    ticker_mapper.load_mappings()
    
    try:
        state.config = NewsConfig(api_key=os.getenv("NEWS_API_KEY", ""))
        logger.info("Configuration validated")
    except ValueError as e:
        logger.critical(f"Config failed: {e}")
        raise
    
    state.http_session = aiohttp.ClientSession()
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL required")
        
        state.db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
        logger.info("Database pool initialized")
    except Exception as e:
        logger.critical(f"Database init failed: {e}")
        raise
    
    # Start background jobs
    asyncio.create_task(calculate_news_price_impact())
    asyncio.create_task(update_source_reliability())
    logger.info("Background jobs started")
    
    logger.info("News service ready")

@app.on_event("shutdown")
async def shutdown_event():
    if state.http_session:
        await state.http_session.close()
    if state.db_pool:
        await state.db_pool.close()

# === HEALTH CHECK ===
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "news",
        "version": "5.1.0",
        "schema": "v5.0 normalized",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": "connected" if state.db_pool else "disconnected"
    }

# === API ENDPOINT ===
@app.get("/api/v1/catalysts/{symbol}")
async def get_catalysts(symbol: str, hours: int = 24, min_strength: float = 0.3):
    """Get news catalysts for symbol (uses normalized schema with JOINs)"""
    
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    
    logger.info(f"Fetching catalysts for {symbol} (hours={hours})")
    
    # Fetch fresh news
    all_articles = []
    try:
        newsapi_articles = await fetch_newsapi(symbol, hours)
        all_articles.extend(newsapi_articles)
    except Exception as e:
        logger.error(f"NewsAPI error for {symbol}: {e}")
    
    # Store articles with normalized schema
    for article in all_articles:
        try:
            await store_news_article(symbol, article)
        except Exception as e:
            logger.error(f"Failed to store article: {e}")
    
    # Query stored news with JOINs (normalized schema)
    news_records = await state.db_pool.fetch("""
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
        AND td.timestamp >= NOW() - INTERVAL '1 day' * $2 / 24
        AND ns.catalyst_strength >= $3
        ORDER BY td.timestamp DESC
        LIMIT 100
    """, symbol.upper(), hours, min_strength)
    
    return {
        "symbol": symbol,
        "catalysts": [dict(r) for r in news_records],
        "count": len(news_records),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎩 Catalyst Trading System - News Service v5.1.0")
    print("=" * 60)
    print("✅ Normalized schema v5.0 with FKs")
    print("✅ Price impact tracking")
    print("✅ Source reliability scoring")
    print("Port: 5008")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=5008, log_level="info")
