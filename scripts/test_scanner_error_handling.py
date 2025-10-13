# Name of Application: Catalyst Trading System
# Name of file: test_scanner_error_handling.py
# Version: 1.0.2
# Last Updated: 2025-10-13
# Purpose: Comprehensive error handling tests (FIXED ASYNC FIXTURES)

# REVISION HISTORY:
# v1.0.2 (2025-10-13) - Fixed async fixtures with @pytest_asyncio.fixture
# v1.0.1 (2025-10-13) - Fixed import paths
# v1.0.0 (2025-10-13) - Initial test suite

"""
Test suite for scanner-service v5.4.0 error handling.

Run with:
    pytest test_scanner_error_handling.py -v
"""

import pytest
import pytest_asyncio  # IMPORTANT: Use pytest_asyncio for async fixtures
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from fastapi import HTTPException
import asyncpg
import aiohttp
import sys
import os

# ============================================================================
# FIX IMPORT PATH
# ============================================================================
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scanner_service_path = os.path.join(project_root, 'services', 'scanner')

if scanner_service_path not in sys.path:
    sys.path.insert(0, scanner_service_path)

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "scanner_service",
        os.path.join(scanner_service_path, "scanner-service.py")
    )
    scanner_service = importlib.util.module_from_spec(spec)
    sys.modules["scanner_service"] = scanner_service
    spec.loader.exec_module(scanner_service)
    
    scan_market = scanner_service.scan_market
    filter_by_technical = scanner_service.filter_by_technical
    persist_scan_results = scanner_service.persist_scan_results
    get_security_id = scanner_service.get_security_id
    get_time_id = scanner_service.get_time_id
    filter_by_catalysts = scanner_service.filter_by_catalysts
    state = scanner_service.state
    
except Exception as e:
    print(f"ERROR: Could not import scanner service: {e}")
    raise

# ============================================================================
# FIXTURES - USING @pytest_asyncio.fixture for async fixtures
# ============================================================================

@pytest_asyncio.fixture  # ← FIXED: Use pytest_asyncio.fixture
async def mock_db_pool():
    """Mock database pool for testing"""
    pool = AsyncMock()
    pool.fetchval = AsyncMock()
    pool.fetch = AsyncMock()
    pool.execute = AsyncMock()
    return pool

@pytest_asyncio.fixture  # ← FIXED: Use pytest_asyncio.fixture
async def setup_state(mock_db_pool):
    """Setup scanner state with mocked dependencies"""
    # Store original values
    original_db = state.db_pool
    original_redis = state.redis_client
    original_http = state.http_session
    
    # Set mocks
    state.db_pool = mock_db_pool
    state.redis_client = AsyncMock()
    state.http_session = AsyncMock()
    
    yield state
    
    # Restore original values
    state.db_pool = original_db
    state.redis_client = original_redis
    state.http_session = original_http

@pytest.fixture  # ← Regular fixture (not async)
def sample_candidates():
    """Sample candidate data for testing"""
    return [
        {
            'symbol': 'AAPL',
            'security_id': 1,
            'price': 150.0,
            'volume': 5000000,
            'change_percent': 2.5,
            'catalyst_strength': 0.8,
            'catalyst_count': 3,
            'catalyst_types': ['earnings', 'upgrade'],
            'technical_score': 0.75,  # ← ADDED
            'composite_score': 0.78,  # ← ADDED
            'selected': False
        },
        {
            'symbol': 'MSFT',
            'security_id': 2,
            'price': 300.0,
            'volume': 3000000,
            'change_percent': 1.5,
            'catalyst_strength': 0.6,
            'catalyst_count': 2,
            'catalyst_types': ['news'],
            'technical_score': 0.65,  # ← ADDED
            'composite_score': 0.63,  # ← ADDED
            'selected': False
        },
        {
            'symbol': 'GOOGL',
            'security_id': 3,
            'price': 120.0,
            'volume': 2000000,
            'change_percent': -1.0,
            'catalyst_strength': 0.4,
            'catalyst_count': 1,
            'catalyst_types': ['news'],
            'technical_score': 0.45,  # ← ADDED
            'composite_score': 0.43,  # ← ADDED
            'selected': False
        }
    ]

# ============================================================================
# TEST SUITE #1: scan_market() - FIX #1
# ============================================================================

class TestScanMarketErrorHandling:
    """Tests for scan_market() specific exception handling"""
    
    @pytest.mark.asyncio
    async def test_database_error_raises_503(self, setup_state):
        """Test that database errors raise HTTPException with 503 status"""
        # Mock database error
        state.db_pool.fetch = AsyncMock(
            side_effect=asyncpg.PostgresError("Connection failed")
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await scan_market()
        
        assert exc_info.value.status_code == 503
        assert 'Database unavailable' in str(exc_info.value.detail)
        assert 'cycle_id' in exc_info.value.detail
        assert exc_info.value.detail['retry_after'] == 30
    
    @pytest.mark.asyncio
    async def test_network_error_raises_502(self, setup_state):
        """Test that network errors raise HTTPException with 502 status"""
        with patch.object(scanner_service, 'filter_by_catalysts',
                         side_effect=aiohttp.ClientError("Connection timeout")):
            with patch.object(scanner_service, 'get_active_universe', 
                            return_value=['AAPL']):
                
                with pytest.raises(HTTPException) as exc_info:
                    await scan_market()
                
                assert exc_info.value.status_code == 502
                assert 'Market data unavailable' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validation_error_raises_400(self, setup_state):
        """Test that validation errors raise HTTPException with 400 status"""
        with patch.object(scanner_service, 'get_active_universe',
                         side_effect=ValueError("Invalid universe parameters")):
            
            with pytest.raises(HTTPException) as exc_info:
                await scan_market()
            
            assert exc_info.value.status_code == 400
            assert 'Invalid scan data' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_timeout_error_raises_504(self, setup_state):
        """Test that timeout errors raise HTTPException with 504 status"""
        with patch.object(scanner_service, 'filter_by_catalysts',
                         side_effect=asyncio.TimeoutError()):
            with patch.object(scanner_service, 'get_active_universe', 
                            return_value=['AAPL']):
            
                with pytest.raises(HTTPException) as exc_info:
                    await scan_market()
                
                assert exc_info.value.status_code == 504
                assert 'Scan timeout' in str(exc_info.value.detail)
                assert exc_info.value.detail['retry_after'] == 120
    
    @pytest.mark.asyncio
    async def test_missing_field_raises_500(self, setup_state):
        """Test that KeyError raises HTTPException with 500 status"""
        with patch.object(scanner_service, 'filter_by_catalysts',
                         side_effect=KeyError('required_field')):
            with patch.object(scanner_service, 'get_active_universe', 
                            return_value=['AAPL']):
            
                with pytest.raises(HTTPException) as exc_info:
                    await scan_market()
                
                assert exc_info.value.status_code == 500
                assert 'Configuration error' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_successful_scan_returns_proper_structure(self, setup_state, sample_candidates):
        """Test that successful scan returns expected data structure"""
        with patch.object(scanner_service, 'get_active_universe', return_value=['AAPL', 'MSFT']):
            with patch.object(scanner_service, 'filter_by_catalysts', return_value=sample_candidates):
                with patch.object(scanner_service, 'filter_by_technical', return_value=sample_candidates):
                    with patch.object(scanner_service, 'persist_scan_results', 
                                    return_value={'success': 3, 'failed': 0, 'total': 3, 
                                                'failed_symbols': [], 'error_details': {}}):
                        
                        result = await scan_market()
                        
                        assert result['success'] is True
                        assert 'cycle_id' in result
                        assert 'timestamp' in result
                        assert result['universe_size'] == 2
                        assert 'candidates' in result
                        assert 'persistence' in result

# ============================================================================
# TEST SUITE #2: filter_by_technical() - FIX #2
# ============================================================================

class TestTechnicalFilterErrorHandling:
    """Tests for filter_by_technical() error tracking and handling"""
    
    @pytest.mark.asyncio
    async def test_raises_if_all_candidates_fail(self, sample_candidates):
        """Test that ValueError is raised if ALL candidates fail"""
        bad_candidates = [
            {
                'symbol': 'TOO_CHEAP',
                'price': 1.0,
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            },
            {
                'symbol': 'TOO_EXPENSIVE',
                'price': 10000.0,
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            }
        ]
        
        with pytest.raises(ValueError) as exc_info:
            await filter_by_technical(bad_candidates)
        
        assert 'failed for ALL' in str(exc_info.value)
        assert str(len(bad_candidates)) in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_returns_empty_if_no_candidates(self):
        """Test that empty list returns empty (doesn't raise)"""
        result = await filter_by_technical([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_successful_filtering_returns_scored_candidates(self, sample_candidates):
        """Test that valid candidates get scored properly"""
        result = await filter_by_technical(sample_candidates)
        
        assert len(result) > 0
        for candidate in result:
            assert 'technical_score' in candidate
            assert 'composite_score' in candidate
    
    @pytest.mark.asyncio
    async def test_filters_by_price_range(self, setup_state):
        """Test that price filters work correctly"""
        candidates = [
            {
                'symbol': 'CHEAP',
                'security_id': 1,
                'price': 3.0,
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            },
            {
                'symbol': 'VALID',
                'security_id': 2,
                'price': 50.0,
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            }
        ]
        
        result = await filter_by_technical(candidates)
        
        assert len(result) == 1
        assert result[0]['symbol'] == 'VALID'
    
    @pytest.mark.asyncio
    async def test_sorts_by_composite_score(self, sample_candidates):
        """Test that results are sorted by composite score"""
        result = await filter_by_technical(sample_candidates)
        
        scores = [c['composite_score'] for c in result]
        assert scores == sorted(scores, reverse=True)

# ============================================================================
# TEST SUITE #3: persist_scan_results() - FIX #3
# ============================================================================

class TestPersistenceErrorHandling:
    """Tests for persist_scan_results() success/failure tracking"""
    
    @pytest.mark.asyncio
    async def test_tracks_successful_persistence(self, setup_state, sample_candidates):
        """Test that successful persistence is tracked"""
        state.db_pool.fetchval = AsyncMock(return_value=1)
        state.db_pool.execute = AsyncMock(return_value=None)
        
        result = await persist_scan_results("test_cycle", sample_candidates)
        
        assert result['success'] == len(sample_candidates)
        assert result['failed'] == 0
        assert result['total'] == len(sample_candidates)
        assert len(result['failed_symbols']) == 0
    
    @pytest.mark.asyncio
    async def test_raises_if_cycle_creation_fails(self, setup_state, sample_candidates):
        """Test that failure to create cycle raises immediately"""
        state.db_pool.fetchval = AsyncMock(return_value=1)
        state.db_pool.execute = AsyncMock(
            side_effect=asyncpg.PostgresError("Cycle creation failed")
        )
        
        with pytest.raises(asyncpg.PostgresError):
            await persist_scan_results("test_cycle", sample_candidates)
    
    @pytest.mark.asyncio
    async def test_raises_if_more_than_50_percent_fail(self, setup_state):
        """Test that RuntimeError is raised if >50% fail"""
        candidates = [
            {'symbol': f'SYM{i}', 'security_id': i, 'price': 50.0, 
             'volume': 5000000, 'change_percent': 2.0,
             'catalyst_strength': 0.8, 'technical_score': 0.7,
             'composite_score': 0.75, 'catalyst_count': 1,
             'catalyst_types': ['news'], 'selected': False}
            for i in range(10)
        ]
        
        state.db_pool.fetchval = AsyncMock(return_value=1)
        
        # Fail 60% (6 out of 10)
        state.db_pool.execute = AsyncMock(
            side_effect=[
                None,  # Cycle creation
                None, None, None, None,  # 4 succeed
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),  # 6 fail
            ]
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            await persist_scan_results("test_cycle", candidates)
        
        assert 'CRITICAL' in str(exc_info.value)
        assert '6/10' in str(exc_info.value)

# ============================================================================
# TEST SUITE #4: Helper Functions Error Handling
# ============================================================================

class TestHelperFunctionsErrorHandling:
    """Tests for get_security_id() and get_time_id() error handling"""
    
    @pytest.mark.asyncio
    async def test_get_security_id_handles_db_error(self, setup_state):
        """Test that get_security_id handles database errors properly"""
        state.db_pool.fetchval = AsyncMock(
            side_effect=asyncpg.PostgresError("DB error")
        )
        
        with pytest.raises(asyncpg.PostgresError):
            await get_security_id("AAPL")
    
    @pytest.mark.asyncio
    async def test_get_security_id_raises_if_none_returned(self, setup_state):
        """Test that ValueError raised if security_id is None"""
        state.db_pool.fetchval = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError) as exc_info:
            await get_security_id("INVALID")
        
        assert "Failed to get security_id" in str(exc_info.value)

# ============================================================================
# SIMPLIFIED TEST RUNNER
# ============================================================================

if __name__ == "__main__":
    print(f"✅ Scanner service imported successfully")
    print(f"   Path: {scanner_service_path}")
    print("")
    pytest.main([__file__, "-v", "--tb=short"])
