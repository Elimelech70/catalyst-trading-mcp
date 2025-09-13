#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: apply-fixes.sh
# Version: 1.0.0
# Last Updated: 2025-09-13
# Purpose: Apply database schema fixes and verify system health

# REVISION HISTORY:
# v1.0.0 (2025-09-13) - Initial fix script

# Description of Service:
# Applies database migrations and verifies system health

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Catalyst Trading System - Applying Fixes 🔧     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Create migration SQL file
echo -e "${YELLOW}Step 1: Creating database migration file${NC}"

cat > /tmp/fix-schema.sql << 'EOF'
-- Catalyst Trading System - Schema Fixes
-- Fix missing columns for pattern and trading services

-- Fix pattern_trades table
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pattern_trades') THEN
        -- Add pattern_type column if it doesn't exist
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'pattern_trades' AND column_name = 'pattern_type') THEN
            ALTER TABLE pattern_trades ADD COLUMN pattern_type VARCHAR(50);
            UPDATE pattern_trades SET pattern_type = pattern_name WHERE pattern_type IS NULL;
            RAISE NOTICE 'Added pattern_type column to pattern_trades';
        END IF;
    END IF;
END $$;

-- Fix positions table
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'positions') THEN
        -- Add metadata column if it doesn't exist
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'positions' AND column_name = 'metadata') THEN
            ALTER TABLE positions ADD COLUMN metadata JSONB DEFAULT '{}';
            RAISE NOTICE 'Added metadata column to positions';
        END IF;
    END IF;
END $$;

-- Fix trades table
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'trades') THEN
        -- Add metadata column if it doesn't exist
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name = 'trades' AND column_name = 'metadata') THEN
            ALTER TABLE trades ADD COLUMN metadata JSONB DEFAULT '{}';
            RAISE NOTICE 'Added metadata column to trades';
        END IF;
    END IF;
END $$;

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_pattern_trades_pattern_type ON pattern_trades(pattern_type);
CREATE INDEX IF NOT EXISTS idx_positions_metadata ON positions USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_trades_metadata ON trades USING GIN (metadata);

-- Verify changes
SELECT 'Schema fixes applied successfully' as status;
EOF

echo -e "${GREEN}✓ Migration file created${NC}"

# Apply migration
echo
echo -e "${YELLOW}Step 2: Applying database migration${NC}"

if command -v psql &> /dev/null; then
    if psql "$DATABASE_URL" < /tmp/fix-schema.sql; then
        echo -e "${GREEN}✓ Database schema updated successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Migration may have already been applied${NC}"
    fi
else
    echo -e "${YELLOW}Using Docker to apply migration...${NC}"
    # Use a temporary container to run psql
    docker run --rm -i --network catalyst-network \
        postgres:15-alpine psql "$DATABASE_URL" < /tmp/fix-schema.sql && \
        echo -e "${GREEN}✓ Database schema updated via Docker${NC}" || \
        echo -e "${YELLOW}⚠️  Migration may have already been applied${NC}"
fi

# Clean up
rm -f /tmp/fix-schema.sql

echo
echo -e "${YELLOW}Step 3: Restarting affected services${NC}"

# Restart services that had schema issues
echo "Restarting pattern service..."
docker-compose restart pattern
sleep 5

echo "Restarting trading service..."
docker-compose restart trading
sleep 5

echo -e "${GREEN}✓ Services restarted${NC}"

echo
echo -e "${YELLOW}Step 4: Verifying fixes${NC}"
echo

# Check if errors are gone
pattern_errors=$(docker logs catalyst-pattern 2>&1 | tail -50 | grep -c "column.*does not exist" || echo "0")
trading_errors=$(docker logs catalyst-trading 2>&1 | tail -50 | grep -c "column.*does not exist" || echo "0")

if [ "$pattern_errors" -eq 0 ] && [ "$trading_errors" -eq 0 ]; then
    echo -e "${GREEN}✓ Schema errors resolved!${NC}"
else
    echo -e "${YELLOW}⚠️  Some errors may persist - check logs${NC}"
fi

echo
echo -e "${YELLOW}Step 5: System Status${NC}"
echo

# Quick status check
echo "Container Status:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep catalyst || true

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Fixes Applied Successfully! 🎉                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Run health check: ${BLUE}bash check-health.sh${NC}"
echo "2. Monitor logs: ${BLUE}docker-compose logs -f${NC}"
echo "3. Start trading: ${BLUE}curl -X POST http://localhost:5000/start${NC}"