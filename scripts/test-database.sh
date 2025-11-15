#!/bin/bash
echo "Testing database integrity..."

# Source .env for DATABASE_URL
source /root/catalyst-trading-mcp/.env

# Test 1: Connection
if psql "$DATABASE_URL" -c "SELECT 1" >/dev/null 2>&1; then
    echo "[OK] Database connection"
else
    echo "[ERROR] Database connection FAILED"
    exit 1
fi

# Test 2: Schema exists
tables=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")

if [ "$tables" -gt 10 ]; then
    echo "[OK] Database schema ($tables tables)"
else
    echo "[ERROR] Database schema INCOMPLETE"
    exit 1
fi

# Test 3: Foreign key constraints
fks=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_type='FOREIGN KEY'")

if [ "$fks" -gt 5 ]; then
    echo "[OK] Foreign key constraints ($fks FKs)"
else
    echo "[ERROR] Foreign key constraints MISSING"
    exit 1
fi

echo "[OK] Database integrity verified"
exit 0
