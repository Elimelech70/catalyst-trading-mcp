#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 5.0.2
Last Updated: 2025-10-04
Purpose: News catalyst detection with config-based ticker mapping

REVISION HISTORY:
v5.0.2 (2025-10-04) - Configuration-Based Ticker Mapping
- Moved ticker mappings to external YAML config file
- Hot-reload capability (update config without code changes)
- Better separation of concerns
- Easier maintenance and updates

v5.0.1 (2025-10-04) - NewsAPI Query Fix
- Fixed query construction to use company names

Description of Service:
Intelligence foundation for Catalyst Trading System.
Loads ticker-to-company mappings from config/ticker_mappings.yaml
Falls back to "{TICKER} stock" for unmapped symbols.
"""

from fastapi import FastAPI, HTTPException
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
import yaml
from pathlib import Path

# Initialize FastAPI
app = FastAPI(
    title="News Intelligence Service",
    version="5.0.2",
    description="News catalyst detection with config-based ticker mapping"
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
    """Format logs as JSON"""
    
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
        if hasattr(record, 'query'):
            log_data["context"]["query"] = record.query
            
        return json.dumps(log_data)

# Configure logging
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
    """Load and manage ticker-to-company mappings from config"""
    
    def __init__(self, config_path: str = "/app/config/ticker_mappings.yaml"):
        self.config_path = config_path
        self.mappings: Dict[str, str] = {}
        self.load_mappings()
    
    def load_mappings(self):
        """Load ticker mappings from YAML config file"""
        try:
            config_file = Path(self.config_path)
            
            if not config_file.exists():
                logger.warning(f"Ticker mapping file not found: {self.config_path}")
                logger.warning("Using fallback strategy for all tickers")
                self.mappings = {}
                return
            
            with open(config_file, 'r') as f:
                self.mappings = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded {len(self.mappings)} ticker mappings from config")
            logger.debug(f"Sample mappings: AAPL={self.mappings.get('AAPL')}, "
                        f"TSLA={self.mappings.get('TSLA')}, "
                        f"MSFT={self.mappings.get('MSFT')}")
            
        except Exception as e:
            logger.error(f"Failed to load ticker mappings: {e}", exc_info=True)
            logger.warning("Using fallback strategy for all tickers")
            self.mappings = {}
    
    def get_search_terms(self, symbol: str) -> str:
        """
        Get optimized search query for NewsAPI
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Company name if mapped, otherwise "{TICKER} stock"
        """
        symbol_upper = symbol.upper()
        
        # Try to get from config
        company_name = self.mappings.get(symbol_upper)
        
        if company_name:
            logger.debug(f"Ticker {symbol_upper} mapped to: '{company_name}'")
            return company_name
        else:
            # Fallback strategy
            fallback = f"{symbol_upper} stock"
            logger.debug(f"Ticker {symbol_upper} not in config, using fallback: '{fallback}'")
            return fallback
    
    def reload(self):
        """Hot-reload mappings from config file"""
        logger.info("Reloading ticker mappings from config")
        old_count = len(self.mappings)
        self.load_mappings()
        new_count = len(self.mappings)
        logger.info(f"Mappings reloaded: {old_count} → {new_count}")

# Initialize ticker mapper
ticker_mapper = TickerMapper()

# === DATA MODELS ===
class NewsSource(str, Enum):
    NEWSAPI = "newsapi"
    YAHOO = "yahoo"

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

# === STARTUP ===
@app.on_event("startup")
async def startup_event():
    logger.info("Starting News Intelligence Service v5.0.2")
    
    # Load ticker mappings from config
    ticker_mapper.load_mappings()
    
    # Initialize config
    try:
        state.config = NewsConfig(
            api_key=os.getenv("NEWS_API_KEY", "")
        )
        logger.info("Configuration validated")
    except ValueError as e:
        logger.critical(f"Config failed: {e}")
        raise
    
    # HTTP session
    state.http_session = aiohttp.ClientSession()
    logger.info("HTTP session initialized")
    
    # Database
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL required")
        
        state.db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
        logger.info("Database pool initialized")
    except Exception as e:
        logger.critical(f"Database init failed: {e}")
        raise
    
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
        "version": "5.0.2",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": "connected" if state.db_pool else "disconnected",
        "http_session": "initialized" if state.http_session else "not_initialized",
        "ticker_mappings": len(ticker_mapper.mappings)
    }

# === ADMIN ENDPOINT ===
@app.post("/admin/reload-mappings")
async def reload_ticker_mappings():
    """Hot-reload ticker mappings from config file (no restart needed)"""
    try:
        ticker_mapper.reload()
        return {
            "status": "success",
            "message": "Ticker mappings reloaded",
            "count": len(ticker_mapper.mappings),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to reload mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")

# === NEWS FETCHING ===
async def fetch_newsapi(symbol: str, hours: int) -> List[Dict]:
    """
    Fetch news from NewsAPI with config-based query optimization
    Uses ticker_mapper to get company names from config
    """
    
    if not symbol or len(symbol) > 10:
        raise ValueError(f"Invalid symbol: {symbol}")
    
    if hours <= 0 or hours > 168:
        raise ValueError(f"Invalid hours: {hours}")
    
    from_date = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    # Get search terms from config-based mapper
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
        logger.debug(f"NewsAPI query for {symbol}: '{search_query}' (last {hours}h)")
        
        async with state.http_session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            
            if resp.status == 200:
                data = await resp.json()
                articles = data.get("articles", [])
                logger.info(f"NewsAPI: {len(articles)} articles for {symbol} using query='{search_query}'")
                return articles
                
            elif resp.status == 401:
                logger.critical("NewsAPI auth failed - invalid API key")
                raise HTTPException(status_code=503, detail="Invalid API key")
                
            elif resp.status == 429:
                logger.error("NewsAPI rate limit exceeded")
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
                
            elif resp.status >= 500:
                logger.error(f"NewsAPI server error: {resp.status}")
                raise HTTPException(status_code=502, detail=f"NewsAPI error: {resp.status}")
                
            else:
                logger.warning(f"Unexpected NewsAPI status: {resp.status}")
                return []
    
    except asyncio.TimeoutError:
        logger.error(f"NewsAPI timeout for {symbol}")
        raise TimeoutError(f"Timeout for {symbol}")
    except aiohttp.ClientError as e:
        logger.error(f"NewsAPI connection error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

async def fetch_yahoo_news(symbol: str, hours: int) -> List[Dict]:
    """Fetch from Yahoo Finance RSS"""
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        
        async with state.http_session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                content = await resp.text()
                feed = feedparser.parse(content)
                
                articles = []
                cutoff = datetime.now() - timedelta(hours=hours)
                
                for entry in feed.entries:
                    published = datetime.fromisoformat(entry.get('published', datetime.now().isoformat()))
                    if published > cutoff:
                        articles.append({
                            'title': entry.get('title'),
                            'description': entry.get('summary'),
                            'url': entry.get('link'),
                            'publishedAt': entry.get('published'),
                            'source': {'name': 'Yahoo Finance'}
                        })
                
                logger.info(f"Yahoo: {len(articles)} articles for {symbol}")
                return articles
            else:
                logger.warning(f"Yahoo RSS returned {resp.status} for {symbol}")
                return []
    except Exception as e:
        logger.warning(f"Yahoo fetch failed for {symbol}: {e}")
        return []

# === API ENDPOINT ===
@app.get("/api/v1/catalysts/{symbol}")
async def get_catalysts(symbol: str, hours: int = 24, min_strength: float = 0.3):
    """Get news catalysts for symbol"""
    
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    
    logger.info(f"Fetching catalysts for {symbol} (hours={hours}, min_strength={min_strength})")
    
    all_articles = []
    
    # Fetch from NewsAPI
    try:
        newsapi_articles = await fetch_newsapi(symbol, hours)
        all_articles.extend(newsapi_articles)
    except Exception as e:
        logger.error(f"NewsAPI error for {symbol}: {e}")
    
    # Fetch from Yahoo
    try:
        yahoo_articles = await fetch_yahoo_news(symbol, hours)
        all_articles.extend(yahoo_articles)
    except Exception as e:
        logger.error(f"Yahoo error for {symbol}: {e}")
    
    # Process articles (sentiment, catalyst detection, etc.)
    # ... rest of processing logic ...
    
    return {
        "symbol": symbol,
        "articles": all_articles,
        "count": len(all_articles),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎩 Catalyst Trading System - News Service v5.0.2")
    print("=" * 60)
    print("✅ Config-based ticker mapping")
    print("✅ Hot-reload capability")
    print("✅ Easy maintenance - no code changes needed")
    print("Port: 5008")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=5008, log_level="info")