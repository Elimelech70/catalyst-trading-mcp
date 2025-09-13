-- Name of Application: Catalyst Trading System
-- Name of file: fix-database-schema.sql
-- Version: 1.0.0
-- Last Updated: 2025-09-13
-- Purpose: Fix missing columns in database schema

-- REVISION HISTORY:
-- v1.0.0 (2025-09-13) - Add missing columns for pattern and trading services

-- Description of Service:
-- SQL migration to add missing columns identified in service logs

-- ============================================================
-- Fix for Pattern Service
-- ============================================================

-- Check if pattern_trades table exists and add missing column
ALTER TABLE pattern_trades 
ADD COLUMN IF NOT EXISTS pattern_type VARCHAR(50);

-- Update existing records with a default value
UPDATE pattern_trades 
SET pattern_type = pattern_name 
WHERE pattern_type IS NULL;

-- ============================================================
-- Fix for Trading Service
-- ============================================================

-- Check if positions table exists and add missing metadata column
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Add metadata to trades table as well
ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- ============================================================
-- Additional helpful indexes
-- ============================================================

-- Index for pattern type queries
CREATE INDEX IF NOT EXISTS idx_pattern_trades_pattern_type 
ON pattern_trades(pattern_type);

-- Index for metadata queries
CREATE INDEX IF NOT EXISTS idx_positions_metadata 
ON positions USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_trades_metadata 
ON trades USING GIN (metadata);

-- ============================================================
-- Verify the changes
-- ============================================================

-- Check pattern_trades columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'pattern_trades' 
AND column_name IN ('pattern_type', 'pattern_name');

-- Check positions columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'positions' 
AND column_name = 'metadata';

-- Check trades columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name = 'metadata';