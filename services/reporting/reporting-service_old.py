#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: reporting-service.py
Version: 3.0.0
Last Updated: 2025-08-18
Purpose: MCP-enabled analytics and reporting service for trading performance

REVISION HISTORY:
v3.0.0 (2024-12-30) - Complete MCP migration
- Converted from Flask REST to MCP protocol
- Resources for all reporting and analytics data
- Tools for report generation and cache management
- Natural language query support via Claude
- Maintained all existing analysis capabilities

Description of Service:
MCP server providing comprehensive analytics and reporting:
1. Trading performance analysis (P&L, win rates, Sharpe ratio)
2. Pattern effectiveness tracking
3. System health monitoring
4. Risk management metrics
5. Daily, weekly, and monthly summaries
6. Portfolio analysis
7. Service performance metrics
"""

import os
import sys
import logging
import json
import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
import structlog
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
import redis
from dotenv import load_dotenv

# MCP imports
from mcp import MCPServer, ResourceParams, ToolParams
from mcp import ResourceResponse, ToolResponse, MCPError
from mcp.server import WebSocketTransport, StdioTransport

# Load environment variables
load_dotenv()

# Database connection utilities
def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(
            os.getenv('DATABASE_URL', 'postgresql://catalyst_user:password@db:5432/catalyst_trading'),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error("Database connection failed", error=str(e))
        raise

def get_redis_connection():
    """Get Redis connection for caching"""
    try:
        return redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))
        return None

# Configure structured logging
log_path = os.getenv('LOG_PATH', '/app/logs')
Path(log_path).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_path, 'reporting_mcp.log')),
        logging.StreamHandler()
    ]
)

logger = structlog.get_logger(__name__)

@dataclass
class PerformanceMetrics:
    """Trading performance metrics data structure"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_volume: int = 0
    total_commissions: float = 0.0

@dataclass
class RiskMetrics:
    """Risk management metrics"""
    current_positions: int = 0
    total_exposure: float = 0.0
    max_position_risk: float = 0.0
    portfolio_beta: float = 0.0
    var_95: float = 0.0  # Value at Risk 95%
    correlation_matrix: Dict = None


class ReportingMCPServer:
    """MCP Server for analytics and reporting"""
    
    def __init__(self):
        # Initialize MCP server
        self.server = MCPServer("reporting-analytics")
        
        # Service configuration
        self.service_name = "reporting-mcp"
        self.port = int(os.getenv('REPORTING_SERVICE_PORT', 5009))
        
        # Database connections
        self.redis_client = get_redis_connection()
        
        # Cache settings
        self.cache_ttl = int(os.getenv('CACHE_TTL_SECONDS', 300))  # 5 minutes
        
        # Register MCP resources and tools
        self._register_resources()
        self._register_tools()
        
        logger.info("Reporting MCP Server v3.0.0 initialized", port=self.port)

    def _register_resources(self):
        """Register MCP resources (read operations)"""
        
        @self.server.resource("reporting/health")
        async def get_health(params: ResourceParams) -> ResourceResponse:
            """Get service health status"""
            try:
                # Test database connection
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                
                # Test Redis connection
                redis_status = "healthy" if self.redis_client and self.redis_client.ping() else "unavailable"
                
                return ResourceResponse(
                    type="service_health",
                    data={
                        'status': 'healthy',
                        'service': self.service_name,
                        'database': 'healthy',
                        'redis': redis_status,
                        'version': '3.0.0'
                    },
                    metadata={'timestamp': datetime.now(timezone.utc).isoformat()}
                )
            except Exception as e:
                return ResourceResponse(
                    type="service_health",
                    data={
                        'status': 'unhealthy',
                        'service': self.service_name,
                        'error': str(e)
                    },
                    metadata={'timestamp': datetime.now(timezone.utc).isoformat()}
                )

        @self.server.resource("reporting/summary/daily")
        async def get_daily_summary(params: ResourceParams) -> ResourceResponse:
            """Get daily trading summary"""
            date_str = params.get('date', datetime.now().strftime('%Y-%m-%d'))
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            summary = await self._generate_daily_summary(target_date)
            
            return ResourceResponse(
                type="daily_summary",
                data=summary,
                metadata={
                    'date': target_date.isoformat(),
                    'cached': summary.get('from_cache', False)
                }
            )

        @self.server.resource("reporting/performance/trading")
        async def get_trading_performance(params: ResourceParams) -> ResourceResponse:
            """Get comprehensive trading performance metrics"""
            period = int(params.get('period', '30'))  # days
            include_positions = params.get('include_positions', False)
            
            performance = await self._calculate_trading_performance(period, include_positions)
            
            return ResourceResponse(
                type="trading_performance",
                data=performance,
                metadata={
                    'period_days': period,
                    'positions_included': include_positions
                }
            )

        @self.server.resource("reporting/analysis/patterns")
        async def get_pattern_effectiveness(params: ResourceParams) -> ResourceResponse:
            """Analyze pattern detection effectiveness"""
            period = int(params.get('period', '30'))
            pattern_type = params.get('pattern_type', 'all')
            
            effectiveness = await self._analyze_pattern_effectiveness(period, pattern_type)
            
            return ResourceResponse(
                type="pattern_effectiveness",
                data=effectiveness,
                metadata={
                    'period_days': period,
                    'pattern_filter': pattern_type
                }
            )

        @self.server.resource("reporting/system/health")
        async def get_system_health(params: ResourceParams) -> ResourceResponse:
            """Get comprehensive system health report"""
            health_report = await self._generate_system_health_report()
            
            return ResourceResponse(
                type="system_health_report",
                data=health_report,
                metadata={'components': len(health_report.get('services', {}))}
            )

        @self.server.resource("reporting/risk/current")
        async def get_risk_metrics(params: ResourceParams) -> ResourceResponse:
            """Get current risk management metrics"""
            metrics = await self._calculate_risk_metrics()
            
            return ResourceResponse(
                type="risk_metrics",
                data=metrics,
                metadata={
                    'alert_count': len(metrics.get('alerts', [])),
                    'positions': metrics['risk_metrics']['current_positions']
                }
            )

        @self.server.resource("reporting/portfolio/analysis")
        async def get_portfolio_analysis(params: ResourceParams) -> ResourceResponse:
            """Get comprehensive portfolio analysis"""
            analysis = await self._analyze_portfolio()
            
            return ResourceResponse(
                type="portfolio_analysis",
                data=analysis,
                metadata={
                    'position_count': analysis['position_count'],
                    'total_value': analysis['portfolio_value']
                }
            )

        @self.server.resource("reporting/summary/weekly")
        async def get_weekly_report(params: ResourceParams) -> ResourceResponse:
            """Get weekly trading report"""
            week_start = params.get('week_start')
            if week_start:
                start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
            else:
                # Default to current week
                today = datetime.now().date()
                start_date = today - timedelta(days=today.weekday())
            
            report = await self._generate_weekly_report(start_date)
            
            return ResourceResponse(
                type="weekly_report",
                data=report,
                metadata={
                    'week_start': start_date.isoformat(),
                    'trading_days': report['weekly_summary']['trading_days']
                }
            )

        @self.server.resource("reporting/performance/services")
        async def get_service_performance(params: ResourceParams) -> ResourceResponse:
            """Get individual service performance metrics"""
            performance = await self._get_service_performance_metrics()
            
            return ResourceResponse(
                type="service_performance",
                data=performance,
                metadata={'service_count': len(performance.get('services', {}))}
            )

        @self.server.resource("reporting/trades/history")
        async def get_trade_history(params: ResourceParams) -> ResourceResponse:
            """Get detailed trade history"""
            days = int(params.get('days', '30'))
            symbol = params.get('symbol')
            status = params.get('status', 'all')  # all, closed, open
            
            history = await self._get_trade_history(days, symbol, status)
            
            return ResourceResponse(
                type="trade_history",
                data=history,
                metadata={
                    'trade_count': len(history),
                    'period_days': days
                }
            )

        @self.server.resource("reporting/performance/by-symbol")
        async def get_symbol_performance(params: ResourceParams) -> ResourceResponse:
            """Get performance breakdown by symbol"""
            days = int(params.get('days', '30'))
            min_trades = int(params.get('min_trades', '5'))
            
            performance = await self._get_symbol_performance(days, min_trades)
            
            return ResourceResponse(
                type="symbol_performance",
                data=performance,
                metadata={
                    'symbol_count': len(performance),
                    'period_days': days
                }
            )

    def _register_tools(self):
        """Register MCP tools (write operations)"""
        
        @self.server.tool("generate_custom_report")
        async def generate_custom_report(params: ToolParams) -> ToolResponse:
            """Generate a custom report based on criteria"""
            report_type = params.get('report_type', 'performance')
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            symbols = params.get('symbols', [])
            
            report = await self._generate_custom_report(
                report_type, start_date, end_date, symbols
            )
            
            return ToolResponse(
                success=True,
                data=report,
                metadata={
                    'report_id': report.get('report_id'),
                    'generated_at': datetime.now(timezone.utc).isoformat()
                }
            )

        @self.server.tool("clear_report_cache")
        async def clear_report_cache(params: ToolParams) -> ToolResponse:
            """Clear cached reports"""
            cache_type = params.get('cache_type', 'all')
            
            cleared = await self._clear_cache(cache_type)
            
            return ToolResponse(
                success=True,
                data={
                    'cleared_keys': cleared,
                    'cache_type': cache_type
                }
            )

        @self.server.tool("export_report")
        async def export_report(params: ToolParams) -> ToolResponse:
            """Export report data in specified format"""
            report_type = params['report_type']
            format = params.get('format', 'json')  # json, csv, pdf
            parameters = params.get('parameters', {})
            
            export_data = await self._export_report(report_type, format, parameters)
            
            return ToolResponse(
                success=True,
                data={
                    'export_id': export_data['export_id'],
                    'format': format,
                    'size_bytes': export_data['size'],
                    'download_url': export_data['url']
                }
            )

        @self.server.tool("schedule_report")
        async def schedule_report(params: ToolParams) -> ToolResponse:
            """Schedule recurring report generation"""
            report_type = params['report_type']
            frequency = params['frequency']  # daily, weekly, monthly
            parameters = params.get('parameters', {})
            
            schedule_id = await self._schedule_report(report_type, frequency, parameters)
            
            return ToolResponse(
                success=True,
                data={
                    'schedule_id': schedule_id,
                    'report_type': report_type,
                    'frequency': frequency,
                    'next_run': self._calculate_next_run(frequency)
                }
            )

    # Core analysis methods (converted to async)
    async def _generate_daily_summary(self, target_date) -> Dict:
        """Generate comprehensive daily trading summary"""
        cache_key = f"daily_summary:{target_date}"
        
        # Check cache first
        if self.redis_client:
            cached = self.redis_client.get(cache_key)
            if cached:
                result = json.loads(cached)
                result['from_cache'] = True
                return result
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get trading activity for the day
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl_amount > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN pnl_amount < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(pnl_amount) as total_pnl,
                        AVG(CASE WHEN pnl_amount > 0 THEN pnl_amount END) as avg_win,
                        AVG(CASE WHEN pnl_amount < 0 THEN pnl_amount END) as avg_loss,
                        MAX(pnl_amount) as largest_win,
                        MIN(pnl_amount) as largest_loss,
                        SUM(quantity) as total_volume
                    FROM trade_records 
                    WHERE DATE(entry_timestamp) = %s
                    AND exit_timestamp IS NOT NULL
                """, (target_date,))
                
                trade_stats = cur.fetchone()
                
                # Get scanning activity
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT symbol) as symbols_scanned,
                        COUNT(*) as scan_results,
                        AVG(catalyst_score) as avg_confidence
                    FROM trading_candidates 
                    WHERE DATE(created_at) = %s
                """, (target_date,))
                
                scan_stats = cur.fetchone()
                
                # Get pattern analysis results
                cur.execute("""
                    SELECT 
                        pattern_type,
                        COUNT(*) as count,
                        AVG(pattern_strength) as avg_confidence
                    FROM pattern_analysis 
                    WHERE DATE(detection_timestamp) = %s
                    GROUP BY pattern_type
                """, (target_date,))
                
                pattern_stats = cur.fetchall()
        
        # Calculate derived metrics
        total_trades = trade_stats['total_trades'] or 0
        winning_trades = trade_stats['winning_trades'] or 0
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = 0
        if trade_stats['avg_loss'] and trade_stats['avg_loss'] < 0:
            gross_profit = abs(trade_stats['avg_win'] or 0) * winning_trades
            gross_loss = abs(trade_stats['avg_loss'] or 0) * (trade_stats['losing_trades'] or 0)
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        summary = {
            'date': target_date.isoformat(),
            'trading_summary': {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': trade_stats['losing_trades'] or 0,
                'win_rate': round(win_rate, 2),
                'total_pnl': float(trade_stats['total_pnl'] or 0),
                'average_win': float(trade_stats['avg_win'] or 0),
                'average_loss': float(trade_stats['avg_loss'] or 0),
                'largest_win': float(trade_stats['largest_win'] or 0),
                'largest_loss': float(trade_stats['largest_loss'] or 0),
                'profit_factor': round(profit_factor, 2),
                'total_volume': trade_stats['total_volume'] or 0
            },
            'scanning_summary': {
                'symbols_scanned': scan_stats['symbols_scanned'] or 0,
                'scan_results': scan_stats['scan_results'] or 0,
                'average_confidence': float(scan_stats['avg_confidence'] or 0)
            },
            'pattern_summary': [
                {
                    'pattern_type': pattern['pattern_type'],
                    'count': pattern['count'],
                    'average_confidence': float(pattern['avg_confidence'])
                }
                for pattern in pattern_stats
            ],
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'from_cache': False
        }
        
        # Cache the result
        if self.redis_client:
            self.redis_client.setex(
                cache_key, 
                self.cache_ttl, 
                json.dumps(summary, default=str)
            )
        
        return summary

    async def _calculate_trading_performance(self, period_days: int, include_positions: bool) -> Dict:
        """Calculate comprehensive trading performance metrics"""
        cache_key = f"trading_performance:{period_days}:{include_positions}"
        
        if self.redis_client:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        
        start_date = datetime.now() - timedelta(days=period_days)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get all closed trades in period
                cur.execute("""
                    SELECT * FROM trade_records 
                    WHERE entry_timestamp >= %s 
                    AND exit_timestamp IS NOT NULL
                    ORDER BY entry_timestamp
                """, (start_date,))
                
                closed_trades = cur.fetchall()
                
                # Get current open positions if requested
                open_positions = []
                if include_positions:
                    cur.execute("""
                        SELECT 
                            tr.*,
                            current_timestamp - tr.entry_timestamp as position_age
                        FROM trade_records tr
                        WHERE tr.exit_timestamp IS NULL
                        ORDER BY tr.entry_timestamp DESC
                    """)
                    open_positions = cur.fetchall()
        
        # Calculate performance metrics
        if not closed_trades:
            return {
                'period_days': period_days,
                'total_trades': 0,
                'performance': PerformanceMetrics().__dict__,
                'daily_returns': [],
                'open_positions': open_positions if include_positions else None,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        
        # Calculate metrics
        total_trades = len(closed_trades)
        winning_trades = len([t for t in closed_trades if (t['pnl_amount'] or 0) > 0])
        losing_trades = len([t for t in closed_trades if (t['pnl_amount'] or 0) < 0])
        
        pnls = [float(t['pnl_amount'] or 0) for t in closed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        average_win = sum(wins) / len(wins) if wins else 0
        average_loss = sum(losses) / len(losses) if losses else 0
        
        # Calculate Sharpe ratio
        daily_returns = self._calculate_daily_returns(closed_trades)
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(daily_returns)
        
        # Calculate profit factor
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        performance = PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            average_win=round(average_win, 2),
            average_loss=round(average_loss, 2),
            largest_win=max(pnls) if pnls else 0,
            largest_loss=min(pnls) if pnls else 0,
            profit_factor=round(profit_factor, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            max_drawdown=round(max_drawdown, 2),
            total_volume=sum([t['quantity'] or 0 for t in closed_trades]),
            total_commissions=0.0
        )
        
        # Format open positions
        if include_positions:
            formatted_positions = []
            for pos in open_positions:
                formatted_positions.append({
                    'symbol': pos['symbol'],
                    'quantity': pos['quantity'],
                    'entry_price': float(pos['entry_price'] or 0),
                    'stop_loss': float(pos['stop_loss'] or 0) if pos.get('stop_loss') else 0,
                    'take_profit': float(pos['take_profit'] or 0) if pos.get('take_profit') else 0,
                    'entry_timestamp': pos['entry_timestamp'].isoformat() if pos['entry_timestamp'] else None,
                    'position_age_hours': pos['position_age'].total_seconds() / 3600 if pos['position_age'] else 0
                })
            open_positions = formatted_positions
        
        result = {
            'period_days': period_days,
            'performance': performance.__dict__,
            'daily_returns': daily_returns,
            'open_positions': open_positions if include_positions else None,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Cache result
        if self.redis_client:
            self.redis_client.setex(
                cache_key, 
                self.cache_ttl, 
                json.dumps(result, default=str)
            )
        
        return result

    async def _analyze_pattern_effectiveness(self, period_days: int, pattern_type: str) -> Dict:
        """Analyze effectiveness of pattern detection"""
        start_date = datetime.now() - timedelta(days=period_days)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Base query for pattern analysis
                base_query = """
                    SELECT 
                        pa.pattern_type,
                        pa.symbol,
                        pa.pattern_strength as confidence,
                        pa.detection_timestamp as created_at,
                        tr.pnl_amount as pnl,
                        tr.entry_timestamp
                    FROM pattern_analysis pa
                    LEFT JOIN trading_candidates tc ON pa.symbol = tc.symbol 
                        AND DATE(pa.detection_timestamp) = DATE(tc.created_at)
                    LEFT JOIN trade_records tr ON tc.symbol = tr.symbol 
                        AND tr.entry_timestamp >= pa.detection_timestamp
                        AND tr.entry_timestamp <= pa.detection_timestamp + INTERVAL '24 hours'
                        AND tr.exit_timestamp IS NOT NULL
                    WHERE pa.detection_timestamp >= %s
                """
                
                params = [start_date]
                if pattern_type != 'all':
                    base_query += " AND pa.pattern_type = %s"
                    params.append(pattern_type)
                
                cur.execute(base_query, params)
                pattern_data = cur.fetchall()
        
        # Analyze effectiveness
        pattern_stats = {}
        
        for row in pattern_data:
            ptype = row['pattern_type']
            if ptype not in pattern_stats:
                pattern_stats[ptype] = {
                    'total_detections': 0,
                    'trades_executed': 0,
                    'profitable_trades': 0,
                    'total_pnl': 0,
                    'avg_confidence': 0,
                    'confidence_sum': 0
                }
            
            stats = pattern_stats[ptype]
            stats['total_detections'] += 1
            stats['confidence_sum'] += float(row['confidence'] or 0)
            
            if row['pnl'] is not None:
                stats['trades_executed'] += 1
                pnl = float(row['pnl'])
                stats['total_pnl'] += pnl
                if pnl > 0:
                    stats['profitable_trades'] += 1
        
        # Calculate derived metrics
        for ptype, stats in pattern_stats.items():
            if stats['total_detections'] > 0:
                stats['avg_confidence'] = stats['confidence_sum'] / stats['total_detections']
                stats['execution_rate'] = (stats['trades_executed'] / stats['total_detections']) * 100
                
            if stats['trades_executed'] > 0:
                stats['success_rate'] = (stats['profitable_trades'] / stats['trades_executed']) * 100
                stats['avg_pnl_per_trade'] = stats['total_pnl'] / stats['trades_executed']
            else:
                stats['success_rate'] = 0
                stats['avg_pnl_per_trade'] = 0
            
            # Remove intermediate calculations
            del stats['confidence_sum']
        
        return {
            'period_days': period_days,
            'pattern_type_filter': pattern_type,
            'pattern_effectiveness': pattern_stats,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _generate_system_health_report(self) -> Dict:
        """Generate comprehensive system health report"""
        # Database health
        db_health = self._check_database_health()
        
        # Redis health
        redis_health = {
            'status': 'healthy' if self.redis_client and self.redis_client.ping() else 'unhealthy',
            'memory_usage': None
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                redis_health['memory_usage'] = info.get('used_memory_human', 'unknown')
            except:
                pass
        
        # Recent errors (placeholder)
        recent_errors = []
        
        return {
            'system_status': 'healthy' if db_health['status'] == 'healthy' else 'degraded',
            'database': db_health,
            'redis': redis_health,
            'recent_errors': recent_errors,
            'uptime_stats': self._get_uptime_stats(),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _calculate_risk_metrics(self) -> Dict:
        """Calculate current risk management metrics"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Current open positions
                cur.execute("""
                    SELECT 
                        COUNT(*) as position_count,
                        SUM(ABS(quantity * entry_price)) as total_exposure,
                        MAX(ABS(quantity * entry_price)) as max_position_value
                    FROM trade_records 
                    WHERE exit_timestamp IS NULL
                """)
                
                position_data = cur.fetchone()
                
                # Recent P&L for VaR calculation
                cur.execute("""
                    SELECT pnl_amount 
                    FROM trade_records 
                    WHERE entry_timestamp >= NOW() - INTERVAL '30 days'
                    AND exit_timestamp IS NOT NULL
                    ORDER BY entry_timestamp
                """)
                
                recent_pnls = [float(row['pnl_amount'] or 0) for row in cur.fetchall()]
        
        # Calculate VaR (95% confidence)
        var_95 = 0
        if recent_pnls:
            var_95 = np.percentile(recent_pnls, 5)
        
        risk_metrics = RiskMetrics(
            current_positions=position_data['position_count'] or 0,
            total_exposure=float(position_data['total_exposure'] or 0),
            max_position_risk=float(position_data['max_position_value'] or 0),
            var_95=float(var_95)
        )
        
        return {
            'risk_metrics': risk_metrics.__dict__,
            'risk_limits': {
                'max_positions': int(os.getenv('MAX_POSITIONS', 5)),
                'max_position_size_pct': float(os.getenv('POSITION_SIZE_PCT', 20)),
                'stop_loss_pct': float(os.getenv('STOP_LOSS_PCT', 2))
            },
            'alerts': self._check_risk_alerts(risk_metrics),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _analyze_portfolio(self) -> Dict:
        """Comprehensive portfolio analysis"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Portfolio composition
                cur.execute("""
                    SELECT 
                        tr.symbol,
                        tr.quantity,
                        tr.entry_price,
                        tr.stop_loss,
                        tr.take_profit,
                        tr.entry_timestamp,
                        CURRENT_TIMESTAMP - tr.entry_timestamp as position_age
                    FROM trade_records tr
                    WHERE tr.exit_timestamp IS NULL
                    ORDER BY tr.entry_timestamp DESC
                """)
                
                positions = cur.fetchall()
                
                # Symbol performance
                cur.execute("""
                    SELECT 
                        symbol,
                        COUNT(*) as trade_count,
                        SUM(pnl_amount) as total_pnl,
                        AVG(pnl_amount) as avg_pnl
                    FROM trade_records 
                    WHERE entry_timestamp >= NOW() - INTERVAL '30 days'
                    AND exit_timestamp IS NOT NULL
                    GROUP BY symbol
                    ORDER BY total_pnl DESC
                """)
                
                symbol_performance = cur.fetchall()
        
        # Calculate portfolio metrics
        total_value = sum([float(p['quantity']) * float(p['entry_price'] or 0) for p in positions])
        
        return {
            'portfolio_value': round(total_value, 2),
            'position_count': len(positions),
            'positions': [
                {
                    'symbol': p['symbol'],
                    'quantity': p['quantity'],
                    'entry_price': float(p['entry_price'] or 0),
                    'stop_loss': float(p['stop_loss'] or 0) if p.get('stop_loss') else 0,
                    'take_profit': float(p['take_profit'] or 0) if p.get('take_profit') else 0,
                    'days_held': p['position_age'].days if p['position_age'] else 0,
                    'hours_held': p['position_age'].total_seconds() / 3600 if p['position_age'] else 0
                }
                for p in positions
            ],
            'top_performers': [
                {
                    'symbol': s['symbol'],
                    'trade_count': s['trade_count'],
                    'total_pnl': float(s['total_pnl'] or 0),
                    'avg_pnl': float(s['avg_pnl'] or 0)
                }
                for s in symbol_performance[:10]
            ],
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _generate_weekly_report(self, start_date) -> Dict:
        """Generate comprehensive weekly report"""
        end_date = start_date + timedelta(days=6)
        
        # Generate daily summaries for the week
        daily_summaries = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_summary = await self._generate_daily_summary(current_date)
            daily_summaries.append(daily_summary)
            current_date += timedelta(days=1)
        
        # Calculate weekly aggregates
        weekly_trades = sum([ds['trading_summary']['total_trades'] for ds in daily_summaries])
        weekly_pnl = sum([ds['trading_summary']['total_pnl'] for ds in daily_summaries])
        weekly_volume = sum([ds['trading_summary']['total_volume'] for ds in daily_summaries])
        
        # Calculate weekly win rate
        total_winning = sum([ds['trading_summary']['winning_trades'] for ds in daily_summaries])
        weekly_win_rate = (total_winning / weekly_trades * 100) if weekly_trades > 0 else 0
        
        return {
            'week_start': start_date.isoformat(),
            'week_end': end_date.isoformat(),
            'weekly_summary': {
                'total_trades': weekly_trades,
                'total_pnl': round(weekly_pnl, 2),
                'win_rate': round(weekly_win_rate, 2),
                'total_volume': weekly_volume,
                'trading_days': len([ds for ds in daily_summaries if ds['trading_summary']['total_trades'] > 0])
            },
            'daily_breakdown': daily_summaries,
            'weekly_performance': await self._calculate_trading_performance(7, False),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _get_service_performance_metrics(self) -> Dict:
        """Get performance metrics for each service"""
        # Add database query performance
        db_performance = self._get_database_performance()
        
        return {
            'database_performance': db_performance,
            'cache_performance': self._get_cache_performance(),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _get_trade_history(self, days: int, symbol: Optional[str], status: str) -> List[Dict]:
        """Get detailed trade history"""
        start_date = datetime.now() - timedelta(days=days)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT * FROM trade_records 
                    WHERE entry_timestamp >= %s
                """
                params = [start_date]
                
                if symbol:
                    query += " AND symbol = %s"
                    params.append(symbol)
                
                if status == 'closed':
                    query += " AND exit_timestamp IS NOT NULL"
                elif status == 'open':
                    query += " AND exit_timestamp IS NULL"
                
                query += " ORDER BY entry_timestamp DESC"
                
                cur.execute(query, params)
                trades = cur.fetchall()
        
        # Format trades for response
        formatted_trades = []
        for trade in trades:
            formatted_trades.append({
                'trade_id': trade['trade_id'],
                'symbol': trade['symbol'],
                'quantity': trade['quantity'],
                'entry_price': float(trade['entry_price'] or 0),
                'exit_price': float(trade['exit_price'] or 0) if trade['exit_price'] else None,
                'entry_timestamp': trade['entry_timestamp'].isoformat() if trade['entry_timestamp'] else None,
                'exit_timestamp': trade['exit_timestamp'].isoformat() if trade['exit_timestamp'] else None,
                'pnl': float(trade['pnl_amount'] or 0) if trade['pnl_amount'] else None,
                'status': 'closed' if trade['exit_timestamp'] else 'open'
            })
        
        return formatted_trades

    async def _get_symbol_performance(self, days: int, min_trades: int) -> List[Dict]:
        """Get performance breakdown by symbol"""
        start_date = datetime.now() - timedelta(days=days)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        symbol,
                        COUNT(*) as trade_count,
                        SUM(CASE WHEN pnl_amount > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(pnl_amount) as total_pnl,
                        AVG(pnl_amount) as avg_pnl,
                        MAX(pnl_amount) as best_trade,
                        MIN(pnl_amount) as worst_trade
                    FROM trade_records 
                    WHERE entry_timestamp >= %s
                    AND exit_timestamp IS NOT NULL
                    GROUP BY symbol
                    HAVING COUNT(*) >= %s
                    ORDER BY total_pnl DESC
                """, (start_date, min_trades))
                
                results = cur.fetchall()
        
        # Format results
        performance = []
        for row in results:
            win_rate = (row['winning_trades'] / row['trade_count'] * 100) if row['trade_count'] > 0 else 0
            performance.append({
                'symbol': row['symbol'],
                'trade_count': row['trade_count'],
                'win_rate': round(win_rate, 2),
                'total_pnl': float(row['total_pnl'] or 0),
                'avg_pnl': float(row['avg_pnl'] or 0),
                'best_trade': float(row['best_trade'] or 0),
                'worst_trade': float(row['worst_trade'] or 0)
            })
        
        return performance

    async def _generate_custom_report(self, report_type: str, start_date: str, 
                                    end_date: str, symbols: List[str]) -> Dict:
        """Generate custom report based on criteria"""
        # This would generate custom reports based on user criteria
        # For now, return a placeholder
        return {
            'report_id': f"REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'symbols': symbols,
            'data': {},
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    async def _clear_cache(self, cache_type: str) -> int:
        """Clear cached reports"""
        if not self.redis_client:
            return 0
        
        cleared = 0
        if cache_type == 'all':
            # Clear all cache keys
            for key in self.redis_client.scan_iter("*"):
                self.redis_client.delete(key)
                cleared += 1
        else:
            # Clear specific cache type
            for key in self.redis_client.scan_iter(f"{cache_type}:*"):
                self.redis_client.delete(key)
                cleared += 1
        
        return cleared

    async def _export_report(self, report_type: str, format: str, parameters: Dict) -> Dict:
        """Export report in specified format"""
        # This would handle report export functionality
        # For now, return placeholder
        export_id = f"EXPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return {
            'export_id': export_id,
            'size': 0,
            'url': f"/exports/{export_id}.{format}"
        }

    async def _schedule_report(self, report_type: str, frequency: str, parameters: Dict) -> str:
        """Schedule recurring report generation"""
        # This would handle report scheduling
        # For now, return placeholder schedule ID
        return f"SCHEDULE_{report_type}_{frequency}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Helper methods
    def _calculate_daily_returns(self, trades: List) -> List[float]:
        """Calculate daily returns from trades"""
        if not trades:
            return []
        
        # Group trades by date and sum P&L
        daily_pnl = {}
        for trade in trades:
            date = trade['entry_timestamp'].date() if hasattr(trade['entry_timestamp'], 'date') else trade['entry_timestamp']
            if isinstance(date, str):
                date = datetime.strptime(date.split()[0], '%Y-%m-%d').date()
            
            if date not in daily_pnl:
                daily_pnl[date] = 0
            daily_pnl[date] += float(trade['pnl_amount'] or 0)
        
        return list(daily_pnl.values())

    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        return (mean_return / std_return) if std_return > 0 else 0

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not returns:
            return 0
        
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        
        return float(np.min(drawdown))

    def _check_database_health(self) -> Dict:
        """Check database health"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    
            return {
                'status': 'healthy',
                'connection': 'successful'
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    def _get_uptime_stats(self) -> Dict:
        """Get system uptime statistics"""
        return {
            'system_start_time': datetime.now(timezone.utc).isoformat(),
            'uptime_hours': 0
        }

    def _check_risk_alerts(self, risk_metrics: RiskMetrics) -> List[Dict]:
        """Check for risk management alerts"""
        alerts = []
        
        max_positions = int(os.getenv('MAX_POSITIONS', 5))
        if risk_metrics.current_positions >= max_positions:
            alerts.append({
                'type': 'max_positions',
                'severity': 'warning',
                'message': f'At maximum position limit: {risk_metrics.current_positions}/{max_positions}'
            })
        
        return alerts

    def _get_database_performance(self) -> Dict:
        """Get database performance metrics"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as active_connections
                        FROM pg_stat_activity 
                        WHERE state = 'active'
                    """)
                    
                    result = cur.fetchone()
            
            return {
                'active_connections': result['active_connections'] if result else 0,
                'status': 'healthy'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def _get_cache_performance(self) -> Dict:
        """Get cache performance metrics"""
        if not self.redis_client:
            return {'status': 'unavailable'}
        
        try:
            info = self.redis_client.info()
            return {
                'status': 'healthy',
                'memory_usage': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0)
            }
        except:
            return {'status': 'error'}

    def _calculate_next_run(self, frequency: str) -> str:
        """Calculate next scheduled run time"""
        now = datetime.now()
        if frequency == 'daily':
            next_run = now + timedelta(days=1)
        elif frequency == 'weekly':
            next_run = now + timedelta(weeks=1)
        elif frequency == 'monthly':
            # Rough approximation
            next_run = now + timedelta(days=30)
        else:
            next_run = now + timedelta(hours=1)
        
        return next_run.isoformat()

    async def run(self):
        """Start the MCP server"""
        logger.info("Starting Reporting MCP Server",
                   version="3.0.0",
                   port=self.port)
        
        # Create WebSocket transport
        transport = WebSocketTransport(host='0.0.0.0', port=self.port)
        
        # Run server
        await self.server.run(transport)


if __name__ == "__main__":
    # Run the MCP server
    server = ReportingMCPServer()
    asyncio.run(server.run())