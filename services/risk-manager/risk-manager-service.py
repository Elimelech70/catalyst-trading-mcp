#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk-manager-service.py
Version: 5.0.0
Last Updated: 2025-10-06
Purpose: Risk management with normalized schema v5.0 (security_id FKs + sector JOINs)

REVISION HISTORY:
v5.0.0 (2025-10-06) - Normalized Schema Update
- ✅ Sector exposure tracking with JOINs (securities → sectors)
- ✅ Position risk calculations with security_id FKs
- ✅ All queries use JOINs (NO symbol VARCHAR!)
- ✅ Real-time risk limits enforcement
- ✅ Daily risk metrics tracking
- ✅ Risk events logging with FKs
- ✅ Error handling compliant with v1.0 standard

v4.2.0 (2025-09-20) - DEPRECATED (Denormalized)
- Had risk tables but used symbol VARCHAR
- No FK relationships with securities/sectors

Description of Service:
Enforces risk management rules using normalized v5.0 schema:
- Position sizing and limits
- Sector exposure limits (via securities → sectors JOIN)
- Daily loss limits
- Max positions per cycle
- Risk/reward validation
- All queries use security_id FKs for data integrity
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
from enum import Enum
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
    SERVICE_NAME = "risk-manager"
    VERSION = "5.0.0"
    PORT = 5004
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://catalyst:catalyst@localhost:5432/catalyst_trading")
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10
    
    # Default risk limits (can be overridden by risk_parameters table)
    MAX_POSITIONS = 5
    MAX_POSITION_SIZE = 1000.00  # USD
    MAX_DAILY_LOSS = 500.00  # USD
    MAX_SECTOR_EXPOSURE = 0.40  # 40% of total capital
    MIN_RISK_REWARD_RATIO = 2.0

# ============================================================================
# ENUMS
# ============================================================================

class RiskLevel(str, Enum):
    """Risk severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskEventType(str, Enum):
    """Types of risk events"""
    POSITION_LIMIT = "position_limit"
    SECTOR_LIMIT = "sector_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_SIZE_LIMIT = "position_size_limit"
    RISK_REWARD_VIOLATION = "risk_reward_violation"

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
            for table in ['positions', 'securities', 'sectors', 'risk_parameters', 'daily_risk_metrics']:
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
    title="Catalyst Risk Manager",
    description="Risk management with normalized schema v5.0",
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

class PositionRequest(BaseModel):
    """Request to validate a new position"""
    symbol: str = Field(..., description="Stock symbol")
    side: str = Field(..., description="long or short")
    quantity: int = Field(..., gt=0, description="Number of shares")
    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_price: float = Field(..., gt=0, description="Stop loss price")
    target_price: Optional[float] = Field(None, gt=0, description="Target price")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return v.upper().strip()
    
    @validator('side')
    def validate_side(cls, v):
        if v.lower() not in ['long', 'short']:
            raise ValueError("Side must be 'long' or 'short'")
        return v.lower()

class RiskCheckResult(BaseModel):
    """Result of risk validation"""
    approved: bool
    risk_level: RiskLevel
    violations: List[str]
    warnings: List[str]
    position_size_usd: float
    risk_amount_usd: float
    risk_reward_ratio: Optional[float]
    sector_exposure_pct: Optional[float]
    daily_pnl: float

class SectorExposure(BaseModel):
    """Sector exposure data"""
    sector_name: str
    position_count: int
    total_exposure_usd: float
    total_pnl: float
    exposure_pct: float

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_risk_parameters(conn: asyncpg.Connection, cycle_id: int) -> Dict[str, Any]:
    """Get risk parameters for the current cycle"""
    params = await conn.fetchrow("""
        SELECT 
            max_positions,
            max_position_size_usd,
            max_daily_loss_usd,
            max_sector_exposure_pct,
            min_risk_reward_ratio
        FROM risk_parameters
        WHERE cycle_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """, cycle_id)
    
    if params:
        return dict(params)
    
    # Return defaults if no custom parameters
    return {
        'max_positions': Config.MAX_POSITIONS,
        'max_position_size_usd': Config.MAX_POSITION_SIZE,
        'max_daily_loss_usd': Config.MAX_DAILY_LOSS,
        'max_sector_exposure_pct': Config.MAX_SECTOR_EXPOSURE,
        'min_risk_reward_ratio': Config.MIN_RISK_REWARD_RATIO
    }

async def get_security_id(conn: asyncpg.Connection, symbol: str) -> int:
    """Get security_id for a symbol"""
    security_id = await conn.fetchval("""
        SELECT security_id FROM securities WHERE symbol = $1
    """, symbol.upper())
    
    if not security_id:
        raise HTTPException(status_code=404, detail=f"Security {symbol} not found")
    
    return security_id

async def log_risk_event(
    conn: asyncpg.Connection,
    cycle_id: int,
    event_type: RiskEventType,
    severity: RiskLevel,
    description: str,
    metadata: Dict = None
):
    """Log a risk event to risk_events table"""
    try:
        await conn.execute("""
            INSERT INTO risk_events (
                cycle_id, event_type, severity, description, metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, NOW())
        """, cycle_id, event_type.value, severity.value, description, metadata or {})
        
        logger.warning(f"Risk event logged: {event_type.value} - {description}")
    except Exception as e:
        logger.error(f"Failed to log risk event: {e}")

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/api/v1/risk/check", response_model=RiskCheckResult)
async def check_position_risk(
    request: PositionRequest,
    cycle_id: int,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Check if a proposed position passes risk checks.
    
    v5.0 Pattern:
    - Uses security_id FK lookups
    - JOINs with sectors table for sector exposure
    - Queries positions table with security_id
    """
    try:
        violations = []
        warnings = []
        
        # Get security_id
        security_id = await get_security_id(conn, request.symbol)
        
        # Get risk parameters
        params = await get_risk_parameters(conn, cycle_id)
        
        # Calculate position metrics
        position_size = request.quantity * request.entry_price
        
        if request.side == 'long':
            risk_amount = request.quantity * (request.entry_price - request.stop_price)
        else:
            risk_amount = request.quantity * (request.stop_price - request.entry_price)
        
        risk_reward_ratio = None
        if request.target_price:
            if request.side == 'long':
                reward = request.quantity * (request.target_price - request.entry_price)
            else:
                reward = request.quantity * (request.entry_price - request.target_price)
            
            if risk_amount > 0:
                risk_reward_ratio = reward / risk_amount
        
        # Check 1: Position size limit
        if position_size > params['max_position_size_usd']:
            violations.append(
                f"Position size ${position_size:.2f} exceeds max ${params['max_position_size_usd']:.2f}"
            )
        
        # Check 2: Risk/reward ratio
        if risk_reward_ratio and risk_reward_ratio < params['min_risk_reward_ratio']:
            violations.append(
                f"Risk/reward {risk_reward_ratio:.2f} below minimum {params['min_risk_reward_ratio']:.2f}"
            )
        
        # Check 3: Max positions limit (using security_id)
        open_positions = await conn.fetchval("""
            SELECT COUNT(*)
            FROM positions
            WHERE cycle_id = $1
            AND status = 'open'
        """, cycle_id)
        
        if open_positions >= params['max_positions']:
            violations.append(
                f"Already at max positions ({open_positions}/{params['max_positions']})"
            )
        
        # Check 4: Sector exposure (JOIN with securities and sectors)
        sector_info = await conn.fetchrow("""
            SELECT 
                sec.sector_name,
                sec.sector_id
            FROM securities s
            JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE s.security_id = $1
        """, security_id)
        
        sector_exposure_pct = 0.0
        if sector_info:
            # Calculate current sector exposure
            sector_data = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as position_count,
                    COALESCE(SUM(p.quantity * p.entry_price), 0) as total_exposure
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                WHERE p.cycle_id = $1
                AND p.status = 'open'
                AND s.sector_id = $2
            """, cycle_id, sector_info['sector_id'])
            
            # Get total capital (sum of all positions)
            total_capital = await conn.fetchval("""
                SELECT COALESCE(SUM(quantity * entry_price), 0)
                FROM positions
                WHERE cycle_id = $1
                AND status = 'open'
            """, cycle_id)
            
            if total_capital > 0:
                current_sector_exposure = float(sector_data['total_exposure'])
                new_total = total_capital + position_size
                new_sector_total = current_sector_exposure + position_size
                sector_exposure_pct = new_sector_total / new_total
                
                if sector_exposure_pct > params['max_sector_exposure_pct']:
                    violations.append(
                        f"Sector {sector_info['sector_name']} exposure {sector_exposure_pct:.1%} "
                        f"exceeds max {params['max_sector_exposure_pct']:.1%}"
                    )
        
        # Check 5: Daily loss limit
        daily_pnl = await conn.fetchval("""
            SELECT COALESCE(SUM(realized_pnl), 0) + COALESCE(SUM(unrealized_pnl), 0)
            FROM positions
            WHERE cycle_id = $1
            AND DATE(created_at) = CURRENT_DATE
        """, cycle_id) or 0.0
        
        if daily_pnl < -params['max_daily_loss_usd']:
            violations.append(
                f"Daily loss ${abs(daily_pnl):.2f} exceeds max ${params['max_daily_loss_usd']:.2f}"
            )
        
        # Determine risk level
        if violations:
            risk_level = RiskLevel.CRITICAL
            approved = False
            
            # Log risk event
            await log_risk_event(
                conn,
                cycle_id,
                RiskEventType.POSITION_LIMIT,
                risk_level,
                f"Position rejected for {request.symbol}: {'; '.join(violations)}",
                {
                    'symbol': request.symbol,
                    'position_size': position_size,
                    'violations': violations
                }
            )
        elif warnings:
            risk_level = RiskLevel.MEDIUM
            approved = True
        else:
            risk_level = RiskLevel.LOW
            approved = True
        
        logger.info(
            f"Risk check for {request.symbol}: approved={approved}, "
            f"risk_level={risk_level.value}, violations={len(violations)}"
        )
        
        return RiskCheckResult(
            approved=approved,
            risk_level=risk_level,
            violations=violations,
            warnings=warnings,
            position_size_usd=position_size,
            risk_amount_usd=risk_amount,
            risk_reward_ratio=risk_reward_ratio,
            sector_exposure_pct=sector_exposure_pct,
            daily_pnl=float(daily_pnl)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in risk check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/risk/sector-exposure")
async def get_sector_exposure(
    cycle_id: int,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Get sector exposure breakdown using JOINs.
    
    v5.0 Pattern:
    - JOIN positions → securities → sectors
    - Calculate exposure per sector
    """
    try:
        exposure = await conn.fetch("""
            SELECT 
                sec.sector_name,
                COUNT(p.position_id) as position_count,
                SUM(p.quantity * p.entry_price) as total_exposure,
                SUM(p.unrealized_pnl) as total_pnl
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND p.status = 'open'
            GROUP BY sec.sector_name, sec.sector_id
            ORDER BY total_exposure DESC
        """, cycle_id)
        
        # Calculate total capital
        total_capital = await conn.fetchval("""
            SELECT COALESCE(SUM(quantity * entry_price), 0)
            FROM positions
            WHERE cycle_id = $1
            AND status = 'open'
        """, cycle_id) or 1.0  # Avoid division by zero
        
        results = []
        for row in exposure:
            results.append({
                'sector_name': row['sector_name'],
                'position_count': row['position_count'],
                'total_exposure_usd': float(row['total_exposure'] or 0),
                'total_pnl': float(row['total_pnl'] or 0),
                'exposure_pct': float(row['total_exposure'] or 0) / total_capital
            })
        
        return {
            "cycle_id": cycle_id,
            "total_capital_usd": float(total_capital),
            "sectors": results
        }
    
    except Exception as e:
        logger.error(f"Error fetching sector exposure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/risk/positions")
async def get_position_risk(
    cycle_id: int,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Get risk metrics for all open positions.
    
    v5.0 Pattern:
    - JOIN positions → securities → sectors
    """
    try:
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
                p.risk_amount,
                p.unrealized_pnl,
                p.realized_pnl,
                (p.risk_amount / (p.entry_price * p.quantity)) * 100 as risk_percent,
                p.created_at
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND p.status = 'open'
            ORDER BY p.risk_amount DESC
        """, cycle_id)
        
        return {
            "cycle_id": cycle_id,
            "count": len(positions),
            "positions": [dict(r) for r in positions]
        }
    
    except Exception as e:
        logger.error(f"Error fetching position risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/risk/daily-limits")
async def get_daily_limits(
    cycle_id: int,
    conn: asyncpg.Connection = Depends(get_db)
):
    """Check daily risk limits"""
    try:
        params = await get_risk_parameters(conn, cycle_id)
        
        # Get today's metrics
        metrics = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'open') as open_positions,
                COALESCE(SUM(risk_amount) FILTER (WHERE status = 'open'), 0) as total_risk,
                COALESCE(SUM(unrealized_pnl) FILTER (WHERE status = 'open'), 0) as unrealized_pnl,
                COALESCE(SUM(realized_pnl), 0) as realized_pnl,
                COALESCE(SUM(realized_pnl) + SUM(unrealized_pnl), 0) as total_pnl
            FROM positions
            WHERE cycle_id = $1
            AND DATE(created_at) = CURRENT_DATE
        """, cycle_id)
        
        daily_pnl = float(metrics['total_pnl'] or 0)
        
        return {
            "cycle_id": cycle_id,
            "date": date.today().isoformat(),
            "limits": {
                "max_positions": params['max_positions'],
                "max_position_size_usd": params['max_position_size_usd'],
                "max_daily_loss_usd": params['max_daily_loss_usd'],
                "max_sector_exposure_pct": params['max_sector_exposure_pct']
            },
            "current": {
                "open_positions": metrics['open_positions'],
                "total_risk_usd": float(metrics['total_risk']),
                "unrealized_pnl": float(metrics['unrealized_pnl']),
                "realized_pnl": float(metrics['realized_pnl']),
                "total_pnl": daily_pnl
            },
            "status": {
                "positions_ok": metrics['open_positions'] < params['max_positions'],
                "daily_loss_ok": daily_pnl > -params['max_daily_loss_usd']
            }
        }
    
    except Exception as e:
        logger.error(f"Error fetching daily limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/risk/update-daily-metrics")
async def update_daily_metrics(
    cycle_id: int,
    conn: asyncpg.Connection = Depends(get_db)
):
    """Update daily risk metrics table"""
    try:
        # Calculate today's metrics
        metrics = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'open') as open_positions,
                COUNT(*) FILTER (WHERE status = 'closed') as closed_positions,
                COALESCE(SUM(realized_pnl), 0) as total_realized_pnl,
                COALESCE(SUM(unrealized_pnl) FILTER (WHERE status = 'open'), 0) as total_unrealized_pnl,
                COUNT(*) FILTER (WHERE realized_pnl > 0) as winning_trades,
                COUNT(*) FILTER (WHERE realized_pnl < 0) as losing_trades,
                MAX(realized_pnl) as largest_win,
                MIN(realized_pnl) as largest_loss
            FROM positions
            WHERE cycle_id = $1
            AND DATE(created_at) = CURRENT_DATE
        """, cycle_id)
        
        # Insert or update daily metrics
        await conn.execute("""
            INSERT INTO daily_risk_metrics (
                cycle_id, date, 
                total_positions_opened, positions_closed,
                total_realized_pnl, total_unrealized_pnl,
                winning_trades, losing_trades,
                largest_win, largest_loss,
                created_at
            ) VALUES (
                $1, CURRENT_DATE, $2, $3, $4, $5, $6, $7, $8, $9, NOW()
            )
            ON CONFLICT (cycle_id, date) DO UPDATE SET
                total_positions_opened = EXCLUDED.total_positions_opened,
                positions_closed = EXCLUDED.positions_closed,
                total_realized_pnl = EXCLUDED.total_realized_pnl,
                total_unrealized_pnl = EXCLUDED.total_unrealized_pnl,
                winning_trades = EXCLUDED.winning_trades,
                losing_trades = EXCLUDED.losing_trades,
                largest_win = EXCLUDED.largest_win,
                largest_loss = EXCLUDED.largest_loss
        """,
            cycle_id,
            metrics['open_positions'] + metrics['closed_positions'],
            metrics['closed_positions'],
            metrics['total_realized_pnl'],
            metrics['total_unrealized_pnl'],
            metrics['winning_trades'],
            metrics['losing_trades'],
            metrics['largest_win'],
            metrics['largest_loss']
        )
        
        logger.info(f"✅ Updated daily metrics for cycle {cycle_id}")
        
        return {"success": True, "metrics": dict(metrics)}
    
    except Exception as e:
        logger.error(f"Error updating daily metrics: {e}")
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
        "features": [
            "Position size limits",
            "Sector exposure tracking (via JOINs)",
            "Daily loss limits",
            "Risk/reward validation",
            "Real-time risk monitoring"
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
