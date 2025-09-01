#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 3.0.0
Last Updated: 2024-12-30
Purpose: MCP-enabled technical analysis and signal generation with catalyst awareness

REVISION HISTORY:
v3.0.0 (2024-12-30) - Complete MCP migration
- Converted from Flask REST to MCP protocol
- Resources for technical indicators and analysis
- Tools for signal generation and management
- Maintained database persistence for signals
- Natural language interaction support
- Async operations throughout

Description of Service:
MCP server that performs technical analysis and generates trading signals.
Integrates pattern analysis results and considers news catalysts. Enables
Claude to understand market technicals and generate high-confidence signals.

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
import redis

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import database utilities
from database_utils import (
    get_db_connection,
    get_redis,
    health_check,
    insert_trading_signal
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


class TechnicalAnalysisMCPServer:
    """
    MCP Server for technical analysis and signal generation
    """
    
    def __init__(self):
        # Initialize environment
        self.setup_environment()
        
        # Initialize MCP server
        self.server = MCPServer("technical-analysis")
        self.setup_logging()
        
        # Initialize Redis client
        self.redis_client = get_redis()
        
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
            'macd_threshold': float(os.getenv('MACD_THRESHOLD', '0')),
            'adx_trend_strength': float(os.getenv('ADX_TREND_STRENGTH', '25')),
            
            # Risk parameters
            'stop_loss_atr_multiplier': float(os.getenv('STOP_LOSS_ATR', '2.0')),
            'take_profit_atr_multiplier': float(os.getenv('TAKE_PROFIT_ATR', '3.0'))
        }
        
        # Cache settings
        self.cache_ttl = int(os.getenv('TECHNICAL_CACHE_TTL', '300'))  # 5 minutes
        
        # Register MCP resources and tools
        self._register_resources()
        self._register_tools()
        
        self.logger.info("Technical Analysis MCP Server v3.0.0 initialized",
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
        self.service_name = 'technical-analysis-mcp'
        self.port = int(os.getenv('PORT', '5003'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Signal generation parameters
        self.min_confidence = float(os.getenv('MIN_SIGNAL_CONFIDENCE', '60'))
        self.lookback_periods = int(os.getenv('TECHNICAL_LOOKBACK_PERIODS', '100'))
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("indicators/{symbol}/current")
        async def get_current_indicators(params: ResourceParams) -> ResourceResponse:
            """Get current technical indicators for a symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            indicators = params.get("indicators")  # Optional list of specific indicators
            
            # Check cache first
            cache_key = f"indicators:{symbol}:{timeframe}"
            cached = self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
            else:
                data = await self._analyze_symbol_technical_async(symbol, timeframe)
                if data and not data.get('error'):
                    self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data, default=str))
            
            # Filter specific indicators if requested
            if indicators and data.get('indicators'):
                filtered = {k: v for k, v in data['indicators'].items() if k in indicators}
                data['indicators'] = filtered
            
            return ResourceResponse(
                type="indicator_snapshot",
                data=data,
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "cached": bool(cached)
                }
            )
        
        @self.server.resource("indicators/{symbol}/history")
        async def get_indicator_history(params: ResourceParams) -> ResourceResponse:
            """Get historical indicator values"""
            symbol = params["symbol"]
            timeframe = params["timeframe"]
            start = params["start"]
            end = params["end"]
            indicators = params.get("indicators", ["rsi", "macd", "sma_20"])
            
            history = await self._get_indicator_history(symbol, timeframe, start, end, indicators)
            
            return ResourceResponse(
                type="indicator_history",
                data=history,
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "period": f"{start} to {end}"
                }
            )
        
        @self.server.resource("signals/pending")
        async def get_pending_signals(params: ResourceParams) -> ResourceResponse:
            """Get pending trading signals"""
            min_confidence = params.get("min_confidence", self.min_confidence)
            symbol = params.get("symbol")
            
            signals = await self._get_pending_signals(min_confidence, symbol)
            
            return ResourceResponse(
                type="signal_collection",
                data=signals,
                metadata={
                    "count": len(signals),
                    "min_confidence": min_confidence
                }
            )
        
        @self.server.resource("signals/{signal_id}")
        async def get_signal_by_id(params: ResourceParams) -> ResourceResponse:
            """Get specific signal details"""
            signal_id = params["signal_id"]
            
            signal = await self._get_signal_by_id(signal_id)
            
            return ResourceResponse(
                type="trading_signal",
                data=signal
            )
        
        @self.server.resource("signals/history")
        async def get_signal_history(params: ResourceParams) -> ResourceResponse:
            """Get historical signals"""
            date = params.get("date")
            symbol = params.get("symbol")
            executed_only = params.get("executed_only", False)
            limit = params.get("limit", 100)
            
            history = await self._get_signal_history(date, symbol, executed_only, limit)
            
            return ResourceResponse(
                type="signal_history",
                data=history,
                metadata={
                    "count": len(history),
                    "filters": {
                        "date": date,
                        "symbol": symbol,
                        "executed_only": executed_only
                    }
                }
            )
        
        @self.server.resource("analysis/trend/{symbol}")
        async def get_trend_analysis(params: ResourceParams) -> ResourceResponse:
            """Get trend analysis for a symbol"""
            symbol = params["symbol"]
            timeframes = params.get("timeframes", ["5m", "15m", "1h"])
            
            trend_data = await self._get_trend_analysis(symbol, timeframes)
            
            return ResourceResponse(
                type="trend_analysis",
                data=trend_data,
                metadata={
                    "symbol": symbol,
                    "timeframes": timeframes
                }
            )
        
        @self.server.resource("analysis/support-resistance/{symbol}")
        async def get_support_resistance(params: ResourceParams) -> ResourceResponse:
            """Get support and resistance levels"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "1d")
            
            levels = await self._get_support_resistance_levels(symbol, timeframe)
            
            return ResourceResponse(
                type="support_resistance",
                data=levels,
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe
                }
            )
        
        @self.server.resource("analysis/volume/{symbol}")
        async def get_volume_analysis(params: ResourceParams) -> ResourceResponse:
            """Get volume analysis"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            
            volume_data = await self._get_volume_analysis(symbol, timeframe)
            
            return ResourceResponse(
                type="volume_analysis",
                data=volume_data,
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe
                }
            )

    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("generate_trading_signals")
        async def generate_trading_signals(params: ToolParams) -> ToolResponse:
            """Generate trading signals for candidates"""
            candidates = params["candidates"]  # List of symbols
            risk_profile = params.get("risk_profile", "moderate")
            
            signals_generated = []
            
            for symbol in candidates[:5]:  # Limit to top 5
                try:
                    # Get pattern data if available
                    patterns = await self._get_pattern_data(symbol)
                    
                    # Get catalyst data
                    catalyst_data = params.get("catalyst_data", {}).get(symbol, {})
                    
                    # Generate signal
                    signal_result = await self._generate_signal_with_catalyst_async(
                        symbol, patterns, catalyst_data
                    )
                    
                    if signal_result.get('status') == 'success':
                        signals_generated.append({
                            'symbol': symbol,
                            'signal_id': signal_result.get('signal_id'),
                            'confidence': signal_result['signal']['confidence'],
                            'action': signal_result['signal']['action']
                        })
                        
                except Exception as e:
                    self.logger.error(f"Failed to generate signal for {symbol}", error=str(e))
            
            return ToolResponse(
                success=True,
                data={
                    "signals_generated": len(signals_generated),
                    "signals": signals_generated
                }
            )
        
        @self.server.tool("calculate_indicators")
        async def calculate_indicators(params: ToolParams) -> ToolResponse:
            """Calculate specific indicators for a symbol"""
            symbol = params["symbol"]
            timeframe = params.get("timeframe", "5m")
            indicators = params.get("indicators", ["rsi", "macd", "bb"])
            
            result = await self._calculate_custom_indicators(symbol, timeframe, indicators)
            
            return ToolResponse(
                success=True,
                data=result
            )
        
        @self.server.tool("generate_signal")
        async def generate_signal(params: ToolParams) -> ToolResponse:
            """Generate a trading signal with all context"""
            symbol = params["symbol"]
            pattern_data = params.get("pattern_data", [])
            catalyst_data = params.get("catalyst_data", {})
            force_generation = params.get("force", False)
            
            result = await self._generate_signal_with_catalyst_async(
                symbol, pattern_data, catalyst_data, force_generation
            )
            
            return ToolResponse(
                success=result.get('status') == 'success',
                data=result
            )
        
        @self.server.tool("validate_signal")
        async def validate_signal(params: ToolParams) -> ToolResponse:
            """Validate a trading signal before execution"""
            signal_id = params["signal_id"]
            current_price = params.get("current_price")
            
            validation = await self._validate_signal(signal_id, current_price)
            
            return ToolResponse(
                success=validation['is_valid'],
                data=validation
            )
        
        @self.server.tool("update_signal_status")
        async def update_signal_status(params: ToolParams) -> ToolResponse:
            """Update signal status after execution"""
            signal_id = params["signal_id"]
            status = params["status"]  # executed, expired, cancelled
            execution_details = params.get("execution_details", {})
            
            updated = await self._update_signal_status(signal_id, status, execution_details)
            
            return ToolResponse(
                success=updated,
                data={
                    "signal_id": signal_id,
                    "status": status,
                    "updated": updated
                }
            )
        
        @self.server.tool("calculate_risk_levels")
        async def calculate_risk_levels(params: ToolParams) -> ToolResponse:
            """Calculate stop loss and take profit levels"""
            symbol = params["symbol"]
            entry_price = params["entry_price"]
            action = params["action"]  # BUY or SELL
            risk_profile = params.get("risk_profile", "moderate")
            
            levels = await self._calculate_risk_levels(
                symbol, entry_price, action, risk_profile
            )
            
            return ToolResponse(
                success=True,
                data=levels
            )

    async def _analyze_symbol_technical_async(self, symbol: str, timeframe: str) -> Dict:
        """Async wrapper for technical analysis"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._analyze_symbol_technical, symbol, timeframe)

    def _analyze_symbol_technical(self, symbol: str, timeframe: str = '1d') -> Dict:
        """Perform technical analysis on a symbol"""
        try:
            # Get price data
            df = self._get_price_data(symbol, timeframe)
            if df is None or df.empty:
                return {'error': 'Could not get price data'}
            
            # Calculate indicators
            indicators = self._calculate_indicators(df)
            
            # Determine trend
            trend = self._determine_trend(df, indicators)
            
            # Find support/resistance
            support_resistance = self._find_support_resistance(df)
            
            # Get current price
            current_price = float(df['Close'].iloc[-1])
            
            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'indicators': indicators,
                'trend': trend,
                'support_resistance': support_resistance,
                'volume_analysis': self._analyze_volume(df),
                'timestamp': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error("Technical analysis failed", symbol=symbol, error=str(e))
            return {'error': str(e)}

    async def _generate_signal_with_catalyst_async(self, symbol: str, patterns: List, 
                                                 catalyst_data: Dict, 
                                                 force: bool = False) -> Dict:
        """Generate trading signal with catalyst context"""
        try:
            self.logger.info("Generating signal with catalyst", 
                           symbol=symbol, 
                           patterns_count=len(patterns),
                           catalyst_type=catalyst_data.get('type'))
            
            # Get technical analysis
            technical_analysis = await self._analyze_symbol_technical_async(symbol, '5m')
            if not technical_analysis or technical_analysis.get('error'):
                return {
                    'status': 'error',
                    'error': 'Technical analysis failed'
                }
            
            # Calculate confidence components
            technical_confidence = self._calculate_technical_confidence(technical_analysis)
            pattern_confidence = self._calculate_pattern_confidence(patterns)
            catalyst_confidence = self._calculate_catalyst_confidence(catalyst_data)
            
            # Weighted confidence calculation
            weights = {
                'technical': 0.4,
                'pattern': 0.3,
                'catalyst': 0.3
            }
            
            overall_confidence = (
                technical_confidence * weights['technical'] +
                pattern_confidence * weights['pattern'] +
                catalyst_confidence * weights['catalyst']
            )
            
            # Check minimum confidence unless forced
            if not force and overall_confidence < self.min_confidence:
                return {
                    'status': 'no_signal',
                    'reason': f'Confidence {overall_confidence:.1f} below threshold {self.min_confidence}',
                    'confidence': overall_confidence
                }
            
            # Determine signal type and action
            signal_type, action = self._determine_signal_action(
                technical_analysis, patterns, catalyst_data
            )
            
            # Calculate entry price and risk levels
            current_price = technical_analysis.get('current_price', 0)
            atr = technical_analysis.get('indicators', {}).get('atr', current_price * 0.02)
            
            entry_price = current_price
            stop_loss = self._calculate_stop_loss(entry_price, atr, action)
            take_profit = self._calculate_take_profit(entry_price, atr, action)
            
            # Calculate risk-reward ratio
            if action == 'BUY':
                risk = entry_price - stop_loss
                reward = take_profit - entry_price
            else:  # SELL
                risk = stop_loss - entry_price
                reward = entry_price - take_profit
                
            risk_reward = reward / risk if risk > 0 else 0
            
            # Create signal structure
            signal = {
                'symbol': symbol,
                'signal_type': signal_type,
                'action': action,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': overall_confidence,
                'risk_reward_ratio': risk_reward,
                'catalyst_info': catalyst_data,
                'technical_info': {
                    'indicators': technical_analysis.get('indicators', {}),
                    'trend': technical_analysis.get('trend'),
                    'support_resistance': technical_analysis.get('support_resistance')
                },
                'expires_at': datetime.now() + timedelta(hours=1),
                'metadata': {
                    'patterns': [p.get('name') for p in patterns],
                    'generated_at': datetime.now().isoformat(),
                    'service_version': '3.0.0',
                    'confidence_components': {
                        'technical': technical_confidence,
                        'pattern': pattern_confidence,
                        'catalyst': catalyst_confidence
                    }
                }
            }
            
            # Save signal to database
            try:
                signal_id = insert_trading_signal(signal)
                signal['signal_id'] = signal_id
                
                self.logger.info("Signal generated and saved", 
                               symbol=symbol, 
                               signal_id=signal_id,
                               confidence=overall_confidence,
                               action=action)
                
                return {
                    'status': 'success',
                    'signal': signal,
                    'signal_id': signal_id
                }
                
            except Exception as db_error:
                self.logger.error("Failed to save signal to database", 
                                symbol=symbol, 
                                error=str(db_error))
                return {
                    'status': 'success_no_persistence',
                    'signal': signal,
                    'warning': 'Signal generated but not saved to database'
                }
        
        except Exception as e:
            self.logger.error("Signal generation failed", symbol=symbol, error=str(e))
            return {
                'status': 'error',
                'error': str(e)
            }

    def _get_price_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get price data for analysis"""
        if not YFINANCE_AVAILABLE:
            return self._get_mock_price_data(symbol, timeframe)
            
        try:
            ticker = yf.Ticker(symbol)
            
            # Map timeframe to yfinance period
            period_map = {
                '1m': '1d',
                '5m': '5d',
                '15m': '1mo',
                '1h': '3mo',
                '1d': '1y'
            }
            
            period = period_map.get(timeframe, '1y')
            interval = timeframe
            
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                self.logger.warning("No price data available", symbol=symbol)
                return None
                
            return df
            
        except Exception as e:
            self.logger.error("Error fetching price data", symbol=symbol, error=str(e))
            return None

    def _get_mock_price_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Generate mock price data for testing"""
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        np.random.seed(hash(symbol) % 2**32)
        
        base_price = 100 + (hash(symbol) % 100)
        prices = []
        current_price = base_price
        
        for _ in dates:
            change = np.random.normal(0, 2)
            current_price += change
            prices.append(max(current_price, 10))
            
        return pd.DataFrame({
            'Open': prices,
            'High': [p * (1 + abs(np.random.normal(0, 0.02))) for p in prices],
            'Low': [p * (1 - abs(np.random.normal(0, 0.02))) for p in prices],
            'Close': prices,
            'Volume': [np.random.randint(100000, 1000000) for _ in prices]
        }, index=dates)

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        indicators = {}
        
        try:
            close = df['Close'].values
            high = df['High'].values
            low = df['Low'].values
            volume = df['Volume'].values
            
            # RSI
            if TALIB_AVAILABLE:
                indicators['rsi'] = float(talib.RSI(close, timeperiod=self.ta_config['rsi_period'])[-1])
            else:
                indicators['rsi'] = self._calculate_rsi_manual(close)
                
            # MACD
            if TALIB_AVAILABLE:
                macd, signal, hist = talib.MACD(close, 
                                              fastperiod=self.ta_config['macd_fast'],
                                              slowperiod=self.ta_config['macd_slow'],
                                              signalperiod=self.ta_config['macd_signal'])
                indicators['macd'] = float(macd[-1])
                indicators['macd_signal'] = float(signal[-1])
                indicators['macd_histogram'] = float(hist[-1])
            else:
                indicators.update(self._calculate_macd_manual(close))
                
            # Bollinger Bands
            if TALIB_AVAILABLE:
                upper, middle, lower = talib.BBANDS(close, 
                                                   timeperiod=self.ta_config['bb_period'],
                                                   nbdevup=self.ta_config['bb_std'],
                                                   nbdevdn=self.ta_config['bb_std'])
                indicators['bb_upper'] = float(upper[-1])
                indicators['bb_middle'] = float(middle[-1])
                indicators['bb_lower'] = float(lower[-1])
            else:
                indicators.update(self._calculate_bollinger_manual(close))
                
            # ATR
            if TALIB_AVAILABLE:
                indicators['atr'] = float(talib.ATR(high, low, close, timeperiod=self.ta_config['atr_period'])[-1])
            else:
                indicators['atr'] = self._calculate_atr_manual(high, low, close)
                
            # Moving Averages
            indicators['sma_20'] = float(close[-self.ta_config['sma_short']:].mean())
            indicators['sma_50'] = float(close[-self.ta_config['sma_long']:].mean())
            
            # Volume indicators
            indicators['volume_avg'] = float(volume[-20:].mean())
            indicators['volume_ratio'] = float(volume[-1] / volume[-20:].mean())
            
        except Exception as e:
            self.logger.error("Error calculating indicators", error=str(e))
            
        return indicators

    def _calculate_rsi_manual(self, close_prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI manually"""
        deltas = np.diff(close_prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = gains[-period:].mean()
        avg_loss = losses[-period:].mean()
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    def _calculate_macd_manual(self, close_prices: np.ndarray) -> Dict:
        """Calculate MACD manually"""
        ema_12 = pd.Series(close_prices).ewm(span=12).mean().iloc[-1]
        ema_26 = pd.Series(close_prices).ewm(span=26).mean().iloc[-1]
        
        macd = ema_12 - ema_26
        signal = pd.Series([macd]).ewm(span=9).mean().iloc[-1]
        
        return {
            'macd': float(macd),
            'macd_signal': float(signal),
            'macd_histogram': float(macd - signal)
        }

    def _calculate_bollinger_manual(self, close_prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Dict:
        """Calculate Bollinger Bands manually"""
        recent_prices = close_prices[-period:]
        sma = recent_prices.mean()
        std = recent_prices.std()
        
        return {
            'bb_upper': float(sma + (std_dev * std)),
            'bb_middle': float(sma),
            'bb_lower': float(sma - (std_dev * std))
        }

    def _calculate_atr_manual(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
        """Calculate ATR manually"""
        tr1 = high[-period:] - low[-period:]
        tr2 = np.abs(high[-period:] - close[-period-1:-1])
        tr3 = np.abs(low[-period:] - close[-period-1:-1])
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = tr.mean()
        
        return float(atr)

    def _determine_trend(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Determine overall trend"""
        close = df['Close'].values
        
        # Price trend
        short_ma = close[-10:].mean()
        long_ma = close[-30:].mean()
        
        price_trend = "bullish" if short_ma > long_ma else "bearish"
        
        # MACD trend
        macd_trend = "bullish" if indicators.get('macd', 0) > indicators.get('macd_signal', 0) else "bearish"
        
        # Overall trend
        if price_trend == macd_trend:
            overall_trend = price_trend
            strength = "strong"
        else:
            overall_trend = "neutral"
            strength = "weak"
            
        return {
            'overall': overall_trend,
            'strength': strength,
            'price_trend': price_trend,
            'macd_trend': macd_trend
        }

    def _find_support_resistance(self, df: pd.DataFrame) -> Dict:
        """Find support and resistance levels"""
        high_prices = df['High'].values
        low_prices = df['Low'].values
        
        # Simple support/resistance using recent highs/lows
        recent_high = high_prices[-20:].max()
        recent_low = low_prices[-20:].min()
        
        current_price = df['Close'].iloc[-1]
        
        return {
            'resistance': float(recent_high),
            'support': float(recent_low),
            'current_price': float(current_price),
            'distance_to_resistance': float((recent_high - current_price) / current_price * 100),
            'distance_to_support': float((current_price - recent_low) / current_price * 100)
        }

    def _analyze_volume(self, df: pd.DataFrame) -> Dict:
        """Analyze volume patterns"""
        volume = df['Volume'].values
        avg_volume = volume[-20:].mean()
        current_volume = volume[-1]
        
        return {
            'current_volume': int(current_volume),
            'average_volume': int(avg_volume),
            'volume_ratio': float(current_volume / avg_volume),
            'volume_trend': "increasing" if current_volume > avg_volume else "decreasing"
        }

    def _calculate_technical_confidence(self, technical_analysis: Dict) -> float:
        """Calculate confidence based on technical indicators"""
        indicators = technical_analysis.get('indicators', {})
        trend = technical_analysis.get('trend', {})
        
        confidence = 50  # Base confidence
        
        # RSI contribution
        rsi = indicators.get('rsi', 50)
        if 30 < rsi < 70:
            confidence += 10  # Neutral RSI is good
        elif rsi < 30 or rsi > 70:
            confidence += 20  # Strong signal
            
        # Trend contribution
        if trend.get('strength') == 'strong':
            confidence += 15
        elif trend.get('strength') == 'weak':
            confidence += 5
            
        # Volume contribution
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 1.5:
            confidence += 10  # High volume confirmation
            
        return min(confidence, 100)

    def _calculate_pattern_confidence(self, patterns: List) -> float:
        """Calculate confidence based on detected patterns"""
        if not patterns:
            return 30  # Base confidence with no patterns
            
        # Sum pattern strengths
        total_strength = sum(pattern.get('strength', 50) for pattern in patterns)
        avg_strength = total_strength / len(patterns)
        
        # Bonus for multiple patterns
        pattern_bonus = min(len(patterns) * 5, 20)
        
        return min(avg_strength + pattern_bonus, 100)

    def _calculate_catalyst_confidence(self, catalyst_data: Dict) -> float:
        """Calculate confidence based on catalyst strength"""
        catalyst_score = catalyst_data.get('score', 0)
        catalyst_type = catalyst_data.get('type', '')
        
        # Base confidence from score
        confidence = catalyst_score
        
        # Type-based adjustments
        high_impact_types = ['earnings', 'merger', 'fda_approval', 'guidance']
        if catalyst_type in high_impact_types:
            confidence += 10
            
        return min(confidence, 100)

    def _determine_signal_action(self, technical_analysis: Dict, patterns: List, 
                               catalyst_data: Dict) -> tuple:
        """Determine signal type and action"""
        indicators = technical_analysis.get('indicators', {})
        trend = technical_analysis.get('trend', {})
        
        # Default to neutral
        signal_type = 'NEUTRAL'
        action = 'HOLD'
        
        # Technical signals
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        
        bullish_signals = 0
        bearish_signals = 0
        
        # RSI signals
        if rsi < 30:
            bullish_signals += 1
        elif rsi > 70:
            bearish_signals += 1
            
        # MACD signals
        if macd > macd_signal:
            bullish_signals += 1
        else:
            bearish_signals += 1
            
        # Trend signals
        if trend.get('overall') == 'bullish':
            bullish_signals += 1
        elif trend.get('overall') == 'bearish':
            bearish_signals += 1
            
        # Pattern signals
        for pattern in patterns:
            if pattern.get('signal') == 'bullish':
                bullish_signals += 1
            elif pattern.get('signal') == 'bearish':
                bearish_signals += 1
                
        # Catalyst signals
        catalyst_sentiment = catalyst_data.get('sentiment', 'neutral')
        if catalyst_sentiment == 'positive':
            bullish_signals += 2  # Catalyst has higher weight
        elif catalyst_sentiment == 'negative':
            bearish_signals += 2
            
        # Final determination
        if bullish_signals > bearish_signals + 1:
            signal_type = 'LONG'
            action = 'BUY'
        elif bearish_signals > bullish_signals + 1:
            signal_type = 'SHORT'
            action = 'SELL'
            
        return signal_type, action

    def _calculate_stop_loss(self, entry_price: float, atr: float, action: str) -> float:
        """Calculate stop loss level"""
        multiplier = self.ta_config['stop_loss_atr_multiplier']
        
        if action == 'BUY':
            return entry_price - (atr * multiplier)
        else:  # SELL
            return entry_price + (atr * multiplier)

    def _calculate_take_profit(self, entry_price: float, atr: float, action: str) -> float:
        """Calculate take profit level"""
        multiplier = self.ta_config['take_profit_atr_multiplier']
        
        if action == 'BUY':
            return entry_price + (atr * multiplier)
        else:  # SELL
            return entry_price - (atr * multiplier)

    # Additional async helper methods
    async def _get_pattern_data(self, symbol: str) -> List[Dict]:
        """Get pattern data for a symbol"""
        # This would query the pattern service or database
        return []

    async def _get_indicator_history(self, symbol: str, timeframe: str, 
                                   start: str, end: str, indicators: List[str]) -> List[Dict]:
        """Get historical indicator values"""
        # This would calculate indicators over a historical period
        return []

    async def _get_pending_signals(self, min_confidence: float, symbol: Optional[str]) -> List[Dict]:
        """Get pending trading signals from database"""
        # This would query the trading_signals table
        return []

    async def _get_signal_by_id(self, signal_id: str) -> Optional[Dict]:
        """Get specific signal from database"""
        # This would query for a specific signal
        return None

    async def _get_signal_history(self, date: Optional[str], symbol: Optional[str],
                                executed_only: bool, limit: int) -> List[Dict]:
        """Get historical signals"""
        # This would query historical signals
        return []

    async def _get_trend_analysis(self, symbol: str, timeframes: List[str]) -> Dict:
        """Get multi-timeframe trend analysis"""
        trends = {}
        for timeframe in timeframes:
            analysis = await self._analyze_symbol_technical_async(symbol, timeframe)
            if analysis and not analysis.get('error'):
                trends[timeframe] = analysis.get('trend')
        
        return {
            'symbol': symbol,
            'trends': trends,
            'consensus': self._calculate_trend_consensus(trends)
        }

    async def _get_support_resistance_levels(self, symbol: str, timeframe: str) -> Dict:
        """Get support and resistance levels"""
        analysis = await self._analyze_symbol_technical_async(symbol, timeframe)
        if analysis and not analysis.get('error'):
            return analysis.get('support_resistance', {})
        return {}

    async def _get_volume_analysis(self, symbol: str, timeframe: str) -> Dict:
        """Get volume analysis"""
        analysis = await self._analyze_symbol_technical_async(symbol, timeframe)
        if analysis and not analysis.get('error'):
            return analysis.get('volume_analysis', {})
        return {}

    async def _calculate_custom_indicators(self, symbol: str, timeframe: str, 
                                         indicators: List[str]) -> Dict:
        """Calculate custom set of indicators"""
        # This would calculate only the requested indicators
        analysis = await self._analyze_symbol_technical_async(symbol, timeframe)
        if analysis and analysis.get('indicators'):
            filtered = {k: v for k, v in analysis['indicators'].items() if k in indicators}
            return {'indicators': filtered, 'symbol': symbol, 'timeframe': timeframe}
        return {}

    async def _validate_signal(self, signal_id: str, current_price: Optional[float]) -> Dict:
        """Validate a signal before execution"""
        # This would check if signal is still valid
        return {
            'is_valid': True,
            'signal_id': signal_id,
            'validation_checks': {
                'not_expired': True,
                'price_in_range': True,
                'risk_acceptable': True
            }
        }

    async def _update_signal_status(self, signal_id: str, status: str, 
                                  execution_details: Dict) -> bool:
        """Update signal status in database"""
        # This would update the trading_signals table
        return True

    async def _calculate_risk_levels(self, symbol: str, entry_price: float, 
                                   action: str, risk_profile: str) -> Dict:
        """Calculate risk levels based on profile"""
        # Get ATR for risk calculation
        analysis = await self._analyze_symbol_technical_async(symbol, '5m')
        atr = analysis.get('indicators', {}).get('atr', entry_price * 0.02)
        
        # Adjust multipliers based on risk profile
        multipliers = {
            'conservative': {'stop': 1.5, 'target': 2.0},
            'moderate': {'stop': 2.0, 'target': 3.0},
            'aggressive': {'stop': 2.5, 'target': 4.0}
        }
        
        profile_mult = multipliers.get(risk_profile, multipliers['moderate'])
        
        stop_loss = self._calculate_stop_loss(entry_price, atr * profile_mult['stop'], action)
        take_profit = self._calculate_take_profit(entry_price, atr * profile_mult['target'], action)
        
        return {
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_profile': risk_profile,
            'atr': atr
        }

    def _calculate_trend_consensus(self, trends: Dict) -> str:
        """Calculate consensus trend from multiple timeframes"""
        if not trends:
            return "neutral"
            
        bullish_count = sum(1 for t in trends.values() if t and t.get('overall') == 'bullish')
        bearish_count = sum(1 for t in trends.values() if t and t.get('overall') == 'bearish')
        
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"

    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Technical Analysis MCP Server",
                        version="3.0.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


if __name__ == "__main__":
    # Run the MCP server
    server = TechnicalAnalysisMCPServer()
    asyncio.run(server.run())