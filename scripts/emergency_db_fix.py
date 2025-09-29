#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: emergency_database_fix.py
Version: 1.0.0
Last Updated: 2025-09-29
Purpose: Emergency script to diagnose and fix critical database connection issues

REVISION HISTORY:
v1.0.0 (2025-09-29) - Emergency database fix
- Kill idle connections immediately
- Fix pattern_type schema issue
- Verify all critical tables
- Provide immediate connection status

Description of Service:
Emergency diagnostic and repair script for database connection pool exhaustion.
Run this FIRST when services fail to start with connection errors.
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from typing import Dict, Any

async def kill_idle_connections() -> Dict[str, Any]:
    """Kill all idle connections to free up slots"""
    try:
        url = os.getenv("DATABASE_URL")
        if not url:
            return {"error": "DATABASE_URL not set"}
        
        conn = await asyncpg.connect(url)
        
        # Get count before
        before_count = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database()
        """)
        
        # Kill idle connections (excluding our own)
        killed = await conn.fetch("""
            SELECT pg_terminate_backend(pid), application_name, state
            FROM pg_stat_activity 
            WHERE datname = current_database()
            AND state = 'idle'
            AND pid != pg_backend_pid()
            AND application_name != ''
        """)
        
        # Get count after
        after_count = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database()
        """)
        
        await conn.close()
        
        return {
            "success": True,
            "before_count": before_count,
            "after_count": after_count,
            "killed_count": len(killed),
            "connections_freed": before_count - after_count
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}

async def fix_pattern_schema() -> Dict[str, Any]:
    """Fix missing pattern_type column"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        # Check if table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'pattern_analysis'
            )
        """)
        
        if not table_exists:
            # Create table with correct schema
            await conn.execute("""
                CREATE TABLE pattern_analysis (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(10) NOT NULL,
                    pattern_type VARCHAR(50) NOT NULL,
                    confidence DECIMAL(4,3) NOT NULL,
                    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.close()
            return {"success": True, "action": "created_table"}
        
        # Check if column exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'pattern_analysis' 
                AND column_name = 'pattern_type'
            )
        """)
        
        if not column_exists:
            await conn.execute("""
                ALTER TABLE pattern_analysis 
                ADD COLUMN pattern_type VARCHAR(50) NOT NULL DEFAULT 'unknown'
            """)
            await conn.close()
            return {"success": True, "action": "added_column"}
        
        await conn.close()
        return {"success": True, "action": "already_exists"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_connection_status() -> Dict[str, Any]:
    """Get detailed connection status"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        # Total connections
        total = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database()
        """)
        
        # Max connections
        max_conn = await conn.fetchval("SHOW max_connections")
        
        # By application
        by_app = await conn.fetch("""
            SELECT 
                application_name,
                state,
                COUNT(*) as count
            FROM pg_stat_activity 
            WHERE datname = current_database()
            GROUP BY application_name, state
            ORDER BY count DESC
        """)
        
        # Idle connections
        idle = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database() 
            AND state = 'idle'
        """)
        
        await conn.close()
        
        usage_percent = round((total / int(max_conn)) * 100, 1)
        
        return {
            "total_connections": total,
            "max_connections": int(max_conn),
            "idle_connections": idle,
            "active_connections": total - idle,
            "usage_percent": usage_percent,
            "status": "CRITICAL" if usage_percent > 80 else "WARNING" if usage_percent > 60 else "HEALTHY",
            "by_application": [dict(row) for row in by_app]
        }
        
    except Exception as e:
        return {"error": str(e)}

async def verify_critical_tables() -> Dict[str, Any]:
    """Verify all critical tables exist"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        required_tables = [
            'trading_cycles',
            'scan_results', 
            'positions',
            'orders',
            'pattern_analysis',
            'news_articles',
            'risk_parameters'
        ]
        
        existing_tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        
        existing_names = [row['table_name'] for row in existing_tables]
        missing = [t for t in required_tables if t not in existing_names]
        
        await conn.close()
        
        return {
            "total_tables": len(existing_names),
            "required_tables": len(required_tables),
            "missing_tables": missing,
            "all_tables": existing_names
        }
        
    except Exception as e:
        return {"error": str(e)}

async def main():
    """Run emergency database fix"""
    print("=" * 80)
    print("🚨 CATALYST TRADING SYSTEM - EMERGENCY DATABASE FIX")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Get current status
    print("📊 STEP 1: Checking current database connection status...")
    print("-" * 80)
    status = await get_connection_status()
    
    if "error" in status:
        print(f"❌ ERROR: {status['error']}")
        print("\n🔍 Troubleshooting:")
        print("   1. Verify DATABASE_URL is set: echo $DATABASE_URL")
        print("   2. Check DigitalOcean database is running")
        print("   3. Verify network connectivity")
        sys.exit(1)
    
    print(f"Total Connections: {status['total_connections']}/{status['max_connections']}")
    print(f"Usage: {status['usage_percent']}% - Status: {status['status']}")
    print(f"Idle: {status['idle_connections']}, Active: {status['active_connections']}\n")
    
    print("By Application:")
    for app in status['by_application']:
        print(f"   {app['application_name'] or 'unnamed'}: {app['count']} ({app['state']})")
    
    # Step 2: Kill idle connections if needed
    if status['usage_percent'] > 60 or status['idle_connections'] > 10:
        print("\n⚠️  STEP 2: High connection usage detected - killing idle connections...")
        print("-" * 80)
        kill_result = await kill_idle_connections()
        
        if kill_result.get('success'):
            print(f"✅ Successfully freed {kill_result['connections_freed']} connections")
            print(f"   Before: {kill_result['before_count']} → After: {kill_result['after_count']}")
        else:
            print(f"❌ Failed to kill connections: {kill_result.get('error')}")
    else:
        print("\n✅ STEP 2: Connection usage is acceptable - skipping cleanup")
    
    # Step 3: Fix pattern schema
    print("\n🔧 STEP 3: Fixing pattern service schema...")
    print("-" * 80)
    pattern_fix = await fix_pattern_schema()
    
    if pattern_fix.get('success'):
        action = pattern_fix['action']
        if action == 'created_table':
            print("✅ Created pattern_analysis table with correct schema")
        elif action == 'added_column':
            print("✅ Added missing pattern_type column")
        else:
            print("✅ Pattern schema already correct")
    else:
        print(f"❌ Schema fix failed: {pattern_fix.get('error')}")
    
    # Step 4: Verify tables
    print("\n📋 STEP 4: Verifying critical tables...")
    print("-" * 80)
    tables = await verify_critical_tables()
    
    if "error" in tables:
        print(f"❌ ERROR: {tables['error']}")
    else:
        print(f"Found {tables['total_tables']} tables")
        if tables['missing_tables']:
            print(f"⚠️  Missing tables: {', '.join(tables['missing_tables'])}")
            print("   Run: python scripts/create-fresh-schema.py")
        else:
            print("✅ All critical tables present")
    
    # Step 5: Final status check
    print("\n📊 STEP 5: Final connection status...")
    print("-" * 80)
    final_status = await get_connection_status()
    
    if "error" not in final_status:
        print(f"Total Connections: {final_status['total_connections']}/{final_status['max_connections']}")
        print(f"Usage: {final_status['usage_percent']}% - Status: {final_status['status']}")
        
        if final_status['usage_percent'] < 50:
            print("✅ Connection pool is healthy!")
        elif final_status['usage_percent'] < 70:
            print("⚠️  Connection usage is moderate - monitor closely")
        else:
            print("🚨 Connection usage still high - services may need restart")
    
    print("\n" + "=" * 80)
    print("🚀 NEXT STEPS:")
    print("=" * 80)
    print("1. Restart services: docker-compose restart")
    print("2. Monitor logs: docker-compose logs -f --tail=100")
    print("3. If issues persist, implement optimized connection pooling")
    print("4. Target connection allocation: 12-43 connections total")
    print("\n✅ Emergency fix complete!")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
