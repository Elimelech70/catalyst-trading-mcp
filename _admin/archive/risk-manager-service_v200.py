#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk-manager-service.py
Version: 2.0.0
Last Updated: 2025-08-30
Purpose: Risk management service for position sizing and stop losses

REVISION HISTORY:
v2.0.0 (2025-08-30) - Converted to FastMCP implementation
"""

from mcp.server.fastmcp import FastMCP
from typing import Dict, Optional
from datetime import datetime

mcp = FastMCP("risk-manager")

# Risk parameters
risk_params = {
    "max_position_size": 0.1,  # 10% of portfolio
    "max_daily_loss": 0.02,    # 2% daily loss limit
    "default_stop_loss": 0.05   # 5% stop loss
}

# Current risk metrics
risk_metrics = {
    "daily_pnl": 0.0,
    "open_risk": 0.0,
    "positions": []
}

@mcp.resource("risk-manager://risk/parameters")
async def get_risk_parameters() -> Dict:
    """Get current risk parameters"""
    return risk_params

@mcp.resource("risk-manager://risk/metrics")
async def get_risk_metrics() -> Dict:
    """Get current risk metrics"""
    return {
        **risk_metrics,
        "timestamp": datetime.now().isoformat()
    }

@mcp.tool()
async def calculate_position_size(
    symbol: str,
    account_balance: float,
    risk_per_trade: float = 0.01
) -> Dict:
    """Calculate appropriate position size"""
    
    # Basic position sizing calculation
    max_position_value = account_balance * risk_params["max_position_size"]
    risk_amount = account_balance * risk_per_trade
    
    # Placeholder price
    current_price = 100.0
    
    # Calculate shares based on risk
    stop_distance = current_price * risk_params["default_stop_loss"]
    shares = int(risk_amount / stop_distance)
    
    # Ensure within max position size
    max_shares = int(max_position_value / current_price)
    shares = min(shares, max_shares)
    
    return {
        "symbol": symbol,
        "recommended_shares": shares,
        "position_value": shares * current_price,
        "risk_amount": risk_amount,
        "stop_loss": current_price * (1 - risk_params["default_stop_loss"])
    }

@mcp.tool()
async def validate_trade(
    symbol: str,
    shares: int,
    price: float,
    account_balance: float
) -> Dict:
    """Validate if trade meets risk parameters"""
    
    position_value = shares * price
    position_pct = position_value / account_balance
    
    # Check position size limit
    if position_pct > risk_params["max_position_size"]:
        return {
            "approved": False,
            "reason": f"Position size {position_pct:.1%} exceeds limit {risk_params['max_position_size']:.1%}"
        }
    
    # Check daily loss limit
    potential_loss = position_value * risk_params["default_stop_loss"]
    if (risk_metrics["daily_pnl"] - potential_loss) < (-account_balance * risk_params["max_daily_loss"]):
        return {
            "approved": False,
            "reason": "Would exceed daily loss limit"
        }
    
    return {
        "approved": True,
        "position_size": position_pct,
        "stop_loss": price * (1 - risk_params["default_stop_loss"]),
        "max_loss": potential_loss
    }

@mcp.tool()
async def update_risk_metrics(
    pnl_change: float,
    position_change: Optional[Dict] = None
) -> Dict:
    """Update risk metrics with new P&L or position changes"""
    
    risk_metrics["daily_pnl"] += pnl_change
    
    if position_change:
        if position_change.get("action") == "open":
            risk_metrics["positions"].append(position_change)
            risk_metrics["open_risk"] += position_change.get("risk", 0)
        elif position_change.get("action") == "close":
            # Remove position and update risk
            risk_metrics["positions"] = [
                p for p in risk_metrics["positions"] 
                if p.get("symbol") != position_change.get("symbol")
            ]
    
    return {
        "success": True,
        "updated_metrics": risk_metrics
    }

if __name__ == "__main__":
    mcp.run()
