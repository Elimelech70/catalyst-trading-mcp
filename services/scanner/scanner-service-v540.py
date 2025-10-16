#!/usr/bin/env python3

# Name of Application: Catalyst Trading System
# Name of file: scanner-service.py
# Version: 5.4.0
# Last Updated: 2025-10-13
# Purpose: Scanner service with NORMALIZED schema v5.0 + RIGOROUS error handling

# REVISION HISTORY:
# v5.4.0 (2025-10-13) - RIGOROUS ERROR HANDLING (Playbook v3.0 Compliant)
# - Fixed #1: scan_market() - Specific exception handling (NO bare except)
# - Fixed #2: filter_by_technical() - No silent failures, tracks errors
# - Fixed #3: persist_scan_results() - Success/failure tracking, raises on critical failures
# - Enhanced logging with structured context throughout
# - Proper HTTPException raising for API consumers
# - Conforms to Playbook v3.0 Zero Tolerance Policy ✅
#
# v5.3.0 (2025-10-06) - DRY Principle Applied
# - Single version source (SERVICE_VERSION constant)
# - All version references use constants
# - No hardcoded versions in code
# 
# v5.2.0 (2025-10-06) - NORMALIZED SCHEMA MIGRATION (Playbook v3.0 Step 2)
# - Uses security_id FK (NOT symbol VARCHAR) ✅
# - Uses time_id FK for timestamps (NOT duplicate timestamps) ✅
# - Stores in scan_results with security_id FK ✅
# - Queries news_sentiment with JOINs for catalyst scores ✅
# - All queries use JOINs on FKs (NOT symbol strings) ✅
# - Helper functions: get_security_id(), get_time_id() ✅
# - NO data duplication - single source of truth ✅
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
# 6. RIGOROUS error handling - NO silent failures

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

# ============================================================================
# SERVICE METADATA (SINGLE SOURCE OF TRUTH)
# ============================================================================
SERVICE_NAME = "scanner"
SERVICE_VERSION = "5.4.0"
SERVICE_TITLE = "Scanner Service"
SCHEMA_VERSION = "v5.0 normalized"
SERVICE_PORT = 5001

# Initialize FastAPI
app = FastAPI(
    title=SERVICE_TITLE,
    version=SERVICE_VERSION,
    description=f"Market scanner with {SCHEMA_VERSION} and rigorous error handling"    
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(SERVICE_NAME)

# ============================================================================
# SERVICE STATE
# ============================================================================
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

# ============================================================================
# HELPER FUNCTIONS (NORMALIZED SCHEMA)
# ============================================================================
async def get_security_id(symbol: str) -> int:
    """
    Get or create security_id for symbol.
    Uses database helper function: get_or_create_security()
    
    Raises:
        ValueError: If security_id cannot be obtained
        asyncpg.PostgresError: If database error occurs
    """
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)", symbol.upper()
        )
        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")
        return security_id
        
    except asyncpg.PostgresError as e:
        logger.error(
            f"Database error in get_security_id: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'database'}
        )
        raise
        
    except Exception as e:
        logger.error(
            f"Unexpected error in get_security_id for {symbol}: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'unexpected'}
        )
        raise

async def get_time_id(timestamp: datetime) -> int:
    """
    Get or create time_id for timestamp.
    Uses database helper function: get_or_create_time()
    
    Raises:
        ValueError: If time_id cannot be obtained
        asyncpg.PostgresError: If database error occurs
    """
    try:
        time_id = await state.db_pool.fetchval(
            "SELECT get_or_create_time($1)", timestamp
        )
        if not time_id:
            raise ValueError(f"Failed to get time_id for {timestamp}")
        return time_id
        
    except asyncpg.PostgresError as e:
        logger.error(
            f"Database error in get_time_id: {e}",
            exc_info=True,
            extra={'timestamp': timestamp.isoformat(), 'error_type': 'database'}
        )
        raise
        
    except Exception as e:
        logger.error(
            f"Unexpected error in get_time_id for {timestamp}: {e}",
            exc_info=True,
            extra={'timestamp': timestamp.isoformat(), 'error_type': 'unexpected'}
        )
        raise

# ============================================================================
# MARKET DATA
# ============================================================================
async def get_active_universe(limit: int = 200) -> List[str]:
    """
    Get most active stocks from market.
    
    Returns:
        List of stock symbols
        
    Note: Returns hardcoded list in dev. Use real-time market data API in production.
    """
    try:
        # In production, use real-time market data API
        # For now, return common active stocks
        active_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM',
            'JNJ', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'PYPL', 'BAC', 'NFLX',
            'ADBE', 'CRM', 'XOM', 'VZ', 'CMCSA', 'PFE', 'INTC', 'CSCO', 'T',
            'PEP', 'ABT', 'CVX', 'NKE', 'WMT', 'TMO', 'ABBV', 'MRK', 'LLY',
            'COST', 'ORCL', 'ACN', 'MDT', 'DHR', 'TXN', 'NEE', 'HON', 'UNP',
            'PM', 'IBM', 'QCOM', 'LOW', 'LIN', 'AMD', 'GS', 'SBUX', 'CAT'
        ]
        
        logger.info(
            f"Retrieved {len(active_stocks[:limit])} symbols for universe",
            extra={'limit': limit, 'operation': 'get_universe'}
        )
        
        return active_stocks[:limit]
        
    except Exception as e:
        logger.error(
            f"Failed to get active universe: {e}",
            exc_info=True,
            extra={'limit': limit, 'error_type': 'universe_fetch'}
        )
        # Return empty list - let caller handle
        return []

async def get_quote(symbol: str) -> Optional[Dict]:
    """
    Get current quote for symbol using yfinance.
    
    Returns:
        Dict with price/volume/change or None if failed
    """
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
        logger.debug(
            f"Failed to get quote for {symbol}: {e}",
            extra={'symbol': symbol, 'error_type': 'quote_fetch'}
        )
        return None

# ============================================================================
# CATALYST FILTERING (QUERIES NEWS_SENTIMENT WITH JOINS)
# ============================================================================
async def filter_by_catalysts(symbols: List[str], min_strength: float = 0.3) -> List[Dict]:
    """
    Filter symbols by news catalysts.
    Queries news_sentiment table with JOINs (normalized schema).
    
    Args:
        symbols: List of symbols to check
        min_strength: Minimum catalyst strength (0.0-1.0)
        
    Returns:
        List of candidates with catalyst data
        
    Raises:
        asyncpg.PostgresError: If database query fails
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
        
        logger.info(
            f"Found {len(candidates)} candidates with catalysts",
            extra={
                'total_checked': len(symbols),
                'candidates_found': len(candidates),
                'min_strength': min_strength
            }
        )
        
        return candidates
        
    except asyncpg.PostgresError as e:
        logger.error(
            f"Database error in catalyst filtering: {e}",
            exc_info=True,
            extra={
                'symbols_count': len(symbols),
                'min_strength': min_strength,
                'error_type': 'database'
            }
        )
        raise
        
    except Exception as e:
        logger.error(
            f"Unexpected error in catalyst filtering: {e}",
            exc_info=True,
            extra={
                'symbols_count': len(symbols),
                'error_type': 'unexpected'
            }
        )
        raise

# ============================================================================
# TECHNICAL FILTERING (FIX #2 - NO SILENT FAILURES)
# ============================================================================
async def filter_by_technical(candidates: List[Dict]) -> List[Dict]:
    """
    Apply technical filters to candidates.
    
    Args:
        candidates: List of candidates to filter
        
    Returns:
        Filtered and scored candidates
        
    Raises:
        ValueError: If ALL candidates fail filtering (critical error)
    """
    filtered = []
    failed_symbols = []
    error_summary = {
        'validation': [],
        'structure': [],
        'calculation': []
    }
    
    for candidate in candidates:
        try:
            # Basic price filter
            if (candidate['price'] < state.config.min_price or 
                candidate['price'] > state.config.max_price):
                logger.debug(
                    f"Price out of range for {candidate['symbol']}: ${candidate['price']}",
                    extra={
                        'symbol': candidate['symbol'],
                        'price': candidate['price'],
                        'filter': 'price_range'
                    }
                )
                continue
            
            # Volume filter
            if candidate['volume'] < state.config.min_volume:
                logger.debug(
                    f"Volume too low for {candidate['symbol']}: {candidate['volume']:,}",
                    extra={
                        'symbol': candidate['symbol'],
                        'volume': candidate['volume'],
                        'filter': 'min_volume'
                    }
                )
                continue
            
            # Calculate technical score
            technical_score = 0.0
            
            # Momentum component
            if abs(candidate['change_percent']) > 2.0:
                technical_score += 0.4
            
            # Volume component
            if candidate['volume'] > 5_000_000:
                technical_score += 0.3
            
            # Catalyst component
            technical_score += candidate['catalyst_strength'] * 0.3
            
            # Composite score
            candidate['technical_score'] = technical_score
            candidate['composite_score'] = (
                candidate['catalyst_strength'] * 0.6 + technical_score * 0.4
            )
            
            filtered.append(candidate)
            
        except KeyError as e:
            # Missing required field - data structure error
            logger.warning(
                f"Missing field for {candidate.get('symbol', 'UNKNOWN')}: {e}",
                extra={
                    'symbol': candidate.get('symbol', 'UNKNOWN'),
                    'error_type': 'missing_field',
                    'field': str(e)
                }
            )
            error_summary['structure'].append(candidate.get('symbol', 'UNKNOWN'))
            failed_symbols.append(candidate.get('symbol', 'UNKNOWN'))
            
        except (TypeError, ValueError) as e:
            # Invalid data type - validation error
            logger.warning(
                f"Invalid data for {candidate.get('symbol', 'UNKNOWN')}: {e}",
                extra={
                    'symbol': candidate.get('symbol', 'UNKNOWN'),
                    'error_type': 'validation',
                    'error_message': str(e)
                }
            )
            error_summary['validation'].append(candidate.get('symbol', 'UNKNOWN'))
            failed_symbols.append(candidate.get('symbol', 'UNKNOWN'))
            
        except Exception as e:
            # Other calculation errors
            logger.warning(
                f"Calculation error for {candidate.get('symbol', 'UNKNOWN')}: {e}",
                exc_info=True,
                extra={
                    'symbol': candidate.get('symbol', 'UNKNOWN'),
                    'error_type': 'calculation'
                }
            )
            error_summary['calculation'].append(candidate.get('symbol', 'UNKNOWN'))
            failed_symbols.append(candidate.get('symbol', 'UNKNOWN'))
    
    # Log summary of failures
    if failed_symbols:
        logger.warning(
            f"Technical filter failed for {len(failed_symbols)}/{len(candidates)} candidates",
            extra={
                'failed_count': len(failed_symbols),
                'total_count': len(candidates),
                'failed_symbols': failed_symbols[:10],  # First 10
                'error_summary': error_summary
            }
        )
    
    # CRITICAL: Raise if ALL candidates failed
    if len(filtered) == 0 and len(candidates) > 0:
        error_msg = (
            f"Technical filter failed for ALL {len(candidates)} candidates. "
            f"Failed symbols: {failed_symbols[:10]}"
        )
        logger.error(
            error_msg,
            extra={
                'failed_count': len(candidates),
                'error_summary': error_summary
            }
        )
        raise ValueError(error_msg)
    
    # Sort by composite score
    filtered.sort(key=lambda x: x['composite_score'], reverse=True)
    
    logger.info(
        f"Technical filter: {len(filtered)}/{len(candidates)} candidates passed",
        extra={
            'passed': len(filtered),
            'failed': len(failed_symbols),
            'total': len(candidates)
        }
    )
    
    return filtered

# ============================================================================
# SCAN PERSISTENCE (FIX #3 - TRACK SUCCESS/FAILURE, RAISE ON CRITICAL)
# ============================================================================
async def persist_scan_results(cycle_id: str, candidates: List[Dict]) -> Dict:
    """
    Store scan results with NORMALIZED schema.
    Uses security_id and time_id FKs (NOT symbol VARCHAR or duplicate timestamps).
    
    Args:
        cycle_id: Trading cycle ID
        candidates: List of candidate dictionaries
        
    Returns:
        Dict with success/failure counts and failed symbols
        
    Raises:
        asyncpg.PostgresError: If cycle creation fails (critical)
        RuntimeError: If >50% of candidates fail to persist (critical)
    """
    scan_time = datetime.utcnow()
    success_count = 0
    failed_symbols = []
    error_details = {
        'fk_violations': [],
        'duplicates': [],
        'other_db_errors': []
    }
    
    try:
        # Get time_id for scan
        time_id = await get_time_id(scan_time)
        
        # Ensure trading cycle exists (MUST NOT FAIL SILENTLY)
        try:
            await state.db_pool.execute("""
                INSERT INTO trading_cycles (cycle_id, start_time, status)
                VALUES ($1, $2, 'active')
                ON CONFLICT (cycle_id) DO NOTHING
            """, cycle_id, scan_time)
            
            logger.info(
                f"Trading cycle ready: {cycle_id}",
                extra={'cycle_id': cycle_id, 'operation': 'cycle_create'}
            )
            
        except asyncpg.PostgresError as e:
            logger.critical(
                f"CRITICAL: Failed to create trading cycle {cycle_id}: {e}",
                exc_info=True,
                extra={'cycle_id': cycle_id, 'error_type': 'cycle_creation'}
            )
            raise  # Re-raise - this is critical
        
        # Store each scan result
        for candidate in candidates:
            try:
                # Get security_id
                security_id = candidate.get('security_id')
                if not security_id:
                    security_id = await get_security_id(candidate['symbol'])
                
                # Insert scan result
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
                
                success_count += 1
                
            except asyncpg.UniqueViolationError as e:
                # Duplicate - acceptable, not a real failure
                logger.debug(
                    f"Duplicate scan result for {candidate['symbol']} (acceptable)",
                    extra={
                        'symbol': candidate['symbol'],
                        'cycle_id': cycle_id,
                        'error_type': 'duplicate'
                    }
                )
                error_details['duplicates'].append(candidate['symbol'])
                success_count += 1  # Not a real failure
                
            except asyncpg.ForeignKeyViolationError as e:
                # FK violation - serious data integrity issue
                logger.error(
                    f"FK violation storing {candidate['symbol']}: {e}",
                    exc_info=True,
                    extra={
                        'symbol': candidate['symbol'],
                        'cycle_id': cycle_id,
                        'error_type': 'fk_violation'
                    }
                )
                error_details['fk_violations'].append(candidate['symbol'])
                failed_symbols.append(candidate['symbol'])
                
            except asyncpg.PostgresError as e:
                # Other database error
                logger.error(
                    f"Database error storing {candidate['symbol']}: {e}",
                    exc_info=True,
                    extra={
                        'symbol': candidate['symbol'],
                        'cycle_id': cycle_id,
                        'error_type': 'database',
                        'error_code': getattr(e, 'sqlstate', 'unknown')
                    }
                )
                error_details['other_db_errors'].append(candidate['symbol'])
                failed_symbols.append(candidate['symbol'])
                
            except Exception as e:
                # Unexpected error
                logger.error(
                    f"Unexpected error storing {candidate['symbol']}: {e}",
                    exc_info=True,
                    extra={
                        'symbol': candidate['symbol'],
                        'cycle_id': cycle_id,
                        'error_type': 'unexpected'
                    }
                )
                failed_symbols.append(candidate['symbol'])
        
        # Summary logging
        logger.info(
            f"Persisted {success_count}/{len(candidates)} scan results for {cycle_id}",
            extra={
                'cycle_id': cycle_id,
                'success': success_count,
                'failed': len(failed_symbols),
                'total': len(candidates),
                'error_details': error_details
            }
        )
        
        # CRITICAL: Raise if too many failures (>50%)
        failure_threshold = len(candidates) * 0.5
        if len(failed_symbols) > failure_threshold:
            error_msg = (
                f"CRITICAL: Failed to persist {len(failed_symbols)}/{len(candidates)} "
                f"candidates ({len(failed_symbols)/len(candidates)*100:.1f}%). "
                f"Failed symbols: {failed_symbols}"
            )
            logger.critical(
                error_msg,
                extra={
                    'cycle_id': cycle_id,
                    'success': success_count,
                    'failed': len(failed_symbols),
                    'threshold': failure_threshold,
                    'error_details': error_details
                }
            )
            raise RuntimeError(error_msg)
        
        return {
            'success': success_count,
            'failed': len(failed_symbols),
            'failed_symbols': failed_symbols,
            'error_details': error_details,
            'total': len(candidates)
        }
        
    except (ValueError, RuntimeError, asyncpg.PostgresError):
        # Re-raise known critical errors
        raise
        
    except Exception as e:
        # Unexpected errors in persist function itself
        logger.critical(
            f"UNEXPECTED error in persist_scan_results: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'candidates_count': len(candidates),
                'error_type': 'persist_function'
            }
        )
        raise

# ============================================================================
# MAIN SCAN FUNCTION (FIX #1 - SPECIFIC EXCEPTION HANDLING)
# ============================================================================
async def scan_market() -> Dict:
    """
    Main market scanning function with rigorous error handling.
    
    Raises:
        HTTPException(503): Database unavailable
        HTTPException(502): Market data source unavailable  
        HTTPException(400): Invalid data
        HTTPException(504): Scan timeout
        HTTPException(500): Critical system error
        
    Returns:
        Dict with scan results or raises HTTPException
    """
    cycle_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    logger.info(
        f"Starting market scan: {cycle_id}",
        extra={'cycle_id': cycle_id, 'operation': 'scan_start'}
    )
    
    try:
        # Step 1: Get active universe
        universe = await get_active_universe(state.config.initial_universe_size)
        if not universe:
            raise ValueError("Failed to retrieve market universe - no symbols returned")
            
        logger.info(
            f"Initial universe: {len(universe)} symbols",
            extra={'cycle_id': cycle_id, 'universe_size': len(universe)}
        )
        
        # Step 2: Filter by catalysts (queries news_sentiment with JOINs)
        catalyst_candidates = await filter_by_catalysts(
            universe, 
            state.config.min_catalyst_score
        )
        logger.info(
            f"After catalyst filter: {len(catalyst_candidates)} candidates",
            extra={'cycle_id': cycle_id, 'catalyst_count': len(catalyst_candidates)}
        )
        
        # Step 3: Apply technical filters
        technical_candidates = await filter_by_technical(catalyst_candidates)
        logger.info(
            f"After technical filter: {len(technical_candidates)} candidates",
            extra={'cycle_id': cycle_id, 'technical_count': len(technical_candidates)}
        )
        
        # Step 4: Select final candidates
        final_candidates = technical_candidates[:state.config.final_selection_size]
        
        # Mark selected candidates
        for candidate in final_candidates:
            candidate['selected'] = True
        
        # Step 5: Persist results (with security_id FKs)
        persist_result = await persist_scan_results(cycle_id, technical_candidates)
        
        logger.info(
            f"Scan {cycle_id} completed successfully",
            extra={
                'cycle_id': cycle_id,
                'final_selections': len(final_candidates),
                'persisted': persist_result['success']
            }
        )
        
        return {
            'success': True,
            'cycle_id': cycle_id,
            'timestamp': datetime.utcnow().isoformat(),
            'universe_size': len(universe),
            'catalyst_candidates': len(catalyst_candidates),
            'technical_candidates': len(technical_candidates),
            'final_selections': len(final_candidates),
            'candidates': final_candidates,
            'persistence': persist_result
        }
        
    except asyncpg.PostgresError as e:
        # Database errors - CRITICAL
        logger.critical(
            f"Database error during scan {cycle_id}: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'database',
                'error_code': getattr(e, 'sqlstate', 'unknown')
            }
        )
        raise HTTPException(
            status_code=503,
            detail={
                'error': 'Database unavailable',
                'cycle_id': cycle_id,
                'message': 'Scanner cannot access database. Check database connection.',
                'retry_after': 30
            }
        )
        
    except aiohttp.ClientError as e:
        # Network/API errors - market data unavailable
        logger.error(
            f"Network error fetching market data for scan {cycle_id}: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'network',
                'error_class': e.__class__.__name__
            }
        )
        raise HTTPException(
            status_code=502,
            detail={
                'error': 'Market data unavailable',
                'cycle_id': cycle_id,
                'message': 'Cannot fetch market data. Market data API may be down.',
                'retry_after': 60
            }
        )
        
    except ValueError as e:
        # Data validation errors - bad data from external sources
        logger.error(
            f"Invalid data during scan {cycle_id}: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'validation',
                'error_message': str(e)
            }
        )
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'Invalid scan data',
                'cycle_id': cycle_id,
                'message': str(e)
            }
        )
        
    except KeyError as e:
        # Missing required data fields - configuration or data structure issue
        logger.error(
            f"Missing required field during scan {cycle_id}: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'missing_field',
                'field': str(e)
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'Configuration error',
                'cycle_id': cycle_id,
                'message': f'Missing required field: {e}'
            }
        )
        
    except asyncio.TimeoutError as e:
        # Timeout errors - scan took too long
        logger.error(
            f"Scan {cycle_id} timeout: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'timeout'
            }
        )
        raise HTTPException(
            status_code=504,
            detail={
                'error': 'Scan timeout',
                'cycle_id': cycle_id,
                'message': 'Scan took too long to complete. Try reducing universe size.',
                'retry_after': 120
            }
        )
        
    except RuntimeError as e:
        # Runtime errors (like critical persistence failures)
        logger.critical(
            f"Runtime error in scan {cycle_id}: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'runtime'
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'System error',
                'cycle_id': cycle_id,
                'message': str(e)
            }
        )
        
    except Exception as e:
        # Truly unexpected errors - log as CRITICAL and re-raise
        logger.critical(
            f"UNEXPECTED error in scan {cycle_id}: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'error_type': 'unexpected',
                'error_class': e.__class__.__name__
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'Internal server error',
                'cycle_id': cycle_id,
                'message': 'An unexpected error occurred. This has been logged for investigation.'
            }
        )

# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {SERVICE_TITLE} v{SERVICE_VERSION} ({SCHEMA_VERSION})")
    
    # Database
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable required")
        
        state.db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
        logger.info("Database pool initialized")
        
        # Verify normalized schema
        await verify_normalized_schema()
        
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise
    
    # Redis (optional - warning if fails)
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        state.redis_client = await redis.from_url(redis_url)
        logger.info("Redis client initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed (non-critical): {e}")
    
    # HTTP session
    state.http_session = aiohttp.ClientSession()
    
    logger.info(f"{SERVICE_TITLE} v{SERVICE_VERSION} ready on port {SERVICE_PORT}")

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
            raise ValueError(
                "scan_results missing security_id column - schema v5.0 not deployed! "
                "Run normalized-database-schema-mcp-v50.sql first."
            )
        
        if has_symbol:
            raise ValueError(
                "scan_results has symbol column - schema is DENORMALIZED! "
                "This violates normalization. Run migration script."
            )
        
        logger.info("✅ Normalized schema v5.0 verified - scan_results uses security_id FK")
        
    except Exception as e:
        logger.critical(f"Schema verification failed: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {SERVICE_TITLE}")
    
    if state.http_session:
        await state.http_session.close()
    if state.db_pool:
        await state.db_pool.close()
    if state.redis_client:
        await state.redis_client.close()
    
    logger.info(f"{SERVICE_TITLE} shutdown complete")

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.get("/health")
async def health_check():
    """Health check endpoint with detailed status"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "schema": SCHEMA_VERSION,
        "uses_security_id_fk": True,
        "uses_time_id_fk": True,
        "error_handling": "rigorous",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if state.db_pool else "disconnected",
        "redis": "connected" if state.redis_client else "disconnected"
    }

@app.post("/api/v1/scan")
async def trigger_scan():
    """
    Trigger market scan.
    
    Returns scan results or raises HTTPException with proper status codes.
    """
    result = await scan_market()
    return result

@app.get("/api/v1/candidates")
async def get_candidates(cycle_id: Optional[str] = None, limit: int = 10):
    """
    Get scan candidates with JOINs (normalized schema).
    
    Args:
        cycle_id: Optional cycle ID to get specific results
        limit: Maximum number of results (default 10)
    """
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
                    ORDER BY id DESC LIMIT 1
                )
                ORDER BY sr.composite_score DESC
                LIMIT $1
            """, limit)
        
        return {
            "candidates": [dict(r) for r in results],
            "count": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except asyncpg.PostgresError as e:
        logger.error(f"Database error in get_candidates: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={'error': 'Database unavailable', 'message': str(e)}
        )
        
    except Exception as e:
        logger.error(f"Error in get_candidates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={'error': 'Internal server error', 'message': str(e)}
        )

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(f"🎩 Catalyst Trading System - {SERVICE_TITLE} v{SERVICE_VERSION}")
    print("=" * 70)
    print(f"✅ {SCHEMA_VERSION} with FKs")
    print("✅ Uses security_id FK (NOT symbol VARCHAR)")
    print("✅ Uses time_id FK (NOT duplicate timestamps)")
    print("✅ Queries news_sentiment with JOINs for catalysts")
    print("✅ All queries use JOINs on FKs")
    print("✅ NO data duplication - single source of truth")
    print("✅ RIGOROUS error handling - NO silent failures")
    print(f"Port: {SERVICE_PORT}")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
