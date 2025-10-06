#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: reporting-service.py
Version: 5.0.0
Last Updated: 2025-10-06
Purpose: Reporting and analytics with normalized schema v5.0 (security_id FKs + JOINs)

REVISION HISTORY:
v5.0.0 (2025-10-06) - Normalized Schema Update
- ✅ All reports use JOINs (positions → securities → sectors)
- ✅ Daily reports aggregate by security_id
- ✅ Performance metrics use FK relationships
- ✅ Pattern success tracking via security_id
- ✅ Sector performance analysis via JOINs
- ✅ No duplicate symbol storage
- ✅ Error handling compliant with v1.0 standard

v4.0.0 (2025-09-15) - DEPRECATED (Denormalized)
- Used symbol VARCHAR in reports
- No FK relationships

Description of Service:
Generates trading reports and analytics using normalized v5.0 schema:
- Daily trading reports (P&L, positions, patterns)
- Performance analytics (win rate, R-multiple, sector performance)
- Position history with security_id tracking
- Pattern success analysis
- All data queried via JOINs for data integrity
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
import asyncpg
import os
import logging

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Service configuration"""
    SERVICE_NAME = "reporting-service"
    VERSION = "5.0.0"
    PORT = 5006
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://catalyst:catalyst@localhost:5432/catalyst_trading")
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class ServiceState:
    """Global service state"""
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.is_healthy = False

state = ServiceState()

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    logger.info(f"Starting {Config.SERVICE_NAME} v{Config.VERSION}")
    
    try:
        # Initialize database pool
        state.db_pool = await asyncpg.create_pool(
            Config.DATABASE_URL,
            min_size=Config.POOL_MIN_SIZE,
            max_size=Config.POOL_MAX_SIZE,
            command_timeout=60
        )
        logger.info("✅ Database pool created")
        
        # Verify schema
        async with state.db_pool.acquire() as conn:
            # Check required tables
            for table in ['positions', 'securities', 'sectors', 'pattern_analysis', 'daily_risk_metrics']:
                exists = await conn.fetchval(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """)
                if not exists:
                    raise Exception(f"{table} table does not exist! Run schema v5.0 first.")
        
        state.is_healthy = True
        logger.info("✅ Schema validation passed - v5.0 normalized tables found")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        state.is_healthy = False
        raise
    finally:
        # Cleanup
        if state.db_pool:
            await state.db_pool.close()
            logger.info("Database pool closed")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Catalyst Reporting Service",
    description="Reporting and analytics with normalized schema v5.0",
    version=Config.VERSION,
    lifespan=lifespan
)

# ============================================================================
# DEPENDENCY: DATABASE CONNECTION
# ============================================================================

async def get_db():
    """Dependency to get database connection"""
    if not state.db_pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized")
    async with state.db_pool.acquire() as conn:
        yield conn

# ============================================================================
# MODELS
# ============================================================================

class DailyReportResponse(BaseModel):
    """Daily trading report"""
    cycle_id: int
    date: str
    summary: Dict[str, Any]
    positions: List[Dict[str, Any]]
    patterns: List[Dict[str, Any]]
    sector_breakdown: List[Dict[str, Any]]
    risk_metrics: Dict[str, Any]

class PerformanceMetrics(BaseModel):
    """Performance analytics"""
    cycle_id: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: Optional[float]
    avg_r_multiple: Optional[float]

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/api/v1/reports/daily", response_model=DailyReportResponse)
async def get_daily_report(
    cycle_id: int,
    date: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Generate daily trading report using JOINs.
    
    v5.0 Pattern:
    - All queries JOIN positions → securities → sectors
    - Pattern queries JOIN pattern_analysis → securities
    - Aggregates by security_id (not symbol duplicates)
    """
    try:
        # Parse date or use today
        if date:
            report_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            report_date = datetime.utcnow().date()
        
        logger.info(f"Generating daily report for cycle {cycle_id} on {report_date}")
        
        # Summary metrics
        summary = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'open') as open_positions,
                COUNT(*) FILTER (WHERE status = 'closed' AND DATE(closed_at) = $2) as closed_today,
                COALESCE(SUM(realized_pnl) FILTER (WHERE DATE(closed_at) = $2), 0) as realized_pnl,
                COALESCE(SUM(unrealized_pnl) FILTER (WHERE status = 'open'), 0) as unrealized_pnl,
                COUNT(*) FILTER (WHERE realized_pnl > 0 AND DATE(closed_at) = $2) as winners_today,
                COUNT(*) FILTER (WHERE realized_pnl < 0 AND DATE(closed_at) = $2) as losers_today
            FROM positions
            WHERE cycle_id = $1
            AND DATE(created_at) <= $2
        """, cycle_id, report_date)
        
        # Open positions with JOINs
        positions = await conn.fetch("""
            SELECT 
                p.position_id,
                p.security_id,
                s.symbol,
                s.company_name,
                sec.sector_name,
                p.side,
                p.quantity,
                p.entry_price,
                p.current_price,
                p.stop_price,
                p.target_price,
                p.unrealized_pnl,
                p.risk_amount,
                (p.unrealized_pnl / NULLIF(p.risk_amount, 0)) as r_multiple,
                p.created_at
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND p.status = 'open'
            ORDER BY p.created_at DESC
        """, cycle_id)
        
        # Patterns detected today with JOINs
        patterns = await conn.fetch("""
            SELECT 
                pa.pattern_id,
                s.symbol,
                s.company_name,
                pa.pattern_type,
                pa.pattern_subtype,
                pa.confidence_score,
                pa.price_at_detection,
                pa.breakout_level,
                td.timestamp as detected_at
            FROM pattern_analysis pa
            JOIN securities s ON s.security_id = pa.security_id
            JOIN time_dimension td ON td.time_id = pa.time_id
            WHERE DATE(td.timestamp) = $1
            ORDER BY pa.confidence_score DESC
            LIMIT 20
        """, report_date)
        
        # Sector breakdown with JOINs
        sector_breakdown = await conn.fetch("""
            SELECT 
                sec.sector_name,
                COUNT(p.position_id) as position_count,
                SUM(p.quantity * p.entry_price) as total_exposure,
                SUM(p.unrealized_pnl) as unrealized_pnl,
                SUM(p.realized_pnl) FILTER (WHERE DATE(p.closed_at) = $2) as realized_pnl_today
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND (p.status = 'open' OR DATE(p.closed_at) = $2)
            GROUP BY sec.sector_name
            ORDER BY total_exposure DESC
        """, cycle_id, report_date)
        
        # Risk metrics from daily_risk_metrics table
        risk_metrics_row = await conn.fetchrow("""
            SELECT 
                total_positions_opened,
                positions_closed,
                total_realized_pnl,
                total_unrealized_pnl,
                winning_trades,
                losing_trades,
                largest_win,
                largest_loss
            FROM daily_risk_metrics
            WHERE cycle_id = $1
            AND date = $2
        """, cycle_id, report_date)
        
        # Build response
        total_pnl = float(summary['realized_pnl'] or 0) + float(summary['unrealized_pnl'] or 0)
        
        return DailyReportResponse(
            cycle_id=cycle_id,
            date=report_date.isoformat(),
            summary={
                'open_positions': summary['open_positions'],
                'closed_today': summary['closed_today'],
                'realized_pnl': float(summary['realized_pnl'] or 0),
                'unrealized_pnl': float(summary['unrealized_pnl'] or 0),
                'total_pnl': total_pnl,
                'winners_today': summary['winners_today'],
                'losers_today': summary['losers_today'],
                'win_rate_today': (
                    summary['winners_today'] / (summary['winners_today'] + summary['losers_today'])
                    if (summary['winners_today'] + summary['losers_today']) > 0 else 0
                )
            },
            positions=[dict(r) for r in positions],
            patterns=[dict(r) for r in patterns],
            sector_breakdown=[dict(r) for r in sector_breakdown],
            risk_metrics=dict(risk_metrics_row) if risk_metrics_row else {}
        )
    
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/reports/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    cycle_id: int,
    days: int = 30,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Get performance metrics for the cycle.
    
    v5.0 Pattern:
    - Aggregates closed positions
    - Calculates win rate, profit factor, R-multiples
    """
    try:
        # Get closed positions
        metrics = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE realized_pnl > 0) as winning_trades,
                COUNT(*) FILTER (WHERE realized_pnl < 0) as losing_trades,
                COALESCE(SUM(realized_pnl), 0) as total_pnl,
                AVG(realized_pnl) FILTER (WHERE realized_pnl > 0) as avg_win,
                AVG(realized_pnl) FILTER (WHERE realized_pnl < 0) as avg_loss,
                MAX(realized_pnl) as largest_win,
                MIN(realized_pnl) as largest_loss,
                SUM(realized_pnl) FILTER (WHERE realized_pnl > 0) as gross_profit,
                ABS(SUM(realized_pnl) FILTER (WHERE realized_pnl < 0)) as gross_loss,
                AVG(realized_pnl / NULLIF(risk_amount, 0)) as avg_r_multiple
            FROM positions
            WHERE cycle_id = $1
            AND status = 'closed'
            AND closed_at >= NOW() - INTERVAL '1 day' * $2
        """, cycle_id, days)
        
        if not metrics or metrics['total_trades'] == 0:
            return PerformanceMetrics(
                cycle_id=cycle_id,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                average_win=0.0,
                average_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                profit_factor=None,
                avg_r_multiple=None
            )
        
        # Calculate profit factor
        profit_factor = None
        if metrics['gross_loss'] and metrics['gross_loss'] > 0:
            profit_factor = float(metrics['gross_profit']) / float(metrics['gross_loss'])
        
        win_rate = metrics['winning_trades'] / metrics['total_trades'] if metrics['total_trades'] > 0 else 0
        
        return PerformanceMetrics(
            cycle_id=cycle_id,
            total_trades=metrics['total_trades'],
            winning_trades=metrics['winning_trades'],
            losing_trades=metrics['losing_trades'],
            win_rate=win_rate,
            total_pnl=float(metrics['total_pnl'] or 0),
            average_win=float(metrics['avg_win'] or 0),
            average_loss=float(metrics['avg_loss'] or 0),
            largest_win=float(metrics['largest_win'] or 0),
            largest_loss=float(metrics['largest_loss'] or 0),
            profit_factor=profit_factor,
            avg_r_multiple=float(metrics['avg_r_multiple']) if metrics['avg_r_multiple'] else None
        )
    
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/reports/position-history/{symbol}")
async def get_position_history(
    symbol: str,
    cycle_id: int,
    limit: int = 50,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Get position history for a specific symbol using security_id.
    
    v5.0 Pattern:
    - Looks up security_id first
    - Queries positions by security_id (not symbol!)
    """
    try:
        # Get security_id
        security_id = await conn.fetchval("""
            SELECT security_id FROM securities WHERE symbol = $1
        """, symbol.upper())
        
        if not security_id:
            raise HTTPException(status_code=404, detail=f"Security {symbol} not found")
        
        # Get position history
        positions = await conn.fetch("""
            SELECT 
                p.position_id,
                s.symbol,
                s.company_name,
                p.side,
                p.quantity,
                p.entry_price,
                p.exit_price,
                p.stop_price,
                p.target_price,
                p.realized_pnl,
                p.risk_amount,
                (p.realized_pnl / NULLIF(p.risk_amount, 0)) as r_multiple,
                p.status,
                p.created_at,
                p.closed_at
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            WHERE p.security_id = $1
            AND p.cycle_id = $2
            ORDER BY p.created_at DESC
            LIMIT $3
        """, security_id, cycle_id, limit)
        
        return {
            "symbol": symbol.upper(),
            "security_id": security_id,
            "cycle_id": cycle_id,
            "count": len(positions),
            "positions": [dict(r) for r in positions]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching position history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/reports/pattern-success")
async def get_pattern_success_rates(
    cycle_id: int,
    days: int = 30,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Analyze which patterns lead to successful trades.
    
    v5.0 Pattern:
    - JOINs pattern_analysis with positions via security_id
    - Tracks which patterns preceded winning trades
    """
    try:
        # Get patterns that were followed by positions
        pattern_stats = await conn.fetch("""
            WITH pattern_positions AS (
                SELECT 
                    pa.pattern_type,
                    pa.pattern_subtype,
                    pa.security_id,
                    pa.time_id,
                    td.timestamp as pattern_time,
                    p.position_id,
                    p.realized_pnl,
                    p.created_at as position_time
                FROM pattern_analysis pa
                JOIN time_dimension td ON td.time_id = pa.time_id
                LEFT JOIN positions p ON p.security_id = pa.security_id
                    AND p.created_at >= td.timestamp
                    AND p.created_at <= td.timestamp + INTERVAL '24 hours'
                    AND p.cycle_id = $1
                WHERE td.timestamp >= NOW() - INTERVAL '1 day' * $2
            )
            SELECT 
                pattern_type,
                pattern_subtype,
                COUNT(DISTINCT security_id) as times_detected,
                COUNT(position_id) as positions_taken,
                COUNT(position_id) FILTER (WHERE realized_pnl > 0) as winning_positions,
                AVG(realized_pnl) FILTER (WHERE realized_pnl IS NOT NULL) as avg_pnl
            FROM pattern_positions
            GROUP BY pattern_type, pattern_subtype
            HAVING COUNT(position_id) > 0
            ORDER BY winning_positions DESC, times_detected DESC
        """, cycle_id, days)
        
        results = []
        for row in pattern_stats:
            success_rate = (
                row['winning_positions'] / row['positions_taken']
                if row['positions_taken'] > 0 else 0
            )
            
            results.append({
                'pattern_type': row['pattern_type'],
                'pattern_subtype': row['pattern_subtype'],
                'times_detected': row['times_detected'],
                'positions_taken': row['positions_taken'],
                'winning_positions': row['winning_positions'],
                'success_rate': success_rate,
                'avg_pnl': float(row['avg_pnl'] or 0)
            })
        
        return {
            "cycle_id": cycle_id,
            "days": days,
            "patterns": results
        }
    
    except Exception as e:
        logger.error(f"Error analyzing pattern success: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/reports/sector-performance")
async def get_sector_performance(
    cycle_id: int,
    days: int = 30,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Get performance breakdown by sector using JOINs.
    
    v5.0 Pattern:
    - JOIN positions → securities → sectors
    - Aggregate P&L by sector
    """
    try:
        sector_stats = await conn.fetch("""
            SELECT 
                sec.sector_name,
                COUNT(p.position_id) as total_positions,
                COUNT(p.position_id) FILTER (WHERE p.realized_pnl > 0) as winning_positions,
                SUM(p.realized_pnl) as total_pnl,
                AVG(p.realized_pnl) as avg_pnl,
                MAX(p.realized_pnl) as best_trade,
                MIN(p.realized_pnl) as worst_trade
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND p.status = 'closed'
            AND p.closed_at >= NOW() - INTERVAL '1 day' * $2
            GROUP BY sec.sector_name
            ORDER BY total_pnl DESC
        """, cycle_id, days)
        
        results = []
        for row in sector_stats:
            win_rate = (
                row['winning_positions'] / row['total_positions']
                if row['total_positions'] > 0 else 0
            )
            
            results.append({
                'sector_name': row['sector_name'] or 'Unknown',
                'total_positions': row['total_positions'],
                'winning_positions': row['winning_positions'],
                'win_rate': win_rate,
                'total_pnl': float(row['total_pnl'] or 0),
                'avg_pnl': float(row['avg_pnl'] or 0),
                'best_trade': float(row['best_trade'] or 0),
                'worst_trade': float(row['worst_trade'] or 0)
            })
        
        return {
            "cycle_id": cycle_id,
            "days": days,
            "sectors": results
        }
    
    except Exception as e:
        logger.error(f"Error analyzing sector performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not state.is_healthy or not state.db_pool:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": Config.SERVICE_NAME,
                "version": Config.VERSION
            }
        )
    
    return {
        "status": "healthy",
        "service": Config.SERVICE_NAME,
        "version": Config.VERSION,
        "schema": "v5.0 normalized",
        "uses_security_id_fk": True,
        "reports": [
            "Daily trading report",
            "Performance metrics (win rate, R-multiples)",
            "Position history by symbol",
            "Pattern success analysis",
            "Sector performance breakdown"
        ]
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=Config.PORT,
        log_level="info"
    )
