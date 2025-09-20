#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: upgrade_to_v42_schema.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Upgrade existing database to v4.2 schema with risk management

REVISION HISTORY:
v4.2.0 (2025-09-20) - Schema upgrade for risk management
- Add missing v4.2 tables (risk_parameters, daily_risk_metrics, risk_events, news_articles)
- Update existing tables with v4.2 enhancements
- Initialize default risk parameters
- Verify all v4.2 functionality

Description:
Upgrades existing Catalyst Trading database to v4.2 schema to support
the new risk management service and enhanced functionality.
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime, date
import json

async def check_existing_tables():
    """Check what tables already exist"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        existing_tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        await conn.close()
        return [row['table_name'] for row in existing_tables]
        
    except Exception as e:
        return f"Error: {e}"

async def create_risk_parameters_table():
    """Create risk_parameters table for dynamic risk configuration"""
    return """
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
    CREATE INDEX IF NOT EXISTS idx_risk_parameters_effective ON risk_parameters(effective_from, effective_until);
    """

async def create_daily_risk_metrics_table():
    """Create daily_risk_metrics table for daily risk tracking"""
    return """
    CREATE TABLE IF NOT EXISTS daily_risk_metrics (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        cycle_id VARCHAR(20),
        
        -- P&L Metrics
        daily_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        daily_gross_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        daily_fees DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        cumulative_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        
        -- Risk Metrics
        max_drawdown DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        risk_budget_used DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        risk_budget_remaining DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        var_95 DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        
        -- Position Metrics
        max_positions INTEGER NOT NULL DEFAULT 0,
        avg_position_size DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        total_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        sector_concentration DECIMAL(4,3) NOT NULL DEFAULT 0.000,
        
        -- Performance Metrics
        sharpe_ratio DECIMAL(6,3),
        win_rate DECIMAL(4,3) NOT NULL DEFAULT 0.000,
        profit_factor DECIMAL(6,3),
        
        -- Risk Events
        risk_alerts INTEGER NOT NULL DEFAULT 0,
        emergency_stops INTEGER NOT NULL DEFAULT 0,
        limit_breaches INTEGER NOT NULL DEFAULT 0,
        
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        
        UNIQUE(date, cycle_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_daily_risk_metrics_date ON daily_risk_metrics(date DESC);
    CREATE INDEX IF NOT EXISTS idx_daily_risk_metrics_cycle ON daily_risk_metrics(cycle_id);
    """

async def create_risk_events_table():
    """Create risk_events table for risk alerts and violations"""
    return """
    CREATE TABLE IF NOT EXISTS risk_events (
        id SERIAL PRIMARY KEY,
        event_type VARCHAR(50) NOT NULL,
        severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
        cycle_id VARCHAR(20),
        symbol VARCHAR(10),
        
        -- Event Details
        title VARCHAR(200) NOT NULL,
        description TEXT NOT NULL,
        risk_metric VARCHAR(50),
        threshold_value DECIMAL(12,4),
        actual_value DECIMAL(12,4),
        
        -- Response
        action_taken VARCHAR(100),
        resolved_at TIMESTAMPTZ,
        resolved_by VARCHAR(50),
        
        -- Context
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        
        CONSTRAINT valid_event_types CHECK (
            event_type IN (
                'daily_loss_limit',
                'position_size_limit', 
                'portfolio_risk_limit',
                'concentration_limit',
                'correlation_limit',
                'emergency_stop',
                'margin_call',
                'system_error'
            )
        )
    );
    
    CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events(event_type);
    CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);
    CREATE INDEX IF NOT EXISTS idx_risk_events_created ON risk_events(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_risk_events_cycle ON risk_events(cycle_id);
    """

async def create_news_articles_table():
    """Create news_articles table for news catalyst tracking"""
    return """
    CREATE TABLE IF NOT EXISTS news_articles (
        id SERIAL PRIMARY KEY,
        
        -- Article Identification
        title VARCHAR(500) NOT NULL,
        url VARCHAR(1000),
        source VARCHAR(100) NOT NULL,
        author VARCHAR(200),
        
        -- Content
        summary TEXT,
        content TEXT,
        keywords TEXT[],
        
        -- Timing
        published_at TIMESTAMPTZ NOT NULL,
        fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        
        -- Relevance
        symbols VARCHAR(10)[],
        sectors VARCHAR(50)[],
        relevance_score DECIMAL(4,3) DEFAULT 0.000,
        sentiment_score DECIMAL(4,3) DEFAULT 0.000,
        
        -- Catalyst Analysis
        catalyst_type VARCHAR(50),
        catalyst_strength VARCHAR(20) CHECK (catalyst_strength IN ('weak', 'moderate', 'strong')),
        price_impact_expected VARCHAR(20) CHECK (price_impact_expected IN ('negative', 'neutral', 'positive')),
        
        -- Processing
        processed BOOLEAN DEFAULT FALSE,
        processing_notes TEXT,
        
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_news_articles_symbols ON news_articles USING GIN(symbols);
    CREATE INDEX IF NOT EXISTS idx_news_articles_published ON news_articles(published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_news_articles_source ON news_articles(source);
    CREATE INDEX IF NOT EXISTS idx_news_articles_relevance ON news_articles(relevance_score DESC);
    CREATE INDEX IF NOT EXISTS idx_news_articles_catalyst ON news_articles(catalyst_type, catalyst_strength);
    """

async def insert_default_risk_parameters():
    """Insert default risk management parameters"""
    return """
    INSERT INTO risk_parameters (parameter_name, parameter_value, parameter_type, description) 
    VALUES 
        ('max_daily_loss', 2000.00, 'currency', 'Maximum daily loss in dollars'),
        ('max_position_size', 0.10, 'percentage', 'Maximum position size as fraction of portfolio'),
        ('max_portfolio_risk', 0.05, 'percentage', 'Maximum total portfolio risk'),
        ('position_size_multiplier', 1.0, 'multiplier', 'Position sizing adjustment factor'),
        ('stop_loss_atr_multiple', 2.0, 'multiplier', 'Stop loss distance in ATR multiples'),
        ('take_profit_atr_multiple', 3.0, 'multiplier', 'Take profit distance in ATR multiples'),
        ('max_positions', 5, 'integer', 'Maximum concurrent positions'),
        ('risk_free_rate', 0.05, 'percentage', 'Risk-free rate for Sharpe ratio'),
        ('correlation_limit', 0.7, 'percentage', 'Maximum correlation between positions'),
        ('sector_concentration_limit', 0.4, 'percentage', 'Maximum concentration in one sector'),
        ('var_confidence_level', 0.95, 'percentage', 'VaR confidence level'),
        ('lookback_period_days', 252, 'integer', 'Lookback period for risk calculations')
    ON CONFLICT (parameter_name) DO NOTHING;
    """

async def update_existing_tables_for_v42():
    """Update existing tables to support v4.2 features"""
    updates = []
    
    # Add risk-related fields to trading_cycles if missing
    updates.append("""
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'trading_cycles' AND column_name = 'total_risk_budget') THEN
            ALTER TABLE trading_cycles ADD COLUMN total_risk_budget DECIMAL(12,2) DEFAULT 2000.00;
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'trading_cycles' AND column_name = 'used_risk_budget') THEN
            ALTER TABLE trading_cycles ADD COLUMN used_risk_budget DECIMAL(12,2) DEFAULT 0.00;
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'trading_cycles' AND column_name = 'current_positions') THEN
            ALTER TABLE trading_cycles ADD COLUMN current_positions INTEGER DEFAULT 0;
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'trading_cycles' AND column_name = 'current_exposure') THEN
            ALTER TABLE trading_cycles ADD COLUMN current_exposure DECIMAL(12,2) DEFAULT 0.00;
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'trading_cycles' AND column_name = 'risk_events') THEN
            ALTER TABLE trading_cycles ADD COLUMN risk_events INTEGER DEFAULT 0;
        END IF;
    END $$;
    """)
    
    # Add risk metrics to positions table if missing  
    updates.append("""
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'positions' AND column_name = 'risk_amount') THEN
            ALTER TABLE positions ADD COLUMN risk_amount DECIMAL(12,2);
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'positions' AND column_name = 'max_risk_percent') THEN
            ALTER TABLE positions ADD COLUMN max_risk_percent DECIMAL(4,3);
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'positions' AND column_name = 'sector') THEN
            ALTER TABLE positions ADD COLUMN sector VARCHAR(50);
        END IF;
    END $$;
    """)
    
    return updates

async def create_v42_triggers():
    """Create triggers for v4.2 functionality"""
    return [
        # Update timestamp trigger for risk_parameters
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
        
        """
        DROP TRIGGER IF EXISTS update_risk_parameters_updated_at ON risk_parameters;
        CREATE TRIGGER update_risk_parameters_updated_at
            BEFORE UPDATE ON risk_parameters
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """,
        
        """
        DROP TRIGGER IF EXISTS update_daily_risk_metrics_updated_at ON daily_risk_metrics;
        CREATE TRIGGER update_daily_risk_metrics_updated_at
            BEFORE UPDATE ON daily_risk_metrics
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """,
        
        """
        DROP TRIGGER IF EXISTS update_news_articles_updated_at ON news_articles;
        CREATE TRIGGER update_news_articles_updated_at
            BEFORE UPDATE ON news_articles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    ]

async def main():
    """Main upgrade routine"""
    print("🎩 Catalyst Trading System - v4.2 Schema Upgrade")
    print("=" * 60)
    
    # Check environment
    if not os.getenv("DATABASE_URL"):
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    print("\n📊 1. Checking Current Schema...")
    print("-" * 40)
    
    existing_tables = await check_existing_tables()
    if isinstance(existing_tables, str):
        print(f"❌ Error: {existing_tables}")
        return
    
    print(f"✅ Found {len(existing_tables)} existing tables:")
    for table in existing_tables:
        print(f"   📋 {table}")
    
    missing_tables = []
    required_v42_tables = ['risk_parameters', 'daily_risk_metrics', 'risk_events', 'news_articles']
    
    for table in required_v42_tables:
        if table not in existing_tables:
            missing_tables.append(table)
    
    if missing_tables:
        print(f"\n⚠️  Missing v4.2 tables: {', '.join(missing_tables)}")
    else:
        print("\n✅ All v4.2 tables already exist!")
    
    print("\n🔧 2. Creating Missing Tables...")
    print("-" * 40)
    
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        # Create missing tables
        table_creators = {
            'risk_parameters': create_risk_parameters_table,
            'daily_risk_metrics': create_daily_risk_metrics_table,
            'risk_events': create_risk_events_table,
            'news_articles': create_news_articles_table
        }
        
        for table_name in missing_tables:
            if table_name in table_creators:
                print(f"📋 Creating {table_name}...")
                sql = await table_creators[table_name]()
                await conn.execute(sql)
                print(f"✅ Created {table_name}")
        
        # Update existing tables
        print("\n🔄 3. Updating Existing Tables for v4.2...")
        print("-" * 40)
        
        updates = await update_existing_tables_for_v42()
        for update_sql in updates:
            await conn.execute(update_sql)
        print("✅ Updated existing tables with v4.2 fields")
        
        # Create triggers
        print("\n⚡ 4. Creating Triggers...")
        print("-" * 40)
        
        triggers = await create_v42_triggers()
        for trigger_sql in triggers:
            await conn.execute(trigger_sql)
        print("✅ Created v4.2 triggers")
        
        # Insert default risk parameters
        print("\n📋 5. Inserting Default Risk Parameters...")
        print("-" * 40)
        
        default_params_sql = await insert_default_risk_parameters()
        await conn.execute(default_params_sql)
        
        # Check how many parameters were inserted
        param_count = await conn.fetchval("SELECT COUNT(*) FROM risk_parameters")
        print(f"✅ Risk parameters configured: {param_count} total")
        
        await conn.close()
        
        print("\n✅ UPGRADE COMPLETE!")
        print("=" * 60)
        print("\n🎯 v4.2 Schema Ready:")
        print("   ✅ Risk management tables created")
        print("   ✅ News catalyst tracking enabled")
        print("   ✅ Enhanced position tracking")
        print("   ✅ Default risk parameters configured")
        
        print("\n🚀 Next Steps:")
        print("1. 📁 Deploy risk-manager service (port 5004)")
        print("2. 🔄 Restart all services")
        print("3. 🧪 Test risk management functionality")
        print("4. 📊 Monitor risk metrics in real-time")
        
    except Exception as e:
        print(f"❌ Upgrade failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())