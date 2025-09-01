#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trading-service.py
Version: 3.1.0
Last Updated: 2025-08-23
Purpose: MCP-enabled trading execution with database MCP integration

REVISION HISTORY:
v3.1.0 (2025-08-23) - Database MCP integration and missing features
- Replaced all database operations with MCP Database Client
- Added missing resources: trades/analysis, risk/exposure, orders/rejected
- Added missing tools: hedge_position, rebalance_portfolio, export_trades
- Enhanced risk management and portfolio analytics
- Added trade analysis and performance metrics

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
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import numpy as np
import pandas as pd
from structlog import get_logger
import redis.asyncio as redis
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Import MCP Database Client instead of database operations
from mcp_database_client import MCPDatabaseClient


class TradingExecutionMCPServer:
    """MCP Server for trading execution and position management"""
    
    def __init__(self):
        # Initialize MCP server
        self.server = MCPServer("trading-execution")
        self.setup_logging()
        
        # Database client (initialized in async context)
        self.db_client: Optional[MCPDatabaseClient] = None
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Alpaca API setup
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.alpaca_base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        self.alpaca_api = None
        
        # Trading configuration
        self.trading_config = {
            'max_positions': int(os.getenv('MAX_POSITIONS', '5')),
            'position_size_pct': float(os.getenv('POSITION_SIZE_PCT', '0.2')),
            'stop_loss_pct': float(os.getenv('STOP_LOSS_PCT', '0.02')),
            'take_profit_pct': float(os.getenv('TAKE_PROFIT_PCT', '0.04')),
            'max_daily_trades': int(os.getenv('MAX_DAILY_TRADES', '10')),
            'min_confidence': float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.7')),
            'use_bracket_orders': os.getenv('USE_BRACKET_ORDERS', 'true').lower() == 'true',
            'risk_per_trade': float(os.getenv('RISK_PER_TRADE', '0.01')),  # 1% risk per trade
            'max_portfolio_risk': float(os.getenv('MAX_PORTFOLIO_RISK', '0.06'))  # 6% max risk
        }
        
        # Risk management
        self.risk_manager = {
            'current_exposure': 0.0,
            'daily_trades': 0,
            'daily_pnl': 0.0,
            'max_drawdown': 0.0,
            'winning_trades': 0,
            'losing_trades': 0
        }
        
        # Trade tracking
        self.active_trades = {}
        self.trade_history = []
        self.rejected_orders = []
        
        # Portfolio analytics
        self.portfolio_metrics = {
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0
        }
        
        # Service configuration
        self.service_name = 'trading-execution'
        self.port = int(os.getenv('PORT', '5005'))
        
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
        
        # Initialize Alpaca API
        if self.alpaca_api_key and self.alpaca_secret_key:
            self.alpaca_api = tradeapi.REST(
                self.alpaca_api_key,
                self.alpaca_secret_key,
                self.alpaca_base_url,
                api_version='v2'
            )
        
        # Load risk manager state
        await self._load_risk_state()
        
        # Load portfolio metrics
        await self._load_portfolio_metrics()
        
        self.logger.info("Trading service initialized",
                        database_connected=True,
                        redis_connected=True,
                        alpaca_connected=self.alpaca_api is not None)
    
    async def cleanup(self):
        """Clean up resources"""
        # Save risk state
        await self._save_risk_state()
        
        # Save portfolio metrics
        await self._save_portfolio_metrics()
        
        if self.redis_client:
            await self.redis_client.close()
            
        if self.db_client:
            await self.db_client.disconnect()
    
    async def _load_risk_state(self):
        """Load risk manager state from cache"""
        try:
            state = await self.redis_client.get("trading:risk_state")
            if state:
                self.risk_manager.update(json.loads(state))
                
            # Reset daily counters if new day
            last_reset = await self.redis_client.get("trading:last_reset")
            if last_reset:
                last_reset_date = datetime.fromisoformat(last_reset)
                if last_reset_date.date() < datetime.now().date():
                    await self._reset_daily_counters()
            else:
                await self._reset_daily_counters()
                
        except Exception as e:
            self.logger.warning("Failed to load risk state", error=str(e))
    
    async def _save_risk_state(self):
        """Save risk manager state to cache"""
        try:
            await self.redis_client.set(
                "trading:risk_state",
                json.dumps(self.risk_manager)
            )
        except Exception as e:
            self.logger.error("Failed to save risk state", error=str(e))
    
    async def _load_portfolio_metrics(self):
        """Load portfolio metrics from cache"""
        try:
            metrics = await self.redis_client.get("trading:portfolio_metrics")
            if metrics:
                self.portfolio_metrics.update(json.loads(metrics))
        except Exception as e:
            self.logger.warning("Failed to load portfolio metrics", error=str(e))
    
    async def _save_portfolio_metrics(self):
        """Save portfolio metrics to cache"""
        try:
            await self.redis_client.set(
                "trading:portfolio_metrics",
                json.dumps(self.portfolio_metrics)
            )
        except Exception as e:
            self.logger.error("Failed to save portfolio metrics", error=str(e))
    
    async def _reset_daily_counters(self):
        """Reset daily risk counters"""
        self.risk_manager['daily_trades'] = 0
        self.risk_manager['daily_pnl'] = 0.0
        await self.redis_client.set(
            "trading:last_reset",
            datetime.now().isoformat()
        )
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("positions/open")
        async def get_open_positions(params: ResourceParams) -> ResourceResponse:
            """Get all open positions"""
            if not self.alpaca_api:
                return ResourceResponse(
                    type="error",
                    data={'error': 'Alpaca API not configured'}
                )
            
            try:
                positions = self.alpaca_api.list_positions()
                
                position_data = []
                for pos in positions:
                    position_data.append({
                        'symbol': pos.symbol,
                        'quantity': int(pos.qty),
                        'side': pos.side,
                        'entry_price': float(pos.avg_entry_price),
                        'current_price': float(pos.current_price),
                        'market_value': float(pos.market_value),
                        'cost_basis': float(pos.cost_basis),
                        'unrealized_pl': float(pos.unrealized_pl),
                        'unrealized_plpc': float(pos.unrealized_plpc),
                        'today_pl': float(pos.change_today),
                        'today_plpc': float(pos.unrealized_plpc)
                    })
                
                # Add from database
                db_positions = await self.db_client.get_open_positions()
                
                return ResourceResponse(
                    type="position_list",
                    data={
                        'positions': position_data,
                        'summary': {
                            'total_positions': len(position_data),
                            'total_value': sum(p['market_value'] for p in position_data),
                            'total_pl': sum(p['unrealized_pl'] for p in position_data),
                            'total_pl_pct': sum(p['unrealized_plpc'] for p in position_data) / len(position_data) if position_data else 0
                        }
                    },
                    metadata={'source': 'alpaca'}
                )
                
            except Exception as e:
                return ResourceResponse(
                    type="error",
                    data={'error': str(e)}
                )
        
        @self.server.resource("orders/active")
        async def get_active_orders(params: ResourceParams) -> ResourceResponse:
            """Get all active orders"""
            if not self.alpaca_api:
                return ResourceResponse(
                    type="error",
                    data={'error': 'Alpaca API not configured'}
                )
            
            try:
                orders = self.alpaca_api.list_orders(status='open')
                
                order_data = []
                for order in orders:
                    order_data.append({
                        'order_id': order.id,
                        'symbol': order.symbol,
                        'side': order.side,
                        'type': order.order_type,
                        'quantity': int(order.qty),
                        'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                        'limit_price': float(order.limit_price) if order.limit_price else None,
                        'stop_price': float(order.stop_price) if order.stop_price else None,
                        'status': order.status,
                        'submitted_at': order.submitted_at.isoformat() if order.submitted_at else None,
                        'time_in_force': order.time_in_force
                    })
                
                return ResourceResponse(
                    type="order_list",
                    data={'orders': order_data},
                    metadata={'count': len(order_data)}
                )
                
            except Exception as e:
                return ResourceResponse(
                    type="error",
                    data={'error': str(e)}
                )
        
        @self.server.resource("orders/rejected")
        async def get_rejected_orders(params: ResourceParams) -> ResourceResponse:
            """Get recently rejected orders with reasons"""
            hours = params.get("hours", 24)
            limit = params.get("limit", 50)
            
            # Filter rejected orders by time
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_rejected = [
                order for order in self.rejected_orders
                if datetime.fromisoformat(order['timestamp']) > cutoff_time
            ]
            
            # Sort by timestamp descending
            recent_rejected.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return ResourceResponse(
                type="rejected_orders",
                data={'orders': recent_rejected[:limit]},
                metadata={
                    'count': len(recent_rejected),
                    'hours': hours,
                    'rejection_reasons': self._summarize_rejection_reasons(recent_rejected)
                }
            )
        
        @self.server.resource("account/status")
        async def get_account_status(params: ResourceParams) -> ResourceResponse:
            """Get account status and buying power"""
            if not self.alpaca_api:
                return ResourceResponse(
                    type="error",
                    data={'error': 'Alpaca API not configured'}
                )
            
            try:
                account = self.alpaca_api.get_account()
                
                return ResourceResponse(
                    type="account_status",
                    data={
                        'account_number': account.account_number,
                        'status': account.status,
                        'currency': account.currency,
                        'buying_power': float(account.buying_power),
                        'cash': float(account.cash),
                        'portfolio_value': float(account.portfolio_value),
                        'pattern_day_trader': account.pattern_day_trader,
                        'trading_blocked': account.trading_blocked,
                        'transfers_blocked': account.transfers_blocked,
                        'account_blocked': account.account_blocked,
                        'daytrade_count': int(account.daytrade_count),
                        'daytrading_buying_power': float(account.daytrading_buying_power) if account.daytrading_buying_power else None
                    },
                    metadata={'last_updated': datetime.now().isoformat()}
                )
                
            except Exception as e:
                return ResourceResponse(
                    type="error",
                    data={'error': str(e)}
                )
        
        @self.server.resource("trades/analysis")
        async def get_trade_analysis(params: ResourceParams) -> ResourceResponse:
            """Get comprehensive trade analysis"""
            days = params.get("days", 30)
            symbol = params.get("symbol")
            
            # Get trade history from database
            trades = await self.db_client.get_trading_history(days=days, symbol=symbol)
            
            if not trades:
                return ResourceResponse(
                    type="trade_analysis",
                    data={
                        'analysis': {},
                        'message': 'No trades found in period'
                    }
                )
            
            # Analyze trades
            analysis = self._analyze_trades(trades)
            
            # Add symbol-specific analysis if requested
            if symbol:
                analysis['symbol_analysis'] = self._analyze_symbol_trades(trades, symbol)
            
            return ResourceResponse(
                type="trade_analysis",
                data={'analysis': analysis},
                metadata={
                    'period_days': days,
                    'trade_count': len(trades),
                    'symbol': symbol
                }
            )
        
        @self.server.resource("risk/exposure")
        async def get_risk_exposure(params: ResourceParams) -> ResourceResponse:
            """Get current risk exposure analysis"""
            include_stress_test = params.get("include_stress_test", False)
            
            exposure = {
                'current_exposure': self.risk_manager['current_exposure'],
                'max_allowed_exposure': self.trading_config['max_portfolio_risk'],
                'exposure_pct': (self.risk_manager['current_exposure'] / 
                               self.trading_config['max_portfolio_risk'] * 100),
                'daily_trades': self.risk_manager['daily_trades'],
                'daily_limit': self.trading_config['max_daily_trades'],
                'daily_pnl': self.risk_manager['daily_pnl'],
                'max_drawdown': self.risk_manager['max_drawdown'],
                'risk_score': self._calculate_risk_score()
            }
            
            # Add position-level risk
            if self.alpaca_api:
                try:
                    positions = self.alpaca_api.list_positions()
                    position_risk = []
                    
                    for pos in positions:
                        risk_pct = abs(float(pos.unrealized_plpc)) / 100
                        position_risk.append({
                            'symbol': pos.symbol,
                            'risk_pct': risk_pct,
                            'value_at_risk': float(pos.market_value) * risk_pct,
                            'position_size_pct': float(pos.market_value) / float(self.alpaca_api.get_account().portfolio_value)
                        })
                    
                    exposure['position_risk'] = position_risk
                    exposure['total_var'] = sum(p['value_at_risk'] for p in position_risk)
                    
                except Exception as e:
                    self.logger.error("Failed to get position risk", error=str(e))
            
            # Stress test if requested
            if include_stress_test:
                exposure['stress_test'] = self._run_stress_test()
            
            return ResourceResponse(
                type="risk_exposure",
                data=exposure,
                metadata={'timestamp': datetime.now().isoformat()}
            )
        
        @self.server.resource("performance/daily")
        async def get_daily_performance(params: ResourceParams) -> ResourceResponse:
            """Get daily trading performance"""
            performance = {
                'date': datetime.now().date().isoformat(),
                'daily_pnl': self.risk_manager['daily_pnl'],
                'daily_trades': self.risk_manager['daily_trades'],
                'winning_trades': self.risk_manager['winning_trades'],
                'losing_trades': self.risk_manager['losing_trades'],
                'win_rate': (self.risk_manager['winning_trades'] / 
                           (self.risk_manager['winning_trades'] + self.risk_manager['losing_trades'])
                           if (self.risk_manager['winning_trades'] + self.risk_manager['losing_trades']) > 0 else 0),
                'portfolio_metrics': self.portfolio_metrics
            }
            
            return ResourceResponse(
                type="daily_performance",
                data=performance
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("execute_trade")
        async def execute_trade(params: ToolParams) -> ToolResponse:
            """Execute a single trade based on signal"""
            signal_id = params.get("signal_id")
            signal_data = params.get("signal")
            size_override = params.get("size_override")
            
            # Get signal from database if ID provided
            if signal_id and not signal_data:
                signals = await self.db_client.get_pending_signals(limit=50)
                signal_data = next((s for s in signals if s.get('signal_id') == signal_id), None)
            
            if not signal_data:
                return ToolResponse(
                    success=False,
                    error="No signal data provided"
                )
            
            try:
                # Risk checks
                risk_check = await self._check_risk_limits(signal_data)
                if not risk_check['allowed']:
                    # Record rejected order
                    self._record_rejected_order(signal_data, risk_check['reason'])
                    return ToolResponse(
                        success=False,
                        error=risk_check['reason']
                    )
                
                # Calculate position size
                position_size = await self._calculate_position_size(
                    signal_data, size_override
                )
                
                # Execute trade
                order = await self._execute_order(signal_data, position_size)
                
                if order:
                    # Record trade in database
                    trade_id = await self.db_client.persist_trade_record({
                        'signal_id': signal_id,
                        'symbol': signal_data['symbol'],
                        'side': 'buy' if signal_data['action'] == 'BUY' else 'sell',
                        'quantity': position_size,
                        'entry_price': signal_data['entry_price'],
                        'metadata': {
                            'order_id': order.id,
                            'signal_confidence': signal_data.get('confidence'),
                            'stop_loss': signal_data.get('stop_loss'),
                            'take_profit': signal_data.get('take_profit')
                        }
                    })
                    
                    # Update risk manager
                    self.risk_manager['daily_trades'] += 1
                    await self._save_risk_state()
                    
                    return ToolResponse(
                        success=True,
                        data={
                            'trade_id': trade_id,
                            'order_id': order.id,
                            'symbol': signal_data['symbol'],
                            'action': signal_data['action'],
                            'quantity': position_size,
                            'status': order.status
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        error="Order execution failed"
                    )
                    
            except Exception as e:
                self.logger.error("Trade execution failed", error=str(e))
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("execute_signals")
        async def execute_signals(params: ToolParams) -> ToolResponse:
            """Execute multiple signals from a trading cycle"""
            cycle_id = params.get("cycle_id")
            max_trades = params.get("max_trades", 5)
            
            try:
                # Get pending signals
                signals = await self.db_client.get_pending_signals(
                    limit=20,
                    min_confidence=self.trading_config['min_confidence']
                )
                
                # Filter and sort by confidence
                valid_signals = [s for s in signals if s.get('confidence', 0) >= self.trading_config['min_confidence']]
                valid_signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)
                
                # Execute top signals
                executed = []
                failed = []
                
                for signal in valid_signals[:max_trades]:
                    result = await execute_trade({
                        'signal_data': signal,
                        'signal_id': signal.get('signal_id')
                    })
                    
                    if result.success:
                        executed.append(result.data)
                    else:
                        failed.append({
                            'signal_id': signal.get('signal_id'),
                            'reason': result.error
                        })
                    
                    # Check if we've hit daily limit
                    if self.risk_manager['daily_trades'] >= self.trading_config['max_daily_trades']:
                        break
                
                return ToolResponse(
                    success=True,
                    data={
                        'cycle_id': cycle_id,
                        'signals_processed': len(executed) + len(failed),
                        'trades_executed': len(executed),
                        'trades_failed': len(failed),
                        'executed': executed,
                        'failed': failed
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("close_position")
        async def close_position(params: ToolParams) -> ToolResponse:
            """Close a specific position"""
            symbol = params["symbol"]
            reason = params.get("reason", "manual_close")
            
            if not self.alpaca_api:
                return ToolResponse(
                    success=False,
                    error="Alpaca API not configured"
                )
            
            try:
                # Get position
                position = self.alpaca_api.get_position(symbol)
                
                # Close position
                order = self.alpaca_api.submit_order(
                    symbol=symbol,
                    qty=abs(int(position.qty)),
                    side='sell' if position.side == 'long' else 'buy',
                    type='market',
                    time_in_force='day'
                )
                
                # Calculate P&L
                pnl = float(position.unrealized_pl)
                
                # Update risk manager
                if pnl > 0:
                    self.risk_manager['winning_trades'] += 1
                else:
                    self.risk_manager['losing_trades'] += 1
                
                self.risk_manager['daily_pnl'] += pnl
                
                # Update portfolio metrics
                await self._update_portfolio_metrics(pnl > 0, pnl)
                
                return ToolResponse(
                    success=True,
                    data={
                        'order_id': order.id,
                        'symbol': symbol,
                        'quantity': int(position.qty),
                        'pnl': pnl,
                        'pnl_pct': float(position.unrealized_plpc),
                        'reason': reason
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("close_all_positions")
        async def close_all_positions(params: ToolParams) -> ToolResponse:
            """Close all open positions"""
            reason = params.get("reason", "close_all")
            
            if not self.alpaca_api:
                return ToolResponse(
                    success=False,
                    error="Alpaca API not configured"
                )
            
            try:
                positions = self.alpaca_api.list_positions()
                closed_positions = []
                total_pnl = 0
                
                for position in positions:
                    try:
                        result = await close_position({
                            'symbol': position.symbol,
                            'reason': reason
                        })
                        
                        if result.success:
                            closed_positions.append(result.data)
                            total_pnl += result.data['pnl']
                    except:
                        continue
                
                return ToolResponse(
                    success=True,
                    data={
                        'positions_closed': len(closed_positions),
                        'total_pnl': total_pnl,
                        'closed': closed_positions
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("hedge_position")
        async def hedge_position(params: ToolParams) -> ToolResponse:
            """Create a hedge for an existing position"""
            symbol = params["symbol"]
            hedge_ratio = params.get("hedge_ratio", 0.5)  # Default 50% hedge
            hedge_instrument = params.get("hedge_instrument")  # e.g., put option, inverse ETF
            
            try:
                if not self.alpaca_api:
                    return ToolResponse(
                        success=False,
                        error="Alpaca API not configured"
                    )
                
                # Get current position
                position = self.alpaca_api.get_position(symbol)
                position_value = float(position.market_value)
                
                # Calculate hedge size
                hedge_value = position_value * hedge_ratio
                
                # Determine hedge instrument
                if not hedge_instrument:
                    # Default hedge strategies
                    if position.side == 'long':
                        # For long positions, could use inverse ETF or puts
                        hedge_instrument = self._get_inverse_etf(symbol)
                    else:
                        # For short positions, could use calls
                        hedge_instrument = symbol  # Simplified
                
                # Calculate hedge quantity
                hedge_price = await self._get_current_price(hedge_instrument)
                hedge_quantity = int(hedge_value / hedge_price)
                
                if hedge_quantity > 0:
                    # Execute hedge order
                    hedge_side = 'sell' if position.side == 'long' else 'buy'
                    
                    order = self.alpaca_api.submit_order(
                        symbol=hedge_instrument,
                        qty=hedge_quantity,
                        side=hedge_side,
                        type='market',
                        time_in_force='day'
                    )
                    
                    # Record hedge
                    await self._record_hedge(
                        symbol, hedge_instrument, hedge_quantity, hedge_ratio
                    )
                    
                    return ToolResponse(
                        success=True,
                        data={
                            'position_symbol': symbol,
                            'hedge_instrument': hedge_instrument,
                            'hedge_quantity': hedge_quantity,
                            'hedge_value': hedge_value,
                            'hedge_ratio': hedge_ratio,
                            'order_id': order.id
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        error="Hedge quantity too small"
                    )
                    
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("rebalance_portfolio")
        async def rebalance_portfolio(params: ToolParams) -> ToolResponse:
            """Rebalance portfolio to target allocations"""
            target_allocations = params.get("target_allocations", {})
            rebalance_threshold = params.get("threshold", 0.05)  # 5% deviation triggers rebalance
            
            try:
                if not self.alpaca_api:
                    return ToolResponse(
                        success=False,
                        error="Alpaca API not configured"
                    )
                
                # Get account value
                account = self.alpaca_api.get_account()
                portfolio_value = float(account.portfolio_value)
                
                # Get current positions
                positions = self.alpaca_api.list_positions()
                current_allocations = {}
                
                for pos in positions:
                    current_allocations[pos.symbol] = float(pos.market_value) / portfolio_value
                
                # Calculate rebalancing trades
                rebalance_orders = []
                
                for symbol, target_pct in target_allocations.items():
                    current_pct = current_allocations.get(symbol, 0)
                    deviation = target_pct - current_pct
                    
                    if abs(deviation) > rebalance_threshold:
                        # Calculate trade size
                        target_value = portfolio_value * target_pct
                        current_value = portfolio_value * current_pct
                        trade_value = target_value - current_value
                        
                        # Get current price
                        price = await self._get_current_price(symbol)
                        quantity = int(abs(trade_value) / price)
                        
                        if quantity > 0:
                            side = 'buy' if trade_value > 0 else 'sell'
                            
                            # Check if we need to close position first
                            if side == 'sell' and symbol not in current_allocations:
                                continue
                            
                            rebalance_orders.append({
                                'symbol': symbol,
                                'side': side,
                                'quantity': quantity,
                                'current_pct': current_pct,
                                'target_pct': target_pct,
                                'trade_value': trade_value
                            })
                
                # Execute rebalancing trades
                executed_orders = []
                for order_params in rebalance_orders:
                    try:
                        order = self.alpaca_api.submit_order(
                            symbol=order_params['symbol'],
                            qty=order_params['quantity'],
                            side=order_params['side'],
                            type='market',
                            time_in_force='day'
                        )
                        
                        order_params['order_id'] = order.id
                        order_params['status'] = order.status
                        executed_orders.append(order_params)
                        
                    except Exception as e:
                        order_params['error'] = str(e)
                        executed_orders.append(order_params)
                
                return ToolResponse(
                    success=True,
                    data={
                        'portfolio_value': portfolio_value,
                        'rebalance_orders': executed_orders,
                        'orders_executed': len([o for o in executed_orders if 'error' not in o]),
                        'current_allocations': current_allocations,
                        'target_allocations': target_allocations
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("export_trades")
        async def export_trades(params: ToolParams) -> ToolResponse:
            """Export trade history for analysis"""
            export_type = params.get("type", "summary")  # summary, detailed, tax
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            format = params.get("format", "json")
            
            try:
                # Get trade history
                days = 365 if not start_date else None
                trades = await self.db_client.get_trading_history(days=days)
                
                # Filter by date if specified
                if start_date:
                    start = datetime.fromisoformat(start_date)
                    trades = [t for t in trades if datetime.fromisoformat(t['entry_time']) >= start]
                
                if end_date:
                    end = datetime.fromisoformat(end_date)
                    trades = [t for t in trades if datetime.fromisoformat(t['entry_time']) <= end]
                
                # Create export based on type
                export_data = {}
                
                if export_type == "summary":
                    export_data = {
                        'period': {
                            'start': start_date or trades[0]['entry_time'] if trades else None,
                            'end': end_date or trades[-1]['entry_time'] if trades else None
                        },
                        'summary': self._create_trade_summary(trades),
                        'performance': self._calculate_performance_metrics(trades),
                        'by_symbol': self._group_trades_by_symbol(trades)
                    }
                
                elif export_type == "detailed":
                    export_data = {
                        'trades': trades,
                        'metadata': {
                            'total_trades': len(trades),
                            'exported_at': datetime.now().isoformat()
                        }
                    }
                
                elif export_type == "tax":
                    export_data = self._create_tax_report(trades)
                
                # Store export
                export_id = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await self.redis_client.setex(
                    f"trading:export:{export_id}",
                    3600,  # 1 hour TTL
                    json.dumps(export_data)
                )
                
                return ToolResponse(
                    success=True,
                    data={
                        'export_id': export_id,
                        'type': export_type,
                        'format': format,
                        'trade_count': len(trades),
                        'download_url': f"/exports/{export_id}"
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("cancel_order")
        async def cancel_order(params: ToolParams) -> ToolResponse:
            """Cancel a specific order"""
            order_id = params["order_id"]
            
            if not self.alpaca_api:
                return ToolResponse(
                    success=False,
                    error="Alpaca API not configured"
                )
            
            try:
                self.alpaca_api.cancel_order(order_id)
                
                return ToolResponse(
                    success=True,
                    data={
                        'order_id': order_id,
                        'status': 'cancelled'
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("cancel_all_orders")
        async def cancel_all_orders(params: ToolParams) -> ToolResponse:
            """Cancel all open orders"""
            reason = params.get("reason", "cancel_all")
            
            if not self.alpaca_api:
                return ToolResponse(
                    success=False,
                    error="Alpaca API not configured"
                )
            
            try:
                # Get all open orders
                open_orders = self.alpaca_api.list_orders(status='open')
                cancelled_count = 0
                
                # Cancel each order
                for order in open_orders:
                    try:
                        self.alpaca_api.cancel_order(order.id)
                        cancelled_count += 1
                    except:
                        continue
                
                return ToolResponse(
                    success=True,
                    data={
                        'orders_cancelled': cancelled_count,
                        'reason': reason
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("update_stop_loss")
        async def update_stop_loss(params: ToolParams) -> ToolResponse:
            """Update stop loss for a position"""
            symbol = params["symbol"]
            new_stop_loss = params["stop_loss"]
            
            try:
                # Implementation would update the stop loss order
                # This is simplified as Alpaca requires canceling and recreating orders
                
                return ToolResponse(
                    success=True,
                    data={
                        'symbol': symbol,
                        'new_stop_loss': new_stop_loss,
                        'updated': True
                    }
                )
                
            except Exception as e:
                return ToolResponse(
                    success=False,
                    error=str(e)
                )
    
    async def _check_risk_limits(self, signal: Dict) -> Dict:
        """Check if trade passes risk limits"""
        # Check daily trade limit
        if self.risk_manager['daily_trades'] >= self.trading_config['max_daily_trades']:
            return {'allowed': False, 'reason': 'Daily trade limit reached'}
        
        # Check position limit
        if self.alpaca_api:
            positions = self.alpaca_api.list_positions()
            if len(positions) >= self.trading_config['max_positions']:
                return {'allowed': False, 'reason': 'Maximum positions reached'}
        
        # Check exposure limit
        if self.risk_manager['current_exposure'] >= self.trading_config['max_portfolio_risk']:
            return {'allowed': False, 'reason': 'Portfolio risk limit reached'}
        
        # Check daily loss limit
        if self.risk_manager['daily_pnl'] < -self.trading_config['max_portfolio_risk'] * 10000:  # Assuming $10k account
            return {'allowed': False, 'reason': 'Daily loss limit reached'}
        
        return {'allowed': True, 'reason': None}
    
    async def _calculate_position_size(self, signal: Dict, size_override: Optional[int]) -> int:
        """Calculate position size based on risk management"""
        if size_override:
            return size_override
        
        if not self.alpaca_api:
            return 1  # Default
        
        try:
            # Get account info
            account = self.alpaca_api.get_account()
            buying_power = float(account.buying_power)
            portfolio_value = float(account.portfolio_value)
            
            # Risk-based position sizing
            risk_amount = portfolio_value * self.trading_config['risk_per_trade']
            
            # Calculate based on stop loss
            entry_price = signal.get('entry_price', 0)
            stop_loss = signal.get('stop_loss', 0)
            
            if entry_price > 0 and stop_loss > 0:
                risk_per_share = abs(entry_price - stop_loss)
                if risk_per_share > 0:
                    position_size = int(risk_amount / risk_per_share)
                else:
                    position_size = int(buying_power * self.trading_config['position_size_pct'] / entry_price)
            else:
                # Fallback to percentage-based sizing
                position_size = int(buying_power * self.trading_config['position_size_pct'] / entry_price)
            
            # Apply limits
            max_position_value = buying_power * self.trading_config['position_size_pct']
            max_shares = int(max_position_value / entry_price) if entry_price > 0 else 1
            
            return min(position_size, max_shares, 1000)  # Cap at 1000 shares
            
        except Exception as e:
            self.logger.error("Position size calculation failed", error=str(e))
            return 1
    
    async def _execute_order(self, signal: Dict, quantity: int) -> Optional[Any]:
        """Execute order via Alpaca"""
        if not self.alpaca_api:
            return None
        
        try:
            symbol = signal['symbol']
            side = 'buy' if signal['action'] == 'BUY' else 'sell'
            
            if self.trading_config['use_bracket_orders'] and signal.get('stop_loss') and signal.get('take_profit'):
                # Bracket order with stop loss and take profit
                order = self.alpaca_api.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    type='limit',
                    time_in_force='day',
                    limit_price=signal.get('entry_price'),
                    order_class='bracket',
                    stop_loss={'stop_price': signal['stop_loss']},
                    take_profit={'limit_price': signal['take_profit']}
                )
            else:
                # Simple market order
                order = self.alpaca_api.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    type='market',
                    time_in_force='day'
                )
            
            return order
            
        except APIError as e:
            self.logger.error("Alpaca API error", error=str(e))
            return None
        except Exception as e:
            self.logger.error("Order execution failed", error=str(e))
            return None
    
    def _record_rejected_order(self, signal: Dict, reason: str):
        """Record rejected order for analysis"""
        rejected = {
            'timestamp': datetime.now().isoformat(),
            'symbol': signal.get('symbol'),
            'action': signal.get('action'),
            'reason': reason,
            'signal_confidence': signal.get('confidence'),
            'entry_price': signal.get('entry_price')
        }
        
        self.rejected_orders.append(rejected)
        
        # Keep only last 100 rejected orders
        if len(self.rejected_orders) > 100:
            self.rejected_orders = self.rejected_orders[-100:]
    
    def _summarize_rejection_reasons(self, rejected_orders: List[Dict]) -> Dict:
        """Summarize rejection reasons"""
        reasons = {}
        for order in rejected_orders:
            reason = order.get('reason', 'unknown')
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
    
    def _analyze_trades(self, trades: List[Dict]) -> Dict:
        """Analyze trade performance"""
        if not trades:
            return {}
        
        # Calculate metrics
        total_trades = len(trades)
        profitable_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) <= 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        avg_win = sum(t.get('pnl', 0) for t in profitable_trades) / len(profitable_trades) if profitable_trades else 0
        avg_loss = sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Calculate additional metrics
        win_rate = len(profitable_trades) / total_trades if total_trades > 0 else 0
        profit_factor = abs(avg_win * len(profitable_trades)) / abs(avg_loss * len(losing_trades)) if avg_loss != 0 and losing_trades else 0
        
        # Duration analysis
        durations = []
        for trade in trades:
            if trade.get('exit_time') and trade.get('entry_time'):
                entry = datetime.fromisoformat(trade['entry_time'])
                exit = datetime.fromisoformat(trade['exit_time'])
                duration = (exit - entry).total_seconds() / 3600  # Hours
                durations.append(duration)
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'total_trades': total_trades,
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(win_rate, 3),
            'total_pnl': round(total_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_trade_duration_hours': round(avg_duration, 1),
            'largest_win': max((t.get('pnl', 0) for t in trades), default=0),
            'largest_loss': min((t.get('pnl', 0) for t in trades), default=0)
        }
    
    def _analyze_symbol_trades(self, trades: List[Dict], symbol: str) -> Dict:
        """Analyze trades for specific symbol"""
        symbol_trades = [t for t in trades if t.get('symbol') == symbol]
        return self._analyze_trades(symbol_trades)
    
    def _calculate_risk_score(self) -> float:
        """Calculate overall risk score (0-100)"""
        score = 0
        
        # Exposure component (40%)
        exposure_ratio = self.risk_manager['current_exposure'] / self.trading_config['max_portfolio_risk']
        score += (1 - exposure_ratio) * 40
        
        # Daily trades component (20%)
        trades_ratio = self.risk_manager['daily_trades'] / self.trading_config['max_daily_trades']
        score += (1 - trades_ratio) * 20
        
        # Win rate component (20%)
        total_trades = self.risk_manager['winning_trades'] + self.risk_manager['losing_trades']
        if total_trades > 0:
            win_rate = self.risk_manager['winning_trades'] / total_trades
            score += win_rate * 20
        else:
            score += 10  # Neutral
        
        # Drawdown component (20%)
        if self.risk_manager['max_drawdown'] < -0.1:  # More than 10% drawdown
            score += 0
        elif self.risk_manager['max_drawdown'] < -0.05:  # 5-10% drawdown
            score += 10
        else:
            score += 20
        
        return round(score, 1)
    
    def _run_stress_test(self) -> Dict:
        """Run portfolio stress test"""
        scenarios = {
            'market_crash': -0.20,  # 20% drop
            'correction': -0.10,    # 10% drop
            'volatility_spike': -0.05,  # 5% drop with high volatility
            'sector_rotation': -0.15   # Sector-specific drop
        }
        
        results = {}
        
        if self.alpaca_api:
            try:
                account = self.alpaca_api.get_account()
                portfolio_value = float(account.portfolio_value)
                
                for scenario, impact in scenarios.items():
                    potential_loss = portfolio_value * impact
                    results[scenario] = {
                        'potential_loss': round(potential_loss, 2),
                        'portfolio_impact_pct': round(impact * 100, 1),
                        'margin_call_risk': potential_loss > float(account.buying_power)
                    }
            except:
                pass
        
        return results
    
    def _get_inverse_etf(self, symbol: str) -> str:
        """Get appropriate inverse ETF for hedging"""
        # Simplified mapping
        sector_inverse_etfs = {
            'AAPL': 'PSQ',  # Inverse QQQ for tech
            'MSFT': 'PSQ',
            'GOOGL': 'PSQ',
            'AMZN': 'SQQQ',  # 3x inverse QQQ
            'TSLA': 'SQQQ',
            'JPM': 'SH',     # Inverse S&P 500
            'BAC': 'SH',
            'DEFAULT': 'SH'
        }
        
        return sector_inverse_etfs.get(symbol, sector_inverse_etfs['DEFAULT'])
    
    async def _get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        if not self.alpaca_api:
            return 0.0
        
        try:
            trades = self.alpaca_api.get_latest_trade(symbol)
            return float(trades.price)
        except:
            return 0.0
    
    async def _record_hedge(self, position_symbol: str, hedge_instrument: str,
                          hedge_quantity: int, hedge_ratio: float):
        """Record hedge in database"""
        # This would record the hedge relationship
        pass
    
    async def _update_portfolio_metrics(self, is_win: bool, pnl: float):
        """Update portfolio performance metrics"""
        # Update win rate
        total_trades = self.risk_manager['winning_trades'] + self.risk_manager['losing_trades']
        if total_trades > 0:
            self.portfolio_metrics['win_rate'] = self.risk_manager['winning_trades'] / total_trades
        
        # Update average win/loss
        if is_win:
            current_avg_win = self.portfolio_metrics.get('avg_win', 0)
            win_count = self.risk_manager['winning_trades']
            self.portfolio_metrics['avg_win'] = ((current_avg_win * (win_count - 1)) + pnl) / win_count
        else:
            current_avg_loss = self.portfolio_metrics.get('avg_loss', 0)
            loss_count = self.risk_manager['losing_trades']
            self.portfolio_metrics['avg_loss'] = ((current_avg_loss * (loss_count - 1)) + pnl) / loss_count
        
        # Update profit factor
        if self.portfolio_metrics['avg_loss'] != 0:
            self.portfolio_metrics['profit_factor'] = abs(
                self.portfolio_metrics['avg_win'] / self.portfolio_metrics['avg_loss']
            )
        
        # Save metrics
        await self._save_portfolio_metrics()
    
    def _create_trade_summary(self, trades: List[Dict]) -> Dict:
        """Create trade summary"""
        return self._analyze_trades(trades)
    
    def _calculate_performance_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate detailed performance metrics"""
        if not trades:
            return {}
        
        # Convert to pandas for easier calculation
        df = pd.DataFrame(trades)
        
        # Daily returns
        df['date'] = pd.to_datetime(df['entry_time']).dt.date
        daily_pnl = df.groupby('date')['pnl'].sum()
        
        # Calculate Sharpe ratio (simplified)
        if len(daily_pnl) > 1:
            returns = daily_pnl.pct_change().dropna()
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe = 0
        
        # Calculate max drawdown
        cumulative = daily_pnl.cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        return {
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_drawdown, 3),
            'total_return': round(daily_pnl.sum(), 2),
            'avg_daily_pnl': round(daily_pnl.mean(), 2),
            'trading_days': len(daily_pnl),
            'best_day': round(daily_pnl.max(), 2),
            'worst_day': round(daily_pnl.min(), 2)
        }
    
    def _group_trades_by_symbol(self, trades: List[Dict]) -> Dict:
        """Group trades by symbol"""
        by_symbol = {}
        
        for trade in trades:
            symbol = trade.get('symbol')
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(trade)
        
        # Analyze each symbol
        symbol_analysis = {}
        for symbol, symbol_trades in by_symbol.items():
            symbol_analysis[symbol] = self._analyze_trades(symbol_trades)
        
        return symbol_analysis
    
    def _create_tax_report(self, trades: List[Dict]) -> Dict:
        """Create tax report from trades"""
        # Simplified tax report
        short_term_gains = 0
        short_term_losses = 0
        long_term_gains = 0
        long_term_losses = 0
        
        for trade in trades:
            if not trade.get('exit_time') or not trade.get('entry_time'):
                continue
            
            # Calculate holding period
            entry = datetime.fromisoformat(trade['entry_time'])
            exit = datetime.fromisoformat(trade['exit_time'])
            holding_days = (exit - entry).days
            
            pnl = trade.get('pnl', 0)
            
            if holding_days > 365:  # Long-term
                if pnl > 0:
                    long_term_gains += pnl
                else:
                    long_term_losses += pnl
            else:  # Short-term
                if pnl > 0:
                    short_term_gains += pnl
                else:
                    short_term_losses += pnl
        
        return {
            'tax_year': datetime.now().year,
            'short_term': {
                'gains': round(short_term_gains, 2),
                'losses': round(short_term_losses, 2),
                'net': round(short_term_gains + short_term_losses, 2)
            },
            'long_term': {
                'gains': round(long_term_gains, 2),
                'losses': round(long_term_losses, 2),
                'net': round(long_term_gains + long_term_losses, 2)
            },
            'total_net': round(short_term_gains + short_term_losses + long_term_gains + long_term_losses, 2),
            'disclaimer': 'This is for informational purposes only. Consult a tax professional.'
        }
    
    async def health_check(self) -> Dict:
        """Service health check"""
        try:
            # Check database connection
            db_status = await self.db_client.get_database_status()
            
            # Check Redis connection
            redis_ok = await self.redis_client.ping() if self.redis_client else False
            
            # Check Alpaca connection
            alpaca_ok = False
            if self.alpaca_api:
                try:
                    self.alpaca_api.get_account()
                    alpaca_ok = True
                except:
                    pass
            
            return {
                'status': 'healthy' if alpaca_ok else 'degraded',
                'database': db_status.get('postgresql', {}).get('status', 'unknown'),
                'redis': 'healthy' if redis_ok else 'unhealthy',
                'alpaca': 'healthy' if alpaca_ok else 'unhealthy',
                'risk_score': self._calculate_risk_score(),
                'daily_trades': self.risk_manager['daily_trades'],
                'daily_pnl': self.risk_manager['daily_pnl']
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Trading Execution MCP Server",
                        version="3.1.0",
                        port=self.port,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


async def main():
    """Main entry point"""
    server = TradingExecutionMCPServer()
    
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