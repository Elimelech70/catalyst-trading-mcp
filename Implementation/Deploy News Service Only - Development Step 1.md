# Deploy News Service Only - Development Step 1

**Objective**: Stop all services, deploy only News Service, verify database recording

**Infrastructure**:

- ✅ **DigitalOcean Managed PostgreSQL** (external, not in Docker)
- ✅ **Redis** (Docker container for caching)
- ✅ **News Service** (Docker container)

---

## Step 1: Stop All Existing Services

```bash
# Stop all running containers
docker-compose down

# Verify everything stopped
docker ps

# Should show no Catalyst services running
```

---

## Step 2: Update News Service File

Replace your existing `services/news/news-service.py` with the new v5.0.0 version.

```bash
# Backup old version (optional)
cp services/news/news-service.py services/news/news-service.py.backup

# Copy new version
# (Replace with the v5.0.0 code from the artifact)
```

---

## Step 3: Verify Environment Variables

Create or update `.env` file with required variables:

```bash
# .env file

# DigitalOcean Managed PostgreSQL Database
# Format: postgresql://username:password@host:port/database?sslmode=require
DATABASE_URL=postgresql://doadmin:your_password@your-cluster.db.ondigitalocean.com:25060/catalyst_trading?sslmode=require

# News API Keys
NEWS_API_KEY=your_newsapi_key_here
BENZINGA_API_KEY=your_benzinga_key_here  # Optional
```

**CRITICAL**: 

- News Service will fail to start if `NEWS_API_KEY` or `DATABASE_URL` are missing
- DATABASE_URL must point to your DigitalOcean managed PostgreSQL
- This is intentional - fail fast on misconfiguration

---

## Step 4: Update docker-compose.yml (News Only)

Create a temporary `docker-compose-news-only.yml`:

```yaml
version: '3.8'

services:
  # Redis (for caching)
  redis:
    image: redis:7-alpine
    container_name: catalyst-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - catalyst-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # News Service ONLY
  news:
    build:
      context: ./services/news
      dockerfile: Dockerfile
    container_name: catalyst-news
    environment:
      # DigitalOcean Managed PostgreSQL Database
      DATABASE_URL: ${DATABASE_URL}
      NEWS_API_KEY: ${NEWS_API_KEY}
      BENZINGA_API_KEY: ${BENZINGA_API_KEY}
    ports:
      - "5008:5008"
    volumes:
      - ./services/news:/app
      - news_logs:/app/logs
    networks:
      - catalyst-network
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  redis_data:
  news_logs:

networks:
  catalyst-network:
    driver: bridge
```

**IMPORTANT**: Database is DigitalOcean managed service, not a Docker container.

---

## Step 5: Verify Database Schema (DigitalOcean)

Ensure the `news_articles` table exists in your DigitalOcean database:

```bash
# Connect to DigitalOcean PostgreSQL
# Use connection details from DigitalOcean console
psql "postgresql://doadmin:your_password@your-cluster.db.ondigitalocean.com:25060/catalyst_trading?sslmode=require"

# Or if you have the connection string in DATABASE_URL:
psql $DATABASE_URL
```

```sql
-- Create table if not exists
CREATE TABLE IF NOT EXISTS news_articles (
    article_id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(10),
    headline TEXT NOT NULL,
    source VARCHAR(100),
    published_at TIMESTAMPTZ NOT NULL,
    url TEXT,
    summary TEXT,
    sentiment VARCHAR(20),
    sentiment_score DECIMAL(4,3),
    catalyst_type VARCHAR(50),
    catalyst_strength DECIMAL(4,3),
    keywords JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT sentiment_score_range CHECK (sentiment_score >= 0 AND sentiment_score <= 1),
    CONSTRAINT catalyst_strength_range CHECK (catalyst_strength >= 0 AND catalyst_strength <= 1)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_news_symbol ON news_articles(symbol);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_created ON news_articles(created_at DESC);

-- Verify table exists
\d news_articles
```

---

## Step 6: Start News Service Only

```bash
# Start with news-only compose file
docker-compose -f docker-compose-news-only.yml up -d

# Watch logs in real-time
docker-compose -f docker-compose-news-only.yml logs -f news

# You should see:
# "Starting News Intelligence Service v5.0.0"
# "Configuration validated successfully"
# "HTTP session initialized"
# "Database connection pool initialized"
# "News service startup complete - ready to process requests"
```

---

## Step 7: Test Health Check

```bash
# Test health endpoint
curl http://localhost:5008/health

# Expected response:
{
  "status": "healthy",
  "service": "news",
  "version": "5.0.0",
  "timestamp": "2025-10-01T14:30:00.000Z",
  "database": "connected",
  "http_session": "initialized",
  "configuration": "valid"
}
```

---

## Step 8: Test News Fetching

```bash
# Test with a real symbol (e.g., AAPL)
curl "http://localhost:5008/api/v1/catalysts/AAPL?hours=24&min_strength=0.3"

# Expected response structure:
{
  "symbol": "AAPL",
  "catalysts": [
    {
      "article_id": "...",
      "symbol": "AAPL",
      "headline": "Apple announces...",
      "source": "Reuters",
      "published_at": "...",
      "sentiment": "bullish",
      "sentiment_score": 0.75,
      "catalyst_type": "product_launch",
      "catalyst_strength": 0.82,
      "keywords": ["launch", "product", "announcement"]
    }
  ],
  "count": 5,
  "timestamp": "2025-10-01T14:30:00.000Z"
}
```

---

## Step 9: Verify Database Recording (DigitalOcean)

```bash
# Connect to DigitalOcean database
psql $DATABASE_URL

# Or with full connection string:
# psql "postgresql://doadmin:password@your-cluster.db.ondigitalocean.com:25060/catalyst_trading?sslmode=require"
```

```sql
-- Check if articles were recorded
SELECT 
    article_id,
    symbol,
    headline,
    sentiment,
    catalyst_type,
    catalyst_strength,
    created_at
FROM news_articles
ORDER BY created_at DESC
LIMIT 10;

-- Should see records for AAPL (or whatever symbol you tested)

-- Check count by symbol
SELECT symbol, COUNT(*) as article_count
FROM news_articles
GROUP BY symbol
ORDER BY article_count DESC;
```

---

## Step 10: Review JSON Logs

```bash
# View logs from container
docker exec catalyst-news cat /app/logs/news-service.log

# Download logs for analysis
docker cp catalyst-news:/app/logs/news-service.log ./news-service.log

# Each log line is JSON:
{
  "timestamp": "2025-10-01T14:30:00.000Z",
  "service": "news-service",
  "level": "INFO",
  "message": "NewsAPI returned 15 articles for AAPL",
  "context": {
    "function": "fetch_newsapi",
    "line": 342,
    "module": "news-service"
  }
}
```

---

## Step 11: Test Error Handling (Optional)

Test that errors are visible (not silent):

```bash
# Test with invalid symbol (too long)
curl "http://localhost:5008/api/v1/catalysts/INVALIDTOOLONGSYMBOL"

# Should return 400 error:
{
  "detail": "Invalid symbol: INVALIDTOOLONGSYMBOL"
}

# Test with invalid hours
curl "http://localhost:5008/api/v1/catalysts/AAPL?hours=200"

# Should return 400 error:
{
  "detail": "Hours must be between 1 and 168"
}
```

---

## Success Criteria ✅

News Service is ready for Orchestration (Step 2) when:

1. ✅ Service starts without errors
2. ✅ Health check returns "healthy"
3. ✅ Can fetch news for test symbols (AAPL, TSLA, etc.)
4. ✅ **Articles are recorded in `news_articles` table**
5. ✅ JSON logs are being written to `/app/logs/news-service.log`
6. ✅ Errors are visible and specific (not silent failures)
7. ✅ Sentiment analysis returns valid results
8. ✅ Catalyst detection is working

---

## Troubleshooting

**If service fails to start:**

```bash
# Check logs
docker-compose -f docker-compose-news-only.yml logs news

# Common issues:
# 1. Missing NEWS_API_KEY → "NEWS_API_KEY environment variable required"
# 2. Missing DATABASE_URL → "DATABASE_URL environment variable required"
# 3. Invalid DATABASE_URL → "Database initialization failed"
# 4. DigitalOcean database unreachable → Check connection string and firewall rules
# 5. Invalid API key → "NewsAPI authentication failed - invalid API key"
```

**DigitalOcean Database Connection Issues:**

```bash
# Test connection manually
psql $DATABASE_URL

# If connection fails:
# 1. Check DigitalOcean firewall rules (Trusted Sources)
# 2. Verify connection string format includes ?sslmode=require
# 3. Check database is running in DigitalOcean console
# 4. Verify credentials are correct
```

**If no articles in database:**

```bash
# Check if fetch is working
curl "http://localhost:5008/api/v1/catalysts/AAPL?hours=24"

# Check logs for errors
docker exec catalyst-news cat /app/logs/news-service.log | grep ERROR

# Check database connection in logs
docker exec catalyst-news cat /app/logs/news-service.log | grep database
```

**If you see silent failures (shouldn't happen with v5.0.0):**

```bash
# This is a bug - report it!
# Download logs and share:
docker cp catalyst-news:/app/logs/news-service.log ./news-service-bug.log
```

---

## What to Share With Claude

Once testing is complete, share:

1. **Startup logs** (first 50 lines)
2. **Test response** from `/api/v1/catalysts/AAPL`
3. **Database query results** showing articles recorded
4. **Any errors encountered** (full log context)
5. **JSON log file** for detailed analysis

---

## Next Step After Verification

Once News Service is confirmed working and recording to database:
→ Proceed to **Orchestration Service (Step 2)**

Do NOT proceed until:

- Database persistence is confirmed
- Error handling is verified
- Logs are reviewable
