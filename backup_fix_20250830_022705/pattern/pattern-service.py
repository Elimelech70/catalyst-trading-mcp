#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: pattern-service.py
Version: 3.1.0
Last Updated: 2025-08-23
Purpose: MCP-enabled pattern detection with database MCP integration

REVISION HISTORY:
v3.1.0 (2025-08-23) - Database MCP integration and missing features
- Replaced all database operations with MCP Database Client
- Added missing resources: patterns/performance, patterns/trending, patterns/by-catalyst
- Added missing tools: train_pattern_model, export_patterns, reset_pattern_cache
- Enhanced pattern tracking and performance metrics
- Added pattern model training capabilities

v3.0.0 (2025-08-18) - Initial MCP implementation
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
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from structlog import get_logger
import redis.asyncio as redis
import yfinance as yf
import talib

# MCP imports
from mcp.server.fastmcp import FastMCP, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import MCP Database Client instead of database operations
from mcp_database_client import MCPDatabaseClient


class PatternAnalysisMCPServer:
    """MCP Server for technical pattern detection and analysis"""
    
    def __init__(self):
        # Initialize MCP server
        self.mcp = FastMCP("pattern-analysis")
        self.setup_logging()
        
        # Database client (initialized in async context)
        self.db_client: Optional[MCPDatabaseClient] = None
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Service configuration
        self.service_name = 'pattern-analysis'
        self.port = int(os.getenv('PORT', '5002'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Pattern detection parameters
        self.min_confidence = float(os.getenv('MIN_PATTERN_CONFIDENCE', '60'))
        self.lookback_periods = int(os.getenv('PATTERN_LOOKBACK_PERIODS', '20'))
        
        # Pattern categories and configurations
        self.pattern_configs = {
            'reversal_patterns': {
                'hammer': {'min_shadow_ratio': 2.0, 'max_body_ratio': 0.3},
                'shooting_star': {'min_shadow_ratio': 2.0, 'max_body_ratio': 0.3},
                'doji': {'max_body_ratio': 0.1},
                'engulfing': {'min_body_coverage': 1.0},
                'harami': {'max_body_coverage': 0.5}
            },
            'continuation_patterns': {
                'flag': {'trend_periods': 5, 'consolidation_periods': 3},
                'pennant': {'trend_periods': 5, 'convergence_rate': 0.8},
                'triangle': {'min_touches': 4, 'convergence_threshold': 0.7}
            },
            'momentum_patterns': {
                'breakout': {'volume_multiplier': 1.5, 'price_threshold': 0.02},
                'gap_up': {'min_gap_percent': 0.02},
                'gap_down': {'min_gap_percent': 0.02},
                'volume_spike': {'min_volume_ratio': 2.0}
            }
        }
        
        # Pattern performance tracking
        self.pattern_performance = {}
        self.performance_window = 30  # days
        
        # Model training data
        self.training_data = []
        self.model_version = "1.0.0"
        self.model_trained_at = None
        
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
        self.db_client = MCPDatabaseClient(
            os.getenv('DATABASE_MCP_URL', 'ws://database-service:5010')
        )
        await self.db_client.connect()
        
        # Initialize Redis
        self.redis_client = await redis.from_url(
            os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
            decode_responses=True
        )
        
        # Load pattern performance data
        await self._load_pattern_performance()
        
        self.logger.info("Pattern service initialized",
                        database_connected=True,
                        redis_connected=True,
                        patterns_configured=len(self.pattern_configs))
    
    async def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            await self.redis_client.close()
            
        if self.db_client:
            await self.db_client.disconnect()
    
    async def _load_pattern_performance(self):
        """Load historical pattern performance from cache"""
        try:
            perf_data = await self.redis_client.get("patterns:performance_metrics")
            if perf_data:
                self.pattern_performance = json.loads(perf_data)
            else:
                # Initialize with default values
                for category in self.pattern_configs:
                    for pattern in self.pattern_configs[category]:
                        self.pattern_performance[pattern] = {
                            'success_rate': 0.5,
                            'avg_return': 0.0,
                            'total_occurrences': 0,
                            'successful_trades': 0
                        }
        except Exception as e:
            self.logger.warning("Failed to load performance data", error=str(e))
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("patterns/by-symbol/{symbol}")
        async def get_patterns_by_symbol(params: ResourceParams) -> ResourceResponse:
            """Get detected patterns for a specific symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            min_confidence = params.get("min_confidence", self.min_confidence)
            catalyst_required = params.get("catalyst_required", False)
            hours = params.get("hours", 24)
            
            # Check cache first
            cache_key = f"pattern:{symbol}:{timeframe}:{hours}h"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                patterns = json.loads(cached)
            else:
                # Get from database via MCP (would need to add this method to db_client)
                # For now, detect patterns in real-time
                patterns = await self._analyze_symbol_patterns(
                    symbol, timeframe, min_confidence, catalyst_required
                )
                
                # Cache for 5 minutes
                await self.redis_client.setex(cache_key, 300, json.dumps(patterns))
            
            return ResourceResponse(
                type="pattern_collection",
                data={'patterns': patterns},
                metadata={
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'count': len(patterns),
                    'min_confidence': min_confidence
                }
            )
        
        @self.server.resource("patterns/statistics")
        async def get_pattern_statistics(params: ResourceParams) -> ResourceResponse:
            """Get pattern success statistics"""
            pattern_types = params.get("pattern_types", [])
            with_catalyst = params.get("with_catalyst", None)
            timeframe = params.get("timeframe", "7d")
            
            # Filter patterns if specific types requested
            if pattern_types:
                stats = {
                    p: self.pattern_performance.get(p, {})
                    for p in pattern_types
                    if p in self.pattern_performance
                }
            else:
                stats = self.pattern_performance
            
            # Calculate aggregate statistics
            total_patterns = sum(p.get('total_occurrences', 0) for p in stats.values())
            successful_patterns = sum(p.get('successful_trades', 0) for p in stats.values())
            overall_success_rate = successful_patterns / total_patterns if total_patterns > 0 else 0
            
            return ResourceResponse(
                type="pattern_stats",
                data={
                    'patterns': stats,
                    'summary': {
                        'total_patterns_detected': total_patterns,
                        'overall_success_rate': round(overall_success_rate, 3),
                        'timeframe': timeframe,
                        'top_performing': self._get_top_patterns(5)
                    }
                },
                metadata={'last_updated': datetime.now().isoformat()}
            )
        
        @self.server.resource("patterns/performance")
        async def get_pattern_performance(params: ResourceParams) -> ResourceResponse:
            """Get detailed pattern performance metrics"""
            days = params.get("days", 30)
            min_occurrences = params.get("min_occurrences", 10)
            
            # Filter patterns by minimum occurrences
            performance_data = {}
            for pattern, metrics in self.pattern_performance.items():
                if metrics.get('total_occurrences', 0) >= min_occurrences:
                    performance_data[pattern] = {
                        **metrics,
                        'confidence_score': self._calculate_confidence_score(metrics),
                        'recommendation': self._get_pattern_recommendation(metrics)
                    }
            
            # Sort by success rate
            sorted_patterns = sorted(
                performance_data.items(),
                key=lambda x: x[1]['success_rate'],
                reverse=True
            )
            
            return ResourceResponse(
                type="pattern_performance",
                data={
                    'patterns': dict(sorted_patterns),
                    'analysis_period_days': days,
                    'min_occurrences_filter': min_occurrences,
                    'patterns_analyzed': len(sorted_patterns)
                },
                metadata={'model_version': self.model_version}
            )
        
        @self.server.resource("patterns/trending")
        async def get_trending_patterns(params: ResourceParams) -> ResourceResponse:
            """Get currently trending patterns across all symbols"""
            hours = params.get("hours", 4)
            limit = params.get("limit", 10)
            
            # Get recent pattern detections from cache
            trending = []
            pattern_counts = {}
            
            # Scan recent detections
            async for key in self.redis_client.scan_iter(match="pattern:*:*:*"):
                try:
                    data = await self.redis_client.get(key)
                    if data:
                        patterns = json.loads(data)
                        for pattern in patterns:
                            pattern_name = pattern.get('pattern_name')
                            if pattern_name:
                                pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1
                except:
                    continue
            
            # Create trending list
            for pattern_name, count in pattern_counts.items():
                if count >= 3:  # Minimum 3 occurrences to be trending
                    trending.append({
                        'pattern': pattern_name,
                        'occurrences': count,
                        'performance': self.pattern_performance.get(pattern_name, {}),
                        'momentum_score': count * self.pattern_performance.get(
                            pattern_name, {}
                        ).get('success_rate', 0.5)
                    })
            
            # Sort by momentum score
            trending.sort(key=lambda x: x['momentum_score'], reverse=True)
            
            return ResourceResponse(
                type="trending_patterns",
                data={'trending': trending[:limit]},
                metadata={
                    'hours': hours,
                    'total_unique_patterns': len(pattern_counts)
                }
            )
        
        @self.server.resource("patterns/by-catalyst")
        async def get_patterns_by_catalyst(params: ResourceParams) -> ResourceResponse:
            """Get patterns grouped by catalyst type"""
            catalyst_type = params.get("catalyst_type")  # earnings, merger, fda, etc.
            min_confidence = params.get("min_confidence", 0.7)
            
            # This would query patterns with specific catalyst associations
            # For now, return categorized mock data
            catalyst_patterns = {
                'earnings': {
                    'common_patterns': ['gap_up', 'breakout', 'flag'],
                    'success_rate': 0.72,
                    'avg_move': 0.045
                },
                'merger': {
                    'common_patterns': ['accumulation', 'triangle', 'breakout'],
                    'success_rate': 0.68,
                    'avg_move': 0.082
                },
                'fda': {
                    'common_patterns': ['gap_up', 'gap_down', 'volume_spike'],
                    'success_rate': 0.65,
                    'avg_move': 0.125
                }
            }
            
            if catalyst_type and catalyst_type in catalyst_patterns:
                data = {catalyst_type: catalyst_patterns[catalyst_type]}
            else:
                data = catalyst_patterns
            
            return ResourceResponse(
                type="catalyst_patterns",
                data=data,
                metadata={
                    'min_confidence': min_confidence,
                    'analysis_period': '90d'
                }
            )
        
        @self.server.resource("patterns/recent")
        async def get_recent_patterns(params: ResourceParams) -> ResourceResponse:
            """Get recently detected patterns across all symbols"""
            limit = params.get("limit", 20)
            min_confidence = params.get("min_confidence", self.min_confidence)
            
            # Get recent patterns from cache
            recent_patterns = []
            
            # This would typically query from database
            # For now, scan cache for recent detections
            count = 0
            async for key in self.redis_client.scan_iter(match="pattern:*:*:*"):
                if count >= limit:
                    break
                    
                try:
                    data = await self.redis_client.get(key)
                    if data:
                        patterns = json.loads(data)
                        for pattern in patterns:
                            if pattern.get('confidence', 0) >= min_confidence:
                                # Extract symbol from key
                                parts = key.split(':')
                                if len(parts) >= 2:
                                    pattern['symbol'] = parts[1]
                                recent_patterns.append(pattern)
                                count += 1
                                if count >= limit:
                                    break
                except:
                    continue
            
            # Sort by timestamp (newest first)
            recent_patterns.sort(
                key=lambda x: x.get('detected_at', ''),
                reverse=True
            )
            
            return ResourceResponse(
                type="recent_patterns",
                data={'patterns': recent_patterns[:limit]},
                metadata={'count': len(recent_patterns)}
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("detect_patterns")
        async def detect_patterns(params: ToolParams) -> ToolResponse:
            """Detect patterns for multiple symbols"""
            symbols = params.get("symbols", [])
            timeframe = params.get("timeframe", "5m")
            catalyst_context = params.get("catalyst_context", {})
            scan_id = params.get("scan_id")
            
            if not symbols:
                return ToolResponse(
                    success=False,
                    error="No symbols provided"
                )
            
            results = {}
            patterns_detected = 0
            
            for symbol in symbols[:20]:  # Limit to 20 symbols per call
                try:
                    patterns = await self._analyze_with_catalyst_context(
                        symbol, timeframe, catalyst_context.get(symbol, {})
                    )
                    
                    if patterns:
                        results[symbol] = patterns
                        patterns_detected += len(patterns)
                        
                        # Persist each pattern
                        for pattern in patterns:
                            await self.db_client.persist_pattern_detection({
                                'symbol': symbol,
                                'pattern_type': pattern['pattern_name'],
                                'confidence': pattern['final_confidence'],
                                'timeframe': timeframe,
                                'pattern_data': pattern,
                                'catalyst_context': catalyst_context.get(symbol, {})
                            })
                        
                except Exception as e:
                    self.logger.error(f"Error detecting patterns for {symbol}",
                                    error=str(e))
                    results[symbol] = {"error": str(e)}
            
            return ToolResponse(
                success=True,
                data={
                    'results': results,
                    'total_patterns': patterns_detected,
                    'symbols_analyzed': len(results)
                },
                metadata={
                    "scan_id": scan_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.server.tool("analyze_pattern")
        async def analyze_pattern(params: ToolParams) -> ToolResponse:
            """Deep analysis of patterns for a specific symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            catalyst_context = params.get("catalyst_context", {})
            include_prediction = params.get("include_prediction", True)
            
            try:
                # Detect patterns
                patterns = await self._analyze_with_catalyst_context(
                    symbol, timeframe, catalyst_context
                )
                
                # Add predictions if requested
                if include_prediction and patterns:
                    for pattern in patterns:
                        pattern['prediction'] = self._predict_pattern_outcome(
                            pattern, catalyst_context
                        )
                
                # Calculate aggregate metrics
                avg_confidence = sum(p['final_confidence'] for p in patterns) / len(patterns) if patterns else 0
                
                return ToolResponse(
                    success=True,
                    data={
                        "symbol": symbol,
                        "patterns": patterns,
                        "pattern_count": len(patterns),
                        "avg_confidence": round(avg_confidence, 2),
                        "recommendation": self._get_trading_recommendation(patterns)
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("record_pattern_outcome")
        async def record_pattern_outcome(params: ToolParams) -> ToolResponse:
            """Record the actual outcome of a detected pattern"""
            pattern_id = params["pattern_id"]
            outcome = params["outcome"]  # success, failure, partial
            actual_move = params.get("actual_move", 0)
            trade_duration = params.get("trade_duration")  # in minutes
            
            try:
                # Update pattern performance
                pattern_type = params.get("pattern_type")
                if pattern_type:
                    await self._update_pattern_performance(
                        pattern_type, outcome, actual_move
                    )
                
                # Log outcome for training data
                self.training_data.append({
                    'pattern_id': pattern_id,
                    'pattern_type': pattern_type,
                    'outcome': outcome,
                    'actual_move': actual_move,
                    'trade_duration': trade_duration,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Limit training data size
                if len(self.training_data) > 10000:
                    self.training_data = self.training_data[-10000:]
                
                return ToolResponse(
                    success=True,
                    data={
                        "pattern_id": pattern_id,
                        "outcome_recorded": True,
                        "performance_updated": True
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("train_pattern_model")
        async def train_pattern_model(params: ToolParams) -> ToolResponse:
            """Train or update the pattern recognition model"""
            model_type = params.get("model_type", "performance")  # performance or detection
            min_samples = params.get("min_samples", 100)
            
            try:
                if len(self.training_data) < min_samples:
                    return ToolResponse(
                        success=False,
                        error=f"Insufficient training data. Have {len(self.training_data)}, need {min_samples}"
                    )
                
                # Perform model training (simplified version)
                if model_type == "performance":
                    # Update pattern performance metrics
                    pattern_metrics = {}
                    
                    for data in self.training_data:
                        pattern = data.get('pattern_type')
                        if pattern:
                            if pattern not in pattern_metrics:
                                pattern_metrics[pattern] = {
                                    'total': 0,
                                    'successful': 0,
                                    'total_return': 0
                                }
                            
                            pattern_metrics[pattern]['total'] += 1
                            if data['outcome'] == 'success':
                                pattern_metrics[pattern]['successful'] += 1
                            pattern_metrics[pattern]['total_return'] += data.get('actual_move', 0)
                    
                    # Update performance data
                    for pattern, metrics in pattern_metrics.items():
                        if metrics['total'] > 0:
                            self.pattern_performance[pattern] = {
                                'success_rate': metrics['successful'] / metrics['total'],
                                'avg_return': metrics['total_return'] / metrics['total'],
                                'total_occurrences': metrics['total'],
                                'successful_trades': metrics['successful']
                            }
                    
                    # Save to cache
                    await self.redis_client.set(
                        "patterns:performance_metrics",
                        json.dumps(self.pattern_performance)
                    )
                
                # Update model metadata
                self.model_version = f"1.{len(self.training_data)}.0"
                self.model_trained_at = datetime.now()
                
                return ToolResponse(
                    success=True,
                    data={
                        "model_type": model_type,
                        "samples_used": len(self.training_data),
                        "patterns_updated": len(pattern_metrics) if model_type == "performance" else 0,
                        "model_version": self.model_version,
                        "trained_at": self.model_trained_at.isoformat()
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("export_patterns")
        async def export_patterns(params: ToolParams) -> ToolResponse:
            """Export pattern data for analysis"""
            export_type = params.get("export_type", "performance")  # performance, detections, training
            format = params.get("format", "json")  # json, csv
            days = params.get("days", 7)
            
            try:
                export_data = {}
                
                if export_type == "performance":
                    export_data = {
                        'performance_metrics': self.pattern_performance,
                        'model_version': self.model_version,
                        'exported_at': datetime.now().isoformat()
                    }
                
                elif export_type == "training":
                    export_data = {
                        'training_data': self.training_data[-1000:],  # Last 1000 samples
                        'total_samples': len(self.training_data),
                        'exported_at': datetime.now().isoformat()
                    }
                
                elif export_type == "detections":
                    # Would query from database for recent detections
                    export_data = {
                        'recent_detections': [],  # Would be populated from DB
                        'period_days': days,
                        'exported_at': datetime.now().isoformat()
                    }
                
                # Store export in cache for download
                export_id = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await self.redis_client.setex(
                    f"patterns:export:{export_id}",
                    3600,  # 1 hour TTL
                    json.dumps(export_data)
                )
                
                return ToolResponse(
                    success=True,
                    data={
                        'export_id': export_id,
                        'export_type': export_type,
                        'format': format,
                        'size': len(json.dumps(export_data)),
                        'download_url': f"/exports/{export_id}"  # Would be actual URL
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("reset_pattern_cache")
        async def reset_pattern_cache(params: ToolParams) -> ToolResponse:
            """Reset pattern detection cache"""
            pattern = params.get("pattern", "pattern:*")
            confirm = params.get("confirm", False)
            
            if not confirm:
                return ToolResponse(
                    success=False,
                    error="Confirmation required to reset cache"
                )
            
            try:
                # Delete matching keys
                deleted = 0
                async for key in self.redis_client.scan_iter(match=pattern):
                    await self.redis_client.delete(key)
                    deleted += 1
                
                return ToolResponse(
                    success=True,
                    data={
                        "keys_deleted": deleted,
                        "pattern": pattern
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("validate_pattern")
        async def validate_pattern(params: ToolParams) -> ToolResponse:
            """Validate a detected pattern against historical data"""
            pattern_type = params["pattern_type"]
            symbol = params["symbol"]
            catalyst_type = params.get("catalyst_type")
            
            try:
                # Get historical performance
                performance = self.pattern_performance.get(pattern_type, {})
                
                # Calculate validation score
                validation = {
                    'pattern_type': pattern_type,
                    'symbol': symbol,
                    'historical_accuracy': performance.get('success_rate', 0.5),
                    'sample_size': performance.get('total_occurrences', 0),
                    'avg_return': performance.get('avg_return', 0),
                    'confidence': self._calculate_confidence_score(performance),
                    'recommendation': 'proceed' if performance.get('success_rate', 0) > 0.6 else 'caution'
                }
                
                # Adjust for catalyst if provided
                if catalyst_type:
                    catalyst_boost = self._get_catalyst_boost(pattern_type, catalyst_type)
                    validation['catalyst_adjusted_confidence'] = min(
                        validation['confidence'] * catalyst_boost, 1.0
                    )
                
                return ToolResponse(
                    success=True,
                    data=validation
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
    
    async def _analyze_symbol_patterns(self, symbol: str, timeframe: str,
                                     min_confidence: float, catalyst_required: bool) -> List[Dict]:
        """Analyze symbol for patterns"""
        try:
            # Get price data
            data = await self._get_price_data(symbol, timeframe)
            if data is None or len(data) < self.lookback_periods:
                return []
            
            # Detect patterns
            detected_patterns = []
            
            # Check each pattern category
            for category, patterns in self.pattern_configs.items():
                for pattern_name, config in patterns.items():
                    pattern = await self._detect_pattern(
                        data, pattern_name, config, {}, category
                    )
                    if pattern and pattern['confidence'] >= min_confidence:
                        # Skip if catalyst required but none present
                        if catalyst_required and pattern.get('catalyst_score', 0) < 0.3:
                            continue
                        
                        detected_patterns.append({
                            'pattern_name': pattern_name,
                            'category': category,
                            'confidence': pattern['confidence'],
                            'final_confidence': pattern.get('final_confidence', pattern['confidence']),
                            'direction': pattern.get('direction'),
                            'detected_at': datetime.now().isoformat(),
                            'metadata': pattern
                        })
            
            return detected_patterns
            
        except Exception as e:
            self.logger.error(f"Error analyzing patterns for {symbol}", error=str(e))
            return []
    
    async def _analyze_with_catalyst_context(self, symbol: str, timeframe: str,
                                           catalyst_info: Dict) -> List[Dict]:
        """Analyze patterns with catalyst weighting"""
        try:
            # Get price data
            data = await self._get_price_data(symbol, timeframe)
            if data is None or len(data) < self.lookback_periods:
                return []
            
            detected_patterns = []
            
            # Detect patterns across all categories
            for category, patterns in self.pattern_configs.items():
                for pattern_name, config in patterns.items():
                    pattern = await self._detect_pattern(
                        data, pattern_name, config, catalyst_info, category
                    )
                    if pattern and pattern['final_confidence'] >= self.min_confidence:
                        detected_patterns.append(pattern)
            
            # Sort by confidence
            detected_patterns.sort(key=lambda x: x['final_confidence'], reverse=True)
            
            # Limit to top 5 patterns
            return detected_patterns[:5]
            
        except Exception as e:
            self.logger.error(f"Error in catalyst-aware pattern analysis", error=str(e))
            return []
    
    async def _get_price_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get price data for pattern analysis"""
        try:
            # Map timeframe to yfinance parameters
            timeframe_map = {
                '1m': ('1d', '1m'),
                '5m': ('5d', '5m'),
                '15m': ('5d', '15m'),
                '1h': ('1mo', '1h'),
                '1d': ('3mo', '1d')
            }
            
            period, interval = timeframe_map.get(timeframe, ('5d', '5m'))
            
            # Get data from yfinance
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                return None
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error getting price data for {symbol}", error=str(e))
            return None
    
    async def _detect_pattern(self, data: pd.DataFrame, pattern_name: str,
                            config: Dict, catalyst_info: Dict,
                            pattern_category: str) -> Optional[Dict]:
        """Generic pattern detection with catalyst weighting"""
        
        if pattern_category == 'reversal_patterns':
            pattern = self._detect_reversal_pattern(data, pattern_name, config)
        elif pattern_category == 'continuation_patterns':
            pattern = self._detect_continuation_pattern(data, pattern_name, config)
        elif pattern_category == 'momentum_patterns':
            pattern = self._detect_momentum_pattern(data, pattern_name, config)
        else:
            return None
        
        if pattern:
            # Add catalyst weighting
            base_confidence = pattern['confidence']
            catalyst_score = catalyst_info.get('score', 0)
            
            # Calculate catalyst boost
            if catalyst_score > 0.7:
                catalyst_multiplier = 1.3
            elif catalyst_score > 0.5:
                catalyst_multiplier = 1.2
            elif catalyst_score > 0.3:
                catalyst_multiplier = 1.1
            else:
                catalyst_multiplier = 1.0
            
            # Apply catalyst boost with cap
            final_confidence = min(base_confidence * catalyst_multiplier, 100)
            
            pattern.update({
                'pattern_name': pattern_name,
                'pattern_type': pattern_category,
                'base_confidence': base_confidence,
                'catalyst_score': catalyst_score,
                'catalyst_multiplier': catalyst_multiplier,
                'final_confidence': round(final_confidence, 2),
                'detected_at': datetime.now().isoformat()
            })
        
        return pattern
    
    def _detect_reversal_pattern(self, data: pd.DataFrame, pattern_name: str,
                                config: Dict) -> Optional[Dict]:
        """Detect reversal patterns"""
        if len(data) < 2:
            return None
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        if pattern_name == 'hammer':
            # Bullish reversal - long lower shadow
            body = abs(latest['Close'] - latest['Open'])
            lower_shadow = min(latest['Open'], latest['Close']) - latest['Low']
            upper_shadow = latest['High'] - max(latest['Open'], latest['Close'])
            
            if body > 0 and lower_shadow > body * config['min_shadow_ratio'] and upper_shadow < body:
                # Check if in downtrend
                sma = data['Close'].rolling(window=20).mean()
                if len(sma) >= 20 and latest['Close'] < sma.iloc[-1]:
                    return {
                        'confidence': 75,
                        'direction': 'bullish',
                        'type': 'reversal'
                    }
        
        elif pattern_name == 'engulfing':
            # Bullish or bearish engulfing
            curr_body = abs(latest['Close'] - latest['Open'])
            prev_body = abs(prev['Close'] - prev['Open'])
            
            if curr_body > prev_body * config['min_body_coverage']:
                if latest['Close'] > latest['Open'] and prev['Close'] < prev['Open']:
                    # Bullish engulfing
                    return {
                        'confidence': 80,
                        'direction': 'bullish',
                        'type': 'reversal'
                    }
                elif latest['Close'] < latest['Open'] and prev['Close'] > prev['Open']:
                    # Bearish engulfing
                    return {
                        'confidence': 80,
                        'direction': 'bearish',
                        'type': 'reversal'
                    }
        
        elif pattern_name == 'doji':
            # Doji - indecision
            body = abs(latest['Close'] - latest['Open'])
            total_range = latest['High'] - latest['Low']
            
            if total_range > 0 and body / total_range < config['max_body_ratio']:
                return {
                    'confidence': 60,
                    'direction': 'neutral',
                    'type': 'reversal'
                }
        
        return None
    
    def _detect_continuation_pattern(self, data: pd.DataFrame, pattern_name: str,
                                   config: Dict) -> Optional[Dict]:
        """Detect continuation patterns"""
        if len(data) < config.get('trend_periods', 5) + config.get('consolidation_periods', 3):
            return None
        
        if pattern_name == 'flag':
            # Flag pattern - trend followed by consolidation
            trend_data = data.iloc[-config['trend_periods']-config['consolidation_periods']:-config['consolidation_periods']]
            consol_data = data.iloc[-config['consolidation_periods']:]
            
            # Check for strong trend
            trend_return = (trend_data['Close'].iloc[-1] - trend_data['Close'].iloc[0]) / trend_data['Close'].iloc[0]
            
            # Check for consolidation
            consol_range = (consol_data['High'].max() - consol_data['Low'].min()) / consol_data['Close'].mean()
            
            if abs(trend_return) > 0.03 and consol_range < 0.02:
                return {
                    'confidence': 70,
                    'direction': 'bullish' if trend_return > 0 else 'bearish',
                    'type': 'continuation',
                    'trend_strength': abs(trend_return)
                }
        
        elif pattern_name == 'triangle':
            # Triangle pattern - converging highs and lows
            if len(data) < config['min_touches'] * 2:
                return None
            
            highs = data['High'].rolling(window=3).max()
            lows = data['Low'].rolling(window=3).min()
            
            # Check for convergence
            high_slope = np.polyfit(range(len(highs)), highs.fillna(method='ffill'), 1)[0]
            low_slope = np.polyfit(range(len(lows)), lows.fillna(method='ffill'), 1)[0]
            
            if high_slope < 0 and low_slope > 0:  # Converging
                convergence_rate = abs(high_slope) + abs(low_slope)
                if convergence_rate > config['convergence_threshold']:
                    return {
                        'confidence': 75,
                        'direction': 'neutral',  # Breakout direction unknown
                        'type': 'continuation',
                        'convergence_rate': convergence_rate
                    }
        
        return None
    
    def _detect_momentum_pattern(self, data: pd.DataFrame, pattern_name: str,
                               config: Dict) -> Optional[Dict]:
        """Detect momentum patterns"""
        if len(data) < 2:
            return None
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        if pattern_name == 'breakout':
            # Price breakout with volume
            price_change = (latest['Close'] - prev['Close']) / prev['Close']
            volume_ratio = latest['Volume'] / data['Volume'].rolling(window=20).mean().iloc[-1]
            
            if (abs(price_change) > config['price_threshold'] and 
                volume_ratio > config['volume_multiplier']):
                return {
                    'confidence': 85,
                    'direction': 'bullish' if price_change > 0 else 'bearish',
                    'type': 'momentum',
                    'volume_surge': volume_ratio
                }
        
        elif pattern_name == 'gap_up' or pattern_name == 'gap_down':
            # Gap patterns
            gap = (latest['Open'] - prev['Close']) / prev['Close']
            
            if pattern_name == 'gap_up' and gap > config['min_gap_percent']:
                return {
                    'confidence': 90,
                    'direction': 'bullish',
                    'type': 'momentum',
                    'gap_size': gap
                }
            elif pattern_name == 'gap_down' and gap < -config['min_gap_percent']:
                return {
                    'confidence': 90,
                    'direction': 'bearish',
                    'type': 'momentum',
                    'gap_size': abs(gap)
                }
        
        elif pattern_name == 'volume_spike':
            # Volume spike pattern
            volume_ratio = latest['Volume'] / data['Volume'].rolling(window=20).mean().iloc[-1]
            
            if volume_ratio > config['min_volume_ratio']:
                price_direction = 'bullish' if latest['Close'] > latest['Open'] else 'bearish'
                return {
                    'confidence': 70,
                    'direction': price_direction,
                    'type': 'momentum',
                    'volume_ratio': volume_ratio
                }
        
        return None
    
    def _calculate_confidence_score(self, metrics: Dict) -> float:
        """Calculate confidence score from performance metrics"""
        success_rate = metrics.get('success_rate', 0.5)
        occurrences = metrics.get('total_occurrences', 0)
        
        # Base confidence on success rate
        confidence = success_rate
        
        # Adjust for sample size
        if occurrences < 10:
            confidence *= 0.7
        elif occurrences < 50:
            confidence *= 0.85
        elif occurrences < 100:
            confidence *= 0.95
        
        return round(confidence, 3)
    
    def _get_pattern_recommendation(self, metrics: Dict) -> str:
        """Get trading recommendation based on pattern metrics"""
        success_rate = metrics.get('success_rate', 0)
        avg_return = metrics.get('avg_return', 0)
        occurrences = metrics.get('total_occurrences', 0)
        
        if occurrences < 10:
            return 'insufficient_data'
        elif success_rate > 0.7 and avg_return > 0.02:
            return 'strong_buy'
        elif success_rate > 0.6 and avg_return > 0.01:
            return 'buy'
        elif success_rate > 0.5:
            return 'hold'
        else:
            return 'avoid'
    
    def _get_top_patterns(self, limit: int) -> List[Dict]:
        """Get top performing patterns"""
        sorted_patterns = sorted(
            self.pattern_performance.items(),
            key=lambda x: x[1].get('success_rate', 0) * x[1].get('total_occurrences', 0),
            reverse=True
        )
        
        return [
            {
                'pattern': name,
                'success_rate': metrics.get('success_rate', 0),
                'avg_return': metrics.get('avg_return', 0),
                'occurrences': metrics.get('total_occurrences', 0)
            }
            for name, metrics in sorted_patterns[:limit]
        ]
    
    def _predict_pattern_outcome(self, pattern: Dict, catalyst_context: Dict) -> Dict:
        """Predict pattern outcome based on historical data"""
        pattern_type = pattern.get('pattern_name')
        performance = self.pattern_performance.get(pattern_type, {})
        
        # Base prediction on historical performance
        success_probability = performance.get('success_rate', 0.5)
        expected_move = performance.get('avg_return', 0)
        
        # Adjust for catalyst
        if catalyst_context.get('score', 0) > 0.5:
            success_probability *= 1.2
            expected_move *= 1.3
        
        return {
            'success_probability': min(success_probability, 0.95),
            'expected_move': round(expected_move, 3),
            'confidence': self._calculate_confidence_score(performance),
            'time_horizon': '1-3 days'
        }
    
    def _get_trading_recommendation(self, patterns: List[Dict]) -> str:
        """Get trading recommendation based on detected patterns"""
        if not patterns:
            return 'no_action'
        
        # Average confidence across patterns
        avg_confidence = sum(p.get('final_confidence', 0) for p in patterns) / len(patterns)
        
        # Check pattern directions
        bullish = sum(1 for p in patterns if p.get('direction') == 'bullish')
        bearish = sum(1 for p in patterns if p.get('direction') == 'bearish')
        
        if avg_confidence > 80:
            if bullish > bearish:
                return 'strong_buy'
            elif bearish > bullish:
                return 'strong_sell'
        elif avg_confidence > 70:
            if bullish > bearish:
                return 'buy'
            elif bearish > bullish:
                return 'sell'
        
        return 'hold'
    
    async def _update_pattern_performance(self, pattern_type: str, outcome: str, 
                                        actual_move: float):
        """Update pattern performance metrics"""
        if pattern_type not in self.pattern_performance:
            self.pattern_performance[pattern_type] = {
                'success_rate': 0.5,
                'avg_return': 0.0,
                'total_occurrences': 0,
                'successful_trades': 0
            }
        
        metrics = self.pattern_performance[pattern_type]
        metrics['total_occurrences'] += 1
        
        if outcome == 'success':
            metrics['successful_trades'] += 1
        
        # Update success rate
        metrics['success_rate'] = metrics['successful_trades'] / metrics['total_occurrences']
        
        # Update average return (exponential moving average)
        alpha = 0.1  # Weight for new data
        metrics['avg_return'] = (1 - alpha) * metrics['avg_return'] + alpha * actual_move
        
        # Save to cache
        await self.redis_client.set(
            "patterns:performance_metrics",
            json.dumps(self.pattern_performance)
        )
    
    def _get_catalyst_boost(self, pattern_type: str, catalyst_type: str) -> float:
        """Get catalyst boost factor for pattern confidence"""
        # Catalyst-pattern affinity matrix
        affinity = {
            'earnings': {
                'gap_up': 1.4,
                'gap_down': 1.4,
                'breakout': 1.3,
                'flag': 1.2
            },
            'merger': {
                'accumulation': 1.5,
                'triangle': 1.3,
                'breakout': 1.4
            },
            'fda': {
                'gap_up': 1.5,
                'gap_down': 1.5,
                'volume_spike': 1.4
            }
        }
        
        return affinity.get(catalyst_type, {}).get(pattern_type, 1.1)
    
    async def health_check(self) -> Dict:
        """Service health check"""
        try:
            # Check database connection
            db_status = await self.db_client.get_database_status()
            
            # Check Redis connection
            redis_ok = await self.redis_client.ping() if self.redis_client else False
            
            return {
                'status': 'healthy',
                'database': db_status.get('postgresql', {}).get('status', 'unknown'),
                'redis': 'healthy' if redis_ok else 'unhealthy',
                'patterns_configured': len(self.pattern_configs),
                'performance_data_loaded': len(self.pattern_performance) > 0,
                'model_version': self.model_version,
                'training_samples': len(self.training_data)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Pattern Analysis MCP Server",
                        version="3.1.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


async def main():
    """Main entry point"""
    server = PatternAnalysisFastMCP()
    
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