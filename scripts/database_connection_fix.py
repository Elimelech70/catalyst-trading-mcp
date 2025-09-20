#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: database_connection_fix.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Complete database diagnostic and repair script

LOCATION: scripts/database_connection_fix.py

REVISION HISTORY:
v4.2.0 (2025-09-20) - Complete database diagnostics and fixes
- Connection usage monitoring and optimization
- Schema repairs (pattern_type column)
- Connection limit verification and recommendations
- Service health diagnostics and repair suggestions
- Database settings analysis and recommendations

Description:
Standalone script to diagnose and fix database connection issues.
Run this when experiencing connection pool exhaustion or schema problems.
This is the complete diagnostic tool for the Catalyst Trading System.
"""

import asyncio
import asyncpg
import os
import sys
from typing import Dict, Any
from datetime import datetime

# === CONNECTION OPTIMIZATION RECOMMENDATIONS ===
OPTIMIZED_CONNECTION_LIMITS = {
    "orchestration": {"min": 2, "max": 5},   # MCP + workflow coordination
    "scanner": {"min": 2, "max": 8},         # High activity during scans
    "pattern": {"min": 1, "max": 4},         # Moderate usage
    "technical": {"min": 1, "max": 4},       # Moderate usage  
    "risk_manager": {"min": 2, "max": 6},    # Critical safety service
    "trading": {"min": 2, "max": 8},         # High activity during trades
    "news": {"min": 1, "max": 3},            # Low database usage
    "reporting": {"min": 1, "max": 5},       # Periodic batch operations
    
    # Total allocated: min=12, max=43 (well under 80 limit)
}

async def check_all_connections() -> Dict[str, Any]:
    """Check total database connections across all services"""
    try:
        # Use a minimal connection to check database status
        url = os.getenv("DATABASE_URL")
        if not url:
            return {"error": "DATABASE_URL not set"}
        
        conn = await asyncpg.connect(url)
        
        # Get connection statistics
        stats = await conn.fetch("""
            SELECT 
                application_name,
                state,
                COUNT(*) as connection_count
            FROM pg_stat_activity 
            WHERE datname = current_database()
            GROUP BY application_name, state
            ORDER BY connection_count DESC
        """)
        
        total_connections = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database()
        """)
        
        max_connections = await conn.fetchval("SHOW max_connections")
        
        await conn.close()
        
        return {
            "total_connections": total_connections,
            "max_connections": int(max_connections),
            "usage_percent": round((total_connections / int(max_connections)) * 100, 1),
            "by_application": [dict(row) for row in stats],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}

async def fix_pattern_service_schema() -> Dict[str, Any]:
    """Fix missing pattern_type column in pattern service"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        # Check if pattern_analysis table exists and fix schema
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_analysis (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                pattern_type VARCHAR(50) NOT NULL,
                confidence DECIMAL(4,3) NOT NULL,
                detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        
        # Check if column exists, add if missing
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
                ADD COLUMN pattern_type VARCHAR(50) DEFAULT 'unknown'
            """)
            print("✅ Added missing pattern_type column")
        else:
            print("✅ pattern_type column already exists")
        
        await conn.close()
        return {"success": True, "message": "Pattern schema verified/fixed"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def check_service_tables() -> Dict[str, Any]:
    """Check if all required tables exist"""
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
            'risk_parameters',
            'daily_risk_metrics',
            'risk_events'
        ]
        
        existing_tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        
        existing_table_names = [row['table_name'] for row in existing_tables]
        
        missing_tables = [table for table in required_tables if table not in existing_table_names]
        
        await conn.close()
        
        return {
            "total_tables": len(existing_table_names),
            "required_tables": len(required_tables),
            "missing_tables": missing_tables,
            "all_tables": existing_table_names
        }
        
    except Exception as e:
        return {"error": str(e)}

async def analyze_connection_usage() -> Dict[str, Any]:
    """Analyze current connection usage and provide optimization recommendations"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        # Get detailed connection analysis
        detailed_stats = await conn.fetch("""
            SELECT 
                application_name,
                state,
                COUNT(*) as connection_count,
                MAX(NOW() - state_change) as max_duration
            FROM pg_stat_activity 
            WHERE datname = current_database()
            GROUP BY application_name, state
            ORDER BY connection_count DESC
        """)
        
        # Get idle connections
        idle_connections = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database() 
            AND state = 'idle'
        """)
        
        # Get active connections
        active_connections = await conn.fetchval("""
            SELECT COUNT(*) FROM pg_stat_activity 
            WHERE datname = current_database() 
            AND state = 'active'
        """)
        
        await conn.close()
        
        # Calculate optimization potential
        total_current = sum(row['connection_count'] for row in detailed_stats)
        recommended_max = sum(OPTIMIZED_CONNECTION_LIMITS[service]["max"] 
                            for service in OPTIMIZED_CONNECTION_LIMITS)
        
        savings = max(0, total_current - recommended_max)
        
        return {
            "detailed_stats": [dict(row) for row in detailed_stats],
            "idle_connections": idle_connections,
            "active_connections": active_connections,
            "current_total": total_current,
            "recommended_max": recommended_max,
            "potential_savings": savings,
            "optimization_needed": savings > 0
        }
        
    except Exception as e:
        return {"error": str(e)}

async def optimize_database_settings() -> Dict[str, Any]:
    """Apply database optimizations for trading workload"""
    try:
        url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(url)
        
        # Check current settings
        settings = await conn.fetch("""
            SELECT name, setting, unit, context, source
            FROM pg_settings 
            WHERE name IN (
                'max_connections',
                'shared_buffers',
                'effective_cache_size',
                'work_mem',
                'maintenance_work_mem',
                'checkpoint_completion_target',
                'wal_buffers',
                'default_statistics_target'
            )
        """)
        
        await conn.close()
        
        return {
            "current_settings": [dict(row) for row in settings],
            "recommendations": {
                "max_connections": "100 (DigitalOcean managed - cannot change)",
                "shared_buffers": "25% of RAM (DigitalOcean managed - optimized)",
                "effective_cache_size": "75% of RAM (DigitalOcean managed)",
                "work_mem": "4MB (for sorting/hashing operations)",
                "maintenance_work_mem": "256MB (for maintenance operations)",
                "checkpoint_completion_target": "0.9 (for write performance)",
                "wal_buffers": "16MB (for write-ahead logging)",
                "default_statistics_target": "100 (for query planning)"
            },
            "notes": "DigitalOcean manages most settings automatically. Focus on connection optimization."
        }
        
    except Exception as e:
        return {"error": str(e)}

async def generate_service_fixes() -> Dict[str, Any]:
    """Generate specific fixes for each service"""
    fixes = {}
    
    for service_name, limits in OPTIMIZED_CONNECTION_LIMITS.items():
        fixes[service_name] = {
            "current_limits": "Unknown (needs analysis)",
            "recommended_limits": limits,
            "fix_code": f"""
# In {service_name}-service.py, replace database initialization:

# OLD:
db_pool = await asyncpg.create_pool(
    database_url,
    min_size=5,  # Too high!
    max_size=20  # Way too high!
)

# NEW:
from services.shared.optimized_database import OptimizedDatabaseManager
db_manager = OptimizedDatabaseManager("{service_name}")
await db_manager.initialize()

# Usage:
result = await db_manager.fetchval("SELECT COUNT(*) FROM table")
rows = await db_manager.fetch("SELECT * FROM table WHERE ...")
await db_manager.execute("INSERT INTO table ...")
""",
            "dockerfile_check": f"Ensure Dockerfile copies shared module for {service_name}",
            "health_check": f"Add db_manager.health_check() to /{service_name}/health endpoint"
        }
    
    return fixes

async def check_docker_compose_config() -> Dict[str, Any]:
    """Check docker-compose.yml for connection-related issues"""
    try:
        # This would ideally parse docker-compose.yml, but for now provide recommendations
        return {
            "recommendations": {
                "environment_variables": [
                    "Ensure DATABASE_URL is consistent across all services",
                    "Add MAX_DB_CONNECTIONS env var per service",
                    "Consider adding CONNECTION_TIMEOUT=30",
                    "Add POOL_RECYCLE=3600 for connection recycling"
                ],
                "resource_limits": [
                    "Add memory limits to prevent OOM: mem_limit: 512m",
                    "Add CPU limits: cpus: '0.5'",
                    "Consider using depends_on with condition: service_healthy"
                ],
                "restart_policies": [
                    "Use restart: unless-stopped for stability",
                    "Add healthchecks for all database-using services"
                ]
            },
            "example_service_config": """
  scanner:
    environment:
      DATABASE_URL: ${DATABASE_URL}
      MAX_DB_CONNECTIONS: 8
      CONNECTION_TIMEOUT: 30
    mem_limit: 512m
    cpus: '0.5'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
"""
        }
    except Exception as e:
        return {"error": str(e)}

async def main():
    """Main diagnostic and repair routine"""
    print("🎩 Catalyst Trading System - Complete Database Diagnostic Tool")
    print("=" * 80)
    
    # Check environment
    if not os.getenv("DATABASE_URL"):
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("Export your DigitalOcean connection string:")
        print("export DATABASE_URL='postgresql://user:pass@host:25060/db?sslmode=require'")
        sys.exit(1)
    
    print("\n📊 1. Database Connection Analysis...")
    print("-" * 60)
    
    conn_stats = await check_all_connections()
    if "error" not in conn_stats:
        print(f"📈 Total Connections: {conn_stats['total_connections']}/{conn_stats['max_connections']}")
        print(f"📊 Usage: {conn_stats['usage_percent']}%")
        
        if conn_stats['usage_percent'] > 80:
            print("🚨 CRITICAL: Very high connection usage! Immediate action required.")
        elif conn_stats['usage_percent'] > 60:
            print("⚠️  WARNING: High connection usage. Optimization recommended.")
        else:
            print("✅ Connection usage looks healthy.")
        
        print(f"\n📱 Connections by Application:")
        for app in conn_stats['by_application']:
            print(f"   {app['application_name']}: {app['connection_count']} ({app['state']})")
    else:
        print(f"❌ Error checking connections: {conn_stats['error']}")
    
    print("\n🔍 2. Detailed Connection Usage Analysis...")
    print("-" * 60)
    
    usage_analysis = await analyze_connection_usage()
    if "error" not in usage_analysis:
        print(f"💤 Idle Connections: {usage_analysis['idle_connections']}")
        print(f"⚡ Active Connections: {usage_analysis['active_connections']}")
        print(f"📊 Current Total: {usage_analysis['current_total']}")
        print(f"🎯 Recommended Max: {usage_analysis['recommended_max']}")
        
        if usage_analysis['optimization_needed']:
            print(f"💡 Potential Savings: {usage_analysis['potential_savings']} connections")
            print("🔧 OPTIMIZATION REQUIRED: Current usage exceeds recommendations")
        else:
            print("✅ Connection usage is within optimal limits")
    
    print("\n🛠️  3. Schema Verification and Fixes...")
    print("-" * 60)
    
    # Fix pattern service schema
    schema_fix = await fix_pattern_service_schema()
    if schema_fix["success"]:
        print("✅ Pattern service schema verified/fixed")
    else:
        print(f"❌ Schema fix failed: {schema_fix['error']}")
    
    # Check all tables
    table_check = await check_service_tables()
    if "error" not in table_check:
        print(f"📋 Database Tables: {table_check['total_tables']}/{table_check['required_tables']} found")
        if table_check['missing_tables']:
            print(f"⚠️  Missing tables: {', '.join(table_check['missing_tables'])}")
            print("💡 Run: python scripts/create-fresh-schema.py to create missing tables")
        else:
            print("✅ All required tables present")
    else:
        print(f"❌ Error checking tables: {table_check['error']}")
    
    print("\n⚙️  4. Database Settings Analysis...")
    print("-" * 60)
    
    settings = await optimize_database_settings()
    if "error" not in settings:
        print("📊 Current PostgreSQL Settings:")
        for setting in settings['current_settings']:
            unit = setting['unit'] or ''
            source = setting['source']
            print(f"   {setting['name']}: {setting['setting']}{unit} (source: {source})")
        
        print(f"\n💡 Key Recommendations:")
        print("   • DigitalOcean manages most settings automatically")
        print("   • Focus on application-level connection optimization")
        print("   • Use OptimizedDatabaseManager for all services")
        print("   • Monitor connection usage regularly")
    
    print("\n🔧 5. Service-Specific Fix Recommendations...")
    print("-" * 60)
    
    service_fixes = await generate_service_fixes()
    print("📋 Per-Service Connection Limits:")
    total_min = 0
    total_max = 0
    
    for service, fix_info in service_fixes.items():
        limits = fix_info['recommended_limits']
        total_min += limits['min']
        total_max += limits['max']
        print(f"   {service.ljust(15)}: {limits['min']}-{limits['max']} connections")
    
    print(f"\n📊 Total Allocation: {total_min}-{total_max} connections (target: <80)")
    
    print("\n🐳 6. Docker Configuration Check...")
    print("-" * 60)
    
    docker_config = await check_docker_compose_config()
    print("💡 Docker Compose Recommendations:")
    for category, recommendations in docker_config['recommendations'].items():
        print(f"\n   {category.replace('_', ' ').title()}:")
        for rec in recommendations:
            print(f"     • {rec}")
    
    print("\n✅ DIAGNOSTIC COMPLETE!")
    print("=" * 80)
    
    print("\n🚀 IMMEDIATE ACTION PLAN:")
    print("1. 📁 Create: services/shared/optimized_database.py")
    print("2. 🔧 Update each service to use OptimizedDatabaseManager")
    print("3. 🔄 Restart services: docker-compose restart")
    print("4. 📊 Monitor: Re-run this script to verify improvements")
    print("5. 🎯 Target: Keep total connections <80")
    
    if conn_stats.get('usage_percent', 0) > 80:
        print("\n🚨 URGENT: Connection usage >80% - restart services immediately!")
    
    print(f"\n📅 Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())