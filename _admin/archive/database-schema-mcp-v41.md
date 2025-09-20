# Catalyst Trading System - Database Schema v4.1

**Name of Application**: Catalyst Trading System  
**Name of file**: database-schema-mcp-v41.md  
**Version**: 4.1.0  
**Last Updated**: 2025-08-31  
**Purpose**: Complete database schema with proper indexing and relationships

**REVISION HISTORY**:
- v4.1.0 (2025-08-31) - Production-ready schema
  - Optimized for high-frequency trading operations
  - Proper partitioning for time-series data
  - Comprehensive indexing strategy
  - JSONB for flexible data storage

**Description**:
PostgreSQL database schema optimized for the Catalyst Trading System, supporting high-frequency trading operations with proper partitioning and indexing.

---

## Database Configuration

### DigitalOcean Managed PostgreSQL
```yaml
Provider: DigitalOcean
Service: Managed PostgreSQL
Version: 15
Plan: Professional (4 vCPUs, 8GB RAM)
Storage: 100GB SSD
Replicas: 1 standby
Connection Pool: 100 connections
Location: NYC3
```

---

## Core Tables

### 1. Trading Cycles

```sql
-- Trading cycles table
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

-- Indexes
CREATE INDEX idx_trading_cycles_status ON trading_cycles(status);
CREATE INDEX idx_trading_cycles_started_at ON trading_cycles(started_at DESC);
CREATE INDEX idx_trading_cycles_active ON trading_cycles(status, started_at DESC) 
    WHERE status = 'active';

-- Trigger for updated_at
CREATE TRIGGER update_trading_cycles_updated_at 
    BEFORE UPDATE ON trading_cycles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 2. Scan Results

```sql
-- Partitioned by date for performance
CREATE TABLE scan_results (
    scan_id VARCHAR(50) NOT NULL,
    cycle_id VARCHAR(20) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    scan_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    change_percent DECIMAL(6,2),
    momentum_score DECIMAL(5,2) CHECK (momentum_score BETWEEN 0 AND 100),
    catalyst_score DECIMAL(5,2) CHECK (catalyst_score BETWEEN 0 AND 100),
    pattern_score DECIMAL(5,2) CHECK (pattern_score BETWEEN 0 AND 100),
    technical_score DECIMAL(5,2) CHECK (technical_score BETWEEN 0 AND 100),
    total_score DECIMAL(5,2) GENERATED ALWAYS AS (
        (momentum_score * 0.3 + catalyst_score * 0.3 + 
         pattern_score * 0.2 + technical_score * 0.2)
    ) STORED,
    catalysts JSONB DEFAULT '[]',
    patterns JSONB DEFAULT '[]',
    signals JSONB DEFAULT '{}',
    is_selected BOOLEAN DEFAULT FALSE,
    selection_rank INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scan_time, scan_id, symbol)
) PARTITION BY RANGE (scan_time);

-- Create partitions for each month
CREATE TABLE scan_results_2025_08 PARTITION OF scan_results
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE scan_results_2025_09 PARTITION OF scan_results
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');

-- Indexes
CREATE INDEX idx_scan_results_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_results_symbol ON scan_results(symbol, scan_time DESC);
CREATE INDEX idx_scan_results_selected ON scan_results(is_selected, total_score DESC) 
    WHERE is_selected = TRUE;
CREATE INDEX idx_scan_results_scores ON scan_results(total_score DESC);
CREATE INDEX idx_scan_results_catalysts ON scan_results USING GIN (catalysts);
```

### 3. Orders

```sql
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL,
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

-- Indexes
CREATE INDEX idx_orders_cycle ON orders(cycle_id);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created ON orders(created_at DESC);
CREATE INDEX idx_orders_pending ON orders(status, created_at) 
    WHERE status IN ('pending', 'submitted');

-- Foreign key
ALTER TABLE orders ADD CONSTRAINT fk_orders_cycle 
    FOREIGN KEY (cycle_id) REFERENCES trading_cycles(cycle_id);
```

### 4. Positions

```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_order_id VARCHAR(50) NOT NULL,
    exit_order_id VARCHAR(50),
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'partial')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    hold_duration INTERVAL GENERATED ALWAYS AS (
        COALESCE(closed_at, NOW()) - opened_at
    ) STORED,
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

-- Indexes
CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_open ON positions(status, opened_at DESC) WHERE status = 'open';
CREATE INDEX idx_positions_pnl ON positions(realized_pnl DESC) WHERE status = 'closed';

-- Foreign keys
ALTER TABLE positions ADD CONSTRAINT fk_positions_cycle 
    FOREIGN KEY (cycle_id) REFERENCES trading_cycles(cycle_id);
ALTER TABLE positions ADD CONSTRAINT fk_positions_entry_order 
    FOREIGN KEY (entry_order_id) REFERENCES orders(order_id);
ALTER TABLE positions ADD CONSTRAINT fk_positions_exit_order 
    FOREIGN KEY (exit_order_id) REFERENCES orders(order_id);
```

### 5. Trading Signals

```sql
CREATE TABLE trading_signals (
    signal_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL,
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

-- Indexes
CREATE INDEX idx_signals_cycle ON trading_signals(cycle_id);
CREATE INDEX idx_signals_symbol ON trading_signals(symbol, created_at DESC);
CREATE INDEX idx_signals_active ON trading_signals(active, symbol) WHERE active = TRUE;
CREATE INDEX idx_signals_type ON trading_signals(signal_type);
```

### 6. Pattern Detections

```sql
CREATE TABLE pattern_detections (
    detection_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL,
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
    valid_until TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_patterns_cycle ON pattern_detections(cycle_id);
CREATE INDEX idx_patterns_symbol ON pattern_detections(symbol, detected_at DESC);
CREATE INDEX idx_patterns_type ON pattern_detections(pattern_type);
CREATE INDEX idx_patterns_confidence ON pattern_detections(confidence DESC);
```

### 7. News Catalysts

```sql
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

-- Indexes
CREATE INDEX idx_news_symbol ON news_catalysts(symbol, published_at DESC);
CREATE INDEX idx_news_published ON news_catalysts(published_at DESC);
CREATE INDEX idx_news_sentiment ON news_catalysts(sentiment, sentiment_score);
CREATE INDEX idx_news_impact ON news_catalysts(impact_level) WHERE impact_level IN ('high', 'critical');
CREATE INDEX idx_news_categories ON news_catalysts USING GIN (categories);
```

### 8. Performance Metrics

```sql
CREATE TABLE performance_metrics (
    metric_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL,
    metric_date DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE WHEN total_trades > 0 
        THEN (winning_trades::DECIMAL / total_trades * 100)
        ELSE 0 END
    ) STORED,
    gross_pnl DECIMAL(12,2) DEFAULT 0,
    commissions DECIMAL(10,2) DEFAULT 0,
    net_pnl DECIMAL(12,2) GENERATED ALWAYS AS (gross_pnl - commissions) STORED,
    average_win DECIMAL(10,2),
    average_loss DECIMAL(10,2),
    largest_win DECIMAL(10,2),
    largest_loss DECIMAL(10,2),
    profit_factor DECIMAL(6,2),
    sharpe_ratio DECIMAL(6,2),
    max_drawdown DECIMAL(10,2),
    recovery_factor DECIMAL(6,2),
    avg_hold_time INTERVAL,
    total_volume BIGINT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(cycle_id, metric_date)
);

-- Indexes
CREATE INDEX idx_metrics_cycle ON performance_metrics(cycle_id);
CREATE INDEX idx_metrics_date ON performance_metrics(metric_date DESC);
CREATE INDEX idx_metrics_pnl ON performance_metrics(net_pnl DESC);
```

### 9. Audit Log

```sql
CREATE TABLE audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    cycle_id VARCHAR(20),
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(50),
    user_action VARCHAR(100),
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE audit_log_2025_08 PARTITION OF audit_log
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

-- Indexes
CREATE INDEX idx_audit_cycle ON audit_log(cycle_id);
CREATE INDEX idx_audit_event ON audit_log(event_type);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
```

---

## Views

### 1. Active Trading View

```sql
CREATE VIEW v_active_trading AS
SELECT 
    tc.cycle_id,
    tc.mode,
    tc.status as cycle_status,
    p.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.unrealized_pnl,
    p.risk_score,
    sr.total_score as scan_score,
    sr.catalysts,
    ts.signal_type,
    ts.confidence as signal_confidence
FROM trading_cycles tc
JOIN positions p ON tc.cycle_id = p.cycle_id
LEFT JOIN LATERAL (
    SELECT * FROM scan_results 
    WHERE symbol = p.symbol 
    ORDER BY scan_time DESC 
    LIMIT 1
) sr ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM trading_signals
    WHERE symbol = p.symbol AND active = TRUE
    ORDER BY created_at DESC
    LIMIT 1
) ts ON TRUE
WHERE tc.status = 'active' 
  AND p.status = 'open';
```

### 2. Daily Performance View

```sql
CREATE VIEW v_daily_performance AS
SELECT 
    DATE(p.closed_at) as trading_date,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE realized_pnl > 0) as winning_trades,
    COUNT(*) FILTER (WHERE realized_pnl < 0) as losing_trades,
    SUM(realized_pnl) as total_pnl,
    AVG(realized_pnl) as avg_pnl,
    MAX(realized_pnl) as best_trade,
    MIN(realized_pnl) as worst_trade,
    AVG(EXTRACT(EPOCH FROM hold_duration)/3600)::DECIMAL(8,2) as avg_hold_hours
FROM positions p
WHERE p.status = 'closed'
  AND p.closed_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(p.closed_at)
ORDER BY trading_date DESC;
```

---

## Functions

### 1. Calculate Position Risk

```sql
CREATE OR REPLACE FUNCTION calculate_position_risk(
    p_position_id INTEGER
) RETURNS DECIMAL AS $$
DECLARE
    v_risk_score DECIMAL(3,2);
    v_position RECORD;
BEGIN
    SELECT * INTO v_position FROM positions WHERE position_id = p_position_id;
    
    -- Calculate risk based on multiple factors
    v_risk_score := 0.0;
    
    -- PnL factor
    IF v_position.unrealized_pnl < -500 THEN
        v_risk_score := v_risk_score + 0.3;
    ELSIF v_position.unrealized_pnl < -200 THEN
        v_risk_score := v_risk_score + 0.2;
    END IF;
    
    -- Hold duration factor
    IF v_position.hold_duration > INTERVAL '4 hours' THEN
        v_risk_score := v_risk_score + 0.2;
    END IF;
    
    -- Stop loss distance factor
    IF v_position.stop_loss IS NOT NULL THEN
        IF ABS(v_position.entry_price - v_position.stop_loss) / v_position.entry_price > 0.05 THEN
            v_risk_score := v_risk_score + 0.2;
        END IF;
    ELSE
        v_risk_score := v_risk_score + 0.3; -- No stop loss
    END IF;
    
    RETURN LEAST(v_risk_score, 1.0);
END;
$$ LANGUAGE plpgsql;
```

### 2. Update Metrics

```sql
CREATE OR REPLACE FUNCTION update_performance_metrics(
    p_cycle_id VARCHAR(20),
    p_date DATE DEFAULT CURRENT_DATE
) RETURNS VOID AS $$
BEGIN
    INSERT INTO performance_metrics (
        cycle_id,
        metric_date,
        total_trades,
        winning_trades,
        losing_trades,
        gross_pnl,
        commissions,
        average_win,
        average_loss,
        largest_win,
        largest_loss,
        avg_hold_time
    )
    SELECT 
        p_cycle_id,
        p_date,
        COUNT(*),
        COUNT(*) FILTER (WHERE realized_pnl > 0),
        COUNT(*) FILTER (WHERE realized_pnl < 0),
        COALESCE(SUM(realized_pnl), 0),
        COALESCE(SUM(o.commission), 0),
        AVG(realized_pnl) FILTER (WHERE realized_pnl > 0),
        AVG(realized_pnl) FILTER (WHERE realized_pnl < 0),
        MAX(realized_pnl),
        MIN(realized_pnl),
        AVG(hold_duration)
    FROM positions p
    JOIN orders o ON p.exit_order_id = o.order_id
    WHERE p.cycle_id = p_cycle_id
      AND DATE(p.closed_at) = p_date
      AND p.status = 'closed'
    ON CONFLICT (cycle_id, metric_date) 
    DO UPDATE SET
        total_trades = EXCLUDED.total_trades,
        winning_trades = EXCLUDED.winning_trades,
        losing_trades = EXCLUDED.losing_trades,
        gross_pnl = EXCLUDED.gross_pnl,
        commissions = EXCLUDED.commissions,
        average_win = EXCLUDED.average_win,
        average_loss = EXCLUDED.average_loss,
        largest_win = EXCLUDED.largest_win,
        largest_loss = EXCLUDED.largest_loss,
        avg_hold_time = EXCLUDED.avg_hold_time,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;
```

---

## Triggers

### 1. Update Timestamp Trigger

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    
CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 2. Position Close Trigger

```sql
CREATE OR REPLACE FUNCTION on_position_closed()
RETURNS TRIGGER AS $$
BEGIN
    -- Calculate realized PnL
    NEW.realized_pnl := (NEW.exit_price - NEW.entry_price) * NEW.quantity;
    NEW.pnl_percent := ((NEW.exit_price - NEW.entry_price) / NEW.entry_price) * 100;
    
    -- Update metrics
    PERFORM update_performance_metrics(NEW.cycle_id, DATE(NEW.closed_at));
    
    -- Log event
    INSERT INTO audit_log (cycle_id, event_type, event_category, entity_type, entity_id, details)
    VALUES (
        NEW.cycle_id,
        'position_closed',
        'trading',
        'position',
        NEW.position_id::VARCHAR,
        jsonb_build_object(
            'symbol', NEW.symbol,
            'pnl', NEW.realized_pnl,
            'close_reason', NEW.close_reason
        )
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER position_closed_trigger
    BEFORE UPDATE OF status ON positions
    FOR EACH ROW
    WHEN (OLD.status = 'open' AND NEW.status = 'closed')
    EXECUTE FUNCTION on_position_closed();
```

---

## Indexes Strategy

### Query Patterns and Indexes

```sql
-- Most common queries and their indexes

-- 1. Get active cycle
-- Query: SELECT * FROM trading_cycles WHERE status = 'active' ORDER BY started_at DESC LIMIT 1
-- Index: idx_trading_cycles_active

-- 2. Get latest scan results for selection
-- Query: SELECT * FROM scan_results WHERE is_selected = true ORDER BY total_score DESC
-- Index: idx_scan_results_selected

-- 3. Get open positions
-- Query: SELECT * FROM positions WHERE status = 'open' AND cycle_id = ?
-- Index: idx_positions_open

-- 4. Get pending orders
-- Query: SELECT * FROM orders WHERE status IN ('pending', 'submitted') ORDER BY created_at
-- Index: idx_orders_pending

-- 5. Get recent news for symbol
-- Query: SELECT * FROM news_catalysts WHERE symbol = ? ORDER BY published_at DESC
-- Index: idx_news_symbol

-- 6. Get active signals
-- Query: SELECT * FROM trading_signals WHERE active = true AND symbol = ?
-- Index: idx_signals_active
```

---

## Maintenance Scripts

### 1. Partition Maintenance

```sql
-- Create next month's partitions
CREATE OR REPLACE FUNCTION create_monthly_partitions()
RETURNS VOID AS $$
DECLARE
    v_start_date DATE;
    v_end_date DATE;
    v_partition_name TEXT;
BEGIN
    v_start_date := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    v_end_date := v_start_date + INTERVAL '1 month';
    
    -- Scan results partition
    v_partition_name := 'scan_results_' || TO_CHAR(v_start_date, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF scan_results FOR VALUES FROM (%L) TO (%L)',
        v_partition_name, v_start_date, v_end_date
    );
    
    -- Audit log partition
    v_partition_name := 'audit_log_' || TO_CHAR(v_start_date, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_log FOR VALUES FROM (%L) TO (%L)',
        v_partition_name, v_start_date, v_end_date
    );
END;
$$ LANGUAGE plpgsql;

-- Schedule monthly
SELECT cron.schedule('create_partitions', '0 0 1 * *', 'SELECT create_monthly_partitions()');
```

### 2. Data Cleanup

```sql
-- Clean old data
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS VOID AS $$
BEGIN
    -- Delete old scan results (keep 30 days)
    DELETE FROM scan_results WHERE scan_time < CURRENT_DATE - INTERVAL '30 days';
    
    -- Archive closed positions older than 90 days
    INSERT INTO positions_archive SELECT * FROM positions 
    WHERE status = 'closed' AND closed_at < CURRENT_DATE - INTERVAL '90 days';
    
    DELETE FROM positions 
    WHERE status = 'closed' AND closed_at < CURRENT_DATE - INTERVAL '90 days';
    
    -- Clean old audit logs (keep 180 days)
    DELETE FROM audit_log WHERE created_at < CURRENT_DATE - INTERVAL '180 days';
    
    -- Vacuum analyze
    VACUUM ANALYZE;
END;
$$ LANGUAGE plpgsql;

-- Schedule daily at 2 AM
SELECT cron.schedule('cleanup_data', '0 2 * * *', 'SELECT cleanup_old_data()');
```

---

## Performance Optimization

### Connection Pool Settings

```sql
-- Recommended settings for postgresql.conf
max_connections = 200
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10MB
min_wal_size = 1GB
max_wal_size = 4GB
```

### Query Optimization

```sql
-- Analyze tables regularly
ANALYZE trading_cycles;
ANALYZE scan_results;
ANALYZE positions;
ANALYZE orders;

-- Monitor slow queries
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View slow queries
SELECT 
    calls,
    mean,
    query
FROM pg_stat_statements
WHERE mean > 100  -- queries taking more than 100ms
ORDER BY mean DESC
LIMIT 10;
```

---

## Backup and Recovery

### Backup Strategy

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
DATABASE_URL="postgresql://user:pass@host:port/catalyst_trading"

# Full backup
pg_dump $DATABASE_URL --format=custom --file=/backups/catalyst_${DATE}.dump

# Keep last 30 days
find /backups -name "catalyst_*.dump" -mtime +30 -delete

# Upload to S3
aws s3 cp /backups/catalyst_${DATE}.dump s3://catalyst-backups/
```

### Recovery Procedure

```bash
# Restore from backup
pg_restore --dbname=$DATABASE_URL --clean --if-exists /backups/catalyst_20250831.dump

# Point-in-time recovery
pg_basebackup -h localhost -D /var/lib/postgresql/recovery -R -P
```

---

## Security

### Row Level Security

```sql
-- Enable RLS on sensitive tables
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY orders_policy ON orders
    FOR ALL
    USING (cycle_id IN (
        SELECT cycle_id FROM trading_cycles 
        WHERE status = 'active'
    ));
```

### Audit Requirements

```sql
-- Comprehensive audit trigger
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        event_type,
        event_category,
        entity_type,
        entity_id,
        details
    ) VALUES (
        TG_OP,
        TG_TABLE_SCHEMA,
        TG_TABLE_NAME,
        CASE 
            WHEN TG_OP = 'DELETE' THEN OLD.id::TEXT
            ELSE NEW.id::TEXT
        END,
        jsonb_build_object(
            'operation', TG_OP,
            'old', to_jsonb(OLD),
            'new', to_jsonb(NEW)
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## Conclusion

This v4.1 database schema provides:

- ✅ **Optimized structure** for high-frequency trading
- ✅ **Proper partitioning** for time-series data
- ✅ **Comprehensive indexing** for query performance
- ✅ **JSONB flexibility** for dynamic data
- ✅ **Audit trails** and security
- ✅ **Maintenance automation** scripts

---

*DevGenius Hat Status: Schema optimized* 🎩