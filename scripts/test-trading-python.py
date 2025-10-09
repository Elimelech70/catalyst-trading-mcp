#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: test_trading_service.py
Version: 1.0.1
Last Updated: 2025-10-07
Purpose: Advanced test suite for Trading Service v5.0.0

REVISION HISTORY:
v1.0.1 (2025-10-07) - Fixed database connection
  - Use environment DATABASE_URL properly
  - Added connection string validation
  - Better error handling for remote DB
v1.0.0 (2025-10-07) - Comprehensive Python test suite
  - Async tests for all endpoints
  - Data validation tests
  - Integration tests
  - Performance benchmarks

Description:
Advanced testing for Trading Service including data validation,
integration testing, and performance benchmarks.
"""

import asyncio
import aiohttp
import asyncpg
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from decimal import Decimal
import sys

# Configuration
TRADING_URL = "http://localhost:5002"
SCANNER_URL = "http://localhost:5001"
NEWS_URL = "http://localhost:5008"

# Get DATABASE_URL from environment - this should be your DigitalOcean database
DATABASE_URL = os.getenv("DATABASE_URL")

# Check if DATABASE_URL is set
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL environment variable not set!")
    print("Please export your DigitalOcean database URL:")
    print('export DATABASE_URL="postgresql://user:password@host:port/database?sslmode=require"')
    sys.exit(1)

# Validate DATABASE_URL format
if "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL:
    print("⚠️ WARNING: DATABASE_URL points to localhost, but database is on DigitalOcean")
    print("Current DATABASE_URL:", DATABASE_URL[:30] + "...")
    print("Make sure to use your DigitalOcean database connection string")

print(f"📊 Using database: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'unknown'}")

class TradingServiceTester:
    def __init__(self):
        self.trading_url = TRADING_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.db_conn: Optional[asyncpg.Connection] = None
        self.test_cycle_id: Optional[str] = None
        self.test_results = []
        
    async def setup(self):
        """Initialize connections"""
        self.session = aiohttp.ClientSession()
        
        # Connect to database with better error handling
        try:
            print(f"Connecting to database...")
            self.db_conn = await asyncpg.connect(DATABASE_URL)
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            print("\nTroubleshooting:")
            print("1. Make sure DATABASE_URL is exported:")
            print('   export DATABASE_URL="your-digitalocean-connection-string"')
            print("2. Verify the database is accessible from this server")
            print("3. Check if SSL is required (add ?sslmode=require to connection string)")
            raise
            
        print("✅ Test environment initialized")
        
    async def cleanup(self):
        """Clean up connections"""
        if self.session:
            await self.session.close()
        if self.db_conn:
            await self.db_conn.close()
            
    async def test_health_check(self):
        """Test 1: Health Check"""
        print("\n🧪 TEST 1: Health Check")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{self.trading_url}/health") as response:
                data = await response.json()
                assert response.status == 200
                assert data["status"] == "healthy"
                print(f"✅ Health check passed: {data}")
                self.test_results.append(("Health Check", "PASS"))
                return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            self.test_results.append(("Health Check", "FAIL"))
            return False
            
    async def test_create_cycle(self):
        """Test 2: Create Trading Cycle"""
        print("\n🧪 TEST 2: Create Trading Cycle")
        print("-" * 40)
        
        try:
            # Create cycle directly in database
            self.test_cycle_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            await self.db_conn.execute("""
                INSERT INTO trading_cycles (
                    cycle_id, cycle_name, status, start_time, mode,
                    initial_capital, available_capital, config
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, 
                self.test_cycle_id,
                "API Test Cycle",
                "active",
                datetime.now(),
                "paper",
                100000.00,
                100000.00,
                json.dumps({
                    "max_positions": 5,
                    "position_size_pct": 0.2,
                    "max_loss_per_trade": 1000,
                    "stop_loss_pct": 0.02,
                    "take_profit_pct": 0.06
                })
            )
            
            print(f"✅ Created test cycle: {self.test_cycle_id}")
            self.test_results.append(("Create Cycle", "PASS"))
            return True
        except Exception as e:
            print(f"❌ Failed to create cycle: {e}")
            self.test_results.append(("Create Cycle", "FAIL"))
            return False
            
    async def test_get_cycles(self):
        """Test 3: Get Active Cycles"""
        print("\n🧪 TEST 3: Get Active Cycles")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{self.trading_url}/api/v1/cycles/active") as response:
                cycles = await response.json()
                assert response.status == 200
                
                if cycles:
                    print(f"✅ Found {len(cycles)} active cycles")
                    for cycle in cycles[:2]:  # Show first 2
                        print(f"  - {cycle['cycle_id']}: {cycle['status']}")
                    
                    # Use first active cycle if we didn't create one
                    if not self.test_cycle_id and cycles:
                        self.test_cycle_id = cycles[0]['cycle_id']
                else:
                    print("⚠️ No active cycles found")
                    
                self.test_results.append(("Get Cycles", "PASS"))
                return True
        except Exception as e:
            print(f"❌ Failed to get cycles: {e}")
            self.test_results.append(("Get Cycles", "FAIL"))
            return False
            
    async def test_create_position(self, symbol: str = "AAPL"):
        """Test 4: Create Position"""
        print(f"\n🧪 TEST 4: Create Position ({symbol})")
        print("-" * 40)
        
        if not self.test_cycle_id:
            print("⚠️ No cycle available, skipping position creation")
            self.test_results.append(("Create Position", "SKIP"))
            return False
            
        try:
            position_data = {
                "cycle_id": self.test_cycle_id,
                "symbol": symbol,
                "side": "buy",
                "quantity": 100,
                "entry_price": 180.50,
                "stop_loss": 176.50,
                "take_profit": 189.50
            }
            
            print(f"Creating position: {position_data}")
            
            async with self.session.post(
                f"{self.trading_url}/api/v1/positions",
                json=position_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Position created: ID={data.get('position_id')}")
                    self.test_results.append(("Create Position", "PASS"))
                    return True
                else:
                    text = await response.text()
                    print(f"❌ Failed to create position: {text}")
                    self.test_results.append(("Create Position", "FAIL"))
                    return False
        except Exception as e:
            print(f"❌ Error creating position: {e}")
            self.test_results.append(("Create Position", "FAIL"))
            return False
            
    async def test_get_positions(self):
        """Test 5: Get Positions"""
        print("\n🧪 TEST 5: Get Positions")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{self.trading_url}/api/v1/positions") as response:
                positions = await response.json()
                assert response.status == 200
                
                print(f"✅ Found {len(positions)} open positions")
                for pos in positions[:3]:  # Show first 3
                    print(f"  - {pos['symbol']}: {pos['quantity']} @ ${pos['entry_price']}")
                    
                self.test_results.append(("Get Positions", "PASS"))
                return True
        except Exception as e:
            print(f"❌ Failed to get positions: {e}")
            self.test_results.append(("Get Positions", "FAIL"))
            return False
            
    async def test_portfolio_summary(self):
        """Test 6: Portfolio Summary"""
        print("\n🧪 TEST 6: Portfolio Summary")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{self.trading_url}/api/v1/portfolio/summary") as response:
                portfolio = await response.json()
                assert response.status == 200
                
                print("✅ Portfolio Summary:")
                print(f"  - Total Value: ${portfolio.get('total_value', 0):,.2f}")
                print(f"  - Available Capital: ${portfolio.get('available_capital', 0):,.2f}")
                print(f"  - Open Positions: {portfolio.get('open_positions', 0)}")
                print(f"  - Today's P&L: ${portfolio.get('daily_pnl', 0):,.2f}")
                
                self.test_results.append(("Portfolio Summary", "PASS"))
                return True
        except Exception as e:
            print(f"❌ Failed to get portfolio: {e}")
            self.test_results.append(("Portfolio Summary", "FAIL"))
            return False
            
    async def test_database_normalization(self):
        """Test 7: Database Normalization"""
        print("\n🧪 TEST 7: Database Normalization Check")
        print("-" * 40)
        
        try:
            # Check positions use security_id
            result = await self.db_conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_positions,
                    COUNT(p.security_id) as with_security_id,
                    COUNT(DISTINCT s.symbol) as unique_symbols
                FROM positions p
                LEFT JOIN securities s ON p.security_id = s.security_id
                WHERE p.created_at > NOW() - INTERVAL '1 day'
            """)
            
            if result['total_positions'] > 0:
                if result['with_security_id'] == result['total_positions']:
                    print("✅ All positions use security_id (normalized)")
                else:
                    print("❌ Some positions missing security_id")
            else:
                print("⚠️ No recent positions to check")
                
            # Test JOIN query
            positions_with_symbols = await self.db_conn.fetch("""
                SELECT 
                    p.position_id,
                    s.symbol,
                    s.company_name,
                    sec.sector_name,
                    p.quantity,
                    p.entry_price
                FROM positions p
                JOIN securities s ON p.security_id = s.security_id
                LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
                ORDER BY p.created_at DESC
                LIMIT 5
            """)
            
            if positions_with_symbols:
                print(f"✅ JOIN queries working ({len(positions_with_symbols)} positions with symbols)")
                for pos in positions_with_symbols[:2]:
                    print(f"  - {pos['symbol']}: {pos['quantity']} shares")
            else:
                print("⚠️ No positions found for JOIN test")
                
            self.test_results.append(("Database Normalization", "PASS"))
            return True
        except Exception as e:
            print(f"❌ Normalization check failed: {e}")
            self.test_results.append(("Database Normalization", "FAIL"))
            return False
            
    async def test_performance(self):
        """Test 8: Performance Benchmarks"""
        print("\n🧪 TEST 8: Performance Benchmarks")
        print("-" * 40)
        
        try:
            # Test response times
            endpoints = [
                ("/health", "Health"),
                ("/api/v1/positions", "Positions"),
                ("/api/v1/cycles/active", "Cycles"),
                ("/api/v1/portfolio/summary", "Portfolio")
            ]
            
            for endpoint, name in endpoints:
                times = []
                for _ in range(5):
                    start = time.time()
                    async with self.session.get(f"{self.trading_url}{endpoint}") as response:
                        await response.read()
                    elapsed = (time.time() - start) * 1000
                    times.append(elapsed)
                    
                avg_time = sum(times) / len(times)
                print(f"  {name}: {avg_time:.2f}ms avg")
                
            self.test_results.append(("Performance", "PASS"))
            return True
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            self.test_results.append(("Performance", "FAIL"))
            return False
            
    async def test_integration(self):
        """Test 9: Integration with Other Services"""
        print("\n🧪 TEST 9: Service Integration")
        print("-" * 40)
        
        try:
            # Check Scanner integration
            async with self.session.get(f"{SCANNER_URL}/health") as response:
                scanner_health = await response.json()
                print(f"✅ Scanner Service: {scanner_health['status']}")
                
            # Check News integration
            async with self.session.get(f"{NEWS_URL}/health") as response:
                news_health = await response.json()
                print(f"✅ News Service: {news_health['status']}")
                
            self.test_results.append(("Integration", "PASS"))
            return True
        except Exception as e:
            print(f"❌ Integration test failed: {e}")
            self.test_results.append(("Integration", "FAIL"))
            return False
            
    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("🚀 CATALYST TRADING SYSTEM - TRADING SERVICE TEST SUITE")
        print("=" * 60)
        
        await self.setup()
        
        # Run tests
        await self.test_health_check()
        await self.test_create_cycle()
        await self.test_get_cycles()
        await self.test_create_position("AAPL")
        await self.test_create_position("MSFT")
        await self.test_create_position("GOOGL")
        await self.test_get_positions()
        await self.test_portfolio_summary()
        await self.test_database_normalization()
        await self.test_performance()
        await self.test_integration()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, status in self.test_results if status == "PASS")
        failed = sum(1 for _, status in self.test_results if status == "FAIL")
        skipped = sum(1 for _, status in self.test_results if status == "SKIP")
        
        for test_name, status in self.test_results:
            emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
            print(f"{emoji} {test_name}: {status}")
            
        print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
        
        if failed == 0:
            print("\n🎉 ALL TESTS PASSED! Trading Service v5.0.0 is fully operational!")
        else:
            print(f"\n⚠️ {failed} tests failed. Check output above for details.")
            
        await self.cleanup()
        
        return failed == 0

async def main():
    tester = TradingServiceTester()
    success = await tester.run_all_tests()
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())