#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 3.1.0
Last Updated: 2025-08-23
Purpose: MCP-enabled news collection with database MCP integration

REVISION HISTORY:
v3.1.0 (2025-08-23) - Database MCP integration and missing features
- Replaced all database_utils imports with MCP Database Client
- Added missing resources: news/sentiment/{symbol}, news/trending, news/sources/health
- Added missing tools: refresh_sources, blacklist_source, prioritize_symbol
- Updated all database operations to use async MCP client
- Enhanced source management and health monitoring

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
import asyncio
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
import aiohttp
import feedparser
from newspaper import Article
from structlog import get_logger
import redis.asyncio as redis

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import MCP Database Client instead of database_utils
from mcp_database_client import MCPDatabaseClient


class NewsMCPServer:
    """MCP Server for news collection and intelligence"""
    
    def __init__(self):
        # Initialize MCP server
        self.server = MCPServer("news-intelligence")
        self.setup_logging()
        
        # Database client (initialized in async context)
        self.db_client: Optional[MCPDatabaseClient] = None
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Service configuration
        self.service_name = 'news-intelligence'
        self.port = int(os.getenv('PORT', '5008'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # News sources configuration
        self.news_sources = {
            'yahoo_finance': {
                'enabled': True,
                'tier': 1,
                'base_url': 'https://finance.yahoo.com/rss/topstories',
                'rate_limit': 30,  # requests per minute
                'health': 'healthy',
                'last_check': None
            },
            'seeking_alpha': {
                'enabled': True,
                'tier': 1,
                'base_url': 'https://seekingalpha.com/market_currents.xml',
                'rate_limit': 20,
                'health': 'healthy',
                'last_check': None
            },
            'marketwatch': {
                'enabled': True,
                'tier': 2,
                'base_url': 'https://feeds.marketwatch.com/marketwatch/topstories',
                'rate_limit': 30,
                'health': 'healthy',
                'last_check': None
            },
            'reuters': {
                'enabled': True,
                'tier': 1,
                'base_url': 'https://www.reutersagency.com/feed/',
                'rate_limit': 20,
                'health': 'healthy',
                'last_check': None
            }
        }
        
        # Blacklisted sources (can be updated via tool)
        self.blacklisted_sources = set()
        
        # Priority symbols (get more frequent updates)
        self.priority_symbols = set()
        
        # Collection configuration
        self.collection_config = {
            'max_articles_per_cycle': int(os.getenv('MAX_ARTICLES_PER_CYCLE', '100')),
            'article_age_hours': int(os.getenv('ARTICLE_AGE_HOURS', '24')),
            'sentiment_threshold': float(os.getenv('SENTIMENT_THRESHOLD', '0.3')),
            'catalyst_keywords': [
                'earnings', 'merger', 'acquisition', 'fda', 'approval',
                'lawsuit', 'investigation', 'upgrade', 'downgrade',
                'guidance', 'revenue', 'profit', 'loss', 'recall'
            ]
        }
        
        # Register MCP endpoints
        self._register_resources()
        self._register_tools()
        self._register_events()
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    async def initialize(self):
        """Initialize async components"""
        # Initialize database client
        self.db_client = MCPDatabaseClient(
            os.getenv('DATABASE_MCP_URL', 'ws://database-service:5010')
        )
        await self.db_client.connect()
        
        # Initialize Redis
        self.redis_client = await redis.from_url(
            os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
            decode_responses=True
        )
        
        # Load saved configuration
        await self._load_configuration()
        
        # Check all news sources
        await self._check_all_sources()
        
        self.logger.info("News service initialized",
                        database_connected=True,
                        redis_connected=True,
                        sources_checked=True)
    
    async def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            await self.redis_client.close()
            
        if self.db_client:
            await self.db_client.disconnect()
    
    async def _load_configuration(self):
        """Load saved configuration from cache"""
        try:
            # Load blacklisted sources
            blacklist = await self.redis_client.smembers("news:blacklisted_sources")
            self.blacklisted_sources = set(blacklist) if blacklist else set()
            
            # Load priority symbols
            priority = await self.redis_client.smembers("news:priority_symbols")
            self.priority_symbols = set(priority) if priority else set()
            
            self.logger.info("Configuration loaded",
                           blacklisted=len(self.blacklisted_sources),
                           priority=len(self.priority_symbols))
        except Exception as e:
            self.logger.warning("Failed to load configuration", error=str(e))
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("news/recent")
        async def get_recent_news(params: ResourceParams) -> ResourceResponse:
            """Get recent news articles"""
            hours = params.get('hours', 24)
            symbol = params.get('symbol')
            min_tier = params.get('min_tier', 3)
            limit = params.get('limit', 100)
            
            # Get from database via MCP
            articles = await self.db_client.get_recent_news(hours=hours, symbol=symbol)
            
            # Filter by tier
            filtered = [a for a in articles if a.get('source_tier', 3) <= min_tier]
            
            # Sort by timestamp
            filtered.sort(key=lambda x: x.get('published_timestamp', ''), reverse=True)
            
            # Limit results
            filtered = filtered[:limit]
            
            return ResourceResponse(
                type="news_collection",
                data={'articles': filtered},
                metadata={
                    'count': len(filtered),
                    'hours': hours,
                    'symbol': symbol
                }
            )
        
        @self.server.resource("news/by-symbol/{symbol}")
        async def get_news_by_symbol(params: ResourceParams) -> ResourceResponse:
            """Get news for specific symbol"""
            symbol = params['symbol']
            hours = params.get('hours', 24)
            include_sentiment = params.get('include_sentiment', True)
            
            # Get articles from database
            articles = await self.db_client.get_recent_news(hours=hours, symbol=symbol)
            
            # Add sentiment if requested
            if include_sentiment:
                for article in articles:
                    if 'sentiment' not in article:
                        article['sentiment'] = self._analyze_sentiment(
                            article.get('headline', '') + ' ' + 
                            article.get('content_snippet', '')
                        )
            
            return ResourceResponse(
                type="symbol_news",
                data={
                    'symbol': symbol,
                    'articles': articles
                },
                metadata={
                    'count': len(articles),
                    'hours': hours
                }
            )
        
        @self.server.resource("news/sentiment/{symbol}")
        async def get_news_sentiment(params: ResourceParams) -> ResourceResponse:
            """Get aggregated sentiment analysis for symbol"""
            symbol = params['symbol']
            timeframe = params.get('timeframe', '24h')
            
            # Convert timeframe to hours
            hours_map = {'1h': 1, '4h': 4, '24h': 24, '7d': 168, '30d': 720}
            hours = hours_map.get(timeframe, 24)
            
            # Get articles
            articles = await self.db_client.get_recent_news(hours=hours, symbol=symbol)
            
            if not articles:
                return ResourceResponse(
                    type="sentiment_analysis",
                    data={
                        'symbol': symbol,
                        'sentiment': 'neutral',
                        'score': 0.0,
                        'confidence': 0.0,
                        'article_count': 0
                    }
                )
            
            # Calculate aggregate sentiment
            sentiments = []
            for article in articles:
                sentiment_data = self._analyze_sentiment(
                    article.get('headline', '') + ' ' + 
                    article.get('content_snippet', '')
                )
                sentiments.append(sentiment_data)
            
            # Aggregate scores
            avg_score = sum(s['score'] for s in sentiments) / len(sentiments)
            avg_confidence = sum(s['confidence'] for s in sentiments) / len(sentiments)
            
            # Determine overall sentiment
            if avg_score > 0.3:
                overall_sentiment = 'positive'
            elif avg_score < -0.3:
                overall_sentiment = 'negative'
            else:
                overall_sentiment = 'neutral'
            
            return ResourceResponse(
                type="sentiment_analysis",
                data={
                    'symbol': symbol,
                    'sentiment': overall_sentiment,
                    'score': round(avg_score, 3),
                    'confidence': round(avg_confidence, 3),
                    'article_count': len(articles),
                    'timeframe': timeframe,
                    'breakdown': {
                        'positive': len([s for s in sentiments if s['sentiment'] == 'positive']),
                        'negative': len([s for s in sentiments if s['sentiment'] == 'negative']),
                        'neutral': len([s for s in sentiments if s['sentiment'] == 'neutral'])
                    }
                }
            )
        
        @self.server.resource("news/trending")
        async def get_trending_news(params: ResourceParams) -> ResourceResponse:
            """Get trending symbols based on news volume"""
            hours = params.get('hours', 4)
            limit = params.get('limit', 20)
            min_articles = params.get('min_articles', 3)
            
            # Get recent articles
            articles = await self.db_client.get_recent_news(hours=hours)
            
            # Count by symbol
            symbol_counts = {}
            symbol_sentiments = {}
            
            for article in articles:
                symbol = article.get('symbol')
                if symbol:
                    symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
                    
                    # Track sentiment
                    if symbol not in symbol_sentiments:
                        symbol_sentiments[symbol] = []
                    
                    sentiment = self._analyze_sentiment(article.get('headline', ''))
                    symbol_sentiments[symbol].append(sentiment['score'])
            
            # Filter by minimum articles
            trending = []
            for symbol, count in symbol_counts.items():
                if count >= min_articles:
                    # Calculate average sentiment
                    sentiments = symbol_sentiments.get(symbol, [])
                    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
                    
                    trending.append({
                        'symbol': symbol,
                        'article_count': count,
                        'avg_sentiment': round(avg_sentiment, 3),
                        'momentum_score': count * (1 + abs(avg_sentiment))  # Volume * sentiment
                    })
            
            # Sort by momentum score
            trending.sort(key=lambda x: x['momentum_score'], reverse=True)
            
            return ResourceResponse(
                type="trending_symbols",
                data={'trending': trending[:limit]},
                metadata={
                    'hours': hours,
                    'total_articles': len(articles)
                }
            )
        
        @self.server.resource("news/sources/health")
        async def get_sources_health(params: ResourceParams) -> ResourceResponse:
            """Get health status of all news sources"""
            health_data = {}
            
            for source_name, source_config in self.news_sources.items():
                health_data[source_name] = {
                    'enabled': source_config['enabled'],
                    'tier': source_config['tier'],
                    'health': source_config['health'],
                    'last_check': source_config['last_check'],
                    'rate_limit': source_config['rate_limit'],
                    'blacklisted': source_name in self.blacklisted_sources
                }
            
            # Calculate aggregate health
            total_sources = len(self.news_sources)
            healthy_sources = sum(1 for s in health_data.values() if s['health'] == 'healthy')
            enabled_sources = sum(1 for s in health_data.values() if s['enabled'] and not s['blacklisted'])
            
            return ResourceResponse(
                type="sources_health",
                data={
                    'sources': health_data,
                    'summary': {
                        'total': total_sources,
                        'healthy': healthy_sources,
                        'enabled': enabled_sources,
                        'health_percentage': round(healthy_sources / total_sources * 100, 1)
                    }
                },
                metadata={'checked_at': datetime.now().isoformat()}
            )
        
        @self.server.resource("news/catalysts")
        async def get_catalyst_news(params: ResourceParams) -> ResourceResponse:
            """Get news with high catalyst potential"""
            hours = params.get('hours', 4)
            min_score = params.get('min_score', 0.7)
            
            # Get recent articles
            articles = await self.db_client.get_recent_news(hours=hours)
            
            # Filter and score by catalyst potential
            catalyst_articles = []
            
            for article in articles:
                catalyst_score = self._calculate_catalyst_score(article)
                if catalyst_score >= min_score:
                    article['catalyst_score'] = catalyst_score
                    article['catalyst_keywords'] = self._extract_catalyst_keywords(article)
                    catalyst_articles.append(article)
            
            # Sort by catalyst score
            catalyst_articles.sort(key=lambda x: x['catalyst_score'], reverse=True)
            
            return ResourceResponse(
                type="catalyst_news",
                data={'articles': catalyst_articles},
                metadata={
                    'count': len(catalyst_articles),
                    'min_score': min_score
                }
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("collect_news")
        async def collect_news(params: ToolParams) -> ToolResponse:
            """Trigger news collection from all sources"""
            sources = params.get("sources", ["all"])
            mode = params.get("mode", "normal")
            symbols = params.get("symbols", None)
            cycle_id = params.get("cycle_id")
            
            try:
                # Log start
                if cycle_id:
                    await self.db_client.log_workflow_step(
                        cycle_id, 'news_collection', 'started',
                        {'sources': sources, 'symbols': symbols}
                    )
                
                # Collect from sources
                results = await self._collect_all_news(symbols, sources)
                
                # Log completion
                if cycle_id:
                    await self.db_client.log_workflow_step(
                        cycle_id, 'news_collection', 'completed',
                        {
                            'articles_collected': results["articles_collected"],
                            'articles_saved': results["articles_saved"]
                        }
                    )
                
                return ToolResponse(
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
                    await self.db_client.log_workflow_step(
                        cycle_id, 'news_collection', 'failed',
                        {'error': str(e)}
                    )
                    
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("refresh_sources")
        async def refresh_sources(params: ToolParams) -> ToolResponse:
            """Refresh news sources and check their health"""
            check_feeds = params.get("check_feeds", True)
            
            try:
                # Check all sources
                results = await self._check_all_sources(check_feeds)
                
                # Update database with health status
                for source_name, status in results.items():
                    await self.db_client.update_service_health(
                        f"news_source_{source_name}",
                        status['health'],
                        {
                            'last_check': status['last_check'],
                            'error': status.get('error')
                        }
                    )
                
                # Calculate summary
                healthy = sum(1 for s in results.values() if s['health'] == 'healthy')
                total = len(results)
                
                return ToolResponse(
                    success=True,
                    data={
                        'sources_checked': total,
                        'healthy': healthy,
                        'degraded': total - healthy,
                        'details': results
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("blacklist_source")
        async def blacklist_source(params: ToolParams) -> ToolResponse:
            """Add or remove a source from the blacklist"""
            source_name = params["source_name"]
            action = params.get("action", "add")  # add or remove
            reason = params.get("reason", "")
            
            try:
                if action == "add":
                    self.blacklisted_sources.add(source_name)
                    await self.redis_client.sadd("news:blacklisted_sources", source_name)
                    
                    # Log the blacklisting
                    self.logger.warning("Source blacklisted",
                                      source=source_name,
                                      reason=reason)
                    
                elif action == "remove":
                    self.blacklisted_sources.discard(source_name)
                    await self.redis_client.srem("news:blacklisted_sources", source_name)
                    
                    self.logger.info("Source removed from blacklist",
                                   source=source_name)
                
                return ToolResponse(
                    success=True,
                    data={
                        'source': source_name,
                        'action': action,
                        'blacklisted': source_name in self.blacklisted_sources,
                        'total_blacklisted': len(self.blacklisted_sources)
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("prioritize_symbol")
        async def prioritize_symbol(params: ToolParams) -> ToolResponse:
            """Add or remove a symbol from priority list"""
            symbol = params["symbol"].upper()
            action = params.get("action", "add")  # add or remove
            reason = params.get("reason", "")
            
            try:
                if action == "add":
                    self.priority_symbols.add(symbol)
                    await self.redis_client.sadd("news:priority_symbols", symbol)
                    
                    self.logger.info("Symbol prioritized",
                                   symbol=symbol,
                                   reason=reason)
                    
                elif action == "remove":
                    self.priority_symbols.discard(symbol)
                    await self.redis_client.srem("news:priority_symbols", symbol)
                    
                    self.logger.info("Symbol deprioritized",
                                   symbol=symbol)
                
                return ToolResponse(
                    success=True,
                    data={
                        'symbol': symbol,
                        'action': action,
                        'prioritized': symbol in self.priority_symbols,
                        'total_priority': len(self.priority_symbols)
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("analyze_sentiment")
        async def analyze_sentiment(params: ToolParams) -> ToolResponse:
            """Analyze sentiment for provided text or symbol"""
            text = params.get("text")
            symbol = params.get("symbol")
            timeframe = params.get("timeframe", "24h")
            
            try:
                if text:
                    # Direct text analysis
                    sentiment = self._analyze_sentiment(text)
                    
                    return ToolResponse(
                        success=True,
                        data=sentiment,
                        metadata={"source": "direct_text"}
                    )
                
                elif symbol:
                    # Analyze news sentiment for symbol
                    hours_map = {"1h": 1, "4h": 4, "24h": 24, "7d": 168}
                    hours = hours_map.get(timeframe, 24)
                    
                    articles = await self.db_client.get_recent_news(
                        hours=hours, symbol=symbol
                    )
                    
                    if not articles:
                        return ToolResponse(
                            success=True,
                            data={
                                "sentiment": "neutral",
                                "confidence": 0.0,
                                "reason": "no_articles"
                            }
                        )
                    
                    # Analyze all articles
                    sentiments = []
                    for article in articles:
                        sentiment = self._analyze_sentiment(
                            article.get('headline', '') + ' ' + 
                            article.get('content_snippet', '')
                        )
                        sentiments.append(sentiment)
                    
                    # Aggregate
                    avg_score = sum(s['score'] for s in sentiments) / len(sentiments)
                    avg_confidence = sum(s['confidence'] for s in sentiments) / len(sentiments)
                    
                    return ToolResponse(
                        success=True,
                        data={
                            "sentiment": "positive" if avg_score > 0.3 else "negative" if avg_score < -0.3 else "neutral",
                            "score": round(avg_score, 3),
                            "confidence": round(avg_confidence, 3),
                            "article_count": len(articles),
                            "timeframe": timeframe
                        }
                    )
                
                else:
                    return ToolResponse(
                        success=False,
                        error="Either 'text' or 'symbol' parameter required"
                    )
                    
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("clear_cache")
        async def clear_cache(params: ToolParams) -> ToolResponse:
            """Clear news cache"""
            pattern = params.get("pattern", "news:*")
            
            try:
                # Get all matching keys
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                
                # Delete keys
                if keys:
                    await self.redis_client.delete(*keys)
                
                return ToolResponse(
                    success=True,
                    data={
                        "cleared": len(keys),
                        "pattern": pattern
                    }
                )
                
            except Exception as e:
                return ToolResponse(
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
            min_tier = filters.get("min_tier", 3)
            
            while True:
                # Check for new news
                recent_news = await self.db_client.get_recent_news(
                    hours=0.1  # Last 6 minutes
                )
                
                for article in recent_news:
                    # Apply filters
                    if symbols and article.get('symbol') not in symbols:
                        continue
                    
                    if article.get('source_tier', 3) > min_tier:
                        continue
                    
                    yield {
                        "type": "news.article",
                        "data": {
                            "symbol": article.get('symbol'),
                            "headline": article.get('headline'),
                            "source": article.get('source'),
                            "sentiment": self._quick_sentiment(article.get('headline')),
                            "catalyst_score": self._calculate_catalyst_score(article),
                            "published": article.get('published_timestamp')
                        }
                    }
                
                await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _collect_all_news(self, symbols: Optional[List[str]], 
                               sources: List[str]) -> Dict:
        """Collect news from all configured sources"""
        start_time = datetime.now()
        results = {
            "articles_collected": 0,
            "articles_saved": 0,
            "duplicates": 0,
            "sources": {}
        }
        
        # Determine which sources to use
        if "all" in sources:
            active_sources = [
                (name, config) for name, config in self.news_sources.items()
                if config['enabled'] and name not in self.blacklisted_sources
            ]
        else:
            active_sources = [
                (name, config) for name, config in self.news_sources.items()
                if name in sources and config['enabled'] and name not in self.blacklisted_sources
            ]
        
        # Collect from each source
        tasks = []
        for source_name, source_config in active_sources:
            tasks.append(
                self._collect_from_source(source_name, source_config, symbols)
            )
        
        # Execute all collections in parallel
        source_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(source_results):
            source_name = active_sources[i][0]
            
            if isinstance(result, Exception):
                self.logger.error(f"Error collecting from {source_name}",
                                error=str(result))
                results["sources"][source_name] = {"error": str(result)}
            else:
                results["sources"][source_name] = result
                results["articles_collected"] += result.get("collected", 0)
                results["articles_saved"] += result.get("saved", 0)
                results["duplicates"] += result.get("duplicates", 0)
        
        # Update execution time
        results["execution_time"] = (datetime.now() - start_time).total_seconds()
        
        return results
    
    async def _collect_from_source(self, source_name: str, source_config: Dict,
                                  symbols: Optional[List[str]]) -> Dict:
        """Collect news from a specific source"""
        result = {
            "collected": 0,
            "saved": 0,
            "duplicates": 0,
            "errors": []
        }
        
        try:
            # Fetch RSS feed
            async with aiohttp.ClientSession() as session:
                async with session.get(source_config['base_url'], timeout=10) as response:
                    content = await response.text()
            
            # Parse feed
            feed = feedparser.parse(content)
            
            # Process entries
            for entry in feed.entries[:self.collection_config['max_articles_per_cycle']]:
                try:
                    # Extract article data
                    article_data = self._extract_article_data(
                        entry, source_name, source_config['tier']
                    )
                    
                    # Skip if no symbol detected and symbols filter is active
                    if symbols and article_data.get('symbol') not in symbols:
                        continue
                    
                    # Skip old articles
                    published = datetime.fromisoformat(article_data['published_timestamp'])
                    age_hours = (datetime.now() - published).total_seconds() / 3600
                    if age_hours > self.collection_config['article_age_hours']:
                        continue
                    
                    result["collected"] += 1
                    
                    # Save to database
                    news_id = await self.db_client.persist_news_article({
                        'headline': article_data['headline'],
                        'source': source_name,
                        'published_timestamp': article_data['published_timestamp'],
                        'symbol': article_data.get('symbol'),
                        'content_snippet': article_data.get('content_snippet'),
                        'metadata': {
                            'source_tier': source_config['tier'],
                            'url': article_data.get('url'),
                            'sentiment': self._quick_sentiment(article_data['headline'])
                        }
                    })
                    
                    if news_id:
                        result["saved"] += 1
                    else:
                        result["duplicates"] += 1
                        
                except Exception as e:
                    result["errors"].append(str(e))
                    self.logger.warning(f"Error processing article from {source_name}",
                                      error=str(e))
            
        except Exception as e:
            result["errors"].append(f"Feed error: {str(e)}")
            self.logger.error(f"Error fetching feed from {source_name}",
                            error=str(e))
        
        return result
    
    def _extract_article_data(self, entry: Any, source: str, tier: int) -> Dict:
        """Extract and normalize article data from feed entry"""
        # Extract basic fields
        headline = entry.get('title', '').strip()
        url = entry.get('link', '')
        published = entry.get('published_parsed')
        
        # Convert published time
        if published:
            published_dt = datetime.fromtimestamp(
                feedparser._parse_date(entry.published).timestamp()
            )
        else:
            published_dt = datetime.now()
        
        # Extract content snippet
        content = ''
        if hasattr(entry, 'summary'):
            content = entry.summary[:500]
        elif hasattr(entry, 'description'):
            content = entry.description[:500]
        
        # Clean HTML from content
        import re
        content = re.sub('<[^<]+?>', '', content)
        
        # Detect symbol from headline and content
        symbol = self._detect_symbol(headline + ' ' + content)
        
        return {
            'headline': headline,
            'url': url,
            'published_timestamp': published_dt.isoformat(),
            'content_snippet': content,
            'symbol': symbol,
            'source_tier': tier
        }
    
    def _detect_symbol(self, text: str) -> Optional[str]:
        """Detect stock symbol from text"""
        import re
        
        # Look for explicit ticker symbols
        # Pattern: $SYMBOL or (SYMBOL) or SYMBOL: at start of sentence
        patterns = [
            r'\$([A-Z]{1,5})\b',  # $AAPL
            r'\(([A-Z]{1,5})\)',   # (AAPL)
            r'\b([A-Z]{1,5}):\s',  # AAPL: at start
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                symbol = match.group(1)
                # Validate it's likely a stock symbol
                if 1 <= len(symbol) <= 5 and symbol.isalpha():
                    return symbol
        
        # If priority symbols mentioned, detect those
        for symbol in self.priority_symbols:
            if symbol in text.upper():
                return symbol
        
        return None
    
    def _analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of text"""
        # Simple keyword-based sentiment analysis
        # In production, use a proper NLP model
        
        positive_words = [
            'surge', 'rally', 'gain', 'rise', 'climb', 'jump', 'soar',
            'positive', 'profit', 'beat', 'exceed', 'upgrade', 'buy',
            'bullish', 'growth', 'improve', 'breakthrough', 'success'
        ]
        
        negative_words = [
            'fall', 'drop', 'decline', 'plunge', 'crash', 'sink', 'tumble',
            'negative', 'loss', 'miss', 'below', 'downgrade', 'sell',
            'bearish', 'concern', 'risk', 'failure', 'lawsuit', 'investigation'
        ]
        
        text_lower = text.lower()
        
        # Count occurrences
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        # Calculate score
        total = positive_count + negative_count
        if total == 0:
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.5
            }
        
        score = (positive_count - negative_count) / total
        confidence = min(total / 10, 1.0)  # More words = higher confidence
        
        # Determine sentiment
        if score > 0.3:
            sentiment = "positive"
        elif score < -0.3:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "score": round(score, 3),
            "confidence": round(confidence, 3)
        }
    
    def _quick_sentiment(self, headline: str) -> str:
        """Quick sentiment check for headlines"""
        sentiment_data = self._analyze_sentiment(headline)
        return sentiment_data["sentiment"]
    
    def _calculate_catalyst_score(self, article: Dict) -> float:
        """Calculate catalyst potential score"""
        score = 0.0
        
        headline = article.get('headline', '').lower()
        content = article.get('content_snippet', '').lower()
        full_text = headline + ' ' + content
        
        # Check for catalyst keywords
        catalyst_count = sum(
            1 for keyword in self.collection_config['catalyst_keywords']
            if keyword in full_text
        )
        
        # Base score from keyword matches
        score = min(catalyst_count * 0.3, 1.0)
        
        # Boost for tier 1 sources
        if article.get('source_tier', 3) == 1:
            score *= 1.2
        
        # Boost for strong sentiment
        sentiment = self._analyze_sentiment(headline)
        if abs(sentiment['score']) > 0.5:
            score *= 1.3
        
        # Cap at 1.0
        return min(score, 1.0)
    
    def _extract_catalyst_keywords(self, article: Dict) -> List[str]:
        """Extract catalyst keywords found in article"""
        headline = article.get('headline', '').lower()
        content = article.get('content_snippet', '').lower()
        full_text = headline + ' ' + content
        
        found_keywords = [
            keyword for keyword in self.collection_config['catalyst_keywords']
            if keyword in full_text
        ]
        
        return found_keywords
    
    async def _check_all_sources(self, check_feeds: bool = False) -> Dict:
        """Check health of all news sources"""
        results = {}
        
        for source_name, source_config in self.news_sources.items():
            try:
                if check_feeds:
                    # Actually try to fetch the feed
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            source_config['base_url'], 
                            timeout=5
                        ) as response:
                            if response.status == 200:
                                source_config['health'] = 'healthy'
                            else:
                                source_config['health'] = 'degraded'
                else:
                    # Just mark as healthy if enabled
                    source_config['health'] = 'healthy' if source_config['enabled'] else 'disabled'
                
                source_config['last_check'] = datetime.now().isoformat()
                
                results[source_name] = {
                    'health': source_config['health'],
                    'last_check': source_config['last_check']
                }
                
            except Exception as e:
                source_config['health'] = 'unhealthy'
                source_config['last_check'] = datetime.now().isoformat()
                
                results[source_name] = {
                    'health': 'unhealthy',
                    'last_check': source_config['last_check'],
                    'error': str(e)
                }
        
        return results
    
    async def health_check(self) -> Dict:
        """Service health check"""
        try:
            # Check database connection
            db_status = await self.db_client.get_database_status()
            
            # Check Redis connection
            redis_ok = await self.redis_client.ping() if self.redis_client else False
            
            # Check news sources
            healthy_sources = sum(
                1 for s in self.news_sources.values() 
                if s['health'] == 'healthy'
            )
            
            return {
                'status': 'healthy',
                'database': db_status.get('postgresql', {}).get('status', 'unknown'),
                'redis': 'healthy' if redis_ok else 'unhealthy',
                'sources': {
                    'healthy': healthy_sources,
                    'total': len(self.news_sources)
                }
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting News Intelligence MCP Server",
                        version="3.1.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


async def main():
    """Main entry point"""
    server = NewsMCPServer()
    
    try:
        # Initialize server
        await server.initialize()
        
        # Run server
        await server.run()
        
    except KeyboardInterrupt:
        server.logger.info("Received interrupt signal")
    except Exception as e:
        server.logger.error("Fatal error", error=str(e))
    finally:
        # Cleanup
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())