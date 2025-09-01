#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 3.0.0
Last Updated: 2025-08-18
Purpose: MCP-enabled technical pattern detection with catalyst awareness

REVISION HISTORY:
v3.0.0 (2024-12-30) - Complete MCP migration
- Converted from Flask REST to MCP protocol
- Resources for pattern data access
- Tools for pattern detection and updates
- Focus on TOP 5 candidates only
- Enhanced catalyst alignment scoring
- MCP session support for workflows

Description of Service:
MCP server for pattern detection that understands news catalysts.
Exposes pattern analysis capabilities through MCP resources and tools,
enabling Claude and other AI assistants to discover trading patterns.
"""

import os
import json
import time
import asyncio
import logging
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from structlog import get_logger
import redis

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import database utilities
from database_utils import (
    get_db_connection,
    health_check,
    log_workflow_step
)

# Handle technical analysis library imports
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("⚠️ TA-Lib not available, using manual calculations")

# Handle yfinance import
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not available, using mock data")


class PatternAnalysisMCPServer:
    """
    MCP Server for catalyst-aware pattern analysis
    """
    
    def __init__(self):
        # Initialize environment
        self.setup_environment()
        
        # Initialize MCP server
        self.server = MCPServer("pattern-analysis")
        self.setup_logging()
        
        # Initialize Redis client
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_password = os.getenv('REDIS_PASSWORD')
        if redis_password and 'localhost' in redis_url:
            redis_url = f'redis://:{redis_password}@localhost:6379/0'
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        
        # Pattern configuration with catalyst weights
        self.pattern_config = self._load_pattern_config()
        
        # Pre-market multiplier
        self.premarket_multiplier = float(os.getenv('PREMARKET_MULTIPLIER', '2.0'))
        
        # Cache settings
        self.cache_ttl = int(os.getenv('PATTERN_CACHE_TTL', '300'))  # 5 minutes
        
        # Register MCP resources and tools
        self._register_resources()
        self._register_tools()
        
        self.logger.info("Pattern Analysis MCP Server v3.0.0 initialized",
                        environment=os.getenv('ENVIRONMENT', 'development'),
                        talib_available=TALIB_AVAILABLE)
        
    def setup_environment(self):
        """Setup environment variables and paths"""
        # Paths
        self.log_path = os.getenv('LOG_PATH', '/app/logs')
        self.data_path = os.getenv('DATA_PATH', '/app/data')
        
        # Create directories
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(self.data_path, exist_ok=True)
        
        # Service configuration
        self.service_name = 'pattern-analysis-mcp'
        self.port = int(os.getenv('PORT', '5002'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Pattern detection parameters
        self.min_confidence = float(os.getenv('MIN_PATTERN_CONFIDENCE', '60'))
        self.lookback_periods = int(os.getenv('PATTERN_LOOKBACK_PERIODS', '20'))
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("patterns/by-symbol/{symbol}")
        async def get_patterns_by_symbol(params: ResourceParams) -> ResourceResponse:
            """Get detected patterns for a specific symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            min_confidence = params.get("min_confidence", self.min_confidence)
            catalyst_required = params.get("catalyst_required", False)
            
            # Check cache first
            cache_key = f"pattern:{symbol}:{timeframe}"
            cached = self.redis_client.get(cache_key)
            if cached:
                patterns = json.loads(cached)
            else:
                # Get from database
                patterns = await self._get_patterns_from_db(
                    symbol, timeframe, min_confidence, catalyst_required
                )
            
            return ResourceResponse(
                type="pattern_collection",
                data=patterns,
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "count": len(patterns)
                }
            )
        
        @self.server.resource("patterns/statistics")
        async def get_pattern_statistics(params: ResourceParams) -> ResourceResponse:
            """Get pattern success statistics"""
            pattern_types = params.get("pattern_types", [])
            with_catalyst = params.get("with_catalyst", None)
            timeframe = params.get("timeframe", "7d")
            
            stats = await self._calculate_pattern_statistics(
                pattern_types, with_catalyst, timeframe
            )
            
            return ResourceResponse(
                type="pattern_stats",
                data=stats,
                metadata={
                    "timeframe": timeframe,
                    "total_patterns": sum(s["total_detected"] for s in stats)
                }
            )
        
        @self.server.resource("patterns/success-rates/catalyst-aligned")
        async def get_catalyst_aligned_success_rates(params: ResourceParams) -> ResourceResponse:
            """Get success rates for catalyst-aligned patterns"""
            pattern_type = params.get("pattern_type")
            catalyst_type = params.get("catalyst_type")
            
            success_data = await self._get_catalyst_aligned_success_rates(
                pattern_type, catalyst_type
            )
            
            return ResourceResponse(
                type="pattern_success_rates",
                data=success_data
            )
        
        @self.server.resource("patterns/detected/recent")
        async def get_recent_patterns(params: ResourceParams) -> ResourceResponse:
            """Get recently detected patterns across all symbols"""
            limit = params.get("limit", 50)
            min_confidence = params.get("min_confidence", self.min_confidence)
            
            patterns = await self._get_recent_patterns(limit, min_confidence)
            
            return ResourceResponse(
                type="recent_patterns",
                data=patterns,
                metadata={
                    "count": len(patterns),
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("detect_patterns_for_candidates")
        async def detect_patterns_for_candidates(params: ToolParams) -> ToolResponse:
            """Detect patterns for TOP 5 trading candidates only"""
            scan_id = params.get("scan_id")
            candidates = params.get("candidates", [])
            
            if len(candidates) > 5:
                candidates = candidates[:5]  # Enforce TOP 5 limit
            
            self.logger.info(f"Detecting patterns for {len(candidates)} candidates",
                           scan_id=scan_id)
            
            results = {
                "analyzed_symbols": len(candidates),
                "patterns_detected": {},
                "skipped_symbols": 0
            }
            
            for symbol in candidates:
                try:
                    # Get catalyst context for symbol
                    context = await self._get_symbol_context(symbol, scan_id)
                    
                    # Detect patterns
                    patterns = await self._analyze_with_catalyst_context(
                        symbol, "5m", context
                    )
                    
                    if patterns:
                        results["patterns_detected"][symbol] = [
                            p["pattern_name"] for p in patterns
                        ]
                        
                except Exception as e:
                    self.logger.error(f"Error detecting patterns for {symbol}", 
                                    error=str(e))
            
            return ToolResponse(
                success=True,
                data=results,
                metadata={
                    "scan_id": scan_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.server.tool("analyze_pattern")
        async def analyze_pattern(params: ToolParams) -> ToolResponse:
            """Analyze patterns for a specific symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            catalyst_context = params.get("catalyst_context", {})
            
            patterns = await self._analyze_with_catalyst_context(
                symbol, timeframe, catalyst_context
            )
            
            return ToolResponse(
                success=True,
                data={
                    "symbol": symbol,
                    "patterns": patterns,
                    "pattern_count": len(patterns)
                }
            )
        
        @self.server.tool("record_pattern_detection")
        async def record_pattern_detection(params: ToolParams) -> ToolResponse:
            """Record a pattern detection to database"""
            pattern_data = {
                "symbol": params["symbol"],
                "pattern_type": params["pattern_type"],
                "confidence": params["confidence"],
                "timeframe": params.get("timeframe", "5m"),
                "pattern_data": params.get("pattern_data", {}),
                "catalyst_context": params.get("catalyst_context", {})
            }
            
            pattern_id = await self._save_pattern_detection(pattern_data)
            
            return ToolResponse(
                success=True,
                data={
                    "pattern_id": pattern_id,
                    "created": True
                }
            )
        
        @self.server.tool("update_pattern_outcome")
        async def update_pattern_outcome(params: ToolParams) -> ToolResponse:
            """Update pattern with actual trading outcome"""
            pattern_id = params["pattern_id"]
            pattern_completed = params["pattern_completed"]
            actual_move = params.get("actual_move", 0)
            success = params["success"]
            
            updated = await self._update_pattern_outcome_db(
                pattern_id, pattern_completed, actual_move, success
            )
            
            return ToolResponse(
                success=updated,
                data={
                    "pattern_id": pattern_id,
                    "updated": updated
                }
            )
        
        @self.server.tool("validate_pattern")
        async def validate_pattern(params: ToolParams) -> ToolResponse:
            """Validate a detected pattern against historical data"""
            pattern_type = params["pattern_type"]
            symbol = params["symbol"]
            catalyst_type = params.get("catalyst_type")
            
            validation = await self._validate_pattern(
                pattern_type, symbol, catalyst_type
            )
            
            return ToolResponse(
                success=True,
                data=validation
            )

    def _load_pattern_config(self) -> Dict:
        """Load pattern configuration with environment overrides"""
        return {
            'reversal_patterns': {
                'hammer': {
                    'base_confidence': float(os.getenv('HAMMER_BASE_CONFIDENCE', '65')),
                    'catalyst_boost': {
                        'positive': 1.5,
                        'negative': 0.7,
                        'neutral': 1.0
                    },
                    'min_shadow_ratio': 2.0
                },
                'shooting_star': {
                    'base_confidence': float(os.getenv('SHOOTING_STAR_BASE_CONFIDENCE', '65')),
                    'catalyst_boost': {
                        'positive': 0.7,
                        'negative': 1.5,
                        'neutral': 1.0
                    },
                    'min_shadow_ratio': 2.0
                },
                'engulfing': {
                    'base_confidence': float(os.getenv('ENGULFING_BASE_CONFIDENCE', '70')),
                    'catalyst_boost': {
                        'positive': 1.4,
                        'negative': 1.4,
                        'neutral': 1.0
                    }
                },
                'doji': {
                    'base_confidence': float(os.getenv('DOJI_BASE_CONFIDENCE', '55')),
                    'catalyst_boost': {
                        'positive': 1.3,
                        'negative': 1.3,
                        'neutral': 1.0
                    },
                    'max_body_ratio': 0.1
                }
            },
            'continuation_patterns': {
                'three_white_soldiers': {
                    'base_confidence': float(os.getenv('THREE_WHITE_BASE_CONFIDENCE', '75')),
                    'catalyst_boost': {
                        'positive': 1.6,
                        'negative': 0.5,
                        'neutral': 1.0
                    }
                },
                'three_black_crows': {
                    'base_confidence': float(os.getenv('THREE_BLACK_BASE_CONFIDENCE', '75')),
                    'catalyst_boost': {
                        'positive': 0.5,
                        'negative': 1.6,
                        'neutral': 1.0
                    }
                }
            },
            'momentum_patterns': {
                'gap_up': {
                    'base_confidence': float(os.getenv('GAP_UP_BASE_CONFIDENCE', '60')),
                    'catalyst_boost': {
                        'positive': 1.7,
                        'negative': 0.4,
                        'neutral': 1.0
                    },
                    'min_gap_percent': 1.0
                },
                'gap_down': {
                    'base_confidence': float(os.getenv('GAP_DOWN_BASE_CONFIDENCE', '60')),
                    'catalyst_boost': {
                        'positive': 0.4,
                        'negative': 1.7,
                        'neutral': 1.0
                    },
                    'min_gap_percent': 1.0
                },
                'volume_surge': {
                    'base_confidence': float(os.getenv('VOLUME_SURGE_BASE_CONFIDENCE', '50')),
                    'catalyst_boost': {
                        'positive': 1.5,
                        'negative': 1.5,
                        'neutral': 1.0
                    },
                    'min_volume_ratio': 2.0
                }
            }
        }

    async def _analyze_with_catalyst_context(self, symbol: str, timeframe: str, 
                                           context: Dict) -> List[Dict]:
        """Analyze patterns with catalyst awareness"""
        self.logger.info(f"Analyzing {symbol} with catalyst context",
                        symbol=symbol,
                        timeframe=timeframe,
                        has_context=bool(context))
        
        # Get price data
        price_data = await self._get_price_data(symbol, timeframe)
        if price_data is None or len(price_data) < self.lookback_periods:
            return []
            
        # Extract catalyst information
        catalyst_info = self._extract_catalyst_info(context)
        
        # Detect patterns
        detected_patterns = []
        
        # Check all pattern types
        for pattern_category in ['reversal_patterns', 'continuation_patterns', 'momentum_patterns']:
            for pattern_name, config in self.pattern_config[pattern_category].items():
                pattern = await self._detect_pattern(
                    price_data, pattern_name, config, catalyst_info, pattern_category
                )
                if pattern and pattern['final_confidence'] >= self.min_confidence:
                    detected_patterns.append(pattern)
                    
        # Sort by confidence
        detected_patterns.sort(key=lambda x: x['final_confidence'], reverse=True)
        
        # Save top patterns to database
        for pattern in detected_patterns[:5]:  # Top 5 patterns
            await self._save_pattern_detection({
                "symbol": symbol,
                "pattern_type": pattern['pattern_name'],
                "confidence": pattern['final_confidence'],
                "timeframe": timeframe,
                "pattern_data": pattern,
                "catalyst_context": catalyst_info
            })
            
        return detected_patterns[:5]  # Return top 5

    async def _detect_pattern(self, data: pd.DataFrame, pattern_name: str,
                            config: Dict, catalyst_info: Dict, 
                            pattern_category: str) -> Optional[Dict]:
        """Generic pattern detection with catalyst weighting"""
        
        # Delegate to specific detection methods based on category
        if pattern_category == 'reversal_patterns':
            return self._detect_reversal_pattern(data, pattern_name, config, catalyst_info)
        elif pattern_category == 'continuation_patterns':
            return self._detect_continuation_pattern(data, pattern_name, config, catalyst_info)
        elif pattern_category == 'momentum_patterns':
            return self._detect_momentum_pattern(data, pattern_name, config, catalyst_info)
        
        return None

    def _detect_reversal_pattern(self, data: pd.DataFrame, pattern_name: str, 
                                config: Dict, catalyst_info: Dict) -> Optional[Dict]:
        """Detect reversal patterns with catalyst weighting"""
        
        if len(data) < 2:
            return None
            
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        pattern_detected = False
        pattern_direction = None
        
        if pattern_name == 'hammer':
            # Bullish reversal - long lower shadow, small body at top
            body = abs(latest['Close'] - latest['Open'])
            lower_shadow = min(latest['Open'], latest['Close']) - latest['Low']
            upper_shadow = latest['High'] - max(latest['Open'], latest['Close'])
            
            if lower_shadow > body * config['min_shadow_ratio'] and upper_shadow < body:
                pattern_detected = True
                pattern_direction = 'bullish'
                
        elif pattern_name == 'shooting_star':
            # Bearish reversal - long upper shadow, small body at bottom
            body = abs(latest['Close'] - latest['Open'])
            upper_shadow = latest['High'] - max(latest['Open'], latest['Close'])
            lower_shadow = min(latest['Open'], latest['Close']) - latest['Low']
            
            if upper_shadow > body * config['min_shadow_ratio'] and lower_shadow < body:
                pattern_detected = True
                pattern_direction = 'bearish'
                
        elif pattern_name == 'engulfing':
            # Check for bullish or bearish engulfing
            if latest['Close'] > latest['Open'] and prev['Close'] < prev['Open']:
                # Potential bullish engulfing
                if latest['Open'] < prev['Close'] and latest['Close'] > prev['Open']:
                    pattern_detected = True
                    pattern_direction = 'bullish'
            elif latest['Close'] < latest['Open'] and prev['Close'] > prev['Open']:
                # Potential bearish engulfing
                if latest['Open'] > prev['Close'] and latest['Close'] < prev['Open']:
                    pattern_detected = True
                    pattern_direction = 'bearish'
                    
        elif pattern_name == 'doji':
            # Indecision pattern - very small body
            body = abs(latest['Close'] - latest['Open'])
            total_range = latest['High'] - latest['Low']
            
            if total_range > 0 and body / total_range < config['max_body_ratio']:
                pattern_detected = True
                pattern_direction = 'neutral'
                
        if not pattern_detected:
            return None
            
        # Calculate confidence with catalyst adjustment
        base_confidence = config['base_confidence']
        catalyst_multiplier = config['catalyst_boost'].get(
            catalyst_info['catalyst_sentiment'], 1.0
        )
        
        # Adjust for pattern-catalyst alignment
        if pattern_direction == 'bullish' and catalyst_info['catalyst_sentiment'] == 'positive':
            catalyst_multiplier *= 1.2  # Extra boost for alignment
        elif pattern_direction == 'bearish' and catalyst_info['catalyst_sentiment'] == 'negative':
            catalyst_multiplier *= 1.2  # Extra boost for alignment
        elif pattern_direction != 'neutral' and catalyst_info['catalyst_sentiment'] != 'neutral':
            if pattern_direction != catalyst_info['catalyst_sentiment']:
                catalyst_multiplier *= 0.7  # Penalty for misalignment
                
        # Pre-market boost
        if catalyst_info['is_pre_market']:
            catalyst_multiplier *= self.premarket_multiplier
            
        final_confidence = min(base_confidence * catalyst_multiplier, 100)
        
        return {
            'pattern_name': pattern_name,
            'pattern_type': 'reversal',
            'pattern_direction': pattern_direction,
            'base_confidence': base_confidence,
            'catalyst_multiplier': catalyst_multiplier,
            'final_confidence': round(final_confidence, 2),
            'detected_at': datetime.now().isoformat(),
            'price': float(latest['Close']),
            'volume': int(latest['Volume']),
            'catalyst_aligned': pattern_direction == catalyst_info['catalyst_sentiment'],
            'catalyst_info': catalyst_info
        }
        
    def _detect_continuation_pattern(self, data: pd.DataFrame, pattern_name: str,
                                   config: Dict, catalyst_info: Dict) -> Optional[Dict]:
        """Detect continuation patterns"""
        
        if len(data) < 3:
            return None
            
        last_three = data.iloc[-3:]
        pattern_detected = False
        pattern_direction = None
        
        if pattern_name == 'three_white_soldiers':
            # Three consecutive bullish candles
            all_bullish = all(row['Close'] > row['Open'] for _, row in last_three.iterrows())
            ascending = all(last_three['Close'].iloc[i] > last_three['Close'].iloc[i-1] 
                          for i in range(1, 3))
            
            if all_bullish and ascending:
                pattern_detected = True
                pattern_direction = 'bullish'
                
        elif pattern_name == 'three_black_crows':
            # Three consecutive bearish candles
            all_bearish = all(row['Close'] < row['Open'] for _, row in last_three.iterrows())
            descending = all(last_three['Close'].iloc[i] < last_three['Close'].iloc[i-1] 
                           for i in range(1, 3))
            
            if all_bearish and descending:
                pattern_detected = True
                pattern_direction = 'bearish'
                
        if not pattern_detected:
            return None
            
        # Calculate confidence
        base_confidence = config['base_confidence']
        catalyst_multiplier = config['catalyst_boost'].get(
            catalyst_info['catalyst_sentiment'], 1.0
        )
        
        # Strong alignment bonus for continuation patterns
        if pattern_direction == catalyst_info['catalyst_sentiment']:
            catalyst_multiplier *= 1.3
            
        # Pre-market boost
        if catalyst_info['is_pre_market']:
            catalyst_multiplier *= self.premarket_multiplier
            
        final_confidence = min(base_confidence * catalyst_multiplier, 100)
        
        return {
            'pattern_name': pattern_name,
            'pattern_type': 'continuation',
            'pattern_direction': pattern_direction,
            'base_confidence': base_confidence,
            'catalyst_multiplier': catalyst_multiplier,
            'final_confidence': round(final_confidence, 2),
            'detected_at': datetime.now().isoformat(),
            'price': float(data.iloc[-1]['Close']),
            'volume': int(data.iloc[-1]['Volume']),
            'catalyst_aligned': pattern_direction == catalyst_info['catalyst_sentiment'],
            'catalyst_info': catalyst_info
        }
        
    def _detect_momentum_pattern(self, data: pd.DataFrame, pattern_name: str,
                               config: Dict, catalyst_info: Dict) -> Optional[Dict]:
        """Detect momentum patterns"""
        
        if len(data) < 2:
            return None
            
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        pattern_detected = False
        pattern_direction = None
        
        if pattern_name == 'gap_up':
            # Gap up pattern
            gap_percent = ((latest['Open'] - prev['Close']) / prev['Close']) * 100
            
            if gap_percent >= config['min_gap_percent']:
                pattern_detected = True
                pattern_direction = 'bullish'
                
        elif pattern_name == 'gap_down':
            # Gap down pattern
            gap_percent = ((prev['Close'] - latest['Open']) / prev['Close']) * 100
            
            if gap_percent >= config['min_gap_percent']:
                pattern_detected = True
                pattern_direction = 'bearish'
                
        elif pattern_name == 'volume_surge':
            # Volume surge pattern
            avg_volume = data['Volume'].iloc[:-1].mean()
            volume_ratio = latest['Volume'] / avg_volume if avg_volume > 0 else 0
            
            if volume_ratio >= config['min_volume_ratio']:
                pattern_detected = True
                # Direction based on price action
                pattern_direction = 'bullish' if latest['Close'] > latest['Open'] else 'bearish'
                
        if not pattern_detected:
            return None
            
        # Calculate confidence
        base_confidence = config['base_confidence']
        catalyst_multiplier = config['catalyst_boost'].get(
            catalyst_info['catalyst_sentiment'], 1.0
        )
        
        # Momentum patterns get huge boost with catalyst alignment
        if pattern_direction == catalyst_info['catalyst_sentiment']:
            catalyst_multiplier *= 1.5
            
        # Pre-market gaps are especially significant
        if catalyst_info['is_pre_market'] and pattern_name in ['gap_up', 'gap_down']:
            catalyst_multiplier *= 1.5
            
        final_confidence = min(base_confidence * catalyst_multiplier, 100)
        
        return {
            'pattern_name': pattern_name,
            'pattern_type': 'momentum',
            'pattern_direction': pattern_direction,
            'base_confidence': base_confidence,
            'catalyst_multiplier': catalyst_multiplier,
            'final_confidence': round(final_confidence, 2),
            'detected_at': datetime.now().isoformat(),
            'price': float(latest['Close']),
            'volume': int(latest['Volume']),
            'catalyst_aligned': pattern_direction == catalyst_info['catalyst_sentiment'],
            'catalyst_info': catalyst_info
        }

    def _extract_catalyst_info(self, context: Dict) -> Dict:
        """Extract catalyst information from context"""
        if not context:
            return {
                'has_catalyst': False,
                'catalyst_type': None,
                'catalyst_sentiment': 'neutral',
                'catalyst_score': 0,
                'is_pre_market': False
            }
            
        # Determine catalyst sentiment based on type
        catalyst_type = context.get('catalyst_type')
        sentiment_map = {
            'earnings_beat': 'positive',
            'earnings_miss': 'negative',
            'fda_approval': 'positive',
            'fda_rejection': 'negative',
            'merger_announcement': 'positive',
            'lawsuit': 'negative',
            'upgrade': 'positive',
            'downgrade': 'negative',
            'guidance_raised': 'positive',
            'guidance_lowered': 'negative',
            'insider_buying': 'positive',
            'insider_selling': 'negative'
        }
        
        catalyst_sentiment = sentiment_map.get(catalyst_type, 'neutral')
        
        # Special handling for earnings
        if catalyst_type == 'earnings' and 'earnings_result' in context:
            catalyst_sentiment = 'positive' if context['earnings_result'] == 'beat' else 'negative'
            
        return {
            'has_catalyst': context.get('has_catalyst', False),
            'catalyst_type': catalyst_type,
            'catalyst_sentiment': catalyst_sentiment,
            'catalyst_score': context.get('catalyst_score', 0),
            'is_pre_market': context.get('market_state') == 'pre-market',
            'news_count': context.get('news_count', 0)
        }

    async def _get_price_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get price data for analysis"""
        if not YFINANCE_AVAILABLE:
            return self._get_mock_price_data(symbol, timeframe)
            
        try:
            ticker = yf.Ticker(symbol)
            
            # Determine period based on timeframe
            period_map = {
                '1m': '7d',
                '5m': '1mo',
                '15m': '2mo',
                '30m': '3mo',
                '1h': '6mo',
                '1d': '2y'
            }
            
            period = period_map.get(timeframe, '1mo')
            data = ticker.history(period=period, interval=timeframe)
            
            if data.empty:
                self.logger.warning(f"No data retrieved for {symbol}")
                return None
                
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}", error=str(e))
            return None

    def _get_mock_price_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Generate mock price data for testing"""
        # Generate 100 periods of random walk data
        periods = 100
        base_price = 100
        
        dates = pd.date_range(end=datetime.now(), periods=periods, freq='5min')
        
        # Random walk
        returns = np.random.normal(0, 0.02, periods)
        prices = base_price * np.exp(np.cumsum(returns))
        
        # OHLC with some realistic relationships
        data = pd.DataFrame({
            'Open': prices * (1 + np.random.uniform(-0.005, 0.005, periods)),
            'High': prices * (1 + np.random.uniform(0, 0.01, periods)),
            'Low': prices * (1 + np.random.uniform(-0.01, 0, periods)),
            'Close': prices,
            'Volume': np.random.randint(100000, 1000000, periods)
        }, index=dates)
        
        # Ensure high is highest and low is lowest
        data['High'] = data[['Open', 'High', 'Low', 'Close']].max(axis=1)
        data['Low'] = data[['Open', 'High', 'Low', 'Close']].min(axis=1)
        
        return data

    async def _get_symbol_context(self, symbol: str, scan_id: str) -> Dict:
        """Get catalyst context for a symbol from the scan"""
        # This would normally query the scanner service or database
        # For now, return mock context
        return {
            'has_catalyst': True,
            'catalyst_type': 'earnings_beat',
            'catalyst_score': 8.5,
            'market_state': 'pre-market',
            'news_count': 3
        }

    async def _get_patterns_from_db(self, symbol: str, timeframe: str,
                                  min_confidence: float, catalyst_required: bool) -> List[Dict]:
        """Get patterns from database"""
        # This would query the pattern_analysis table
        # For now, return empty list
        return []

    async def _calculate_pattern_statistics(self, pattern_types: List[str],
                                          with_catalyst: Optional[bool],
                                          timeframe: str) -> List[Dict]:
        """Calculate pattern success statistics"""
        # This would query the database for historical pattern performance
        # For now, return mock statistics
        mock_stats = []
        
        for pattern_type in pattern_types or ['hammer', 'engulfing', 'gap_up']:
            mock_stats.append({
                "pattern_type": pattern_type,
                "success_rate": 0.72,
                "avg_confidence": 0.85,
                "total_detected": 145,
                "with_catalyst": 89,
                "without_catalyst": 56
            })
            
        return mock_stats

    async def _get_catalyst_aligned_success_rates(self, pattern_type: Optional[str],
                                                catalyst_type: Optional[str]) -> Dict:
        """Get success rates for catalyst-aligned patterns"""
        # This would query historical outcomes
        # For now, return mock data
        return {
            "success_rate": 0.75,
            "sample_size": 234,
            "confidence_interval": [0.71, 0.79],
            "pattern_type": pattern_type or "all",
            "catalyst_type": catalyst_type or "all",
            "historical_performance": {
                "avg_gain": 0.082,
                "avg_hold_time": "3.5 hours",
                "win_rate": 0.75
            }
        }

    async def _get_recent_patterns(self, limit: int, min_confidence: float) -> List[Dict]:
        """Get recently detected patterns"""
        # This would query the database
        # For now, return empty list
        return []

    async def _save_pattern_detection(self, pattern_data: Dict) -> int:
        """Save pattern detection to database"""
        try:
            # Transform to database format
            db_data = {
                'symbol': pattern_data['symbol'],
                'pattern_name': pattern_data['pattern_type'],
                'pattern_type': pattern_data.get('pattern_data', {}).get('pattern_type', 'unknown'),
                'base_confidence': pattern_data.get('pattern_data', {}).get('base_confidence', 0),
                'final_confidence': pattern_data['confidence'],
                'timeframe': pattern_data['timeframe'],
                'metadata': {
                    'pattern_data': pattern_data.get('pattern_data', {}),
                    'catalyst_context': pattern_data.get('catalyst_context', {})
                },
                'detected_at': datetime.now()
            }
            


            # Insert pattern detection directly
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                     cur.execute("""
                        INSERT INTO pattern_analysis (
                            symbol, pattern_name, pattern_type,
                            base_confidence, final_confidence,
                            timeframe, metadata, detected_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        RETURNING pattern_id
                    """, (
                        db_data['symbol'],
                        db_data['pattern_name'],
                        db_data['pattern_type'],
                        db_data['base_confidence'],
                        db_data['final_confidence'],
                        db_data['timeframe'],
                        json.dumps(db_data['metadata']),
                        db_data['detected_at']
                    ))
                    pattern_id = cur.fetchone()[0]
                    return pattern_id
            
        except Exception as e:
            self.logger.error("Failed to save pattern detection", error=str(e))
            return 0

    async def _update_pattern_outcome_db(self, pattern_id: int, pattern_completed: bool,
                                       actual_move: float, success: bool) -> bool:
        """Update pattern outcome in database"""
        # This would update the pattern_analysis table
        # For now, return success
        return True

    async def _validate_pattern(self, pattern_type: str, symbol: str,
                              catalyst_type: Optional[str]) -> Dict:
        """Validate pattern against historical data"""
        # This would check historical performance
        # For now, return mock validation
        return {
            "pattern_type": pattern_type,
            "symbol": symbol,
            "catalyst_type": catalyst_type,
            "historical_accuracy": 0.73,
            "sample_size": 45,
            "recommendation": "proceed" if 0.73 > 0.7 else "skip",
            "confidence": 0.82
        }

    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Pattern Analysis MCP Server",
                        version="3.0.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


if __name__ == "__main__":
    # Run the MCP server
    server = PatternAnalysisMCPServer()
    asyncio.run(server.run())