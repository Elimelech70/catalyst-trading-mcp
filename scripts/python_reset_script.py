#!/usr/bin/env python3
"""
Database Reset Script - DigitalOcean Compatible
Uses asyncpg to directly execute SQL
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
import re

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

def smart_sql_split(sql_text):
    """
    Split SQL by semicolons, but respect:
    - Dollar-quoted strings ($$...$$)
    - Single quotes ('...')
    - Comments (-- and /* */)
    """
    statements = []
    current = []
    in_dollar_quote = False
    in_single_quote = False
    in_block_comment = False
    dollar_tag = None
    
    i = 0
    while i < len(sql_text):
        char = sql_text[i]
        
        # Check for block comment start
        if not in_dollar_quote and not in_single_quote and sql_text[i:i+2] == '/*':
            in_block_comment = True
            current.append(sql_text[i:i+2])
            i += 2
            continue
        
        # Check for block comment end
        if in_block_comment and sql_text[i:i+2] == '*/':
            in_block_comment = False
            current.append(sql_text[i:i+2])
            i += 2
            continue
        
        # Skip if in block comment
        if in_block_comment:
            current.append(char)
            i += 1
            continue
        
        # Check for dollar quote
        if not in_single_quote and char == '$':
            # Look for matching $tag$
            match = re.match(r'\$(\w*)\$', sql_text[i:])
            if match:
                tag = match.group(0)
                if not in_dollar_quote:
                    # Starting dollar quote
                    in_dollar_quote = True
                    dollar_tag = tag
                    current.append(tag)
                    i += len(tag)
                    continue
                elif tag == dollar_tag:
                    # Ending dollar quote
                    in_dollar_quote = False
                    current.append(tag)
                    dollar_tag = None
                    i += len(tag)
                    continue
        
        # Check for single quote (if not in dollar quote)
        if not in_dollar_quote and char == "'":
            # Check if escaped
            if i > 0 and sql_text[i-1] == '\\':
                current.append(char)
                i += 1
                continue
            in_single_quote = not in_single_quote
            current.append(char)
            i += 1
            continue
        
        # Check for semicolon (statement terminator)
        if char == ';' and not in_dollar_quote and not in_single_quote:
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        
        # Regular character
        current.append(char)
        i += 1
    
    # Add last statement if exists
    stmt = ''.join(current).strip()
    if stmt:
        statements.append(stmt)
    
    return statements

async def reset_database():
    # DigitalOcean connection string
    database_url = os.getenv('DATABASE_URL', 
        'postgresql://doadmin:AVNS_COlEfvzem_NMElg7hd_@catalyst-trading-db-do-user-23488393-0.l.db.ondigitalocean.com:25060/defaultdb?sslmode=require'
    )
    
    # Check schema file exists
    schema_file = Path('normalized-database-schema-mcp-v50.sql')
    if not schema_file.exists():
        print(f"{RED}ERROR: Schema file not found: {schema_file}{NC}")
        print("Please ensure normalized-database-schema-mcp-v50.sql is in the current directory")
        sys.exit(1)
    
    print("=" * 70)
    print("🎩 Catalyst Trading System - Database Reset v5.0")
    print("=" * 70)
    print()
    print(f"{RED}⚠️  WARNING: This will DELETE ALL DATA!{NC}")
    print()
    print(f"Database: DigitalOcean (defaultdb)")
    print(f"Schema File: {schema_file}")
    print()
    
    confirm = input("Type 'yes' to confirm: ")
    if confirm != 'yes':
        print(f"{YELLOW}Aborted{NC}")
        sys.exit(0)
    
    print()
    print(f"{YELLOW}Starting database reset...{NC}")
    print()
    
    try:
        # Connect to database
        print("Connecting to DigitalOcean database...")
        conn = await asyncpg.connect(database_url)
        
        # Step 0: Nuclear option - drop entire public schema and recreate
        print("Step 0: Nuclear reset - dropping entire public schema...")
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.execute("CREATE SCHEMA public")
        await conn.execute("GRANT ALL ON SCHEMA public TO doadmin")
        await conn.execute("GRANT ALL ON SCHEMA public TO public")
        
        print(f"{GREEN}✅ Public schema recreated (completely clean){NC}")
        print()
        
        # Step 1: Create new schema
        print("Step 1: Creating normalized schema v5.0...")
        
        # Read schema file
        schema_sql = schema_file.read_text()
        
        # Remove line comments (but keep block comments for now)
        lines = []
        for line in schema_sql.split('\n'):
            # Remove inline -- comments but keep the rest of the line
            if '--' in line:
                # Find -- not inside quotes
                idx = line.find('--')
                if idx >= 0:
                    line = line[:idx]
            lines.append(line)
        
        clean_sql = '\n'.join(lines)
        
        # Smart split respecting dollar quotes
        print("Parsing SQL (respecting dollar-quoted functions)...")
        statements = smart_sql_split(clean_sql)
        
        # Filter out empty statements and comments
        statements = [s for s in statements if s and not s.strip().startswith('/*')]
        
        print(f"Executing {len(statements)} SQL statements...")
        
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    await conn.execute(statement)
                    if i % 5 == 0:
                        print(f"  Progress: {i}/{len(statements)} statements...")
                except Exception as e:
                    # Check if it's a "already exists" error - skip those
                    if "already exists" in str(e):
                        print(f"{YELLOW}  Skipping: {str(e)[:80]}...{NC}")
                        continue
                    else:
                        print(f"{RED}Failed on statement {i}:{NC}")
                        print(f"Statement preview: {statement[:300]}...")
                        print(f"Error: {e}")
                        raise
        
        print(f"{GREEN}✅ Schema created successfully ({len(statements)} statements){NC}")
        print()
        
        # Step 2: Verify
        print("Step 2: Verifying schema...")
        print()
        
        # Check dimension tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('securities', 'sectors', 'time_dimension')
            ORDER BY table_name
        """)
        print("📊 Dimension Tables:")
        for row in tables:
            print(f"  ✓ {row['table_name']}")
        print()
        
        # Check helper functions
        functions = await conn.fetch("""
            SELECT proname 
            FROM pg_proc 
            WHERE proname IN ('get_or_create_security', 'get_or_create_time')
        """)
        print("🔧 Helper Functions:")
        for row in functions:
            print(f"  ✓ {row['proname']}")
        print()
        
        # Check materialized views
        views = await conn.fetch("""
            SELECT matviewname 
            FROM pg_matviews 
            WHERE schemaname = 'public'
        """)
        print("📈 Materialized Views:")
        for row in views:
            print(f"  ✓ {row['matviewname']}")
        print()
        
        # Check sectors
        sectors = await conn.fetch("SELECT sector_name, sector_code FROM sectors ORDER BY sector_id")
        print(f"🏢 Seeded Sectors ({len(sectors)}):")
        for row in sectors:
            print(f"  ✓ {row['sector_name']} ({row['sector_code']})")
        print()
        
        # Check economic indicators
        indicators = await conn.fetch("""
            SELECT indicator_code, indicator_name 
            FROM economic_indicators 
            ORDER BY indicator_code
        """)
        print(f"📉 Seeded Economic Indicators ({len(indicators)}):")
        for row in indicators:
            print(f"  ✓ {row['indicator_code']}: {row['indicator_name']}")
        print()
        
        # Test helper function
        print("🧪 Testing helper functions...")
        security_id = await conn.fetchval("SELECT get_or_create_security('AAPL')")
        print(f"  ✓ get_or_create_security('AAPL') = {security_id}")
        
        time_id = await conn.fetchval("SELECT get_or_create_time(NOW())")
        print(f"  ✓ get_or_create_time(NOW()) = {time_id}")
        print()
        
        # Verify FK constraints
        print("🔍 Verifying FK constraints...")
        constraint_count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        """)
        print(f"  ✓ Found {constraint_count} FK constraints")
        print()
        
        await conn.close()
        
        print("=" * 70)
        print(f"{GREEN}✅ Database reset complete!{NC}")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. ✅ News Service v5.1.0 (already updated with normalized schema)")
        print("2. 🔄 Update scanner-service.py to use security_id FK")
        print("3. 🔄 Update trading-service.py to use security_id FK")
        print("4. 🔄 Update technical-service.py to persist indicators")
        print()
        print("Run services:")
        print("  python services/news/news-service.py")
        print()
        
    except Exception as e:
        print(f"{RED}ERROR: {e}{NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(reset_database())
