#!/usr/bin/env python3
"""
Catalyst Trading System - Fresh Schema Creator
Name of Application: Catalyst Trading System
Name of file: create_schema.py
Version: 4.1.0
Last Updated: 2025-09-14
Purpose: Create v4.1 schema in empty database

REVISION HISTORY:
v4.1.0 (2025-09-14) - Initial schema creation
- Creates all required tables for v4.1
- Sets up indexes and relationships
- Initializes with default data
"""

import psycopg2
import os
import sys
from datetime import datetime

def create_schema():
    """Create fresh v4.1 schema in empty database"""
    
    print("="*60)
    print("🎩 Catalyst Trading System - Schema Creator v4.1")
    print("="*60)
    print("\nYour database is empty. Let's create the v4.1 schema!")
    print("\nEnter your DigitalOcean connection string:")
    
    db_url = input("Connection string: ").strip()
    if not db_url:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            print("❌ No connection string provided!")
            return
    
    try:
        print("\n📡 Connecting to DigitalOcean database...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Verify database is empty
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        table_count = cur.fetchone()[0]
        print(f"✅ Connected! Found {table_count} existing tables.")
        
        if table_count > 0:
            response = input(f"\n⚠️  Database has {table_count} tables. Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                return
        
        print("\n🔨 Creating v4.1 schema...")
        print("-" * 40)
        
        # Create helper function
        print("  Creating helper functions...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        # 1. Create trading_cycles table (master table)
        print("  Creating trading_cycles table...")
        cur.execute("""
            CREATE TABLE trading_cycles (
                cycle_id VARCHAR(20) PRIMARY KEY,
                mode VARCHAR(20) NOT NULL CHECK (mode IN ('aggressive', 'normal', 'conservative')),
                status VARCHAR(20) NOT NULL DEFAULT 'active' 
                    CHECK (status IN ('active', 'paused', 'stopped')),
                scan_frequency INTEGER NOT NULL CHECK (scan_frequency BETWEEN 60 AND 3600),
                max_positions INTEGER NOT NULL DEFAULT 5 CHECK (max_positions BETWEEN 1 AND 10),
                risk_level DECIMAL(3,2) NOT NULL DEFAULT 0.5 CHECK (risk_level BETWEEN 0.0 AND 1.0),
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                stopped_at TIMESTAMPTZ,
                stop_reason VARCHAR(100),
                configuration JSONB DEFAULT '{}',
                metrics JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX idx_trading_cycles_status ON trading_cycles(status);
            CREATE INDEX idx_trading_cycles_started_at ON trading_cycles(started_at DESC);
            
            CREATE TRIGGER update_trading_cycles_updated_at 
                BEFORE UPDATE ON trading_cycles
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        # 2. Create orders table
        print("  Creating orders table...")
        cur.execute("""
            CREATE TABLE orders (
                order_id VARCHAR(50) PRIMARY KEY,
                cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
                symbol VARCHAR(10) NOT NULL,
                direction VARCHAR(10) NOT NULL CHECK (direction IN ('buy', 'sell')),
                order_type VARCHAR(20) NOT NULL 
                    CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                limit_price DECIMAL(10,2),
                stop_price DECIMAL(10,2),
                time_in_force VARCHAR(10) DEFAULT 'day' 
                    CHECK (time_in_force IN ('day', 'gtc', 'ioc', 'fok')),
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'submitted', 'partial', 'filled', 'cancelled', 'rejected')),
                submitted_at TIMESTAMPTZ,
                filled_at TIMESTAMPTZ,
                executed_price DECIMAL(10,2),
                executed_quantity INTEGER,
                commission DECIMAL(8,2),
                reject_reason VARCHAR(200),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX idx_orders_cycle ON orders(cycle_id);
            CREATE INDEX idx_orders_symbol ON orders(symbol);
            CREATE INDEX idx_orders_status ON orders(status);
            CREATE INDEX idx_orders_created ON orders(created_at DESC);
            
            CREATE TRIGGER update_orders_updated_at 
                BEFORE UPDATE ON orders
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        # 3. Create positions table
        print("  Creating positions table...")
        cur.execute("""
            CREATE TABLE positions (
                position_id SERIAL PRIMARY KEY,
                cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
                symbol VARCHAR(10) NOT NULL,
                side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                entry_order_id VARCHAR(50) REFERENCES orders(order_id),
                exit_order_id VARCHAR(50) REFERENCES orders(order_id),
                entry_price DECIMAL(10,2) NOT NULL,
                exit_price DECIMAL(10,2),
                stop_loss DECIMAL(10,2),
                take_profit DECIMAL(10,2),
                status VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'closed', 'partial')),
                opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at TIMESTAMPTZ,
                unrealized_pnl DECIMAL(12,2),
                realized_pnl DECIMAL(12,2),
                pnl_percent DECIMAL(6,2),
                max_profit DECIMAL(12,2),
                max_loss DECIMAL(12,2),
                risk_score DECIMAL(3,2),
                close_reason VARCHAR(100),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX idx_positions_cycle ON positions(cycle_id);
            CREATE INDEX idx_positions_symbol ON positions(symbol);
            CREATE INDEX idx_positions_status ON positions(status);
            CREATE INDEX idx_positions_open ON positions(status, opened_at DESC) WHERE status = 'open';
            
            CREATE TRIGGER update_positions_updated_at 
                BEFORE UPDATE ON positions
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        # 4. Create pattern_detections table
        print("  Creating pattern_detections table...")
        cur.execute("""
            CREATE TABLE pattern_detections (
                detection_id SERIAL PRIMARY KEY,
                cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
                symbol VARCHAR(10) NOT NULL,
                pattern_type VARCHAR(50) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                confidence DECIMAL(3,2) CHECK (confidence BETWEEN 0.0 AND 1.0),
                entry_point DECIMAL(10,2),
                target_price DECIMAL(10,2),
                stop_loss DECIMAL(10,2),
                risk_reward_ratio DECIMAL(4,2),
                pattern_data JSONB DEFAULT '{}',
                detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                valid_until TIMESTAMPTZ,
                profitable BOOLEAN DEFAULT NULL,
                actual_outcome DECIMAL(10,2) DEFAULT NULL,
                outcome_verified_at TIMESTAMPTZ DEFAULT NULL
            );
            
            CREATE INDEX idx_patterns_cycle ON pattern_detections(cycle_id);
            CREATE INDEX idx_patterns_symbol ON pattern_detections(symbol, detected_at DESC);
            CREATE INDEX idx_patterns_type ON pattern_detections(pattern_type);
            CREATE INDEX idx_patterns_confidence ON pattern_detections(confidence DESC);
        """)
        
        # 5. Create scan_results table (simplified, non-partitioned for now)
        print("  Creating scan_results table...")
        cur.execute("""
            CREATE TABLE scan_results (
                scan_id VARCHAR(50) NOT NULL,
                cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
                symbol VARCHAR(10) NOT NULL,
                scan_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                price DECIMAL(10,2) NOT NULL,
                volume BIGINT NOT NULL,
                change_percent DECIMAL(6,2),
                momentum_score DECIMAL(5,2),
                catalyst_score DECIMAL(5,2),
                pattern_score DECIMAL(5,2),
                technical_score DECIMAL(5,2),
                catalysts JSONB DEFAULT '[]',
                patterns JSONB DEFAULT '[]',
                signals JSONB DEFAULT '{}',
                is_selected BOOLEAN DEFAULT FALSE,
                selection_rank INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (scan_id, symbol, scan_time)
            );
            
            CREATE INDEX idx_scan_results_cycle ON scan_results(cycle_id);
            CREATE INDEX idx_scan_results_symbol ON scan_results(symbol, scan_time DESC);
        """)
        
        # 6. Create trading_signals table
        print("  Creating trading_signals table...")
        cur.execute("""
            CREATE TABLE trading_signals (
                signal_id SERIAL PRIMARY KEY,
                cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
                symbol VARCHAR(10) NOT NULL,
                signal_type VARCHAR(50) NOT NULL,
                signal_strength VARCHAR(20) CHECK (signal_strength IN ('weak', 'moderate', 'strong')),
                confidence DECIMAL(3,2) CHECK (confidence BETWEEN 0.0 AND 1.0),
                action VARCHAR(20) CHECK (action IN ('buy', 'sell', 'hold', 'close')),
                source VARCHAR(50) NOT NULL,
                parameters JSONB DEFAULT '{}',
                active BOOLEAN DEFAULT TRUE,
                triggered_at TIMESTAMPTZ,
                expired_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX idx_signals_cycle ON trading_signals(cycle_id);
            CREATE INDEX idx_signals_symbol ON trading_signals(symbol, created_at DESC);
            CREATE INDEX idx_signals_active ON trading_signals(active, symbol) WHERE active = TRUE;
        """)
        
        # 7. Create news_catalysts table
        print("  Creating news_catalysts table...")
        cur.execute("""
            CREATE TABLE news_catalysts (
                catalyst_id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                headline TEXT NOT NULL,
                summary TEXT,
                source VARCHAR(100),
                url TEXT,
                sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
                sentiment_score DECIMAL(3,2),
                relevance_score DECIMAL(3,2),
                impact_level VARCHAR(20) CHECK (impact_level IN ('low', 'medium', 'high', 'critical')),
                categories TEXT[],
                entities JSONB DEFAULT '[]',
                published_at TIMESTAMPTZ NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX idx_news_symbol ON news_catalysts(symbol, published_at DESC);
            CREATE INDEX idx_news_published ON news_catalysts(published_at DESC);
        """)
        
        # 8. Create service_health table
        print("  Creating service_health table...")
        cur.execute("""
            CREATE TABLE service_health (
                health_id SERIAL PRIMARY KEY,
                service_name VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'offline')),
                uptime_seconds INTEGER,
                cpu_usage DECIMAL(5,2),
                memory_usage DECIMAL(5,2),
                last_heartbeat TIMESTAMPTZ NOT NULL,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX idx_health_service ON service_health(service_name, created_at DESC);
        """)
        
        # 9. Create initial trading cycle
        print("  Creating initial trading cycle...")
        cur.execute("""
            INSERT INTO trading_cycles (
                cycle_id,
                mode,
                status,
                scan_frequency,
                max_positions,
                risk_level,
                configuration
            ) VALUES (
                'INITIAL_' || TO_CHAR(NOW(), 'YYYYMMDD'),
                'normal',
                'paused',
                300,
                5,
                0.5,
                '{
                    "stop_loss_percent": 2.0,
                    "take_profit_percent": 4.0,
                    "max_position_size": 1000,
                    "min_volume": 1000000,
                    "min_price": 5.0,
                    "max_price": 500.0
                }'::jsonb
            );
        """)
        
        # Commit all changes
        conn.commit()
        print("\n✅ Schema created successfully!")
        
        # Verify tables were created
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        print("\n📊 Created tables:")
        print("-" * 40)
        for table in tables:
            print(f"  ✅ {table[0]}")
        
        print("\n🎉 SUCCESS!")
        print("="*60)
        print("\nNext steps:")
        print("1. Restart Docker services:")
        print("   docker-compose down")
        print("   docker-compose up -d")
        print("\n2. Check logs for errors:")
        print("   docker-compose logs --tail=100")
        print("\n3. Services should now start without database errors!")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

if __name__ == "__main__":
    create_schema()