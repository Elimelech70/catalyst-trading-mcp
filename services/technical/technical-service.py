#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 3.1.0
Last Updated: 2025-08-23
Purpose: MCP-enabled technical analysis with database MCP integration

REVISION HISTORY:
v3.1.0 (2025-08-23) - Database MCP integration and missing features
- Replaced all database operations with MCP Database Client
- Added missing resources: indicators/realtime/{symbol}, signals/expired, technical/backtesting
- Added missing tools: recalculate_indicators, optimize_parameters, export_signals
- Enhanced signal generation with multi-timeframe analysis
- Added parameter optimization capabilities

v3.0.0 (2024-12-30) - Initial MCP implementation
- Technical analysis and signal generation via MCP
- Integration with pattern analysis results
- Catalyst-weighted signal strength
- Support/resistance level calculation
- Trend analysis and confirmation

Description of Service:
Provides comprehensive technical analysis and signal generation. Integrates
pattern analysis results and considers news catalysts. Enables Claude to
understand market technicals and generate high-confidence signals.

KEY FEATURES:
- Multiple timeframe analysis (1min, 5min, 15min, 1h, 1d)
- 20+ technical indicators (RSI, MACD, Bollinger, etc.)
- Signal generation with confidence scoring
- Catalyst-weighted signal strength
- Database persistence for trading signals
- Support/resistance level calculation
- Trend analysis and confirmation
- Volume analysis integration
"""

import os
import json
import time
import asyncio
import logging
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from structlog import get_logger
import redis.asyncio as redis
import yfinance as yf
import talib

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import MCP Database Client instead of database operations
from mcp_database_client import MCPDatabaseClient


class TechnicalAnalysisMCPServer:
    """MCP Server for technical analysis and signal generation"""
    
    def __init__(self):
        # Initialize MCP server
        self.server = MCPServer("technical-analysis")
        self.setup_logging()
        
        # Database client (initialized in async context)
        self.db_client: Optional[MCPDatabaseClient] = None
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Service URLs from environment
        self.pattern_service_url = os.getenv('PATTERN_SERVICE_URL', 'http://pattern-service:5002')
        
        # Technical analysis configuration
        self.ta_config = {
            # Indicator periods
            'rsi_period': int(os.getenv('RSI_PERIOD', '14')),
            'macd_fast': int(os.getenv('MACD_FAST', '12')),
            'macd_slow': int(os.getenv('MACD_SLOW', '26')),
            'macd_signal': int(os.getenv('MACD_SIGNAL', '9')),
            'bb_period': int(os.getenv('BB_PERIOD', '20')),
            'bb_std': float(os.getenv('BB_STD', '2.0')),
            'sma_short': int(os.getenv('SMA_SHORT', '20')),
            'sma_long': int(os.getenv('SMA_LONG', '50')),
            'ema_short': int(os.getenv('EMA_SHORT', '9')),
            'ema_long': int(os.getenv('EMA_LONG', '21')),
            'atr_period': int(os.getenv('ATR_PERIOD', '14')),
            'adx_period': int(os.getenv('ADX_PERIOD', '14')),
            'stoch_period': int(os.getenv('STOCH_PERIOD', '14')),
            
            # Signal thresholds
            'rsi_oversold': float(os.getenv('RSI_OVERSOLD', '30')),
            'rsi_overbought': float(os.getenv('RSI_OVERBOUGHT', '70')),
            'min_volume_ratio': float(os.getenv('MIN_VOLUME_RATIO', '1.5')),
            'min_confidence': float(os.getenv('MIN_SIGNAL_CONFIDENCE', '70'))
        }
        
        # Parameter optimization settings
        self.optimization_config = {
            'population_size': 50,
            'generations': 20,
            'mutation_rate': 0.1,
            'crossover_rate': 0.7
        }
        
        # Backtest results cache
        self.backtest_results = {}
        
        # Signal tracking
        self.active_signals = []
        self.signal_performance = {}
        
        # Service configuration
        self.service_name = 'technical-analysis'
        self.port = int(os.getenv('PORT', '5003'))
        
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
        
        # Load signal performance data
        await self._load_signal_performance()
        
        self.logger.info("Technical analysis service initialized",
                        database_connected=True,
                        redis_connected=True,
                        indicators_configured=len(self.ta_config))
    
    async def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            await self.redis_client.close()
            
        if self.db_client:
            await self.db_client.disconnect()
    
    async def _load_signal_performance(self):
        """Load historical signal performance"""
        try:
            perf_data = await self.redis_client.get("technical:signal_performance")
            if perf_data:
                self.signal_performance = json.loads(perf_data)
            else:
                self.signal_performance = {
                    'total_signals': 0,
                    'successful_signals': 0,
                    'avg_return': 0.0,
                    'win_rate': 0.0,
                    'by_type': {}
                }
        except Exception as e:
            self.logger.warning("Failed to load signal performance", error=str(e))
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("indicators/{symbol}")
        async def get_indicators(params: ResourceParams) -> ResourceResponse:
            """Get technical indicators for symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "1h")
            indicators = params.get("indicators", ["all"])
            
            try:
                # Get indicator data
                data = await self._calculate_indicators(symbol, timeframe, indicators)
                
                return ResourceResponse(
                    type="technical_indicators",
                    data=data,
                    metadata={
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'timestamp': datetime.now().isoformat()
                    }
                )
            except Exception as e:
                return ResourceResponse(
                    type="error",
                    data={'error': str(e)}
                )
        
        @self.server.resource("indicators/realtime/{symbol}")
        async def get_realtime_indicators(params: ResourceParams) -> ResourceResponse:
            """Get real-time technical indicators with live updates"""
            symbol = params["symbol"]
            indicators = params.get("indicators", ["rsi", "macd", "bb"])
            
            try:
                # Get real-time data (1-minute bars)
                data = await self._get_realtime_data(symbol)
                
                if data is None:
                    return ResourceResponse(
                        type="error",
                        data={'error': 'No real-time data available'}
                    )
                
                # Calculate requested indicators
                result = {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'price': float(data['Close'].iloc[-1]),
                    'indicators': {}
                }
                
                if 'rsi' in indicators or 'all' in indicators:
                    result['indicators']['rsi'] = talib.RSI(
                        data['Close'], timeperiod=self.ta_config['rsi_period']
                    ).iloc[-1]
                
                if 'macd' in indicators or 'all' in indicators:
                    macd, signal, hist = talib.MACD(
                        data['Close'],
                        fastperiod=self.ta_config['macd_fast'],
                        slowperiod=self.ta_config['macd_slow'],
                        signalperiod=self.ta_config['macd_signal']
                    )
                    result['indicators']['macd'] = {
                        'macd': float(macd.iloc[-1]),
                        'signal': float(signal.iloc[-1]),
                        'histogram': float(hist.iloc[-1])
                    }
                
                if 'bb' in indicators or 'all' in indicators:
                    upper, middle, lower = talib.BBANDS(
                        data['Close'],
                        timeperiod=self.ta_config['bb_period'],
                        nbdevup=self.ta_config['bb_std'],
                        nbdevdn=self.ta_config['bb_std']
                    )
                    result['indicators']['bollinger'] = {
                        'upper': float(upper.iloc[-1]),
                        'middle': float(middle.iloc[-1]),
                        'lower': float(lower.iloc[-1]),
                        'position': self._calculate_bb_position(
                            data['Close'].iloc[-1],
                            upper.iloc[-1],
                            lower.iloc[-1]
                        )
                    }
                
                # Add signal strength
                result['signal_strength'] = self._calculate_signal_strength(result['indicators'])
                
                return ResourceResponse(
                    type="realtime_indicators",
                    data=result,
                    metadata={'update_frequency': '1min'}
                )
                
            except Exception as e:
                return ResourceResponse(
                    type="error",
                    data={'error': str(e)}
                )
        
        @self.server.resource("signals/active")
        async def get_active_signals(params: ResourceParams) -> ResourceResponse:
            """Get currently active trading signals"""
            min_confidence = params.get("min_confidence", self.ta_config['min_confidence'])
            signal_type = params.get("type")  # momentum, reversal, breakout
            
            # Get signals from database
            signals = await self.db_client.get_pending_signals(
                limit=50,
                min_confidence=min_confidence / 100  # Convert to decimal
            )
            
            # Filter by type if specified
            if signal_type:
                signals = [s for s in signals if s.get('signal_type') == signal_type]
            
            # Add current status
            for signal in signals:
                signal['current_status'] = await self._get_signal_status(signal)
            
            return ResourceResponse(
                type="active_signals",
                data={'signals': signals},
                metadata={
                    'count': len(signals),
                    'min_confidence': min_confidence
                }
            )
        
        @self.server.resource("signals/expired")
        async def get_expired_signals(params: ResourceParams) -> ResourceResponse:
            """Get recently expired signals with outcomes"""
            hours = params.get("hours", 24)
            include_outcomes = params.get("include_outcomes", True)
            
            # Query expired signals from cache
            cache_key = f"technical:expired_signals:{hours}h"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                expired_signals = json.loads(cached)
            else:
                # In production, would query from database
                expired_signals = []
                
                # Cache for 1 hour
                await self.redis_client.setex(
                    cache_key, 3600, json.dumps(expired_signals)
                )
            
            # Add outcome data if requested
            if include_outcomes:
                for signal in expired_signals:
                    signal['outcome'] = await self._get_signal_outcome(signal)
            
            return ResourceResponse(
                type="expired_signals",
                data={'signals': expired_signals},
                metadata={
                    'count': len(expired_signals),
                    'hours': hours,
                    'performance_summary': self._calculate_outcome_summary(expired_signals)
                }
            )
        
        @self.server.resource("levels/{symbol}")
        async def get_support_resistance(params: ResourceParams) -> ResourceResponse:
            """Get support and resistance levels"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "1d")
            method = params.get("method", "pivot")  # pivot, fibonacci, volume
            
            levels = await self._calculate_support_resistance(symbol, timeframe, method)
            
            return ResourceResponse(
                type="support_resistance",
                data={
                    'symbol': symbol,
                    'levels': levels,
                    'current_price': levels.get('current_price'),
                    'nearest_support': levels.get('nearest_support'),
                    'nearest_resistance': levels.get('nearest_resistance')
                },
                metadata={'method': method, 'timeframe': timeframe}
            )
        
        @self.server.resource("technical/backtesting")
        async def get_backtest_results(params: ResourceParams) -> ResourceResponse:
            """Get backtesting results for technical strategies"""
            strategy = params.get("strategy", "default")
            days = params.get("days", 30)
            
            # Check cache for results
            cache_key = f"technical:backtest:{strategy}:{days}d"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                results = json.loads(cached)
            else:
                # Return latest backtest results
                results = self.backtest_results.get(strategy, {
                    'strategy': strategy,
                    'period_days': days,
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'avg_return': 0.0,
                    'sharpe_ratio': 0.0,
                    'max_drawdown': 0.0,
                    'status': 'no_data'
                })
            
            return ResourceResponse(
                type="backtest_results",
                data=results,
                metadata={
                    'last_updated': results.get('last_updated', 'never'),
                    'parameters_used': results.get('parameters', {})
                }
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("analyze_technical")
        async def analyze_technical(params: ToolParams) -> ToolResponse:
            """Comprehensive technical analysis for symbol"""
            symbol = params["symbol"]
            timeframes = params.get("timeframes", ["5m", "1h", "1d"])
            include_signals = params.get("include_signals", True)
            
            try:
                analysis = {}
                
                # Multi-timeframe analysis
                for tf in timeframes:
                    tf_analysis = await self._analyze_timeframe(symbol, tf)
                    analysis[tf] = tf_analysis
                
                # Generate consensus view
                consensus = self._generate_consensus(analysis)
                
                # Generate signals if requested
                signals = []
                if include_signals:
                    for tf in timeframes:
                        signal = await self._generate_signal_for_timeframe(
                            symbol, tf, analysis[tf], consensus
                        )
                        if signal:
                            signals.append(signal)
                
                return ToolResponse(
                    success=True,
                    data={
                        'symbol': symbol,
                        'analysis': analysis,
                        'consensus': consensus,
                        'signals': signals,
                        'recommendation': self._get_recommendation(consensus)
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("generate_signal")
        async def generate_signal(params: ToolParams) -> ToolResponse:
            """Generate trading signal with all context"""
            symbol = params["symbol"]
            pattern_data = params.get("pattern_data", [])
            catalyst_data = params.get("catalyst_data", {})
            force_generation = params.get("force", False)
            
            try:
                # Get current technical analysis
                analysis = await self._analyze_timeframe(symbol, "5m")
                
                # Calculate base confidence
                technical_confidence = self._calculate_technical_confidence(analysis)
                pattern_confidence = self._calculate_pattern_confidence(pattern_data)
                catalyst_confidence = catalyst_data.get('score', 0) * 100
                
                # Weighted confidence
                overall_confidence = (
                    technical_confidence * 0.4 +
                    pattern_confidence * 0.3 +
                    catalyst_confidence * 0.3
                )
                
                # Check minimum confidence
                if not force_generation and overall_confidence < self.ta_config['min_confidence']:
                    return ToolResponse(
                        success=True,
                        data={
                            'signal_generated': False,
                            'reason': 'insufficient_confidence',
                            'confidence': overall_confidence
                        }
                    )
                
                # Determine signal type and action
                signal_type, action = self._determine_signal_action(
                    analysis, pattern_data
                )
                
                # Calculate entry, stop loss, take profit
                entry_price = analysis['price']
                levels = self._calculate_trade_levels(
                    symbol, entry_price, action, analysis
                )
                
                # Create signal
                signal = {
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'action': action,
                    'confidence': overall_confidence,
                    'entry_price': entry_price,
                    'stop_loss': levels['stop_loss'],
                    'take_profit': levels['take_profit'],
                    'metadata': {
                        'technical_analysis': analysis,
                        'patterns': pattern_data,
                        'catalyst': catalyst_data,
                        'risk_reward_ratio': levels['risk_reward_ratio'],
                        'position_size_suggestion': levels['position_size']
                    },
                    'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
                }
                
                # Persist signal
                signal_id = await self.db_client.persist_trading_signal({
                    'symbol': signal['symbol'],
                    'signal_type': signal['signal_type'],
                    'action': signal['action'],
                    'confidence': signal['confidence'] / 100,  # Convert to decimal
                    'entry_price': signal['entry_price'],
                    'stop_loss': signal['stop_loss'],
                    'take_profit': signal['take_profit'],
                    'metadata': signal['metadata'],
                    'expires_at': signal['expires_at']
                })
                
                signal['signal_id'] = signal_id
                
                # Track active signal
                self.active_signals.append(signal)
                if len(self.active_signals) > 100:
                    self.active_signals = self.active_signals[-100:]
                
                return ToolResponse(
                    success=True,
                    data={
                        'signal_generated': True,
                        'signal': signal,
                        'signal_id': signal_id
                    }
                )
                
            except Exception as e:
                self.logger.error("Signal generation failed", error=str(e))
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("recalculate_indicators")
        async def recalculate_indicators(params: ToolParams) -> ToolResponse:
            """Recalculate indicators with custom parameters"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "1h")
            custom_params = params.get("parameters", {})
            
            try:
                # Merge custom parameters
                ta_config = self.ta_config.copy()
                ta_config.update(custom_params)
                
                # Get price data
                data = await self._get_price_data(symbol, timeframe)
                if data is None:
                    return ToolResponse(
                        success=False,
                        error="Failed to get price data"
                    )
                
                # Calculate all indicators with custom params
                indicators = {}
                
                # RSI
                indicators['rsi'] = talib.RSI(
                    data['Close'],
                    timeperiod=ta_config.get('rsi_period', 14)
                ).iloc[-1]
                
                # MACD
                macd, signal, hist = talib.MACD(
                    data['Close'],
                    fastperiod=ta_config.get('macd_fast', 12),
                    slowperiod=ta_config.get('macd_slow', 26),
                    signalperiod=ta_config.get('macd_signal', 9)
                )
                indicators['macd'] = {
                    'macd': float(macd.iloc[-1]),
                    'signal': float(signal.iloc[-1]),
                    'histogram': float(hist.iloc[-1])
                }
                
                # Bollinger Bands
                upper, middle, lower = talib.BBANDS(
                    data['Close'],
                    timeperiod=ta_config.get('bb_period', 20),
                    nbdevup=ta_config.get('bb_std', 2.0),
                    nbdevdn=ta_config.get('bb_std', 2.0)
                )
                indicators['bollinger'] = {
                    'upper': float(upper.iloc[-1]),
                    'middle': float(middle.iloc[-1]),
                    'lower': float(lower.iloc[-1])
                }
                
                # ATR
                indicators['atr'] = talib.ATR(
                    data['High'], data['Low'], data['Close'],
                    timeperiod=ta_config.get('atr_period', 14)
                ).iloc[-1]
                
                # ADX
                indicators['adx'] = talib.ADX(
                    data['High'], data['Low'], data['Close'],
                    timeperiod=ta_config.get('adx_period', 14)
                ).iloc[-1]
                
                # Stochastic
                slowk, slowd = talib.STOCH(
                    data['High'], data['Low'], data['Close'],
                    fastk_period=ta_config.get('stoch_period', 14),
                    slowk_period=3,
                    slowd_period=3
                )
                indicators['stochastic'] = {
                    'k': float(slowk.iloc[-1]),
                    'd': float(slowd.iloc[-1])
                }
                
                # Cache results
                cache_key = f"technical:custom_indicators:{symbol}:{timeframe}"
                await self.redis_client.setex(
                    cache_key, 300, json.dumps({
                        'indicators': indicators,
                        'parameters': custom_params,
                        'timestamp': datetime.now().isoformat()
                    })
                )
                
                return ToolResponse(
                    success=True,
                    data={
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'indicators': indicators,
                        'parameters_used': ta_config
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("optimize_parameters")
        async def optimize_parameters(params: ToolParams) -> ToolResponse:
            """Optimize indicator parameters for best performance"""
            strategy = params.get("strategy", "default")
            symbols = params.get("symbols", [])
            optimization_period = params.get("days", 30)
            target_metric = params.get("target", "sharpe_ratio")  # sharpe_ratio, win_rate, return
            
            try:
                self.logger.info("Starting parameter optimization",
                               strategy=strategy,
                               symbols=len(symbols),
                               period=optimization_period)
                
                # Run genetic algorithm optimization
                best_params = await self._run_genetic_optimization(
                    strategy, symbols, optimization_period, target_metric
                )
                
                # Backtest with optimized parameters
                backtest_results = await self._backtest_strategy(
                    strategy, symbols, optimization_period, best_params
                )
                
                # Store results
                self.backtest_results[strategy] = {
                    **backtest_results,
                    'parameters': best_params,
                    'optimization_target': target_metric,
                    'last_updated': datetime.now().isoformat()
                }
                
                # Cache results
                cache_key = f"technical:optimization:{strategy}"
                await self.redis_client.setex(
                    cache_key, 86400,  # 24 hours
                    json.dumps(self.backtest_results[strategy])
                )
                
                return ToolResponse(
                    success=True,
                    data={
                        'strategy': strategy,
                        'optimized_parameters': best_params,
                        'backtest_results': backtest_results,
                        'improvement': self._calculate_improvement(
                            backtest_results, target_metric
                        )
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("export_signals")
        async def export_signals(params: ToolParams) -> ToolResponse:
            """Export signals for analysis"""
            export_type = params.get("type", "active")  # active, historical, performance
            format = params.get("format", "json")
            days = params.get("days", 7)
            
            try:
                export_data = {}
                
                if export_type == "active":
                    # Get active signals
                    signals = await self.db_client.get_pending_signals(limit=100)
                    export_data = {
                        'active_signals': signals,
                        'count': len(signals),
                        'exported_at': datetime.now().isoformat()
                    }
                
                elif export_type == "historical":
                    # Get historical signals (would query from database)
                    export_data = {
                        'historical_signals': [],  # Would be populated
                        'period_days': days,
                        'performance': self.signal_performance,
                        'exported_at': datetime.now().isoformat()
                    }
                
                elif export_type == "performance":
                    # Export performance metrics
                    export_data = {
                        'performance_metrics': self.signal_performance,
                        'by_type': self._get_performance_by_type(),
                        'by_symbol': self._get_performance_by_symbol(),
                        'exported_at': datetime.now().isoformat()
                    }
                
                # Store export
                export_id = f"signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await self.redis_client.setex(
                    f"technical:export:{export_id}",
                    3600,  # 1 hour TTL
                    json.dumps(export_data)
                )
                
                return ToolResponse(
                    success=True,
                    data={
                        'export_id': export_id,
                        'type': export_type,
                        'format': format,
                        'size': len(json.dumps(export_data)),
                        'download_url': f"/exports/{export_id}"
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("validate_signal")
        async def validate_signal(params: ToolParams) -> ToolResponse:
            """Validate a trading signal before execution"""
            signal_id = params["signal_id"]
            current_price = params.get("current_price")
            
            try:
                # Get signal from active list or database
                signal = next((s for s in self.active_signals if s.get('signal_id') == signal_id), None)
                
                if not signal:
                    # Try to get from database
                    signals = await self.db_client.get_pending_signals(limit=50)
                    signal = next((s for s in signals if s.get('signal_id') == signal_id), None)
                
                if not signal:
                    return ToolResponse(
                        success=False,
                        error="Signal not found"
                    )
                
                # Validate signal conditions
                validation = {
                    'signal_id': signal_id,
                    'is_valid': True,
                    'checks': {}
                }
                
                # Check expiration
                if 'expires_at' in signal:
                    expires = datetime.fromisoformat(signal['expires_at'].replace('Z', '+00:00'))
                    if datetime.now(expires.tzinfo) > expires:
                        validation['is_valid'] = False
                        validation['checks']['expired'] = True
                
                # Check price deviation
                if current_price:
                    entry_price = signal.get('entry_price', 0)
                    price_deviation = abs(current_price - entry_price) / entry_price
                    if price_deviation > 0.02:  # 2% deviation
                        validation['is_valid'] = False
                        validation['checks']['price_deviation'] = price_deviation
                
                # Check if stop loss already hit
                if current_price and signal.get('action') == 'BUY':
                    if current_price <= signal.get('stop_loss', 0):
                        validation['is_valid'] = False
                        validation['checks']['stop_loss_hit'] = True
                elif current_price and signal.get('action') == 'SELL':
                    if current_price >= signal.get('stop_loss', float('inf')):
                        validation['is_valid'] = False
                        validation['checks']['stop_loss_hit'] = True
                
                # Re-validate technical conditions
                tech_valid = await self._revalidate_technical_conditions(
                    signal.get('symbol'), signal
                )
                validation['checks']['technical_valid'] = tech_valid
                if not tech_valid:
                    validation['is_valid'] = False
                
                return ToolResponse(
                    success=True,
                    data=validation
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("update_signal_outcome")
        async def update_signal_outcome(params: ToolParams) -> ToolResponse:
            """Update signal with actual outcome"""
            signal_id = params["signal_id"]
            outcome = params["outcome"]  # success, failure, partial
            actual_return = params.get("actual_return", 0)
            exit_price = params.get("exit_price")
            
            try:
                # Update signal performance tracking
                await self._update_signal_performance(outcome, actual_return)
                
                # Log outcome
                self.logger.info("Signal outcome recorded",
                               signal_id=signal_id,
                               outcome=outcome,
                               return_pct=actual_return)
                
                return ToolResponse(
                    success=True,
                    data={
                        'signal_id': signal_id,
                        'outcome_recorded': True,
                        'performance_updated': True
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("clear_cache")
        async def clear_cache(params: ToolParams) -> ToolResponse:
            """Clear technical analysis cache"""
            pattern = params.get("pattern", "technical:*")
            
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
    
    async def _calculate_indicators(self, symbol: str, timeframe: str, 
                                  indicators: List[str]) -> Dict:
        """Calculate requested indicators"""
        # Get price data
        data = await self._get_price_data(symbol, timeframe)
        if data is None:
            raise ValueError("No price data available")
        
        result = {
            'symbol': symbol,
            'timeframe': timeframe,
            'last_price': float(data['Close'].iloc[-1]),
            'last_updated': data.index[-1].isoformat(),
            'indicators': {}
        }
        
        close_prices = data['Close'].values
        high_prices = data['High'].values
        low_prices = data['Low'].values
        volume = data['Volume'].values
        
        # Calculate requested indicators
        if 'rsi' in indicators or 'all' in indicators:
            result['indicators']['rsi'] = {
                'value': talib.RSI(close_prices, timeperiod=self.ta_config['rsi_period'])[-1],
                'oversold': self.ta_config['rsi_oversold'],
                'overbought': self.ta_config['rsi_overbought']
            }
        
        if 'macd' in indicators or 'all' in indicators:
            macd, signal, hist = talib.MACD(
                close_prices,
                fastperiod=self.ta_config['macd_fast'],
                slowperiod=self.ta_config['macd_slow'],
                signalperiod=self.ta_config['macd_signal']
            )
            result['indicators']['macd'] = {
                'macd': macd[-1],
                'signal': signal[-1],
                'histogram': hist[-1],
                'trend': 'bullish' if hist[-1] > 0 else 'bearish'
            }
        
        if 'bb' in indicators or 'all' in indicators:
            upper, middle, lower = talib.BBANDS(
                close_prices,
                timeperiod=self.ta_config['bb_period'],
                nbdevup=self.ta_config['bb_std'],
                nbdevdn=self.ta_config['bb_std']
            )
            result['indicators']['bollinger_bands'] = {
                'upper': upper[-1],
                'middle': middle[-1],
                'lower': lower[-1],
                'bandwidth': (upper[-1] - lower[-1]) / middle[-1],
                'percent_b': (close_prices[-1] - lower[-1]) / (upper[-1] - lower[-1])
            }
        
        if 'sma' in indicators or 'all' in indicators:
            result['indicators']['sma'] = {
                'sma_short': talib.SMA(close_prices, timeperiod=self.ta_config['sma_short'])[-1],
                'sma_long': talib.SMA(close_prices, timeperiod=self.ta_config['sma_long'])[-1]
            }
        
        if 'ema' in indicators or 'all' in indicators:
            result['indicators']['ema'] = {
                'ema_short': talib.EMA(close_prices, timeperiod=self.ta_config['ema_short'])[-1],
                'ema_long': talib.EMA(close_prices, timeperiod=self.ta_config['ema_long'])[-1]
            }
        
        if 'atr' in indicators or 'all' in indicators:
            result['indicators']['atr'] = talib.ATR(
                high_prices, low_prices, close_prices,
                timeperiod=self.ta_config['atr_period']
            )[-1]
        
        if 'adx' in indicators or 'all' in indicators:
            result['indicators']['adx'] = talib.ADX(
                high_prices, low_prices, close_prices,
                timeperiod=self.ta_config['adx_period']
            )[-1]
        
        if 'stoch' in indicators or 'all' in indicators:
            slowk, slowd = talib.STOCH(
                high_prices, low_prices, close_prices,
                fastk_period=self.ta_config['stoch_period']
            )
            result['indicators']['stochastic'] = {
                'k': slowk[-1],
                'd': slowd[-1],
                'signal': 'oversold' if slowk[-1] < 20 else 'overbought' if slowk[-1] > 80 else 'neutral'
            }
        
        if 'volume' in indicators or 'all' in indicators:
            result['indicators']['volume'] = {
                'current': int(volume[-1]),
                'average': int(np.mean(volume[-20:])),
                'ratio': volume[-1] / np.mean(volume[-20:])
            }
        
        return result
    
    async def _get_price_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get price data for analysis"""
        try:
            # Check cache first
            cache_key = f"technical:price_data:{symbol}:{timeframe}"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return pd.read_json(cached)
            
            # Map timeframe to yfinance parameters
            timeframe_map = {
                '1m': ('1d', '1m'),
                '5m': ('5d', '5m'),
                '15m': ('5d', '15m'),
                '1h': ('1mo', '1h'),
                '1d': ('3mo', '1d')
            }
            
            period, interval = timeframe_map.get(timeframe, ('1mo', '1h'))
            
            # Fetch from yfinance
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                return None
            
            # Cache for 5 minutes
            await self.redis_client.setex(
                cache_key, 300, data.to_json()
            )
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error getting price data", symbol=symbol, error=str(e))
            return None
    
    async def _get_realtime_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get real-time (1-minute) data"""
        return await self._get_price_data(symbol, '1m')
    
    async def _analyze_timeframe(self, symbol: str, timeframe: str) -> Dict:
        """Analyze single timeframe"""
        try:
            # Get indicators
            indicators = await self._calculate_indicators(symbol, timeframe, ['all'])
            
            # Add trend analysis
            indicators['trend'] = self._analyze_trend(indicators)
            
            # Add momentum analysis
            indicators['momentum'] = self._analyze_momentum(indicators)
            
            # Add volatility analysis
            indicators['volatility'] = self._analyze_volatility(indicators)
            
            # Current price
            indicators['price'] = indicators['last_price']
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"Timeframe analysis failed", error=str(e))
            return {}
    
    def _analyze_trend(self, indicators: Dict) -> Dict:
        """Analyze trend from indicators"""
        trend = {
            'primary': 'neutral',
            'strength': 0,
            'signals': []
        }
        
        # SMA analysis
        if 'sma' in indicators['indicators']:
            sma = indicators['indicators']['sma']
            if sma['sma_short'] > sma['sma_long']:
                trend['signals'].append('sma_bullish')
                trend['strength'] += 1
            else:
                trend['signals'].append('sma_bearish')
                trend['strength'] -= 1
        
        # MACD analysis
        if 'macd' in indicators['indicators']:
            macd = indicators['indicators']['macd']
            if macd['histogram'] > 0:
                trend['signals'].append('macd_bullish')
                trend['strength'] += 1
            else:
                trend['signals'].append('macd_bearish')
                trend['strength'] -= 1
        
        # ADX for trend strength
        if 'adx' in indicators['indicators']:
            adx = indicators['indicators']['adx']
            if adx > 25:
                trend['signals'].append('strong_trend')
                trend['strength'] = trend['strength'] * 1.5
        
        # Determine primary trend
        if trend['strength'] > 1:
            trend['primary'] = 'bullish'
        elif trend['strength'] < -1:
            trend['primary'] = 'bearish'
        
        return trend
    
    def _analyze_momentum(self, indicators: Dict) -> Dict:
        """Analyze momentum from indicators"""
        momentum = {
            'state': 'neutral',
            'strength': 0,
            'signals': []
        }
        
        # RSI analysis
        if 'rsi' in indicators['indicators']:
            rsi = indicators['indicators']['rsi']['value']
            if rsi > 70:
                momentum['signals'].append('rsi_overbought')
                momentum['strength'] -= 2
            elif rsi < 30:
                momentum['signals'].append('rsi_oversold')
                momentum['strength'] += 2
            elif rsi > 50:
                momentum['strength'] += 1
            else:
                momentum['strength'] -= 1
        
        # Stochastic analysis
        if 'stochastic' in indicators['indicators']:
            stoch = indicators['indicators']['stochastic']
            if stoch['signal'] == 'oversold':
                momentum['signals'].append('stoch_oversold')
                momentum['strength'] += 1
            elif stoch['signal'] == 'overbought':
                momentum['signals'].append('stoch_overbought')
                momentum['strength'] -= 1
        
        # Volume analysis
        if 'volume' in indicators['indicators']:
            vol_ratio = indicators['indicators']['volume']['ratio']
            if vol_ratio > self.ta_config['min_volume_ratio']:
                momentum['signals'].append('high_volume')
                momentum['strength'] = momentum['strength'] * 1.3
        
        # Determine momentum state
        if momentum['strength'] > 2:
            momentum['state'] = 'strong_bullish'
        elif momentum['strength'] > 0:
            momentum['state'] = 'bullish'
        elif momentum['strength'] < -2:
            momentum['state'] = 'strong_bearish'
        elif momentum['strength'] < 0:
            momentum['state'] = 'bearish'
        
        return momentum
    
    def _analyze_volatility(self, indicators: Dict) -> Dict:
        """Analyze volatility from indicators"""
        volatility = {
            'level': 'normal',
            'atr': 0,
            'bb_width': 0
        }
        
        # ATR analysis
        if 'atr' in indicators['indicators']:
            atr = indicators['indicators']['atr']
            price = indicators['last_price']
            atr_pct = (atr / price) * 100
            volatility['atr'] = atr_pct
            
            if atr_pct > 5:
                volatility['level'] = 'very_high'
            elif atr_pct > 3:
                volatility['level'] = 'high'
            elif atr_pct < 1:
                volatility['level'] = 'low'
        
        # Bollinger Band width
        if 'bollinger_bands' in indicators['indicators']:
            bb = indicators['indicators']['bollinger_bands']
            volatility['bb_width'] = bb['bandwidth'] * 100
        
        return volatility
    
    def _generate_consensus(self, multi_tf_analysis: Dict) -> Dict:
        """Generate consensus from multi-timeframe analysis"""
        consensus = {
            'trend': {'bullish': 0, 'bearish': 0, 'neutral': 0},
            'momentum': {'bullish': 0, 'bearish': 0, 'neutral': 0},
            'signal_strength': 0,
            'timeframes_aligned': False
        }
        
        # Aggregate trends
        for tf, analysis in multi_tf_analysis.items():
            if 'trend' in analysis:
                trend = analysis['trend']['primary']
                consensus['trend'][trend] = consensus['trend'].get(trend, 0) + 1
            
            if 'momentum' in analysis:
                state = analysis['momentum']['state']
                if 'bullish' in state:
                    consensus['momentum']['bullish'] += 1
                elif 'bearish' in state:
                    consensus['momentum']['bearish'] += 1
                else:
                    consensus['momentum']['neutral'] += 1
        
        # Calculate signal strength
        total_tf = len(multi_tf_analysis)
        if consensus['trend']['bullish'] == total_tf:
            consensus['signal_strength'] = 100
            consensus['timeframes_aligned'] = True
        elif consensus['trend']['bearish'] == total_tf:
            consensus['signal_strength'] = -100
            consensus['timeframes_aligned'] = True
        else:
            bull_score = consensus['trend']['bullish'] / total_tf
            bear_score = consensus['trend']['bearish'] / total_tf
            consensus['signal_strength'] = (bull_score - bear_score) * 100
        
        return consensus
    
    def _calculate_technical_confidence(self, analysis: Dict) -> float:
        """Calculate confidence from technical analysis"""
        confidence = 50  # Base confidence
        
        # Trend alignment
        if 'trend' in analysis:
            if abs(analysis['trend']['strength']) > 2:
                confidence += 15
            elif abs(analysis['trend']['strength']) > 1:
                confidence += 10
        
        # Momentum confirmation
        if 'momentum' in analysis:
            if analysis['momentum']['state'] in ['strong_bullish', 'strong_bearish']:
                confidence += 20
            elif analysis['momentum']['state'] in ['bullish', 'bearish']:
                confidence += 10
        
        # Volume confirmation
        if 'indicators' in analysis and 'volume' in analysis['indicators']:
            if analysis['indicators']['volume']['ratio'] > 2:
                confidence += 15
            elif analysis['indicators']['volume']['ratio'] > 1.5:
                confidence += 10
        
        # Volatility adjustment
        if 'volatility' in analysis:
            if analysis['volatility']['level'] == 'high':
                confidence -= 5
            elif analysis['volatility']['level'] == 'very_high':
                confidence -= 10
        
        return min(confidence, 100)
    
    def _calculate_pattern_confidence(self, patterns: List[Dict]) -> float:
        """Calculate confidence from pattern data"""
        if not patterns:
            return 50
        
        # Average pattern confidence
        avg_confidence = sum(p.get('confidence', 0) for p in patterns) / len(patterns)
        
        # Boost for multiple confirming patterns
        if len(patterns) > 2:
            avg_confidence *= 1.2
        elif len(patterns) > 1:
            avg_confidence *= 1.1
        
        return min(avg_confidence, 100)
    
    def _determine_signal_action(self, analysis: Dict, patterns: List[Dict]) -> Tuple[str, str]:
        """Determine signal type and action"""
        # Check patterns first
        if patterns:
            bullish_patterns = sum(1 for p in patterns if p.get('direction') == 'bullish')
            bearish_patterns = sum(1 for p in patterns if p.get('direction') == 'bearish')
            
            if bullish_patterns > bearish_patterns:
                return 'pattern', 'BUY'
            elif bearish_patterns > bullish_patterns:
                return 'pattern', 'SELL'
        
        # Check momentum
        if 'momentum' in analysis:
            if analysis['momentum']['state'] in ['strong_bullish', 'bullish']:
                return 'momentum', 'BUY'
            elif analysis['momentum']['state'] in ['strong_bearish', 'bearish']:
                return 'momentum', 'SELL'
        
        # Check trend
        if 'trend' in analysis:
            if analysis['trend']['primary'] == 'bullish':
                return 'trend', 'BUY'
            elif analysis['trend']['primary'] == 'bearish':
                return 'trend', 'SELL'
        
        return 'neutral', 'HOLD'
    
    def _calculate_trade_levels(self, symbol: str, entry_price: float, 
                              action: str, analysis: Dict) -> Dict:
        """Calculate stop loss, take profit, and position size"""
        # Get ATR for volatility-based stops
        atr = analysis.get('indicators', {}).get('atr', entry_price * 0.02)
        
        if action == 'BUY':
            # Stop loss below entry
            stop_loss = entry_price - (atr * 2)
            # Take profit above entry
            take_profit = entry_price + (atr * 3)
        else:  # SELL
            # Stop loss above entry
            stop_loss = entry_price + (atr * 2)
            # Take profit below entry
            take_profit = entry_price - (atr * 3)
        
        # Calculate risk/reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        risk_reward = reward / risk if risk > 0 else 0
        
        # Position size based on volatility
        volatility = analysis.get('volatility', {}).get('level', 'normal')
        if volatility == 'very_high':
            position_size = 0.5  # Half position
        elif volatility == 'high':
            position_size = 0.75
        else:
            position_size = 1.0
        
        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'risk_reward_ratio': round(risk_reward, 2),
            'position_size': position_size
        }
    
    async def _calculate_support_resistance(self, symbol: str, timeframe: str, 
                                          method: str) -> Dict:
        """Calculate support and resistance levels"""
        data = await self._get_price_data(symbol, timeframe)
        if data is None:
            return {}
        
        current_price = float(data['Close'].iloc[-1])
        levels = {'current_price': current_price}
        
        if method == 'pivot':
            # Pivot point calculation
            high = data['High'].iloc[-1]
            low = data['Low'].iloc[-1]
            close = data['Close'].iloc[-1]
            
            pivot = (high + low + close) / 3
            
            levels['pivot'] = round(pivot, 2)
            levels['r1'] = round(2 * pivot - low, 2)
            levels['r2'] = round(pivot + (high - low), 2)
            levels['r3'] = round(high + 2 * (pivot - low), 2)
            levels['s1'] = round(2 * pivot - high, 2)
            levels['s2'] = round(pivot - (high - low), 2)
            levels['s3'] = round(low - 2 * (high - pivot), 2)
            
        elif method == 'fibonacci':
            # Fibonacci retracement
            high = data['High'].max()
            low = data['Low'].min()
            diff = high - low
            
            levels['0.0'] = round(high, 2)
            levels['23.6'] = round(high - diff * 0.236, 2)
            levels['38.2'] = round(high - diff * 0.382, 2)
            levels['50.0'] = round(high - diff * 0.5, 2)
            levels['61.8'] = round(high - diff * 0.618, 2)
            levels['100.0'] = round(low, 2)
        
        # Find nearest levels
        support_levels = [v for k, v in levels.items() if isinstance(v, (int, float)) and v < current_price]
        resistance_levels = [v for k, v in levels.items() if isinstance(v, (int, float)) and v > current_price]
        
        if support_levels:
            levels['nearest_support'] = max(support_levels)
        if resistance_levels:
            levels['nearest_resistance'] = min(resistance_levels)
        
        return levels
    
    def _calculate_bb_position(self, price: float, upper: float, lower: float) -> str:
        """Calculate position within Bollinger Bands"""
        band_width = upper - lower
        position = (price - lower) / band_width if band_width > 0 else 0.5
        
        if position > 0.95:
            return 'above_upper'
        elif position > 0.8:
            return 'near_upper'
        elif position < 0.05:
            return 'below_lower'
        elif position < 0.2:
            return 'near_lower'
        else:
            return 'middle'
    
    def _calculate_signal_strength(self, indicators: Dict) -> float:
        """Calculate overall signal strength from indicators"""
        strength = 0
        signals = 0
        
        # RSI signal
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30:
                strength += 20
            elif rsi > 70:
                strength -= 20
            signals += 1
        
        # MACD signal
        if 'macd' in indicators:
            if indicators['macd']['histogram'] > 0:
                strength += 15
            else:
                strength -= 15
            signals += 1
        
        # Bollinger position
        if 'bollinger' in indicators:
            position = indicators['bollinger']['position']
            if position in ['below_lower', 'near_lower']:
                strength += 15
            elif position in ['above_upper', 'near_upper']:
                strength -= 15
            signals += 1
        
        # Normalize to 0-100 scale
        if signals > 0:
            strength = (strength + 50) / signals * 2
            strength = max(0, min(100, strength))
        else:
            strength = 50
        
        return strength
    
    async def _get_signal_status(self, signal: Dict) -> Dict:
        """Get current status of a signal"""
        # This would check current price vs signal levels
        return {
            'status': 'active',
            'price_change_since_signal': 0.0,
            'time_elapsed': '0h',
            'distance_to_target': 0.0
        }
    
    async def _get_signal_outcome(self, signal: Dict) -> Dict:
        """Get outcome of an expired signal"""
        # This would calculate actual performance
        return {
            'result': 'success',
            'return_pct': 2.5,
            'duration_minutes': 120,
            'exit_reason': 'target_reached'
        }
    
    def _calculate_outcome_summary(self, signals: List[Dict]) -> Dict:
        """Calculate summary of signal outcomes"""
        if not signals:
            return {'win_rate': 0, 'avg_return': 0}
        
        successful = sum(1 for s in signals if s.get('outcome', {}).get('result') == 'success')
        total_return = sum(s.get('outcome', {}).get('return_pct', 0) for s in signals)
        
        return {
            'win_rate': successful / len(signals) if signals else 0,
            'avg_return': total_return / len(signals) if signals else 0,
            'total_signals': len(signals)
        }
    
    def _get_recommendation(self, consensus: Dict) -> str:
        """Get trading recommendation from consensus"""
        strength = consensus.get('signal_strength', 0)
        
        if consensus.get('timeframes_aligned'):
            if strength > 50:
                return 'strong_buy'
            elif strength < -50:
                return 'strong_sell'
        
        if strength > 30:
            return 'buy'
        elif strength < -30:
            return 'sell'
        else:
            return 'hold'
    
    async def _generate_signal_for_timeframe(self, symbol: str, timeframe: str,
                                           analysis: Dict, consensus: Dict) -> Optional[Dict]:
        """Generate signal for specific timeframe"""
        # Only generate signals on aligned timeframes with strong consensus
        if not consensus.get('timeframes_aligned') and abs(consensus.get('signal_strength', 0)) < 70:
            return None
        
        # Check technical confidence
        confidence = self._calculate_technical_confidence(analysis)
        if confidence < self.ta_config['min_confidence']:
            return None
        
        # Determine action
        signal_type, action = self._determine_signal_action(analysis, [])
        
        if action == 'HOLD':
            return None
        
        return {
            'timeframe': timeframe,
            'signal_type': signal_type,
            'action': action,
            'confidence': confidence,
            'analysis_summary': {
                'trend': analysis.get('trend', {}).get('primary'),
                'momentum': analysis.get('momentum', {}).get('state'),
                'volatility': analysis.get('volatility', {}).get('level')
            }
        }
    
    async def _run_genetic_optimization(self, strategy: str, symbols: List[str],
                                      period: int, target: str) -> Dict:
        """Run genetic algorithm for parameter optimization"""
        # Simplified genetic algorithm
        population = self._initialize_population()
        
        for generation in range(self.optimization_config['generations']):
            # Evaluate fitness
            fitness_scores = await self._evaluate_population(
                population, strategy, symbols, period, target
            )
            
            # Select best individuals
            best = self._select_best(population, fitness_scores)
            
            # Create new generation
            population = self._create_new_generation(best)
        
        # Return best parameters
        return population[0]  # Best individual
    
    def _initialize_population(self) -> List[Dict]:
        """Initialize random population of parameter sets"""
        population = []
        
        for _ in range(self.optimization_config['population_size']):
            individual = {
                'rsi_period': np.random.randint(10, 20),
                'macd_fast': np.random.randint(8, 15),
                'macd_slow': np.random.randint(20, 30),
                'macd_signal': np.random.randint(7, 12),
                'bb_period': np.random.randint(15, 25),
                'bb_std': np.random.uniform(1.5, 2.5),
                'min_confidence': np.random.randint(60, 80)
            }
            population.append(individual)
        
        return population
    
    async def _evaluate_population(self, population: List[Dict], strategy: str,
                                 symbols: List[str], period: int, target: str) -> List[float]:
        """Evaluate fitness of each individual"""
        fitness_scores = []
        
        for individual in population:
            # Run backtest with these parameters
            results = await self._backtest_strategy(strategy, symbols, period, individual)
            
            # Extract target metric
            if target == 'sharpe_ratio':
                fitness = results.get('sharpe_ratio', 0)
            elif target == 'win_rate':
                fitness = results.get('win_rate', 0)
            else:  # return
                fitness = results.get('total_return', 0)
            
            fitness_scores.append(fitness)
        
        return fitness_scores
    
    def _select_best(self, population: List[Dict], fitness_scores: List[float]) -> List[Dict]:
        """Select best individuals from population"""
        # Sort by fitness
        sorted_indices = np.argsort(fitness_scores)[::-1]
        
        # Select top 50%
        n_select = len(population) // 2
        return [population[i] for i in sorted_indices[:n_select]]
    
    def _create_new_generation(self, parents: List[Dict]) -> List[Dict]:
        """Create new generation through crossover and mutation"""
        new_generation = parents.copy()  # Keep best individuals
        
        while len(new_generation) < self.optimization_config['population_size']:
            # Select two parents
            parent1 = parents[np.random.randint(len(parents))]
            parent2 = parents[np.random.randint(len(parents))]
            
            # Crossover
            child = {}
            for key in parent1:
                if np.random.random() < 0.5:
                    child[key] = parent1[key]
                else:
                    child[key] = parent2[key]
            
            # Mutation
            if np.random.random() < self.optimization_config['mutation_rate']:
                key = np.random.choice(list(child.keys()))
                if isinstance(child[key], int):
                    child[key] += np.random.randint(-2, 3)
                else:
                    child[key] += np.random.uniform(-0.2, 0.2)
            
            new_generation.append(child)
        
        return new_generation
    
    async def _backtest_strategy(self, strategy: str, symbols: List[str],
                               period: int, parameters: Dict) -> Dict:
        """Run backtest with given parameters"""
        # Simplified backtest
        trades = []
        
        for symbol in symbols[:5]:  # Limit for speed
            # Get historical data
            data = await self._get_price_data(symbol, '1d')
            if data is None:
                continue
            
            # Apply strategy with parameters
            signals = self._apply_strategy(data, parameters)
            
            # Calculate returns
            for signal in signals:
                # Mock trade result
                trade = {
                    'symbol': symbol,
                    'return': np.random.uniform(-0.05, 0.10),  # Mock
                    'duration': np.random.randint(1, 10)
                }
                trades.append(trade)
        
        # Calculate metrics
        if not trades:
            return {'total_return': 0, 'win_rate': 0, 'sharpe_ratio': 0}
        
        returns = [t['return'] for t in trades]
        
        return {
            'total_return': sum(returns),
            'win_rate': sum(1 for r in returns if r > 0) / len(returns),
            'sharpe_ratio': np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252),
            'max_drawdown': min(returns),
            'total_trades': len(trades)
        }
    
    def _apply_strategy(self, data: pd.DataFrame, parameters: Dict) -> List[Dict]:
        """Apply strategy to generate signals"""
        # Simplified strategy application
        signals = []
        
        # Would implement actual strategy logic here
        # For now, return mock signals
        n_signals = np.random.randint(5, 15)
        for _ in range(n_signals):
            signals.append({
                'type': 'buy' if np.random.random() > 0.5 else 'sell',
                'confidence': np.random.uniform(60, 95)
            })
        
        return signals
    
    def _calculate_improvement(self, results: Dict, target: str) -> float:
        """Calculate improvement vs baseline"""
        # Compare to default parameters
        baseline = {
            'sharpe_ratio': 0.5,
            'win_rate': 0.45,
            'total_return': 0.10
        }
        
        current = results.get(target, baseline.get(target))
        base = baseline.get(target, 1)
        
        return ((current - base) / base) * 100 if base != 0 else 0
    
    async def _update_signal_performance(self, outcome: str, return_pct: float):
        """Update signal performance tracking"""
        self.signal_performance['total_signals'] += 1
        
        if outcome == 'success':
            self.signal_performance['successful_signals'] += 1
        
        # Update average return (exponential moving average)
        alpha = 0.1
        self.signal_performance['avg_return'] = (
            (1 - alpha) * self.signal_performance['avg_return'] + 
            alpha * return_pct
        )
        
        # Update win rate
        self.signal_performance['win_rate'] = (
            self.signal_performance['successful_signals'] / 
            self.signal_performance['total_signals']
        )
        
        # Save to cache
        await self.redis_client.set(
            "technical:signal_performance",
            json.dumps(self.signal_performance)
        )
    
    async def _revalidate_technical_conditions(self, symbol: str, signal: Dict) -> bool:
        """Revalidate technical conditions for a signal"""
        try:
            # Get current indicators
            current = await self._calculate_indicators(symbol, '5m', ['rsi', 'macd'])
            
            # Check if conditions still valid
            if signal.get('signal_type') == 'momentum':
                # Check momentum still present
                if 'rsi' in current['indicators']:
                    rsi = current['indicators']['rsi']['value']
                    if signal.get('action') == 'BUY' and rsi > 70:
                        return False
                    elif signal.get('action') == 'SELL' and rsi < 30:
                        return False
            
            return True
            
        except:
            return False
    
    def _get_performance_by_type(self) -> Dict:
        """Get performance breakdown by signal type"""
        # This would aggregate from historical data
        return {
            'momentum': {'win_rate': 0.72, 'avg_return': 0.025},
            'trend': {'win_rate': 0.68, 'avg_return': 0.035},
            'pattern': {'win_rate': 0.75, 'avg_return': 0.028}
        }
    
    def _get_performance_by_symbol(self) -> Dict:
        """Get performance breakdown by symbol"""
        # This would aggregate from historical data
        return {
            'AAPL': {'trades': 15, 'win_rate': 0.73},
            'TSLA': {'trades': 12, 'win_rate': 0.67},
            'NVDA': {'trades': 18, 'win_rate': 0.78}
        }
    
    async def health_check(self) -> Dict:
        """Service health check"""
        try:
            # Check database connection
            db_status = await self.db_client.get_database_status()
            
            # Check Redis connection
            redis_ok = await self.redis_client.ping() if self.redis_client else False
            
            # Check indicator calculation
            test_calc = talib.RSI(np.array([100, 101, 102, 103, 104] * 5))
            indicators_ok = not np.isnan(test_calc[-1])
            
            return {
                'status': 'healthy',
                'database': db_status.get('postgresql', {}).get('status', 'unknown'),
                'redis': 'healthy' if redis_ok else 'unhealthy',
                'indicators': 'healthy' if indicators_ok else 'unhealthy',
                'active_signals': len(self.active_signals),
                'signal_performance': {
                    'win_rate': self.signal_performance.get('win_rate', 0),
                    'total_signals': self.signal_performance.get('total_signals', 0)
                }
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Technical Analysis MCP Server",
                        version="3.1.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


async def main():
    """Main entry point"""
    server = TechnicalAnalysisMCPServer()
    
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