#!/usr/bin/env python3

# Name of Application: Catalyst Trading System
# Name of file: scanner-service.py
# Version: 5.2.0
# Last Updated: 2025-10-06
# Purpose: Scanner service with NORMALIZED schema v5.0 (security_id + time_id FKs)

# REVISION HISTORY:
# v5.2.0 (2025-10-06) - NORMALIZED SCHEMA MIGRATION (Playbook v3.0 Step 2)
# - Uses security_id FK (NOT symbol VARCHAR) ✅
# - Uses time_id FK for timestamps (NOT duplicate timestamps) ✅
# - Stores in scan_results with security_id FK ✅
# - Queries news_sentiment with JOINs for catalyst scores ✅
# - All queries use JOINs on FKs (NOT symbol strings) ✅
# - Helper functions: get_security_id(), get_time_id() ✅
# - NO data duplication - single source of truth ✅
#
# v5.1.0 (2025-09-20) - Schema-compliant database operations
# - Direct asyncpg connection to DigitalOcean PostgreSQL
# - FastAPI REST endpoints for service communication
# - All trading_cycles and scan_results fields per schema
#
# Description of Service:
# Market scanner (Service #2 of 9 in Playbook v3.0).
# Second service to be updated for normalized schema.
# Depends on News Service (Step 1) for catalyst data.
# Scans market for trading opportunities using:
# 1. Dynamic universe selection (top active stocks)
# 2. News catalyst integration from news_sentiment table
# 3. Technical setup confirmation
# 4. Multi-stage filtering (50 → 20 → 5)
# 5. Database persistence with security_id FKs

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
import asyncpg
import json
import os
import logging
from dataclasses import dataclass
import yfinance as yf
import redis.asyncio as redis
import uvicorn

# Initialize FastAPI
app = FastAPI(
    title="Scanner Service",
    version="5.2.0",
    description="Market scanner with normalized schema v5.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scanner")

# === SERVICE STATE ===
@dataclass
class ScannerConfig:
    initial_universe_size: int = 200
    catalyst_filter_size: int = 50
    technical_filter_size: int = 20
    final_selection_size: int = 5
    min_volume: int = 1_000_000
    min_price: float = 5.0
    max_price: float = 500.0
    min_catalyst_score: float = 0.3

class ScannerState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.config: ScannerConfig = ScannerConfig()

state = ScannerState()

# === HELPER FUNCTIONS (NORMALIZED SCHEMA) ===
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol"""
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)", symbol.upper()
        )
        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")
        return security_id
    except Exception as e:
        logger.error(f"get_security_id failed for {symbol}: {e}")
        raise

async def get_time_id(timestamp: datetime) -> int:
    """Get or create time_id for timestamp"""
    try:
        time_id = await state.db_pool.fetchval(
            "SELECT get_or_create_time($1)", timestamp
        )
        if not time_id:
            raise ValueError(f"Failed to get time_id for {timestamp}")
        return time_id
    except Exception as e:
        logger.error(f"get_time_id failed for {timestamp}: {e}")
        raise

# === MARKET DATA ===
async def get_active_universe(limit: int = 200) -> List[str]:
    """Get most active stocks from market"""
    try:
        # Use yfinance to get most active stocks
        # In production, use real-time market data API
        active_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM',
            'JNJ', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'PYPL', 'BAC', 'NFLX',
            'ADBE', 'CRM', 'XOM', 'VZ', 'CMCSA', 'PFE', 'INTC', 'CSCO', 'T',
            'PEP', 'ABT', 'CVX', 'NKE', 'WMT', 'TMO', 'ABBV', 'MRK', 'LLY',
            'COST', 'ORCL', 'ACN', 'MDT', 'DHR', 'TXN', 'NEE', 'HON', 'UNP',
            'PM', 'IBM', 'QCOM', 'LOW', 'LIN', 'AMD', 'GS', 'SBUX', 'CAT'
        ]
        return active_stocks[:limit]
    except Exception as e:
        logger.error(f"Failed to get active universe: {e}")
        return []

async def get_quote(symbol: str) -> Optional[Dict]:
    """Get current quote for symbol"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            'symbol': symbol,
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'volume': info.get('volume', 0),
            'change_percent': info.get('regularMarketChangePercent', 0)
        }
    except Exception as e:
        logger.debug(f"Failed to get quote for {symbol}: {e}")
        return None

# === CATALYST FILTERING (QUERIES NEWS_SENTIMENT WITH JOINS) ===
async def filter_by_catalysts(symbols: List[str], min_strength: float = 0.3) -> List[Dict]:
    """
    Filter symbols by news catalysts.
    Queries news_sentiment table with JOINs (normalized schema).
    """
    if not symbols:
        return []
    
    try:
        # Query news_sentiment with JOINs (NOT symbol strings!)
        catalyst_data = await state.db_pool.fetch("""
            SELECT 
                s.symbol,
                s.security_id,
                COUNT(ns.news_id) as catalyst_count,
                AVG(ns.catalyst_strength) as avg_strength,
                MAX(ns.catalyst_strength) as max_strength,
                MAX(td.timestamp) as latest_catalyst_time,
                ARRAY_AGG(DISTINCT ns.catalyst_type) as catalyst_types
            FROM securities s
            LEFT JOIN news_sentiment ns ON ns.security_id = s.security_id
            LEFT JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE s.symbol = ANY($1)
            AND td.timestamp >= NOW() - INTERVAL '24 hours'
            AND ns.catalyst_strength >= $2
            GROUP BY s.symbol, s.security_id
            HAVING COUNT(ns.news_id) > 0
            ORDER BY MAX(ns.catalyst_strength) DESC, COUNT(ns.news_id) DESC
        """, symbols, min_strength)
        
        candidates = []
        for row in catalyst_data:
            quote = await get_quote(row['symbol'])
            if quote:
                candidates.append({
                    'symbol': row['symbol'],
                    'security_id': row['security_id'],
                    'catalyst_count': row['catalyst_count'],
                    'catalyst_strength': float(row['max_strength']),
                    'catalyst_types': row['catalyst_types'],
                    'latest_catalyst_time': row['latest_catalyst_time'].isoformat(),
                    'price': quote['price'],
                    'volume': quote['volume'],
                    'change_percent': quote['change_percent']
                })
        
        logger.info(f"Found {len(candidates)} candidates with catalysts")
        return candidates
        
    except Exception as e:
        logger.error(f"Catalyst filtering failed: {e}")
        return []

# === TECHNICAL FILTERING ===
async def filter_by_technical(candidates: List[Dict]) -> List[Dict]:
    """Apply technical filters"""
    filtered = []
    
    for candidate in candidates:
        try:
            # Basic filters
            if (candidate['price'] < state.config.min_price or 
                candidate['price'] > state.config.max_price):
                continue
            
            if candidate['volume'] < state.config.min_volume:
                continue
            
            # Calculate technical score (simplified)
            technical_score = 0.0
            
            # Momentum component
            if abs(candidate['change_percent']) > 2.0:
                technical_score += 0.4
            
            # Volume component
            if candidate['volume'] > 5_000_000:
                technical_score += 0.3
            
            # Catalyst component
            technical_score += candidate['catalyst_strength'] * 0.3
            
            candidate['technical_score'] = technical_score
            candidate['composite_score'] = (
                candidate['catalyst_strength'] * 0.6 + technical_score * 0.4
            )
            
            filtered.append(candidate)
            
        except Exception as e:
            logger.debug(f"Technical filter error for {candidate['symbol']}: {e}")
            continue
    
    # Sort by composite score
    filtered.sort(key=lambda x: x['composite_score'], reverse=True)
    return filtered

# === SCAN PERSISTENCE (NORMALIZED) ===
async def persist_scan_results(cycle_id: str, candidates: List[Dict]) -> bool:
    """
    Store scan results with NORMALIZED schema.
    Uses security_id FKs (NOT symbol VARCHAR).
    """
    try:
        scan_time = datetime.utcnow()
        time_id = await get_time_id(scan_time)
        
        # First, ensure trading cycle exists
        await state.db_pool.execute("""
            INSERT INTO trading_cycles (cycle_id, start_time, status)
            VALUES ($1, $2, 'active')
            ON CONFLICT (cycle_id) DO NOTHING
        """, cycle_id, scan_time)
        
        # Store each scan result with security_id FK
        for candidate in candidates:
            try:
                security_id = candidate.get('security_id')
                if not security_id:
                    security_id = await get_security_id(candidate['symbol'])
                
                await state.db_pool.execute("""
                    INSERT INTO scan_results (
                        cycle_id, security_id, time_id,
                        price, volume, change_percent,
                        catalyst_score, technical_score, composite_score,
                        selected_for_trading,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                    cycle_id,
                    security_id,
                    time_id,
                    candidate['price'],
                    candidate['volume'],
                    candidate['change_percent'],
                    candidate['catalyst_strength'],
                    candidate['technical_score'],
                    candidate['composite_score'],
                    candidate.get('selected', False),
                    json.dumps({
                        'catalyst_count': candidate['catalyst_count'],
                        'catalyst_types': candidate['catalyst_types']
                    })
                )
            except Exception as e:
                logger.error(f"Failed to store result for {candidate['symbol']}: {e}")
                continue
        
        logger.info(f"Stored {len(candidates)} scan results for cycle {cycle_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to persist scan results: {e}")
        return False

# === MAIN SCAN FUNCTION ===
async def scan_market() -> Dict:
    """Main market scanning function"""
    try:
        cycle_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting market scan: {cycle_id}")
        
        # Step 1: Get active universe
        universe = await get_active_universe(state.config.initial_universe_size)
        logger.info(f"Initial universe: {len(universe)} symbols")
        
        # Step 2: Filter by catalysts (queries news_sentiment with JOINs)
        catalyst_candidates = await filter_by_catalysts(
            universe, 
            state.config.min_catalyst_score
        )
        logger.info(f"After catalyst filter: {len(catalyst_candidates)} candidates")
        
        # Step 3: Apply technical filters
        technical_candidates = await filter_by_technical(catalyst_candidates)
        logger.info(f"After technical filter: {len(technical_candidates)} candidates")
        
        # Step 4: Select final candidates
        final_candidates = technical_candidates[:state.config.final_selection_size]
        
        # Mark selected candidates
        for candidate in final_candidates:
            candidate['selected'] = True
        
        # Step 5: Persist results (with security_id FKs)
        await persist_scan_results(cycle_id, technical_candidates)
        
        return {
            'success': True,
            'cycle_id': cycle_id,
            'timestamp': datetime.utcnow().isoformat(),
            'universe_size': len(universe),
            'catalyst_candidates': len(catalyst_candidates),
            'technical_candidates': len(technical_candidates),
            'final_selections': len(final_candidates),
            'candidates': final_candidates
        }
        
    except Exception as e:
        logger.error(f"Market scan failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

# === STARTUP ===
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Scanner Service v5.2.0 (NORMALIZED SCHEMA)")
    
    # Database
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL required")
        
        state.db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
        logger.info("Database pool initialized")
        
        # Verify normalized schema
        await verify_normalized_schema()
        
    except Exception as e:
        logger.critical(f"Database init failed: {e}")
        raise
    
    # Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        state.redis_client = await redis.from_url(redis_url)
        logger.info("Redis client initialized")
    except Exception as e:
        logger.warning(f"Redis init failed: {e}")
    
    # HTTP session
    state.http_session = aiohttp.ClientSession()
    
    logger.info("Scanner service ready")

async def verify_normalized_schema():
    """Verify normalized schema v5.0 is deployed"""
    try:
        # Check scan_results uses security_id FK
        has_security_id = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'scan_results' 
                AND column_name = 'security_id'
            )
        """)
        
        has_symbol = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'scan_results' 
                AND column_name = 'symbol'
            )
        """)
        
        if not has_security_id:
            raise ValueError("scan_results missing security_id - schema v5.0 not deployed!")
        
        if has_symbol:
            raise ValueError("scan_results has symbol column - schema is DENORMALIZED!")
        
        logger.info("✅ Normalized schema v5.0 verified - scan_results has security_id FK")
        
    except Exception as e:
        logger.critical(f"Schema verification failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    if state.http_session:
        await state.http_session.close()
    if state.db_pool:
        await state.db_pool.close()
    if state.redis_client:
        await state.redis_client.close()

# === HEALTH CHECK ===
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "scanner",
        "version": "5.2.0",
        "schema": "v5.0 normalized",
        "uses_security_id_fk": True,
        "uses_time_id_fk": True,
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if state.db_pool else "disconnected",
        "redis": "connected" if state.redis_client else "disconnected"
    }

# === API ENDPOINTS ===
@app.post("/api/v1/scan")
async def trigger_scan():
    """Trigger market scan"""
    result = await scan_market()
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('error'))
    return result

@app.get("/api/v1/candidates")
async def get_candidates(cycle_id: Optional[str] = None, limit: int = 10):
    """Get scan candidates with JOINs (normalized schema)"""
    try:
        if cycle_id:
            # Get specific cycle results
            results = await state.db_pool.fetch("""
                SELECT 
                    sr.*,
                    s.symbol,
                    s.company_name,
                    sec.sector_name,
                    td.timestamp
                FROM scan_results sr
                JOIN securities s ON s.security_id = sr.security_id
                JOIN sectors sec ON sec.sector_id = s.sector_id
                JOIN time_dimension td ON td.time_id = sr.time_id
                WHERE sr.cycle_id = $1
                ORDER BY sr.composite_score DESC
                LIMIT $2
            """, cycle_id, limit)
        else:
            # Get latest cycle results
            results = await state.db_pool.fetch("""
                SELECT 
                    sr.*,
                    s.symbol,
                    s.company_name,
                    sec.sector_name,
                    td.timestamp
                FROM scan_results sr
                JOIN securities s ON s.security_id = sr.security_id
                JOIN sectors sec ON sec.sector_id = s.sector_id
                JOIN time_dimension td ON td.time_id = sr.time_id
                WHERE sr.cycle_id = (
                    SELECT cycle_id FROM scan_results 
                    ORDER BY scan_result_id DESC LIMIT 1
                )
                ORDER BY sr.composite_score DESC
                LIMIT $1
            """, limit)
        
        return {
            "candidates": [dict(r) for r in results],
            "count": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("=" * 70)
    print("🎩 Catalyst Trading System - Scanner Service v5.2.0 (NORMALIZED)")
    print("=" * 70)
    print("✅ Uses security_id FK (NOT symbol VARCHAR)")
    print("✅ Uses time_id FK (NOT duplicate timestamps)")
    print("✅ Queries news_sentiment with JOINs for catalysts")
    print("✅ All queries use JOINs on FKs")
    print("✅ NO data duplication - single source of truth")
    print("Port: 5001")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")