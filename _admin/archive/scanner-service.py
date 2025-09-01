#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: scanner-service.py
Version: 4.0.1
Last Updated: 2025-01-31
Purpose: MCP-enabled security scanner with comprehensive market data collection

REVISION HISTORY:
v4.0.1 (2025-01-31) - Fixed database_utils import issue
- Removed dependency on non-existent database_utils module
- Implemented database functions directly in service
v4.0.0 (2024-12-30) - Complete MCP migration
- Converted from Flask REST to MCP protocol
- Resources for market data and candidate access
- Tools for scanning and candidate selection
- Maintains 100 security tracking, 5 for trading
- Alpaca API integration preserved
- Natural language interaction via Claude

Description of Service:
MCP server that scans markets for trading opportunities. Tracks top 100
securities comprehensively while selecting top 5 for active trading.
Enables Claude to discover and analyze market opportunities naturally.
"""

# Standard library imports
import os
import sys
import json
import time
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Third-party imports
import requests
import pandas as pd
import numpy as np
from alpaca_trade_api import REST
import redis
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch, Json as PgJson
from psycopg2.pool import ThreadedConnectionPool
import structlog

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Technical analysis
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("WARNING: TA-Lib not available, using fallback calculations")


class ScannerMCPServer:
    """
    MCP Server for market scanning and security selection
    """
    
    def __init__(self):
        """Initialize the MCP scanner server"""
        self.setup_environment()
        self.setup_logging()
        
        # Initialize MCP server
        self.server = MCPServer("security-scanner")
        
        # Initialize Alpaca API client
        self.alpaca_api = REST(
            os.getenv('ALPACA_API_KEY'),
            os.getenv('ALPACA_SECRET_KEY'),
            os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets'),
            api_version='v2'
        )
        
        # Database connection pool
        self.db_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', '5432')),
            database=os.getenv('DATABASE_NAME', 'catalyst_trading'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Redis client
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Service URLs
        self.news_service_url = os.getenv('NEWS_SERVICE_URL', 'http://news-service:5008')
        
        # Enhanced scan parameters
        self.scan_params = {
            'initial_universe_size': int(os.getenv('INITIAL_UNIVERSE_SIZE', '200')),
            'top_tracking_size': int(os.getenv('TOP_TRACKING_SIZE', '100')),
            'catalyst_filter_size': int(os.getenv('CATALYST_FILTER_SIZE', '50')),
            'final_selection_size': int(os.getenv('FINAL_SELECTION_SIZE', '5')),
            'min_price': float(os.getenv('MIN_PRICE', '1.0')),
            'max_price': float(os.getenv('MAX_PRICE', '500.0')),
            'min_volume': int(os.getenv('MIN_VOLUME', '500000')),
            'cache_ttl': int(os.getenv('SCANNER_CACHE_TTL', '300')),
            'concurrent_requests': int(os.getenv('SCANNER_CONCURRENT', '10'))
        }
        
        # Collection frequencies (in minutes)
        self.collection_frequencies = {
            'ultra_high': 1,
            'high_freq': 15,
            'medium_freq': 60,
            'low_freq': 360,
            'archive': 1440
        }
        
        # Tracking state cache
        self.tracking_state = {}
        asyncio.create_task(self._load_tracking_state())
        
        # Register MCP resources and tools
        self._register_resources()
        self._register_tools()
        
        self.logger.info("Scanner MCP Server v4.0.1 initialized",
                        environment=os.getenv('ENVIRONMENT', 'development'),
                        tracking_size=self.scan_params['top_tracking_size'],
                        data_source="Alpaca Markets")
        
    def setup_environment(self):
        """Setup environment variables and paths"""
        self.log_path = os.getenv('LOG_PATH', '/app/logs')
        self.data_path = os.getenv('DATA_PATH', '/app/data')
        
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(self.data_path, exist_ok=True)
        
        self.service_name = 'scanner-mcp'
        self.port = int(os.getenv('PORT', '5001'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = structlog.get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("candidates/active")
        async def get_active_candidates(params: ResourceParams) -> ResourceResponse:
            """Get current active trading candidates"""
            min_score = params.get("min_score", 0)
            scan_id = params.get("scan_id")
            
            # Check cache first
            cache_key = f"candidates:active:{scan_id or 'latest'}"
            cached = self.redis_client.get(cache_key)
            if cached:
                candidates = json.loads(cached)
            else:
                candidates = await self._get_active_candidates_from_db(scan_id)
                if candidates:
                    self.redis_client.setex(cache_key, 300, json.dumps(candidates, default=str))
            
            # Filter by min_score if specified
            if min_score > 0:
                candidates = [c for c in candidates if c.get('catalyst_score', 0) >= min_score]
            
            return ResourceResponse(
                type="candidate_collection",
                data=candidates[:5],  # Always return top 5
                metadata={
                    "scan_id": scan_id or "latest",
                    "timestamp": datetime.now().isoformat(),
                    "count": len(candidates[:5])
                }
            )
        
        @self.server.resource("candidates/history")
        async def get_candidate_history(params: ResourceParams) -> ResourceResponse:
            """Get historical scan results"""
            date = params.get("date")
            symbol = params.get("symbol")
            limit = params.get("limit", 100)
            
            history = await self._get_scan_history(date, symbol, limit)
            
            return ResourceResponse(
                type="candidate_history",
                data=history,
                metadata={
                    "count": len(history),
                    "date_filter": date,
                    "symbol_filter": symbol
                }
            )
        
        @self.server.resource("market/universe")
        async def get_market_universe(params: ResourceParams) -> ResourceResponse:
            """Get current tracked market universe"""
            include_metrics = params.get("include_metrics", False)
            
            universe = list(self.tracking_state.keys())
            
            if include_metrics:
                universe_data = []
                for symbol in universe:
                    state = self.tracking_state[symbol]
                    universe_data.append({
                        "symbol": symbol,
                        "rank": state.get("rank", 999),
                        "last_score": state.get("last_score", 0),
                        "collection_frequency": state.get("collection_frequency", "low_freq"),
                        "last_updated": state.get("last_updated").isoformat() if state.get("last_updated") else None
                    })
                universe = sorted(universe_data, key=lambda x: x["rank"])
            
            return ResourceResponse(
                type="market_universe",
                data=universe[:100],  # Top 100
                metadata={
                    "total_tracked": len(self.tracking_state),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.server.resource("scanner/tracking-state")
        async def get_tracking_state(params: ResourceParams) -> ResourceResponse:
            """Get detailed tracking state"""
            symbol = params.get("symbol")
            
            if symbol:
                state = self.tracking_state.get(symbol, {})
                data = {"symbol": symbol, **state} if state else None
            else:
                data = {
                    "tracking_count": len(self.tracking_state),
                    "frequency_breakdown": self._get_frequency_breakdown(),
                    "last_scan": await self._get_last_scan_info()
                }
            
            return ResourceResponse(
                type="tracking_state",
                data=data
            )
        
        @self.server.resource("market/movers")
        async def get_market_movers(params: ResourceParams) -> ResourceResponse:
            """Get current market movers"""
            movers = await self._get_market_movers_async()
            
            return ResourceResponse(
                type="market_movers",
                data=movers[:50],  # Top 50 movers
                metadata={
                    "count": len(movers),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.server.resource("market/status")
        async def get_market_status(params: ResourceParams) -> ResourceResponse:
            """Get current market status"""
            status = await self._get_market_status()
            
            return ResourceResponse(
                type="market_status",
                data=status
            )
        
        @self.server.resource("scanner/performance")
        async def get_scanner_performance(params: ResourceParams) -> ResourceResponse:
            """Get scanner performance metrics"""
            days = params.get("days", 7)
            
            metrics = await self._get_scanner_performance_metrics(days)
            
            return ResourceResponse(
                type="scanner_performance",
                data=metrics
            )

    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("scan_market")
        async def scan_market(params: ToolParams) -> ToolResponse:
            """Run comprehensive market scan"""
            mode = params.get("mode", "normal")
            universe_size = params.get("universe_size", self.scan_params['initial_universe_size'])
            output_limit = params.get("output_limit", self.scan_params['catalyst_filter_size'])
            
            self.logger.info(f"Starting market scan", mode=mode, universe_size=universe_size)
            
            # Run the scan
            scan_result = await self._perform_enhanced_scan(mode, universe_size, output_limit)
            
            return ToolResponse(
                success=True,
                data={
                    "scan_id": scan_result["scan_id"],
                    "evaluated": scan_result["metadata"]["total_scanned"],
                    "recorded": scan_result["metadata"]["total_tracked"],  # All saved to market_data
                    "candidates": len(scan_result["securities"]),  # TOP 5 for trading
                    "top_candidates": scan_result["securities"]
                },
                metadata={
                    "execution_time": scan_result["metadata"]["execution_time"],
                    "mode": mode
                }
            )
        
        @self.server.tool("scan_premarket")
        async def scan_premarket(params: ToolParams) -> ToolResponse:
            """Run specialized pre-market scan"""
            symbols = params.get("symbols", [])
            
            # If no symbols provided, get from news
            if not symbols:
                movers = await self._get_market_movers_async()
                symbols = movers[:100]
            
            scan_result = await self._perform_premarket_scan(symbols)
            
            return ToolResponse(
                success=True,
                data=scan_result
            )
        
        @self.server.tool("analyze_catalyst")
        async def analyze_catalyst(params: ToolParams) -> ToolResponse:
            """Analyze catalyst strength for a symbol"""
            symbol = params["symbol"]
            news_ids = params.get("news_ids", [])
            
            analysis = await self._analyze_catalyst_strength(symbol, news_ids)
            
            return ToolResponse(
                success=True,
                data=analysis
            )
        
        @self.server.tool("select_candidates")
        async def select_candidates(params: ToolParams) -> ToolResponse:
            """Select final trading candidates from a larger set"""
            candidates = params["candidates"]
            limit = params.get("limit", 5)
            criteria = params.get("criteria", "composite_score")
            
            # Sort by criteria
            sorted_candidates = sorted(
                candidates, 
                key=lambda x: x.get(criteria, 0), 
                reverse=True
            )
            
            # Select top N
            selected = sorted_candidates[:limit]
            
            # Save to database
            scan_id = f"SELECT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            for i, candidate in enumerate(selected):
                candidate['rank'] = i + 1
                await self._save_trading_candidate(candidate, scan_id)
            
            return ToolResponse(
                success=True,
                data={
                    "selected": selected,
                    "scan_id": scan_id,
                    "selection_criteria": criteria
                }
            )
        
        @self.server.tool("update_tracking")
        async def update_tracking(params: ToolParams) -> ToolResponse:
            """Update tracking state for securities"""
            updates = params["updates"]  # List of {symbol, frequency, rank}
            
            for update in updates:
                symbol = update["symbol"]
                self.tracking_state[symbol] = {
                    "symbol": symbol,
                    "last_updated": datetime.now(),
                    "collection_frequency": update.get("frequency", "medium_freq"),
                    "rank": update.get("rank", 999),
                    "last_score": update.get("score", 0)
                }
            
            # Save to database
            await self._save_tracking_state()
            
            return ToolResponse(
                success=True,
                data={
                    "updated_count": len(updates),
                    "tracking_total": len(self.tracking_state)
                }
            )
        
        @self.server.tool("save_scan")
        async def save_scan(params: ToolParams) -> ToolResponse:
            """Save complete scan results"""
            scan_id = params["scan_id"]
            results = params["results"]
            persist_all = params.get("persist_all", True)
            
            # Save all results to market_data table
            if persist_all:
                await self._store_comprehensive_scan_data(results, scan_id)
            
            # Save top 5 as trading candidates
            top_5 = results[:5]
            saved_count = 0
            for candidate in top_5:
                if await self._save_trading_candidate(candidate, scan_id):
                    saved_count += 1
            
            return ToolResponse(
                success=True,
                data={
                    "scan_id": scan_id,
                    "market_data_saved": len(results) if persist_all else 0,
                    "trading_candidates_saved": saved_count
                }
            )

    async def _perform_enhanced_scan(self, mode: str, universe_size: int, 
                                   output_limit: int) -> Dict:
        """Perform enhanced market scan"""
        start_time = datetime.now()
        
        try:
            # Generate scan ID
            scan_id = f"SCAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{mode}"
            
            # Step 1: Get market movers
            universe = await self._get_market_movers_async()
            self.logger.info("Initial universe selected", count=len(universe))
            
            # Step 2: Get enriched data with technical indicators
            enriched_data = await self._get_enriched_data_batch(universe[:universe_size])
            
            # Step 3: Score candidates
            for candidate in enriched_data:
                score = self._calculate_comprehensive_score(candidate)
                candidate['composite_score'] = score
                
            # Sort by score
            enriched_data.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
            
            # Step 4: Get top 100 and top 5
            top_100 = enriched_data[:self.scan_params['top_tracking_size']]
            top_5 = enriched_data[:self.scan_params['final_selection_size']]
            
            # Step 5: Update tracking state
            for i, candidate in enumerate(top_100):
                symbol = candidate['symbol']
                candidate['rank'] = i + 1
                self.tracking_state[symbol] = {
                    'symbol': symbol,
                    'last_updated': datetime.now(),
                    'collection_frequency': self._get_frequency_by_rank(i),
                    'last_score': candidate.get('composite_score', 0),
                    'rank': i + 1
                }
                
            # Step 6: Store comprehensive market data
            await self._store_comprehensive_scan_data(top_100, scan_id)
            
            # Step 7: Update daily aggregates
            await self._update_daily_aggregates()
            
            # Save top 5 as trading candidates
            for candidate in top_5:
                await self._save_trading_candidate(candidate, scan_id)
                
            # Return results
            return {
                'scan_id': scan_id,
                'timestamp': datetime.now().isoformat(),
                'mode': mode,
                'securities': top_5,  # Top 5 for trading
                'metadata': {
                    'total_scanned': len(universe),
                    'total_tracked': len(top_100),
                    'total_selected': len(top_5),
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            }
            
        except Exception as e:
            self.logger.error("Scan failed", error=str(e), traceback=traceback.format_exc())
            return {
                'scan_id': None,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'securities': [],
                'metadata': {'execution_time': 0}
            }

    async def _perform_premarket_scan(self, symbols: List[str]) -> Dict:
        """Perform specialized pre-market scan"""
        scan_id = f"PREMARKET_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get pre-market data
        premarket_data = []
        for symbol in symbols:
            try:
                # Get pre-market quote
                quote = self.alpaca_api.get_latest_quote(symbol)
                
                # Check for pre-market activity
                if quote and hasattr(quote, 'timestamp'):
                    market_open = datetime.now().replace(hour=9, minute=30, second=0)
                    if quote.timestamp < market_open:
                        premarket_data.append({
                            'symbol': symbol,
                            'premarket_price': float(quote.ask_price),
                            'premarket_volume': 0,  # Would need different data source
                            'timestamp': quote.timestamp
                        })
            except:
                continue
        
        return {
            'scan_id': scan_id,
            'premarket_active': len(premarket_data),
            'symbols': premarket_data[:20]
        }

    async def _get_enriched_data_batch(self, symbols: List[str]) -> List[Dict]:
        """Get enriched data for multiple symbols concurrently"""
        enriched_data = []
        
        # Use asyncio for concurrent requests
        tasks = []
        for symbol in symbols:
            task = asyncio.create_task(self._get_enriched_symbol_data_async(symbol))
            tasks.append(task)
        
        # Gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict) and result:
                enriched_data.append(result)
        
        return enriched_data

    async def _get_enriched_symbol_data_async(self, symbol: str) -> Optional[Dict]:
        """Async version of enriched symbol data retrieval"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_enriched_symbol_data, symbol)

    def _get_enriched_symbol_data(self, symbol: str) -> Optional[Dict]:
        """Get enriched symbol data with technical indicators using Alpaca"""
        try:
            # Get latest quote and trade data
            latest_quote = self.alpaca_api.get_latest_quote(symbol)
            latest_trade = self.alpaca_api.get_latest_trade(symbol)
            
            # Get historical bars for technical indicators
            end = datetime.now()
            start = end - timedelta(days=30)
            
            bars_response = self.alpaca_api.get_bars(
                symbol,
                '1Day',
                start=start.isoformat(),
                end=end.isoformat(),
                limit=30
            )
            
            # Convert bars to DataFrame
            bars_data = []
            for bar in bars_response:
                bars_data.append({
                    'timestamp': bar.t,
                    'open': bar.o,
                    'high': bar.h,
                    'low': bar.l,
                    'close': bar.c,
                    'volume': bar.v
                })
            
            if not bars_data:
                return None
                
            bars = pd.DataFrame(bars_data)
            bars.set_index('timestamp', inplace=True)
            
            # Get current data
            current_price = float(latest_trade.price)
            current_volume = int(bars['volume'].iloc[-1]) if len(bars) > 0 else 0
            
            # Get snapshot for additional data
            snapshot = self.alpaca_api.get_snapshot(symbol)
            daily_bar = snapshot.daily_bar
            prev_daily_bar = snapshot.prev_daily_bar
            
            # Calculate technical indicators
            close_prices = bars['close'].values
            high_prices = bars['high'].values
            low_prices = bars['low'].values
            volumes = bars['volume'].values
            
            # Calculate indicators
            technical_data = self._calculate_technical_indicators(
                close_prices, high_prices, low_prices, volumes
            )
            
            # Build comprehensive data
            data = {
                'symbol': symbol,
                'scan_timestamp': datetime.now(),
                'price': current_price,
                'open_price': float(daily_bar.o) if daily_bar else float(bars['open'].iloc[-1]),
                'high_price': float(daily_bar.h) if daily_bar else float(bars['high'].iloc[-1]),
                'low_price': float(daily_bar.l) if daily_bar else float(bars['low'].iloc[-1]),
                'previous_close': float(prev_daily_bar.c) if prev_daily_bar else float(bars['close'].iloc[-2]) if len(bars) > 1 else current_price,
                'volume': current_volume,
                'average_volume': int(volumes[-20:].mean()) if len(volumes) >= 20 else current_volume,
                'market_cap': 0,  # Alpaca doesn't provide market cap
                'sector': 'Unknown',
                'industry': 'Unknown',
                'news_count': 0,
                'has_news': False,
                **technical_data
            }
            
            # Calculate derived metrics
            data['price_change'] = data['price'] - data['previous_close']
            data['price_change_pct'] = (data['price_change'] / data['previous_close'] * 100) if data['previous_close'] > 0 else 0
            data['gap_pct'] = ((data['open_price'] - data['previous_close']) / data['previous_close'] * 100) if data['previous_close'] > 0 else 0
            data['relative_volume'] = (data['volume'] / data['average_volume']) if data['average_volume'] > 0 else 1
            data['dollar_volume'] = data['price'] * data['volume']
            data['day_range_pct'] = ((data['high_price'] - data['low_price']) / data['low_price'] * 100) if data['low_price'] > 0 else 0
            
            # Additional Alpaca metrics
            data['bid_price'] = float(latest_quote.bid_price) if latest_quote else data['price']
            data['ask_price'] = float(latest_quote.ask_price) if latest_quote else data['price']
            data['spread'] = data['ask_price'] - data['bid_price']
            data['spread_pct'] = (data['spread'] / data['price'] * 100) if data['price'] > 0 else 0
            
            # Get news data (async would be better)
            news_data = self._get_symbol_news(symbol)
            data.update(news_data)
                
            return data
            
        except Exception as e:
            self.logger.debug(f"Error getting enriched data for {symbol}", error=str(e))
            return None

    def _get_symbol_news(self, symbol: str) -> Dict:
        """Get news data for symbol"""
        try:
            response = requests.get(
                f"{self.news_service_url}/news/{symbol}",
                params={'hours': 24},
                timeout=3
            )
            if response.status_code == 200:
                news_data = response.json()
                return {
                    'news_count': news_data.get('count', 0),
                    'has_news': news_data.get('count', 0) > 0,
                    'primary_catalyst': news_data.get('primary_catalyst', ''),
                    'news_recency_hours': news_data.get('most_recent_hours', 24),
                    'catalyst_type': news_data.get('catalyst_type', '')
                }
        except:
            pass
        
        return {
            'news_count': 0,
            'has_news': False,
            'primary_catalyst': '',
            'news_recency_hours': 24,
            'catalyst_type': ''
        }

    def _calculate_technical_indicators(self, close_prices, high_prices, 
                                      low_prices, volumes) -> Dict:
        """Calculate technical indicators"""
        indicators = {}
        
        try:
            if TALIB_AVAILABLE and len(close_prices) >= 20:
                # RSI
                rsi = talib.RSI(close_prices, timeperiod=14)
                indicators['rsi_14'] = float(rsi[-1]) if not np.isnan(rsi[-1]) else None
                
                # Moving averages
                sma_20 = talib.SMA(close_prices, timeperiod=20)
                indicators['sma_20'] = float(sma_20[-1]) if not np.isnan(sma_20[-1]) else None
                
                if len(close_prices) >= 50:
                    sma_50 = talib.SMA(close_prices, timeperiod=50)
                    indicators['sma_50'] = float(sma_50[-1]) if not np.isnan(sma_50[-1]) else None
                else:
                    indicators['sma_50'] = None
                    
                # VWAP approximation
                typical_price = (high_prices + low_prices + close_prices) / 3
                indicators['vwap'] = float(np.sum(typical_price[-20:] * volumes[-20:]) / np.sum(volumes[-20:]))
                
            else:
                # Fallback calculations
                if len(close_prices) >= 14:
                    # Simple RSI
                    deltas = np.diff(close_prices[-15:])
                    gains = deltas[deltas > 0].sum() / 14
                    losses = -deltas[deltas < 0].sum() / 14
                    rs = gains / losses if losses > 0 else 100
                    indicators['rsi_14'] = float(100 - (100 / (1 + rs)))
                else:
                    indicators['rsi_14'] = None
                    
                # Simple moving averages
                indicators['sma_20'] = float(np.mean(close_prices[-20:])) if len(close_prices) >= 20 else None
                indicators['sma_50'] = float(np.mean(close_prices[-50:])) if len(close_prices) >= 50 else None
                
                # VWAP
                if len(close_prices) >= 20:
                    typical_price = (high_prices[-20:] + low_prices[-20:] + close_prices[-20:]) / 3
                    indicators['vwap'] = float(np.sum(typical_price * volumes[-20:]) / np.sum(volumes[-20:]))
                else:
                    indicators['vwap'] = None
                    
        except Exception as e:
            self.logger.debug("Error calculating indicators", error=str(e))
            indicators = {'rsi_14': None, 'sma_20': None, 'sma_50': None, 'vwap': None}
            
        return indicators

    def _calculate_comprehensive_score(self, data: Dict) -> float:
        """Calculate comprehensive score with multiple factors"""
        score = 0
        
        # News catalyst score (0-40 points)
        news_score = 0
        if data.get('has_news', False):
            news_score += 20
            news_count = data.get('news_count', 0)
            news_score += min(15, news_count * 3)
            # Recency bonus
            recency = data.get('news_recency_hours', 24)
            if recency < 1:
                news_score += 5
            elif recency < 4:
                news_score += 3
        score += news_score
        
        # Volume score (0-30 points)
        volume_score = 0
        rel_volume = data.get('relative_volume', 1)
        if rel_volume > 3:
            volume_score += 30
        elif rel_volume > 2:
            volume_score += 20
        elif rel_volume > 1.5:
            volume_score += 10
        score += volume_score
        
        # Price action score (0-20 points)
        price_score = 0
        price_change_pct = data.get('price_change_pct', 0)
        if abs(price_change_pct) > 5:
            price_score += 20
        elif abs(price_change_pct) > 3:
            price_score += 15
        elif abs(price_change_pct) > 1:
            price_score += 10
        score += price_score
        
        # Technical score (0-10 points)
        tech_score = 0
        rsi = data.get('rsi_14')
        if rsi and (rsi > 70 or rsi < 30):
            tech_score += 5
        if data.get('price') and data.get('sma_20'):
            if data['price'] > data['sma_20']:
                tech_score += 5
        score += tech_score
        
        # Market cap adjustment
        market_cap = data.get('market_cap', 0)
        if market_cap > 10000000000:  # 10B+
            score *= 1.1
        elif market_cap < 100000000:  # <100M
            score *= 0.8
        
        # Spread penalty
        spread_pct = data.get('spread_pct', 0)
        if spread_pct > 1:
            score *= 0.9
        elif spread_pct > 0.5:
            score *= 0.95
            
        return round(score, 2)

    def _get_frequency_by_rank(self, rank: int) -> str:
        """Get collection frequency by rank"""
        if rank < 5:
            return 'ultra_high'
        elif rank < 20:
            return 'high_freq'
        elif rank < 50:
            return 'medium_freq'
        else:
            return 'low_freq'

    async def _get_market_movers_async(self) -> List[str]:
        """Get market movers asynchronously"""
        # Start with default universe
        movers = list(self.default_universe)
        
        # Try to get trending from news service
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    f"{self.news_service_url}/trending",
                    params={'hours': 24},
                    timeout=5
                )
            )
            if response.status_code == 200:
                data = response.json()
                news_symbols = [item['symbol'] for item in data.get('trending', [])]
                movers = news_symbols + movers
        except Exception as e:
            self.logger.warning("Could not get news trending", error=str(e))
            
        # Remove duplicates
        return list(dict.fromkeys(movers))

    async def _get_market_status(self) -> Dict:
        """Get current market status"""
        try:
            clock = self.alpaca_api.get_clock()
            return {
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat() if clock.next_close else None,
                "timestamp": clock.timestamp.isoformat() if clock.timestamp else None
            }
        except:
            return {
                "is_open": False,
                "error": "Could not retrieve market status"
            }

    async def _analyze_catalyst_strength(self, symbol: str, news_ids: List[str]) -> Dict:
        """Analyze catalyst strength for a symbol"""
        # Get news details
        news_score = len(news_ids) * 10
        
        # Get current market data
        data = self._get_enriched_symbol_data(symbol)
        
        if not data:
            return {
                "symbol": symbol,
                "catalyst_strength": 0,
                "error": "Could not retrieve market data"
            }
        
        # Calculate catalyst impact
        volume_impact = data.get('relative_volume', 1) - 1
        price_impact = abs(data.get('price_change_pct', 0))
        
        catalyst_strength = min(10, (news_score + volume_impact * 20 + price_impact) / 3)
        
        return {
            "symbol": symbol,
            "catalyst_type": data.get('catalyst_type', 'unknown'),
            "catalyst_strength": round(catalyst_strength, 1),
            "expected_impact": "high" if catalyst_strength > 7 else "medium" if catalyst_strength > 4 else "low",
            "time_sensitivity": "4_hours" if catalyst_strength > 7 else "1_day",
            "volume_impact": round(volume_impact, 2),
            "price_impact": round(price_impact, 2)
        }

    async def _save_trading_candidate(self, candidate: Dict, scan_id: str) -> bool:
        """Save trading candidate to database"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            with conn.cursor() as cursor:
                # Create table if needed
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trading_candidates (
                        candidate_id SERIAL PRIMARY KEY,
                        symbol VARCHAR(10) NOT NULL,
                        scan_id VARCHAR(100),
                        scan_type VARCHAR(50),
                        catalyst_score DECIMAL(10,2),
                        catalyst_type VARCHAR(100),
                        primary_news_id VARCHAR(100),
                        volume_ratio DECIMAL(10,2),
                        price_change_pct DECIMAL(10,2),
                        market_cap BIGINT,
                        selection_rank INTEGER,
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        status VARCHAR(50) DEFAULT 'pending'
                    )
                """)
                
                # Insert candidate
                cursor.execute("""
                    INSERT INTO trading_candidates 
                    (symbol, scan_id, scan_type, catalyst_score, catalyst_type, 
                     primary_news_id, volume_ratio, price_change_pct, market_cap, 
                     selection_rank, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    candidate.get('symbol'),
                    scan_id,
                    'enhanced',
                    candidate.get('composite_score', 0),
                    candidate.get('catalyst_type'),
                    candidate.get('primary_news_id'),
                    candidate.get('relative_volume', 1.0),
                    candidate.get('price_change_pct', 0),
                    candidate.get('market_cap', 0),
                    candidate.get('rank', 0),
                    PgJson({
                        'scan_id': scan_id,
                        'scan_timestamp': candidate.get('scan_timestamp', datetime.now()).isoformat(),
                        'has_news': candidate.get('has_news', False),
                        'news_count': candidate.get('news_count', 0)
                    })
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving candidate {candidate.get('symbol')}", error=str(e))
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.db_pool.putconn(conn)

    async def _store_comprehensive_scan_data(self, securities: List[Dict], scan_id: str):
        """Store comprehensive scan data for ALL tracked securities"""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Create table if needed
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scan_market_data (
                        scan_id VARCHAR(100),
                        symbol VARCHAR(10),
                        scan_timestamp TIMESTAMPTZ,
                        price DECIMAL(10,2),
                        open_price DECIMAL(10,2),
                        high_price DECIMAL(10,2),
                        low_price DECIMAL(10,2),
                        previous_close DECIMAL(10,2),
                        volume BIGINT,
                        average_volume BIGINT,
                        relative_volume DECIMAL(10,2),
                        dollar_volume DECIMAL(20,2),
                        price_change DECIMAL(10,2),
                        price_change_pct DECIMAL(10,2),
                        gap_pct DECIMAL(10,2),
                        day_range_pct DECIMAL(10,2),
                        rsi_14 DECIMAL(5,2),
                        sma_20 DECIMAL(10,2),
                        sma_50 DECIMAL(10,2),
                        vwap DECIMAL(10,2),
                        has_news BOOLEAN,
                        news_count INTEGER,
                        catalyst_score DECIMAL(10,2),
                        primary_catalyst TEXT,
                        news_recency_hours INTEGER,
                        scan_rank INTEGER,
                        made_top_20 BOOLEAN,
                        made_top_5 BOOLEAN,
                        selected_for_trading BOOLEAN,
                        market_cap BIGINT,
                        sector VARCHAR(100),
                        industry VARCHAR(100),
                        bid_price DECIMAL(10,2),
                        ask_price DECIMAL(10,2),
                        spread DECIMAL(10,2),
                        spread_pct DECIMAL(10,2),
                        PRIMARY KEY (scan_id, symbol)
                    )
                """)
                
                # Prepare batch insert data
                insert_data = []
                
                for i, security in enumerate(securities):
                    try:
                        catalyst_score = security.get('composite_score', 0) * (security.get('news_count', 0) / 10) if security.get('news_count', 0) > 0 else 0
                        
                        insert_data.append((
                            scan_id,
                            security['symbol'],
                            security.get('scan_timestamp', datetime.now()),
                            security.get('price'),
                            security.get('open_price'),
                            security.get('high_price'),
                            security.get('low_price'),
                            security.get('previous_close'),
                            security.get('volume'),
                            security.get('average_volume'),
                            security.get('relative_volume'),
                            security.get('dollar_volume'),
                            security.get('price_change'),
                            security.get('price_change_pct'),
                            security.get('gap_pct'),
                            security.get('day_range_pct'),
                            security.get('rsi_14'),
                            security.get('sma_20'),
                            security.get('sma_50'),
                            security.get('vwap'),
                            security.get('has_news', False),
                            security.get('news_count', 0),
                            catalyst_score,
                            security.get('primary_catalyst'),
                            security.get('news_recency_hours'),
                            i + 1,  # scan_rank
                            i < 20,  # made_top_20
                            i < 5,   # made_top_5
                            i < 5,   # selected_for_trading
                            security.get('market_cap'),
                            security.get('sector'),
                            security.get('industry'),
                            security.get('bid_price'),
                            security.get('ask_price'),
                            security.get('spread'),
                            security.get('spread_pct')
                        ))
                    except Exception as e:
                        self.logger.error(f"Error preparing data for {security.get('symbol', 'UNKNOWN')}", 
                                        error=str(e))
                        continue
                
                # Batch insert
                if insert_data:
                    execute_batch(cursor, """
                        INSERT INTO scan_market_data (
                            scan_id, symbol, scan_timestamp,
                            price, open_price, high_price, low_price, previous_close,
                            volume, average_volume, relative_volume, dollar_volume,
                            price_change, price_change_pct, gap_pct, day_range_pct,
                            rsi_14, sma_20, sma_50, vwap,
                            has_news, news_count, catalyst_score, primary_catalyst, news_recency_hours,
                            scan_rank, made_top_20, made_top_5, selected_for_trading,
                            market_cap, sector, industry,
                            bid_price, ask_price, spread, spread_pct
                        ) VALUES %s
                        ON CONFLICT (scan_id, symbol) DO NOTHING
                    """, insert_data)
                    
                    self.logger.info(f"Stored scan market data for {len(insert_data)} securities")
                
                conn.commit()
                
        except Exception as e:
            self.logger.error("Error storing scan data", error=str(e))
            conn.rollback()
        finally:
            self.db_pool.putconn(conn)

    async def _update_daily_aggregates(self):
        """Update daily aggregate data"""
        # This is a placeholder - implement actual aggregation logic
        self.logger.info("Daily aggregates update triggered")

    async def _load_tracking_state(self):
        """Load tracking state from database"""
        try:
            conn = self.db_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Create table if needed
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS security_tracking_state (
                        symbol VARCHAR(10) PRIMARY KEY,
                        last_updated TIMESTAMPTZ,
                        collection_frequency VARCHAR(20),
                        last_score DECIMAL(10,2),
                        rank INTEGER
                    )
                """)
                
                cursor.execute("""
                    SELECT * FROM security_tracking_state
                    WHERE collection_frequency != 'archive'
                    LIMIT 200
                """)
                
                for row in cursor.fetchall():
                    self.tracking_state[row['symbol']] = {
                        'symbol': row['symbol'],
                        'last_updated': row['last_updated'],
                        'collection_frequency': row['collection_frequency'],
                        'last_score': row.get('last_score', 0),
                        'rank': row.get('rank', 999)
                    }
                    
        except Exception as e:
            self.logger.info("Could not load tracking state", error=str(e))
        finally:
            if 'conn' in locals():
                self.db_pool.putconn(conn)

    async def _save_tracking_state(self):
        """Save tracking state to database"""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                for symbol, state in self.tracking_state.items():
                    cursor.execute("""
                        INSERT INTO security_tracking_state 
                        (symbol, last_updated, collection_frequency, last_score, rank)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (symbol) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            collection_frequency = EXCLUDED.collection_frequency,
                            last_score = EXCLUDED.last_score,
                            rank = EXCLUDED.rank
                    """, (
                        symbol,
                        state['last_updated'],
                        state['collection_frequency'],
                        state.get('last_score', 0),
                        state.get('rank', 999)
                    ))
                conn.commit()
        except Exception as e:
            self.logger.error("Error saving tracking state", error=str(e))
            conn.rollback()
        finally:
            self.db_pool.putconn(conn)

    def _get_frequency_breakdown(self) -> Dict[str, int]:
        """Get breakdown of securities by collection frequency"""
        breakdown = {
            'ultra_high': 0,
            'high_freq': 0,
            'medium_freq': 0,
            'low_freq': 0,
            'archive': 0
        }
        
        for state in self.tracking_state.values():
            freq = state.get('collection_frequency', 'low_freq')
            if freq in breakdown:
                breakdown[freq] += 1
                
        return breakdown

    async def _get_active_candidates_from_db(self, scan_id: Optional[str]) -> List[Dict]:
        """Get active candidates from database"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if scan_id:
                    cursor.execute("""
                        SELECT * FROM trading_candidates 
                        WHERE scan_id = %s 
                        ORDER BY selection_rank
                    """, (scan_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM trading_candidates 
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        AND status = 'pending'
                        ORDER BY created_at DESC, selection_rank
                        LIMIT 10
                    """)
                    
                return cursor.fetchall()
        except Exception as e:
            self.logger.error("Error getting active candidates", error=str(e))
            return []
        finally:
            if conn:
                self.db_pool.putconn(conn)

    async def _get_scan_history(self, date: Optional[str], symbol: Optional[str], 
                              limit: int) -> List[Dict]:
        """Get scan history from database"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = "SELECT * FROM scan_market_data WHERE 1=1"
                params = []
                
                if date:
                    query += " AND DATE(scan_timestamp) = %s"
                    params.append(date)
                    
                if symbol:
                    query += " AND symbol = %s"
                    params.append(symbol)
                    
                query += " ORDER BY scan_timestamp DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            self.logger.error("Error getting scan history", error=str(e))
            return []
        finally:
            if conn:
                self.db_pool.putconn(conn)

    async def _get_last_scan_info(self) -> Dict:
        """Get information about the last scan"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT scan_id, MIN(scan_timestamp) as timestamp, 
                           COUNT(DISTINCT symbol) as total_scanned,
                           SUM(CASE WHEN selected_for_trading THEN 1 ELSE 0 END) as candidates_selected
                    FROM scan_market_data
                    WHERE scan_timestamp > NOW() - INTERVAL '24 hours'
                    GROUP BY scan_id
                    ORDER BY MIN(scan_timestamp) DESC
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        "scan_id": result['scan_id'],
                        "timestamp": result['timestamp'].isoformat(),
                        "total_scanned": result['total_scanned'],
                        "candidates_selected": result['candidates_selected']
                    }
                    
                return {
                    "scan_id": None,
                    "timestamp": datetime.now().isoformat(),
                    "candidates_selected": 0
                }
        except Exception as e:
            self.logger.error("Error getting last scan info", error=str(e))
            return {
                "scan_id": None,
                "error": str(e)
            }
        finally:
            if conn:
                self.db_pool.putconn(conn)

    async def _get_scanner_performance_metrics(self, days: int) -> Dict:
        """Get scanner performance metrics"""
        conn = None
        try:
            conn = self.db_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT scan_id) as scans_performed,
                        AVG(EXTRACT(EPOCH FROM (MAX(scan_timestamp) - MIN(scan_timestamp)))) as avg_execution_time
                    FROM scan_market_data
                    WHERE scan_timestamp > NOW() - INTERVAL '%s days'
                    GROUP BY scan_id
                """, (days,))
                
                metrics = cursor.fetchone() or {
                    "scans_performed": 0,
                    "avg_execution_time": 0
                }
                
                # Calculate success rate (simplified - you'd want actual trade outcomes)
                metrics["success_rate"] = 0.75  # Placeholder
                metrics["top_performing_picks"] = []  # Would need trade results
                
                return metrics
        except Exception as e:
            self.logger.error("Error getting performance metrics", error=str(e))
            return {
                "scans_performed": 0,
                "avg_execution_time": 0,
                "success_rate": 0,
                "top_performing_picks": []
            }
        finally:
            if conn:
                self.db_pool.putconn(conn)

    # Default universe
    default_universe = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD',
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'V', 'MA',
        'JNJ', 'PFE', 'UNH', 'CVS', 'ABBV', 'MRK', 'LLY',
        'XOM', 'CVX', 'COP', 'SLB', 'OXY',
        'WMT', 'HD', 'PG', 'KO', 'PEP', 'MCD', 'NKE', 'DIS',
        'SPY', 'QQQ', 'IWM', 'DIA', 'VXX'
    ]

    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Scanner MCP Server",
                        version="4.0.1",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


if __name__ == "__main__":
    # Run the MCP server
    server = ScannerMCPServer()
    asyncio.run(server.run())