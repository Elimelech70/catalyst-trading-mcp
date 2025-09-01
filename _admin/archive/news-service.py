#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 3.0.1
Last Updated: 2025-08-18
Purpose: MCP-enabled news collection and intelligence service

REVISION HISTORY:
v3.0.1 (2025-08-18) - Fixed port and database imports
- Changed port from 5108 to 5008
- Fixed database_utils imports
- Added missing database functions
- Corrected MCP implementation

v3.0.0 (2024-12-30) - Complete MCP migration
- Transformed from REST to MCP protocol
- News data exposed as resources
- Collection operations as tools
- Real-time news event streaming
- Claude-optimized data access

Description of Service:
This MCP server collects news from multiple sources and provides
intelligent access to news data for trading decisions.
"""

import os
import json
import time
import logging
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
import structlog
from mcp import MCPServer, MCPRequest, MCPResponse, ResourceParams, ToolParams
from mcp.transport import WebSocketTransport, StdioTransport
import aiohttp
import feedparser
import redis.asyncio as redis
import psycopg2.extras

# Import database utilities - only what's actually available
from database_utils import (
    get_db_connection,
    health_check,
    log_workflow_step
)


class NewsMCPServer:
    """MCP Server for news collection and intelligence"""
    
    def __init__(self):
        self.server = MCPServer("news-intelligence")
        self.logger = structlog.get_logger().bind(service="news_mcp")
        
        # API Keys from environment
        self.api_keys = {
            'newsapi': os.getenv('NEWSAPI_KEY', ''),
            'alphavantage': os.getenv('ALPHAVANTAGE_KEY', ''),
            'finnhub': os.getenv('FINNHUB_KEY', '')
        }
        
        # RSS feeds with tier classification
        self.rss_feeds = {
            'marketwatch': {
                'url': 'https://feeds.marketwatch.com/marketwatch/topstories/',
                'tier': 1
            },
            'yahoo_finance': {
                'url': 'https://finance.yahoo.com/rss/',
                'tier': 1
            },
            'seeking_alpha': {
                'url': 'https://seekingalpha.com/feed.xml',
                'tier': 2
            }
        }
        
        # Collection configuration
        self.collection_config = {
            'max_articles_per_source': int(os.getenv('MAX_ARTICLES_PER_SOURCE', '20')),
            'collection_timeout': int(os.getenv('COLLECTION_TIMEOUT', '30')),
            'concurrent_sources': int(os.getenv('CONCURRENT_SOURCES', '3')),
            'cache_ttl': int(os.getenv('NEWS_CACHE_TTL', '300'))
        }
        
        # Initialize Redis client asynchronously
        self.redis_client = None
        
        # Register resources and tools
        self._register_resources()
        self._register_tools()
        self._register_events()
        
        self.logger.info("News MCP Server initialized", version="3.0.1")
        
    async def _init_redis(self):
        """Initialize Redis client"""
        if not self.redis_client:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            redis_password = os.getenv('REDIS_PASSWORD')
            
            if redis_password and 'localhost' in redis_url:
                # Add password to URL
                redis_url = f'redis://:{redis_password}@localhost:6379/0'
                
            self.redis_client = await redis.from_url(redis_url, decode_responses=True)
    
    # Database helper functions that were missing
    def get_recent_news(self, symbol: Optional[str] = None, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent news from database"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT news_id, symbol, headline, source, 
                           published_timestamp, content_snippet, url,
                           is_pre_market, market_state, headline_keywords,
                           mentioned_tickers, source_tier, metadata
                    FROM news_raw
                    WHERE published_timestamp > CURRENT_TIMESTAMP - INTERVAL %s
                """
                params = [f'{hours} hours']
                
                if symbol:
                    query += " AND symbol = %s"
                    params.append(symbol)
                
                query += " ORDER BY published_timestamp DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                
                news_items = []
                for row in cur.fetchall():
                    item = dict(row)
                    # Convert datetime to string for JSON serialization
                    if item.get('published_timestamp'):
                        item['published_timestamp'] = item['published_timestamp'].isoformat()
                    news_items.append(item)
                
                return news_items
    
    def insert_news_article(self, article: Dict) -> Optional[str]:
        """Insert news article into database"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        INSERT INTO news_raw (
                            news_id, symbol, headline, source,
                            published_timestamp, content_snippet, url,
                            is_pre_market, market_state, headline_keywords,
                            mentioned_tickers, source_tier, metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (news_id) DO NOTHING
                        RETURNING news_id
                    """, (
                        article['news_id'],
                        article.get('symbol'),
                        article['headline'],
                        article['source'],
                        article['published_timestamp'],
                        article.get('content_snippet'),
                        article.get('url'),
                        article.get('is_pre_market', False),
                        article.get('market_state', 'unknown'),
                        article.get('headline_keywords', []),
                        article.get('mentioned_tickers', []),
                        article.get('source_tier', 5),
                        json.dumps(article.get('metadata', {}))
                    ))
                    
                    result = cur.fetchone()
                    return result['news_id'] if result else None
                    
                except Exception as e:
                    self.logger.error(f"Error inserting news article", error=str(e))
                    conn.rollback()
                    raise
    
    def _register_resources(self):
        """Register data resources"""
        
        @self.server.resource("news/raw")
        async def get_raw_news(params: ResourceParams) -> MCPResponse:
            """Access raw news data"""
            filters = params.get("filters", {})
            since = filters.get('since')
            limit = filters.get('limit', 100)
            symbol = filters.get('symbol')
            source_tier = filters.get('source_tier')
            
            # Query database
            news_articles = self.get_recent_news(
                symbol=symbol,
                hours=24 if not since else None,
                limit=limit
            )
            
            return MCPResponse(
                resource_type="news_collection",
                data=news_articles,
                metadata={
                    "count": len(news_articles),
                    "last_updated": datetime.now().isoformat()
                }
            )
        
        @self.server.resource("news/by-symbol/{symbol}")
        async def get_news_by_symbol(params: ResourceParams) -> MCPResponse:
            """Get news for specific symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "24h")
            
            # Convert timeframe to hours
            hours_map = {
                "1h": 1, "4h": 4, "24h": 24, "7d": 168, "30d": 720
            }
            hours = hours_map.get(timeframe, 24)
            
            news_articles = self.get_recent_news(symbol=symbol, hours=hours)
            
            # Calculate sentiment and other analytics
            sentiment = self._analyze_news_sentiment(news_articles)
            
            return MCPResponse(
                resource_type="symbol_news",
                data={
                    'symbol': symbol,
                    'articles': news_articles,
                    'sentiment': sentiment,
                    'timeframe': timeframe
                }
            )
        
        @self.server.resource("news/catalysts/active")
        async def get_active_catalysts(params: ResourceParams) -> MCPResponse:
            """Get news with active catalysts"""
            min_score = params.get("min_catalyst_score", 50)
            limit = params.get("limit", 50)
            
            # Query for high-catalyst news
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT ON (symbol) *
                        FROM news_raw
                        WHERE published_timestamp > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                        AND source_tier <= 3
                        AND (
                            headline_keywords @> ARRAY['earnings']::text[] OR
                            headline_keywords @> ARRAY['fda']::text[] OR
                            headline_keywords @> ARRAY['merger']::text[] OR
                            headline_keywords @> ARRAY['guidance']::text[]
                        )
                        ORDER BY symbol, published_timestamp DESC
                        LIMIT %s
                    """, (limit,))
                    
                    catalysts = []
                    for row in cur.fetchall():
                        catalyst = dict(row)
                        if catalyst.get('published_timestamp'):
                            catalyst['published_timestamp'] = catalyst['published_timestamp'].isoformat()
                        catalysts.append(catalyst)
            
            return MCPResponse(
                resource_type="catalyst_collection",
                data=catalysts,
                metadata={"active_catalysts": len(catalysts)}
            )
        
        @self.server.resource("news/sources/metrics")
        async def get_source_metrics(params: ResourceParams) -> MCPResponse:
            """Get news source reliability metrics"""
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT source, source_tier, 
                               COUNT(*) as article_count,
                               AVG(CASE WHEN is_pre_market THEN 1 ELSE 0 END) as premarket_ratio
                        FROM news_raw
                        WHERE published_timestamp > CURRENT_TIMESTAMP - INTERVAL '7 days'
                        GROUP BY source, source_tier
                        ORDER BY source_tier, article_count DESC
                    """)
                    
                    metrics = []
                    for row in cur.fetchall():
                        metrics.append(dict(row))
            
            return MCPResponse(
                resource_type="source_metrics",
                data=metrics
            )
        
        @self.server.resource("news/trending")
        async def get_trending_news(params: ResourceParams) -> MCPResponse:
            """Get trending news stories"""
            hours = params.get("hours", 4)
            limit = params.get("limit", 20)
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT symbol, 
                               COUNT(*) as mention_count,
                               MIN(published_timestamp) as first_seen,
                               MAX(published_timestamp) as last_seen,
                               array_agg(DISTINCT source ORDER BY source) as sources
                        FROM news_raw
                        WHERE published_timestamp > CURRENT_TIMESTAMP - INTERVAL %s
                        AND symbol IS NOT NULL
                        GROUP BY symbol
                        HAVING COUNT(*) >= 2
                        ORDER BY mention_count DESC, MAX(published_timestamp) DESC
                        LIMIT %s
                    """, (f'{hours} hours', limit))
                    
                    trending = []
                    for row in cur.fetchall():
                        trend = dict(row)
                        if trend.get('first_seen'):
                            trend['first_seen'] = trend['first_seen'].isoformat()
                        if trend.get('last_seen'):
                            trend['last_seen'] = trend['last_seen'].isoformat()
                        trending.append(trend)
            
            return MCPResponse(
                resource_type="trending_news",
                data=trending
            )
    
    def _register_tools(self):
        """Register callable tools"""
        
        @self.server.tool("collect_news")
        async def collect_news(params: ToolParams) -> MCPResponse:
            """Trigger news collection"""
            sources = params.get("sources", ["all"])
            mode = params.get("mode", "normal")
            symbols = params.get("symbols", None)
            cycle_id = params.get("cycle_id")
            
            try:
                # Log start
                if cycle_id:
                    log_workflow_step(cycle_id, 'news_collection', 'started', 
                                    sources=sources, symbols=symbols)
                
                # Initialize Redis if needed
                await self._init_redis()
                
                # Collect from sources
                results = await self._collect_all_news(symbols, sources)
                
                # Log completion
                if cycle_id:
                    log_workflow_step(cycle_id, 'news_collection', 'completed',
                                    articles_collected=results["articles_collected"],
                                    articles_saved=results["articles_saved"])
                
                return MCPResponse(
                    success=True,
                    data={
                        "collected": results["articles_collected"],
                        "new": results["articles_saved"],
                        "duplicates": results["duplicates"],
                        "sources": results["sources"],
                        "duration": results["execution_time"]
                    },
                    metadata={"mode": mode}
                )
            except Exception as e:
                if cycle_id:
                    log_workflow_step(cycle_id, 'news_collection', 'failed', error=str(e))
                    
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("analyze_sentiment")
        async def analyze_sentiment(params: ToolParams) -> MCPResponse:
            """Analyze news sentiment for symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "24h")
            
            try:
                # Get news for symbol
                hours_map = {"1h": 1, "4h": 4, "24h": 24, "7d": 168}
                hours = hours_map.get(timeframe, 24)
                
                news_articles = self.get_recent_news(symbol=symbol, hours=hours)
                sentiment = self._analyze_news_sentiment(news_articles)
                
                return MCPResponse(
                    success=True,
                    data=sentiment,
                    confidence=sentiment["confidence"]
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("track_narrative")
        async def track_narrative(params: ToolParams) -> MCPResponse:
            """Track narrative evolution for a story"""
            narrative_id = params.get("narrative_id")
            keywords = params.get("keywords", [])
            
            try:
                # Track narrative across sources
                narrative_data = await self._track_narrative_evolution(
                    narrative_id, keywords
                )
                
                return MCPResponse(
                    success=True,
                    data=narrative_data
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
    
    def _register_events(self):
        """Register event streams"""
        
        @self.server.event_stream("news.realtime")
        async def news_realtime_stream(params: Dict) -> AsyncGenerator:
            """Stream real-time news events"""
            filters = params.get("filters", {})
            symbols = filters.get("symbols", [])
            min_tier = filters.get("min_tier", 5)
            
            while True:
                # Check for new news
                recent_news = self.get_recent_news(hours=0.1, limit=10)  # Last 6 minutes
                
                for article in recent_news:
                    if (not symbols or article.get('symbol') in symbols) and \
                       article.get('source_tier', 5) <= min_tier:
                        
                        yield {
                            "type": "news.article",
                            "data": {
                                "symbol": article.get('symbol'),
                                "headline": article.get('headline'),
                                "source": article.get('source'),
                                "sentiment": self._quick_sentiment(article.get('headline')),
                                "catalyst_score": self._calculate_catalyst_score(article)
                            }
                        }
                
                await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _collect_all_news(self, symbols: Optional[List[str]], sources: List[str]) -> Dict:
        """Collect news from all configured sources"""
        start_time = datetime.now()
        all_news = []
        collection_stats = {}
        
        # Use asyncio for concurrent collection
        tasks = []
        
        if 'all' in sources or 'newsapi' in sources:
            if self.api_keys['newsapi']:
                tasks.append(self._collect_newsapi_async(symbols))
        
        if 'all' in sources or 'rss' in sources:
            tasks.append(self._collect_rss_async())
        
        if 'all' in sources or 'alphavantage' in sources:
            if self.api_keys['alphavantage'] and symbols:
                tasks.append(self._collect_alphavantage_async(symbols))
        
        if 'all' in sources or 'finnhub' in sources:
            if self.api_keys['finnhub'] and symbols:
                tasks.append(self._collect_finnhub_async(symbols))
        
        # Collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Collection task failed", error=str(result))
            else:
                source_name, news_items = result
                all_news.extend(news_items)
                collection_stats[source_name] = len(news_items)
        
        # Save all collected news
        save_stats = self._save_news_items(all_news)
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'success',
            'execution_time': execution_time,
            'articles_collected': save_stats['total'],
            'articles_saved': save_stats['saved'],
            'duplicates': save_stats['duplicates'],
            'errors': save_stats['errors'],
            'sources': collection_stats,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _collect_newsapi_async(self, symbols: Optional[List[str]]) -> tuple:
        """Collect news from NewsAPI asynchronously"""
        collected_news = []
        base_url = "https://newsapi.org/v2/everything"
        
        queries = symbols[:5] if symbols else ['stock market', 'S&P 500', 'NYSE']
        
        async with aiohttp.ClientSession() as session:
            for query in queries:
                try:
                    # Check cache first
                    cache_key = f"newsapi:{query}"
                    if self.redis_client:
                        cached_data = await self.redis_client.get(cache_key)
                        if cached_data:
                            collected_news.extend(json.loads(cached_data))
                            continue
                    
                    params = {
                        'apiKey': self.api_keys['newsapi'],
                        'q': query,
                        'language': 'en',
                        'sortBy': 'publishedAt',
                        'pageSize': self.collection_config['max_articles_per_source'],
                        'from': (datetime.now() - timedelta(days=1)).isoformat()
                    }
                    
                    async with session.get(base_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            articles = []
                            
                            for article in data.get('articles', []):
                                news_item = self._process_newsapi_article(article, query, symbols)
                                articles.append(news_item)
                                collected_news.append(news_item)
                            
                            # Cache the results
                            if self.redis_client:
                                await self.redis_client.setex(
                                    cache_key,
                                    self.collection_config['cache_ttl'],
                                    json.dumps(articles)
                                )
                                
                except Exception as e:
                    self.logger.error(f"Error collecting from NewsAPI", error=str(e))
        
        return ('newsapi', collected_news)
    
    async def _collect_rss_async(self) -> tuple:
        """Collect RSS feeds asynchronously"""
        collected_news = []
        
        for source_name, feed_info in self.rss_feeds.items():
            try:
                # RSS parsing is synchronous, so run in executor
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(
                    None, feedparser.parse, feed_info['url']
                )
                
                for entry in feed.entries[:self.collection_config['max_articles_per_source']]:
                    news_item = self._process_rss_entry(entry, source_name, feed_info['tier'])
                    collected_news.append(news_item)
                    
            except Exception as e:
                self.logger.error(f"Error collecting RSS feed {source_name}", error=str(e))
        
        return ('rss', collected_news)
    
    async def _collect_alphavantage_async(self, symbols: List[str]) -> tuple:
        """Collect AlphaVantage news asynchronously"""
        collected_news = []
        base_url = "https://www.alphavantage.co/query"
        
        async with aiohttp.ClientSession() as session:
            for symbol in symbols[:5]:
                try:
                    params = {
                        'function': 'NEWS_SENTIMENT',
                        'tickers': symbol,
                        'apikey': self.api_keys['alphavantage']
                    }
                    
                    async with session.get(base_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for article in data.get('feed', []):
                                news_item = self._process_alphavantage_article(article, symbol)
                                collected_news.append(news_item)
                                
                except Exception as e:
                    self.logger.error(f"Error collecting AlphaVantage news", error=str(e))
        
        return ('alphavantage', collected_news)
    
    async def _collect_finnhub_async(self, symbols: List[str]) -> tuple:
        """Collect Finnhub news asynchronously"""
        collected_news = []
        base_url = "https://finnhub.io/api/v1/company-news"
        
        async with aiohttp.ClientSession() as session:
            for symbol in symbols[:5]:
                try:
                    date_from = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    date_to = datetime.now().strftime('%Y-%m-%d')
                    
                    params = {
                        'symbol': symbol,
                        'from': date_from,
                        'to': date_to,
                        'token': self.api_keys['finnhub']
                    }
                    
                    async with session.get(base_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for article in data[:self.collection_config['max_articles_per_source']]:
                                news_item = self._process_finnhub_article(article, symbol)
                                collected_news.append(news_item)
                                
                except Exception as e:
                    self.logger.error(f"Error collecting Finnhub news", error=str(e))
        
        return ('finnhub', collected_news)
    
    def _process_newsapi_article(self, article: Dict, query: str, symbols: Optional[List[str]]) -> Dict:
        """Process NewsAPI article"""
        published = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
        
        return {
            'news_id': self._generate_news_id(
                article.get('title', ''),
                article.get('source', {}).get('name', 'NewsAPI'),
                str(published)
            ),
            'symbol': query if query in (symbols or []) else None,
            'headline': article.get('title', ''),
            'source': article.get('source', {}).get('name', 'NewsAPI'),
            'published_timestamp': published,
            'content_snippet': article.get('description', '')[:500],
            'url': article.get('url'),
            'is_pre_market': self._is_pre_market_news(published),
            'market_state': self._get_market_state(published),
            'headline_keywords': self._extract_headline_keywords(article.get('title', '')),
            'mentioned_tickers': self._extract_mentioned_tickers(
                article.get('title', '') + ' ' + article.get('description', '')
            ),
            'source_tier': self._determine_source_tier(
                article.get('source', {}).get('name', 'Unknown')
            )
        }
    
    def _process_rss_entry(self, entry: Dict, source_name: str, tier: int) -> Dict:
        """Process RSS feed entry"""
        published = datetime.fromtimestamp(
            time.mktime(entry.published_parsed)
        ) if hasattr(entry, 'published_parsed') else datetime.now()
        
        return {
            'news_id': self._generate_news_id(
                entry.get('title', ''),
                source_name,
                str(published)
            ),
            'symbol': None,
            'headline': entry.get('title', ''),
            'source': source_name,
            'published_timestamp': published,
            'content_snippet': entry.get('summary', '')[:500],
            'url': entry.get('link'),
            'is_pre_market': self._is_pre_market_news(published),
            'market_state': self._get_market_state(published),
            'headline_keywords': self._extract_headline_keywords(entry.get('title', '')),
            'mentioned_tickers': self._extract_mentioned_tickers(
                entry.get('title', '') + ' ' + entry.get('summary', '')
            ),
            'source_tier': tier
        }
    
    def _process_alphavantage_article(self, article: Dict, symbol: str) -> Dict:
        """Process AlphaVantage article"""
        published = datetime.strptime(
            article['time_published'],
            '%Y%m%dT%H%M%S'
        )
        
        return {
            'news_id': self._generate_news_id(
                article.get('title', ''),
                article.get('source', 'AlphaVantage'),
                str(published)
            ),
            'symbol': symbol,
            'headline': article.get('title', ''),
            'source': article.get('source', 'AlphaVantage'),
            'published_timestamp': published,
            'content_snippet': article.get('summary', '')[:500],
            'url': article.get('url'),
            'is_pre_market': self._is_pre_market_news(published),
            'market_state': self._get_market_state(published),
            'headline_keywords': self._extract_headline_keywords(article.get('title', '')),
            'mentioned_tickers': self._extract_mentioned_tickers(
                article.get('title', '') + ' ' + article.get('summary', '')
            ),
            'source_tier': self._determine_source_tier(article.get('source', 'Unknown')),
            'metadata': {
                'ticker_sentiment': article.get('ticker_sentiment', {}),
                'overall_sentiment_score': article.get('overall_sentiment_score')
            }
        }
    
    def _process_finnhub_article(self, article: Dict, symbol: str) -> Dict:
        """Process Finnhub article"""
        published = datetime.fromtimestamp(article.get('datetime', time.time()))
        
        return {
            'news_id': self._generate_news_id(
                article.get('headline', ''),
                article.get('source', 'Finnhub'),
                str(published)
            ),
            'symbol': symbol,
            'headline': article.get('headline', ''),
            'source': article.get('source', 'Finnhub'),
            'published_timestamp': published,
            'content_snippet': article.get('summary', '')[:500],
            'url': article.get('url'),
            'is_pre_market': self._is_pre_market_news(published),
            'market_state': self._get_market_state(published),
            'headline_keywords': self._extract_headline_keywords(article.get('headline', '')),
            'mentioned_tickers': self._extract_mentioned_tickers(
                article.get('headline', '') + ' ' + article.get('summary', '')
            ),
            'source_tier': self._determine_source_tier(article.get('source', 'Unknown'))
        }
    
    def _generate_news_id(self, headline: str, source: str, timestamp: str) -> str:
        """Generate unique ID for news article"""
        content = f"{headline}_{source}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_pre_market_news(self, timestamp: datetime) -> bool:
        """Check if news was published during pre-market hours"""
        timezone_offset = int(os.getenv('TIMEZONE_OFFSET', '-5'))
        est_hour = timestamp.hour + timezone_offset
        if est_hour < 0:
            est_hour += 24
        elif est_hour >= 24:
            est_hour -= 24
        return 4 <= est_hour < 9.5
    
    def _get_market_state(self, timestamp: datetime) -> str:
        """Determine market state when news was published"""
        timezone_offset = int(os.getenv('TIMEZONE_OFFSET', '-5'))
        est_hour = timestamp.hour + timezone_offset
        if est_hour < 0:
            est_hour += 24
        elif est_hour >= 24:
            est_hour -= 24
        
        weekday = timestamp.weekday()
        
        if weekday >= 5:  # Weekend
            return "weekend"
        
        if 4 <= est_hour < 9.5:
            return "pre-market"
        elif 9.5 <= est_hour < 16:
            return "regular"
        elif 16 <= est_hour < 20:
            return "after-hours"
        else:
            return "closed"
    
    def _extract_headline_keywords(self, headline: str) -> List[str]:
        """Extract important keywords from headline"""
        keywords = []
        headline_lower = headline.lower()
        
        keyword_patterns = {
            'earnings': ['earnings', 'revenue', 'profit', 'loss', 'beat', 'miss', 'eps'],
            'fda': ['fda', 'approval', 'drug', 'clinical', 'trial', 'phase'],
            'merger': ['merger', 'acquisition', 'acquire', 'buyout', 'takeover', 'deal'],
            'analyst': ['upgrade', 'downgrade', 'rating', 'price target', 'analyst'],
            'guidance': ['guidance', 'forecast', 'outlook', 'warns', 'expects', 'raises', 'lowers']
        }
        
        for category, patterns in keyword_patterns.items():
            if any(pattern in headline_lower for pattern in patterns):
                keywords.append(category)
        
        return keywords
    
    def _extract_mentioned_tickers(self, text: str) -> List[str]:
        """Extract stock tickers mentioned in text"""
        import re
        
        ticker_pattern = r'\$?[A-Z]{1,5}\b'
        exclusions = {'I', 'A', 'THE', 'AND', 'OR', 'TO', 'IN', 'OF', 'FOR',
                     'CEO', 'CFO', 'IPO', 'FDA', 'SEC', 'NYSE', 'ETF', 'AI', 'IT'}
        
        potential_tickers = re.findall(ticker_pattern, text)
        
        tickers = []
        for ticker in potential_tickers:
            ticker = ticker.replace('$', '')
            if ticker not in exclusions and len(ticker) >= 2:
                tickers.append(ticker)
        
        return list(set(tickers))
    
    def _determine_source_tier(self, source: str) -> int:
        """Determine reliability tier of news source"""
        tier_mapping = {
            'Reuters': 1, 'Bloomberg': 1, 'Wall Street Journal': 1,
            'MarketWatch': 1, 'CNBC': 1, 'Yahoo Finance': 1,
            'Seeking Alpha': 2, 'Investing.com': 2, 'TheStreet': 2,
            'Benzinga': 3, 'InvestorPlace': 3, 'Motley Fool': 3,
            'StockTwits': 4, 'Reddit': 4
        }
        
        for key, tier in tier_mapping.items():
            if key.lower() in source.lower():
                return tier
        
        return 5  # Default to lowest tier
    
    def _save_news_items(self, news_items: List[Dict]) -> Dict[str, int]:
        """Save news items to database"""
        stats = {'total': len(news_items), 'saved': 0, 'duplicates': 0, 'errors': 0}
        
        for item in news_items:
            try:
                news_id = self.insert_news_article(item)
                if news_id:
                    stats['saved'] += 1
                else:
                    stats['duplicates'] += 1
            except Exception as e:
                self.logger.error("Error saving news item", error=str(e))
                stats['errors'] += 1
        
        return stats
    
    def _analyze_news_sentiment(self, articles: List[Dict]) -> Dict:
        """Analyze sentiment from news articles"""
        if not articles:
            return {
                'overall': 'neutral',
                'confidence': 0.0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0
            }
        
        positive_count = 0
        negative_count = 0
        
        for article in articles:
            keywords = article.get('headline_keywords', [])
            headline_lower = article.get('headline', '').lower()
            
            # Simple sentiment based on keywords
            positive_words = ['beat', 'upgrade', 'approval', 'raised', 'growth', 'profit']
            negative_words = ['miss', 'downgrade', 'rejection', 'lowered', 'loss', 'warning']
            
            if any(word in headline_lower for word in positive_words):
                positive_count += 1
            elif any(word in headline_lower for word in negative_words):
                negative_count += 1
        
        total = len(articles)
        neutral_count = total - positive_count - negative_count
        
        # Determine overall sentiment
        if positive_count > negative_count * 1.5:
            overall = 'positive'
        elif negative_count > positive_count * 1.5:
            overall = 'negative'
        else:
            overall = 'neutral'
        
        confidence = max(positive_count, negative_count) / total if total > 0 else 0
        
        return {
            'overall': overall,
            'confidence': round(confidence, 2),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count
        }
    
    def _quick_sentiment(self, headline: str) -> str:
        """Quick sentiment analysis for streaming"""
        headline_lower = headline.lower()
        
        positive_words = ['beat', 'upgrade', 'approval', 'raised', 'growth']
        negative_words = ['miss', 'downgrade', 'rejection', 'lowered', 'loss']
        
        if any(word in headline_lower for word in positive_words):
            return 'positive'
        elif any(word in headline_lower for word in negative_words):
            return 'negative'
        else:
            return 'neutral'
    
    def _calculate_catalyst_score(self, article: Dict) -> float:
        """Calculate catalyst score for an article"""
        score = 0
        
        # Source tier contribution
        tier = article.get('source_tier', 5)
        score += (6 - tier) * 10  # Tier 1 = 50, Tier 5 = 10
        
        # Keyword contribution
        keywords = article.get('headline_keywords', [])
        high_impact_keywords = ['earnings', 'fda', 'merger', 'guidance']
        for keyword in keywords:
            if keyword in high_impact_keywords:
                score += 15
            else:
                score += 5
        
        # Recency contribution
        if article.get('is_pre_market'):
            score += 20
        
        # Market state contribution
        if article.get('market_state') in ['pre-market', 'after-hours']:
            score += 10
        
        return min(score, 100)  # Cap at 100
    
    async def _track_narrative_evolution(self, narrative_id: str, keywords: List[str]) -> Dict:
        """Track how a narrative evolves across sources"""
        # Implementation would track story progression
        return {
            'narrative_id': narrative_id,
            'keywords': keywords,
            'evolution': [],
            'status': 'tracking'
        }
    
    async def run(self):
        """Run the MCP server"""
        # FIXED: Changed port from 5108 to 5008
        self.logger.info("Starting News MCP Server", port=5008)
        
        # Initialize Redis
        await self._init_redis()
        
        # Support both WebSocket and stdio transports
        if os.getenv('MCP_TRANSPORT', 'websocket') == 'stdio':
            transport = StdioTransport()
        else:
            transport = WebSocketTransport(port=5008)  # FIXED: Changed from 5108
        
        await self.server.run(transport)


if __name__ == "__main__":
    server = NewsMCPServer()
    asyncio.run(server.run())