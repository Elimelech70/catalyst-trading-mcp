# Catalyst Trading System - Service Audit Playbook

**Name of Application**: Catalyst Trading System  
**Name of file**: service-audit-playbook.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-01  
**Purpose**: Comprehensive methodology and standards for rigorous service error handling audits

---

## Document Purpose

This playbook defines the **standard methodology** for auditing and fixing error handling across all Catalyst Trading System services. It captures:
- ✅ Lessons learned from initial audits
- ✅ Business rules and requirements
- ✅ Systematic audit methodology
- ✅ Error handling best practices
- ✅ Quality standards for production readiness

**Use this document as the foundation for every service audit.**

---

## Section 1: Core Principles & Philosophy

### 1.1 Fundamental Truths

**Truth #1: Lazy Error Handling Steals From Us**
- Silent failures make debugging impossible
- Hidden errors appear as "working" features
- Quick fixes create technical debt that compounds
- Shortcuts today = hours of debugging tomorrow

**Truth #2: This System Handles Real Money**
- Trading Service: Every hidden error is potential financial loss
- News Service: Missing catalysts = missing opportunities
- Scanner Service: Bad data = bad trades
- Risk Manager: Silent failures = unprotected positions

**Truth #3: Intelligence Quality Drives Everything**
```
News Intelligence → Scanner Selection → Analysis → Trading Decisions
```
If the first link is broken, everything downstream is garbage.

### 1.2 Zero Tolerance Policy

**We have ZERO tolerance for:**
- ❌ Bare `except:` catching everything including system exits
- ❌ `except Exception:` without specific handling
- ❌ Returning empty arrays/None/neutral hiding real failures
- ❌ Logging errors then continuing as if nothing happened
- ❌ Converting all errors to generic HTTP 500
- ❌ Silent failures in background tasks
- ❌ Swallowing exceptions without re-raising

### 1.3 What "Production Ready" Means

A service is production-ready when:
1. ✅ Every error path has specific handling
2. ✅ Failures are loud and visible
3. ✅ Logs include context and tracebacks (`exc_info=True`)
4. ✅ Invalid inputs rejected before processing
5. ✅ External API failures handled per API
6. ✅ Database errors never silently fail
7. ✅ Critical errors trigger alerts
8. ✅ Tests verify error paths work correctly

---

## Section 2: Strategic Service Priority

### 2.1 Service Development & Audit Order

**Development Workflow Priority**

Each service must be working and recording data to the database before moving to the next:

1. **News Service** (FIRST) - Intelligence foundation
   - Must be recording news articles to database
   - Sentiment analysis working
   - Catalyst detection operational
   - Verify database persistence before proceeding

2. **Orchestration Service** (SECOND) - System coordination
   - Coordinates all services via REST APIs
   - Provides Claude Desktop MCP interface
   - Workflow management operational
   - Can communicate with News service

3. **Dashboard** (THIRD) - System visualization
   - Visualizes services through Orchestration MCP
   - Real-time monitoring of News service
   - Service health display
   - Foundation for monitoring all future services

4. **Scanner Service** (FOURTH) - Market scanning using news intelligence
   - Uses news data to identify securities
   - Records scan results to database
   - Candidate selection working
   - Visible in dashboard

5. **Pattern Service** (FIFTH) - Chart pattern detection
   - Analyzes securities identified by Scanner
   - Records pattern analysis to database
   - Pattern detection operational
   - Visible in dashboard

6. **Technical Analysis Service** (SIXTH) - Technical indicators
   - Adds technical analysis to candidates
   - Records indicator data to database
   - Multi-timeframe analysis working
   - Visible in dashboard

7. **Risk Manager Service** (SEVENTH) - Position sizing and risk validation
   - Validates trade risk before execution
   - Records risk metrics to database
   - Risk calculations operational
   - Visible in dashboard

8. **Trading Service** (EIGHTH) - Order execution
   - Executes validated trades
   - Records orders and positions to database
   - Paper trading functional
   - Visible in dashboard

9. **Reporting Service** (NINTH) - Performance analytics
   - Analyzes trading performance
   - Generates reports from database
   - P&L tracking operational
   - Visible in dashboard

**Key Principle**: Each service must demonstrate working database persistence before moving to next service. This ensures data flows correctly through the system.

**Development Strategy**: By building Orchestration and Dashboard early (positions 2-3), we gain full visibility and monitoring capability for all subsequent services. This makes development and debugging significantly easier.

### 2.2 Critical Business Rules

**Rule #1: Failed Stop Loss = Auto-Close Position**
- If stop loss order cannot be placed, immediately close position
- Position without downside protection is unacceptable risk
- Log as CRITICAL and send immediate alert
- Emergency procedure if auto-close fails

**Rule #2: News Intelligence Must Be Reliable**
- Missing news catalysts = blind trading
- Sentiment analysis failures must be visible
- API failures must not silently return empty
- Scanner must know when news intelligence unavailable

**Rule #3: Database Failures Are Never Silent**
- Orders placed but not recorded = reconciliation nightmare
- News not persisted = no historical analysis
- All database errors must be logged and visible
- Consider database failures as service degradation

**Rule #4: Error Simulation Testing Required**
- Every error path must have a test
- Tests must verify errors surface correctly
- No deploying fixes without test coverage
- Mock API failures, timeouts, bad data

---

## Section 3: Systematic Audit Methodology

### 3.1 Pre-Audit Preparation

**Step 1: Understand Service Purpose**
- What is this service's core responsibility?
- What other services depend on it?
- What happens if this service fails?
- What data does it provide to downstream services?

**Step 2: Review Design Documentation**
- Find service specification in design docs
- Identify required functionality
- Note version expectations
- Review database schema dependencies

**Step 3: Map Critical Paths**
- Identify main API endpoints
- Map external dependencies (APIs, databases)
- List background tasks
- Note data persistence requirements

### 3.2 Audit Execution Process

**Phase 1: Discovery (30 minutes)**
1. Pull complete service file(s)
2. Count total try/catch blocks
3. Identify external API calls
4. Note database operations
5. List background tasks

**Phase 2: Analysis (2-4 hours per service)**

For each try/catch block, document:

```markdown
## Issue #N: [Description] 🔴/🟡/🟢 [Severity]

**Location**: [Function name, line numbers]

**Current Code**:
```python
[Actual code with problems highlighted]
```

**Why This Is Critical/High/Medium**:
[Explain real-world consequences]

**Real Consequences**:
- What happens when this error occurs?
- How does it affect downstream services?
- What does the user/system see?
- What should happen instead?

**The Fix**:
```python
[Complete corrected code with comments]
```

**Key Improvements**:
1. [Specific improvement]
2. [Specific improvement]
3. [...]
```

**Phase 3: Categorization (30 minutes)**

Classify each issue:
- 🔴 **CRITICAL**: Service breaking, financial risk, data loss
- 🟡 **HIGH**: Functionality degraded, debugging difficult
- 🟢 **MEDIUM**: Poor practice, maintainability issue

**Phase 4: Questions & Decisions (15 minutes)**

List strategic questions that need answers:
1. Configuration decisions (fail vs degrade gracefully)
2. Retry strategies
3. Alerting priorities
4. Recovery procedures

### 3.3 Documentation Standards

**Every audit document must include:**

1. **Header Section**
   - Service name and version
   - Priority level (why this service matters)
   - Lines of code, try/catch count
   - Critical dependencies

2. **Issues Section**
   - Each issue numbered sequentially
   - Severity clearly marked
   - Current code shown
   - Fix provided
   - Consequences explained

3. **Summary Section**
   - Count of issues by severity
   - Estimated effort to fix
   - Production deployment blockers

4. **Strategic Questions**
   - Configuration decisions needed
   - Business rule clarifications
   - Alerting strategy
   - Recovery procedures

5. **Milestone Integration**
   - Link to overall milestone tracking
   - Update priority if needed
   - Mark completion criteria

---

## Section 4: Error Handling Patterns

### 4.1 The Anti-Patterns (What NOT To Do)

**Anti-Pattern #1: The Silent Failure**
```python
# ❌ BAD
try:
    result = do_something()
    return result
except:
    return []  # Hides ALL errors
```

**Anti-Pattern #2: The Error Eraser**
```python
# ❌ BAD
try:
    process_data()
except Exception as e:
    logger.error(f"Error: {e}")  # Logs but loses traceback
    return {"success": False}    # Appears handled but isn't
```

**Anti-Pattern #3: The Everything Catcher**
```python
# ❌ BAD
try:
    api_call()
except Exception as e:  # Too broad!
    raise HTTPException(500, str(e))  # Generic 500
```

**Anti-Pattern #4: The Pass Pretender**
```python
# ❌ BAD
try:
    important_operation()
except:
    pass  # Silently swallows everything
```

**Anti-Pattern #5: The Default Liar**
```python
# ❌ BAD
try:
    sentiment = analyze_sentiment(text)
    return sentiment
except:
    return "neutral"  # Lies about analysis success
```

### 4.2 The Correct Patterns (What TO Do)

**Pattern #1: Validate Before Try**
```python
# ✅ GOOD
def process_order(symbol: str, quantity: int):
    # Validate BEFORE try block
    if not symbol or len(symbol) > 10:
        raise ValueError(f"Invalid symbol: {symbol}")
    
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive: {quantity}")
    
    # Now try the operation
    try:
        result = execute_order(symbol, quantity)
        return result
    except SpecificError as e:
        # Handle only expected errors
        logger.error(f"Order execution failed: {e}", exc_info=True)
        raise HTTPException(400, f"Order failed: {str(e)}")
```

**Pattern #2: Catch Specific Exceptions**
```python
# ✅ GOOD
try:
    data = await fetch_api(symbol)
    return data
    
except aiohttp.ClientError as e:
    # Network/connection errors
    logger.error(f"API connection failed: {e}")
    raise HTTPException(503, "Service temporarily unavailable")
    
except asyncio.TimeoutError:
    # Timeout errors
    logger.warning(f"API timeout for {symbol}")
    raise HTTPException(504, "Request timeout")
    
except ValueError as e:
    # Data parsing errors
    logger.error(f"Invalid API response: {e}")
    raise HTTPException(502, "Invalid data from external service")

# No generic Exception catch - let unexpected errors crash!
```

**Pattern #3: Preserve Context**
```python
# ✅ GOOD
try:
    result = complex_operation(data)
    return result
except KeyError as e:
    logger.error(
        f"Missing required field in data: {e}",
        exc_info=True,  # ← CRITICAL: Preserves traceback
        extra={
            "data_keys": list(data.keys()),
            "missing_key": str(e)
        }
    )
    raise HTTPException(400, f"Missing required field: {e}")
```

**Pattern #4: Explicit Over Implicit**
```python
# ✅ GOOD
def analyze_sentiment(text: str) -> Dict:
    if not text or not text.strip():
        raise ValueError("Empty text provided")
    
    try:
        blob = TextBlob(text)
        return {
            "sentiment": calculate_sentiment(blob),
            "score": blob.sentiment.polarity,
            "success": True  # ← Explicit success flag
        }
    except UnicodeDecodeError as e:
        raise ValueError(f"Text encoding error: {e}")
    # Don't catch generic Exception
```

**Pattern #5: Fail Fast, Fail Loud**
```python
# ✅ GOOD
async def store_critical_data(data):
    if not state.db_pool:
        logger.critical("Database not initialized - cannot store data")
        raise RuntimeError("Database unavailable")
    
    try:
        async with state.db_pool.acquire() as conn:
            await conn.execute(...)
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True)
        raise  # Don't hide database errors!
```

### 4.3 API-Specific Error Handling

**External API Template**:
```python
async def fetch_from_external_api(symbol: str) -> List[Dict]:
    """Fetch data with proper API error handling
    
    Raises:
        ValueError: Invalid inputs
        HTTPException: API errors (401, 429, 500)
        TimeoutError: Request timeout
    """
    
    # Validate inputs FIRST
    if not symbol:
        raise ValueError("Symbol required")
    
    # Check configuration
    if not state.api_key:
        logger.critical("API key not configured")
        raise ValueError("Service misconfigured - no API key")
    
    try:
        async with state.http_session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            
            # Handle specific status codes
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"API returned {len(data)} items")
                return data
                
            elif resp.status == 401:
                logger.critical("API authentication failed")
                raise HTTPException(503, "Service misconfigured")
                
            elif resp.status == 429:
                logger.error("API rate limit exceeded")
                raise HTTPException(429, "Rate limit exceeded")
                
            elif resp.status >= 500:
                logger.error(f"API server error: {resp.status}")
                raise HTTPException(502, f"External service error")
                
            else:
                logger.error(f"Unexpected status: {resp.status}")
                raise HTTPException(502, f"Unexpected response")
    
    except asyncio.TimeoutError:
        logger.error("API timeout")
        raise TimeoutError("Request timeout")
        
    except aiohttp.ClientError as e:
        logger.error(f"Connection error: {e}")
        raise HTTPException(503, "Connection failed")
```

**Database Operation Template**:
```python
async def persist_to_database(data: List[Item]) -> None:
    """Store data with proper database error handling
    
    Raises:
        RuntimeError: Database not available
        asyncpg.PostgresError: Database errors
    """
    
    if not data:
        return  # Nothing to store
    
    if not state.db_pool:
        logger.critical("Database pool not initialized")
        raise RuntimeError("Database unavailable")
    
    try:
        async with state.db_pool.acquire() as conn:
            for item in data:
                try:
                    await conn.execute("""
                        INSERT INTO table (...)
                        VALUES (...)
                        ON CONFLICT DO NOTHING
                    """, ...)
                except asyncpg.UniqueViolationError:
                    # Duplicate is OK - skip
                    logger.debug(f"Duplicate item skipped")
                    
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True)
        raise  # Never hide database errors!
```

---

## Section 5: Milestone & Progress Tracking

### 5.1 Living Document Approach

Each service audit becomes part of the master tracking document with:
- Current status
- Priority level
- Completion criteria
- Dependencies
- Estimated effort

### 5.2 Review Cadence

**After Each Service Audit**:
1. Update overall progress metrics
2. Reassess priorities based on findings
3. Identify cross-service patterns
4. Update this playbook with new learnings

**After Each Service Fix**:
1. Mark milestone complete
2. Review production logs for new error patterns
3. Update error handling standards if needed
4. Document lessons learned

### 5.3 Production Readiness Gates

**No service deploys to production until**:
1. ✅ Complete error handling audit done
2. ✅ All CRITICAL issues fixed
3. ✅ All HIGH priority issues fixed
4. ✅ Error simulation tests written and passing
5. ✅ Logging includes proper context
6. ✅ Alerting configured for critical errors
7. ✅ Documentation updated
8. ✅ Code review completed

---

## Section 6: Quality Checklist

### 6.1 Code Review Checklist

For every service, verify:

**Error Handling**:
- [ ] No bare `except:` statements
- [ ] No `except Exception:` without re-raise
- [ ] All external API calls have specific error handling
- [ ] Database operations never silently fail
- [ ] Background tasks have error handling
- [ ] Invalid inputs rejected before processing

**Logging**:
- [ ] Error logs include `exc_info=True`
- [ ] Logs include relevant context
- [ ] Critical errors marked as CRITICAL
- [ ] Debug logs for troubleshooting
- [ ] No sensitive data in logs

**Validation**:
- [ ] All inputs validated before processing
- [ ] Validation errors raise specific exceptions
- [ ] Error messages are helpful for debugging
- [ ] HTTP status codes are appropriate

**Testing**:
- [ ] Tests for happy path
- [ ] Tests for each error path
- [ ] Tests verify errors surface correctly
- [ ] Tests verify error messages
- [ ] Integration tests cover failure scenarios

**Documentation**:
- [ ] Error handling approach documented
- [ ] Known failure modes documented
- [ ] Recovery procedures documented
- [ ] Alerting strategy defined

### 6.2 Service-Specific Considerations

**Trading Service**:
- Order execution errors must be specific (buying power, invalid symbol, etc.)
- Bracket order failures must trigger position close
- Paper trading must use real market prices
- All financial operations logged comprehensively

**News Service**:
- Sentiment analysis failures must not return neutral
- API failures must not return empty
- Source-specific error handling required
- Catalyst detection errors must be visible

**Scanner Service**:
- Data fetch failures must be visible
- Empty results must distinguish between "no data" and "error"
- Symbol blacklist failures must not crash service
- Scoring errors must be logged with context

**Risk Manager Service**:
- Risk calculation errors cannot be hidden
- Position validation failures must be explicit
- Daily limit checks must fail loudly
- Emergency stop must override all errors

---

## Section 7: Common Questions & Answers

### Q1: When should we fail fast vs degrade gracefully?

**Fail Fast When**:
- Critical configuration missing (API keys, database)
- Core functionality cannot work
- Financial risk if we continue
- Data integrity at risk

**Degrade Gracefully When**:
- Optional features fail
- Secondary data sources unavailable
- Non-critical background tasks fail
- Can provide partial functionality safely

### Q2: How do we handle third-party API rate limits?

**Strategy**:
1. Track rate limit usage
2. Implement exponential backoff
3. Use multiple sources when available
4. Alert when rate limits approached
5. Have fallback data sources
6. Never silently return empty

### Q3: What gets logged as CRITICAL vs ERROR vs WARNING?

**CRITICAL**:
- Service cannot function (database down, API key invalid)
- Financial risk (position without stop loss)
- Data loss risk (persistence failures)
- Security issues (authentication failures)

**ERROR**:
- Operation failed but service continues
- Expected errors that need investigation
- External API failures
- Data quality issues

**WARNING**:
- Degraded performance
- Retrying operations
- Using fallback data
- Rate limit approaching

### Q4: When do we re-raise vs handle exceptions?

**Re-raise When**:
- You don't know how to handle it
- Caller needs to know about the failure
- It's a bug that needs fixing
- Service cannot continue safely

**Handle When**:
- You can recover gracefully
- You can provide alternative data
- You can retry successfully
- Error is expected and managed

---

## Section 8: Success Metrics

### 8.1 Code Quality Metrics

**Target Metrics**:
- Zero bare `except:` statements
- Zero `except Exception:` without re-raise
- 100% of external API calls have specific error handling
- 100% of database operations have error handling
- All critical paths have error simulation tests

### 8.2 Operational Metrics

**Track These**:
- Error rate per service per hour
- Error type distribution
- Mean time to detect (MTTD)
- Mean time to resolve (MTTR)
- False positive alert rate

### 8.3 Before/After Comparison

**Before Rigorous Error Handling**:
- Services appear working but silently fail
- Debugging takes hours due to missing context
- Production issues discovered by users
- High uncertainty about system health

**After Rigorous Error Handling**:
- Failures are loud and visible
- Debugging is fast with full context
- Issues caught before production
- High confidence in system health

---

## Section 9: Using This Playbook

### 9.1 For Service Audits

**Direction Template**:
```
Audit [Service Name] using the Service Audit Playbook methodology.

Priority: [Critical/High/Medium] - [Why this service matters]

Key Focus Areas:
- [Specific area 1]
- [Specific area 2]
- [Specific area 3]

Critical Business Rules:
- [Relevant rule from playbook]

Strategic Questions:
- [Question 1]
- [Question 2]
```

### 9.2 For Service Fixes

**Direction Template**:
```
Fix [Issue #N] from [Service Name] audit following the playbook patterns.

Severity: [Critical/High/Medium]
Estimated Effort: [X hours]

Apply Pattern: [Specific pattern from Section 4]

Test Coverage Required:
- [Test case 1]
- [Test case 2]

Documentation Required:
- [What needs documenting]
```

### 9.3 For Progress Reviews

**Review Template**:
```
Review progress on [Service Name] using playbook standards.

Completion Criteria:
- [Criterion 1 from Section 5.3]
- [Criterion 2]
- ...

Assess:
- Are all CRITICAL issues fixed?
- Are tests comprehensive?
- Is documentation complete?
- Ready for production?
```

---

## Section 10: Evolution & Improvement

### 10.1 Playbook Updates

This playbook evolves based on:
- New error patterns discovered
- Lessons from production
- Team feedback
- New technology/tools
- Regulatory requirements

**Update Process**:
1. Identify improvement needed
2. Discuss with team
3. Update playbook
4. Apply retroactively if critical
5. Document change in revision history

### 10.2 Continuous Learning

After each service audit, ask:
- What new error pattern did we discover?
- What fix was particularly effective?
- What should be added to the playbook?
- What anti-pattern is common across services?

---

## Appendix A: Quick Reference

### Error Handling Severity Guide

🔴 **CRITICAL**: Fix immediately
- Silent failures in financial operations
- Missing stop loss on positions
- Sentiment returns neutral hiding errors
- Database persistence failures
- API key failures returning empty

🟡 **HIGH**: Fix soon
- Generic error messages
- Missing error context in logs
- Partial functionality failures
- Degraded user experience

🟢 **MEDIUM**: Improve when possible
- Logging without exc_info
- Could be more specific
- Better error messages
- Code maintainability

### Common Fix Patterns

1. **Validate → Try → Specific Catch → Log → Raise**
2. **Check Config → Fail Fast if Missing**
3. **API Call → Status-Specific Handling → Timeout Handling**
4. **Database Op → Never Catch Generic Exception**
5. **Background Task → Log CRITICAL on Failure**

### Testing Requirements

- Happy path test
- Each error path test
- Invalid input test
- Timeout simulation test
- API failure simulation test
- Database failure test

---

## Appendix B: Revision History

**v1.0.0 (2025-10-01)**: Initial playbook creation
- Documented lessons from Trading and News service audits
- Established core principles and methodology
- Created error handling patterns library
- Defined production readiness gates
- Set up milestone tracking framework

---

**END OF PLAYBOOK**

This living document guides all future service audits and improvements.
