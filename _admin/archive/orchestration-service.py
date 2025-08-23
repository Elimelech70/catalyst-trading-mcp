#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 3.0.0
Last Updated: 2024-08-18
Purpose: MCP-enabled orchestration service for news-driven trading workflow

REVISION HISTORY:
v3.0.0 (2024-12-30) - Complete MCP migration
- Transformed from REST to MCP protocol
- All operations exposed as resources (read) and tools (write)
- WebSocket and stdio transport support
- Claude-native integration
- Maintains backward compatibility during transition

Description of Service:
This MCP server orchestrates the news-driven workflow:
1. News Collection → 2. Security Selection → 3. Pattern Analysis → 
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

# Import database utilities
from database_utils import (
    get_db_connection,
    create_trading_cycle,
    update_trading_cycle,
    update_service_health,
    get_service_health,
    health_check,
    log_workflow_step
)


class OrchestrationMCPServer:
    """MCP Server for trading workflow orchestration"""
    
    def __init__(self):
        self.server = MCPServer("orchestration")
        self.logger = structlog.get_logger().bind(service="orchestration_mcp")
        
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
            }
        }
        
        # Trading cycle state
        self.current_cycle = None
        self.cycle_history = []
        
        # Workflow configuration
        self.workflow_config = {
            'pre_market': {
                'enabled': os.getenv('PREMARKET_ENABLED', 'true').lower() == 'true',
                'start_time': os.getenv('PREMARKET_START', '04:00'),
                'end_time': os.getenv('PREMARKET_END', '09:30'),
                'interval_minutes': int(os.getenv('PREMARKET_INTERVAL', '5')),
                'mode': 'aggressive'
            },
            'market_hours': {
                'enabled': os.getenv('MARKET_HOURS_ENABLED', 'true').lower() == 'true',
                'start_time': os.getenv('MARKET_START', '09:30'),
                'end_time': os.getenv('MARKET_END', '16:00'),
                'interval_minutes': int(os.getenv('MARKET_INTERVAL', '30')),
                'mode': 'normal'
            }
        }
        
        # Register resources and tools
        self._register_resources()
        self._register_tools()
        
        self.logger.info("Orchestration MCP Server initialized", version="3.0.0")
        
    def _register_resources(self):
        """Register read-only resources"""
        
        @self.server.resource("workflow/status")
        async def get_workflow_status(params: ResourceParams) -> MCPResponse:
            """Get current workflow status and configuration"""
            return MCPResponse(
                resource_type="workflow_status",
                data={
                    'config': self.workflow_config,
                    'current_cycle': self._serialize_cycle(self.current_cycle),
                    'cycle_history': [self._serialize_cycle(c) for c in self.cycle_history[-10:]],
                    'timestamp': datetime.now().isoformat()
                }
            )
        
        @self.server.resource("health/services")
        async def get_services_health(params: ResourceParams) -> MCPResponse:
            """Get health status of all services"""
            health_data = await self._check_all_services_health()
            return MCPResponse(
                resource_type="services_health",
                data=health_data
            )
        
        @self.server.resource("config/trading")
        async def get_trading_config(params: ResourceParams) -> MCPResponse:
            """Get current trading configuration"""
            config = {
                'trading_enabled': os.getenv('TRADING_ENABLED', 'false').lower() == 'true',
                'max_positions': int(os.getenv('MAX_POSITIONS', '5')),
                'position_size': float(os.getenv('POSITION_SIZE', '0.02')),
                'stop_loss_percent': float(os.getenv('STOP_LOSS_PERCENT', '0.02')),
                'workflow_config': self.workflow_config
            }
            return MCPResponse(
                resource_type="trading_config",
                data=config
            )
        
        @self.server.resource("cycle/current")
        async def get_current_cycle(params: ResourceParams) -> MCPResponse:
            """Get current trading cycle details"""
            if not self.current_cycle:
                return MCPResponse(
                    resource_type="cycle_status",
                    data={'status': 'no_active_cycle'}
                )
            return MCPResponse(
                resource_type="cycle_status",
                data=self._serialize_cycle(self.current_cycle)
            )
        
        @self.server.resource("cycle/history")
        async def get_cycle_history(params: ResourceParams) -> MCPResponse:
            """Get trading cycle history"""
            limit = params.get('limit', 50)
            cycles = self.cycle_history[-limit:]
            return MCPResponse(
                resource_type="cycle_history",
                data={'cycles': [self._serialize_cycle(c) for c in cycles]}
            )
        
    def _register_tools(self):
        """Register callable tools"""
        
        @self.server.tool("start_trading_cycle")
        async def start_trading_cycle(params: ToolParams) -> MCPResponse:
            """Start a new trading cycle"""
            mode = params.get('mode', 'normal')
            
            if self.current_cycle and self.current_cycle['status'] == 'running':
                return MCPResponse(
                    success=False,
                    error="Cycle already running",
                    data={'cycle_id': self.current_cycle['cycle_id']}
                )
            
            try:
                cycle = await self._start_new_cycle(mode)
                return MCPResponse(
                    success=True,
                    data=self._serialize_cycle(cycle)
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("stop_trading")
        async def stop_trading(params: ToolParams) -> MCPResponse:
            """Stop current trading cycle"""
            if not self.current_cycle:
                return MCPResponse(
                    success=False,
                    error="No active cycle to stop"
                )
            
            try:
                await self._stop_current_cycle(params.get('reason', 'manual_stop'))
                return MCPResponse(
                    success=True,
                    data={'message': 'Trading cycle stopped'}
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("run_backtest")
        async def run_backtest(params: ToolParams) -> MCPResponse:
            """Run backtest on historical data"""
            try:
                start_date = params.get('start_date')
                end_date = params.get('end_date')
                strategy = params.get('strategy', 'default')
                
                # Placeholder for backtest implementation
                result = {
                    'backtest_id': f"bt_{int(time.time())}",
                    'start_date': start_date,
                    'end_date': end_date,
                    'strategy': strategy,
                    'status': 'queued',
                    'message': 'Backtest queued for execution'
                }
                
                return MCPResponse(
                    success=True,
                    data=result
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("update_config")
        async def update_config(params: ToolParams) -> MCPResponse:
            """Update trading configuration"""
            try:
                config_key = params.get('key')
                config_value = params.get('value')
                
                if not config_key:
                    return MCPResponse(
                        success=False,
                        error="Configuration key required"
                    )
                
                # Update environment variable or configuration
                os.environ[config_key] = str(config_value)
                
                return MCPResponse(
                    success=True,
                    data={
                        'key': config_key,
                        'value': config_value,
                        'updated_at': datetime.now().isoformat()
                    }
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("emergency_stop")
        async def emergency_stop(params: ToolParams) -> MCPResponse:
            """Emergency stop all trading activities"""
            try:
                # Stop current cycle
                if self.current_cycle:
                    await self._stop_current_cycle('emergency_stop')
                
                # Send emergency stop to trading service
                trading_response = await self._call_service_tool(
                    'trading', 'emergency_stop', {}
                )
                
                return MCPResponse(
                    success=True,
                    data={
                        'status': 'emergency_stop_completed',
                        'trading_stopped': trading_response.success if trading_response else False,
                        'timestamp': datetime.now().isoformat()
                    }
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
        
        @self.server.tool("run_workflow_step")
        async def run_workflow_step(params: ToolParams) -> MCPResponse:
            """Execute a specific workflow step"""
            step_name = params.get('step_name')
            cycle_id = params.get('cycle_id', self.current_cycle.get('cycle_id') if self.current_cycle else None)
            
            if not cycle_id:
                return MCPResponse(
                    success=False,
                    error="No active cycle"
                )
            
            try:
                result = await self._execute_workflow_step(step_name, cycle_id, params)
                return MCPResponse(
                    success=True,
                    data=result
                )
            except Exception as e:
                return MCPResponse(
                    success=False,
                    error=str(e)
                )
    
    async def _start_new_cycle(self, mode: str) -> Dict:
        """Start a new trading cycle"""
        # Create cycle using database function
        cycle_id = create_trading_cycle({
            'scan_type': mode,
            'target_securities': 50,
            'config': {'mode': mode}
})
        self.current_cycle = {
            'cycle_id': cycle_id,
            'mode': mode,
            'status': 'running',
            'start_time': datetime.now(),
            'steps_completed': [],
            'errors': []
        }
        
        # Log workflow start
        log_workflow_step(cycle_id, 'workflow_start', 'started', 
                        result={'mode': mode})
        
        # Start workflow execution
        asyncio.create_task(self._run_trading_workflow(cycle_id, mode))
        
        return self.current_cycle
    
    async def _run_trading_workflow(self, cycle_id: str, mode: str):
        """Execute the complete trading workflow via MCP"""
        try:
            self.logger.info("Starting trading workflow", cycle_id=cycle_id, mode=mode)
            
            # Step 1: Collect News
            log_workflow_step(cycle_id, 'news_collection', 'started')
            news_result = await self._call_service_tool(
                'news', 'collect_news', {'mode': mode, 'cycle_id': cycle_id}
            )
            
            if news_result and news_result.success:
                articles_collected = news_result.data.get('articles_collected', 0)
                self.current_cycle['news_collected'] = articles_collected
                self.current_cycle['steps_completed'].append('news_collection')
                log_workflow_step(cycle_id, 'news_collection', 'completed',
                                result=news_result.data, records_processed=articles_collected)
            else:
                log_workflow_step(cycle_id, 'news_collection', 'failed',
                                error_message=news_result.error if news_result else 'Unknown error')
            
            # Step 2: Security Scanning
            log_workflow_step(cycle_id, 'security_scanning', 'started')
            scan_result = await self._call_service_tool(
                'scanner', 'scan_market', {'mode': mode, 'news_context': news_result.data if news_result else {}}
            )
            
            if scan_result and scan_result.success:
                candidates = scan_result.data.get('candidates', [])
                self.current_cycle['candidates_selected'] = len(candidates)
                self.current_cycle['steps_completed'].append('security_scanning')
                
                # Step 3: Pattern Analysis for top 5 candidates
                patterns_analyzed = 0
                for candidate in candidates[:5]:
                    pattern_result = await self._call_service_tool(
                        'pattern', 'detect_patterns', {
                            'symbol': candidate['symbol'],
                            'catalyst_context': candidate.get('catalyst_data', {})
                        }
                    )
                    if pattern_result and pattern_result.success:
                        patterns_analyzed += 1
                
                if patterns_analyzed > 0:
                    self.current_cycle['patterns_analyzed'] = patterns_analyzed
                    self.current_cycle['steps_completed'].append('pattern_analysis')
                
                # Step 4: Signal Generation
                signals_generated = 0
                for candidate in candidates[:5]:
                    signal_result = await self._call_service_tool(
                        'technical', 'generate_signal', {
                            'symbol': candidate['symbol'],
                            'catalyst_score': candidate.get('catalyst_score', 0),
                            'patterns': []  # Would come from pattern analysis
                        }
                    )
                    if signal_result and signal_result.success:
                        signals_generated += 1
                
                if signals_generated > 0:
                    self.current_cycle['signals_generated'] = signals_generated
                    self.current_cycle['steps_completed'].append('signal_generation')
                
                # Step 5: Trade Execution
                if os.getenv('TRADING_ENABLED', 'false').lower() == 'true' and signals_generated > 0:
                    trade_result = await self._call_service_tool(
                        'trading', 'execute_signals', {'cycle_id': cycle_id}
                    )
                    
                    if trade_result and trade_result.success:
                        self.current_cycle['trades_executed'] = trade_result.data.get('trades_executed', 0)
                        self.current_cycle['steps_completed'].append('trade_execution')
            
            # Complete cycle
            await self._complete_cycle(cycle_id, 'completed')
            
        except Exception as e:
            self.logger.error("Error in trading workflow", cycle_id=cycle_id, error=str(e))
            self.current_cycle['errors'].append(str(e))
            await self._complete_cycle(cycle_id, 'failed', str(e))
    
    async def _call_service_tool(self, service_key: str, tool_name: str, params: Dict) -> Optional[MCPResponse]:
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
    
    async def _check_all_services_health(self) -> Dict:
        """Check health of all services via MCP"""
        health_status = {}
        
        for service_key, service_info in self.services.items():
            try:
                # Call health resource on each service
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(service_info['mcp_url']) as ws:
                        request = MCPRequest(
                            type="resource",
                            resource="health/status",
                            params={}
                        )
                        await ws.send_json(request.to_dict())
                        
                        response_data = await ws.receive_json()
                        response = MCPResponse.from_dict(response_data)
                        
                        health_status[service_key] = {
                            'status': 'healthy' if response.success else 'unhealthy',
                            'last_check': datetime.now().isoformat(),
                            'details': response.data
                        }
            except Exception as e:
                health_status[service_key] = {
                    'status': 'unreachable',
                    'last_check': datetime.now().isoformat(),
                    'error': str(e)
                }
        
        return health_status
    
    async def _complete_cycle(self, cycle_id: str, status: str, error: str = None):
        """Complete a trading cycle"""
        self.current_cycle['status'] = status
        self.current_cycle['end_time'] = datetime.now()
        self.current_cycle['duration'] = (
            self.current_cycle['end_time'] - self.current_cycle['start_time']
        ).total_seconds()
        
        # Update database
        updates = {
            'status': status,
            'end_time': datetime.now(),
            'candidates_found': self.current_cycle.get('candidates_selected', 0),
            'trades_executed': self.current_cycle.get('trades_executed', 0),
            'total_pnl': self.current_cycle.get('total_pnl', 0.0),
            'errors': self.current_cycle.get('errors', []) if error else []
        }

        if error:
            updates['error_message'] = error
        
        update_trading_cycle(cycle_id, updates)
        
        # Log workflow completion
        log_workflow_step(cycle_id, 'workflow_complete', status,
                        result={'duration_seconds': self.current_cycle['duration']})
        
        # Archive current cycle
        self.cycle_history.append(self.current_cycle.copy())
        if len(self.cycle_history) > 100:
            self.cycle_history.pop(0)
    
    async def _stop_current_cycle(self, reason: str):
        """Stop the current trading cycle"""
        if self.current_cycle:
            await self._complete_cycle(
                self.current_cycle['cycle_id'], 
                'stopped', 
                f"Stopped: {reason}"
            )
            self.current_cycle = None
    
    async def _execute_workflow_step(self, step_name: str, cycle_id: str, params: Dict) -> Dict:
        """Execute a specific workflow step"""
        # Map step names to service tools
        step_mapping = {
            'collect_news': ('news', 'collect_news'),
            'scan_market': ('scanner', 'scan_market'),
            'detect_patterns': ('pattern', 'detect_patterns'),
            'generate_signals': ('technical', 'generate_signal'),
            'execute_trades': ('trading', 'execute_signals')
        }
        
        if step_name not in step_mapping:
            raise ValueError(f"Unknown workflow step: {step_name}")
        
        service_key, tool_name = step_mapping[step_name]
        params['cycle_id'] = cycle_id
        
        result = await self._call_service_tool(service_key, tool_name, params)
        
        if result and result.success:
            return result.data
        else:
            raise Exception(result.error if result else "Step execution failed")
    
    def _serialize_cycle(self, cycle: Optional[Dict]) -> Optional[Dict]:
        """Serialize cycle for response"""
        if not cycle:
            return None
        
        serialized = cycle.copy()
        # Convert datetime objects to ISO strings
        for field in ['start_time', 'end_time']:
            if field in serialized and isinstance(serialized[field], datetime):
                serialized[field] = serialized[field].isoformat()
        
        return serialized
    
    async def run(self):
        """Run the MCP server"""
        self.logger.info("Starting Orchestration MCP Server", port=5000)
        
        # Support both WebSocket and stdio transports
        if os.getenv('MCP_TRANSPORT', 'websocket') == 'stdio':
            transport = StdioTransport()
        else:
            transport = WebSocketTransport(port=5000)
        
        await self.server.run(transport)


if __name__ == "__main__":
    server = OrchestrationMCPServer()
    asyncio.run(server.run())
