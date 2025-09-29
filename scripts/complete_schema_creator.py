#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: create_complete_schema.py
Version: 4.2.0
Last Updated: 2025-09-29
Purpose: Create complete v4.2 database schema from scratch

REVISION HISTORY:
v4.2.0 (2025-09-29) - Complete schema creation
- All core trading tables
- Risk management tables  
- Pattern and news tables
- Indexes and constraints
- Default risk parameters

Description of Service:
Creates the complete Catalyst Trading System database schema
from scratch. Run this on a fresh database or to recreate schema.
"""

import asyncio
import asyncpg
import os
from datetime import datetime, date

# === CORE TRADING TABLES ===

TRADING_CYCLES_TABLE = """
CREATE TABLE IF NOT EXISTS trading_cycles (
    cycle_id VARCHAR(20) PRIMARY KEY,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('aggressive', 'normal', 'conservative')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'stopped', 'completed', 'emergency_stopped')),
    
    -- Risk Configuration
    max_positions INTEGER NOT NULL DEFAULT 5,
    max_daily_loss DECIMAL(12,2) NOT NULL DEFAULT 2000.00,
    position_size_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.0,
    risk_level DECIMAL(3,2) NOT NULL DEFAULT 0.02,
    
    -- Timing
    scan_frequency INTEGER NOT NULL DEFAULT 300,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    
    -- Risk Metrics
    total_risk_budget DECIMAL(12,2) NOT NULL DEFAULT 2000.00,
    used_risk_budget DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    current_positions INTEGER NOT NULL DEFAULT 0,
    current_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    
    -- Metadata
    configuration JSONB DEFAULT '{}',
    risk_events INTEGER NOT NULL DEFAULT 0,
    emergency_stops INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SCAN_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS scan_results (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    scan_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(10) NOT NULL,
    
    -- Scores
    momentum_score DECIMAL(5,2) NOT NULL,
    volume_score DECIMAL(5,2) NOT NULL,
    catalyst_score DECIMAL(5,2) NOT NULL,
    technical_score DECIMAL(5,2),
    composite_score DECIMAL(5,2) NOT NULL,
    
    -- Market Data
    price DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    avg_volume_20d BIGINT,
    price_change_pct DECIMAL(6,2),
    
    -- Rankings
    rank INTEGER,
    selected_for_trading BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    scan_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scan_results_cycle ON scan_results(cycle_id, scan_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scan_results_score ON scan_results(composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_scan_results_symbol ON scan_results(symbol);
"""

POSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),
    
    -- Position Details
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_price DECIMAL(10,2) NOT NULL,
    current_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    
    -- Risk Management
    risk_amount DECIMAL(12,2) NOT NULL,
    position_risk_score DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    max_position_risk DECIMAL(3,2) NOT NULL DEFAULT 0.02,
    
    -- Status and Timing
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'partial', 'risk_reduced')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    
    -- P&L
    unrealized_pnl DECIMAL(12,2),
    realized_pnl DECIMAL(12,2),
    pnl_percent DECIMAL(6,2),
    max_profit DECIMAL(12,2),
    max_loss DECIMAL(12,2),
    
    -- Risk Events
    risk_warnings INTEGER NOT NULL DEFAULT 0,
    risk_violations INTEGER NOT NULL DEFAULT 0,
    stop_loss_triggered BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    close_reason VARCHAR(100),
    sector VARCHAR(50),
    confidence DECIMAL(4,3),
    pattern_detected VARCHAR(50),
    fees DECIMAL(10,2) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_cycle ON positions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_opened ON positions(opened_at DESC);
"""

ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    symbol VARCHAR(10) NOT NULL,
    
    -- Order Details
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    
    -- Pricing
    limit_price DECIMAL(10,2),
    stop_price DECIMAL(10,2),
    filled_price DECIMAL(10,2),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'submitted', 'filled', 'partial', 'cancelled', 'rejected')),
    
    -- Timing
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    
    -- Execution
    filled_quantity INTEGER DEFAULT 0,
    remaining_quantity INTEGER,
    fees DECIMAL(10,2) DEFAULT 0,
    
    -- Metadata
    broker_order_id VARCHAR(100),
    reason VARCHAR(200),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id);
CREATE INDEX IF NOT EXISTS idx_orders_cycle ON orders(cycle_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_submitted ON orders(submitted_at DESC);
"""

# === RISK MANAGEMENT TABLES ===

RISK_PARAMETERS_TABLE = """
CREATE TABLE IF NOT EXISTS risk_parameters (
    id SERIAL PRIMARY KEY,
    parameter_name VARCHAR(50) NOT NULL UNIQUE,
    parameter_value DECIMAL(12,4) NOT NULL,
    parameter_type VARCHAR(20) NOT NULL DEFAULT 'numeric',
    description TEXT,
    set_by VARCHAR(50) DEFAULT 'system',
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_parameters_name ON risk_parameters(parameter_name);
"""

DAILY_RISK_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_risk_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    cycle_id VARCHAR(20),
    
    -- P&L Metrics
    daily_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    daily_gross_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    daily_fees DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    cumulative_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    
    -- Trade Metrics
    trades_taken INTEGER NOT NULL DEFAULT 0,
    trades_won INTEGER NOT NULL DEFAULT 0,
    trades_lost INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    
    -- Risk Metrics
    risk_used DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    max_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    max_drawdown DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    sharpe_ratio DECIMAL(6,3),
    
    -- Position Metrics
    max_positions INTEGER NOT NULL DEFAULT 0,
    avg_position_size DECIMAL(12,2),
    largest_win DECIMAL(12,2),
    largest_loss DECIMAL(12,2),
    
    -- Limits and Events
    daily_loss_limit_hit BOOLEAN DEFAULT FALSE,
    emergency_stop_triggered BOOLEAN DEFAULT FALSE,
    risk_events INTEGER NOT NULL DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(date, cycle_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_risk_date ON daily_risk_metrics(date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_risk_cycle ON daily_risk_metrics(cycle_id);
"""

RISK_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical', 'emergency')),
    cycle_id VARCHAR(20),
    symbol VARCHAR(10),
    
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events(event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);
CREATE INDEX IF NOT EXISTS idx_risk_events_created ON risk_events(created_at DESC);
"""

# === PATTERN AND NEWS TABLES ===

PATTERN_ANALYSIS_TABLE = """
CREATE TABLE IF NOT EXISTS pattern_analysis (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    confidence DECIMAL(4,3) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pattern_symbol ON pattern_analysis(symbol);
CREATE INDEX IF NOT EXISTS idx_pattern_type ON pattern_analysis(pattern_type);
CREATE INDEX IF NOT EXISTS idx_pattern_detected ON pattern_analysis(detected_at DESC);
"""

NEWS_ARTICLES_TABLE = """
CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    source VARCHAR(100),
    url TEXT,
    
    published_at TIMESTAMPTZ NOT NULL,
    
    -- Sentiment Analysis
    sentiment_score DECIMAL(4,3),
    relevance_score DECIMAL(4,3),
    catalyst_type VARCHAR(50),
    impact_prediction VARCHAR(20),
    
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_symbol ON news_articles(symbol);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_catalyst ON news_articles(catalyst_type);
"""

# === DEFAULT DATA ===

DEFAULT_RISK_PARAMETERS = """
INSERT INTO risk_parameters (parameter_name, parameter_value, parameter_type, description, set_by) VALUES
    ('max_daily_loss', 2000.00, 'currency', 'Maximum loss allowed per day', 'system'),
    ('max_position_risk', 0.02, 'percentage', 'Maximum risk per position (2%)', 'system'),
    ('max_portfolio_risk', 0.06, 'percentage', 'Maximum total portfolio risk (6%)', 'system'),
    ('max_positions', 5, 'count', 'Maximum concurrent positions', 'system'),
    ('position_size_base', 10000.00, 'currency', 'Base position size', 'system'),
    ('stop_loss_atr_multiplier', 2.0, 'multiplier', 'Stop loss ATR multiplier', 'system'),
    ('min_risk_reward_ratio', 2.0, 'ratio', 'Minimum risk/reward ratio', 'system'),
    ('max_correlation', 0.70, 'percentage', 'Maximum position correlation', 'system')
ON CONFLICT (parameter_name) DO NOTHING;
"""

async def create_complete_schema():
    """Create complete database schema"""
    url = os.getenv("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        conn = await asyncpg.connect(url)
        
        print("🎩 Catalyst Trading System - Complete Schema Creation")
        print("=" * 70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Core Trading Tables
        print("📊 Creating Core Trading Tables...")
        print("-" * 70)
        
        print("  Creating trading_cycles...")
        await conn.execute(TRADING_CYCLES_TABLE)
        print("  ✅ trading_cycles created")
        
        print("  Creating scan_results...")
        await conn.execute(SCAN_RESULTS_TABLE)
        print("  ✅ scan_results created")
        
        print("  Creating positions...")
        await conn.execute(POSITIONS_TABLE)
        print("  ✅ positions created")
        
        print("  Creating orders...")
        await conn.execute(ORDERS_TABLE)
        print("  ✅ orders created")
        
        # Risk Management Tables
        print("\n🛡️  Creating Risk Management Tables...")
        print("-" * 70)
        
        print("  Creating risk_parameters...")
        await conn.execute(RISK_PARAMETERS_TABLE)
        print("  ✅ risk_parameters created")
        
        print("  Creating daily_risk_metrics...")
        await conn.execute(DAILY_RISK_METRICS_TABLE)
        print("  ✅ daily_risk_metrics created")
        
        print("  Creating risk_events...")
        await conn.execute(RISK_EVENTS_TABLE)
        print("  ✅ risk_events created")
        
        # Pattern and News Tables
        print("\n📈 Creating Analysis Tables...")
        print("-" * 70)
        
        print("  Creating pattern_analysis...")
        await conn.execute(PATTERN_ANALYSIS_TABLE)
        print("  ✅ pattern_analysis created")
        
        print("  Creating news_articles...")
        await conn.execute(NEWS_ARTICLES_TABLE)
        print("  ✅ news_articles created")
        
        # Insert Default Data
        print("\n⚙️  Inserting Default Risk Parameters...")
        print("-" * 70)
        await conn.execute(DEFAULT_RISK_PARAMETERS)
        
        param_count = await conn.fetchval("SELECT COUNT(*) FROM risk_parameters")
        print(f"  ✅ Inserted {param_count} default risk parameters")
        
        # Verify All Tables
        print("\n✅ Verifying Schema...")
        print("-" * 70)
        
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        table_names = [row['table_name'] for row in tables]
        print(f"  Total tables created: {len(table_names)}")
        for table in table_names:
            print(f"    📋 {table}")
        
        await conn.close()
        
        print("\n" + "=" * 70)
        print("🎉 SCHEMA CREATION COMPLETE!")
        print("=" * 70)
        
        print("\n🚀 Next Steps:")
        print("1. ✅ Database schema is ready")
        print("2. 🔄 Restart all services: docker-compose restart")
        print("3. 📊 Monitor service health: docker-compose ps")
        print("4. 📝 Check logs: docker-compose logs -f")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Schema creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(create_complete_schema())
