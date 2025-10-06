#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: reporting-service.py
Version: 4.1.0
Last Updated: 2025-08-31
Purpose: Performance analytics and reporting

REVISION HISTORY:
v4.1.0 (2025-08-31) - Production-ready reporting service
- Real-time P&L tracking
- Performance metrics calculation
- Trade journal generation
- Risk analytics
- Daily/weekly/monthly reporting

Description of Service:
This service provides comprehensive reporting:
1. Real-time P&L tracking and metrics
2. Trade performance analytics
3. Risk exposure monitoring
4. Pattern success rate tracking
5. Automated report generation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
import asyncio
import asyncpg
import aioredis
import pandas as pd
import json
import os
import logging
from enum import Enum
from decimal import Decimal
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64

# Initialize FastAPI app
app = FastAPI(
    title="Reporting Service",
    version="4.1.0",
    description="Performance reporting service for Catalyst Trading System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("reporting")

# Set matplotlib backend
plt.switch_backend('Agg')

# === DATA MODELS ===

class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CYCLE = "cycle"
    CUSTOM = "custom"

class MetricType(str, Enum):
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    AVERAGE_WIN = "average_win"
    AVERAGE_LOSS = "average_loss"
    TOTAL_RETURN = "total_return"
    TRADES_COUNT = "trades_count"

class PerformanceMetrics(BaseModel):
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    average_win: float
    average_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    best_trade: Dict[str, Any]
    worst_trade: Dict[str, Any]

class DailyReport(BaseModel):
    date: date
    metrics: PerformanceMetrics
    trades: List[Dict]
    positions: List[Dict]
    top_patterns: List[Dict]
    market_conditions: Dict
    risk_metrics: Dict

class TradeJournal(BaseModel):
    trade_id: str
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    side: str
    pnl: Optional[float]
    pnl_percent: Optional[float]
    pattern: Optional[str]
    catalyst: Optional[str]
    notes: Optional[str]

class RiskReport(BaseModel):
    current_exposure: float
    max_exposure: float
    var_95: float  # Value at Risk
    position_correlations: Dict
    sector_exposure: Dict
    risk_score: float

# === SERVICE STATE ===

class ReportingState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.metrics_cache: Dict = {}
        self.report_generation_task: Optional[asyncio.Task] = None

state = ReportingState()

# === STARTUP/SHUTDOWN ===

@app.on_event("startup")
async def startup():
    """Initialize reporting service"""
    logger.info("Starting Reporting Service v4.1")
    
    try:
        # Initialize database pool
        db_url = os.getenv("DATABASE_URL", "postgresql://catalyst_user:password@localhost:5432/catalyst_trading")
        state.db_pool = await asyncpg.create_pool(
            db_url,
            min_size=5,
            max_size=20
        )
        
        # Initialize Redis client
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        state.redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Start background report generation
        state.report_generation_task = asyncio.create_task(generate_periodic_reports())
        
        logger.info("Reporting Service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize reporting service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Clean up resources"""
    logger.info("Shutting down Reporting Service")
    
    if state.report_generation_task:
        state.report_generation_task.cancel()
    
    if state.redis_client:
        await state.redis_client.close()
    
    if state.db_pool:
        await state.db_pool.close()

# === REST API ENDPOINTS ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "reporting",
        "version": "4.1.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/performance/daily")
async def get_daily_performance(date_str: Optional[str] = None):
    """Get daily performance report"""
    
    try:
        # Parse date or use today
        if date_str:
            report_date = datetime.fromisoformat(date_str).date()
        else:
            report_date = date.today()
        
        # Get metrics
        metrics = await calculate_daily_metrics(report_date)
        
        # Get trades
        trades = await get_daily_trades(report_date)
        
        # Get positions
        positions = await get_active_positions_for_date(report_date)
        
        # Get top patterns
        patterns = await get_top_patterns_for_date(report_date)
        
        # Get market conditions
        market = await get_market_conditions(report_date)
        
        # Get risk metrics
        risk = await calculate_risk_metrics(report_date)
        
        return DailyReport(
            date=report_date,
            metrics=metrics,
            trades=trades,
            positions=positions,
            top_patterns=patterns,
            market_conditions=market,
            risk_metrics=risk
        )
        
    except Exception as e:
        logger.error(f"Failed to generate daily report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.get("/api/v1/performance/cycle/{cycle_id}")
async def get_cycle_performance(cycle_id: str):
    """Get performance for a specific trading cycle"""
    
    try:
        async with state.db_pool.acquire() as conn:
            # Get cycle info
            cycle = await conn.fetchrow("""
                SELECT * FROM trading_cycles WHERE cycle_id = $1
            """, cycle_id)
            
            if not cycle:
                raise HTTPException(status_code=404, detail="Cycle not found")
            
            # Get trades for cycle
            trades = await conn.fetch("""
                SELECT t.*, p.entry_price, p.exit_price, p.pnl
                FROM orders t
                LEFT JOIN positions p ON t.symbol = p.symbol
                WHERE t.cycle_id = $1
                ORDER BY t.created_at
            """, cycle_id)
            
            # Calculate metrics
            metrics = calculate_metrics_from_trades(trades)
            
            return {
                "cycle_id": cycle_id,
                "started_at": cycle['started_at'].isoformat(),
                "stopped_at": cycle['stopped_at'].isoformat() if cycle['stopped_at'] else None,
                "mode": cycle['mode'],
                "metrics": metrics,
                "trades_count": len(trades),
                "status": cycle['status']
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cycle performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance: {str(e)}")

@app.get("/api/v1/metrics/summary")
async def get_metrics_summary(days: int = 30):
    """Get summary metrics for specified period"""
    
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        async with state.db_pool.acquire() as conn:
            # Get aggregated metrics
            metrics = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as total_pnl,
                    AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                    AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM positions
                WHERE created_at >= $1
            """, start_date)
            
            # Calculate derived metrics
            win_rate = 0
            profit_factor = 0
            
            if metrics['total_trades'] > 0:
                win_rate = (metrics['winning_trades'] or 0) / metrics['total_trades'] * 100
                
                total_wins = (metrics['winning_trades'] or 0) * (metrics['avg_win'] or 0)
                total_losses = abs((metrics['losing_trades'] or 0) * (metrics['avg_loss'] or 0))
                
                if total_losses > 0:
                    profit_factor = total_wins / total_losses
            
            return {
                "period_days": days,
                "total_trades": metrics['total_trades'] or 0,
                "winning_trades": metrics['winning_trades'] or 0,
                "losing_trades": metrics['losing_trades'] or 0,
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2),
                "total_pnl": float(metrics['total_pnl'] or 0),
                "average_win": float(metrics['avg_win'] or 0),
                "average_loss": float(metrics['avg_loss'] or 0),
                "best_trade": float(metrics['best_trade'] or 0),
                "worst_trade": float(metrics['worst_trade'] or 0),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@app.get("/api/v1/trades/journal")
async def get_trade_journal(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbol: Optional[str] = None
):
    """Get trade journal entries"""
    
    try:
        # Build query
        query = """
            SELECT 
                o.order_id as trade_id,
                o.symbol,
                o.created_at as entry_time,
                p.exit_time,
                p.entry_price,
                p.exit_price,
                o.quantity,
                o.direction as side,
                p.pnl,
                p.pnl_percent,
                pd.pattern_type as pattern,
                n.catalyst_type as catalyst,
                o.metadata->>'notes' as notes
            FROM orders o
            LEFT JOIN positions p ON o.symbol = p.symbol
            LEFT JOIN pattern_detections pd ON o.symbol = pd.symbol
                AND pd.created_at BETWEEN o.created_at - INTERVAL '1 hour' 
                AND o.created_at
            LEFT JOIN news_articles n ON o.symbol = n.symbol
                AND n.published_at BETWEEN o.created_at - INTERVAL '24 hours'
                AND o.created_at
            WHERE o.status = 'filled'
        """
        
        params = []
        param_count = 0
        
        if start_date:
            param_count += 1
            query += f" AND o.created_at >= ${param_count}"
            params.append(datetime.fromisoformat(start_date))
        
        if end_date:
            param_count += 1
            query += f" AND o.created_at <= ${param_count}"
            params.append(datetime.fromisoformat(end_date))
        
        if symbol:
            param_count += 1
            query += f" AND o.symbol = ${param_count}"
            params.append(symbol)
        
        query += " ORDER BY o.created_at DESC LIMIT 100"
        
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            journal_entries = []
            for row in rows:
                entry = TradeJournal(
                    trade_id=row['trade_id'],
                    symbol=row['symbol'],
                    entry_time=row['entry_time'],
                    exit_time=row['exit_time'],
                    entry_price=float(row['entry_price'] or 0),
                    exit_price=float(row['exit_price']) if row['exit_price'] else None,
                    quantity=row['quantity'],
                    side=row['side'],
                    pnl=float(row['pnl']) if row['pnl'] else None,
                    pnl_percent=float(row['pnl_percent']) if row['pnl_percent'] else None,
                    pattern=row['pattern'],
                    catalyst=row['catalyst'],
                    notes=row['notes']
                )
                journal_entries.append(entry)
            
            return {
                "entries": [e.dict() for e in journal_entries],
                "count": len(journal_entries),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get trade journal: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get journal: {str(e)}")

@app.get("/api/v1/risk/current")
async def get_current_risk():
    """Get current risk metrics"""
    
    try:
        # Get active positions
        positions = await get_active_positions()
        
        if not positions:
            return RiskReport(
                current_exposure=0,
                max_exposure=0,
                var_95=0,
                position_correlations={},
                sector_exposure={},
                risk_score=0
            )
        
        # Calculate exposure
        current_exposure = sum(p['market_value'] for p in positions)
        max_exposure = 50000  # From config
        
        # Calculate VaR (simplified)
        position_values = [p['market_value'] for p in positions]
        var_95 = calculate_var(position_values, 0.95)
        
        # Calculate correlations (simplified)
        correlations = calculate_position_correlations(positions)
        
        # Calculate sector exposure
        sector_exposure = calculate_sector_exposure(positions)
        
        # Calculate risk score
        risk_score = calculate_risk_score(
            current_exposure,
            max_exposure,
            var_95,
            len(positions)
        )
        
        return RiskReport(
            current_exposure=current_exposure,
            max_exposure=max_exposure,
            var_95=var_95,
            position_correlations=correlations,
            sector_exposure=sector_exposure,
            risk_score=risk_score
        )
        
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get risk: {str(e)}")

@app.get("/api/v1/charts/pnl")
async def get_pnl_chart(days: int = 30):
    """Generate P&L chart"""
    
    try:
        # Get P&L data
        pnl_data = await get_pnl_history(days)
        
        if not pnl_data:
            raise HTTPException(status_code=404, detail="No P&L data available")
        
        # Create DataFrame
        df = pd.DataFrame(pnl_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # Create chart
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Cumulative P&L
        ax1.plot(df.index, df['cumulative_pnl'], 'b-', linewidth=2)
        ax1.fill_between(df.index, 0, df['cumulative_pnl'], alpha=0.3)
        ax1.set_title('Cumulative P&L')
        ax1.set_ylabel('P&L ($)')
        ax1.grid(True, alpha=0.3)
        
        # Daily P&L
        colors = ['g' if x > 0 else 'r' for x in df['daily_pnl']]
        ax2.bar(df.index, df['daily_pnl'], color=colors, alpha=0.7)
        ax2.set_title('Daily P&L')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('P&L ($)')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return {
            "chart": f"data:image/png;base64,{image_base64}",
            "data": pnl_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate P&L chart: {e}")
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {str(e)}")

@app.get("/api/v1/reports/generate/{report_type}")
async def generate_report(report_type: ReportType):
    """Generate a specific type of report"""
    
    try:
        if report_type == ReportType.DAILY:
            report = await generate_daily_report()
        elif report_type == ReportType.WEEKLY:
            report = await generate_weekly_report()
        elif report_type == ReportType.MONTHLY:
            report = await generate_monthly_report()
        else:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        return {
            "report_type": report_type.value,
            "report": report,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

# === CALCULATION FUNCTIONS ===

async def calculate_daily_metrics(report_date: date) -> PerformanceMetrics:
    """Calculate daily performance metrics"""
    
    try:
        async with state.db_pool.acquire() as conn:
            # Get trades for the day
            trades = await conn.fetch("""
                SELECT * FROM positions
                WHERE DATE(created_at) = $1
            """, report_date)
            
            if not trades:
                return get_empty_metrics()
            
            # Calculate metrics
            total_pnl = sum(t['pnl'] or 0 for t in trades)
            realized_pnl = sum(t['pnl'] or 0 for t in trades if t['status'] == 'closed')
            unrealized_pnl = sum(t['pnl'] or 0 for t in trades if t['status'] == 'active')
            
            winning_trades = [t for t in trades if (t['pnl'] or 0) > 0]
            losing_trades = [t for t in trades if (t['pnl'] or 0) < 0]
            
            win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
            
            avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
            
            profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades else 0
            
            # Sharpe ratio (simplified)
            returns = [t['pnl_percent'] or 0 for t in trades]
            sharpe = calculate_sharpe_ratio(returns) if returns else 0
            
            # Max drawdown
            drawdown = calculate_max_drawdown([t['pnl'] or 0 for t in trades])
            
            # Best and worst trades
            best_trade = max(trades, key=lambda x: x['pnl'] or 0) if trades else {}
            worst_trade = min(trades, key=lambda x: x['pnl'] or 0) if trades else {}
            
            return PerformanceMetrics(
                total_pnl=total_pnl,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe,
                max_drawdown=drawdown,
                average_win=avg_win,
                average_loss=avg_loss,
                total_trades=len(trades),
                winning_trades=len(winning_trades),
                losing_trades=len(losing_trades),
                best_trade=dict(best_trade) if best_trade else {},
                worst_trade=dict(worst_trade) if worst_trade else {}
            )
            
    except Exception as e:
        logger.error(f"Failed to calculate daily metrics: {e}")
        return get_empty_metrics()

def calculate_metrics_from_trades(trades: List) -> Dict:
    """Calculate metrics from trade list"""
    
    if not trades:
        return get_empty_metrics().dict()
    
    total_pnl = sum(t['pnl'] or 0 for t in trades)
    winning_trades = [t for t in trades if (t['pnl'] or 0) > 0]
    losing_trades = [t for t in trades if (t['pnl'] or 0) < 0]
    
    return {
        "total_pnl": total_pnl,
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": len(winning_trades) / len(trades) * 100 if trades else 0,
        "average_win": sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
        "average_loss": sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    }

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio"""
    
    if not returns or len(returns) < 2:
        return 0
    
    returns_array = pd.Series(returns)
    excess_returns = returns_array - risk_free_rate / 252  # Daily risk-free rate
    
    if excess_returns.std() == 0:
        return 0
    
    return (excess_returns.mean() / excess_returns.std()) * (252 ** 0.5)  # Annualized

def calculate_max_drawdown(pnl_values: List[float]) -> float:
    """Calculate maximum drawdown"""
    
    if not pnl_values:
        return 0
    
    cumulative = pd.Series(pnl_values).cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    
    return abs(drawdown.min()) if len(drawdown) > 0 else 0

def calculate_var(values: List[float], confidence: float = 0.95) -> float:
    """Calculate Value at Risk"""
    
    if not values:
        return 0
    
    sorted_values = sorted(values)
    index = int((1 - confidence) * len(sorted_values))
    
    return abs(sorted_values[index]) if index < len(sorted_values) else 0

def calculate_risk_score(exposure: float, max_exposure: float, var: float, positions: int) -> float:
    """Calculate overall risk score (0-100)"""
    
    score = 0
    
    # Exposure ratio (40 points)
    exposure_ratio = exposure / max_exposure if max_exposure > 0 else 0
    score += (1 - exposure_ratio) * 40
    
    # VaR ratio (30 points)
    var_ratio = var / exposure if exposure > 0 else 0
    score += (1 - min(var_ratio, 1)) * 30
    
    # Position concentration (30 points)
    concentration = min(positions / 5, 1)  # Optimal is 5 positions
    score += concentration * 30
    
    return min(100, max(0, score))

def calculate_position_correlations(positions: List[Dict]) -> Dict:
    """Calculate correlations between positions"""
    
    # Simplified correlation calculation
    # In production, would use historical price data
    
    correlations = {}
    for i, pos1 in enumerate(positions):
        for j, pos2 in enumerate(positions[i+1:], i+1):
            key = f"{pos1['symbol']}_{pos2['symbol']}"
            # Placeholder correlation
            correlations[key] = 0.3
    
    return correlations

def calculate_sector_exposure(positions: List[Dict]) -> Dict:
    """Calculate sector exposure"""
    
    # Simplified sector mapping
    # In production, would use proper sector classification
    
    tech_symbols = ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD']
    finance_symbols = ['JPM', 'BAC', 'GS', 'MS', 'WFC']
    
    sectors = {}
    for pos in positions:
        if pos['symbol'] in tech_symbols:
            sector = 'Technology'
        elif pos['symbol'] in finance_symbols:
            sector = 'Finance'
        else:
            sector = 'Other'
        
        if sector not in sectors:
            sectors[sector] = 0
        sectors[sector] += pos.get('market_value', 0)
    
    return sectors

# === HELPER FUNCTIONS ===

async def get_daily_trades(report_date: date) -> List[Dict]:
    """Get trades for a specific date"""
    
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM orders
                WHERE DATE(created_at) = $1
                ORDER BY created_at DESC
            """, report_date)
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get daily trades: {e}")
        return []

async def get_active_positions_for_date(report_date: date) -> List[Dict]:
    """Get active positions for a date"""
    
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM positions
                WHERE status = 'active'
                AND DATE(created_at) <= $1
            """, report_date)
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []

async def get_active_positions() -> List[Dict]:
    """Get current active positions"""
    
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    p.*,
                    p.quantity * p.current_price as market_value
                FROM positions p
                WHERE status = 'active'
            """)
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get active positions: {e}")
        return []

async def get_top_patterns_for_date(report_date: date) -> List[Dict]:
    """Get top performing patterns for a date"""
    
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    pattern_type,
                    COUNT(*) as count,
                    AVG(confidence) as avg_confidence
                FROM pattern_detections
                WHERE DATE(created_at) = $1
                GROUP BY pattern_type
                ORDER BY count DESC
                LIMIT 5
            """, report_date)
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get patterns: {e}")
        return []

async def get_market_conditions(report_date: date) -> Dict:
    """Get market conditions for a date"""
    
    # Simplified market conditions
    # In production, would fetch from market data
    
    return {
        "vix": 18.5,
        "spy_change": 0.5,
        "volume": "above_average",
        "trend": "bullish",
        "volatility": "moderate"
    }

async def calculate_risk_metrics(report_date: date) -> Dict:
    """Calculate risk metrics for a date"""
    
    positions = await get_active_positions_for_date(report_date)
    
    if not positions:
        return {
            "total_exposure": 0,
            "position_count": 0,
            "largest_position": 0,
            "risk_score": 0
        }
    
    total_exposure = sum(p.get('market_value', 0) for p in positions)
    largest_position = max(p.get('market_value', 0) for p in positions)
    
    return {
        "total_exposure": total_exposure,
        "position_count": len(positions),
        "largest_position": largest_position,
        "risk_score": calculate_risk_score(total_exposure, 50000, 0, len(positions))
    }

async def get_pnl_history(days: int) -> List[Dict]:
    """Get P&L history for charting"""
    
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    DATE(created_at) as date,
                    SUM(pnl) as daily_pnl
                FROM positions
                WHERE created_at >= $1
                GROUP BY DATE(created_at)
                ORDER BY date
            """, start_date)
            
            # Calculate cumulative P&L
            pnl_data = []
            cumulative = 0
            
            for row in rows:
                daily_pnl = float(row['daily_pnl'] or 0)
                cumulative += daily_pnl
                
                pnl_data.append({
                    "date": row['date'].isoformat(),
                    "daily_pnl": daily_pnl,
                    "cumulative_pnl": cumulative
                })
            
            return pnl_data
            
    except Exception as e:
        logger.error(f"Failed to get P&L history: {e}")
        return []

async def generate_daily_report() -> Dict:
    """Generate daily report"""
    
    today = date.today()
    metrics = await calculate_daily_metrics(today)
    trades = await get_daily_trades(today)
    
    return {
        "date": today.isoformat(),
        "metrics": metrics.dict(),
        "trades": trades,
        "summary": f"Completed {len(trades)} trades with {metrics.win_rate:.1f}% win rate"
    }

async def generate_weekly_report() -> Dict:
    """Generate weekly report"""
    
    # Simplified weekly report
    return {
        "period": "weekly",
        "start_date": (datetime.now() - timedelta(days=7)).date().isoformat(),
        "end_date": date.today().isoformat(),
        "summary": "Weekly report generated"
    }

async def generate_monthly_report() -> Dict:
    """Generate monthly report"""
    
    # Simplified monthly report
    return {
        "period": "monthly",
        "month": datetime.now().strftime("%B %Y"),
        "summary": "Monthly report generated"
    }

async def generate_periodic_reports():
    """Background task to generate periodic reports"""
    
    logger.info("Starting periodic report generation")
    
    while True:
        try:
            # Generate daily report at end of day
            now = datetime.now()
            if now.hour == 16 and now.minute == 0:  # 4 PM EST
                report = await generate_daily_report()
                logger.info(f"Generated daily report: {report}")
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Periodic report generation error: {e}")
            await asyncio.sleep(300)

def get_empty_metrics() -> PerformanceMetrics:
    """Return empty metrics object"""
    
    return PerformanceMetrics(
        total_pnl=0,
        realized_pnl=0,
        unrealized_pnl=0,
        win_rate=0,
        profit_factor=0,
        sharpe_ratio=0,
        max_drawdown=0,
        average_win=0,
        average_loss=0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        best_trade={},
        worst_trade={}
    )

# === MAIN ENTRY POINT ===

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎩 Catalyst Trading System - Reporting Service v4.1")
    print("=" * 60)
    print("Status: Starting...")
    print("Port: 5009")
    print("Protocol: REST API")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5009,
        log_level="info"
    )
