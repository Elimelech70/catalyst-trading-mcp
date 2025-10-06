# Catalyst Trading System - Service Audit Playbook v2.0

**Version**: 2.0.0  
**Last Updated**: 2025-10-04  
**Purpose**: Complete methodology for service development with proper database foundation

---

## 🚨 CRITICAL CHANGE IN v2.0

**Database Schema MUST be fixed BEFORE auditing services!**

The old playbook had us fixing services that write to a broken, denormalized schema. This creates:
- ❌ Data duplication bugs
- ❌ Inconsistent storage patterns  
- ❌ Poor ML training data
- ❌ Need to refactor services again later

**New Approach**: Fix database schema FIRST, then audit/fix services to use it properly.

---

## Section 1: Core Principles (Unchanged)

### 1.1 Fundamental Truths

**Truth #1: Lazy Error Handling Steals From Us**
- Silent failures make debugging impossible
- Quick fixes create technical debt that compounds

**Truth #2: This System Handles Real Money**
- Every hidden error is potential financial loss

**Truth #3: Intelligence Quality Drives Everything**
```
News Intelligence → Scanner Selection → Analysis → Trading Decisions
```

**Truth #4: Poor Database Design = Poor ML Models** ⭐ NEW
- Denormalized data = duplicated, inconsistent features
- Proper normalization = clean ML training data
- Schema defines data quality at the source

### 1.2 Zero Tolerance Policy (Unchanged)

❌ Bare `except:` catching everything  
❌ `except Exception:` without specific handling  
❌ Returning empty arrays hiding failures  
❌ Silent database persistence failures  
❌ **Storing duplicate data across tables** ⭐ NEW

---

## Section 2: UPDATED Service Development Order

### **STEP 0: DATABASE SCHEMA FOUNDATION** ⭐ NEW - DO THIS FIRST!

**Before ANY service work, normalize the database:**

#### 0.1 Create Normalized Schema

**Tables to Create:**
```sql
1. securities (master entity - single source of truth)
2. trading_history (OHLCV time series)
3. news_sentiment (news with impact tracking)
4. technical_indicators (calculated indicators)
5. security_fundamentals (quarterly financials)
6. security_statistics (daily stats)
```

**Action Items:**
- [ ] Run `normalized_securities_schema.sql`
- [ ] Verify all tables created
- [ ] Create indexes
- [ ] Set up foreign keys
- [ ] Create ML feature views

#### 0.2 Migration Strategy

**Migrate existing data:**
```sql
-- Extract securities from scan_results
INSERT INTO securities (symbol, sector, company_name)
SELECT DISTINCT symbol, metadata->>'sector', metadata->>'company_name'
FROM scan_results;

-- Migrate news articles
INSERT INTO news_sentiment (security_id, headline, ...)
SELECT s.security_id, na.title, ...
FROM news_articles na
JOIN securities s ON s.symbol = na.symbol;
```

**Action Items:**
- [ ] Backfill securities table from existing data
- [ ] Migrate news_articles → news_sentiment
- [ ] Migrate historical scan data → trading_history
- [ ] Verify data integrity with JOIN queries

#### 0.3 Validation Queries

**Run these to verify schema:**
```sql
-- Check for orphaned records
SELECT COUNT(*) FROM news_sentiment ns
LEFT JOIN securities s ON ns.security_id = s.security_id
WHERE s.security_id IS NULL;

-- Verify feature view works
SELECT * FROM v_ml_features LIMIT 10;

-- Check data completeness
SELECT 
    s.symbol,
    COUNT(DISTINCT th.id) as price_records,
    COUNT(DISTINCT ns.news_id) as news_records,
    COUNT(DISTINCT ti.indicator_id) as indicator_records
FROM securities s
LEFT JOIN trading_history th USING (security_id)
LEFT JOIN news_sentiment ns USING (security_id)
LEFT JOIN technical_indicators ti USING (security_id)
GROUP BY s.symbol;
```

**Success Criteria:**
- ✅ All tables exist with proper indexes
- ✅ Foreign keys enforce referential integrity
- ✅ Existing data migrated successfully
- ✅ No orphaned records
- ✅ ML feature views return data

**⚠️ DO NOT PROCEED to Step 1 until Step 0 is complete!**

---

### **STEP 1: News Service** (Intelligence Foundation)

**Prerequisites:**
- ✅ Step 0 complete (normalized schema exists)

**What to Fix:**
1. **Error Handling Audit** (from v1.0 playbook)
   - Fix try/catch lazy coding
   - Specific exception handling
   - Proper logging with context

2. **Database Integration** ⭐ NEW
   - Update to use `securities` table
   - Store news in `news_sentiment` table
   - Use `security_id` foreign keys (not symbol strings)
   - Track price impact fields (price_impact_1h, etc.)

**Code Changes Required:**
```python
# OLD (v5.0.2):
await db.execute("""
    INSERT INTO news_articles (symbol, headline, sentiment_score, ...)
    VALUES ($1, $2, $3, ...)
""", symbol, headline, score, ...)

# NEW (v2.0):
# Step 1: Get security_id
security_id = await db.fetchval(
    "SELECT security_id FROM securities WHERE symbol = $1", 
    symbol
)

# Step 2: Store with FK
await db.execute("""
    INSERT INTO news_sentiment (
        security_id, headline, sentiment_score,
        sentiment_label, catalyst_type, catalyst_strength
    ) VALUES ($1, $2, $3, $4, $5, $6)
""", security_id, headline, score, label, catalyst_type, strength)
```

**Verification:**
- [ ] News stored with `security_id` FK
- [ ] No symbol duplication (uses securities table)
- [ ] Sentiment labels calculated correctly
- [ ] Catalyst strength tracked
- [ ] Error handling audited per v1.0 playbook

---

### **STEP 2: Orchestration Service** (System Coordination)

**Prerequisites:**
- ✅ Step 0 complete (schema normalized)
- ✅ Step 1 complete (News service writes to normalized schema)

**What to Fix:**
1. Error handling audit
2. Database queries use JOINs on `security_id`
3. No duplicate symbol lookups

**Code Pattern:**
```python
# Query news with security info (via JOIN)
news_with_security = await db.fetch("""
    SELECT 
        s.symbol, s.company_name, s.sector,
        ns.headline, ns.sentiment_score, ns.catalyst_type
    FROM news_sentiment ns
    JOIN securities s USING (security_id)
    WHERE ns.published_at > $1
    ORDER BY ns.published_at DESC
""", cutoff_time)
```

---

### **STEP 3: Dashboard** (Visibility)

**Prerequisites:**
- ✅ Steps 0-2 complete

**Queries Dashboard Uses:**
```sql
-- Use ML feature view for complete data
SELECT * FROM v_ml_features
WHERE symbol = 'AAPL'
ORDER BY timestamp DESC;

-- Latest securities with all metrics
SELECT * FROM v_securities_latest
WHERE is_active = TRUE
ORDER BY latest_news_date DESC;
```

---

### **STEP 4: Scanner Service** (Market Scanning)

**Prerequisites:**
- ✅ Steps 0-3 complete

**Database Integration:**
```python
# Ensure security exists before scanning
async def scan_symbol(symbol: str):
    # Step 1: Ensure in securities table
    security_id = await ensure_security_exists(symbol)
    
    # Step 2: Store OHLCV in trading_history
    await db.execute("""
        INSERT INTO trading_history (
            security_id, timestamp, timeframe,
            open, high, low, close, volume
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    """, security_id, timestamp, '5min', o, h, l, c, v)
    
    # Step 3: Store scan results (references security_id)
    await db.execute("""
        INSERT INTO scan_results (
            cycle_id, security_id, momentum_score, ...
        ) VALUES ($1, $2, $3, ...)
    """, cycle_id, security_id, score, ...)
```

**No More:**
- ❌ Storing sector in scan_results.metadata (use FK to securities)
- ❌ Calling yfinance every scan (check securities table first)

---

### **STEP 5-9: Remaining Services**

**Pattern for ALL services:**

1. ✅ **Check** if security exists in `securities` table
2. ✅ **Get** `security_id` (not symbol string)
3. ✅ **Store** data with `security_id` FK
4. ✅ **Query** using JOINs on `security_id`
5. ✅ **Never duplicate** data from `securities` table

---

## Section 3: Database-First Development Rules ⭐ NEW

### Rule #1: Always Use security_id

**Don't:**
```python
# BAD - Using symbol everywhere
await db.execute(
    "INSERT INTO positions (symbol, ...) VALUES ($1, ...)",
    symbol, ...
)
```

**Do:**
```python
# GOOD - Using security_id FK
security_id = await get_or_create_security(symbol)
await db.execute(
    "INSERT INTO positions (security_id, ...) VALUES ($1, ...)",
    security_id, ...
)
```

### Rule #2: Never Duplicate Master Data

**Don't:**
```python
# BAD - Storing sector in multiple places
await db.execute(
    "INSERT INTO scan_results (symbol, sector, ...) VALUES ($1, $2, ...)",
    symbol, sector, ...
)
```

**Do:**
```python
# GOOD - Sector lives in securities table only
await db.execute(
    "INSERT INTO scan_results (security_id, ...) VALUES ($1, ...)",
    security_id, ...
)

# Query with JOIN to get sector
results = await db.fetch("""
    SELECT sr.*, s.sector
    FROM scan_results sr
    JOIN securities s USING (security_id)
""")
```

### Rule #3: Track Impact for ML

**Always populate impact tracking fields:**
```python
# When storing news, track price impact
await db.execute("""
    INSERT INTO news_sentiment (
        security_id, headline, published_at,
        price_impact_1h,  -- ML feature!
        price_impact_4h,  -- ML feature!
        price_impact_1d   -- ML feature!
    ) VALUES ($1, $2, $3, $4, $5, $6)
""", ...)
```

**Background job to calculate impact:**
```python
async def update_news_price_impact():
    """Calculate price change after news events"""
    
    news_events = await db.fetch("""
        SELECT news_id, security_id, published_at
        FROM news_sentiment
        WHERE price_impact_1h IS NULL
        AND published_at < NOW() - INTERVAL '1 hour'
    """)
    
    for event in news_events:
        # Get price 1 hour after
        price_after = await db.fetchval("""
            SELECT close FROM trading_history
            WHERE security_id = $1
            AND timestamp > $2
            AND timeframe = '1hour'
            ORDER BY timestamp ASC LIMIT 1
        """, event['security_id'], event['published_at'])
        
        # Calculate impact
        impact = calculate_impact(price_before, price_after)
        
        # Update news record
        await db.execute("""
            UPDATE news_sentiment
            SET price_impact_1h = $1
            WHERE news_id = $2
        """, impact, event['news_id'])
```

---

## Section 4: Migration Checklist

### Phase 1: Database (Week 1)
- [ ] Create normalized schema
- [ ] Migrate existing data
- [ ] Verify data integrity
- [ ] Create feature views
- [ ] Test JOIN queries

### Phase 2: Update Services (Weeks 2-4)
- [ ] News Service → uses news_sentiment table
- [ ] Scanner Service → uses trading_history table
- [ ] All services → use security_id FKs
- [ ] Remove duplicate data storage
- [ ] Update all queries to use JOINs

### Phase 3: ML Pipeline (Week 5)
- [ ] Extract features via v_ml_features view
- [ ] Train models on normalized data
- [ ] Validate impact tracking works
- [ ] Test correlation queries (news → price)

---

## Section 5: Success Criteria

### Database Schema (Step 0)
- ✅ All 6 normalized tables exist
- ✅ Foreign keys enforce relationships
- ✅ Indexes on all FK columns
- ✅ Feature views return data
- ✅ Migration complete, no data loss

### Each Service
- ✅ Error handling audit complete (v1.0 playbook)
- ✅ Uses security_id FKs (not symbol strings)
- ✅ No duplicate data storage
- ✅ Queries use JOINs properly
- ✅ Database persistence verified
- ✅ Tests cover schema integration

### System-Wide
- ✅ Clean feature extraction for ML
- ✅ News → price impact correlation works
- ✅ No denormalized data anywhere
- ✅ All services writing to correct tables

---

## Appendix: Key Changes from v1.0

**What's New in v2.0:**
1. ⭐ **Step 0 added**: Database schema normalization FIRST
2. ⭐ **Truth #4 added**: Database design affects ML quality
3. ⭐ **Section 3 added**: Database-first development rules
4. ⭐ **Migration checklist**: Phased approach to updates
5. ⭐ **Impact tracking**: ML-ready price impact fields

**Why This Order Matters:**
- Fixing services before fixing schema = wasted work
- Schema defines data quality at the source
- Normalized data = better ML models
- One migration, then build on solid foundation

---

## Quick Reference Card

### Before Starting ANY Service Work:
```
1. ✅ Is Step 0 complete? (normalized schema exists)
2. ✅ Can I query v_ml_features successfully?
3. ✅ Are foreign keys enforced?
4. ✅ Is migration data verified?

If NO to any → STOP, finish Step 0 first!
```

### When Updating a Service:
```
1. Get security_id (not symbol)
2. Store with FK reference
3. Query with JOINs
4. Never duplicate master data
5. Follow v1.0 error handling rules
```

### Database Pattern:
```python
# Always:
security_id = await ensure_security_exists(symbol)

# Store:
INSERT INTO table (security_id, ...) VALUES ($1, ...)

# Query:
SELECT * FROM table t
JOIN securities s USING (security_id)
WHERE ...
```

---

**END OF PLAYBOOK v2.0**

Database normalization is not optional - it's the foundation everything else builds on.