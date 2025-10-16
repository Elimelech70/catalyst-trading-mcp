#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: test_catalyst_workflow.py (Configuration Fix)
Version: 1.0.1
Last Updated: 2025-10-16
Purpose: Fixed configuration loading for workflow test suite

REVISION HISTORY:
v1.0.1 (2025-10-16) - Fixed DATABASE_URL loading
  - Added proper environment variable loading
  - Added validation before use
  - Better error messages for missing config

Description:
Configuration fix for the test workflow script to properly load
DATABASE_URL from environment variables.
"""

import os
import sys
import asyncio
import asyncpg
from datetime import datetime

# ======================================================================
# CONFIGURATION FIX
# ======================================================================

class Config:
    """Configuration loaded from environment variables"""
    
    # Load DATABASE_URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Service URLs (with defaults for local testing)
    ORCHESTRATION_URL = os.getenv("ORCHESTRATION_URL", "http://localhost:5000")
    SCANNER_URL = os.getenv("SCANNER_URL", "http://localhost:5001") 
    PATTERN_URL = os.getenv("PATTERN_URL", "http://localhost:5002")
    TECHNICAL_URL = os.getenv("TECHNICAL_URL", "http://localhost:5003")
    RISK_URL = os.getenv("RISK_URL", "http://localhost:5004")
    TRADING_URL = os.getenv("TRADING_URL", "http://localhost:5005")
    NEWS_URL = os.getenv("NEWS_URL", "http://localhost:5008")
    REPORTING_URL = os.getenv("REPORTING_URL", "http://localhost:5009")
    
    # Redis configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Trading configuration
    TRADING_MODE = os.getenv("TRADING_MODE", "paper")
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.DATABASE_URL:
            print("❌ ERROR: DATABASE_URL environment variable not set!")
            print("\nTo fix this, run:")
            print('export DATABASE_URL="postgresql://doadmin:YOUR_PASSWORD@YOUR_CLUSTER.db.ondigitalocean.com:25060/catalyst_trading?sslmode=require"')
            print("\nReplace YOUR_PASSWORD and YOUR_CLUSTER with your actual DigitalOcean database credentials.")
            return False
            
        # Check if it looks like a valid PostgreSQL URL
        if not cls.DATABASE_URL.startswith("postgresql://"):
            print("⚠️ WARNING: DATABASE_URL doesn't look like a PostgreSQL connection string")
            print(f"Current value: {cls.DATABASE_URL[:30]}...")
            return False
            
        # Warn if using localhost with DigitalOcean deployment
        if "localhost" in cls.DATABASE_URL or "127.0.0.1" in cls.DATABASE_URL:
            print("⚠️ WARNING: DATABASE_URL points to localhost, but you're using DigitalOcean")
            print("Make sure to use your DigitalOcean database connection string")
            
        return True

# Create config instance
config = Config()

# ======================================================================
# TEST SUITE INITIALIZATION
# ======================================================================

async def run_all_tests():
    """Run all workflow tests with proper configuration"""
    
    # Validate configuration first
    if not config.validate():
        print("\n❌ Configuration validation failed. Exiting...")
        sys.exit(1)
    
    print("======================================================================")
    print("CATALYST TRADING SYSTEM - WORKFLOW TEST SUITE v1.0.1")
    print("======================================================================")
    print(f"Starting tests at {datetime.now().isoformat()}")
    print(f"\nConfiguration:")
    
    # Safely display configuration (hide password)
    db_display = config.DATABASE_URL
    if '@' in db_display:
        # Hide password in display
        parts = db_display.split('@')
        user_part = parts[0].split('://')[1].split(':')[0]
        host_part = parts[1]
        db_display = f"postgresql://{user_part}:****@{host_part}"
    
    print(f"Database: {db_display}")
    print(f"Orchestration: {config.ORCHESTRATION_URL}")
    print(f"Trading Mode: {config.TRADING_MODE}")
    print("-" * 70)
    
    # Now proceed with tests
    try:
        # Test database connection
        print("\n📊 Testing database connection...")
        conn = await asyncpg.connect(config.DATABASE_URL)
        
        # Check database version
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Connected to PostgreSQL: {version.split(',')[0]}")
        
        # Check if tables exist
        table_count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        print(f"✅ Found {table_count} tables in database")
        
        await conn.close()
        
        # Add your other tests here...
        print("\n✅ All tests completed successfully!")
        return True
        
    except asyncpg.PostgresError as e:
        print(f"\n❌ Database error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your DATABASE_URL is correct")
        print("2. Ensure your IP is whitelisted in DigitalOcean trusted sources")
        print("3. Verify the database is running")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

# ======================================================================
# MAIN EXECUTION
# ======================================================================

if __name__ == "__main__":
    # Run the test suite
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)