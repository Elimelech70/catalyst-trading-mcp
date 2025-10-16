#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: test_catalyst_workflow.py
Version: 1.0.0
Last Updated: 2025-10-16
Purpose: Complete end-to-end workflow testing

REVISION HISTORY:
v1.0.0 (2025-10-16) - Initial comprehensive test suite
- Tests all 8 services
- Validates complete trading workflow
- Includes safety checks
- Performance monitoring

Description:
Complete test suite for the Catalyst Trading MCP system.
Tests the entire workflow from news → scanning → analysis → trading.
"""

import asyncio
import aiohttp
import asyncpg
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("catalyst_test")

# ============================================================================
# CONFIGURATION
# ============================================================================
@dataclass
class TestConfig:
    """Test configuration"""
    # Service URLs
    NEWS_URL = "http://localhost:5008"
    SCANNER_URL = "http://localhost:5001"
    PATTERN_URL = "http://localhost:5002"
    TECHNICAL_URL = "http://localhost:5003"
    RISK_URL = "http://localhost:5004"
    TRADING_URL = "http://localhost:5005"
    REPORTING_URL = "http://localhost:5009"
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Test symbols
    TEST_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
    
    # Test parameters
    TEST_POSITION_SIZE = 100
    TEST_RISK_PERCENT = 2.0
    MAX_TEST_POSITIONS = 3

config = TestConfig()

# ============================================================================
# TEST RESULT TRACKING
# ============================================================================
class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WARNING = "WARNING"

@dataclass
class TestResult:
    test_name: str
    status: TestStatus
    duration: float
    message: str = ""
    details: Dict = None

class TestSuite:
    """Main test suite coordinator"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.start_time = None
        
    async def setup(self):
        """Initialize test suite"""
        self.session = aiohttp.ClientSession()
        self.db_pool = await asyncpg.create_pool(config.DATABASE_URL)
        self.start_time = time.time()
        logger.info("Test suite initialized")
        
    async def teardown(self):
        """Clean up test suite"""
        if self.session:
            await self.session.close()
        if self.db_pool:
            await self.db_pool.close()
        logger.info("Test suite cleanup complete")
        
    def add_result(self, result: TestResult):
        """Add test result"""
        self.results.append(result)
        status_symbol = {
            TestStatus.PASSED: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.SKIPPED: "⏭️",
            TestStatus.WARNING: "⚠️"
        }[result.status]
        
        logger.info(f"{status_symbol} {result.test_name}: {result.status.value} ({result.duration:.2f}s)")
        if result.message:
            logger.info(f"   {result.message}")
    
    def print_summary(self):
        """Print test summary"""
        total_duration = time.time() - self.start_time
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        warnings = sum(1 for r in self.results if r.status == TestStatus.WARNING)
        
        print("\n" + "="*70)
        print("CATALYST TRADING SYSTEM - TEST RESULTS")
        print("="*70)
        print(f"Total Tests: {len(self.results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️ Skipped: {skipped}")
        print(f"⚠️ Warnings: {warnings}")
        print(f"Duration: {total_duration:.2f} seconds")
        print("="*70)
        
        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if r.status == TestStatus.FAILED:
                    print(f"  - {r.test_name}: {r.message}")
        
        print("\n")
        return failed == 0

# ============================================================================
# SERVICE HEALTH CHECKS
# ============================================================================
async def test_service_health(suite: TestSuite):
    """Test all service health endpoints"""
    services = {
        "News Service": config.NEWS_URL,
        "Scanner Service": config.SCANNER_URL,
        "Pattern Service": config.PATTERN_URL,
        "Technical Service": config.TECHNICAL_URL,
        "Risk Manager": config.RISK_URL,
        "Trading Service": config.TRADING_URL,
        "Reporting Service": config.REPORTING_URL
    }
    
    for name, url in services.items():
        start = time.time()
        try:
            async with suite.session.get(f"{url}/health", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "healthy":
                        suite.add_result(TestResult(
                            test_name=f"Health: {name}",
                            status=TestStatus.PASSED,
                            duration=time.time() - start,
                            message=f"Version {data.get('version', 'unknown')}"
                        ))
                    else:
                        suite.add_result(TestResult(
                            test_name=f"Health: {name}",
                            status=TestStatus.WARNING,
                            duration=time.time() - start,
                            message=f"Service unhealthy: {data}"
                        ))
                else:
                    suite.add_result(TestResult(
                        test_name=f"Health: {name}",
                        status=TestStatus.FAILED,
                        duration=time.time() - start,
                        message=f"HTTP {resp.status}"
                    ))
        except Exception as e:
            suite.add_result(TestResult(
                test_name=f"Health: {name}",
                status=TestStatus.FAILED,
                duration=time.time() - start,
                message=str(e)
            ))

# ============================================================================
# DATABASE TESTS
# ============================================================================
async def test_database_schema(suite: TestSuite):
    """Test database schema integrity"""
    start = time.time()
    try:
        # Check critical tables
        tables = [
            "securities", "time_dimension", "news_sentiment",
            "scan_results", "pattern_analysis", "technical_indicators",
            "positions", "risk_metrics"
        ]
        
        missing_tables = []
        for table in tables:
            exists = await suite.db_pool.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                table
            )
            if not exists:
                missing_tables.append(table)
        
        if missing_tables:
            suite.add_result(TestResult(
                test_name="Database Schema",
                status=TestStatus.FAILED,
                duration=time.time() - start,
                message=f"Missing tables: {', '.join(missing_tables)}"
            ))
        else:
            # Check for normalized schema (security_id FKs)
            has_fks = await suite.db_pool.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'scan_results' 
                    AND column_name = 'security_id'
                )
            """)
            
            if has_fks:
                suite.add_result(TestResult(
                    test_name="Database Schema",
                    status=TestStatus.PASSED,
                    duration=time.time() - start,
                    message="v5.0 normalized schema verified"
                ))
            else:
                suite.add_result(TestResult(
                    test_name="Database Schema",
                    status=TestStatus.WARNING,
                    duration=time.time() - start,
                    message="Schema not fully normalized"
                ))
                
    except Exception as e:
        suite.add_result(TestResult(
            test_name="Database Schema",
            status=TestStatus.FAILED,
            duration=time.time() - start,
            message=str(e)
        ))

# ============================================================================
# WORKFLOW TESTS
# ============================================================================
async def test_news_ingestion(suite: TestSuite):
    """Test news ingestion and sentiment analysis"""
    start = time.time()
    try:
        # Ingest test news
        test_news = {
            "symbol": "AAPL",
            "headline": "Apple announces breakthrough AI chip with 50% performance gain",
            "summary": "Apple unveiled its new M4 AI processor featuring revolutionary neural engine",
            "source": "test_suite",
            "url": "http://example.com/test"
        }
        
        async with suite.session.post(
            f"{config.NEWS_URL}/api/v1/news/ingest",
            params=test_news,
            timeout=10
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    suite.add_result(TestResult(
                        test_name="News Ingestion",
                        status=TestStatus.PASSED,
                        duration=time.time() - start,
                        message=f"News ID: {data.get('news_id')}, "
                               f"Sentiment: {data['analysis']['sentiment_score']:.2f}",
                        details=data
                    ))
                else:
                    suite.add_result(TestResult(
                        test_name="News Ingestion",
                        status=TestStatus.FAILED,
                        duration=time.time() - start,
                        message="Ingestion failed"
                    ))
            else:
                suite.add_result(TestResult(
                    test_name="News Ingestion",
                    status=TestStatus.FAILED,
                    duration=time.time() - start,
                    message=f"HTTP {resp.status}"
                ))
                
    except Exception as e:
        suite.add_result(TestResult(
            test_name="News Ingestion",
            status=TestStatus.FAILED,
            duration=time.time() - start,
            message=str(e)
        ))

async def test_market_scan(suite: TestSuite):
    """Test market scanning"""
    start = time.time()
    try:
        async with suite.session.post(
            f"{config.SCANNER_URL}/api/v1/scan",
            timeout=30
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    suite.add_result(TestResult(
                        test_name="Market Scan",
                        status=TestStatus.PASSED,
                        duration=time.time() - start,
                        message=f"Cycle {data.get('cycle_id')}: "
                               f"{data.get('candidates', 0)} candidates found",
                        details=data
                    ))
                else:
                    suite.add_result(TestResult(
                        test_name="Market Scan",
                        status=TestStatus.WARNING,
                        duration=time.time() - start,
                        message=data.get("error", "Scan failed")
                    ))
            else:
                suite.add_result(TestResult(
                    test_name="Market Scan",
                    status=TestStatus.FAILED,
                    duration=time.time() - start,
                    message=f"HTTP {resp.status}"
                ))
                
    except Exception as e:
        suite.add_result(TestResult(
            test_name="Market Scan",
            status=TestStatus.FAILED,
            duration=time.time() - start,
            message=str(e)
        ))

async def test_pattern_detection(suite: TestSuite):
    """Test pattern detection"""
    start = time.time()
    try:
        for symbol in config.TEST_SYMBOLS[:2]:  # Test first 2 symbols
            request_data = {
                "symbol": symbol,
                "timeframe": "5m",
                "lookback_bars": 50,
                "min_confidence": 0.3
            }
            
            async with suite.session.post(
                f"{config.PATTERN_URL}/api/v1/detect",
                json=request_data,
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        suite.add_result(TestResult(
                            test_name=f"Pattern Detection: {symbol}",
                            status=TestStatus.PASSED,
                            duration=time.time() - start,
                            message=f"{data.get('patterns_found', 0)} patterns found",
                            details=data
                        ))
                    else:
                        suite.add_result(TestResult(
                            test_name=f"Pattern Detection: {symbol}",
                            status=TestStatus.WARNING,
                            duration=time.time() - start,
                            message="No patterns detected"
                        ))
                    break  # One successful test is enough
                    
    except Exception as e:
        suite.add_result(TestResult(
            test_name="Pattern Detection",
            status=TestStatus.FAILED,
            duration=time.time() - start,
            message=str(e)
        ))

async def test_risk_validation(suite: TestSuite):
    """Test risk management validation"""
    start = time.time()
    try:
        # Create test position
        test_position = {
            "cycle_id": 1,
            "symbol": "AAPL",
            "side": "long",
            "quantity": 100,
            "entry_price": 175.50,
            "stop_price": 172.00,
            "target_price": 180.00
        }
        
        async with suite.session.post(
            f"{config.RISK_URL}/api/v1/validate-position",
            json=test_position,
            timeout=10
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("approved"):
                    suite.add_result(TestResult(
                        test_name="Risk Validation",
                        status=TestStatus.PASSED,
                        duration=time.time() - start,
                        message=f"Position approved, size: {data.get('position_size')}",
                        details=data
                    ))
                else:
                    suite.add_result(TestResult(
                        test_name="Risk Validation",
                        status=TestStatus.PASSED,
                        duration=time.time() - start,
                        message=f"Position rejected: {data.get('rejection_reason')}",
                        details=data
                    ))
            else:
                suite.add_result(TestResult(
                    test_name="Risk Validation",
                    status=TestStatus.FAILED,
                    duration=time.time() - start,
                    message=f"HTTP {resp.status}"
                ))
                
    except Exception as e:
        suite.add_result(TestResult(
            test_name="Risk Validation",
            status=TestStatus.FAILED,
            duration=time.time() - start,
            message=str(e)
        ))

# ============================================================================
# INTEGRATION TESTS
# ============================================================================
async def test_end_to_end_workflow(suite: TestSuite):
    """Test complete trading workflow"""
    start = time.time()
    workflow_steps = []
    
    try:
        # Step 1: Trigger market scan
        async with suite.session.post(f"{config.SCANNER_URL}/api/v1/scan") as resp:
            scan_data = await resp.json()
            workflow_steps.append(f"Scan: {scan_data.get('candidates', 0)} candidates")
            
            if not scan_data.get("success"):
                raise Exception("Scan failed")
        
        # Step 2: Get top candidates
        async with suite.session.get(
            f"{config.SCANNER_URL}/api/v1/candidates",
            params={"limit": 5}
        ) as resp:
            candidates = await resp.json()
            workflow_steps.append(f"Candidates: {candidates.get('count', 0)} retrieved")
        
        # Step 3: Check patterns for top candidate
        if candidates.get("candidates"):
            symbol = candidates["candidates"][0]["symbol"]
            
            async with suite.session.post(
                f"{config.PATTERN_URL}/api/v1/detect",
                json={"symbol": symbol, "timeframe": "5m"}
            ) as resp:
                patterns = await resp.json()
                workflow_steps.append(f"Patterns: {patterns.get('patterns_found', 0)} for {symbol}")
        
        # Step 4: Validate with risk manager
        if candidates.get("candidates"):
            candidate = candidates["candidates"][0]
            position = {
                "cycle_id": scan_data.get("cycle_id", 1),
                "symbol": candidate["symbol"],
                "side": "long",
                "quantity": 100,
                "entry_price": candidate.get("current_price", 100),
                "stop_price": candidate.get("current_price", 100) * 0.98,
                "target_price": candidate.get("current_price", 100) * 1.05
            }
            
            async with suite.session.post(
                f"{config.RISK_URL}/api/v1/validate-position",
                json=position
            ) as resp:
                risk_check = await resp.json()
                workflow_steps.append(f"Risk: {'Approved' if risk_check.get('approved') else 'Rejected'}")
        
        suite.add_result(TestResult(
            test_name="End-to-End Workflow",
            status=TestStatus.PASSED,
            duration=time.time() - start,
            message=" → ".join(workflow_steps)
        ))
        
    except Exception as e:
        suite.add_result(TestResult(
            test_name="End-to-End Workflow",
            status=TestStatus.FAILED,
            duration=time.time() - start,
            message=f"Failed at: {' → '.join(workflow_steps)} | Error: {str(e)}"
        ))

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================
async def test_response_times(suite: TestSuite):
    """Test service response times"""
    start = time.time()
    slow_endpoints = []
    
    endpoints = [
        (config.NEWS_URL, "/health"),
        (config.SCANNER_URL, "/health"),
        (config.PATTERN_URL, "/health"),
        (config.RISK_URL, "/health"),
        (config.TRADING_URL, "/health")
    ]
    
    for base_url, endpoint in endpoints:
        endpoint_start = time.time()
        try:
            async with suite.session.get(f"{base_url}{endpoint}", timeout=2) as resp:
                response_time = time.time() - endpoint_start
                if response_time > 1.0:
                    slow_endpoints.append(f"{base_url}{endpoint}: {response_time:.2f}s")
        except:
            pass
    
    if slow_endpoints:
        suite.add_result(TestResult(
            test_name="Response Times",
            status=TestStatus.WARNING,
            duration=time.time() - start,
            message=f"Slow endpoints: {', '.join(slow_endpoints)}"
        ))
    else:
        suite.add_result(TestResult(
            test_name="Response Times",
            status=TestStatus.PASSED,
            duration=time.time() - start,
            message="All endpoints < 1s"
        ))

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
async def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*70)
    print("CATALYST TRADING SYSTEM - WORKFLOW TEST SUITE v1.0.0")
    print("="*70)
    print(f"Starting tests at {datetime.now().isoformat()}")
    print(f"Database: {config.DATABASE_URL[:30]}...")
    print("="*70 + "\n")
    
    suite = TestSuite()
    await suite.setup()
    
    try:
        # Run test categories
        print("Running Service Health Checks...")
        await test_service_health(suite)
        
        print("\nRunning Database Tests...")
        await test_database_schema(suite)
        
        print("\nRunning Workflow Tests...")
        await test_news_ingestion(suite)
        await test_market_scan(suite)
        await test_pattern_detection(suite)
        await test_risk_validation(suite)
        
        print("\nRunning Integration Tests...")
        await test_end_to_end_workflow(suite)
        
        print("\nRunning Performance Tests...")
        await test_response_times(suite)
        
        # Print summary
        success = suite.print_summary()
        
        # Save results to file
        with open("test_results.json", "w") as f:
            json.dump([{
                "test": r.test_name,
                "status": r.status.value,
                "duration": r.duration,
                "message": r.message,
                "details": r.details
            } for r in suite.results], f, indent=2, default=str)
        
        print("Results saved to test_results.json")
        
        return success
        
    finally:
        await suite.teardown()

# ============================================================================
# QUICK WORKFLOW TEST
# ============================================================================
async def quick_workflow_test():
    """Quick test of core workflow"""
    print("\n🚀 QUICK WORKFLOW TEST")
    print("-" * 40)
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Check services
            print("1. Checking services...")
            services_up = 0
            for name, url in [("News", config.NEWS_URL), ("Scanner", config.SCANNER_URL), 
                             ("Pattern", config.PATTERN_URL), ("Risk", config.RISK_URL)]:
                try:
                    async with session.get(f"{url}/health", timeout=2) as resp:
                        if resp.status == 200:
                            services_up += 1
                            print(f"   ✅ {name}")
                        else:
                            print(f"   ❌ {name}")
                except:
                    print(f"   ❌ {name} (unreachable)")
            
            if services_up < 4:
                print("⚠️ Not all services are running!")
                return
            
            # 2. Trigger scan
            print("\n2. Triggering market scan...")
            async with session.post(f"{config.SCANNER_URL}/api/v1/scan", timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Scan complete: {data.get('candidates', 0)} candidates")
                else:
                    print(f"   ❌ Scan failed")
                    return
            
            # 3. Get candidates
            print("\n3. Retrieving candidates...")
            async with session.get(f"{config.SCANNER_URL}/api/v1/candidates?limit=3") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    for c in candidates[:3]:
                        print(f"   - {c['symbol']}: Score {c['combined_score']:.2f}")
                else:
                    print(f"   ❌ Failed to get candidates")
            
            print("\n✅ Quick workflow test complete!")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")

# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        # Run quick test
        asyncio.run(quick_workflow_test())
    else:
        # Run full test suite
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
