# Catalyst Trading System - Database Schema v4.2

**Name of Application**: Catalyst Trading System  
**Name of file**: database-schema-mcp-v42.md  
**Version**: 4.2.0  
**Last Updated**: 2025-09-20  
**Purpose**: Complete database schema with integrated risk management

**REVISION HISTORY**:

- v4.2.0 (2025-09-20) - Added Risk Management Tables
  - Added risk_parameters table for dynamic risk configuration
  - Added daily_risk_metrics table for daily risk tracking
  - Added risk_events table for risk alerts and violations
  - Added position_risk_metrics table for individual position risk
  - Enhanced positions table with risk-related fields
  - Added portfolio_exposure table for exposure tracking
  - Added risk management functions and triggers

**Description**:
Complete PostgreSQL database schema supporting all trading operations with comprehensive risk management, real-time risk tracking, and safety controls.

---

## Table of Contents

1. [Core Trading Tables](#1-core-trading-tables)
2. [Risk Management Tables](#2-risk-management-tables)
3. [Enhanced Reporting Tables](#3-enhanced-reporting-tables)
4. [Views with Risk Integration](#4-views-with-risk-integration)
5. [Risk Management Functions](#5-risk-management-functions)
6. [Triggers and Constraints](#6-triggers-and-constraints)
7. [Indexes for Performance](#7-indexes-for-performance)

---

## 1. Core Trading Tables

### 1.1 Trading Cycles (Enhanced)

```sql
CREATE TABLE trading_cycles (
    cycle_id VARCHAR(20) PRIMARY KEY,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('aggressive', 'normal', 'conservative')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'stopped', 'completed', 'emergency_stopped')),

    -- Risk Configuration for Cycle
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
```

### 1.2 Positions (Enhanced with Risk)

```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),

    -- Position Details
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_order_id VARCHAR(50) REFERENCES orders(order_id),
    exit_order_id VARCHAR(50) REFERENCES orders(order_id),
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),

    -- Risk Management
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    risk_amount DECIMAL(12,2) NOT NULL, -- Amount at risk
    position_risk_score DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- 0-100 risk score
    max_position_risk DECIMAL(3,2) NOT NULL DEFAULT 0.02, -- Max % risk for position
    risk_adjusted_size INTEGER, -- Risk-calculated position size

    -- Status and Performance
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'partial', 'risk_reduced')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    hold_duration INTERVAL GENERATED ALWAYS AS (
        CASE WHEN closed_at IS NOT NULL THEN closed_at - opened_at ELSE NULL END
    ) STORED,

    -- P&L and Risk Metrics
    unrealized_pnl DECIMAL(12,2),
    realized_pnl DECIMAL(12,2),
    pnl_percent DECIMAL(6,2),
    max_profit DECIMAL(12,2),
    max_loss DECIMAL(12,2),
    max_drawdown_pct DECIMAL(6,2),

    -- Risk Events
    risk_warnings INTEGER NOT NULL DEFAULT 0,
    risk_violations INTEGER NOT NULL DEFAULT 0,
    stop_loss_triggered BOOLEAN DEFAULT FALSE,
    take_profit_triggered BOOLEAN DEFAULT FALSE,
    risk_reduced_times INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    close_reason VARCHAR(100),
    risk_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 2. Risk Management Tables

### 2.1 Risk Parameters (Dynamic Configuration)

```sql
CREATE TABLE risk_parameters (
    parameter_id SERIAL PRIMARY KEY,
    parameter_name VARCHAR(50) NOT NULL,
    parameter_value DECIMAL(12,4) NOT NULL,
    parameter_type VARCHAR(20) NOT NULL CHECK (parameter_type IN ('limit', 'multiplier', 'percentage', 'amount')),

    -- Metadata
    description TEXT,
    set_by VARCHAR(50) NOT NULL DEFAULT 'system',
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id), -- NULL = global

    -- Timing
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to TIMESTAMPTZ,

    -- Change tracking
    previous_value DECIMAL(12,4),
    change_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure only one active parameter per name per scope
    UNIQUE(parameter_name, cycle_id, effective_from) DEFERRABLE INITIALLY DEFERRED
);

-- Default risk parameters
INSERT INTO risk_parameters (parameter_name, parameter_value, parameter_type, description) VALUES
('max_daily_loss', 2000.00, 'amount', 'Maximum daily loss limit in dollars'),
('max_position_size', 0.10, 'percentage', 'Maximum position size as percentage of portfolio'),
('max_portfolio_risk', 0.05, 'percentage', 'Maximum total portfolio risk'),
('position_size_multiplier', 1.00, 'multiplier', 'Position sizing adjustment factor'),
('stop_loss_atr_multiple', 2.00, 'multiplier', 'Stop loss distance as multiple of ATR'),
('take_profit_atr_multiple', 3.00, 'multiplier', 'Take profit distance as multiple of ATR'),
('max_positions', 5, 'limit', 'Maximum number of concurrent positions'),
('risk_free_rate', 0.05, 'percentage', 'Risk-free rate for Sharpe ratio calculations'),
('correlation_limit', 0.70, 'percentage', 'Maximum correlation between positions'),
('sector_concentration_limit', 0.40, 'percentage', 'Maximum concentration in one sector');
```

### 2.2 Daily Risk Metrics

```sql
CREATE TABLE daily_risk_metrics (
    date DATE PRIMARY KEY,
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id),

    -- Daily P&L and Limits
    daily_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    daily_loss_limit DECIMAL(12,2) NOT NULL DEFAULT 2000.00,
    daily_loss_used_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    remaining_risk_budget DECIMAL(12,2) NOT NULL DEFAULT 2000.00,

    -- Position Metrics
    position_count INTEGER NOT NULL DEFAULT 0,
    max_position_count INTEGER NOT NULL DEFAULT 5,
    total_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    max_exposure_limit DECIMAL(12,2) NOT NULL DEFAULT 10000.00,

    -- Risk Scores and Ratios
    portfolio_risk_score DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- 0-100
    var_95 DECIMAL(12,2), -- Value at Risk 95% confidence
    var_99 DECIMAL(12,2), -- Value at Risk 99% confidence
    max_drawdown DECIMAL(12,2),
    max_drawdown_pct DECIMAL(6,2),

    -- Performance Metrics
    sharpe_ratio DECIMAL(6,3),
    sortino_ratio DECIMAL(6,3),
    win_rate DECIMAL(5,2),
    profit_factor DECIMAL(6,3),

    -- Risk Events
    risk_warnings INTEGER NOT NULL DEFAULT 0,
    risk_violations INTEGER NOT NULL DEFAULT 0,
    emergency_stops INTEGER NOT NULL DEFAULT 0,
    trades_rejected_by_risk INTEGER NOT NULL DEFAULT 0,

    -- Timing
    first_trade_at TIMESTAMPTZ,
    last_trade_at TIMESTAMPTZ,

    -- Metadata
    risk_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.3 Risk Events and Alerts

```sql
CREATE TABLE risk_events (
    event_id SERIAL PRIMARY KEY,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN (
        'daily_loss_warning', 'daily_loss_breach', 'position_risk_high', 
        'correlation_warning', 'emergency_stop', 'risk_limit_updated',
        'position_size_rejected', 'sector_concentration_high'
    )),
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),

    -- Event Details
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,

    -- Context
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id),
    position_id INTEGER REFERENCES positions(position_id),
    symbol VARCHAR(10),

    -- Risk Data Snapshot
    risk_metrics_snapshot JSONB,
    trigger_value DECIMAL(12,4),
    limit_value DECIMAL(12,4),

    -- Response
    action_taken VARCHAR(50),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Metadata
    triggered_by VARCHAR(50) NOT NULL DEFAULT 'system',
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.4 Position Risk Metrics

```sql
CREATE TABLE position_risk_metrics (
    metric_id SERIAL PRIMARY KEY,
    position_id INTEGER NOT NULL REFERENCES positions(position_id),

    -- Risk Calculations
    position_value DECIMAL(12,2) NOT NULL,
    risk_amount DECIMAL(12,2) NOT NULL,
    risk_percentage DECIMAL(5,2) NOT NULL,

    -- Risk Ratios
    risk_reward_ratio DECIMAL(6,3),
    position_beta DECIMAL(6,3),
    position_correlation DECIMAL(6,3),

    -- VaR and Risk Metrics
    position_var_95 DECIMAL(12,2),
    position_var_99 DECIMAL(12,2),
    expected_shortfall DECIMAL(12,2),

    -- Stop Loss Analysis
    stop_loss_distance_pct DECIMAL(5,2),
    stop_loss_atr_multiple DECIMAL(4,2),
    stop_loss_probability DECIMAL(5,2),

    -- Time-based Risk
    time_decay_risk DECIMAL(5,2),
    overnight_risk DECIMAL(5,2),

    -- Calculated at timestamp
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    market_price DECIMAL(10,2) NOT NULL,

    -- Metadata
    calculation_method VARCHAR(50) DEFAULT 'standard',
    risk_model_version VARCHAR(10) DEFAULT '1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.5 Portfolio Exposure Tracking

```sql
CREATE TABLE portfolio_exposure (
    exposure_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id),

    -- Symbol-level Exposure
    symbol VARCHAR(10) NOT NULL,
    sector VARCHAR(50),
    market_cap_category VARCHAR(20) CHECK (market_cap_category IN ('large', 'mid', 'small', 'micro')),

    -- Exposure Amounts
    gross_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    net_exposure DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    exposure_percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,

    -- Risk Contribution
    risk_contribution DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    var_contribution DECIMAL(12,2),
    correlation_risk DECIMAL(5,2),

    -- Position Count
    position_count INTEGER NOT NULL DEFAULT 0,

    -- Timing
    as_of_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint for daily exposure per symbol per cycle
    UNIQUE(date, cycle_id, symbol)
);
```

---

## 3. Enhanced Reporting Tables

### 3.1 Risk-Adjusted Performance Reports

```sql
CREATE TABLE performance_reports (
    report_id SERIAL PRIMARY KEY,
    report_type VARCHAR(20) NOT NULL CHECK (report_type IN ('daily', 'weekly', 'monthly', 'cycle')),
    report_date DATE NOT NULL,
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id),

    -- Basic Performance
    total_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    realized_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    unrealized_pnl DECIMAL(12,2) NOT NULL DEFAULT 0.00,

    -- Trade Statistics
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,2) NOT NULL DEFAULT 0.00,

    -- Risk-Adjusted Metrics
    sharpe_ratio DECIMAL(6,3),
    sortino_ratio DECIMAL(6,3),
    calmar_ratio DECIMAL(6,3),
    max_drawdown DECIMAL(12,2),
    max_drawdown_pct DECIMAL(6,2),

    -- Risk Management Performance
    risk_events_count INTEGER NOT NULL DEFAULT 0,
    trades_rejected_by_risk INTEGER NOT NULL DEFAULT 0,
    risk_rejection_rate DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    avg_position_risk DECIMAL(5,2),
    max_daily_loss_used DECIMAL(5,2),

    -- Portfolio Metrics
    avg_portfolio_exposure DECIMAL(12,2),
    max_portfolio_exposure DECIMAL(12,2),
    avg_position_count DECIMAL(4,1),
    max_position_count INTEGER,

    -- Risk Efficiency
    return_per_unit_risk DECIMAL(8,4),
    risk_adjusted_return DECIMAL(8,4),

    -- Report Metadata
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generated_by VARCHAR(50) DEFAULT 'system',
    report_status VARCHAR(20) DEFAULT 'final',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Views with Risk Integration

### 4.1 Current Portfolio Risk View

```sql
CREATE VIEW v_current_portfolio_risk AS
SELECT 
    tc.cycle_id,
    tc.mode as trading_mode,

    -- Position Summary
    COUNT(p.position_id) as current_positions,
    tc.max_positions,
    ROUND((COUNT(p.position_id)::DECIMAL / tc.max_positions) * 100, 2) as position_utilization_pct,

    -- Exposure Summary
    COALESCE(SUM(p.quantity * p.entry_price), 0) as total_exposure,
    COALESCE(SUM(p.risk_amount), 0) as total_risk_amount,

    -- Daily P&L and Limits
    drm.daily_pnl,
    drm.daily_loss_limit,
    drm.daily_loss_used_pct,
    drm.remaining_risk_budget,

    -- Risk Scores
    drm.portfolio_risk_score,
    COALESCE(AVG(p.position_risk_score), 0) as avg_position_risk_score,
    COALESCE(MAX(p.position_risk_score), 0) as max_position_risk_score,

    -- Risk Status
    CASE 
        WHEN drm.daily_loss_used_pct >= 100 THEN 'DAILY_LIMIT_EXCEEDED'
        WHEN drm.daily_loss_used_pct >= 95 THEN 'CRITICAL_RISK'
        WHEN drm.daily_loss_used_pct >= 80 THEN 'HIGH_RISK'
        WHEN drm.daily_loss_used_pct >= 50 THEN 'MEDIUM_RISK'
        ELSE 'LOW_RISK'
    END as risk_status,

    -- Trading Status
    CASE 
        WHEN tc.status = 'emergency_stopped' THEN FALSE
        WHEN drm.daily_loss_used_pct >= 100 THEN FALSE
        WHEN COUNT(p.position_id) >= tc.max_positions THEN FALSE
        ELSE TRUE
    END as can_open_new_positions,

    tc.updated_at as last_updated

FROM trading_cycles tc
LEFT JOIN positions p ON tc.cycle_id = p.cycle_id AND p.status = 'open'
LEFT JOIN daily_risk_metrics drm ON DATE(NOW()) = drm.date AND tc.cycle_id = drm.cycle_id
WHERE tc.status = 'active'
GROUP BY tc.cycle_id, tc.mode, tc.max_positions, tc.status, tc.updated_at,
         drm.daily_pnl, drm.daily_loss_limit, drm.daily_loss_used_pct, 
         drm.remaining_risk_budget, drm.portfolio_risk_score;
```

### 4.2 Risk Events Summary View

```sql
CREATE VIEW v_risk_events_summary AS
SELECT 
    DATE(created_at) as event_date,
    event_type,
    severity,
    COUNT(*) as event_count,
    COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) as resolved_count,
    COUNT(*) FILTER (WHERE resolved_at IS NULL) as unresolved_count,

    -- Latest event details
    MAX(created_at) as latest_event_time,
    FIRST_VALUE(description) OVER (
        PARTITION BY DATE(created_at), event_type, severity 
        ORDER BY created_at DESC
    ) as latest_description,

    -- Impact metrics
    AVG(trigger_value) as avg_trigger_value,
    MAX(trigger_value) as max_trigger_value,

    -- Response metrics
    COUNT(*) FILTER (WHERE action_taken IS NOT NULL) as actions_taken,
    ARRAY_AGG(DISTINCT action_taken) FILTER (WHERE action_taken IS NOT NULL) as actions_list

FROM risk_events 
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), event_type, severity
ORDER BY event_date DESC, severity DESC, event_count DESC;
```

### 4.3 Position Risk Analysis View

```sql
CREATE VIEW v_position_risk_analysis AS
SELECT 
    p.position_id,
    p.cycle_id,
    p.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.status,

    -- Risk Metrics
    p.risk_amount,
    p.position_risk_score,
    p.stop_loss,
    p.take_profit,

    -- Current Performance
    p.unrealized_pnl,
    CASE 
        WHEN p.entry_price > 0 THEN 
            ROUND((p.unrealized_pnl / (p.quantity * p.entry_price)) * 100, 2)
        ELSE 0 
    END as unrealized_pnl_pct,

    -- Risk Analysis
    CASE 
        WHEN p.stop_loss IS NOT NULL AND p.entry_price > 0 THEN
            ROUND((ABS(p.entry_price - p.stop_loss) / p.entry_price) * 100, 2)
        ELSE NULL
    END as stop_loss_distance_pct,

    -- Risk Status
    CASE 
        WHEN p.position_risk_score >= 80 THEN 'HIGH_RISK'
        WHEN p.position_risk_score >= 60 THEN 'MEDIUM_RISK'
        WHEN p.position_risk_score >= 40 THEN 'LOW_RISK'
        ELSE 'MINIMAL_RISK'
    END as risk_category,

    -- Time Analysis
    p.opened_at,
    EXTRACT(EPOCH FROM (NOW() - p.opened_at))/3600 as hours_held,

    -- Risk Events
    p.risk_warnings,
    p.risk_violations,
    p.risk_reduced_times,

    p.updated_at

FROM positions p
WHERE p.status IN ('open', 'partial')
ORDER BY p.position_risk_score DESC, p.unrealized_pnl ASC;
```

---

## 5. Risk Management Functions

### 5.1 Calculate Position Risk Score

```sql
CREATE OR REPLACE FUNCTION calculate_position_risk_score(
    p_position_id INTEGER
) RETURNS DECIMAL AS $$
DECLARE
    v_position RECORD;
    v_risk_score DECIMAL(5,2) := 0.0;
    v_daily_metrics RECORD;
BEGIN
    -- Get position details
    SELECT * INTO v_position FROM positions WHERE position_id = p_position_id;

    -- Get current daily metrics
    SELECT * INTO v_daily_metrics 
    FROM daily_risk_metrics 
    WHERE date = CURRENT_DATE 
    LIMIT 1;

    -- P&L Risk Factor (0-30 points)
    IF v_position.unrealized_pnl < -1000 THEN
        v_risk_score := v_risk_score + 30;
    ELSIF v_position.unrealized_pnl < -500 THEN
        v_risk_score := v_risk_score + 20;
    ELSIF v_position.unrealized_pnl < -200 THEN
        v_risk_score := v_risk_score + 10;
    END IF;

    -- Hold Duration Risk (0-20 points)
    IF EXTRACT(EPOCH FROM (NOW() - v_position.opened_at))/3600 > 8 THEN
        v_risk_score := v_risk_score + 20;
    ELSIF EXTRACT(EPOCH FROM (NOW() - v_position.opened_at))/3600 > 4 THEN
        v_risk_score := v_risk_score + 10;
    END IF;

    -- Stop Loss Risk (0-25 points)
    IF v_position.stop_loss IS NULL THEN
        v_risk_score := v_risk_score + 25;
    ELSIF v_position.entry_price > 0 THEN
        IF ABS(v_position.entry_price - v_position.stop_loss) / v_position.entry_price > 0.05 THEN
            v_risk_score := v_risk_score + 15;
        ELSIF ABS(v_position.entry_price - v_position.stop_loss) / v_position.entry_price > 0.03 THEN
            v_risk_score := v_risk_score + 8;
        END IF;
    END IF;

    -- Portfolio Context Risk (0-25 points)
    IF v_daily_metrics.daily_loss_used_pct IS NOT NULL THEN
        IF v_daily_metrics.daily_loss_used_pct > 80 THEN
            v_risk_score := v_risk_score + 25;
        ELSIF v_daily_metrics.daily_loss_used_pct > 60 THEN
            v_risk_score := v_risk_score + 15;
        ELSIF v_daily_metrics.daily_loss_used_pct > 40 THEN
            v_risk_score := v_risk_score + 8;
        END IF;
    END IF;

    RETURN LEAST(v_risk_score, 100.0);
END;
$$ LANGUAGE plpgsql;
```

### 5.2 Update Daily Risk Metrics

```sql
CREATE OR REPLACE FUNCTION update_daily_risk_metrics(
    p_date DATE DEFAULT CURRENT_DATE
) RETURNS VOID AS $$
DECLARE
    v_cycle_id VARCHAR(20);
    v_daily_pnl DECIMAL(12,2);
    v_position_count INTEGER;
    v_total_exposure DECIMAL(12,2);
    v_risk_params RECORD;
BEGIN
    -- Get active cycle
    SELECT cycle_id INTO v_cycle_id 
    FROM trading_cycles 
    WHERE status = 'active' 
    LIMIT 1;

    IF v_cycle_id IS NULL THEN
        RETURN;
    END IF;

    -- Calculate daily metrics
    SELECT 
        COALESCE(SUM(realized_pnl), 0) + COALESCE(SUM(unrealized_pnl), 0),
        COUNT(*) FILTER (WHERE status IN ('open', 'partial')),
        COALESCE(SUM(quantity * entry_price), 0)
    INTO v_daily_pnl, v_position_count, v_total_exposure
    FROM positions 
    WHERE cycle_id = v_cycle_id 
    AND DATE(opened_at) = p_date;

    -- Get risk parameters
    SELECT 
        MAX(parameter_value) FILTER (WHERE parameter_name = 'max_daily_loss') as max_daily_loss,
        MAX(parameter_value) FILTER (WHERE parameter_name = 'max_positions') as max_positions
    INTO v_risk_params
    FROM risk_parameters
    WHERE effective_from <= NOW() 
    AND (effective_to IS NULL OR effective_to > NOW());

    -- Insert or update daily metrics
    INSERT INTO daily_risk_metrics (
        date, cycle_id, daily_pnl, daily_loss_limit, 
        daily_loss_used_pct, remaining_risk_budget,
        position_count, max_position_count, total_exposure
    ) VALUES (
        p_date, v_cycle_id, v_daily_pnl, v_risk_params.max_daily_loss,
        CASE WHEN v_risk_params.max_daily_loss > 0 
             THEN (ABS(LEAST(v_daily_pnl, 0)) / v_risk_params.max_daily_loss) * 100 
             ELSE 0 END,
        v_risk_params.max_daily_loss - ABS(LEAST(v_daily_pnl, 0)),
        v_position_count, v_risk_params.max_positions::INTEGER, v_total_exposure
    )
    ON CONFLICT (date) DO UPDATE SET
        daily_pnl = EXCLUDED.daily_pnl,
        daily_loss_used_pct = EXCLUDED.daily_loss_used_pct,
        remaining_risk_budget = EXCLUDED.remaining_risk_budget,
        position_count = EXCLUDED.position_count,
        total_exposure = EXCLUDED.total_exposure,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;
```

### 5.3 Validate Trade Risk

```sql
CREATE OR REPLACE FUNCTION validate_trade_risk(
    p_symbol VARCHAR(10),
    p_side VARCHAR(10),
    p_intended_value DECIMAL(12,2),
    p_account_balance DECIMAL(12,2) DEFAULT 50000
) RETURNS JSONB AS $$
DECLARE
    v_daily_metrics RECORD;
    v_risk_params RECORD;
    v_position_count INTEGER;
    v_result JSONB;
    v_max_position_value DECIMAL(12,2);
    v_position_pct DECIMAL(5,2);
    v_approved BOOLEAN := TRUE;
    v_reasons TEXT[] := '{}';
BEGIN
    -- Get current daily metrics
    SELECT * INTO v_daily_metrics 
    FROM daily_risk_metrics 
    WHERE date = CURRENT_DATE 
    LIMIT 1;

    -- Get risk parameters
    SELECT 
        MAX(parameter_value) FILTER (WHERE parameter_name = 'max_daily_loss') as max_daily_loss,
        MAX(parameter_value) FILTER (WHERE parameter_name = 'max_position_size') as max_position_size,
        MAX(parameter_value) FILTER (WHERE parameter_name = 'max_positions') as max_positions
    INTO v_risk_params
    FROM risk_parameters
    WHERE effective_from <= NOW() 
    AND (effective_to IS NULL OR effective_to > NOW());

    -- Get current position count
    SELECT COUNT(*) INTO v_position_count
    FROM positions 
    WHERE status IN ('open', 'partial');

    -- Check position count limit
    IF v_position_count >= v_risk_params.max_positions THEN
        v_approved := FALSE;
        v_reasons := array_append(v_reasons, 'Maximum positions limit exceeded');
    END IF;

    -- Check position size limit
    v_max_position_value := p_account_balance * v_risk_params.max_position_size;
    v_position_pct := p_intended_value / p_account_balance;

    IF p_intended_value > v_max_position_value THEN
        v_approved := FALSE;
        v_reasons := array_append(v_reasons, 
            format('Position size %.1f%% exceeds limit %.1f%%', 
                   v_position_pct * 100, v_risk_params.max_position_size * 100));
    END IF;

    -- Check daily loss limit
    IF v_daily_metrics.daily_loss_used_pct IS NOT NULL AND v_daily_metrics.daily_loss_used_pct >= 95 THEN
        v_approved := FALSE;
        v_reasons := array_append(v_reasons, 'Daily loss limit nearly exceeded');
    END IF;

    -- Build result
    v_result := jsonb_build_object(
        'approved', v_approved,
        'reasons', v_reasons,
        'approved_position_size', 
            CASE WHEN v_approved THEN p_intended_value 
                 ELSE LEAST(p_intended_value, v_max_position_value) END,
        'position_size_pct', v_position_pct,
        'risk_assessment', jsonb_build_object(
            'daily_loss_used_pct', COALESCE(v_daily_metrics.daily_loss_used_pct, 0),
            'position_utilization', (v_position_count::DECIMAL / v_risk_params.max_positions) * 100,
            'remaining_positions', v_risk_params.max_positions - v_position_count
        )
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Triggers and Constraints

### 6.1 Risk Monitoring Triggers

```sql
-- Trigger to update position risk scores
CREATE OR REPLACE FUNCTION update_position_risk_trigger()
RETURNS TRIGGER AS $$
BEGIN
    NEW.position_risk_score := calculate_position_risk_score(NEW.position_id);
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER position_risk_update_trigger
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_position_risk_trigger();

-- Trigger to update daily risk metrics when positions change
CREATE OR REPLACE FUNCTION position_change_risk_trigger()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM update_daily_risk_metrics(CURRENT_DATE);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER position_change_trigger
    AFTER INSERT OR UPDATE OR DELETE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION position_change_risk_trigger();

-- Trigger to create risk events for critical situations
CREATE OR REPLACE FUNCTION risk_event_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Daily loss warning at 80%
    IF NEW.daily_loss_used_pct >= 80 AND (OLD.daily_loss_used_pct IS NULL OR OLD.daily_loss_used_pct < 80) THEN
        INSERT INTO risk_events (event_type, severity, title, description, cycle_id, trigger_value, limit_value)
        VALUES ('daily_loss_warning', 'high', 'Daily Loss Warning', 
                format('Daily loss reached %.1f%% of limit', NEW.daily_loss_used_pct),
                NEW.cycle_id, NEW.daily_loss_used_pct, 80);
    END IF;

    -- Daily loss breach at 100%
    IF NEW.daily_loss_used_pct >= 100 AND (OLD.daily_loss_used_pct IS NULL OR OLD.daily_loss_used_pct < 100) THEN
        INSERT INTO risk_events (event_type, severity, title, description, cycle_id, trigger_value, limit_value)
        VALUES ('daily_loss_breach', 'critical', 'Daily Loss Limit Exceeded', 
                format('Daily loss limit exceeded: %.1f%%', NEW.daily_loss_used_pct),
                NEW.cycle_id, NEW.daily_loss_used_pct, 100);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER daily_risk_event_trigger
    AFTER UPDATE ON daily_risk_metrics
    FOR EACH ROW
    EXECUTE FUNCTION risk_event_trigger();
```

---

## 7. Indexes for Performance

```sql
-- Risk Management Indexes
CREATE INDEX idx_risk_parameters_active ON risk_parameters(parameter_name, effective_from, effective_to) 
    WHERE effective_to IS NULL;

CREATE INDEX idx_daily_risk_metrics_date ON daily_risk_metrics(date DESC);

CREATE INDEX idx_risk_events_type_severity ON risk_events(event_type, severity, created_at DESC);

CREATE INDEX idx_risk_events_unresolved ON risk_events(created_at DESC) 
    WHERE resolved_at IS NULL;

-- Enhanced Position Indexes
CREATE INDEX idx_positions_risk_score ON positions(position_risk_score DESC) 
    WHERE status IN ('open', 'partial');

CREATE INDEX idx_positions_cycle_status ON positions(cycle_id, status, opened_at DESC);

CREATE INDEX idx_positions_symbol_status ON positions(symbol, status, updated_at DESC);

-- Portfolio Exposure Indexes
CREATE INDEX idx_portfolio_exposure_date_symbol ON portfolio_exposure(date DESC, symbol);

CREATE INDEX idx_portfolio_exposure_sector ON portfolio_exposure(date DESC, sector);

-- Performance Indexes
CREATE INDEX idx_performance_reports_type_date ON performance_reports(report_type, report_date DESC);
```

---

