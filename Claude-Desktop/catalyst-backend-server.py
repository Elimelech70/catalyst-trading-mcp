#!/usr/bin/env python3
"""
Catalyst Trading Dashboard Server
Provides WebSocket and REST API for the trading dashboard
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import aiohttp
from aiohttp import web
import aiohttp_cors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradingDataManager:
    """Manages trading data and state"""
    
    def __init__(self):
        self.trades = []
        self.portfolio = {
            'balance': 10000.0,
            'positions': {},
            'daily_pnl': 0.0,
            'total_pnl': 0.0
        }
        self.market_data = {}
        self.system_status = {
            'trading_active': True,
            'connected': True,
            'latency': 0,
            'messages_per_sec': 0,
            'uptime': datetime.now()
        }
        self.logs = []
        
    def add_trade(self, trade: Dict):
        """Add a new trade"""
        trade['timestamp'] = datetime.now().isoformat()
        trade['id'] = len(self.trades) + 1
        self.trades.append(trade)
        self.add_log(f"Trade executed: {trade['pair']} {trade['type']} {trade['amount']} @ {trade['price']}", 'INFO')
        return trade
    
    def add_log(self, message: str, level: str = 'INFO'):
        """Add a log entry"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        self.logs.append(log_entry)
        # Keep only last 100 logs
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]
        return log_entry
    
    def get_dashboard_data(self) -> Dict:
        """Get complete dashboard data"""
        return {
            'portfolio': self.portfolio,
            'recent_trades': self.trades[-20:] if self.trades else [],
            'system_status': {
                **self.system_status,
                'uptime_seconds': (datetime.now() - self.system_status['uptime']).total_seconds()
            },
            'logs': self.logs[-20:],
            'market_data': self.market_data
        }
    
    def generate_ml_dataset(self) -> Dict:
        """Generate dataset for ML training"""
        dataset = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_trades': len(self.trades),
                'date_range': {
                    'start': self.trades[0]['timestamp'] if self.trades else None,
                    'end': self.trades[-1]['timestamp'] if self.trades else None
                }
            },
            'features': [],
            'labels': []
        }
        
        # Process trades for ML features
        for i, trade in enumerate(self.trades):
            if i > 0:
                # Calculate features based on previous trades
                feature = {
                    'price_change': float(trade.get('price', 0)) - float(self.trades[i-1].get('price', 0)),
                    'volume': float(trade.get('amount', 0)),
                    'trade_type': 1 if trade.get('type') == 'BUY' else 0,
                    'time_since_last': (
                        datetime.fromisoformat(trade['timestamp']) - 
                        datetime.fromisoformat(self.trades[i-1]['timestamp'])
                    ).total_seconds()
                }
                dataset['features'].append(feature)
                
                # Label could be profit/loss of next trade
                if i < len(self.trades) - 1:
                    dataset['labels'].append(float(trade.get('pnl', 0)) > 0)
        
        return dataset

class CatalystServer:
    """Main server for the Catalyst Trading Dashboard"""
    
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.data_manager = TradingDataManager()
        self.websockets = set()
        self.setup_routes()
        self.setup_cors()
        
    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/dashboard', self.handle_dashboard)
        self.app.router.add_get('/api/trades', self.handle_trades)
        self.app.router.add_post('/api/trade', self.handle_new_trade)
        self.app.router.add_get('/api/logs', self.handle_logs)
        self.app.router.add_get('/api/ml-data', self.handle_ml_data)
        self.app.router.add_post('/api/control', self.handle_control)
        self.app.router.add_get('/ws', self.websocket_handler)
        
    def setup_cors(self):
        """Setup CORS for cross-origin requests"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        for route in list(self.app.router.routes()):
            cors.add(route)
    
    async def handle_index(self, request):
        """Serve the dashboard HTML"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Catalyst Trading Dashboard</title></head>
        <body>
            <h1>Catalyst Trading Dashboard Server</h1>
            <p>API is running. Connect your dashboard to this server.</p>
            <ul>
                <li>WebSocket: ws://localhost:8080/ws</li>
                <li>Dashboard Data: http://localhost:8080/api/dashboard</li>
                <li>Trades: http://localhost:8080/api/trades</li>
                <li>Logs: http://localhost:8080/api/logs</li>
            </ul>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type='text/html')
    
    async def handle_dashboard(self, request):
        """Get dashboard data"""
        data = self.data_manager.get_dashboard_data()
        return web.json_response(data)
    
    async def handle_trades(self, request):
        """Get trades list"""
        limit = int(request.rel_url.query.get('limit', 20))
        trades = self.data_manager.trades[-limit:]
        return web.json_response({'trades': trades})
    
    async def handle_new_trade(self, request):
        """Handle new trade submission"""
        data = await request.json()
        trade = self.data_manager.add_trade(data)
        
        # Broadcast to WebSocket clients
        await self.broadcast_update('new_trade', trade)
        
        return web.json_response({'success': True, 'trade': trade})
    
    async def handle_logs(self, request):
        """Get system logs"""
        limit = int(request.rel_url.query.get('limit', 50))
        logs = self.data_manager.logs[-limit:]
        return web.json_response({'logs': logs})
    
    async def handle_ml_data(self, request):
        """Generate and return ML dataset"""
        dataset = self.data_manager.generate_ml_dataset()
        return web.json_response(dataset)
    
    async def handle_control(self, request):
        """Handle control commands (pause/resume/stop)"""
        data = await request.json()
        command = data.get('command')
        
        if command == 'pause':
            self.data_manager.system_status['trading_active'] = False
            self.data_manager.add_log('Trading paused by user', 'WARN')
        elif command == 'resume':
            self.data_manager.system_status['trading_active'] = True
            self.data_manager.add_log('Trading resumed by user', 'INFO')
        elif command == 'emergency_stop':
            self.data_manager.system_status['trading_active'] = False
            self.data_manager.add_log('EMERGENCY STOP activated', 'ERROR')
            # Close all positions logic here
        
        await self.broadcast_update('status_change', self.data_manager.system_status)
        
        return web.json_response({'success': True, 'status': self.data_manager.system_status})
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.websockets.add(ws)
        
        try:
            # Send initial data
            await ws.send_json({
                'type': 'connected',
                'data': self.data_manager.get_dashboard_data()
            })
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    # Handle incoming WebSocket messages
                    if data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong'})
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    
        except Exception as e:
            logger.error(f'WebSocket handler error: {e}')
        finally:
            self.websockets.remove(ws)
            
        return ws
    
    async def broadcast_update(self, update_type: str, data: Any):
        """Broadcast update to all WebSocket clients"""
        message = json.dumps({
            'type': update_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
        for ws in self.websockets:
            try:
                await ws.send_str(message)
            except Exception as e:
                logger.error(f'Error broadcasting to websocket: {e}')
    
    async def simulate_trading(self):
        """Simulate trading activity for testing"""
        pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT']
        
        while True:
            await asyncio.sleep(5)  # Generate activity every 5 seconds
            
            # Simulate a trade
            import random
            trade = {
                'pair': random.choice(pairs),
                'type': random.choice(['BUY', 'SELL']),
                'amount': round(random.uniform(0.01, 1.0), 4),
                'price': round(random.uniform(100, 70000), 2),
                'pnl': round(random.uniform(-100, 200), 2)
            }
            
            self.data_manager.add_trade(trade)
            await self.broadcast_update('new_trade', trade)
            
            # Update system metrics
            self.data_manager.system_status['latency'] = random.randint(5, 50)
            self.data_manager.system_status['messages_per_sec'] = random.randint(100, 500)
            
    def run(self):
        """Start the server"""
        logger.info(f"Starting Catalyst Trading Dashboard Server on {self.host}:{self.port}")
        
        # Start background tasks
        asyncio.ensure_future(self.simulate_trading())
        
        # Run the web server
        web.run_app(self.app, host=self.host, port=self.port)

def main():
    """Main entry point"""
    server = CatalystServer(
        host=os.getenv('HOST', 'localhost'),
        port=int(os.getenv('PORT', 8080))
    )
    server.run()

if __name__ == '__main__':
    main()
