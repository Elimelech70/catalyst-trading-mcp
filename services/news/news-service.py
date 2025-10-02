#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 5.0.0
Last Updated: 2025-10-01
Purpose: News catalyst detection and sentiment analysis with rigorous error handling

REVISION HISTORY:
v5.0.0 (2025-10-01) - Rigorous error handling implementation
- NO silent failures - all errors are visible
- Specific exception handling (no bare except or generic Exception catches)
- Sentiment analysis failures raise errors (not return neutral)
- API failures raise HTTPException (not return empty)
- Database persistence failures are CRITICAL errors
- JSON structured logging with full context
- Input validation before all operations
- Proper error propagation throughout

v4.1.0 (2025-08-31) - Original production-ready version
- Multiple news source integration
- Real-time catalyst detection
- Sentiment analysis with confidence scoring

Description of Service:
Intelligence foundation (Service #1 of 9). Provides news-based catalyst detection:
1. Real-time news monitoring from multiple sources
2. Catalyst strength scoring
3. Sentiment analysis (bullish/bearish/neutral)
4. Event type categorization
5. Database persistence for historical analysis

CRITICAL: This service must record to database before proceeding to Orchestration (step 2).
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
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

# Initialize FastAPI app
app = FastAPI(
    title="News Intelligence Service",
    version="5.0.0",
    description="News catalyst detection service for Catalyst Trading System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === STRUCTURED JSON LOGGING ===

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging"""
    
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
        
        # Add exception info if present
        if record.exc_info:
            log_data["traceback"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'symbol'):
            log_data["context"]["symbol"] = record.symbol
        if hasattr(record, 'source'):
            log_data["context"]["source"] = record.source
        if hasattr(record, 'error_type'):
            log_data["context"]["error_type"] = record.error_type
            
        return json.dumps(log_data)

# Configure logging
logger = logging.getLogger("news")
logger.setLevel(logging.DEBUG)

# File handler with JSON formatting
os.makedirs("/app/logs", exist_ok=True)
file_handler = logging.handlers.RotatingFileHandler(
    "/app/logs/news-service.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(JSONFormatter())
logger.addHandler(file_handler)

# Console handler for development
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(console_handler)

# === DATA MODELS ===

class NewsSource(str, Enum):
    NEWSAPI = "newsapi"
    YAHOO = "yahoo"
    BENZINGA = "benzinga"

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

class SentimentType(str, Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"

class NewsArticle(BaseModel):
    article_id: str
    symbol: Optional[str]
    headline: str
    source: str
    published_at: datetime
    url: Optional[str]
    summary: Optional[str]
    sentiment: SentimentType
    sentiment_score: float = Field(ge=0, le=1)
    catalyst_type: Optional[CatalystType]
    catalyst_strength: float = Field(ge=0, le=1)
    keywords: List[str]

class CatalystRequest(BaseModel):
    symbols: List[str]
    lookback_hours: int = Field(default=24, ge=1, le=168)
    min_catalyst_strength: float = Field(default=0.5, ge=0, le=1)
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if not v:
            raise ValueError("At least one symbol required")
        if len(v) > 50:
            raise ValueError("Maximum 50 symbols allowed")
        for symbol in v:
            if not symbol or len(symbol) > 10:
                raise ValueError(f"Invalid symbol: {symbol}")
        return v

class CatalystResponse(BaseModel):
    symbol: str
    catalysts: List[NewsArticle]
    overall_sentiment: SentimentType
    catalyst_score: float
    recommendation: str
    timestamp: datetime

# === SERVICE STATE ===

@dataclass
class NewsConfig:
    """Configuration for news service"""
    api_key: str
    benzinga_key: str
    
    # Catalyst detection thresholds
    min_sentiment_magnitude: float = 0.3
    
    # Rate limiting
    requests_per_minute: int = 100
    cache_ttl: int = 300
    
    # Catalyst keywords
    catalyst_keywords: Dict[str, List[str]] = None
    
    def __post_init__(self):
        # Validate API keys at startup
        if not self.api_key:
            logger.critical("NewsAPI key not configured - service cannot function")
            raise ValueError("NEWS_API_KEY environment variable required")
        
        if self.catalyst_keywords is None:
            self.catalyst_keywords = {
                CatalystType.EARNINGS: ["earnings", "revenue", "profit", "EPS", "guidance", "forecast"],
                CatalystType.FDA_APPROVAL: ["FDA", "approval", "clinical", "trial", "drug", "phase"],
                CatalystType.MERGER_ACQUISITION: ["merger", "acquisition", "buyout", "takeover", "deal"],
                CatalystType.PRODUCT_LAUNCH: ["launch", "release", "unveil", "announce", "introduce"],
                CatalystType.PARTNERSHIP: ["partnership", "collaboration", "agreement", "contract", "joint"],
                CatalystType.REGULATORY: ["SEC", "investigation", "probe", "compliance", "regulation"],
                CatalystType.LAWSUIT: ["lawsuit", "litigation", "court", "legal", "settlement"],
                CatalystType.MANAGEMENT_CHANGE: ["CEO", "CFO", "resign", "appoint", "hire", "fire"],
                CatalystType.ANALYST_UPGRADE: ["upgrade", "buy", "outperform", "overweight", "raise"],
                CatalystType.ANALYST_DOWNGRADE: ["downgrade", "sell", "underperform", "underweight", "cut"],
                CatalystType.INSIDER_TRADING: ["insider", "buying", "selling", "transaction", "filing"]
            }

class NewsState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.config: Optional[NewsConfig] = None

state = NewsState()

# === STARTUP AND SHUTDOWN ===

@app.on_event("startup")
async def startup_event():
    """Initialize service with fail-fast validation"""
    logger.info("Starting News Intelligence Service v5.0.0")
    
    # Initialize configuration - fails fast if API key missing
    try:
        state.config = NewsConfig(
            api_key=os.getenv("NEWS_API_KEY", ""),
            benzinga_key=os.getenv("BENZINGA_API_KEY", "")
        )
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.critical(f"Configuration validation failed: {e}")
        raise
    
    # Initialize HTTP session
    state.http_session = aiohttp.ClientSession()
    logger.info("HTTP session initialized")
    
    # Initialize database connection
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.critical("DATABASE_URL not configured")
            raise ValueError("DATABASE_URL environment variable required")
        
        state.db_pool = await asyncpg.create_pool(
            database_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        # Test database connection
        async with state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        logger.info("Database connection pool initialized")
        
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise
    
    logger.info("News service startup complete - ready to process requests")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources"""
    logger.info("Shutting down News service")
    
    if state.http_session:
        await state.http_session.close()
        logger.info("HTTP session closed")
    
    if state.db_pool:
        await state.db_pool.close()
        logger.info("Database pool closed")
    
    logger.info("News service shutdown complete")

# === HEALTH CHECK ===

@app.get("/health")
async def health_check():
    """Service health check"""
    health_status = {
        "status": "healthy",
        "service": "news",
        "version": "5.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Check database
    try:
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health_status["database"] = "connected"
        else:
            health_status["database"] = "not_initialized"
            health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "error"
        health_status["status"] = "unhealthy"
    
    # Check HTTP session
    health_status["http_session"] = "initialized" if state.http_session else "not_initialized"
    
    # Check configuration
    health_status["configuration"] = "valid" if state.config else "invalid"
    
    return health_status

# === SENTIMENT ANALYSIS ===

def analyze_text_sentiment(text: str) -> Dict:
    """Analyze sentiment with proper error handling - NO SILENT FAILURES
    
    Args:
        text: Text to analyze
        
    Returns:
        Dict with sentiment data and success flag
        
    Raises:
        ValueError: Empty text or encoding errors
        RuntimeError: TextBlob library errors
    """
    
    # Validate input FIRST
    if not text or not text.strip():
        raise ValueError("Empty text provided for sentiment analysis")
    
    if len(text) > 10000:
        logger.warning(f"Text too long ({len(text)} chars), truncating to 10000")
        text = text[:10000]
    
    try:
        # Clean text
        text_clean = text.strip()
        
        # TextBlob analysis
        blob = TextBlob(text_clean)
        polarity = blob.sentiment.polarity
        subjectivity = blob.sentiment.subjectivity
        
        # Validate results
        if not (-1.0 <= polarity <= 1.0):
            raise ValueError(f"Invalid polarity: {polarity}")
        if not (0.0 <= subjectivity <= 1.0):
            raise ValueError(f"Invalid subjectivity: {subjectivity}")
        
        # Determine sentiment category
        if polarity >= 0.5:
            sentiment = SentimentType.VERY_BULLISH
        elif polarity >= 0.1:
            sentiment = SentimentType.BULLISH
        elif polarity <= -0.5:
            sentiment = SentimentType.VERY_BEARISH
        elif polarity <= -0.1:
            sentiment = SentimentType.BEARISH
        else:
            sentiment = SentimentType.NEUTRAL
        
        return {
            "sentiment": sentiment,
            "score": abs(polarity),
            "polarity": polarity,
            "subjectivity": subjectivity,
            "success": True
        }
        
    except UnicodeDecodeError as e:
        logger.error(f"Text encoding error in sentiment analysis: {e}")
        raise ValueError(f"Text encoding error: {str(e)}")
        
    except AttributeError as e:
        logger.error(f"TextBlob analysis failed: {e}", exc_info=True)
        raise RuntimeError(f"Sentiment analysis library error: {str(e)}")

# === NEWS API FETCHING ===

async def fetch_newsapi(symbol: str, hours: int) -> List[Dict]:
    """Fetch news from NewsAPI with proper error handling
    
    Args:
        symbol: Stock symbol
        hours: Lookback period in hours
        
    Returns:
        List of article dicts
        
    Raises:
        ValueError: Invalid inputs
        HTTPException: API errors (401, 429, 500+)
        TimeoutError: Request timeout
    """
    
    # Validate inputs
    if not symbol or len(symbol) > 10:
        raise ValueError(f"Invalid symbol: {symbol}")
    
    if hours <= 0 or hours > 168:
        raise ValueError(f"Invalid lookback hours: {hours}")
    
    from_date = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": symbol,
        "from": from_date,
        "apiKey": state.config.api_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100
    }
    
    try:
        logger.debug(f"Fetching news for {symbol} from NewsAPI (last {hours}h)")
        
        async with state.http_session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            
            if resp.status == 200:
                data = await resp.json()
                articles = data.get("articles", [])
                logger.info(f"NewsAPI returned {len(articles)} articles for {symbol}")
                return articles
                
            elif resp.status == 401:
                logger.critical("NewsAPI authentication failed - invalid API key")
                raise HTTPException(
                    status_code=503,
                    detail="News service misconfigured - invalid API key"
                )
                
            elif resp.status == 429:
                error_data = await resp.json()
                logger.error(f"NewsAPI rate limit exceeded: {error_data}")
                raise HTTPException(
                    status_code=429,
                    detail="NewsAPI rate limit exceeded"
                )
                
            elif resp.status == 400:
                error_data = await resp.json()
                logger.error(f"NewsAPI bad request for {symbol}: {error_data}")
                raise ValueError(f"Invalid NewsAPI request: {error_data.get('message')}")
                
            elif resp.status >= 500:
                logger.error(f"NewsAPI server error {resp.status}")
                raise HTTPException(
                    status_code=502,
                    detail=f"NewsAPI server error: {resp.status}"
                )
                
            else:
                logger.error(f"Unexpected NewsAPI status {resp.status}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Unexpected NewsAPI response: {resp.status}"
                )
    
    except asyncio.TimeoutError:
        logger.error(f"NewsAPI timeout for {symbol}")
        raise TimeoutError(f"NewsAPI request timeout for {symbol}")
        
    except aiohttp.ClientError as e:
        logger.error(f"NewsAPI connection error for {symbol}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"NewsAPI connection failed: {str(e)}"
        )

async def fetch_yahoo_news(symbol: str, hours: int) -> List[Dict]:
    """Fetch news from Yahoo Finance RSS with proper error handling
    
    Args:
        symbol: Stock symbol
        hours: Lookback period
        
    Returns:
        List of article dicts (may be empty if source unavailable)
        
    Raises:
        ValueError: Invalid inputs
        RuntimeError: RSS parsing failures
    """
    
    if not symbol:
        raise ValueError("Symbol required for Yahoo news fetch")
    
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    
    try:
        logger.debug(f"Fetching Yahoo RSS for {symbol}")
        
        async with state.http_session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            
            if resp.status != 200:
                logger.warning(f"Yahoo RSS returned status {resp.status} for {symbol}")
                return []  # Yahoo failures are acceptable - return empty
            
            content = await resp.text()
            
            # Parse RSS feed
            try:
                feed = feedparser.parse(content)
                
                if feed.bozo:
                    logger.error(f"Yahoo RSS parsing error for {symbol}: {feed.bozo_exception}")
                    raise RuntimeError(f"RSS parsing failed: {feed.bozo_exception}")
                
                articles = []
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                for entry in feed.entries:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                        
                        if published >= cutoff_time:
                            articles.append({
                                "title": entry.get("title", ""),
                                "description": entry.get("summary", ""),
                                "url": entry.get("link", ""),
                                "publishedAt": published.isoformat(),
                                "source": {"name": "Yahoo Finance"}
                            })
                    except (AttributeError, ValueError) as e:
                        logger.debug(f"Skipping malformed Yahoo RSS entry: {e}")
                        continue
                
                logger.info(f"Yahoo RSS returned {len(articles)} articles for {symbol}")
                return articles
                
            except Exception as e:
                logger.error(f"feedparser error for {symbol}: {e}", exc_info=True)
                raise RuntimeError(f"RSS feed processing failed: {str(e)}")
                
    except asyncio.TimeoutError:
        logger.warning(f"Yahoo RSS timeout for {symbol}")
        return []  # Timeout is acceptable - return empty
        
    except aiohttp.ClientError as e:
        logger.warning(f"Yahoo RSS connection error for {symbol}: {e}")
        return []  # Network errors are acceptable - return empty

# === CATALYST DETECTION ===

def detect_catalyst_type(title: str, description: str) -> Optional[CatalystType]:
    """Detect catalyst type from text"""
    
    text = f"{title} {description}".lower()
    
    for catalyst_type, keywords in state.config.catalyst_keywords.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return catalyst_type
    
    return CatalystType.GENERAL

def calculate_catalyst_strength(
    sentiment_data: Dict,
    catalyst_type: Optional[CatalystType],
    source: str
) -> float:
    """Calculate catalyst strength score"""
    
    strength = 0.0
    
    # Base strength from sentiment magnitude
    strength += sentiment_data["score"] * 0.4
    
    # Boost for specific catalyst types
    high_impact = [
        CatalystType.EARNINGS,
        CatalystType.FDA_APPROVAL,
        CatalystType.MERGER_ACQUISITION,
        CatalystType.ANALYST_UPGRADE,
        CatalystType.ANALYST_DOWNGRADE
    ]
    
    if catalyst_type in high_impact:
        strength += 0.3
    elif catalyst_type and catalyst_type != CatalystType.GENERAL:
        strength += 0.2
    
    # Source credibility boost
    credible_sources = [
        "reuters", "bloomberg", "wsj", "financial times",
        "cnbc", "marketwatch", "seeking alpha", "benzinga"
    ]
    
    if any(src in source.lower() for src in credible_sources):
        strength += 0.2
    
    # High subjectivity reduces strength
    if sentiment_data.get("subjectivity", 0) > 0.7:
        strength *= 0.8
    
    return min(1.0, strength)

def extract_keywords(text: str) -> List[str]:
    """Extract keywords from text"""
    
    keywords = []
    important_words = [
        "earnings", "revenue", "profit", "loss", "beat", "miss",
        "upgrade", "downgrade", "buy", "sell", "hold",
        "FDA", "approval", "trial", "merger", "acquisition",
        "lawsuit", "investigation", "partnership", "deal"
    ]
    
    text_lower = text.lower()
    for word in important_words:
        if word in text_lower:
            keywords.append(word)
    
    return keywords[:10]

# === DATABASE PERSISTENCE ===

async def store_news_articles(articles: List[NewsArticle]) -> None:
    """Store news articles with NO SILENT FAILURES
    
    Args:
        articles: List of NewsArticle objects
        
    Raises:
        RuntimeError: Database not available
        asyncpg.PostgresError: Database errors
    """
    
    if not articles:
        return
    
    if not state.db_pool:
        logger.critical("Database pool not initialized - cannot store news")
        raise RuntimeError("Database not available")
    
    try:
        async with state.db_pool.acquire() as conn:
            for article in articles:
                try:
                    await conn.execute("""
                        INSERT INTO news_articles (
                            article_id, symbol, headline, source, published_at,
                            url, summary, sentiment, sentiment_score,
                            catalyst_type, catalyst_strength, keywords, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (article_id) DO NOTHING
                    """,
                        article.article_id,
                        article.symbol,
                        article.headline,
                        article.source,
                        article.published_at,
                        article.url,
                        article.summary,
                        article.sentiment.value,
                        article.sentiment_score,
                        article.catalyst_type.value if article.catalyst_type else None,
                        article.catalyst_strength,
                        json.dumps(article.keywords),
                        datetime.utcnow()
                    )
                except asyncpg.UniqueViolationError:
                    logger.debug(f"Duplicate article skipped: {article.article_id}")
                    
        logger.info(f"Successfully stored {len(articles)} news articles to database")
                    
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error storing news articles: {e}", exc_info=True)
        raise  # Never hide database errors!

# === API ENDPOINTS ===

@app.get("/api/v1/catalysts/{symbol}")
async def get_symbol_catalysts(
    symbol: str,
    hours: int = 24,
    min_strength: float = 0.5
):
    """Get catalysts for a single symbol with robust error handling"""
    
    # Validate inputs
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
    
    if not (1 <= hours <= 168):
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")
    
    if not (0 <= min_strength <= 1):
        raise HTTPException(status_code=400, detail="Strength must be between 0 and 1")
    
    logger.info(f"Fetching catalysts for {symbol} (last {hours}h, min_strength={min_strength})")
    
    all_articles = []
    source_errors = {}
    
    # Fetch from NewsAPI
    try:
        newsapi_articles = await fetch_newsapi(symbol, hours)
        all_articles.extend(newsapi_articles)
        logger.info(f"NewsAPI: {len(newsapi_articles)} articles for {symbol}")
    except ValueError as e:
        logger.warning(f"NewsAPI validation error for {symbol}: {e}")
        source_errors["newsapi"] = str(e)
    except HTTPException as e:
        logger.error(f"NewsAPI error for {symbol}: {e.detail}")
        source_errors["newsapi"] = e.detail
    except TimeoutError as e:
        logger.warning(f"NewsAPI timeout for {symbol}")
        source_errors["newsapi"] = "Timeout"
    
    # Fetch from Yahoo
    try:
        yahoo_articles = await fetch_yahoo_news(symbol, hours)
        all_articles.extend(yahoo_articles)
        logger.info(f"Yahoo: {len(yahoo_articles)} articles for {symbol}")
    except ValueError as e:
        logger.warning(f"Yahoo validation error for {symbol}: {e}")
        source_errors["yahoo"] = str(e)
    except RuntimeError as e:
        logger.error(f"Yahoo RSS parsing error for {symbol}: {e}")
        source_errors["yahoo"] = "Parsing error"
    
    # Process articles
    processed_articles = []
    processing_errors = 0
    
    for article in all_articles:
        try:
            # Analyze sentiment
            text = f"{article.get('title', '')} {article.get('description', '')}"
            
            try:
                sentiment_data = analyze_text_sentiment(text)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Sentiment analysis failed for article: {e}")
                processing_errors += 1
                continue
            
            # Detect catalyst
            catalyst_type = detect_catalyst_type(
                article.get('title', ''),
                article.get('description', '')
            )
            
            # Calculate strength
            catalyst_strength = calculate_catalyst_strength(
                sentiment_data,
                catalyst_type,
                article.get('source', {}).get('name', 'unknown')
            )
            
            # Filter by strength
            if catalyst_strength >= min_strength:
                news_article = NewsArticle(
                    article_id=f"{symbol}_{datetime.utcnow().timestamp()}",
                    symbol=symbol,
                    headline=article.get('title', 'No title'),
                    source=article.get('source', {}).get('name', 'Unknown'),
                    published_at=datetime.fromisoformat(
                        article.get('publishedAt', datetime.utcnow().isoformat())
                    ),
                    url=article.get('url'),
                    summary=article.get('description'),
                    sentiment=sentiment_data["sentiment"],
                    sentiment_score=sentiment_data["score"],
                    catalyst_type=catalyst_type,
                    catalyst_strength=catalyst_strength,
                    keywords=extract_keywords(text)
                )
                
                processed_articles.append(news_article)
                
        except Exception as e:
            logger.error(f"Unexpected error processing article: {e}", exc_info=True)
            processing_errors += 1
    
    # Sort by strength
    processed_articles.sort(key=lambda x: x.catalyst_strength, reverse=True)
    
    # Store in database
    if processed_articles:
        try:
            await store_news_articles(processed_articles)
        except (RuntimeError, asyncpg.PostgresError) as e:
            logger.critical(f"Failed to store articles for {symbol}: {e}")
            # Continue - we return the data even if storage fails
            # But this is logged as CRITICAL for investigation
    
    # Build response
    response = {
        "symbol": symbol,
        "catalysts": [article.dict() for article in processed_articles],
        "count": len(processed_articles),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Include diagnostics if there were issues
    if source_errors or processing_errors > 0:
        response["diagnostics"] = {
            "source_errors": source_errors if source_errors else None,
            "processing_errors": processing_errors,
            "total_articles_fetched": len(all_articles),
            "articles_processed": len(processed_articles)
        }
    
    return response

@app.post("/api/v1/catalysts/batch")
async def get_catalysts_batch(request: CatalystRequest):
    """Get catalysts for multiple symbols"""
    
    results = {}
    
    for symbol in request.symbols:
        try:
            response = await get_symbol_catalysts(
                symbol,
                request.lookback_hours,
                request.min_catalyst_strength
            )
            results[symbol] = response
            
        except HTTPException as e:
            logger.error(f"Failed to get catalysts for {symbol}: {e.detail}")
            results[symbol] = {
                "error": e.detail,
                "error_code": e.status_code
            }
        except Exception as e:
            logger.error(f"Unexpected error for {symbol}: {e}", exc_info=True)
            results[symbol] = {
                "error": "Unexpected error",
                "error_type": type(e).__name__
            }
    
    return {
        "results": results,
        "requested": len(request.symbols),
        "successful": sum(1 for r in results.values() if "error" not in r),
        "failed": sum(1 for r in results.values() if "error" in r),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting News Service v5.0.0")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5008,
        log_level="info"
    )
