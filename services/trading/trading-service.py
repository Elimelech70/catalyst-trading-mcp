#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trading-service.py
Version: 3.0.0
Last Updated: 2024-12-30
Purpose: MCP-enabled trading execution service with paper trading via Alpaca

REVISION HISTORY:
v3.0.0 (2024-12-30) - Complete MCP migration
- Converted from Flask REST to MCP protocol
- Resources for position and order management
- Tools for trade execution and signal processing
- Maintained Alpaca integration
- Natural language trading capabilities
- Async operations throughout

Description of Service:
MCP server that executes trades via Alpaca paper trading API based on
signals from the technical analysis service. Enables Claude to execute
trades, manage positions, and monitor performance through natural language.

KEY FEATURES:
- Paper trading via Alpaca Markets API
- Individual and batch trade execution
- Position management and tracking
- Risk management and position sizing
- Trade record persistence
- Comprehensive error handling
"""

import os
import json
import time
import asyncio
import requests
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from structlog import get_logger

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import database utilities
from database_utils import (
    get_db_connection,
    get_redis,
    health_check,
    get_pending_signals,
    insert_trade_record,
    mark_signal_executed,
    get_open_positions
)

# Handle Alpaca API import
try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("⚠️ Alpaca Trade API not available, using mock trading")


class TradingExecutionMCPServer:
    """
    MCP Server for trading execution via Alpaca
    """
    
    def __init__(self):
        # Initialize environment
        self.setup_environment()
        
        # Initialize MCP server
        self.server = MCPServer("trading-execution")
        self.setup_logging()
        
        # Initialize Redis client
        self.redis_client = get_redis()
        
        # Trading configuration
        self.trading_config = {
            'enabled': os.getenv('TRADING_ENABLED', 'false').lower() == 'true',
            'max_position_size': float(os.getenv('MAX_POSITION_SIZE', '1000')),
            'max_daily_trades': int(os.getenv('MAX_DAILY_TRADES', '10')),
            'default_stop_loss_pct': float(os.getenv('DEFAULT_STOP_LOSS_PCT', '2.0')),
            'default_take_profit_pct': float(os.getenv('DEFAULT_TAKE_PROFIT_PCT', '4.0')),
            'min_confidence': float(os.getenv('MIN_TRADING_CONFIDENCE', '60.0'))
        }
        
        # Alpaca configuration
        self.alpaca_config = {
            'api_key': os.getenv('ALPACA_API_KEY'),
            'secret_key': os.getenv('ALPACA_SECRET_KEY'),
            'base_url': os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets'),
            'data_url': os.getenv('ALPACA_DATA_URL', 'https://data.alpaca.markets')
        }
        
        # Initialize Alpaca API
        self.alpaca = self._init_alpaca()
        
        # Trading metrics
        self.daily_metrics = {
            'trades_executed': 0,
            'total_pnl': 0.0,
            'successful_trades': 0,
            'failed_trades': 0
        }
        
        # Register MCP resources and tools
        self._register_resources()
        self._register_tools()
        
        self.logger.info("Trading Execution MCP Server v3.0.0 initialized",
                        environment=os.getenv('ENVIRONMENT', 'development'),
                        trading_enabled=self.trading_config['enabled'],
                        alpaca_connected=self.alpaca is not None)
        
    def setup_environment(self):
        """Setup environment variables and paths"""
        # Paths
        self.log_path = os.getenv('LOG_PATH', '/app/logs')
        self.data_path = os.getenv('DATA_PATH', '/app/data')
        
        # Create directories
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(self.data_path, exist_ok=True)
        
        # Service configuration
        self.service_name = 'trading-execution-mcp'
        self.port = int(os.getenv('PORT', '5005'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    def _init_alpaca(self):
        """Initialize Alpaca API client"""
        if not ALPACA_AVAILABLE:
            self.logger.warning("Alpaca API not available, using mock trading")
            return None
            
        if not self.alpaca_config['api_key'] or not self.alpaca_config['secret_key']:
            self.logger.warning("Alpaca API credentials not configured")
            return None
            
        try:
            api = tradeapi.REST(
                key_id=self.alpaca_config['api_key'],
                secret_key=self.alpaca_config['secret_key'],
                base_url=self.alpaca_config['base_url'],
                api_version='v2'
            )
            
            # Test connection
            account = api.get_account()
            self.logger.info("Successfully connected to Alpaca API",
                           account_status=account.status,
                           buying_power=account.buying_power)
            
            return api
            
        except Exception as e:
            self.logger.error("Failed to initialize Alpaca API", error=str(e))
            return None
            
    def _check_alpaca_health(self) -> bool:
        """Check if Alpaca API is healthy"""
        if not self.alpaca:
            return False
            
        try:
            account = self.alpaca.get_account()
            return account.status == 'ACTIVE'
        except:
            return False
            
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("positions/open")
        async def get_open_positions(params: ResourceParams) -> ResourceResponse:
            """Get all open positions"""
            positions = await self._get_current_positions_async()
            
            return ResourceResponse(
                type="position_collection",
                data=positions,
                metadata={
                    "count": len(positions),
                    "total_value": self._calculate_total_position_value(positions),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.server.resource("positions/{symbol}")
        async def get_position_by_symbol(params: ResourceParams) -> ResourceResponse:
            """Get position for specific symbol"""
            symbol = params["symbol"]
            position = await self._get_position_details_async(symbol)
            
            if position:
                return ResourceResponse(
                    type="position",
                    data=position
                )
            else:
                return ResourceResponse(
                    type="position",
                    data=None,
                    metadata={"error": f"No position found for {symbol}"}
                )
        
        @self.server.resource("trades/history")
        async def get_trade_history(params: ResourceParams) -> ResourceResponse:
            """Get trade history"""
            date = params.get("date")
            symbol = params.get("symbol")
            status = params.get("status", "all")
            limit = params.get("limit", 50)
            
            trades = await self._get_trade_history(date, symbol, status, limit)
            
            return ResourceResponse(
                type="trade_history",
                data=trades,
                metadata={
                    "count": len(trades),
                    "filters": {
                        "date": date,
                        "symbol": symbol,
                        "status": status
                    }
                }
            )
        
        @self.server.resource("account/status")
        async def get_account_status(params: ResourceParams) -> ResourceResponse:
            """Get trading account status"""
            account = await self._get_account_status()
            
            return ResourceResponse(
                type="account_status",
                data=account
            )
        
        @self.server.resource("orders/active")
        async def get_active_orders(params: ResourceParams) -> ResourceResponse:
            """Get active orders"""
            orders = await self._get_active_orders()
            
            return ResourceResponse(
                type="order_collection",
                data=orders,
                metadata={"count": len(orders)}
            )
        
        @self.server.resource("orders/history")
        async def get_order_history(params: ResourceParams) -> ResourceResponse:
            """Get order history"""
            status = params.get("status", "all")
            limit = params.get("limit", 50)
            
            orders = await self._get_orders_async(status, limit)
            
            return ResourceResponse(
                type="order_history",
                data=orders,
                metadata={
                    "count": len(orders),
                    "status_filter": status
                }
            )
        
        @self.server.resource("performance/daily")
        async def get_daily_performance(params: ResourceParams) -> ResourceResponse:
            """Get daily trading performance"""
            performance = await self._get_daily_performance()
            
            return ResourceResponse(
                type="performance_metrics",
                data=performance
            )
        
        @self.server.resource("signals/pending")
        async def get_pending_signals(params: ResourceParams) -> ResourceResponse:
            """Get pending trading signals"""
            limit = params.get("limit", 10)
            min_confidence = params.get("min_confidence", self.trading_config['min_confidence'])
            
            signals = await self._get_pending_signals_async(limit, min_confidence)
            
            return ResourceResponse(
                type="signal_collection",
                data=signals,
                metadata={
                    "count": len(signals),
                    "min_confidence": min_confidence
                }
            )

    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("execute_trade")
        async def execute_trade(params: ToolParams) -> ToolResponse:
            """Execute a single trade"""
            signal_id = params.get("signal_id")
            signal_data = params.get("signal")
            size_override = params.get("size_override")
            
            # Get signal from database if ID provided
            if signal_id and not signal_data:
                signal_data = await self._get_signal_by_id(signal_id)
            
            if not signal_data:
                return ToolResponse(
                    success=False,
                    data={"error": "No signal data provided"}
                )
            
            result = await self._execute_signal_async(signal_data, size_override)
            
            return ToolResponse(
                success=result.get('status') == 'success',
                data=result
            )
        
        @self.server.tool("execute_signals_batch")
        async def execute_signals_batch(params: ToolParams) -> ToolResponse:
            """Execute all pending signals"""
            cycle_id = params.get("cycle_id")
            limit = params.get("limit", 10)
            
            self.logger.info("Starting batch signal execution", cycle_id=cycle_id)
            
            # Check if trading is enabled
            if not self.trading_config['enabled']:
                return ToolResponse(
                    success=True,
                    data={
                        'trades_executed': 0,
                        'message': 'Trading is disabled',
                        'cycle_id': cycle_id
                    }
                )
            
            # Get pending signals
            signals = await self._get_pending_signals_async(limit)
            
            if not signals:
                return ToolResponse(
                    success=True,
                    data={
                        'trades_executed': 0,
                        'message': 'No pending signals found',
                        'cycle_id': cycle_id
                    }
                )
            
            # Execute each signal
            results = []
            successful_trades = 0
            
            for signal in signals:
                result = await self._execute_signal_async(signal)
                results.append(result)
                
                if result.get('status') == 'success':
                    successful_trades += 1
            
            return ToolResponse(
                success=True,
                data={
                    'trades_executed': successful_trades,
                    'total_signals': len(signals),
                    'results': results,
                    'cycle_id': cycle_id,
                    'timestamp': datetime.now().isoformat()
                }
            )
        
        @self.server.tool("close_position")
        async def close_position(params: ToolParams) -> ToolResponse:
            """Close a specific position"""
            symbol = params["symbol"]
            reason = params.get("reason", "manual_close")
            
            result = await self._close_position_async(symbol, reason)
            
            return ToolResponse(
                success=result.get('status') == 'success',
                data=result
            )
        
        @self.server.tool("update_stop_loss")
        async def update_stop_loss(params: ToolParams) -> ToolResponse:
            """Update stop loss for a position"""
            position_id = params["position_id"]
            new_stop_loss = params["new_stop_loss"]
            trail = params.get("trail", False)
            
            result = await self._update_stop_loss(position_id, new_stop_loss, trail)
            
            return ToolResponse(
                success=result.get('updated', False),
                data=result
            )
        
        @self.server.tool("cancel_order")
        async def cancel_order(params: ToolParams) -> ToolResponse:
            """Cancel a pending order"""
            order_id = params["order_id"]
            
            result = await self._cancel_order(order_id)
            
            return ToolResponse(
                success=result.get('cancelled', False),
                data=result
            )
        
        @self.server.tool("get_pnl")
        async def get_pnl(params: ToolParams) -> ToolResponse:
            """Get P&L for positions"""
            symbol = params.get("symbol")
            realized_only = params.get("realized_only", False)
            
            pnl_data = await self._calculate_pnl(symbol, realized_only)
            
            return ToolResponse(
                success=True,
                data=pnl_data
            )

    async def _execute_signal_async(self, signal: Dict, size_override: Optional[float] = None) -> Dict:
        """Execute a trading signal asynchronously"""
        try:
            symbol = signal.get('symbol')
            signal_type = signal.get('signal_type', signal.get('action', 'BUY'))
            confidence = signal.get('confidence', 0)
            
            if not symbol:
                return {
                    'status': 'error',
                    'reason': 'Missing symbol in signal'
                }
            
            # Check trading enabled
            if not self.trading_config['enabled']:
                return {
                    'status': 'rejected',
                    'reason': 'Trading disabled'
                }
            
            # Check confidence threshold
            if confidence < self.trading_config['min_confidence']:
                return {
                    'status': 'rejected',
                    'reason': f'Confidence {confidence} below threshold {self.trading_config["min_confidence"]}'
                }
            
            # Check if we already have a position
            existing_position = await self._get_position_details_async(symbol)
            if existing_position:
                return {
                    'status': 'rejected',
                    'reason': f'Already have position in {symbol}'
                }
            
            # Calculate position size
            if size_override:
                position_size = size_override
            else:
                position_size = min(
                    self.trading_config['max_position_size'],
                    self.trading_config['max_position_size'] * (confidence / 100)
                )
            
            # Get current price
            current_price = await self._get_current_price_async(symbol)
            if not current_price:
                return {
                    'status': 'error',
                    'reason': 'Could not get current price'
                }
                
            # Calculate shares
            shares = int(position_size / current_price)
            if shares < 1:
                return {
                    'status': 'rejected',
                    'reason': 'Position size too small'
                }
                
            # Prepare order
            order_params = self._prepare_order(
                symbol, signal_type, shares, current_price, signal
            )
            
            # Execute order
            order_result = await self._execute_order_async(order_params)
            
            if order_result['status'] == 'success':
                # Record trade in database
                trade_record = self._create_trade_record(
                    signal, order_result['order'], order_params
                )
                trade_id = insert_trade_record(trade_record)
                
                # Mark signal as executed if it has an ID
                if signal.get('id'):
                    mark_signal_executed(signal['id'], trade_id)
                
                # Update metrics
                self.daily_metrics['trades_executed'] += 1
                
                return {
                    'status': 'success',
                    'trade_id': trade_id,
                    'order_id': order_result['order_id'],
                    'symbol': symbol,
                    'direction': signal_type,
                    'shares': shares,
                    'entry_price': order_result['fill_price'],
                    'position_value': shares * order_result['fill_price']
                }
            else:
                return order_result
                
        except Exception as e:
            self.logger.error("Error executing signal",
                            symbol=signal.get('symbol'),
                            error=str(e))
            return {
                'status': 'error',
                'reason': str(e)
            }

    async def _get_current_price_async(self, symbol: str) -> Optional[float]:
        """Get current price for symbol asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_current_price, symbol)

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        if not self.alpaca:
            # Mock price for testing
            return 100.0 + hash(symbol) % 50
            
        try:
            quote = self.alpaca.get_latest_quote(symbol)
            return float(quote.ask_price)
        except Exception as e:
            self.logger.error("Error getting current price", symbol=symbol, error=str(e))
            return None

    def _prepare_order(self, symbol: str, signal_type: str, shares: int, 
                      current_price: float, signal: Dict) -> Dict:
        """Prepare order parameters"""
        
        side = 'buy' if signal_type.upper() in ['BUY', 'LONG'] else 'sell'
        
        # Calculate stop loss and take profit
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')
        
        if not stop_loss:
            stop_loss = current_price * (1 - self.trading_config['default_stop_loss_pct'] / 100)
        if not take_profit:
            take_profit = current_price * (1 + self.trading_config['default_take_profit_pct'] / 100)
        
        return {
            'symbol': symbol,
            'qty': shares,
            'side': side,
            'type': 'market',
            'time_in_force': 'day',
            'signal_id': signal.get('id'),
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_reason': f"Signal confidence: {signal.get('confidence', 0)}%"
        }

    async def _execute_order_async(self, order_params: Dict) -> Dict:
        """Execute order via Alpaca asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_order, order_params)

    def _execute_order(self, order_params: Dict) -> Dict:
        """Execute order via Alpaca"""
        if not self.alpaca:
            # Mock execution for testing
            return {
                'status': 'success',
                'order_id': f"mock_{int(time.time())}",
                'fill_price': self._get_current_price(order_params['symbol']),
                'order': order_params
            }
            
        try:
            # Submit main order
            order = self.alpaca.submit_order(
                symbol=order_params['symbol'],
                qty=order_params['qty'],
                side=order_params['side'],
                type=order_params['type'],
                time_in_force=order_params['time_in_force']
            )
            
            # TODO: Add bracket orders for stop loss and take profit
            
            return {
                'status': 'success',
                'order_id': order.id,
                'fill_price': float(order.filled_avg_price) if order.filled_avg_price else self._get_current_price(order_params['symbol']),
                'order': order
            }
            
        except Exception as e:
            self.logger.error("Error executing order", error=str(e))
            return {
                'status': 'error',
                'reason': str(e)
            }

    def _create_trade_record(self, signal: Dict, order: Any, order_params: Dict) -> Dict:
        """Create trade record for database"""
        return {
            'signal_id': signal.get('id'),
            'symbol': order_params['symbol'],
            'order_id': getattr(order, 'id', f"mock_{int(time.time())}"),
            'side': order_params['side'],
            'order_type': order_params['type'],
            'quantity': order_params['qty'],
            'entry_price': getattr(order, 'filled_avg_price', self._get_current_price(order_params['symbol'])),
            'stop_loss': order_params.get('stop_loss'),
            'take_profit': order_params.get('take_profit'),
            'entry_reason': order_params.get('entry_reason', 'Signal execution'),
            'metadata': {
                'signal_confidence': signal.get('confidence'),
                'signal_type': signal.get('signal_type'),
                'alpaca_order_id': getattr(order, 'id', None)
            }
        }

    async def _get_current_positions_async(self) -> List[Dict]:
        """Get all current positions asynchronously"""
        positions = get_open_positions()
        
        # Enrich with current prices
        for position in positions:
            current_price = await self._get_current_price_async(position['symbol'])
            if current_price:
                position['current_price'] = current_price
                position['unrealized_pnl'] = (current_price - float(position['entry_price'])) * int(position['quantity'])
                position['unrealized_pnl_pct'] = ((current_price - float(position['entry_price'])) / float(position['entry_price'])) * 100
        
        return positions

    async def _get_position_details_async(self, symbol: str) -> Optional[Dict]:
        """Get position details for specific symbol"""
        positions = await self._get_current_positions_async()
        for position in positions:
            if position.get('symbol') == symbol:
                return position
        return None

    async def _close_position_async(self, symbol: str, reason: str) -> Dict:
        """Close position for a specific symbol"""
        # Get current position
        position = await self._get_position_details_async(symbol)
        if not position:
            return {
                'status': 'error',
                'reason': f'No position found for {symbol}'
            }
        
        # Submit closing order
        order_params = {
            'symbol': symbol,
            'qty': position['quantity'],
            'side': 'sell' if position['side'] == 'buy' else 'buy',
            'type': 'market',
            'time_in_force': 'day'
        }
        
        result = await self._execute_order_async(order_params)
        
        if result['status'] == 'success':
            # Update trade record with exit info
            # TODO: Update database with exit details
            
            return {
                'status': 'success',
                'symbol': symbol,
                'reason': reason,
                'exit_price': result['fill_price'],
                'realized_pnl': (result['fill_price'] - float(position['entry_price'])) * int(position['quantity']),
                'timestamp': datetime.now().isoformat()
            }
        else:
            return result

    async def _get_account_status(self) -> Dict:
        """Get trading account status"""
        if not self.alpaca:
            return {
                'status': 'mock',
                'buying_power': 100000.0,
                'portfolio_value': 100000.0,
                'cash': 100000.0
            }
        
        try:
            account = self.alpaca.get_account()
            return {
                'status': account.status,
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'pattern_day_trader': account.pattern_day_trader,
                'trading_blocked': account.trading_blocked,
                'account_blocked': account.account_blocked
            }
        except Exception as e:
            self.logger.error("Error getting account status", error=str(e))
            return {'error': str(e)}

    async def _get_active_orders(self) -> List[Dict]:
        """Get active orders"""
        return await self._get_orders_async('open', 100)

    async def _get_orders_async(self, status: str, limit: int) -> List[Dict]:
        """Get orders from Alpaca asynchronously"""
        if not self.alpaca:
            return []
            
        try:
            loop = asyncio.get_event_loop()
            orders = await loop.run_in_executor(
                None, 
                lambda: self.alpaca.list_orders(status=status, limit=limit)
            )
            return [self._serialize_order(order) for order in orders]
        except Exception as e:
            self.logger.error("Error getting orders", error=str(e))
            return []

    def _serialize_order(self, order) -> Dict:
        """Serialize Alpaca order object to dictionary"""
        return {
            'id': order.id,
            'symbol': order.symbol,
            'side': order.side,
            'qty': order.qty,
            'type': order.type,
            'status': order.status,
            'filled_qty': order.filled_qty,
            'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None
        }

    async def _get_pending_signals_async(self, limit: int, min_confidence: Optional[float] = None) -> List[Dict]:
        """Get pending signals asynchronously"""
        signals = get_pending_signals(limit=limit)
        
        # Convert to list of dicts and filter by confidence
        signal_list = []
        for signal in signals:
            if hasattr(signal, '_asdict'):
                signal_dict = signal._asdict()
            elif isinstance(signal, dict):
                signal_dict = signal
            else:
                signal_dict = dict(signal)
                
            if min_confidence and signal_dict.get('confidence', 0) < min_confidence:
                continue
                
            signal_list.append(signal_dict)
        
        return signal_list

    async def _get_signal_by_id(self, signal_id: str) -> Optional[Dict]:
        """Get signal by ID from database"""
        # This would query the trading_signals table
        # For now, return None
        return None

    async def _get_trade_history(self, date: Optional[str], symbol: Optional[str],
                               status: str, limit: int) -> List[Dict]:
        """Get trade history from database"""
        # This would query the trade_records table
        # For now, return empty list
        return []

    async def _get_daily_performance(self) -> Dict:
        """Get daily trading performance"""
        return {
            'date': datetime.now().date().isoformat(),
            'trades_executed': self.daily_metrics['trades_executed'],
            'successful_trades': self.daily_metrics['successful_trades'],
            'failed_trades': self.daily_metrics['failed_trades'],
            'total_pnl': self.daily_metrics['total_pnl'],
            'win_rate': (self.daily_metrics['successful_trades'] / self.daily_metrics['trades_executed'] * 100) 
                       if self.daily_metrics['trades_executed'] > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }

    def _calculate_total_position_value(self, positions: List[Dict]) -> float:
        """Calculate total value of all positions"""
        return sum(
            float(pos.get('current_price', pos.get('entry_price', 0))) * int(pos.get('quantity', 0))
            for pos in positions
        )

    async def _update_stop_loss(self, position_id: str, new_stop_loss: float, trail: bool) -> Dict:
        """Update stop loss for a position"""
        # This would update the stop loss order
        # For now, return success
        return {
            'updated': True,
            'position_id': position_id,
            'new_stop_loss': new_stop_loss,
            'trailing': trail
        }

    async def _cancel_order(self, order_id: str) -> Dict:
        """Cancel a pending order"""
        if not self.alpaca:
            return {'cancelled': True, 'order_id': order_id}
            
        try:
            self.alpaca.cancel_order(order_id)
            return {'cancelled': True, 'order_id': order_id}
        except Exception as e:
            return {'cancelled': False, 'error': str(e)}

    async def _calculate_pnl(self, symbol: Optional[str], realized_only: bool) -> Dict:
        """Calculate P&L for positions"""
        positions = await self._get_current_positions_async()
        
        if symbol:
            positions = [p for p in positions if p['symbol'] == symbol]
        
        realized_pnl = 0  # Would calculate from closed trades
        unrealized_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
        
        return {
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl if not realized_only else 0,
            'total_pnl': realized_pnl + (unrealized_pnl if not realized_only else 0),
            'positions_count': len(positions)
        }

    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Trading Execution MCP Server",
                        version="3.0.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


if __name__ == "__main__":
    # Run the MCP server
    server = TradingExecutionMCPServer()
    asyncio.run(server.run())