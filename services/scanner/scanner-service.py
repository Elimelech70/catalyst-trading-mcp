#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: scanner-service.py
Version: 4.1.0
Last Updated: 2025-08-23
Purpose: MCP-enabled security scanner with database MCP integration
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import numpy as np
from structlog import get_logger
import redis.asyncio as redis
import aiohttp
import pandas as pd
import yfinance as yf

# MCP imports
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server

# Import MCP Database Client
import sys
sys.path.append("/app/shared")
# from mcp_database_client import MCPDatabaseClient


class ScannerMCPServer:
    """MCP Server for market scanning and security selection"""
    
    def __init__(self):
        self.service_name = "scanner"
        # Initialize MCP server
        self.mcp = FastMCP("security-scanner")
        self.setup_logging()
        
        # Database client (initialized in async context)
        self.db_client: Optional[MCPDatabaseClient] = None
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Service configuration
        self.port = int(os.getenv('PORT', '5001'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Alpaca API configuration
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.alpaca_base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        # News service URL
        self.news_service_url = os.getenv('NEWS_SERVICE_URL', 'http://news-service:5008')
        
        # Scanner configuration
        self.scanner_config = {
            'max_candidates': int(os.getenv('MAX_CANDIDATES', '100')),
            'top_candidates': int(os.getenv('TOP_CANDIDATES', '5')),
            'min_volume': int(os.getenv('MIN_VOLUME', '1000000')),
            'min_price': float(os.getenv('MIN_PRICE', '5.0')),
            'max_price': float(os.getenv('MAX_PRICE', '500.0')),
            'min_catalyst_score': float(os.getenv('MIN_CATALYST_SCORE', '0.3')),
            'scan_frequency': int(os.getenv('SCAN_FREQUENCY', '300'))  # 5 minutes
        }
        
        # Dynamic thresholds (can be adjusted via tool)
        self.dynamic_thresholds = {
            'min_momentum_score': 50,
            'min_volume_ratio': 1.5,
            'min_price_change': 0.02,
            'max_spread_pct': 1.0
        }
        
        # Blacklisted symbols
        self.blacklisted_symbols: Set[str] = set()
        
        # Scan history for performance tracking
        self.scan_history = []
        self.max_history_size = 100
        
        # Default universe of stocks to scan
        self.default_universe = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM',
            'JNJ', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'PYPL', 'BAC', 'NFLX',
            'ADBE', 'CRM', 'XOM', 'VZ', 'CMCSA', 'PFE', 'INTC', 'CSCO', 'T',
            'PEP', 'ABT', 'CVX', 'NKE', 'WMT', 'TMO', 'ABBV', 'MRK', 'LLY',
            'COST', 'ORCL', 'ACN', 'MDT', 'DHR', 'TXN', 'NEE', 'HON', 'UNP',
            'PM', 'IBM', 'QCOM', 'LOW', 'LIN', 'AMD', 'GS', 'SBUX', 'CAT',
            'CVS', 'AMT', 'INTU', 'AXP', 'BLK', 'CHTR', 'BA', 'ISRG', 'SPGI',
            'GILD', 'ZTS', 'TGT', 'MMM', 'BKNG', 'MDLZ', 'MO', 'PLD', 'CI',
            'SYK', 'CB', 'DE', 'DUK', 'CL', 'SHW', 'FIS', 'BDX', 'SO', 'ITW',
            'BSX', 'MMC', 'TJX', 'USB', 'PNC', 'CSX', 'RTX', 'NSC', 'MS',
            'SCHW', 'EL', 'ADP', 'CME', 'VRTX', 'HUM', 'LRCX', 'ATVI'
        ]
        
        # Register MCP endpoints
        self._register_resources()
        self._register_tools()
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    async def initialize(self):
        """Initialize async components"""
        # Initialize database client
        # self.db_client = MCPDatabaseClient(
        os.getenv('DATABASE_MCP_URL', 'ws://database-service:5010')
    )
        # await self.db_client.connect()
        
        # Initialize Redis
        self.redis_client = await redis.from_url(
            os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
            decode_responses=True
        )
        
        # Load configuration
        await self._load_configuration()
        
        self.logger.info("Scanner service initialized",
                        database_connected=True,
                        redis_connected=True,
                        blacklisted=len(self.blacklisted_symbols))
    
    async def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            await self.redis_client.close()
            
        if self.db_client:
            # await self.db_client.disconnect()
    
    async def _load_configuration(self):
        """Load saved configuration from cache"""
        try:
            # Load blacklisted symbols
            blacklist = await self.redis_client.smembers("scanner:blacklisted_symbols")
            self.blacklisted_symbols = set(blacklist) if blacklist else set()
            
            # Load dynamic thresholds
            thresholds = await self.redis_client.get("scanner:dynamic_thresholds")
            if thresholds:
                self.dynamic_thresholds.update(json.loads(thresholds))
                
        except Exception as e:
            self.logger.warning("Failed to load configuration", error=str(e))
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.mcp.resource("http://candidates/active")
        async def get_active_candidates() -> Dict:
            """Get currently active trading candidates"""
            # Get from cache
            cached = await self.redis_client.get("scanner:latest_candidates")
            
            if cached:
                candidates = json.loads(cached)
            else:
                candidates = []
            
            # Add metadata
            for candidate in candidates:
                candidate['blacklisted'] = candidate.get('symbol') in self.blacklisted_symbols
            
            return {
                'type': 'candidate_list',
                'data': {'candidates': candidates},
                'metadata': {
                    'count': len(candidates),
                    'cached': cached is not None,
                    'max_candidates': self.scanner_config['max_candidates']
                }
            }
        
        @self.mcp.resource("http://candidates/rejected")
        async def get_rejected_candidates() -> Dict:
            """Get recently rejected candidates with rejection reasons"""
            hours = 1  # Default
            limit = 50  # Default
            
            # Get from cache
            cache_key = f"scanner:rejected_candidates:{hours}h"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                rejected = json.loads(cached)
            else:
                rejected = []
            
            return {
                'type': 'rejected_candidates',
                'data': {'rejected': rejected[:limit]},
                'metadata': {
                    'count': len(rejected),
                    'hours': hours,
                    'reasons': self._get_rejection_reason_summary(rejected)
                }
            }
        
        @self.mcp.resource("http://scanner/history")
        async def get_scan_history() -> Dict:
            """Get scanner execution history"""
            limit = 20  # Default
            include_candidates = False  # Default
            
            # Get recent history
            history = self.scan_history[-limit:]
            
            # Optionally remove candidate details to reduce size
            if not include_candidates:
                history = [
                    {k: v for k, v in scan.items() if k != 'candidates'}
                    for scan in history
                ]
            
            return {
                'type': 'scan_history',
                'data': {'history': history},
                'metadata': {
                    'total_scans': len(self.scan_history),
                    'returned': len(history)
                }
            }
        
        @self.mcp.resource("http://scanner/performance")
        async def get_scanner_performance() -> Dict:
            """Get scanner performance metrics"""
            timeframe = '24h'  # Default
            
            # Calculate performance metrics
            performance = await self._calculate_performance_metrics(timeframe)
            
            return {
                'type': 'scanner_performance',
                'data': performance,
                'metadata': {'timeframe': timeframe}
            }
        
        @self.mcp.resource("http://market/movers")
        async def get_market_movers() -> Dict:
            """Get top market movers"""
            mover_type = 'gainers'  # Default
            limit = 10  # Default
            
            # Get market data
            movers = await self._get_market_movers(mover_type, limit)
            
            return {
                'type': 'market_movers',
                'data': {
                    'type': mover_type,
                    'movers': movers
                },
                'metadata': {'timestamp': datetime.now().isoformat()}
            }
        
        @self.mcp.resource("http://scanner/thresholds")
        async def get_scanner_thresholds() -> Dict:
            """Get current scanner thresholds"""
            return {
                'type': 'scanner_thresholds',
                'data': {
                    'static': self.scanner_config,
                    'dynamic': self.dynamic_thresholds
                },
                'metadata': {'adjustable': list(self.dynamic_thresholds.keys())}
            }
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.mcp.tool("scan_market")
        async def scan_market(params: dict) -> Dict:
            """Perform market scan for trading candidates"""
            mode = params.get('mode', 'normal')
            news_context = params.get('news_context', {})
            force = params.get('force', False)
            max_candidates = params.get('max_candidates', self.scanner_config['max_candidates'])
            
            try:
                # Check if we should skip (unless forced)
                if not force:
                    last_scan = await self.redis_client.get("scanner:last_scan_time")
                    if last_scan:
                        last_scan_time = datetime.fromisoformat(last_scan)
                        time_since = (datetime.now() - last_scan_time).total_seconds()
                        if time_since < self.scanner_config['scan_frequency']:
                            return {
                                'success': False,
                                'error': f"Scan frequency limit. Next scan in {self.scanner_config['scan_frequency'] - time_since:.0f} seconds"
                            }
                
                # Start scan
                scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                scan_start = datetime.now()
                
                self.logger.info("Starting market scan",
                               scan_id=scan_id,
                               mode=mode,
                               max_candidates=max_candidates)
                
                # Get market movers
                symbols = await self._get_scan_universe(mode, news_context)
                
                # Filter blacklisted symbols
                symbols = [s for s in symbols if s not in self.blacklisted_symbols]
                
                # Scan symbols
                candidates = await self._scan_symbols(symbols, news_context)
                
                # Sort by score
                candidates.sort(key=lambda x: x['score'], reverse=True)
                
                # Limit to max candidates
                candidates = candidates[:max_candidates]
                
                # Add rank
                for i, candidate in enumerate(candidates):
                    candidate['rank'] = i + 1
                    candidate['scan_id'] = scan_id
                
                # Calculate scan duration
                scan_duration = (datetime.now() - scan_start).total_seconds()
                
                # Save scan results
                scan_result = {
                    'scan_id': scan_id,
                    'timestamp': scan_start.isoformat(),
                    'mode': mode,
                    'symbols_scanned': len(symbols),
                    'candidates_found': len(candidates),
                    'duration': scan_duration,
                    'thresholds': self.dynamic_thresholds.copy()
                }
                
                # Persist to database
                # await self.db_client.persist_scan_results({
                    'scan_id': scan_id,
                    'timestamp': scan_start,
                    'candidates': candidates,
                    'metadata': scan_result
                })
                
                # Cache results
                await self.redis_client.setex(
                    "scanner:latest_candidates",
                    self.scanner_config['scan_frequency'],
                    json.dumps(candidates)
                )
                await self.redis_client.set(
                    "scanner:last_scan_time",
                    datetime.now().isoformat()
                )
                
                # Add to history
                scan_result['candidates'] = candidates
                self.scan_history.append(scan_result)
                if len(self.scan_history) > self.max_history_size:
                    self.scan_history.pop(0)
                
                # Log top candidates
                for candidate in candidates[:5]:
                    self.logger.info("Top candidate found",
                                   rank=candidate['rank'],
                                   symbol=candidate['symbol'],
                                   score=candidate['score'])
                
                return {
                    'success': True,
                    'data': {
                        'scan_id': scan_id,
                        'candidates': candidates,
                        'summary': {
                            'symbols_scanned': len(symbols),
                            'candidates_found': len(candidates),
                            'top_score': candidates[0]['score'] if candidates else 0,
                            'duration': scan_duration
                        }
                    }
                }
                
            except Exception as e:
                self.logger.error("Market scan failed", error=str(e))
                return {
                    'success': False,
                    'error': str(e)
                }
        
        @self.mcp.tool("force_rescan")
        async def force_rescan(params: dict) -> Dict:
            """Force an immediate market rescan"""
            reason = params.get('reason', 'manual_trigger')
            clear_cache = params.get('clear_cache', True)
            
            try:
                # Clear cache if requested
                if clear_cache:
                    await self.redis_client.delete(
                        "scanner:latest_candidates",
                        "scanner:last_scan_time"
                    )
                
                # Run scan with force flag
                scan_result = await scan_market({
                    'mode': 'forced',
                    'force': True,
                    'news_context': {'reason': reason}
                })
                
                if scan_result.get('success'):
                    return {
                        'success': True,
                        'data': {
                            'scan_id': scan_result['data']['scan_id'],
                            'candidates_found': scan_result['data']['summary']['candidates_found'],
                            'reason': reason
                        }
                    }
                else:
                    return scan_result
                    
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        
        @self.mcp.tool("blacklist_symbol")
        async def blacklist_symbol(params: dict) -> Dict:
            """Add or remove symbol from blacklist"""
            symbol = params['symbol'].upper()
            action = params.get('action', 'add')  # add or remove
            reason = params.get('reason', '')
            
            try:
                if action == 'add':
                    self.blacklisted_symbols.add(symbol)
                    await self.redis_client.sadd("scanner:blacklisted_symbols", symbol)
                    
                    # Log blacklisting
                    self.logger.warning("Symbol blacklisted",
                                      symbol=symbol,
                                      reason=reason)
                    
                    # Remove from current candidates if present
                    cached = await self.redis_client.get("scanner:latest_candidates")
                    if cached:
                        candidates = json.loads(cached)
                        candidates = [c for c in candidates if c['symbol'] != symbol]
                        await self.redis_client.setex(
                            "scanner:latest_candidates",
                            self.scanner_config['scan_frequency'],
                            json.dumps(candidates)
                        )
                    
                elif action == 'remove':
                    self.blacklisted_symbols.discard(symbol)
                    await self.redis_client.srem("scanner:blacklisted_symbols", symbol)
                    
                    self.logger.info("Symbol removed from blacklist",
                                   symbol=symbol)
                
                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'action': action,
                        'blacklisted': symbol in self.blacklisted_symbols,
                        'total_blacklisted': len(self.blacklisted_symbols)
                    }
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        
        @self.mcp.tool("adjust_thresholds")
        async def adjust_thresholds(params: dict) -> Dict:
            """Adjust dynamic scanner thresholds"""
            threshold_name = params['threshold_name']
            new_value = params['new_value']
            
            try:
                if threshold_name not in self.dynamic_thresholds:
                    return {
                        'success': False,
                        'error': f"Unknown threshold: {threshold_name}"
                    }
                
                # Validate value
                if threshold_name == 'min_momentum_score':
                    new_value = max(0, min(100, float(new_value)))
                elif threshold_name in ['min_volume_ratio', 'min_price_change', 'max_spread_pct']:
                    new_value = max(0, float(new_value))
                
                # Update threshold
                old_value = self.dynamic_thresholds[threshold_name]
                self.dynamic_thresholds[threshold_name] = new_value
                
                # Save to cache
                await self.redis_client.set(
                    "scanner:dynamic_thresholds",
                    json.dumps(self.dynamic_thresholds)
                )
                
                self.logger.info("Threshold adjusted",
                               threshold=threshold_name,
                               old_value=old_value,
                               new_value=new_value)
                
                return {
                    'success': True,
                    'data': {
                        'threshold': threshold_name,
                        'old_value': old_value,
                        'new_value': new_value,
                        'all_thresholds': self.dynamic_thresholds
                    }
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        
        @self.mcp.tool("analyze_candidate")
        async def analyze_candidate(params: dict) -> Dict:
            """Deep analysis of a specific candidate"""
            symbol = params['symbol'].upper()
            include_technicals = params.get('include_technicals', True)
            include_news = params.get('include_news', True)
            
            try:
                analysis = {}
                
                # Get market data
                market_data = await self._get_symbol_data(symbol)
                analysis['market_data'] = market_data
                
                # Calculate scores
                analysis['scores'] = {
                    'momentum': self._calculate_momentum_score(market_data),
                    'volume': self._calculate_volume_score(market_data),
                    'catalyst': 0  # Will be updated if news included
                }
                
                # Get news if requested
                if include_news:
                    news_data = await self._get_symbol_news(symbol)
                    analysis['news'] = news_data
                    analysis['scores']['catalyst'] = news_data.get('catalyst_score', 0)
                
                # Technical indicators if requested
                if include_technicals:
                    technicals = await self._calculate_technicals(symbol)
                    analysis['technicals'] = technicals
                
                # Overall score
                analysis['overall_score'] = self._calculate_overall_score(analysis['scores'])
                
                # Recommendation
                if symbol in self.blacklisted_symbols:
                    analysis['recommendation'] = 'blacklisted'
                elif analysis['overall_score'] >= self.dynamic_thresholds['min_momentum_score']:
                    analysis['recommendation'] = 'candidate'
                else:
                    analysis['recommendation'] = 'monitor'
                
                return {
                    'success': True,
                    'data': analysis
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        
        @self.mcp.tool("clear_cache")
        async def clear_cache(params: dict) -> Dict:
            """Clear scanner cache"""
            pattern = params.get("pattern", "scanner:*")
            
            try:
                # Get all matching keys
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                
                # Delete keys
                if keys:
                    await self.redis_client.delete(*keys)
                
                return {
                    'success': True,
                    'data': {
                        "cleared": len(keys),
                        "pattern": pattern
                    }
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
    
    async def _get_scan_universe(self, mode: str, news_context: Dict) -> List[str]:
        """Get universe of symbols to scan"""
        symbols = set(self.default_universe)
        
        # Add trending symbols from news
        if news_context.get('trending_symbols'):
            symbols.update(news_context['trending_symbols'])
        
        # Get market movers
        try:
            movers = await self._get_market_movers_async()
            symbols.update(movers)
        except Exception as e:
            self.logger.warning("Failed to get market movers", error=str(e))
        
        return list(symbols)
    
    async def _scan_symbols(self, symbols: List[str], news_context: Dict) -> List[Dict]:
        """Scan multiple symbols and score them"""
        candidates = []
        
        # Batch process symbols
        batch_size = 20
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            
            # Process batch in parallel
            tasks = [self._scan_symbol(symbol, news_context) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter valid results
            for result in results:
                if isinstance(result, dict) and result.get('score', 0) >= self.dynamic_thresholds['min_momentum_score']:
                    candidates.append(result)
        
        return candidates
    
    async def _scan_symbol(self, symbol: str, news_context: Dict) -> Optional[Dict]:
        """Scan individual symbol"""
        try:
            # Get market data
            data = await self._get_symbol_data(symbol)
            if not data:
                return None
            
            # Apply filters
            if not self._apply_filters(data):
                return None
            
            # Calculate scores
            momentum_score = self._calculate_momentum_score(data)
            volume_score = self._calculate_volume_score(data)
            
            # Get catalyst score from news
            catalyst_score = 0
            catalyst_data = {}
            if symbol in news_context.get('symbol_catalysts', {}):
                catalyst_data = news_context['symbol_catalysts'][symbol]
                catalyst_score = catalyst_data.get('score', 0) * 30  # Weight catalyst
            
            # Overall score
            overall_score = (momentum_score * 0.4 + 
                           volume_score * 0.3 + 
                           catalyst_score * 0.3)
            
            return {
                'symbol': symbol,
                'score': round(overall_score, 2),
                'momentum_score': round(momentum_score, 2),
                'volume_score': round(volume_score, 2),
                'catalyst_score': round(catalyst_score, 2),
                'price': data.get('price'),
                'price_change_pct': data.get('price_change_pct'),
                'volume': data.get('volume'),
                'relative_volume': data.get('relative_volume'),
                'market_cap': data.get('market_cap'),
                'catalyst_data': catalyst_data,
                'scan_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.debug(f"Error scanning {symbol}: {str(e)}")
            return None
    
    async def _get_symbol_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for symbol"""
        try:
            # Check cache first
            cache_key = f"scanner:symbol_data:{symbol}"
            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Fetch from yfinance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get current data
            hist = ticker.history(period="5d")
            if hist.empty:
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            
            # Calculate metrics
            data = {
                'symbol': symbol,
                'price': round(current_price, 2),
                'prev_close': round(prev_close, 2),
                'price_change': round(current_price - prev_close, 2),
                'price_change_pct': round((current_price - prev_close) / prev_close * 100, 2),
                'volume': int(hist['Volume'].iloc[-1]),
                'avg_volume': int(hist['Volume'].mean()),
                'relative_volume': round(hist['Volume'].iloc[-1] / hist['Volume'].mean(), 2),
                'high': round(hist['High'].iloc[-1], 2),
                'low': round(hist['Low'].iloc[-1], 2),
                'market_cap': info.get('marketCap', 0),
                'float': info.get('floatShares', 0),
                'short_ratio': info.get('shortRatio', 0),
                'beta': info.get('beta', 1),
                'pe_ratio': info.get('forwardPE', 0),
                'rsi_14': self._calculate_rsi(hist['Close'], 14),
                'sma_20': round(hist['Close'].rolling(window=20).mean().iloc[-1], 2) if len(hist) >= 20 else current_price,
                'spread_pct': round((info.get('ask', current_price) - info.get('bid', current_price)) / current_price * 100, 2) if info.get('ask') and info.get('bid') else 0
            }
            
            # Cache for 1 minute
            await self.redis_client.setex(cache_key, 60, json.dumps(data))
            
            return data
            
        except Exception as e:
            self.logger.debug(f"Error getting data for {symbol}: {str(e)}")
            return None
    
    def _apply_filters(self, data: Dict) -> bool:
        """Apply basic filters to symbol data"""
        # Price filter
        if data['price'] < self.scanner_config['min_price'] or data['price'] > self.scanner_config['max_price']:
            return False
        
        # Volume filter
        if data['volume'] < self.scanner_config['min_volume']:
            return False
        
        # Spread filter
        if data.get('spread_pct', 0) > self.dynamic_thresholds['max_spread_pct']:
            return False
        
        # Price change filter
        if abs(data.get('price_change_pct', 0)) < self.dynamic_thresholds['min_price_change'] * 100:
            return False
        
        return True
    
    def _calculate_momentum_score(self, data: Dict) -> float:
        """Calculate momentum score (0-100)"""
        score = 0
        
        # Price change component (0-40 points)
        price_change = abs(data.get('price_change_pct', 0))
        if price_change > 5:
            score += 40
        elif price_change > 3:
            score += 30
        elif price_change > 2:
            score += 20
        elif price_change > 1:
            score += 10
        
        # RSI component (0-30 points)
        rsi = data.get('rsi_14')
        if rsi:
            if rsi > 70 or rsi < 30:  # Overbought/oversold
                score += 30
            elif rsi > 60 or rsi < 40:
                score += 20
            elif rsi > 55 or rsi < 45:
                score += 10
        
        # Price vs SMA component (0-30 points)
        if data.get('sma_20'):
            price_vs_sma = (data['price'] - data['sma_20']) / data['sma_20'] * 100
            if abs(price_vs_sma) > 5:
                score += 30
            elif abs(price_vs_sma) > 3:
                score += 20
            elif abs(price_vs_sma) > 1:
                score += 10
        
        return min(score, 100)
    
    def _calculate_volume_score(self, data: Dict) -> float:
        """Calculate volume score (0-100)"""
        score = 0
        
        # Relative volume component (0-60 points)
        rel_volume = data.get('relative_volume', 1)
        if rel_volume > 3:
            score += 60
        elif rel_volume > 2:
            score += 40
        elif rel_volume > 1.5:
            score += 20
        
        # Absolute volume component (0-40 points)
        volume = data.get('volume', 0)
        if volume > 10000000:
            score += 40
        elif volume > 5000000:
            score += 30
        elif volume > 2000000:
            score += 20
        elif volume > 1000000:
            score += 10
        
        return min(score, 100)
    
    def _calculate_overall_score(self, scores: Dict) -> float:
        """Calculate weighted overall score"""
        weights = {
            'momentum': 0.4,
            'volume': 0.3,
            'catalyst': 0.3
        }
        
        total = sum(scores.get(k, 0) * v for k, v in weights.items())
        return round(total, 2)
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> Optional[float]:
        """Calculate RSI indicator"""
        try:
            if len(prices) < period + 1:
                return None
            
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None
        except:
            return None
    
    async def _get_symbol_news(self, symbol: str) -> Dict:
        """Get news data for symbol from news service"""
        try:
            # In production, would call news service MCP
            # For now, return mock data
            return {
                'article_count': 3,
                'sentiment': 'positive',
                'catalyst_score': 0.7,
                'latest_headline': f"Breaking: {symbol} announces major development"
            }
        except:
            return {}
    
    async def _calculate_technicals(self, symbol: str) -> Dict:
        """Calculate technical indicators"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            
            if hist.empty:
                return {}
            
            close = hist['Close']
            
            return {
                'sma_20': round(close.rolling(window=20).mean().iloc[-1], 2) if len(close) >= 20 else None,
                'sma_50': round(close.rolling(window=50).mean().iloc[-1], 2) if len(close) >= 50 else None,
                'rsi_14': self._calculate_rsi(close, 14),
                'volatility': round(close.pct_change().std() * np.sqrt(252) * 100, 2),  # Annualized
                'trend': 'up' if close.iloc[-1] > close.iloc[-5] else 'down'
            }
        except:
            return {}
    
    async def _get_market_movers(self, mover_type: str, limit: int) -> List[Dict]:
        """Get market movers"""
        # In production, would use Alpaca API
        # For now, return top symbols by type
        if mover_type == 'gainers':
            return [{'symbol': s, 'change_pct': 5.0} for s in self.default_universe[:limit]]
        elif mover_type == 'losers':
            return [{'symbol': s, 'change_pct': -5.0} for s in self.default_universe[-limit:]]
        else:  # volume
            return [{'symbol': s, 'volume': 10000000} for s in self.default_universe[:limit]]
    
    async def _get_market_movers_async(self) -> List[str]:
        """Get market movers asynchronously"""
        # Start with default universe
        movers = list(self.default_universe)
        
        # In production, would fetch from Alpaca API
        # Try to get trending from news service
        try:
            # Would call news service for trending symbols
            pass
        except:
            pass
        
        return movers[:50]  # Top 50
    
    def _get_rejection_reason_summary(self, rejected: List[Dict]) -> Dict:
        """Summarize rejection reasons"""
        reasons = {}
        for item in rejected:
            reason = item.get('rejection_reason', 'unknown')
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
    
    async def _calculate_performance_metrics(self, timeframe: str) -> Dict:
        """Calculate scanner performance metrics"""
        # In production, would query from database
        # For now, return calculated metrics from history
        
        total_scans = len(self.scan_history)
        if total_scans == 0:
            return {
                'scans_executed': 0,
                'avg_candidates_per_scan': 0,
                'avg_scan_duration': 0,
                'top_performing_sectors': [],
                'success_rate': 0
            }
        
        avg_candidates = sum(s['candidates_found'] for s in self.scan_history) / total_scans
        avg_duration = sum(s['duration'] for s in self.scan_history) / total_scans
        
        return {
            'scans_executed': total_scans,
            'avg_candidates_per_scan': round(avg_candidates, 1),
            'avg_scan_duration': round(avg_duration, 2),
            'top_performing_sectors': ['Technology', 'Healthcare', 'Finance'],  # Mock
            'success_rate': 0.73,  # Mock
            'threshold_effectiveness': {
                'momentum': 0.82,
                'volume': 0.76,
                'catalyst': 0.91
            }
        }
    
    async def health_check(self) -> Dict:
        """Service health check"""
        try:
            # Check database connection
            db_status = # await self.db_client.get_database_status()
            
            # Check Redis connection
            redis_ok = await self.redis_client.ping() if self.redis_client else False
            
            # Check last scan time
            last_scan = await self.redis_client.get("scanner:last_scan_time")
            time_since_scan = None
            if last_scan:
                last_scan_time = datetime.fromisoformat(last_scan)
                time_since_scan = (datetime.now() - last_scan_time).total_seconds()
            
            return {
                'status': 'healthy',
                'database': db_status.get('postgresql', {}).get('status', 'unknown'),
                'redis': 'healthy' if redis_ok else 'unhealthy',
                'last_scan': last_scan,
                'time_since_scan': time_since_scan,
                'blacklisted_symbols': len(self.blacklisted_symbols),
                'scan_history_size': len(self.scan_history)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Security Scanner MCP Server",
                        version="4.1.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Run server with stdio transport
        await stdio_server(self.mcp).run()


async def main():
    """Main entry point"""
    server = ScannerMCPServer()
    
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