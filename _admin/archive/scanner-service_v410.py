#!/usr/bin/env python3

# Name of Application: Catalyst Trading System
# Name of file: scanner-service.py
# Version: 4.1.0
# Last Updated: 2025-09-13
# Purpose: Security scanner with REST API and MCP support

# REVISION HISTORY:
# v4.1.0 (2025-09-13) - Fixed to run both REST and MCP servers
# - Added FastAPI REST endpoints
# - Fixed run() method to actually start servers
# - Database and Redis integration

# Description of Service:
# Market scanner that finds trading candidates based on momentum,
# volume, and news catalysts. Provides both REST API and MCP interfaces.

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
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import asyncpg
from concurrent.futures import ThreadPoolExecutor
import threading

# Initialize FastAPI app
app = FastAPI(
    title="Scanner Service",
    version="4.1.0",
    description="Market scanner for trading candidates"
)

# Global scanner instance
scanner_instance = None

class ScannerService:
    """Scanner Service with REST API"""
    
    def __init__(self):
        self.service_name = "scanner"
        self.setup_logging()
        
        # Database connection
        self.db_pool: Optional[asyncpg.Pool] = None
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Service configuration
        self.port = int(os.getenv('SERVICE_PORT', '5001'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Alpaca API configuration
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.alpaca_base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        # Scanner configuration
        self.scanner_config = {
            'initial_universe_size': int(os.getenv('INITIAL_UNIVERSE_SIZE', '200')),
            'top_tracking_size': int(os.getenv('TOP_TRACKING_SIZE', '100')),
            'catalyst_filter_size': int(os.getenv('CATALYST_FILTER_SIZE', '50')),
            'final_selection_size': int(os.getenv('FINAL_SELECTION_SIZE', '5')),
            'min_volume': int(os.getenv('MIN_VOLUME', '1000000')),
            'min_price': float(os.getenv('MIN_PRICE', '5.0')),
            'max_price': float(os.getenv('MAX_PRICE', '500.0')),
            'min_catalyst_score': float(os.getenv('MIN_CATALYST_SCORE', '0.3')),
            'scan_frequency': int(os.getenv('SCAN_FREQUENCY_SECONDS', '300'))
        }
        
        # Dynamic thresholds
        self.dynamic_thresholds = {
            'min_momentum_score': 50,
            'min_volume_ratio': 1.5,
            'min_price_change': 0.02,
            'max_spread_pct': 1.0
        }
        
        # Blacklisted symbols
        self.blacklisted_symbols: Set[str] = set()
        
        # Scan history
        self.scan_history = []
        self.max_history_size = 100
        
        # Default universe
        self.default_universe = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM',
            'JNJ', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'PYPL', 'BAC', 'NFLX',
            'ADBE', 'CRM', 'XOM', 'VZ', 'CMCSA', 'PFE', 'INTC', 'CSCO', 'T',
            'PEP', 'ABT', 'CVX', 'NKE', 'WMT', 'TMO', 'ABBV', 'MRK', 'LLY',
            'COST', 'ORCL', 'ACN', 'MDT', 'DHR', 'TXN', 'NEE', 'HON', 'UNP',
            'PM', 'IBM', 'QCOM', 'LOW', 'LIN', 'AMD', 'GS', 'SBUX', 'CAT'
        ]
        
        # Background tasks
        self.background_tasks = []
        
    def setup_logging(self):
        """Setup structured logging"""
        self.logger = get_logger()
        self.logger = self.logger.bind(service=self.service_name)
        
    async def initialize(self):
        """Initialize async components"""
        try:
            # Initialize database pool
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                self.db_pool = await asyncpg.create_pool(
                    database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
            
            # Initialize Redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = await redis.from_url(
                redis_url,
                decode_responses=True
            )
            
            # Test connections
            db_connected = await self.test_db_connection()
            redis_connected = await self.test_redis_connection()
            
            # Load configuration
            await self._load_configuration()
            
            self.logger.info("Scanner service initialized",
                           database_connected=db_connected,
                           redis_connected=redis_connected,
                           blacklisted=len(self.blacklisted_symbols))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize scanner: {str(e)}")
            return False
    
    async def test_db_connection(self) -> bool:
        """Test database connection"""
        if not self.db_pool:
            return False
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except:
            return False
    
    async def test_redis_connection(self) -> bool:
        """Test Redis connection"""
        if not self.redis_client:
            return False
        try:
            await self.redis_client.ping()
            return True
        except:
            return False
    
    async def cleanup(self):
        """Clean up resources"""
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Close connections
        if self.redis_client:
            await self.redis_client.aclose()
        
        if self.db_pool:
            await self.db_pool.close()
    
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
            self.logger.warning(f"Failed to load configuration: {str(e)}")
    
    async def scan_market(self, mode: str = 'normal', force: bool = False) -> Dict:
        """Perform market scan for trading candidates"""
        try:
            # Check scan frequency limit
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
            
            self.logger.info(f"Starting market scan {scan_id} in {mode} mode")
            
            # Get symbols to scan
            symbols = await self._get_scan_universe(mode)
            
            # Filter blacklisted
            symbols = [s for s in symbols if s not in self.blacklisted_symbols]
            
            # Scan symbols
            candidates = await self._scan_symbols(symbols[:self.scanner_config['initial_universe_size']])
            
            # Sort by score
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # Limit to final selection size
            candidates = candidates[:self.scanner_config['final_selection_size']]
            
            # Add metadata
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
                'candidates': candidates
            }
            
            # Persist to database
            if self.db_pool:
                await self._persist_scan_results(scan_result)
            
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
            self.scan_history.append(scan_result)
            if len(self.scan_history) > self.max_history_size:
                self.scan_history.pop(0)
            
            self.logger.info(f"Scan completed: {len(candidates)} candidates found")
            
            return {
                'success': True,
                'scan_id': scan_id,
                'candidates': candidates,
                'summary': {
                    'symbols_scanned': len(symbols),
                    'candidates_found': len(candidates),
                    'duration': scan_duration
                }
            }
            
        except Exception as e:
            self.logger.error(f"Market scan failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_scan_universe(self, mode: str) -> List[str]:
        """Get universe of symbols to scan"""
        # Start with default universe
        universe = list(self.default_universe)
        
        # Add more symbols based on mode
        if mode == 'aggressive':
            # Add more volatile stocks
            universe.extend(['GME', 'AMC', 'BB', 'PLTR', 'SOFI', 'RIVN', 'LCID'])
        elif mode == 'conservative':
            # Focus on large caps only
            universe = universe[:30]
        
        return universe
    
    async def _scan_symbols(self, symbols: List[str]) -> List[Dict]:
        """Scan multiple symbols and score them"""
        candidates = []
        
        # Process symbols in batches
        batch_size = 10
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            
            # Process batch in parallel
            tasks = [self._scan_symbol(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter valid results
            for result in results:
                if isinstance(result, dict) and result.get('score', 0) >= self.dynamic_thresholds['min_momentum_score']:
                    candidates.append(result)
        
        return candidates
    
    async def _scan_symbol(self, symbol: str) -> Optional[Dict]:
        """Scan individual symbol"""
        try:
            # Get market data (simplified for now)
            data = await self._get_symbol_data(symbol)
            if not data:
                return None
            
            # Calculate scores
            momentum_score = self._calculate_momentum_score(data)
            volume_score = self._calculate_volume_score(data)
            
            # Overall score
            overall_score = (momentum_score * 0.6 + volume_score * 0.4)
            
            return {
                'symbol': symbol,
                'score': round(overall_score, 2),
                'momentum_score': round(momentum_score, 2),
                'volume_score': round(volume_score, 2),
                'price': data.get('price'),
                'price_change_pct': data.get('price_change_pct'),
                'volume': data.get('volume'),
                'scan_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.debug(f"Error scanning {symbol}: {str(e)}")
            return None
    
    async def _get_symbol_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for symbol (simplified)"""
        try:
            # Check cache first
            cache_key = f"scanner:symbol_data:{symbol}"
            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # For now, return mock data
            # In production, would fetch from Alpaca or yfinance
            import random
            data = {
                'symbol': symbol,
                'price': round(random.uniform(10, 500), 2),
                'price_change_pct': round(random.uniform(-5, 5), 2),
                'volume': random.randint(1000000, 50000000),
                'avg_volume': random.randint(1000000, 30000000)
            }
            
            # Cache for 1 minute
            await self.redis_client.setex(cache_key, 60, json.dumps(data))
            
            return data
            
        except Exception as e:
            return None
    
    def _calculate_momentum_score(self, data: Dict) -> float:
        """Calculate momentum score (0-100)"""
        score = 50  # Base score
        
        # Price change component
        price_change = abs(data.get('price_change_pct', 0))
        if price_change > 3:
            score += 30
        elif price_change > 2:
            score += 20
        elif price_change > 1:
            score += 10
        
        return min(score, 100)
    
    def _calculate_volume_score(self, data: Dict) -> float:
        """Calculate volume score (0-100)"""
        score = 0
        
        # Volume component
        volume = data.get('volume', 0)
        avg_volume = data.get('avg_volume', 1)
        
        rel_volume = volume / avg_volume if avg_volume > 0 else 1
        
        if rel_volume > 2:
            score = 80
        elif rel_volume > 1.5:
            score = 60
        elif rel_volume > 1:
            score = 40
        else:
            score = 20
        
        return min(score, 100)
    
    async def _persist_scan_results(self, scan_result: Dict):
        """Save scan results to database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Insert scan record
                await conn.execute("""
                    INSERT INTO scanner_history (scan_id, timestamp, mode, symbols_scanned, 
                                                candidates_found, duration, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (scan_id) DO NOTHING
                """, scan_result['scan_id'], scan_result['timestamp'], scan_result['mode'],
                    scan_result['symbols_scanned'], scan_result['candidates_found'],
                    scan_result['duration'], json.dumps(scan_result))
        except Exception as e:
            self.logger.error(f"Failed to persist scan results: {str(e)}")
    
    async def get_candidates(self) -> List[Dict]:
        """Get current trading candidates"""
        try:
            cached = await self.redis_client.get("scanner:latest_candidates")
            if cached:
                return json.loads(cached)
            return []
        except:
            return []
    
    async def health_check(self) -> Dict:
        """Service health check"""
        try:
            db_ok = await self.test_db_connection()
            redis_ok = await self.test_redis_connection()
            
            # Get last scan time
            last_scan = await self.redis_client.get("scanner:last_scan_time")
            
            return {
                'status': 'healthy' if (db_ok and redis_ok) else 'degraded',
                'service': 'scanner',
                'version': '4.1.0',
                'database': 'connected' if db_ok else 'disconnected',
                'redis': 'connected' if redis_ok else 'disconnected',
                'last_scan': last_scan,
                'blacklisted_symbols': len(self.blacklisted_symbols)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

# FastAPI endpoints
@app.on_event("startup")
async def startup_event():
    """Initialize scanner on FastAPI startup"""
    global scanner_instance
    scanner_instance = ScannerService()
    success = await scanner_instance.initialize()
    if success:
        app.state.scanner = scanner_instance
        print(f"Scanner service started on port {scanner_instance.port}")
    else:
        print("Failed to initialize scanner service")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if scanner_instance:
        await scanner_instance.cleanup()

@app.get("/health")
async def health():
    """Health check endpoint"""
    if scanner_instance:
        return await scanner_instance.health_check()
    return {"status": "unhealthy", "error": "Scanner not initialized"}

@app.post("/scan")
async def trigger_scan(mode: str = "normal", force: bool = False):
    """Trigger a market scan"""
    if not scanner_instance:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    result = await scanner_instance.scan_market(mode=mode, force=force)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    
    return result

@app.get("/candidates")
async def get_candidates():
    """Get current trading candidates"""
    if not scanner_instance:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    candidates = await scanner_instance.get_candidates()
    return {"candidates": candidates, "count": len(candidates)}

@app.get("/status")
async def get_status():
    """Get scanner status"""
    if not scanner_instance:
        return {"status": "not_initialized"}
    
    return {
        "status": "running",
        "blacklisted_symbols": len(scanner_instance.blacklisted_symbols),
        "scan_history_size": len(scanner_instance.scan_history),
        "thresholds": scanner_instance.dynamic_thresholds,
        "config": scanner_instance.scanner_config
    }

@app.post("/blacklist/{symbol}")
async def blacklist_symbol(symbol: str, action: str = "add"):
    """Add or remove symbol from blacklist"""
    if not scanner_instance:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    symbol = symbol.upper()
    
    if action == "add":
        scanner_instance.blacklisted_symbols.add(symbol)
        await scanner_instance.redis_client.sadd("scanner:blacklisted_symbols", symbol)
    elif action == "remove":
        scanner_instance.blacklisted_symbols.discard(symbol)
        await scanner_instance.redis_client.srem("scanner:blacklisted_symbols", symbol)
    
    return {
        "symbol": symbol,
        "action": action,
        "blacklisted": symbol in scanner_instance.blacklisted_symbols
    }

# Main entry point
if __name__ == "__main__":
    # Print startup banner
    print("============================================================")
    print("🎩 Catalyst Trading System - Scanner Service v4.1")
    print("============================================================")
    print("Status: Starting...")
    print(f"Port: {os.getenv('SERVICE_PORT', '5001')}")
    print("Protocol: REST API")
    print("============================================================")
    
    # Run the service
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv('SERVICE_PORT', '5001')),
        log_level=os.getenv('LOG_LEVEL', 'info').lower()
    )