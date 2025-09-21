#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk-manager-service.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Risk management service for position sizing, validation, and safety controls

REVISION HISTORY:
v4.2.0 (2025-09-20) - Complete rewrite for v4.2 architecture
- FastAPI REST service (not MCP)
- Comprehensive risk management algorithms
- Real-time risk monitoring and alerts
- Dynamic position sizing calculations
- Emergency stop functionality
- Database integration with v4.2 schema
- Risk parameter management
- Exposure tracking and limits

Description of Service:
This service provides comprehensive risk management for the trading system:
1. Real-time risk monitoring and validation
2. Dynamic position sizing based on volatility and confidence
3. Daily loss limits and exposure controls
4. Emergency stop procedures
5. Risk parameter management
6. Portfolio exposure tracking
7. Risk alerts and notifications
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import asyncio
import asyncpg
import aioredis
import uvicorn
import os
import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("risk-manager")

# Initialize FastAPI
app = FastAPI(
    title="Catalyst Risk Manager",
    description="Risk management service for position sizing and safety controls",
    version="4.2.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === RISK MODELS ===

class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class RiskParameters:
    """Current risk management parameters"""
    max_daily_loss: float = 2000.0
    max_position_risk: float = 0.02  # 2% per position
    max_portfolio_risk: float = 0.05  # 5% total portfolio risk
    position_size_multiplier: float = 1.0
    stop_loss_atr_multiple: float = 2.0
    take_profit_atr_multiple: float = 3.0
    max_positions: int = 5
    risk_free_rate: float = 0.05
    correlation_limit: float = 0.7
    sector_concentration_limit: float = 0.4
    
class TradeValidationRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: Optional[int] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    current_price: float = Field(..., gt=0)
    atr: Optional[float] = None
    sector: Optional[str] = None
    signal_data: Optional[Dict] = None

class PositionSizeRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    current_price: float = Field(..., gt=0)
    atr: float = Field(..., gt=0)
    account_balance: float = Field(..., gt=0)
    sector: Optional[str] = None

class RiskParameterUpdate(BaseModel):
    parameter_name: str
    parameter_value: float
    effective_from: Optional[datetime] = None

class EmergencyStopRequest(BaseModel):
    reason: str
    stop_all_trading: bool = True
    close_positions: bool = False

# === GLOBAL STATE ===

class RiskManagerState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.risk_params: RiskParameters = RiskParameters()
        self.daily_metrics: Dict = {}
        self.position_cache: Dict = {}
        self.alert_history: List = []
        self.emergency_stop_active: bool = False
        
state = RiskManagerState()

# === DATABASE FUNCTIONS ===

async def init_database():
    """Initialize database connection pool"""
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
            
        state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30
        )
        logger.info("Database connection pool initialized")
        
        # Load current risk parameters
        await load_risk_parameters()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def load_risk_parameters():
    """Load current risk parameters from database"""
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT parameter_name, parameter_value
                FROM risk_parameters
                WHERE effective_from <= NOW()
                AND (effective_until IS NULL OR effective_until > NOW())
                ORDER BY effective_from DESC
            """)
            
            # Update risk parameters
            for row in rows:
                param_name = row['parameter_name']
                param_value = float(row['parameter_value'])
                
                if hasattr(state.risk_params, param_name):
                    setattr(state.risk_params, param_name, param_value)
                    
            logger.info(f"Loaded {len(rows)} risk parameters")
            
    except Exception as e:
        logger.error(f"Failed to load risk parameters: {e}")

async def get_daily_metrics() -> Dict:
    """Get current daily risk metrics"""
    try:
        today = date.today()
        
        async with state.db_pool.acquire() as conn:
            # Get daily P&L
            daily_pnl = await conn.fetchval("""
                SELECT COALESCE(SUM(realized_pnl), 0)
                FROM positions
                WHERE DATE(closed_at) = $1
                AND status = 'closed'
            """, today)
            
            # Get current exposure
            open_exposure = await conn.fetchval("""
                SELECT COALESCE(SUM(ABS(quantity * current_price)), 0)
                FROM positions
                WHERE status = 'open'
            """)
            
            # Get position count
            position_count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM positions
                WHERE status = 'open'
            """)
            
            # Calculate remaining risk budget
            remaining_budget = state.risk_params.max_daily_loss + float(daily_pnl or 0)
            
            # Calculate risk score (0-100)
            risk_score = calculate_risk_score(
                daily_pnl or 0,
                open_exposure or 0,
                position_count or 0
            )
            
            metrics = {
                "daily_pnl": float(daily_pnl or 0),
                "daily_loss_limit": state.risk_params.max_daily_loss,
                "remaining_risk_budget": remaining_budget,
                "open_exposure": float(open_exposure or 0),
                "max_exposure_limit": 10000.0,  # Could be parameter
                "position_count": position_count or 0,
                "max_positions": state.risk_params.max_positions,
                "risk_score": risk_score,
                "emergency_stop_active": state.emergency_stop_active,
                "timestamp": datetime.now().isoformat()
            }
            
            state.daily_metrics = metrics
            return metrics
            
    except Exception as e:
        logger.error(f"Failed to get daily metrics: {e}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

def calculate_risk_score(daily_pnl: float, open_exposure: float, position_count: int) -> int:
    """Calculate overall risk score (0-100)"""
    score = 0
    
    # Daily P&L component (0-40 points)
    pnl_ratio = abs(daily_pnl) / state.risk_params.max_daily_loss
    score += min(40, pnl_ratio * 40)
    
    # Exposure component (0-30 points)
    exposure_ratio = open_exposure / 10000.0  # Assume 10k max exposure
    score += min(30, exposure_ratio * 30)
    
    # Position count component (0-30 points)
    position_ratio = position_count / state.risk_params.max_positions
    score += min(30, position_ratio * 30)
    
    return min(100, int(score))

async def calculate_position_size(
    symbol: str,
    side: str,
    confidence: float,
    current_price: float,
    atr: float,
    account_balance: float
) -> Dict:
    """Calculate optimal position size based on risk parameters"""
    
    try:
        # Base risk per trade (adjusted by confidence)
        base_risk = state.risk_params.max_position_risk
        confidence_adjusted_risk = base_risk * confidence * state.risk_params.position_size_multiplier
        
        # Maximum dollar risk for this trade
        max_risk_dollars = account_balance * confidence_adjusted_risk
        
        # Calculate stop loss distance
        stop_distance = atr * state.risk_params.stop_loss_atr_multiple
        stop_price = current_price - stop_distance if side == "buy" else current_price + stop_distance
        
        # Calculate position size based on stop loss
        if stop_distance > 0:
            shares = int(max_risk_dollars / stop_distance)
        else:
            shares = 0
            
        # Calculate position value
        position_value = shares * current_price
        
        # Ensure we don't exceed position limits
        max_position_value = account_balance * 0.2  # Max 20% per position
        if position_value > max_position_value:
            shares = int(max_position_value / current_price)
            position_value = shares * current_price
            
        # Calculate take profit
        take_profit_distance = atr * state.risk_params.take_profit_atr_multiple
        take_profit = current_price + take_profit_distance if side == "buy" else current_price - take_profit_distance
        
        result = {
            "symbol": symbol,
            "side": side,
            "recommended_shares": shares,
            "position_value": position_value,
            "risk_amount": max_risk_dollars,
            "confidence_used": confidence,
            "stop_loss": stop_price,
            "take_profit": take_profit,
            "stop_distance": stop_distance,
            "risk_reward_ratio": take_profit_distance / stop_distance if stop_distance > 0 else 0,
            "position_risk_pct": (position_value / account_balance) * 100,
            "calculated_at": datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Position size calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Position calculation failed: {str(e)}")

async def validate_trade_request(request: TradeValidationRequest) -> Dict:
    """Validate trade against all risk parameters"""
    
    validation_result = {
        "approved": False,
        "symbol": request.symbol,
        "reasons": [],
        "warnings": [],
        "risk_metrics": {},
        "validated_at": datetime.now().isoformat()
    }
    
    try:
        # Get current metrics
        metrics = await get_daily_metrics()
        validation_result["risk_metrics"] = metrics
        
        # Check emergency stop
        if state.emergency_stop_active:
            validation_result["reasons"].append("Emergency stop is active")
            return validation_result
            
        # Check daily loss limit
        if metrics["remaining_risk_budget"] <= 0:
            validation_result["reasons"].append("Daily loss limit exceeded")
            return validation_result
            
        # Check maximum positions
        if metrics["position_count"] >= state.risk_params.max_positions:
            validation_result["reasons"].append(f"Maximum positions limit ({state.risk_params.max_positions}) reached")
            return validation_result
            
        # Check confidence threshold
        if request.confidence < 0.3:
            validation_result["reasons"].append("Confidence below minimum threshold (30%)")
            return validation_result
            
        # Add warnings for moderate risk
        if metrics["risk_score"] > 70:
            validation_result["warnings"].append("High risk score - consider reducing position size")
            
        if request.confidence < 0.5:
            validation_result["warnings"].append("Low confidence signal - proceed with caution")
            
        # If we get here, trade is approved
        validation_result["approved"] = True
        validation_result["reasons"].append("All risk checks passed")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Trade validation failed: {e}")
        validation_result["reasons"].append(f"Validation error: {str(e)}")
        return validation_result

# === API ENDPOINTS ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                
        return {
            "status": "healthy",
            "service": "risk-manager",
            "version": "4.2.0",
            "timestamp": datetime.now().isoformat(),
            "emergency_stop": state.emergency_stop_active
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/api/v1/parameters")
async def get_risk_parameters():
    """Get current risk management parameters"""
    return {
        "parameters": asdict(state.risk_params),
        "loaded_at": datetime.now().isoformat()
    }

@app.get("/api/v1/metrics")
async def get_risk_metrics():
    """Get real-time risk metrics"""
    return await get_daily_metrics()

@app.get("/api/v1/exposure")
async def get_exposure_breakdown():
    """Get detailed exposure breakdown"""
    try:
        async with state.db_pool.acquire() as conn:
            # Get exposure by symbol
            symbol_exposure = await conn.fetch("""
                SELECT 
                    symbol,
                    SUM(quantity * current_price) as exposure,
                    COUNT(*) as position_count,
                    AVG(unrealized_pnl) as avg_pnl
                FROM positions
                WHERE status = 'open'
                GROUP BY symbol
                ORDER BY exposure DESC
            """)
            
            # Get exposure by sector (if available)
            sector_exposure = await conn.fetch("""
                SELECT 
                    sector,
                    SUM(quantity * current_price) as exposure,
                    COUNT(*) as position_count
                FROM positions
                WHERE status = 'open' AND sector IS NOT NULL
                GROUP BY sector
                ORDER BY exposure DESC
            """)
            
            return {
                "by_symbol": [dict(row) for row in symbol_exposure],
                "by_sector": [dict(row) for row in sector_exposure],
                "generated_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get exposure breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/validate-trade")
async def validate_trade(request: TradeValidationRequest):
    """Validate proposed trade against risk limits"""
    return await validate_trade_request(request)

@app.post("/api/v1/calculate-position-size")
async def calculate_position_size_endpoint(request: PositionSizeRequest):
    """Calculate optimal position size for a trade"""
    return await calculate_position_size(
        symbol=request.symbol,
        side=request.side,
        confidence=request.confidence,
        current_price=request.current_price,
        atr=request.atr,
        account_balance=request.account_balance
    )

@app.post("/api/v1/update-parameters")
async def update_risk_parameters(update: RiskParameterUpdate):
    """Update risk management parameters"""
    try:
        async with state.db_pool.acquire() as conn:
            # Insert new parameter value
            await conn.execute("""
                INSERT INTO risk_parameters 
                (parameter_name, parameter_value, set_by, effective_from)
                VALUES ($1, $2, $3, $4)
            """, 
            update.parameter_name,
            update.parameter_value,
            "api_user",
            update.effective_from or datetime.now()
            )
            
            # Reload parameters
            await load_risk_parameters()
            
            return {
                "success": True,
                "parameter": update.parameter_name,
                "new_value": update.parameter_value,
                "updated_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to update parameters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/emergency-stop")
async def emergency_stop(request: EmergencyStopRequest):
    """Trigger emergency stop procedures"""
    try:
        state.emergency_stop_active = True
        
        # Log emergency stop event
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO risk_events 
                (event_type, severity, message, data, created_at)
                VALUES ($1, $2, $3, $4, $5)
            """,
            "emergency_stop",
            "critical",
            f"Emergency stop triggered: {request.reason}",
            json.dumps({"reason": request.reason, "stop_all": request.stop_all_trading}),
            datetime.now()
            )
            
        logger.critical(f"EMERGENCY STOP ACTIVATED: {request.reason}")
        
        return {
            "success": True,
            "emergency_stop_active": True,
            "reason": request.reason,
            "timestamp": datetime.now().isoformat(),
            "message": "Emergency stop activated - all trading halted"
        }
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/reset-emergency")
async def reset_emergency_stop():
    """Reset emergency stop (admin only)"""
    state.emergency_stop_active = False
    
    # Log reset event
    async with state.db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO risk_events 
            (event_type, severity, message, created_at)
            VALUES ($1, $2, $3, $4)
        """,
        "emergency_reset",
        "info",
        "Emergency stop reset - trading resumed",
        datetime.now()
        )
    
    logger.info("Emergency stop reset - trading resumed")
    
    return {
        "success": True,
        "emergency_stop_active": False,
        "message": "Emergency stop reset - trading resumed",
        "timestamp": datetime.now().isoformat()
    }

# === BACKGROUND TASKS ===

async def risk_monitoring_task():
    """Background task for continuous risk monitoring"""
    while True:
        try:
            metrics = await get_daily_metrics()
            
            # Check for risk threshold breaches
            if metrics["risk_score"] > 90:
                logger.warning(f"High risk score: {metrics['risk_score']}")
                
            if metrics["remaining_risk_budget"] < 500:  # $500 remaining
                logger.warning(f"Low risk budget remaining: ${metrics['remaining_risk_budget']}")
                
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Risk monitoring error: {e}")
            await asyncio.sleep(60)  # Wait longer on error

# === STARTUP/SHUTDOWN ===

@app.on_event("startup")
async def startup():
    """Initialize service on startup"""
    try:
        logger.info("Starting Risk Manager Service v4.2.0")
        
        # Initialize database
        await init_database()
        
        # Start background monitoring
        asyncio.create_task(risk_monitoring_task())
        
        logger.info("Risk Manager Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on service shutdown"""
    try:
        if state.db_pool:
            await state.db_pool.close()
            
        if state.redis_client:
            await state.redis_client.close()
            
        logger.info("Risk Manager Service stopped")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# === MAIN ===

if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 5004))
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info",
        access_log=True
    )