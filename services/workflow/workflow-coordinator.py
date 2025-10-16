#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: workflow-coordinator.py
Version: 1.0.0
Last Updated: 2025-10-16
Purpose: HTTP service that orchestrates the trading workflow pipeline

REVISION HISTORY:
v1.0.0 (2025-10-16) - Initial implementation
- Coordinates scanner → pattern → technical → risk → trading
- Implements the 100 → 35 → 20 → 10 → 5 candidate filtering
- Background task processing
- RESTful API for trigger and monitoring

Description:
This service handles the actual trading workflow coordination,
calling each service in sequence and filtering candidates.
Runs on port 5010 as a standard HTTP service.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import aiohttp
import asyncio
import logging
import os
import json
from dataclasses import dataclass

SERVICE_NAME = "workflow"
SERVICE_VERSION = "1.0.o"
SERVICE_PORT = 5006

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("workflow")

# ============================================================================
# CONFIGURATION
# ============================================================================
@dataclass
class Config:
    SERVICE_PORT = 5006 # Different from MCP orchestration (5000)
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Service URLs (internal Docker network)
    SCANNER_URL = os.getenv("SCANNER_URL", "http://scanner:5001")
    PATTERN_URL = os.getenv("PATTERN_URL", "http://pattern:5002")
    TECHNICAL_URL = os.getenv("TECHNICAL_URL", "http://technical:5003")
    RISK_URL = os.getenv("RISK_URL", "http://risk-manager:5004")
    TRADING_URL = os.getenv("TRADING_URL", "http://trading:5005")
    NEWS_URL = os.getenv("NEWS_URL", "http://news:5008")
    
    # Workflow parameters
    MAX_INITIAL_CANDIDATES = 100
    AFTER_NEWS_FILTER = 35
    AFTER_PATTERN_FILTER = 20
    AFTER_TECHNICAL_FILTER = 10
    FINAL_TRADING_CANDIDATES = 5
    
    # Timing
    WORKFLOW_TIMEOUT = 300  # 5 minutes
    SERVICE_TIMEOUT = 30    # 30 seconds per service call

config = Config()

# ============================================================================
# STATE MANAGEMENT
# ============================================================================
class WorkflowStatus(str, Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    FILTERING_NEWS = "filtering_news"
    ANALYZING_PATTERNS = "analyzing_patterns"
    TECHNICAL_ANALYSIS = "technical_analysis"
    RISK_VALIDATION = "risk_validation"
    EXECUTING_TRADES = "executing_trades"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowState:
    def __init__(self):
        self.current_cycle = None
        self.status = WorkflowStatus.IDLE
        self.last_run = None
        self.active_positions = []
        self.db_pool = None
        self.http_session = None

state = WorkflowState()

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Workflow Coordinator v1.0.0")
    
    # Initialize database
    if config.DATABASE_URL:
        state.db_pool = await asyncpg.create_pool(config.DATABASE_URL)
        logger.info("Database pool initialized")
    
    # Initialize HTTP session
    state.http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=config.SERVICE_TIMEOUT)
    )
    logger.info("HTTP session initialized")
    
    logger.info(f"Workflow Coordinator ready on port {config.SERVICE_PORT}")
    
    yield
    
    # Shutdown
    if state.http_session:
        await state.http_session.close()
    if state.db_pool:
        await state.db_pool.close()
    logger.info("Workflow Coordinator shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title="Workflow Coordinator",
    version="1.0.0",
    description="Orchestrates the trading workflow pipeline",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# WORKFLOW ORCHESTRATION
# ============================================================================
async def run_trading_workflow(cycle_id: str, mode: str = "normal"):
    """
    Main workflow orchestration logic.
    Implements: Scanner → News → Pattern → Technical → Risk → Trading
    """
    try:
        state.status = WorkflowStatus.SCANNING
        state.current_cycle = cycle_id
        workflow_result = {
            "cycle_id": cycle_id,
            "started_at": datetime.utcnow(),
            "mode": mode,
            "stages": {}
        }
        
        # ========== STAGE 1: Market Scan (100 candidates) ==========
        logger.info(f"[{cycle_id}] Stage 1: Scanning market...")
        async with state.http_session.post(f"{config.SCANNER_URL}/api/v1/scan") as resp:
            if resp.status != 200:
                raise Exception(f"Scanner failed: HTTP {resp.status}")
            scan_data = await resp.json()
        
        candidates = scan_data.get("picks", [])[:config.MAX_INITIAL_CANDIDATES]
        workflow_result["stages"]["scan"] = {
            "candidates": len(candidates),
            "duration": (datetime.utcnow() - workflow_result["started_at"]).total_seconds()
        }
        logger.info(f"[{cycle_id}] Scan complete: {len(candidates)} candidates")
        
        if not candidates:
            state.status = WorkflowStatus.COMPLETED
            workflow_result["status"] = "no_candidates"
            return workflow_result
        
        # ========== STAGE 2: News Filter (100 → 35) ==========
        state.status = WorkflowStatus.FILTERING_NEWS
        logger.info(f"[{cycle_id}] Stage 2: Filtering by news catalysts...")
        
        news_candidates = []
        for candidate in candidates:
            try:
                async with state.http_session.get(
                    f"{config.NEWS_URL}/api/v1/news/{candidate['symbol']}?limit=5"
                ) as resp:
                    if resp.status == 200:
                        news_data = await resp.json()
                        # Check for positive catalysts
                        if news_data.get("news"):
                            sentiment = sum(n.get("sentiment_score", 0) for n in news_data["news"]) / len(news_data["news"])
                            if sentiment > 0.3:  # Positive sentiment threshold
                                candidate["news_sentiment"] = sentiment
                                news_candidates.append(candidate)
            except:
                continue
            
            if len(news_candidates) >= config.AFTER_NEWS_FILTER:
                break
        
        workflow_result["stages"]["news"] = {
            "candidates": len(news_candidates),
            "filtered_out": len(candidates) - len(news_candidates)
        }
        logger.info(f"[{cycle_id}] News filter: {len(news_candidates)} candidates remain")
        
        # ========== STAGE 3: Pattern Analysis (35 → 20) ==========
        state.status = WorkflowStatus.ANALYZING_PATTERNS
        logger.info(f"[{cycle_id}] Stage 3: Analyzing patterns...")
        
        pattern_candidates = []
        for candidate in news_candidates:
            try:
                async with state.http_session.post(
                    f"{config.PATTERN_URL}/api/v1/detect",
                    json={"symbol": candidate["symbol"], "timeframe": "5m", "min_confidence": 0.6}
                ) as resp:
                    if resp.status == 200:
                        pattern_data = await resp.json()
                        if pattern_data.get("patterns_found", 0) > 0:
                            candidate["patterns"] = pattern_data["patterns"]
                            candidate["pattern_confidence"] = max(
                                p.get("confidence", 0) for p in pattern_data["patterns"]
                            )
                            pattern_candidates.append(candidate)
            except:
                continue
            
            if len(pattern_candidates) >= config.AFTER_PATTERN_FILTER:
                break
        
        # Sort by pattern confidence
        pattern_candidates.sort(key=lambda x: x.get("pattern_confidence", 0), reverse=True)
        pattern_candidates = pattern_candidates[:config.AFTER_PATTERN_FILTER]
        
        workflow_result["stages"]["patterns"] = {
            "candidates": len(pattern_candidates),
            "with_patterns": len([c for c in pattern_candidates if c.get("patterns")])
        }
        logger.info(f"[{cycle_id}] Pattern analysis: {len(pattern_candidates)} candidates remain")
        
        # ========== STAGE 4: Technical Analysis (20 → 10) ==========
        state.status = WorkflowStatus.TECHNICAL_ANALYSIS
        logger.info(f"[{cycle_id}] Stage 4: Technical analysis...")
        
        technical_candidates = []
        for candidate in pattern_candidates:
            try:
                # Get technical indicators
                async with state.http_session.get(
                    f"{config.TECHNICAL_URL}/api/v1/indicators/{candidate['symbol']}"
                ) as resp:
                    if resp.status == 200:
                        tech_data = await resp.json()
                        # Calculate composite technical score
                        rsi = tech_data.get("rsi", 50)
                        macd_signal = tech_data.get("macd_signal", 0)
                        
                        # Bullish conditions
                        if 30 < rsi < 70 and macd_signal > 0:
                            candidate["technical_score"] = (
                                (70 - abs(rsi - 50)) / 20 * 0.5 +  # RSI score
                                min(macd_signal / 10, 1) * 0.5      # MACD score
                            )
                            technical_candidates.append(candidate)
            except:
                continue
            
            if len(technical_candidates) >= config.AFTER_TECHNICAL_FILTER:
                break
        
        # Sort by technical score
        technical_candidates.sort(key=lambda x: x.get("technical_score", 0), reverse=True)
        technical_candidates = technical_candidates[:config.AFTER_TECHNICAL_FILTER]
        
        workflow_result["stages"]["technical"] = {
            "candidates": len(technical_candidates),
            "avg_score": sum(c.get("technical_score", 0) for c in technical_candidates) / len(technical_candidates) if technical_candidates else 0
        }
        logger.info(f"[{cycle_id}] Technical analysis: {len(technical_candidates)} candidates remain")
        
        # ========== STAGE 5: Risk Validation (10 → 5) ==========
        state.status = WorkflowStatus.RISK_VALIDATION
        logger.info(f"[{cycle_id}] Stage 5: Risk validation...")
        
        validated_candidates = []
        for candidate in technical_candidates:
            try:
                # Prepare position for risk validation
                position_request = {
                    "cycle_id": cycle_id,
                    "symbol": candidate["symbol"],
                    "side": "long",
                    "quantity": 100,  # Base quantity
                    "entry_price": candidate.get("current_price", 100),
                    "stop_price": candidate.get("current_price", 100) * 0.98,
                    "target_price": candidate.get("current_price", 100) * 1.05
                }
                
                async with state.http_session.post(
                    f"{config.RISK_URL}/api/v1/validate-position",
                    json=position_request
                ) as resp:
                    if resp.status == 200:
                        risk_data = await resp.json()
                        if risk_data.get("approved"):
                            candidate["position_size"] = risk_data.get("position_size")
                            candidate["risk_score"] = risk_data.get("risk_score")
                            validated_candidates.append(candidate)
            except:
                continue
            
            if len(validated_candidates) >= config.FINAL_TRADING_CANDIDATES:
                break
        
        workflow_result["stages"]["risk"] = {
            "validated": len(validated_candidates),
            "rejected": len(technical_candidates) - len(validated_candidates)
        }
        logger.info(f"[{cycle_id}] Risk validation: {len(validated_candidates)} candidates approved")
        
        # ========== STAGE 6: Execute Trades (Top 5) ==========
        state.status = WorkflowStatus.EXECUTING_TRADES
        logger.info(f"[{cycle_id}] Stage 6: Executing trades...")
        
        executed_trades = []
        for candidate in validated_candidates[:config.FINAL_TRADING_CANDIDATES]:
            try:
                trade_request = {
                    "symbol": candidate["symbol"],
                    "side": "buy",
                    "quantity": candidate.get("position_size", 100),
                    "order_type": "market",
                    "cycle_id": cycle_id
                }
                
                async with state.http_session.post(
                    f"{config.TRADING_URL}/api/v1/orders",
                    json=trade_request
                ) as resp:
                    if resp.status == 200:
                        trade_data = await resp.json()
                        executed_trades.append({
                            "symbol": candidate["symbol"],
                            "order_id": trade_data.get("order_id"),
                            "quantity": candidate.get("position_size")
                        })
            except Exception as e:
                logger.error(f"Failed to execute trade for {candidate['symbol']}: {e}")
                continue
        
        workflow_result["stages"]["trading"] = {
            "executed": len(executed_trades),
            "trades": executed_trades
        }
        logger.info(f"[{cycle_id}] Trading complete: {len(executed_trades)} trades executed")
        
        # ========== COMPLETE ==========
        state.status = WorkflowStatus.COMPLETED
        workflow_result["completed_at"] = datetime.utcnow()
        workflow_result["total_duration"] = (
            workflow_result["completed_at"] - workflow_result["started_at"]
        ).total_seconds()
        workflow_result["status"] = "success"
        
        return workflow_result
        
    except Exception as e:
        logger.error(f"[{cycle_id}] Workflow failed: {e}")
        state.status = WorkflowStatus.FAILED
        return {
            "cycle_id": cycle_id,
            "status": "failed",
            "error": str(e)
        }
    finally:
        state.last_run = datetime.utcnow()

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "workflow-coordinator",
        "version": "1.0.0",
        "current_status": state.status,
        "last_run": state.last_run.isoformat() if state.last_run else None,
        "active_cycle": state.current_cycle
    }

@app.post("/api/v1/workflow/start")
async def start_workflow(background_tasks: BackgroundTasks, mode: str = "normal"):
    """Start a new trading workflow cycle"""
    if state.status not in [WorkflowStatus.IDLE, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
        raise HTTPException(
            status_code=409,
            detail=f"Workflow already running: {state.status}"
        )
    
    cycle_id = f"cycle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    # Start workflow in background
    background_tasks.add_task(run_trading_workflow, cycle_id, mode)
    
    return {
        "success": True,
        "cycle_id": cycle_id,
        "status": "started",
        "mode": mode
    }

@app.get("/api/v1/workflow/status")
async def get_workflow_status():
    """Get current workflow status"""
    return {
        "status": state.status,
        "current_cycle": state.current_cycle,
        "last_run": state.last_run.isoformat() if state.last_run else None,
        "active_positions": len(state.active_positions)
    }

@app.post("/api/v1/workflow/stop")
async def stop_workflow():
    """Stop the current workflow"""
    if state.status in [WorkflowStatus.IDLE, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
        return {"success": False, "message": "No active workflow to stop"}
    
    state.status = WorkflowStatus.IDLE
    return {"success": True, "message": "Workflow stop requested"}

@app.get("/api/v1/workflow/history")
async def get_workflow_history(limit: int = 10):
    """Get workflow run history"""
    if not state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    rows = await state.db_pool.fetch("""
        SELECT cycle_id, start_time, end_time, status, 
               initial_universe_size, final_candidates
        FROM trading_cycles
        ORDER BY start_time DESC
        LIMIT $1
    """, limit)
    
    return {
        "history": [dict(row) for row in rows]
    }

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "workflow-coordinator:app",
        host="0.0.0.0",
        port=config.SERVICE_PORT,
        reload=False
    )
