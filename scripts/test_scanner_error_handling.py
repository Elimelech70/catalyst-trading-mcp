# Name of Application: Catalyst Trading System
# Name of file: test_scanner_error_handling.py
# Version: 1.0.0
# Last Updated: 2025-10-13
# Purpose: Comprehensive error handling tests for scanner-service v5.4.0

# REVISION HISTORY:
# v1.0.0 (2025-10-13) - Initial test suite for error handling
# - Tests for all specific exception types (Fix #1)
# - Tests for technical filter error tracking (Fix #2)
# - Tests for persistence failure handling (Fix #3)
# - Tests for critical failure detection
# - Tests for HTTP status codes
# - Tests for structured logging

"""
Test suite for scanner-service v5.4.0 error handling.

Tests the three major fixes:
1. scan_market() - Specific exception handling with proper HTTP codes
2. filter_by_technical() - No silent failures, tracks errors
3. persist_scan_results() - Success/failure tracking, raises on critical failures

Run with:
    pytest test_scanner_error_handling.py -v
    pytest test_scanner_error_handling.py -v --log-cli-level=INFO
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from fastapi import HTTPException
import asyncpg
import aiohttp

# Import the scanner service components
# Adjust import path based on your project structure
import sys
sys.path.insert(0, '../services/scanner')
from scanner_service import (
    scan_market,
    filter_by_technical,
    persist_scan_results,
    get_security_id,
    get_time_id,
    filter_by_catalysts,
    state
)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def mock_db_pool():
    """Mock database pool for testing"""
    pool = AsyncMock()
    pool.fetchval = AsyncMock()
    pool.fetch = AsyncMock()
    pool.execute = AsyncMock()
    return pool

@pytest.fixture
async def setup_state(mock_db_pool):
    """Setup scanner state with mocked dependencies"""
    state.db_pool = mock_db_pool
    state.redis_client = AsyncMock()
    state.http_session = AsyncMock()
    yield state
    # Cleanup
    state.db_pool = None
    state.redis_client = None
    state.http_session = None

@pytest.fixture
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
            'catalyst_types': ['earnings', 'upgrade']
        },
        {
            'symbol': 'MSFT',
            'security_id': 2,
            'price': 300.0,
            'volume': 3000000,
            'change_percent': 1.5,
            'catalyst_strength': 0.6,
            'catalyst_count': 2,
            'catalyst_types': ['news']
        },
        {
            'symbol': 'GOOGL',
            'security_id': 3,
            'price': 120.0,
            'volume': 2000000,
            'change_percent': -1.0,
            'catalyst_strength': 0.4,
            'catalyst_count': 1,
            'catalyst_types': ['news']
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
        # Mock network error during quote fetching
        with patch('scanner_service.get_quote', 
                   side_effect=aiohttp.ClientError("API unreachable")):
            with patch('scanner_service.filter_by_catalysts',
                       side_effect=aiohttp.ClientError("Connection timeout")):
                
                with pytest.raises(HTTPException) as exc_info:
                    await scan_market()
                
                assert exc_info.value.status_code == 502
                assert 'Market data unavailable' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validation_error_raises_400(self, setup_state):
        """Test that validation errors raise HTTPException with 400 status"""
        # Mock validation error
        with patch('scanner_service.get_active_universe',
                   side_effect=ValueError("Invalid universe parameters")):
            
            with pytest.raises(HTTPException) as exc_info:
                await scan_market()
            
            assert exc_info.value.status_code == 400
            assert 'Invalid scan data' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_timeout_error_raises_504(self, setup_state):
        """Test that timeout errors raise HTTPException with 504 status"""
        # Mock timeout
        with patch('scanner_service.filter_by_catalysts',
                   side_effect=asyncio.TimeoutError()):
            
            with pytest.raises(HTTPException) as exc_info:
                await scan_market()
            
            assert exc_info.value.status_code == 504
            assert 'Scan timeout' in str(exc_info.value.detail)
            assert exc_info.value.detail['retry_after'] == 120
    
    @pytest.mark.asyncio
    async def test_missing_field_raises_500(self, setup_state):
        """Test that KeyError raises HTTPException with 500 status"""
        # Mock KeyError
        with patch('scanner_service.filter_by_catalysts',
                   side_effect=KeyError('required_field')):
            
            with pytest.raises(HTTPException) as exc_info:
                await scan_market()
            
            assert exc_info.value.status_code == 500
            assert 'Configuration error' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_runtime_error_raises_500(self, setup_state):
        """Test that RuntimeError raises HTTPException with 500 status"""
        # Mock runtime error (e.g., critical persistence failure)
        with patch('scanner_service.persist_scan_results',
                   side_effect=RuntimeError("Critical persistence failure")):
            # Need to mock other functions to get to persist_scan_results
            with patch('scanner_service.get_active_universe', return_value=['AAPL']):
                with patch('scanner_service.filter_by_catalysts', return_value=[]):
                    with patch('scanner_service.filter_by_technical', return_value=[]):
                        
                        with pytest.raises(HTTPException) as exc_info:
                            await scan_market()
                        
                        assert exc_info.value.status_code == 500
                        assert 'System error' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_unexpected_error_raises_500(self, setup_state):
        """Test that unexpected errors raise HTTPException with 500 status"""
        # Mock unexpected error
        with patch('scanner_service.get_active_universe',
                   side_effect=Exception("Something weird happened")):
            
            with pytest.raises(HTTPException) as exc_info:
                await scan_market()
            
            assert exc_info.value.status_code == 500
            assert 'Internal server error' in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_successful_scan_returns_proper_structure(self, setup_state, sample_candidates):
        """Test that successful scan returns expected data structure"""
        # Mock successful flow
        with patch('scanner_service.get_active_universe', return_value=['AAPL', 'MSFT']):
            with patch('scanner_service.filter_by_catalysts', return_value=sample_candidates):
                with patch('scanner_service.filter_by_technical', return_value=sample_candidates):
                    with patch('scanner_service.persist_scan_results', 
                               return_value={'success': 3, 'failed': 0, 'total': 3}):
                        
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
    async def test_tracks_validation_errors(self, sample_candidates, caplog):
        """Test that validation errors are tracked and logged"""
        # Create candidate with invalid data
        bad_candidate = {
            'symbol': 'BAD',
            'price': 'not_a_number',  # Invalid type
            'volume': 5000000,
            'change_percent': 2.0,
            'catalyst_strength': 0.8,
            'catalyst_count': 1,
            'catalyst_types': ['news']
        }
        
        candidates = sample_candidates + [bad_candidate]
        
        with caplog.at_level('WARNING'):
            result = await filter_by_technical(candidates)
        
        # Should have logged warning
        assert any('Invalid data' in record.message for record in caplog.records)
        # Should still return valid candidates
        assert len(result) >= len(sample_candidates)
    
    @pytest.mark.asyncio
    async def test_tracks_missing_fields(self, caplog):
        """Test that missing field errors are tracked"""
        # Candidate missing required fields
        incomplete_candidate = {
            'symbol': 'INCOMPLETE',
            'price': 100.0,
            # Missing volume, change_percent, catalyst_strength
        }
        
        with caplog.at_level('WARNING'):
            result = await filter_by_technical([incomplete_candidate])
        
        # Should log warning about missing field
        assert any('Missing field' in record.message or 'KeyError' in record.message 
                   for record in caplog.records)
    
    @pytest.mark.asyncio
    async def test_raises_if_all_candidates_fail(self, sample_candidates):
        """Test that ValueError is raised if ALL candidates fail"""
        # Create candidates that will all fail price filter
        bad_candidates = [
            {
                'symbol': 'TOO_CHEAP',
                'price': 1.0,  # Below min_price
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            },
            {
                'symbol': 'TOO_EXPENSIVE',
                'price': 10000.0,  # Above max_price
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
            assert 0 <= candidate['technical_score'] <= 1
            assert 0 <= candidate['composite_score'] <= 1
    
    @pytest.mark.asyncio
    async def test_filters_by_price_range(self, setup_state):
        """Test that price filters work correctly"""
        candidates = [
            {
                'symbol': 'CHEAP',
                'security_id': 1,
                'price': 3.0,  # Below min_price (5.0)
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            },
            {
                'symbol': 'VALID',
                'security_id': 2,
                'price': 50.0,  # Valid
                'volume': 5000000,
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            }
        ]
        
        result = await filter_by_technical(candidates)
        
        # Should only return VALID
        assert len(result) == 1
        assert result[0]['symbol'] == 'VALID'
    
    @pytest.mark.asyncio
    async def test_filters_by_volume(self, setup_state):
        """Test that volume filter works correctly"""
        candidates = [
            {
                'symbol': 'LOW_VOL',
                'security_id': 1,
                'price': 50.0,
                'volume': 500000,  # Below min_volume (1M)
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            },
            {
                'symbol': 'HIGH_VOL',
                'security_id': 2,
                'price': 50.0,
                'volume': 5000000,  # Valid
                'change_percent': 2.0,
                'catalyst_strength': 0.8,
                'catalyst_count': 1,
                'catalyst_types': ['news']
            }
        ]
        
        result = await filter_by_technical(candidates)
        
        # Should only return HIGH_VOL
        assert len(result) == 1
        assert result[0]['symbol'] == 'HIGH_VOL'
    
    @pytest.mark.asyncio
    async def test_sorts_by_composite_score(self, sample_candidates):
        """Test that results are sorted by composite score"""
        result = await filter_by_technical(sample_candidates)
        
        # Check that scores are in descending order
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
        # Mock successful database operations
        state.db_pool.fetchval = AsyncMock(return_value=1)  # time_id
        state.db_pool.execute = AsyncMock(return_value=None)
        
        result = await persist_scan_results("test_cycle", sample_candidates)
        
        assert result['success'] == len(sample_candidates)
        assert result['failed'] == 0
        assert result['total'] == len(sample_candidates)
        assert len(result['failed_symbols']) == 0
    
    @pytest.mark.asyncio
    async def test_tracks_fk_violations(self, setup_state, sample_candidates):
        """Test that FK violations are tracked separately"""
        state.db_pool.fetchval = AsyncMock(return_value=1)
        
        # First candidate succeeds, second has FK violation
        state.db_pool.execute = AsyncMock(
            side_effect=[
                None,  # Cycle creation
                None,  # First candidate success
                asyncpg.ForeignKeyViolationError("FK violation"),  # Second fails
                None   # Third succeeds
            ]
        )
        
        result = await persist_scan_results("test_cycle", sample_candidates)
        
        assert result['failed'] == 1
        assert len(result['error_details']['fk_violations']) == 1
        assert 'MSFT' in result['failed_symbols']
    
    @pytest.mark.asyncio
    async def test_tracks_duplicate_entries(self, setup_state, sample_candidates):
        """Test that duplicate entries are handled correctly"""
        state.db_pool.fetchval = AsyncMock(return_value=1)
        
        # Mock duplicate error (should count as success)
        state.db_pool.execute = AsyncMock(
            side_effect=[
                None,  # Cycle creation
                asyncpg.UniqueViolationError("Duplicate"),  # First is duplicate
                None,  # Second succeeds
                None   # Third succeeds
            ]
        )
        
        result = await persist_scan_results("test_cycle", sample_candidates)
        
        assert result['success'] == len(sample_candidates)
        assert result['failed'] == 0  # Duplicates don't count as failures
        assert len(result['error_details']['duplicates']) == 1
    
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
    
    @pytest.mark.asyncio
    async def test_does_not_raise_if_less_than_50_percent_fail(self, setup_state):
        """Test that partial failures (<50%) don't raise"""
        candidates = [
            {'symbol': f'SYM{i}', 'security_id': i, 'price': 50.0,
             'volume': 5000000, 'change_percent': 2.0,
             'catalyst_strength': 0.8, 'technical_score': 0.7,
             'composite_score': 0.75, 'catalyst_count': 1,
             'catalyst_types': ['news'], 'selected': False}
            for i in range(10)
        ]
        
        state.db_pool.fetchval = AsyncMock(return_value=1)
        
        # Fail 40% (4 out of 10) - should NOT raise
        state.db_pool.execute = AsyncMock(
            side_effect=[
                None,  # Cycle creation
                None, None, None, None, None, None,  # 6 succeed
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),
                asyncpg.PostgresError("Failed"),  # 4 fail
            ]
        )
        
        # Should not raise
        result = await persist_scan_results("test_cycle", candidates)
        
        assert result['success'] == 6
        assert result['failed'] == 4
    
    @pytest.mark.asyncio
    async def test_returns_detailed_error_summary(self, setup_state):
        """Test that error details are properly categorized"""
        candidates = [
            {'symbol': 'DUP', 'security_id': 1, 'price': 50.0,
             'volume': 5000000, 'change_percent': 2.0,
             'catalyst_strength': 0.8, 'technical_score': 0.7,
             'composite_score': 0.75, 'catalyst_count': 1,
             'catalyst_types': ['news'], 'selected': False},
            {'symbol': 'FK_FAIL', 'security_id': 2, 'price': 50.0,
             'volume': 5000000, 'change_percent': 2.0,
             'catalyst_strength': 0.8, 'technical_score': 0.7,
             'composite_score': 0.75, 'catalyst_count': 1,
             'catalyst_types': ['news'], 'selected': False},
            {'symbol': 'DB_ERROR', 'security_id': 3, 'price': 50.0,
             'volume': 5000000, 'change_percent': 2.0,
             'catalyst_strength': 0.8, 'technical_score': 0.7,
             'composite_score': 0.75, 'catalyst_count': 1,
             'catalyst_types': ['news'], 'selected': False}
        ]
        
        state.db_pool.fetchval = AsyncMock(return_value=1)
        state.db_pool.execute = AsyncMock(
            side_effect=[
                None,  # Cycle creation
                asyncpg.UniqueViolationError("Duplicate"),
                asyncpg.ForeignKeyViolationError("FK error"),
                asyncpg.PostgresError("Other error")
            ]
        )
        
        result = await persist_scan_results("test_cycle", candidates)
        
        assert 'DUP' in result['error_details']['duplicates']
        assert 'FK_FAIL' in result['error_details']['fk_violations']
        assert 'DB_ERROR' in result['error_details']['other_db_errors']

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
    
    @pytest.mark.asyncio
    async def test_get_time_id_handles_db_error(self, setup_state):
        """Test that get_time_id handles database errors properly"""
        state.db_pool.fetchval = AsyncMock(
            side_effect=asyncpg.PostgresError("DB error")
        )
        
        with pytest.raises(asyncpg.PostgresError):
            await get_time_id(datetime.utcnow())
    
    @pytest.mark.asyncio
    async def test_get_time_id_raises_if_none_returned(self, setup_state):
        """Test that ValueError raised if time_id is None"""
        state.db_pool.fetchval = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError) as exc_info:
            await get_time_id(datetime.utcnow())
        
        assert "Failed to get time_id" in str(exc_info.value)

# ============================================================================
# TEST SUITE #5: Logging and Observability
# ============================================================================

class TestLoggingAndObservability:
    """Tests for structured logging and error context"""
    
    @pytest.mark.asyncio
    async def test_logs_include_cycle_id(self, setup_state, caplog):
        """Test that all scan logs include cycle_id"""
        with patch('scanner_service.get_active_universe', return_value=[]):
            with caplog.at_level('INFO'):
                try:
                    await scan_market()
                except:
                    pass
        
        # Should have cycle_id in logs
        assert any('scan_' in record.message for record in caplog.records)
    
    @pytest.mark.asyncio
    async def test_logs_include_error_type(self, setup_state, caplog):
        """Test that error logs include error_type in extra"""
        state.db_pool.fetchval = AsyncMock(
            side_effect=asyncpg.PostgresError("DB error")
        )
        
        with caplog.at_level('ERROR'):
            with pytest.raises(asyncpg.PostgresError):
                await get_security_id("AAPL")
        
        # Should log the error
        assert any('Database error' in record.message for record in caplog.records)
    
    @pytest.mark.asyncio
    async def test_critical_errors_logged_as_critical(self, setup_state, caplog):
        """Test that critical errors use CRITICAL log level"""
        with patch('scanner_service.get_active_universe',
                   side_effect=Exception("Critical failure")):
            with caplog.at_level('CRITICAL'):
                with pytest.raises(HTTPException):
                    await scan_market()
        
        assert any(record.levelname == 'CRITICAL' for record in caplog.records)

# ============================================================================
# TEST SUITE #6: Integration Tests
# ============================================================================

class TestErrorHandlingIntegration:
    """Integration tests for complete error flows"""
    
    @pytest.mark.asyncio
    async def test_partial_failure_completes_successfully(self, setup_state):
        """Test that scan completes even with some failures"""
        # Mock mixed success/failure scenario
        good_candidates = [
            {'symbol': 'AAPL', 'security_id': 1, 'price': 150.0,
             'volume': 5000000, 'change_percent': 2.0,
             'catalyst_strength': 0.8, 'catalyst_count': 2,
             'catalyst_types': ['earnings']}
        ]
        
        bad_candidates = [
            {'symbol': 'BAD', 'price': 1.0,  # Will fail price filter
             'volume': 100, 'change_percent': 0.1,
             'catalyst_strength': 0.1, 'catalyst_count': 0,
             'catalyst_types': []}
        ]
        
        with patch('scanner_service.get_active_universe', return_value=['AAPL', 'BAD']):
            with patch('scanner_service.filter_by_catalysts', 
                       return_value=good_candidates + bad_candidates):
                with patch('scanner_service.persist_scan_results',
                           return_value={'success': 1, 'failed': 0, 'total': 1}):
                    
                    result = await scan_market()
                    
                    assert result['success'] is True
                    assert len(result['candidates']) > 0
    
    @pytest.mark.asyncio
    async def test_recovers_from_transient_errors(self, setup_state):
        """Test that system can recover from transient errors"""
        # First call fails, second succeeds
        call_count = [0]
        
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise asyncpg.PostgresError("Transient error")
            return None
        
        state.db_pool.execute = AsyncMock(side_effect=side_effect)
        
        # First call should fail
        with pytest.raises(HTTPException):
            await scan_market()
        
        # Reset mock for second call
        state.db_pool.execute = AsyncMock(return_value=None)
        state.db_pool.fetchval = AsyncMock(return_value=1)
        
        with patch('scanner_service.get_active_universe', return_value=['AAPL']):
            with patch('scanner_service.filter_by_catalysts', return_value=[]):
                with patch('scanner_service.filter_by_technical', return_value=[]):
                    # Second call should succeed (no candidates is ok)
                    result = await scan_market()
                    assert result['success'] is True

# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
