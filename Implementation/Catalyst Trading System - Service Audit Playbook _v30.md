# Catalyst Trading System - Service Audit Playbook v3.0

**Version**: 3.0.0  
**Last Updated**: 2025-10-06  
**Purpose**: Complete service migration to normalized schema v5.0 with adaptive time-series

---

## 🚨 CRITICAL UPDATE: v3.0 vs v2.0

**What's New in v3.0:**
1. ⭐ **Complete v5.0 schema requirements** - All tables, indexes, views defined
2. ⭐ **Adaptive time-series storage** - Volatility-based sampling frequency
3. ⭐ **Detailed gap analysis per service** - Exactly what to change in each file
4. ⭐ **Time dimension table** - Time as its own entity with FKs
5. ⭐ **Comprehensive testing strategy** - Unit, integration, data integrity tests
6. ⭐ **4-week migration timeline** - Phased approach with priorities

**v2.0 said**: "Normalize the database"  
**v3.0 says**: "Here's EXACTLY how to normalize, test, and migrate every service"

---

## Quick Reference Card

### Before Starting ANY Service Work:
```
1. ✅ Is normalized schema v5.0 deployed? (not v4.2!)
2. ✅ Do helper functions exist? (get_or_create_security, get_or_create_time)
3. ✅ Are dimension tables populated? (securities, sectors, time_dimension)
4. ✅ Do materialized views work? (v_ml_features, v_securities_latest)
5. ✅ Is adaptive sampling configured? (active_securities, volatility_regimes)

If NO to any → STOP, deploy v5.0 schema first!
```

### When Updating ANY Service:
```
1. Get security_id (NOT symbol VARCHAR)
2. Get time_id for time-series data (NOT duplicate timestamps)
3. Store with FK references (NOT raw data)
4. Query with JOINs (NOT symbol strings)
5. Never duplicate master data
6. Follow v1.0 error handling rules (no silent failures)
7. Add tests for normalization (no orphans)
```

### Normalized Database Pattern:
```python
# ALWAYS use this pattern:

# 1. Get FKs
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", symbol
)
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", timestamp
)

# 2. Store with FKs
INSERT INTO table (security_id, time_id, ...) 
VALUES ($1, $2, ...)

# 3. Query with JOINs
SELECT t.*, s.symbol, s.company_name, sec.sector_name
FROM table t
JOIN securities s ON s.security_id = t.security_id
JOIN sectors sec ON sec.sector_id = s.sector_id
WHERE s.symbol = $1
```

---

## Section 1: Core Principles

### 1.1 Fundamental Truths

**Truth #1.1: Lazy Error Handling Steals From Us**
- Silent failures make debugging impossible
- Quick fixes create technical debt that compounds

**Truth #1.2: Don't make changes unless conforms to design documents in git

**Truth #1.3: If new idea that does not conform design documents, add to Business Improvement document.

**Truth #2: This System Handles Real Money**
- Every hidden error is potential financial loss

**Truth #3: Intelligence Quality Drives Everything**
```
News Intelligence → Scanner Selection → Analysis → Trading Decisions
```

**Truth #4: Poor Database Design = Poor ML Models**
- Denormalized data = duplicated, inconsistent features
- Proper normalization = clean ML training data
- Schema defines data quality at the source
- Adaptive sampling = high resolution when it matters, efficiency when calm

**Truth #5: Time is its Own Dimension** ⭐ NEW
- Time is not just a timestamp column
- Time has rich metadata (market session, trading day, boundaries)
- Time relationships enable efficient queries
- Time-based partitioning improves performance

### 1.2 Zero Tolerance Policy

❌ Bare `except:` catching everything  
❌ `except Exception:` without specific handling  
❌ Returning empty arrays hiding failures  
❌ Silent database persistence failures  
❌ Storing duplicate data across tables
❌ **Storing symbol VARCHAR in fact tables** ⭐ NEW
❌ **Storing duplicate timestamps** ⭐ NEW
❌ **Ignoring referential integrity** ⭐ NEW

---

## Section 2: STEP 0 - Database Schema v5.0 Deployment

### **CRITICAL: Do this BEFORE touching any service!**

### 0.1 Deploy Normalized Schema v5.0

**Dimension Tables (Master Data - Single Source of Truth):**
```sql
✅ securities (security_id PK) - Master entity for ALL stock data
✅ sectors (sector_id PK) - Normalized sector/industry data
✅ time_dimension (time_id PK) - Time as its own entity
```

**Fact/Event Tables (Use FKs - NO Duplication):**
```sql
✅ trading_history (security_id FK, time_id FK) - OHLCV partitioned
✅ news_sentiment (security_id FK, time_id FK) - News with impact tracking
✅ technical_indicators (security_id FK, time_id FK) - All indicators
✅ sector_correlations (security_id FK) - Daily cross-sectional
✅ economic_indicators - Market-wide (FREE FRED data)
✅ security_fundamentals (security_id FK) - Quarterly earnings
✅ analyst_estimates (security_id FK) - Estimate tracking
```

**Trading Tables (Use security_id FK):**
```sql
✅ trading_cycles (cycle_id PK) - Cycle management
✅ positions (security_id FK, cycle_id FK) - Position tracking
✅ scan_results (security_id FK, cycle_id FK) - Scanner output
✅ orders (security_id FK, position_id FK) - Order execution
```

**Adaptive Sampling Tables (NEW v5.0):**
```sql
✅ active_securities - Top 20 stocks to track
✅ volatility_regimes - Volatility state detection
✅ adaptive_sampling_rules - Frequency change rules
```

**Materialized Views (Pre-joined for ML):**
```sql
✅ v_ml_features - Complete ML feature set via JOINs
✅ v_securities_latest - Latest security data
✅ v_event_correlations - Price → News → Economic correlation
```

### 0.2 Helper Functions (Critical!)

```sql
-- Function 1: Get or create security_id
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities WHERE symbol = p_symbol;
    
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, name)
        VALUES (p_symbol, p_symbol)
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

-- Function 2: Get or create time_id
CREATE OR REPLACE FUNCTION get_or_create_time(p_timestamp TIMESTAMPTZ)
RETURNS BIGINT AS $$
DECLARE
    v_time_id BIGINT;
BEGIN
    SELECT time_id INTO v_time_id
    FROM time_dimension WHERE timestamp = p_timestamp;
    
    IF v_time_id IS NULL THEN
        INSERT INTO time_dimension (
            timestamp, date, year, quarter, month, week,
            day_of_month, day_of_week, day_of_year,
            hour, minute
        ) VALUES (
            p_timestamp,
            DATE(p_timestamp),
            EXTRACT(YEAR FROM p_timestamp),
            EXTRACT(QUARTER FROM p_timestamp),
            EXTRACT(MONTH FROM p_timestamp),
            EXTRACT(WEEK FROM p_timestamp),
            EXTRACT(DAY FROM p_timestamp),
            EXTRACT(DOW FROM p_timestamp),
            EXTRACT(DOY FROM p_timestamp),
            EXTRACT(HOUR FROM p_timestamp),
            EXTRACT(MINUTE FROM p_timestamp)
        )
        RETURNING time_id INTO v_time_id;
    END IF;
    
    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;

-- Function 3: Detect volatility regime
CREATE OR REPLACE FUNCTION detect_volatility_regime(
    p_security_id INTEGER,
    p_price_change_pct DECIMAL,
    p_volume_ratio DECIMAL,
    p_has_news BOOLEAN
) RETURNS VARCHAR AS $$
-- Implementation per adaptive-timeseries-design-v51.md
$$ LANGUAGE plpgsql;
```

### 0.3 Seed Data

```sql
-- Insert default sectors
INSERT INTO sectors (sector_name, sector_code, sector_etf_symbol) VALUES
    ('Technology', 'XLK', 'XLK'),
    ('Healthcare', 'XLV', 'XLV'),
    ('Financials', 'XLF', 'XLF'),
    ('Consumer Discretionary', 'XLY', 'XLY'),
    ('Communication Services', 'XLC', 'XLC'),
    ('Industrials', 'XLI', 'XLI'),
    ('Consumer Staples', 'XLP', 'XLP'),
    ('Energy', 'XLE', 'XLE'),
    ('Utilities', 'XLU', 'XLU'),
    ('Real Estate', 'XLRE', 'XLRE'),
    ('Materials', 'XLB', 'XLB')
ON CONFLICT (sector_name) DO NOTHING;

-- Insert FRED economic indicators to track
INSERT INTO economic_indicators (indicator_code, indicator_name, category, units, frequency, date, value) VALUES
    ('DFF', 'Federal Funds Effective Rate', 'interest_rate', 'percentage', 'daily', CURRENT_DATE, 0),
    ('T10Y2Y', '10-Year Treasury - 2-Year Spread', 'interest_rate', 'percentage', 'daily', CURRENT_DATE, 0),
    ('VIXCLS', 'VIX Volatility Index', 'market_sentiment', 'index', 'daily', CURRENT_DATE, 0),
    ('CPIAUCSL', 'Consumer Price Index', 'inflation', 'index', 'monthly', CURRENT_DATE, 0),
    ('UNRATE', 'Unemployment Rate', 'employment', 'percentage', 'monthly', CURRENT_DATE, 0),
    ('PAYEMS', 'Nonfarm Payrolls', 'employment', 'thousands', 'monthly', CURRENT_DATE, 0),
    ('GDP', 'Gross Domestic Product', 'gdp', 'billions', 'quarterly', CURRENT_DATE, 0)
ON CONFLICT (indicator_code, date) DO NOTHING;
```

### 0.4 Validation Checklist

**Run these queries to verify schema v5.0:**

```sql
-- 1. Check all dimension tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('securities', 'sectors', 'time_dimension')
ORDER BY table_name;
-- Should return: sectors, securities, time_dimension

-- 2. Check helper functions exist
SELECT proname FROM pg_proc 
WHERE proname IN ('get_or_create_security', 'get_or_create_time', 'detect_volatility_regime');
-- Should return: all 3 functions

-- 3. Test helper functions work
SELECT get_or_create_security('AAPL');  -- Should return 1
SELECT get_or_create_security('AAPL');  -- Should return 1 (same ID)
SELECT * FROM securities;  -- Should show AAPL

SELECT get_or_create_time(NOW());  -- Should return time_id

-- 4. Check FK constraints enforced
SELECT tc.table_name, tc.constraint_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;
-- Should show many FK constraints

-- 5. Check materialized views exist
SELECT matviewname FROM pg_matviews 
WHERE schemaname = 'public';
-- Should return: v_ml_features, v_securities_latest

-- 6. Test ML features view works
SELECT * FROM v_ml_features LIMIT 1;
-- Should return data (or empty if no data yet)

-- 7. Check no orphaned records possible
SELECT COUNT(*) FROM scan_results sr
LEFT JOIN securities s ON s.security_id = sr.security_id
WHERE s.security_id IS NULL;
-- Should return 0 (or fail if scan_results still has symbol column)
```

### 0.5 Success Criteria for Step 0

**✅ COMPLETE when ALL these are true:**
- [ ] All dimension tables created (securities, sectors, time_dimension)
- [ ] All fact tables created with FK constraints
- [ ] All adaptive sampling tables created
- [ ] Helper functions exist and work
- [ ] Materialized views created
- [ ] Sectors and economic indicators seeded
- [ ] All validation queries pass
- [ ] No orphaned records possible (FKs enforced)

**⚠️ DO NOT PROCEED to Step 1 until Step 0 is 100% complete!**

---

## Section 3: Service Migration Steps (Weeks 2-4)

### **STEP 1: News Service** (Week 2, Days 1-4)

**File**: `services/news/news-service.py` v5.0.0  
**Priority**: ⭐⭐⭐ CRITICAL FIRST (Intelligence Foundation - Service #1 of 9)  
**Effort**: 3-4 days  
**Lines Changed**: ~300

**WHY FIRST?**
- News provides catalyst detection for Scanner
- Scanner's catalyst_score depends on news data
- Active securities selection driven by news events
- News events trigger volatility regime changes
- Price impact tracking is ML-critical

**Current State (WRONG)**:
```python
# ❌ Stores in news_articles table with symbol VARCHAR
await db.execute("""
    INSERT INTO news_articles (
        symbol, headline, published_at, sentiment_score, ...
    ) VALUES ($1, $2, $3, $4, ...)
""", symbol, headline, published_at, score, ...)
```

**Target State (CORRECT)**:
```python
# ✅ Stores in news_sentiment with security_id + time_id FKs
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", symbol
)
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", published_at
)

await db.execute("""
    INSERT INTO news_sentiment (
        security_id, time_id, headline, summary, url, source,
        sentiment_score, sentiment_label,
        catalyst_type, catalyst_strength,
        source_reliability_score, metadata
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
""", 
    security_id, time_id, headline, summary, url, source,
    score, label, cat_type, strength, 0.500, metadata_json
)
```

**Required Changes**:

1. **Add helper functions at top**:
```python
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol"""
    security_id = await state.db_pool.fetchval(
        "SELECT get_or_create_security($1)", symbol
    )
    if not security_id:
        raise ValueError(f"Failed to get security_id for {symbol}")
    return security_id

async def get_time_id(timestamp: datetime) -> int:
    """Get or create time_id for timestamp"""
    time_id = await state.db_pool.fetchval(
        "SELECT get_or_create_time($1)", timestamp
    )
    if not time_id:
        raise ValueError(f"Failed to get time_id for {timestamp}")
    return time_id
```

2. **Update news storage function**:
```python
async def store_news_article(article: Dict):
    """Store news with proper FKs and impact tracking"""
    
    # Get FKs
    security_id = await get_security_id(article['symbol'])
    time_id = await get_time_id(article['published_at'])
    
    # Analyze sentiment
    sentiment_score, sentiment_label = await analyze_sentiment(article['headline'])
    
    # Detect catalyst
    catalyst_type, catalyst_strength = await detect_catalyst(article)
    
    # Store in news_sentiment table
    news_id = await state.db_pool.fetchval("""
        INSERT INTO news_sentiment (
            security_id, time_id, 
            headline, summary, url, source,
            sentiment_score, sentiment_label,
            catalyst_type, catalyst_strength,
            source_reliability_score,
            metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING news_id
    """, 
        security_id, time_id,
        article['headline'], article.get('summary'), 
        article.get('url'), article['source'],
        sentiment_score, sentiment_label,
        catalyst_type, catalyst_strength,
        0.500,  # Initial reliability score
        json.dumps(article.get('metadata', {}))
    )
    
    logger.info(f"Stored news {news_id} for {article['symbol']}")
    return news_id
```

3. **Add price impact tracking (background job)**:
```python
async def calculate_news_price_impact():
    """Background job: Calculate actual price impact after news events"""
    
    while True:
        try:
            # Find news events without price impact calculated
            news_events = await state.db_pool.fetch("""
                SELECT 
                    ns.news_id, 
                    ns.security_id, 
                    td.timestamp as published_at,
                    th_before.close as price_before
                FROM news_sentiment ns
                JOIN time_dimension td ON td.time_id = ns.time_id
                LEFT JOIN LATERAL (
                    SELECT close FROM trading_history
                    WHERE security_id = ns.security_id
                    AND time_id <= ns.time_id
                    ORDER BY time_id DESC LIMIT 1
                ) th_before ON TRUE
                WHERE ns.price_impact_5min IS NULL
                AND td.timestamp < NOW() - INTERVAL '5 minutes'
                LIMIT 100
            """)
            
            for event in news_events:
                # Get prices at different intervals after news
                prices = await state.db_pool.fetchrow("""
                    SELECT 
                        (SELECT close FROM trading_history th
                         JOIN time_dimension td ON td.time_id = th.time_id
                         WHERE th.security_id = $1 
                         AND td.timestamp >= $2 + INTERVAL '5 minutes'
                         ORDER BY td.timestamp ASC LIMIT 1) as price_5min,
                        
                        (SELECT close FROM trading_history th
                         JOIN time_dimension td ON td.time_id = th.time_id
                         WHERE th.security_id = $1 
                         AND td.timestamp >= $2 + INTERVAL '15 minutes'
                         ORDER BY td.timestamp ASC LIMIT 1) as price_15min,
                        
                        (SELECT close FROM trading_history th
                         JOIN time_dimension td ON td.time_id = th.time_id
                         WHERE th.security_id = $1 
                         AND td.timestamp >= $2 + INTERVAL '30 minutes'
                         ORDER BY td.timestamp ASC LIMIT 1) as price_30min
                """, event['security_id'], event['published_at'])
                
                # Calculate % impacts
                if event['price_before'] and prices:
                    impact_5min = ((prices['price_5min'] - event['price_before']) / 
                                  event['price_before'] * 100) if prices['price_5min'] else None
                    impact_15min = ((prices['price_15min'] - event['price_before']) / 
                                   event['price_before'] * 100) if prices['price_15min'] else None
                    impact_30min = ((prices['price_30min'] - event['price_before']) / 
                                   event['price_before'] * 100) if prices['price_30min'] else None
                    
                    # Update news_sentiment with impacts
                    await state.db_pool.execute("""
                        UPDATE news_sentiment
                        SET price_impact_5min = $1,
                            price_impact_15min = $2,
                            price_impact_30min = $3
                        WHERE news_id = $4
                    """, impact_5min, impact_15min, impact_30min, event['news_id'])
                    
                    logger.info(f"Updated price impact for news {event['news_id']}: "
                              f"5min={impact_5min:.2f}%, 15min={impact_15min:.2f}%")
            
            # Wait before next check
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Price impact calculation error: {e}")
            await asyncio.sleep(60)
```

4. **Add source reliability tracking**:
```python
async def update_source_reliability():
    """Track which news sources accurately predict price moves"""
    
    # Get news with both catalyst prediction and actual impact
    correlations = await state.db_pool.fetch("""
        SELECT 
            source,
            catalyst_strength,
            price_impact_15min,
            COUNT(*) as count
        FROM news_sentiment
        WHERE price_impact_15min IS NOT NULL
        AND catalyst_strength IS NOT NULL
        GROUP BY source, catalyst_strength, price_impact_15min
    """)
    
    # Calculate reliability per source
    source_scores = {}
    for row in correlations:
        source = row['source']
        
        # Strong catalyst should = strong impact
        predicted_strong = row['catalyst_strength'] in ['strong', 'very_strong']
        actual_strong = abs(row['price_impact_15min']) > 1.0  # >1% move
        
        if source not in source_scores:
            source_scores[source] = {'correct': 0, 'total': 0}
        
        source_scores[source]['total'] += row['count']
        if predicted_strong == actual_strong:
            source_scores[source]['correct'] += row['count']
    
    # Update reliability scores
    for source, stats in source_scores.items():
        reliability = stats['correct'] / stats['total'] if stats['total'] > 0 else 0.5
        
        await state.db_pool.execute("""
            UPDATE news_sentiment
            SET source_reliability_score = $1
            WHERE source = $2
        """, reliability, source)
        
        logger.info(f"Updated {source} reliability: {reliability:.3f} "
                   f"({stats['correct']}/{stats['total']})")
```

5. **Update query patterns**:
```python
# ❌ OLD:
news = await db.fetch("""
    SELECT * FROM news_articles WHERE symbol = $1
""", symbol)

# ✅ NEW:
news = await db.fetch("""
    SELECT 
        ns.*,
        s.symbol,
        s.company_name,
        sec.sector_name,
        td.timestamp as published_at,
        td.market_session
    FROM news_sentiment ns
    JOIN securities s ON s.security_id = ns.security_id
    JOIN sectors sec ON sec.sector_id = s.sector_id
    JOIN time_dimension td ON td.time_id = ns.time_id
    WHERE s.symbol = $1
    AND td.timestamp >= NOW() - INTERVAL '24 hours'
    ORDER BY td.timestamp DESC
""", symbol)
```

6. **Start background jobs on startup**:
```python
@app.on_event("startup")
async def startup_event():
    # Start price impact calculation
    asyncio.create_task(calculate_news_price_impact())
    
    # Start source reliability updates (hourly)
    asyncio.create_task(update_source_reliability_hourly())
```

**Verification Tests**:
```python
@pytest.mark.asyncio
async def test_news_uses_security_id_and_time_id():
    """Verify news service uses both security_id and time_id FKs"""
    
    # Store news
    news_data = {
        'symbol': 'AAPL',
        'headline': 'Test News',
        'published_at': datetime.now(),
        'source': 'test'
    }
    await news_service.store_news_article(news_data)
    
    # Verify stored with FKs
    result = await db.fetchrow("""
        SELECT 
            ns.*,
            s.symbol,
            td.timestamp
        FROM news_sentiment ns
        JOIN securities s ON s.security_id = ns.security_id
        JOIN time_dimension td ON td.time_id = ns.time_id
        WHERE ns.headline = $1
    """, 'Test News')
    
    assert result is not None
    assert 'security_id' in result
    assert 'time_id' in result
    assert result['symbol'] == 'AAPL'
    
    # Verify no orphans
    orphans = await db.fetchval("""
        SELECT COUNT(*) FROM news_sentiment ns
        LEFT JOIN securities s ON s.security_id = ns.security_id
        WHERE s.security_id IS NULL
    """)
    assert orphans == 0

@pytest.mark.asyncio
async def test_price_impact_calculated():
    """Verify price impact is tracked"""
    
    # Store news
    await news_service.store_news_article(news_data)
    
    # Store some price data after
    # ... (add trading_history records)
    
    # Run impact calculation
    await news_service.calculate_news_price_impact()
    
    # Verify impact populated
    impact = await db.fetchval("""
        SELECT price_impact_5min FROM news_sentiment
        WHERE headline = $1
    """, 'Test News')
    
    assert impact is not None
```

**Success Criteria for News Service**:
- [ ] Uses security_id FK (not symbol VARCHAR)
- [ ] Uses time_id FK (not duplicate timestamps)
- [ ] Stores in news_sentiment table (not news_articles)
- [ ] Tracks sentiment_score and sentiment_label
- [ ] Detects catalyst_type and catalyst_strength
- [ ] Calculates price_impact_5min, 15min, 30min (background job)
- [ ] Updates source_reliability_score
- [ ] All queries use JOINs
- [ ] Tests pass (no orphans)

---

### **STEP 2: Scanner Service** (Week 2, Days 5-6 + Week 3, Day 1)

**File**: `services/scanner/scanner-service.py` v5.1.0  
**Priority**: ⭐⭐ CRITICAL (depends on News)  
**Effort**: 2-3 days  
**Lines Changed**: ~200

**WHY SECOND?**
- Scanner needs News service working first
- Scanner's catalyst_score pulls from news_sentiment table
- Scanner selects candidates based on news catalysts

**Current State (WRONG)**:
```python
# ❌ Stores symbol VARCHAR directly
await db.execute("""
    INSERT INTO scan_results (cycle_id, symbol, price, volume, ...)
    VALUES ($1, $2, $3, $4, ...)
""", cycle_id, 'AAPL', 150.00, 1000000, ...)
```

**Target State (CORRECT)**:
```python
# ✅ Uses security_id FK
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", 'AAPL'
)

await db.execute("""
    INSERT INTO scan_results (cycle_id, security_id, price, volume, ...)
    VALUES ($1, $2, $3, $4, ...)
""", cycle_id, security_id, 150.00, 1000000, ...)
```

**Required Changes**:

1. **Add helper at top of file**:
```python
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol"""
    security_id = await state.db_pool.fetchval(
        "SELECT get_or_create_security($1)", symbol
    )
    if not security_id:
        raise ValueError(f"Failed to get security_id for {symbol}")
    return security_id
```

2. **Update `persist_scan_results()` function**:
```python
async def persist_scan_results(cycle_id: str, candidates: List[Dict]):
    for candidate in candidates:
        # Get security_id
        security_id = await get_security_id(candidate['symbol'])
        
        # Store with FK
        await state.db_pool.execute("""
            INSERT INTO scan_results (
                cycle_id, security_id, price, volume,
                momentum_score, volume_score, catalyst_score,
                technical_score, composite_score, rank,
                selected_for_trading, scan_metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, 
            cycle_id, security_id, candidate['price'], candidate['volume'],
            candidate['momentum_score'], candidate['volume_score'], 
            candidate['catalyst_score'], candidate['technical_score'],
            candidate['composite_score'], candidate.get('rank'),
            candidate.get('selected_for_trading', False),
            json.dumps(candidate.get('metadata', {}))
        )
```

3. **Update all query patterns**:
```python
# ❌ OLD:
results = await db.fetch("""
    SELECT * FROM scan_results WHERE symbol = $1
""", symbol)

# ✅ NEW:
results = await db.fetch("""
    SELECT 
        sr.*,
        s.symbol,
        s.company_name,
        sec.sector_name
    FROM scan_results sr
    JOIN securities s ON s.security_id = sr.security_id
    JOIN sectors sec ON sec.sector_id = s.sector_id
    WHERE s.symbol = $1
    ORDER BY sr.scan_timestamp DESC
""", symbol)
```

**Verification Tests**:
```python
@pytest.mark.asyncio
async def test_scanner_uses_security_id():
    # Run scan
    await scanner.scan_market()
    
    # Verify scan_results has security_id FK
    result = await db.fetchrow("""
        SELECT sr.*, s.symbol 
        FROM scan_results sr
        JOIN securities s ON s.security_id = sr.security_id
        LIMIT 1
    """)
    
    assert result is not None
    assert 'security_id' in result
    assert 'symbol' in result  # From JOIN
    
    # Verify no orphans
    orphans = await db.fetchval("""
        SELECT COUNT(*) FROM scan_results sr
        LEFT JOIN securities s ON s.security_id = sr.security_id
        WHERE s.security_id IS NULL
    """)
    assert orphans == 0
```

---

### **STEP 2: Trading Service** (Week 2, Days 4-6)

**File**: `services/trading/trading-service.py` v4.2.0  
**Priority**: ⭐ CRITICAL (handles money!)  
**Effort**: 3-4 days  
**Lines Changed**: ~250

**Required Changes**:

1. **Update positions table**:
```python
# ✅ NEW:
security_id = await get_security_id(symbol)

position_id = await db.fetchval("""
    INSERT INTO positions (
        cycle_id, security_id, side, quantity, 
        entry_price, stop_loss, take_profit, risk_amount
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    RETURNING position_id
""", cycle_id, security_id, side, qty, price, stop, target, risk)
```

2. **Update orders table**:
```python
# ✅ NEW:
await db.execute("""
    INSERT INTO orders (
        order_id, position_id, cycle_id, security_id,
        side, order_type, quantity, status, ...
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, ...)
""", order_id, position_id, cycle_id, security_id, ...)
```

3. **Update position queries with JOINs**:
```python
# ✅ NEW:
positions = await db.fetch("""
    SELECT 
        p.*,
        s.symbol,
        s.company_name,
        sec.sector_name
    FROM positions p
    JOIN securities s ON s.security_id = p.security_id
    JOIN sectors sec ON sec.sector_id = s.sector_id
    WHERE p.cycle_id = $1 AND p.status = 'open'
""", cycle_id)
```

---

### **STEP 3: News Service** (Week 3, Days 1-4)

**File**: `services/news/news-service.py` v5.0.0  
**Priority**: ⭐ CRITICAL (ML data quality)  
**Effort**: 3-4 days  
**Lines Changed**: ~300

**Required Changes**:

1. **Migrate to news_sentiment table**:
```python
# ✅ NEW:
security_id = await get_security_id(symbol)
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", published_at
)

await db.execute("""
    INSERT INTO news_sentiment (
        security_id, time_id, headline, summary, url, source,
        sentiment_score, sentiment_label,
        catalyst_type, catalyst_strength,
        source_reliability_score,
        metadata
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
""", 
    security_id, time_id, headline, summary, url, source,
    score, label, cat_type, strength, reliability, metadata_json
)
```

2. **Add price impact tracking (background job)**:
```python
async def calculate_news_price_impact():
    """Calculate actual price impact after news"""
    
    news_events = await db.fetch("""
        SELECT ns.news_id, ns.security_id, td.timestamp
        FROM news_sentiment ns
        JOIN time_dimension td ON td.time_id = ns.time_id
        WHERE ns.price_impact_5min IS NULL
        AND td.timestamp < NOW() - INTERVAL '5 minutes'
    """)
    
    for event in news_events:
        # Get price 5/15/30min after
        prices = await db.fetchrow("""
            SELECT 
                (SELECT close FROM trading_history 
                 WHERE security_id = $1 AND time_id > $2 
                 ORDER BY time_id ASC LIMIT 1) as price_5min_after,
                (SELECT close FROM trading_history 
                 WHERE security_id = $1 AND time_id > $2 + INTERVAL '10 minutes'
                 ORDER BY time_id ASC LIMIT 1) as price_15min_after
        """, event['security_id'], event['time_id'])
        
        # Calculate % impact
        # Update news_sentiment with impacts
```

3. **Add source reliability tracking**:
```python
async def update_source_reliability():
    """Track which sources accurately predict moves"""
    # Compare predicted vs actual impact
    # Update news_sentiment.source_reliability_score
```

---

### **STEP 4: Technical Service** (Week 3, Days 5-6 + Week 4, Day 1)

**File**: `services/technical/technical-service.py` v4.1.0  
**Priority**: ⭐ HIGH (ML features)  
**Effort**: 3-4 days  
**Lines Changed**: ~400

**Required Changes**:

1. **Add database persistence** (currently NO storage!):
```python
@app.get("/api/v1/indicators/{symbol}")
async def get_indicators(symbol: str, timeframe: str = '1hour'):
    security_id = await get_security_id(symbol)
    time_id = await db.fetchval(
        "SELECT get_or_create_time($1)", datetime.now()
    )
    
    # Calculate indicators
    indicators = await calculate_all_indicators(symbol, timeframe)
    
    # ✅ PERSIST TO DATABASE
    await db.execute("""
        INSERT INTO technical_indicators (
            security_id, time_id, timeframe,
            sma_20, sma_50, sma_200, ema_9, ema_21,
            rsi_14, macd, macd_signal, macd_histogram,
            atr_14, bollinger_upper, bollinger_middle, bollinger_lower,
            vpoc, vah, val, obv, volume_ratio, unusual_volume_flag,
            bid_ask_spread, order_flow_imbalance,
            support_level, resistance_level
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 
                  $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
        ON CONFLICT (security_id, time_id, timeframe) 
        DO UPDATE SET ...
    """, security_id, time_id, timeframe, ...)
    
    return indicators
```

2. **Add volume profile** (ML critical):
```python
async def calculate_volume_profile(bars):
    """Calculate VPOC, VAH, VAL"""
    # Volume profile implementation
    return vpoc, vah, val
```

3. **Add microstructure** (ML critical):
```python
async def calculate_microstructure(symbol):
    """Calculate bid-ask spread, order flow"""
    # Microstructure implementation
    return bid_ask_spread, order_flow_imbalance
```

---

### **STEP 5: Pattern Service** (Week 4, Days 2-3)

**File**: `services/pattern/pattern-service.py` v4.1.0  
**Priority**: ⭐ MEDIUM  
**Effort**: 2 days  
**Lines Changed**: ~150

**Required Changes**:
```python
# ✅ NEW:
security_id = await get_security_id(symbol)
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", detected_at
)

await db.execute("""
    INSERT INTO pattern_analysis (
        security_id, time_id, pattern_type, pattern_subtype, timeframe,
        confidence_score, price_at_detection, volume_at_detection,
        breakout_level, target_price, stop_level, metadata
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
""", security_id, time_id, ...)
```

---

### **STEP 6: Risk Manager** (Week 4, Day 4)

**File**: `services/risk-manager/risk-manager-service.py` v4.2.0  
**Priority**: ⭐ MEDIUM  
**Effort**: 2 days  
**Lines Changed**: ~100

**Required Changes**:
```python
# Update sector exposure tracking
async def check_sector_exposure(symbol: str):
    security_id = await get_security_id(symbol)
    
    sector_exposure = await db.fetchrow("""
        SELECT 
            sec.sector_name,
            SUM(p.quantity * p.entry_price) as exposure,
            COUNT(*) as position_count
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        JOIN sectors sec ON sec.sector_id = s.sector_id
        WHERE p.status = 'open'
        AND s.security_id = $1
        GROUP BY sec.sector_name
    """, security_id)
```

---

### **STEP 7: Orchestration Service** (Week 4, Day 5)

**File**: `services/orchestration/orchestration-service.py` v4.1.0  
**Priority**: LOW (coordination only)  
**Effort**: 1 day  
**Lines Changed**: ~50

**Required Changes**:
- Handle responses with security_id + symbol
- Pass security_id between services
- No direct database changes (calls other services)

---

### **STEP 8: Reporting Service** (Week 4, Day 5)

**File**: `services/reporting/reporting-service.py` v4.1.0  
**Priority**: LOW  
**Effort**: 1 day  
**Lines Changed**: ~100

**Required Changes**:
- Update all queries to use JOINs
- Use v_ml_features and v_securities_latest views
- Report on normalized data

---

## Section 4: Testing Strategy

### 4.1 Unit Tests (Per Service)

```python
# test_{service}_normalized.py template
import pytest
import asyncpg

@pytest.mark.asyncio
async def test_service_uses_security_id():
    """Verify service stores security_id FK, not symbol"""
    
    # Trigger service action
    await service.perform_action('AAPL')
    
    # Verify FK usage
    result = await db.fetchrow("""
        SELECT t.*, s.symbol 
        FROM table t
        JOIN securities s ON s.security_id = t.security_id
        LIMIT 1
    """)
    
    assert result is not None
    assert 'security_id' in result
    assert 'symbol' in result  # From JOIN
    
@pytest.mark.asyncio
async def test_no_orphaned_records():
    """Verify no orphaned records (FKs enforced)"""
    
    orphans = await db.fetchval("""
        SELECT COUNT(*) FROM table t
        LEFT JOIN securities s ON s.security_id = t.security_id
        WHERE s.security_id IS NULL
    """)
    assert orphans == 0
```

### 4.2 Integration Tests

```python
# test_normalized_workflow.py
@pytest.mark.asyncio
async def test_end_to_end_normalized():
    """Test complete workflow with v5.0 schema"""
    
    # 1. Scanner finds candidates
    scan_result = await scanner.scan_market()
    assert 'security_id' in scan_result['candidates'][0]
    
    # 2. News for candidate
    news = await news_service.get_news(candidate['symbol'])
    assert all('security_id' in n for n in news)
    
    # 3. Technical indicators
    await technical_service.get_indicators(candidate['symbol'])
    
    # 4. Verify ML features queryable
    ml_features = await db.fetch("""
        SELECT * FROM v_ml_features
        WHERE security_id = $1
    """, candidate['security_id'])
    
    assert len(ml_features) > 0
```

### 4.3 Data Integrity Tests

```python
# test_data_integrity.py
@pytest.mark.asyncio
async def test_symbol_only_in_securities():
    """Verify symbol stored ONLY in securities table"""
    
    tables = ['scan_results', 'positions', 'orders', 'news_sentiment']
    
    for table in tables:
        columns = await db.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = $1
        """, table)
        
        column_names = [c['column_name'] for c in columns]
        assert 'symbol' not in column_names
        assert 'security_id' in column_names
```

---

## Section 5: Migration Timeline

### Week 1: Database Foundation
- [ ] Day 1-2: DROP existing DB, CREATE v5.0 schema
- [ ] Day 3: Verify helper functions, seed data
- [ ] Day 4: Create materialized views
- [ ] Day 5: Validation & testing

### Week 2: Core Trading Services
- [ ] Day 1-3: Scanner Service (CRITICAL)
- [ ] Day 4-6: Trading Service (handles money!)
- [ ] Day 6: Risk Manager updates

### Week 3: Intelligence Services
- [ ] Day 1-4: News Service (ML quality)
- [ ] Day 5-6 + Week 4 Day 1: Technical Service (ML features)

### Week 4: Coordination & Polish
- [ ] Day 2-3: Pattern Service
- [ ] Day 4: Risk Manager completion
- [ ] Day 5: Orchestration + Reporting
- [ ] Day 5: Integration testing
- [ ] Weekend: Deploy to production

---

## Section 6: Success Criteria

### Database Schema (Step 0)
- ✅ All v5.0 tables created with correct structure
- ✅ All FK constraints enforced
- ✅ Helper functions work (get_or_create_security, get_or_create_time)
- ✅ Materialized views return data
- ✅ Sectors and economic indicators seeded
- ✅ No orphaned records possible

### Each Service (Steps 1-8)
- ✅ Uses security_id FK (NOT symbol VARCHAR)
- ✅ Uses time_id FK for time-series (NOT duplicate timestamps)
- ✅ All queries use JOINs (NOT symbol strings)
- ✅ No duplicate data storage
- ✅ Error handling audited (v1.0 rules)
- ✅ Tests pass (unit + integration)

### System-Wide
- ✅ ML features queryable via v_ml_features view
- ✅ News → price impact correlation works
- ✅ Adaptive sampling functional (volatility-based)
- ✅ No denormalized data anywhere
- ✅ All 7 services writing to correct tables

---

## Appendix: Quick Command Reference

### Deploy v5.0 Schema
```bash
# 1. Drop existing database (dev only!)
psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 2. Create v5.0 normalized schema
psql $DATABASE_URL -f normalized-database-schema-mcp-v50.sql

# 3. Verify deployment
psql $DATABASE_URL -f validate-schema-v50.sql
```

### Test a Service
```bash
# Run service-specific tests
pytest tests/test_scanner_normalized.py -v

# Run integration tests
pytest tests/test_normalized_workflow.py -v

# Run data integrity tests
pytest tests/test_data_integrity.py -v
```

### Monitor Migration Progress
```bash
# Check which services still use symbol VARCHAR
grep -r "symbol VARCHAR" services/*/

# Check for orphaned records
psql $DATABASE_URL -c "
SELECT table_name, COUNT(*) as orphans
FROM (
    SELECT 'scan_results' as table_name, COUNT(*) FROM scan_results sr
    LEFT JOIN securities s ON s.security_id = sr.security_id
    WHERE s.security_id IS NULL
) sub
WHERE orphans > 0;
"
```

---

**END OF PLAYBOOK v3.0**

*Database normalization v5.0 with adaptive time-series is not optional - it's the foundation for professional-grade ML trading!* 🎩✨