#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: scanner-service.py
Version: 5.1.0
Last Updated: 2025-09-20
Purpose: Scanner service with REST API and direct database persistence following v4.1 schema

REVISION HISTORY:
v5.1.0 (2025-09-20) - Schema-compliant database operations
- Updated persist_scan_results() to follow database-schema-mcp-v41.md exactly
- Updated score_candidate() to return all required schema fields
- Proper cycle_id generation as VARCHAR(20)
- All trading_cycles and scan_results fields per schema

v5.0.0 (2025-09-19) - REST API architecture with direct DB
- Removed MCP database client dependency
- Direct asyncpg connection to DigitalOcean PostgreSQL
- FastAPI REST endpoints for service communication
- Fixed data persistence issue
- Proper health checks

Description of Service:
Market scanner that identifies trading opportunities using REST API
for inter-service communication and direct database persistence.
Schema-compliant operations for v4.1 database structure.
"""

import os
import asyncio
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import logging
import alpaca_trade_api as tradeapi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("scanner-service")

# FastAPI app
app = FastAPI(
    title="Scanner Service",
    version="5.1.0",
    description="Market scanner with REST API - Schema v4.1 compliant"
)

# Global connections
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
alpaca_client: Optional[tradeapi.REST] = None

# Configuration
SCAN_CONFIG = {
    'initial_universe_size': int(os.getenv('INITIAL_UNIVERSE_SIZE', '200')),
    'top_tracking_size': int(os.getenv('TOP_TRACKING_SIZE', '100')),
    'catalyst_filter_size': int(os.getenv('CATALYST_FILTER_SIZE', '50')),
    'final_selection_size': int(os.getenv('FINAL_SELECTION_SIZE', '5')),
    'scan_frequency': int(os.getenv('SCAN_FREQUENCY', '300'))  # 5 minutes
}

# ========== PYDANTIC MODELS ==========

class ScanRequest(BaseModel):
    mode: str = "normal"
    max_candidates: int = 5
    news_context: Optional[Dict] = None
    symbols: Optional[List[str]] = None

class ScanResult(BaseModel):
    scan_id: str
    timestamp: str
    mode: str
    candidates_found: int
    candidates: List[Dict]
    metadata: Dict

class CandidateScore(BaseModel):
    symbol: str
    momentum_score: float
    volume_score: float
    catalyst_score: float
    composite_score: float
    metadata: Dict

# ========== DATABASE CONNECTION ==========

async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global db_pool
    if not db_pool:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        logger.info("Creating database connection pool...")
        try:
            db_pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                command_timeout=60
            )
            
            # Test connection
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {str(e)}")
            raise
    return db_pool

# ========== STARTUP/SHUTDOWN ==========

@app.on_event("startup")
async def startup():
    """Initialize connections on startup"""
    global redis_client, alpaca_client
    
    try:
        # Initialize database pool
        await get_db_pool()
        
        # Initialize Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected")
        
        # Initialize Alpaca
        alpaca_client = tradeapi.REST(
            key_id=os.getenv('ALPACA_API_KEY'),
            secret_key=os.getenv('ALPACA_SECRET_KEY'),
            base_url=os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        )
        logger.info("Alpaca client initialized")
        
        # Ensure database tables exist
        await ensure_tables_exist()
        
        logger.info("Scanner service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start scanner service: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Clean up connections"""
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

# ========== REST API ENDPOINTS ==========

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        health_status = {
            "status": "healthy",
            "service": "scanner",
            "version": "5.1.0",
            "timestamp": datetime.now().isoformat()
        }
        
        # Check database
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health_status["database"] = "connected"
        except:
            health_status["database"] = "disconnected"
            health_status["status"] = "degraded"
        
        # Check Redis
        try:
            await redis_client.ping()
            health_status["redis"] = "connected"
        except:
            health_status["redis"] = "disconnected"
            health_status["status"] = "degraded"
        
        # Check Alpaca
        try:
            account = alpaca_client.get_account()
            health_status["alpaca"] = "connected"
            health_status["market_status"] = "open" if account.trading_blocked == False else "closed"
        except:
            health_status["alpaca"] = "disconnected"
            health_status["status"] = "degraded"
        
        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(content=health_status, status_code=status_code)
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/api/v1/scan", response_model=ScanResult)
async def perform_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Perform market scan and persist results"""
    try:
        scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        scan_timestamp = datetime.now()
        
        logger.info(f"Starting scan {scan_id} in {request.mode} mode")
        
        # Get market movers
        symbols = await get_market_movers(request.mode)
        
        # Score candidates
        candidates = []
        rank = 1
        for symbol in symbols[:request.max_candidates * 2]:  # Get more to filter
            score = await score_candidate(symbol, request.news_context)
            if score['composite_score'] > 50:  # Minimum threshold
                score['rank'] = rank
                candidates.append(score)
                rank += 1
        
        # Sort by composite score
        candidates.sort(key=lambda x: x['composite_score'], reverse=True)
        candidates = candidates[:request.max_candidates]
        
        # Update ranks after sorting
        for i, candidate in enumerate(candidates):
            candidate['rank'] = i + 1
        
        # Prepare scan result
        scan_result = {
            'scan_id': scan_id,
            'timestamp': scan_timestamp,
            'mode': request.mode,
            'candidates': candidates,
            'metadata': {
                'symbols_scanned': len(symbols),
                'candidates_found': len(candidates)
            }
        }
        
        # Persist in background
        background_tasks.add_task(persist_scan_results, scan_result)
        
        # Cache latest candidates
        await redis_client.setex(
            "scanner:latest_candidates",
            SCAN_CONFIG['scan_frequency'],
            json.dumps(candidates)
        )
        
        logger.info(f"Scan {scan_id} completed: {len(candidates)} candidates found")
        
        return ScanResult(
            scan_id=scan_id,
            timestamp=scan_timestamp.isoformat(),
            mode=request.mode,
            candidates_found=len(candidates),
            candidates=candidates,
            metadata=scan_result['metadata']
        )
        
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/candidates")
async def get_current_candidates():
    """Get current trading candidates"""
    try:
        # Try cache first
        cached = await redis_client.get("scanner:latest_candidates")
        if cached:
            return json.loads(cached)
        
        # Get from database
        async with db_pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT DISTINCT ON (symbol) 
                    symbol, momentum_score, catalyst_score, 
                    pattern_score, technical_score, composite_score, 
                    price, volume, change_percent
                FROM scan_results
                WHERE scan_time > NOW() - INTERVAL '1 hour'
                ORDER BY symbol, scan_time DESC
                LIMIT 5
            """)
            
            candidates = [dict(r) for r in results]
            return candidates
            
    except Exception as e:
        logger.error(f"Failed to get candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/scan/{scan_id}")
async def get_scan_results(scan_id: str):
    """Get specific scan results"""
    try:
        async with db_pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT * FROM scan_results
                WHERE scan_id = $1
                ORDER BY composite_score DESC
            """, scan_id)
            
            if not results:
                raise HTTPException(status_code=404, detail="Scan not found")
            
            return [dict(r) for r in results]
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== SCANNING LOGIC ==========

async def get_market_movers(mode: str) -> List[str]:
    """Get market movers from Alpaca"""
    try:
        if mode == "premarket":
            # Get pre-market movers
            assets = alpaca_client.list_assets(status='active', asset_class='us_equity')
            return [a.symbol for a in assets if a.tradable][:SCAN_CONFIG['initial_universe_size']]
        else:
            # Get most active stocks
            bars = alpaca_client.get_bars(
                ['SPY'],  # Use SPY as proxy for market
                timeframe='1Day',
                limit=1
            )
            
            # Get top volume stocks (simplified)
            assets = alpaca_client.list_assets(status='active', asset_class='us_equity')
            tradable = [a.symbol for a in assets if a.tradable and a.marginable]
            return tradable[:SCAN_CONFIG['initial_universe_size']]
            
    except Exception as e:
        logger.error(f"Failed to get market movers: {str(e)}")
        return []

async def score_candidate(symbol: str, news_context: Optional[Dict]) -> Dict:
    """
    Score a candidate following the v4.1 schema scoring fields
    Returns all score fields required by the schema
    """
    try:
        # Get latest price data
        bars = alpaca_client.get_bars(
            symbol,
            timeframe='1Day',
            limit=20
        )
        
        if not bars or len(bars) == 0:
            return {
                'symbol': symbol,
                'price': 0,
                'volume': 0,
                'momentum_score': 0,
                'catalyst_score': 0,
                'pattern_score': 0,
                'technical_score': 0,
                'composite_score': 0  # Will be calculated by DB as GENERATED column
            }
        
        latest_bar = bars[-1]
        
        # Calculate momentum score (0-100 scale as per schema)
        price_change = ((latest_bar.c - bars[0].c) / bars[0].c) * 100
        momentum_score = min(100, max(0, 50 + (price_change * 2)))
        
        # Calculate volume score for technical_score
        avg_volume = sum(b.v for b in bars[:-1]) / len(bars[:-1]) if len(bars) > 1 else 1
        volume_ratio = latest_bar.v / avg_volume if avg_volume > 0 else 1
        technical_score = min(100, volume_ratio * 30)
        
        # Calculate catalyst score (with news if available)
        catalyst_score = 50  # Base score
        if news_context and symbol in news_context:
            catalyst_score = min(100, catalyst_score + 25)  # Boost for news
        
        # Pattern score (simplified - would integrate pattern detection service)
        pattern_score = 50  # Default, would come from pattern service
        
        # Composite score will be calculated by database GENERATED column
        # total_score = (momentum * 0.3 + catalyst * 0.3 + pattern * 0.2 + technical * 0.2)
        composite_score = (
            momentum_score * 0.3 + 
            catalyst_score * 0.3 + 
            pattern_score * 0.2 + 
            technical_score * 0.2
        )
        
        return {
            'symbol': symbol,
            'price': float(latest_bar.c),
            'volume': int(latest_bar.v),
            'price_change_pct': round(price_change, 2),
            'momentum_score': round(momentum_score, 2),
            'catalyst_score': round(catalyst_score, 2),
            'pattern_score': round(pattern_score, 2),
            'technical_score': round(technical_score, 2),
            'composite_score': round(composite_score, 2),
            'catalysts': [],  # Would be populated from news service
            'patterns': [],   # Would be populated from pattern service
            'signals': {}     # Would be populated from technical service
        }
        
    except Exception as e:
        logger.error(f"Failed to score {symbol}: {str(e)}")
        return {
            'symbol': symbol,
            'price': 0,
            'volume': 0,
            'momentum_score': 0,
            'catalyst_score': 0,
            'pattern_score': 0,
            'technical_score': 0,
            'composite_score': 0
        }

# ========== DATABASE OPERATIONS ==========

async def ensure_tables_exist():
    """Ensure required database tables exist"""
    try:
        async with db_pool.acquire() as conn:
            # Create tables if they don't exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trading_cycles (
                    cycle_id VARCHAR(20) PRIMARY KEY,
                    mode VARCHAR(20) DEFAULT 'normal',
                    status VARCHAR(20) DEFAULT 'active',
                    scan_frequency INTEGER DEFAULT 300,
                    max_positions INTEGER DEFAULT 5,
                    risk_level DECIMAL(3,2) DEFAULT 0.5,
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    ended_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    metrics JSONB DEFAULT '{}'
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_results (
                    scan_time TIMESTAMPTZ NOT NULL,
                    scan_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(10) NOT NULL,
                    cycle_id VARCHAR(20),
                    price DECIMAL(10,2) DEFAULT 0,
                    volume BIGINT DEFAULT 0,
                    change_percent DECIMAL(6,2) DEFAULT 0,
                    momentum_score DECIMAL(5,2) DEFAULT 0,
                    catalyst_score DECIMAL(5,2) DEFAULT 0,
                    pattern_score DECIMAL(5,2) DEFAULT 0,
                    technical_score DECIMAL(5,2) DEFAULT 0,
                    composite_score DECIMAL(5,2) GENERATED ALWAYS AS (
                        (momentum_score * 0.3 + catalyst_score * 0.3 + 
                         pattern_score * 0.2 + technical_score * 0.2)
                    ) STORED,
                    catalysts JSONB DEFAULT '[]',
                    patterns JSONB DEFAULT '[]',
                    signals JSONB DEFAULT '{}',
                    is_selected BOOLEAN DEFAULT FALSE,
                    selection_rank INTEGER,
                    PRIMARY KEY (scan_time, scan_id, symbol)
                )
            """)
            
            logger.info("Database tables verified")
            
    except Exception as e:
        logger.error(f"Failed to create tables: {str(e)}")
        raise

async def persist_scan_results(scan_data: Dict):
    """
    Persist scan results following the v4.1 database schema exactly
    """
    try:
        async with db_pool.acquire() as conn:
            # Check for active cycle or create one - following schema exactly
            cycle_id = await conn.fetchval("""
                SELECT cycle_id FROM trading_cycles 
                WHERE status = 'active' 
                ORDER BY started_at DESC 
                LIMIT 1
            """)
            
            if not cycle_id:
                # Generate cycle_id as VARCHAR(20) - format: YYYYMMDD-NNN
                today = datetime.now().strftime('%Y%m%d')
                count = await conn.fetchval("""
                    SELECT COUNT(*) FROM trading_cycles 
                    WHERE cycle_id LIKE $1
                """, f"{today}-%")
                
                cycle_id = f"{today}-{count+1:03d}"
                
                # Insert with all required fields from schema
                await conn.execute("""
                    INSERT INTO trading_cycles (
                        cycle_id, mode, status, scan_frequency, 
                        max_positions, risk_level, started_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """, 
                    cycle_id,           # VARCHAR(20)
                    'normal',           # mode: normal/aggressive/conservative
                    'active',           # status: active
                    300,                # scan_frequency: 300 seconds (5 min)
                    5,                  # max_positions: 5
                    0.5                 # risk_level: 0.5 (50%)
                )
                logger.info(f"Created trading cycle: {cycle_id}")
            
            # Insert scan results with correct schema fields
            saved_count = 0
            for candidate in scan_data.get('candidates', []):
                try:
                    # Ensure we have all required fields
                    await conn.execute("""
                        INSERT INTO scan_results (
                            scan_id, cycle_id, symbol, scan_time,
                            price, volume, change_percent,
                            momentum_score, catalyst_score, pattern_score, technical_score,
                            catalysts, patterns, signals,
                            is_selected, selection_rank
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 
                            $12, $13, $14, $15, $16
                        )
                        ON CONFLICT (scan_time, scan_id, symbol) DO UPDATE SET
                            price = EXCLUDED.price,
                            volume = EXCLUDED.volume,
                            momentum_score = EXCLUDED.momentum_score,
                            catalyst_score = EXCLUDED.catalyst_score,
                            pattern_score = EXCLUDED.pattern_score,
                            technical_score = EXCLUDED.technical_score
                    """, 
                        scan_data['scan_id'],                    # scan_id VARCHAR(50)
                        cycle_id,                                 # cycle_id VARCHAR(20)
                        candidate['symbol'],                      # symbol VARCHAR(10)
                        scan_data['timestamp'],                   # scan_time TIMESTAMPTZ
                        float(candidate.get('price', 0)),        # price DECIMAL(10,2)
                        int(candidate.get('volume', 0)),         # volume BIGINT
                        float(candidate.get('price_change_pct', 0)), # change_percent
                        float(candidate.get('momentum_score', 0)),    # momentum_score
                        float(candidate.get('catalyst_score', 0)),    # catalyst_score
                        float(candidate.get('pattern_score', 0)),     # pattern_score
                        float(candidate.get('technical_score', 0)),   # technical_score
                        json.dumps(candidate.get('catalysts', [])),   # catalysts JSONB
                        json.dumps(candidate.get('patterns', [])),    # patterns JSONB
                        json.dumps(candidate.get('signals', {})),     # signals JSONB
                        candidate.get('rank', 0) <= 5,           # is_selected (top 5)
                        candidate.get('rank', 0)                 # selection_rank
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save candidate {candidate['symbol']}: {str(e)}")
            
            logger.info(f"✅ Persisted {saved_count}/{len(scan_data.get('candidates', []))} scan results to database")
            
            # Update cycle metrics as per schema
            if saved_count > 0:
                await conn.execute("""
                    UPDATE trading_cycles 
                    SET metrics = jsonb_build_object(
                        'last_scan_time', to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                        'total_scans', COALESCE((metrics->>'total_scans')::int, 0) + 1,
                        'candidates_found', $2
                    ),
                    updated_at = NOW()
                    WHERE cycle_id = $1
                """, cycle_id, saved_count)
            
    except Exception as e:
        logger.error(f"❌ Failed to persist scan results: {str(e)}")
        raise

# ========== MAIN ==========

if __name__ == "__main__":
    port = int(os.getenv('SERVICE_PORT', '5001'))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )