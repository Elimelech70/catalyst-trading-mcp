#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 3.1.0
Last Updated: 2025-08-23
Purpose: MCP-enabled workflow orchestration with database MCP integration

REVISION HISTORY:
v3.1.0 (2025-08-23) - Database MCP integration
- Replaced all database_utils imports with MCP Database Client
- Added missing MCP resources: config/trading, workflow/history, health/detailed
- Added missing MCP tools: run_backtest, emergency_stop, reset_system
- Updated all database operations to use async MCP client
- Enhanced service lifecycle management

v3.0.0 (2024-12-30) - Initial MCP implementation
- Workflow orchestration across all services
- Trading cycle management
- Service health monitoring

Description of Service:
Primary MCP server for Claude interaction. Orchestrates trading workflows
across all services: 1. News Collection → 2. Security Selection → 3. Pattern Analysis → 
4. Signal Generation → 5. Trade Execution → 6. Outcome Tracking
"""

import os
import sys
import json
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import structlog
from mcp import MCPServer, MCPRequest, MCPResponse, ResourceParams, ToolParams
from mcp.transport import WebSocketTransport, StdioTransport
import aiohttp
import redis.asyncio as redis

# Import MCP Database Client instead of database_utils
from mcp_database_client import MCPDatabaseClient


class OrchestrationMCPServer:
    """MCP Server for trading workflow orchestration"""
    
    def __init__(self):
        self.server = MCPServer("orchestration")
        self.logger = structlog.get_logger().bind(service="orchestration_mcp")
        
        # Database client (initialized in async context)
        self.db_client: Optional[MCPDatabaseClient] = None
        
        # Service registry
        self.services = {
            'news': {
                'name': 'news_intelligence',
                'mcp_url': os.getenv('NEWS_MCP_URL', 'ws://news-service:5008'),
                'port': 5008,
                'status': 'unknown'
            },
            'scanner': {
                'name': 'security_scanner',
                'mcp_url': os.getenv('SCANNER_MCP_URL', 'ws://scanner-service:5001'),
                'port': 5001,
                'status': 'unknown'
            },
            'pattern': {
                'name': 'pattern_analysis',
                'mcp_url': os.getenv('PATTERN_MCP_URL', 'ws://pattern-service:5002'),
                'port': 5002,
                'status': 'unknown'
            },
            'technical': {
                'name': 'technical_analysis',
                'mcp_url': os.getenv('TECHNICAL_MCP_URL', 'ws://technical-service:5003'),
                'port': 5003,
                'status': 'unknown'
            },
            'trading': {
                'name': 'trading_execution',
                'mcp_url': os.getenv('TRADING_MCP_URL', 'ws://trading-service:5005'),
                'port': 5005,
                'status': 'unknown'
            },
            'reporting': {
                'name': 'reporting_analytics',
                'mcp_url': os.getenv('REPORTING_MCP_URL', 'ws://reporting-service:5009'),
                'port': 5009,
                'status': 'unknown'
            },
            'database': {
                'name': 'database_service',
                'mcp_url': os.getenv('DATABASE_MCP_URL', 'ws://database-service:5010'),
                'port': 5010,
                'status': 'unknown'
            }
        }
        
        # Trading cycle state
        self.current_cycle = None
        self.cycle_history = []
        
        # Workflow configuration
        self.workflow_config = {
            'max_candidates': int(os.getenv('MAX_CANDIDATES', '100')),
            'top_candidates': int(os.getenv('TOP_CANDIDATES', '5')),
            'cycle_interval': int(os.getenv('CYCLE_INTERVAL', '300')),  # 5 minutes
            'pre_market_start': os.getenv('PRE_MARKET_START', '04:00'),
            'market_open': os.getenv('MARKET_OPEN', '09:30'),
            'market_close': os.getenv('MARKET_CLOSE', '16:00'),
            'after_hours_end': os.getenv('AFTER_HOURS_END', '20:00')
        }
        
        # Trading configuration
        self.trading_config = {
            'trading_enabled': os.getenv('TRADING_ENABLED', 'false').lower() == 'true',
            'max_positions': int(os.getenv('MAX_POSITIONS', '5')),
            'position_size_pct': float(os.getenv('POSITION_SIZE_PCT', '0.2')),
            'stop_loss_pct': float(os.getenv('STOP_LOSS_PCT', '0.02')),
            'take_profit_pct': float(os.getenv('TAKE_PROFIT_PCT', '0.04')),
            'max_daily_trades': int(os.getenv('MAX_DAILY_TRADES', '10'))
        }
        
        # Redis client for caching
        self.redis_client = None
        
        # Workflow control
        self.running = False
        self.workflow_task = None
        
        # Register MCP endpoints
        self._register_resources()
        self._register_tools()
        
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
        
        # Check all services
        await self._check_all_services()
        
        self.logger.info("Orchestration service initialized",
                        database_connected=True,
                        redis_connected=True,
                        services_checked=True)
    
    async def cleanup(self):
        """Clean up resources"""
        if self.workflow_task and not self.workflow_task.done():
            self.workflow_task.cancel()
            
        if self.redis_client:
            await self.redis_client.close()
            
        if self.db_client:
            await self.db_client.disconnect()
    
    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("workflow/status")
        async def get_workflow_status(params: ResourceParams) -> MCPResponse:
            """Get current workflow status"""
            status = {
                'running': self.running,
                'current_cycle': self.current_cycle,
                'cycle_history': self.cycle_history[-10:],  # Last 10 cycles
                'services': {k: v['status'] for k, v in self.services.items()},
                'next_cycle': self._get_next_cycle_time() if self.running else None
            }
            
            return MCPResponse(
                type="workflow_status",
                data=status,
                metadata={'timestamp': datetime.now().isoformat()}
            )
        
        @self.server.resource("workflow/history")
        async def get_workflow_history(params: ResourceParams) -> MCPResponse:
            """Get workflow execution history"""
            limit = params.get('limit', 50)
            status_filter = params.get('status')  # completed, failed, all
            
            history = self.cycle_history
            if status_filter and status_filter != 'all':
                history = [c for c in history if c.get('status') == status_filter]
            
            return MCPResponse(
                type="workflow_history",
                data={'cycles': history[-limit:]},
                metadata={'total': len(history), 'filtered': len(history[-limit:])}
            )
        
        @self.server.resource("health/services")
        async def get_services_health(params: ResourceParams) -> MCPResponse:
            """Get health status of all services"""
            health_data = {}
            
            for service_key, service_info in self.services.items():
                # Get health from database
                service_health = await self.db_client.get_service_health(service_info['name'])
                health_data[service_key] = {
                    'name': service_info['name'],
                    'port': service_info['port'],
                    'status': service_health.get('status', 'unknown'),
                    'last_check': service_health.get('last_check'),
                    'details': service_health.get('details', {})
                }
            
            return MCPResponse(
                type="services_health",
                data=health_data,
                metadata={'checked_at': datetime.now().isoformat()}
            )
        
        @self.server.resource("health/detailed")
        async def get_detailed_health(params: ResourceParams) -> MCPResponse:
            """Get detailed system health including database and cache"""
            # Get database status
            db_status = await self.db_client.get_database_status()
            
            # Get cache status
            cache_status = await self.db_client.get_cache_status()
            
            # Get service health
            services_health = {}
            for service_key, service_info in self.services.items():
                service_health = await self.db_client.get_service_health(service_info['name'])
                services_health[service_key] = service_health
            
            return MCPResponse(
                type="detailed_health",
                data={
                    'database': db_status,
                    'cache': cache_status,
                    'services': services_health,
                    'orchestration': {
                        'status': 'healthy',
                        'workflow_running': self.running,
                        'current_cycle': self.current_cycle is not None
                    }
                },
                metadata={'timestamp': datetime.now().isoformat()}
            )
        
        @self.server.resource("config/trading")
        async def get_trading_config(params: ResourceParams) -> MCPResponse:
            """Get current trading configuration"""
            return MCPResponse(
                type="trading_config",
                data={
                    **self.trading_config,
                    'workflow_config': self.workflow_config
                },
                metadata={'source': 'environment'}
            )
        
        @self.server.resource("candidates/active")
        async def get_active_candidates(params: ResourceParams) -> MCPResponse:
            """Get currently active trading candidates"""
            if not self.current_cycle:
                return MCPResponse(
                    type="candidates",
                    data={'candidates': []},
                    metadata={'cycle_active': False}
                )
            
            candidates = self.current_cycle.get('candidates', [])
            return MCPResponse(
                type="candidates",
                data={'candidates': candidates},
                metadata={
                    'cycle_id': self.current_cycle.get('cycle_id'),
                    'count': len(candidates)
                }
            )
    
    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("start_trading_cycle")
        async def start_trading_cycle(params: ToolParams) -> MCPResponse:
            """Start the automated trading workflow"""
            if self.running:
                return MCPResponse(
                    success=False,
                    error="Trading cycle already running"
                )
            
            mode = params.get('mode', 'normal')
            self.running = True
            
            # Start the workflow task
            self.workflow_task = asyncio.create_task(self._run_workflow_loop(mode))
            
            return MCPResponse(
                success=True,
                data={
                    'status': 'started',
                    'mode': mode,
                    'cycle_interval': self.workflow_config['cycle_interval']
                }
            )
        
        @self.server.tool("stop_trading")
        async def stop_trading(params: ToolParams) -> MCPResponse:
            """Stop the automated trading workflow"""
            reason = params.get('reason', 'manual_stop')
            emergency = params.get('emergency', False)
            
            self.running = False
            
            if self.workflow_task and not self.workflow_task.done():
                self.workflow_task.cancel()
            
            # Close any open positions if emergency stop
            positions_closed = 0
            if emergency and self.trading_config['trading_enabled']:
                result = await self._call_service_tool(
                    'trading', 'close_all_positions', {'reason': reason}
                )
                if result and result.success:
                    positions_closed = result.data.get('positions_closed', 0)
            
            return MCPResponse(
                success=True,
                data={
                    'status': 'stopped',
                    'reason': reason,
                    'emergency': emergency,
                    'positions_closed': positions_closed
                }
            )
        
        @self.server.tool("emergency_stop")
        async def emergency_stop(params: ToolParams) -> MCPResponse:
            """Emergency stop - halt all operations and close positions"""
            reason = params.get('reason', 'emergency_stop')
            
            # Stop workflow
            self.running = False
            if self.workflow_task and not self.workflow_task.done():
                self.workflow_task.cancel()
            
            # Close all positions
            positions_result = await self._call_service_tool(
                'trading', 'close_all_positions', {'reason': reason}
            )
            
            # Cancel all pending orders
            orders_result = await self._call_service_tool(
                'trading', 'cancel_all_orders', {'reason': reason}
            )
            
            # Log emergency stop
            if self.current_cycle:
                await self.db_client.log_workflow_step(
                    self.current_cycle['cycle_id'],
                    'emergency_stop',
                    'completed',
                    {'reason': reason}
                )
            
            return MCPResponse(
                success=True,
                data={
                    'status': 'emergency_stopped',
                    'positions_closed': positions_result.data.get('positions_closed', 0) if positions_result else 0,
                    'orders_cancelled': orders_result.data.get('orders_cancelled', 0) if orders_result else 0,
                    'reason': reason
                }
            )
        
        @self.server.tool("run_single_cycle")
        async def run_single_cycle(params: ToolParams) -> MCPResponse:
            """Run a single trading cycle manually"""
            mode = params.get('mode', 'normal')
            
            if self.running:
                return MCPResponse(
                    success=False,
                    error="Cannot run manual cycle while automated workflow is active"
                )
            
            # Run one cycle
            cycle_result = await self._run_single_trading_cycle(mode)
            
            return MCPResponse(
                success=True,
                data=cycle_result
            )
        
        @self.server.tool("update_config")
        async def update_config(params: ToolParams) -> MCPResponse:
            """Update trading configuration"""
            config_key = params['config_key']
            config_value = params['config_value']
            
            # Update appropriate config
            if config_key in self.trading_config:
                old_value = self.trading_config[config_key]
                self.trading_config[config_key] = config_value
                
                # Some configs need type conversion
                if config_key in ['max_positions', 'max_daily_trades']:
                    self.trading_config[config_key] = int(config_value)
                elif config_key in ['position_size_pct', 'stop_loss_pct', 'take_profit_pct']:
                    self.trading_config[config_key] = float(config_value)
                elif config_key == 'trading_enabled':
                    self.trading_config[config_key] = str(config_value).lower() == 'true'
                
            elif config_key in self.workflow_config:
                old_value = self.workflow_config[config_key]
                self.workflow_config[config_key] = config_value
                
                if config_key in ['max_candidates', 'top_candidates', 'cycle_interval']:
                    self.workflow_config[config_key] = int(config_value)
            else:
                return MCPResponse(
                    success=False,
                    error=f"Unknown configuration key: {config_key}"
                )
            
            return MCPResponse(
                success=True,
                data={
                    'updated': True,
                    'key': config_key,
                    'old_value': old_value,
                    'new_value': config_value,
                    'requires_restart': config_key in ['cycle_interval']
                }
            )
        
        @self.server.tool("run_backtest")
        async def run_backtest(params: ToolParams) -> MCPResponse:
            """Run a backtest with specified parameters"""
            start_date = params['start_date']
            end_date = params['end_date']
            strategy_params = params.get('strategy_params', {})
            symbols = params.get('symbols', [])
            
            # Call reporting service to run backtest
            backtest_result = await self._call_service_tool(
                'reporting', 'run_backtest', {
                    'start_date': start_date,
                    'end_date': end_date,
                    'strategy_params': strategy_params,
                    'symbols': symbols
                }
            )
            
            if not backtest_result or not backtest_result.success:
                return MCPResponse(
                    success=False,
                    error="Backtest failed to execute"
                )
            
            return MCPResponse(
                success=True,
                data=backtest_result.data
            )
        
        @self.server.tool("reset_system")
        async def reset_system(params: ToolParams) -> MCPResponse:
            """Reset system state - clear caches, reset counters"""
            confirm = params.get('confirm', False)
            
            if not confirm:
                return MCPResponse(
                    success=False,
                    error="Reset requires confirmation"
                )
            
            # Clear Redis caches
            if self.redis_client:
                await self.redis_client.flushdb()
            
            # Reset cycle history
            self.cycle_history = []
            self.current_cycle = None
            
            # Reset service states
            for service in self.services.values():
                service['status'] = 'unknown'
            
            # Clear any cached data in services
            reset_tasks = []
            for service_key in ['scanner', 'pattern', 'technical', 'news']:
                reset_tasks.append(
                    self._call_service_tool(service_key, 'clear_cache', {})
                )
            
            await asyncio.gather(*reset_tasks, return_exceptions=True)
            
            return MCPResponse(
                success=True,
                data={
                    'reset_complete': True,
                    'caches_cleared': True,
                    'history_cleared': True
                }
            )
    
    async def _run_workflow_loop(self, mode: str):
        """Main workflow loop"""
        self.logger.info("Starting workflow loop", mode=mode)
        
        while self.running:
            try:
                # Check if we're in trading hours
                if not self._is_trading_hours() and mode != 'test':
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Run a trading cycle
                await self._run_single_trading_cycle(mode)
                
                # Wait for next cycle
                await asyncio.sleep(self.workflow_config['cycle_interval'])
                
            except asyncio.CancelledError:
                self.logger.info("Workflow loop cancelled")
                break
            except Exception as e:
                self.logger.error("Error in workflow loop", error=str(e))
                await asyncio.sleep(30)  # Wait before retry
    
    async def _run_single_trading_cycle(self, mode: str) -> Dict:
        """Run a single trading cycle"""
        cycle_id = None
        
        try:
            # Create trading cycle in database
            cycle_id = await self.db_client.create_trading_cycle({
                'cycle_type': mode,
                'metadata': {
                    'start_time': datetime.now().isoformat(),
                    'workflow_config': self.workflow_config,
                    'trading_config': self.trading_config
                }
            })
            
            self.current_cycle = {
                'cycle_id': cycle_id,
                'mode': mode,
                'start_time': datetime.now(),
                'status': 'running',
                'steps_completed': [],
                'errors': []
            }
            
            # Step 1: News Collection
            await self.db_client.log_workflow_step(cycle_id, 'news_collection', 'started')
            news_result = await self._call_service_tool(
                'news', 'collect_news', {
                    'mode': mode,
                    'cycle_id': cycle_id
                }
            )
            
            if news_result and news_result.success:
                news_collected = news_result.data.get('collected', 0)
                self.current_cycle['news_collected'] = news_collected
                self.current_cycle['steps_completed'].append('news_collection')
                await self.db_client.log_workflow_step(
                    cycle_id, 'news_collection', 'completed',
                    {'articles_collected': news_collected}
                )
            else:
                await self.db_client.log_workflow_step(
                    cycle_id, 'news_collection', 'failed',
                    {'error': news_result.error if news_result else 'Unknown error'}
                )
            
            # Step 2: Security Scanning
            await self.db_client.log_workflow_step(cycle_id, 'security_scanning', 'started')
            scan_result = await self._call_service_tool(
                'scanner', 'scan_market', {
                    'mode': mode,
                    'news_context': news_result.data if news_result else {},
                    'max_candidates': self.workflow_config['max_candidates']
                }
            )
            
            if scan_result and scan_result.success:
                candidates = scan_result.data.get('candidates', [])
                self.current_cycle['candidates'] = candidates
                self.current_cycle['candidates_selected'] = len(candidates)
                self.current_cycle['steps_completed'].append('security_scanning')
                
                await self.db_client.log_workflow_step(
                    cycle_id, 'security_scanning', 'completed',
                    {'candidates_found': len(candidates)}
                )
                
                # Step 3: Pattern Analysis for top candidates
                top_candidates = candidates[:self.workflow_config['top_candidates']]
                patterns_analyzed = 0
                
                for candidate in top_candidates:
                    pattern_result = await self._call_service_tool(
                        'pattern', 'detect_patterns', {
                            'symbol': candidate['symbol'],
                            'catalyst_context': candidate.get('catalyst_data', {})
                        }
                    )
                    if pattern_result and pattern_result.success:
                        patterns_analyzed += 1
                        candidate['patterns'] = pattern_result.data.get('patterns', [])
                
                if patterns_analyzed > 0:
                    self.current_cycle['patterns_analyzed'] = patterns_analyzed
                    self.current_cycle['steps_completed'].append('pattern_analysis')
                
                # Step 4: Signal Generation for top candidates
                signals_generated = 0
                for candidate in top_candidates:
                    signal_result = await self._call_service_tool(
                        'technical', 'generate_signal', {
                            'symbol': candidate['symbol'],
                            'catalyst_score': candidate.get('catalyst_score', 0),
                            'patterns': candidate.get('patterns', [])
                        }
                    )
                    if signal_result and signal_result.success:
                        signals_generated += 1
                        candidate['signal'] = signal_result.data.get('signal')
                
                if signals_generated > 0:
                    self.current_cycle['signals_generated'] = signals_generated
                    self.current_cycle['steps_completed'].append('signal_generation')
                
                # Step 5: Trade Execution (if enabled)
                if self.trading_config['trading_enabled'] and signals_generated > 0:
                    trade_result = await self._call_service_tool(
                        'trading', 'execute_signals', {'cycle_id': cycle_id}
                    )
                    
                    if trade_result and trade_result.success:
                        self.current_cycle['trades_executed'] = trade_result.data.get('trades_executed', 0)
                        self.current_cycle['steps_completed'].append('trade_execution')
            
            # Complete cycle
            await self._complete_cycle(cycle_id, 'completed')
            
            return {
                'cycle_id': cycle_id,
                'status': 'completed',
                'steps_completed': self.current_cycle['steps_completed'],
                'summary': {
                    'news_collected': self.current_cycle.get('news_collected', 0),
                    'candidates_found': self.current_cycle.get('candidates_selected', 0),
                    'patterns_analyzed': self.current_cycle.get('patterns_analyzed', 0),
                    'signals_generated': self.current_cycle.get('signals_generated', 0),
                    'trades_executed': self.current_cycle.get('trades_executed', 0)
                }
            }
            
        except Exception as e:
            self.logger.error("Error in trading cycle", cycle_id=cycle_id, error=str(e))
            if cycle_id:
                await self._complete_cycle(cycle_id, 'failed', str(e))
            
            return {
                'cycle_id': cycle_id,
                'status': 'failed',
                'error': str(e)
            }
    
    async def _complete_cycle(self, cycle_id: str, status: str, error: Optional[str] = None):
        """Complete a trading cycle"""
        try:
            # Update cycle in database
            await self.db_client.update_trading_cycle(
                cycle_id, status,
                {
                    'end_time': datetime.now().isoformat(),
                    'error': error,
                    'summary': {
                        'steps_completed': self.current_cycle.get('steps_completed', []),
                        'news_collected': self.current_cycle.get('news_collected', 0),
                        'candidates_selected': self.current_cycle.get('candidates_selected', 0),
                        'trades_executed': self.current_cycle.get('trades_executed', 0)
                    }
                }
            )
            
            # Update cycle status
            if self.current_cycle:
                self.current_cycle['status'] = status
                self.current_cycle['end_time'] = datetime.now()
                if error:
                    self.current_cycle['errors'].append(error)
                
                # Add to history
                self.cycle_history.append(self.current_cycle.copy())
                
                # Keep only last 100 cycles in memory
                if len(self.cycle_history) > 100:
                    self.cycle_history = self.cycle_history[-100:]
            
        except Exception as e:
            self.logger.error("Error completing cycle", cycle_id=cycle_id, error=str(e))
    
    async def _call_service_tool(self, service_key: str, tool_name: str, 
                                params: Dict) -> Optional[MCPResponse]:
        """Call a tool on another MCP service"""
        service = self.services.get(service_key)
        if not service:
            self.logger.error(f"Unknown service: {service_key}")
            return None
        
        try:
            # Create MCP client connection to service
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(service['mcp_url']) as ws:
                    # Send tool invocation
                    request = MCPRequest(
                        type="tool",
                        tool=tool_name,
                        params=params
                    )
                    await ws.send_json(request.to_dict())
                    
                    # Wait for response
                    response_data = await ws.receive_json()
                    return MCPResponse.from_dict(response_data)
                    
        except Exception as e:
            self.logger.error(f"Error calling {service_key}.{tool_name}", error=str(e))
            return None
    
    async def _check_all_services(self):
        """Check health of all services"""
        for service_key, service_info in self.services.items():
            try:
                # Skip database service (we're already connected)
                if service_key == 'database':
                    service_info['status'] = 'healthy'
                    continue
                
                # Try to connect and check health
                async with aiohttp.ClientSession() as session:
                    health_url = f"http://{service_key}-service:{service_info['port']}/health"
                    async with session.get(health_url, timeout=5) as response:
                        if response.status == 200:
                            service_info['status'] = 'healthy'
                        else:
                            service_info['status'] = 'degraded'
            except:
                service_info['status'] = 'unhealthy'
            
            # Update service health in database
            await self.db_client.update_service_health(
                service_info['name'],
                service_info['status'],
                {'last_check': datetime.now().isoformat()}
            )
    
    def _is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        # Convert times to comparable format
        pre_market_start = self.workflow_config['pre_market_start']
        after_hours_end = self.workflow_config['after_hours_end']
        
        # Simple comparison (assumes times are in 24h format)
        return pre_market_start <= current_time <= after_hours_end
    
    def _get_next_cycle_time(self) -> str:
        """Calculate next cycle execution time"""
        if not self.running:
            return None
        
        next_time = datetime.now() + timedelta(seconds=self.workflow_config['cycle_interval'])
        return next_time.isoformat()
    
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
                'workflow_running': self.running,
                'services': {k: v['status'] for k, v in self.services.items()}
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def run(self):
        """Start the MCP server"""
        self.logger.info("Starting Orchestration MCP Server",
                        version="3.1.0",
                        port=5000,
                        environment=os.getenv('ENVIRONMENT', 'development'))
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=5000)
        
        # Run server
        await self.server.run(transport)


async def main():
    """Main entry point"""
    server = OrchestrationMCPServer()
    
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