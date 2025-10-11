#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: populate-trading.py
Version: 1.0.0
Last Updated: 2025-10-11
Purpose: Fetch historical bars from Alpaca and populate trading_history table

REVISION HISTORY:
v1.0.0 (2025-10-11) - Initial version
- Fetches OHLCV data from Alpaca API
- Stores in trading_history with proper FKs (security_id, time_id)
- Uses helper functions for normalized schema v5.0
"""

import os
import asyncpg
import asyncio
from datetime import datetime, timedelta
import aiohttp
from dotenv import load_dotenv

# ✅ Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
# ✅ Force data API endpoint (not trading endpoint!)
ALPACA_DATA_URL = "https://data.alpaca.markets"
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")  # For trading

# Validate required environment variables
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment")
if not ALPACA_API_KEY:
    raise ValueError("ALPACA_API_KEY not found in environment")
if not ALPACA_SECRET_KEY:
    raise ValueError("ALPACA_SECRET_KEY not found in environment")

print(f"✅ Loaded environment variables")
print(f"   Database: {DATABASE_URL.split('@')[1].split('/')[0]}...")  # Show host only
print(f"   Alpaca Data API: {ALPACA_DATA_URL}")  # Market data endpoint
print(f"   Alpaca Trading API: {ALPACA_BASE_URL}")  # Trading endpoint

async def fetch_and_store_bars(symbol: str, timeframe: str = "5Min", days: int = 5):
    """
    Fetch bars from Alpaca and store in trading_history.
    
    Uses normalized schema v5.0 pattern:
    1. Get security_id via helper function
    2. Get time_id for each bar via helper function
    3. Store with FKs (no symbol VARCHAR duplication!)
    """
    
    print(f"\n{'='*60}")
    print(f"Fetching {symbol} data - {timeframe} bars for last {days} days")
    print(f"{'='*60}\n")
    
    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Step 1: Get security_id
        security_id = await conn.fetchval(
            "SELECT get_or_create_security($1)", symbol
        )
        print(f"✅ Security ID for {symbol}: {security_id}")
        
        # Prepare Alpaca request
        end = datetime.now()
        start = end - timedelta(days=days)
        
        # Alpaca v2 bars endpoint (use data API, not trading API!)
        url = f"{ALPACA_DATA_URL}/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": timeframe,
            "start": start.isoformat() + "Z",
            "end": end.isoformat() + "Z",
            "limit": 10000,
            "adjustment": "raw"
        }
        headers = {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
        }
        
        print(f"📡 Fetching from Alpaca API...")
        print(f"   URL: {url}")
        print(f"   Timeframe: {timeframe}")
        print(f"   Period: {start.date()} to {end.date()}")
        
        # Fetch from Alpaca
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Alpaca API error {resp.status}: {error_text}")
                
                data = await resp.json()
        
        if "bars" not in data or not data["bars"]:
            print(f"⚠️  No bars returned from Alpaca")
            print(f"   Response: {data}")
            return
        
        bars = data["bars"]
        print(f"✅ Fetched {len(bars)} bars from Alpaca\n")
        
        # Step 2: Insert into trading_history
        print(f"💾 Inserting bars into trading_history table...")
        inserted = 0
        skipped = 0
        
        for idx, bar in enumerate(bars):
            # Parse timestamp
            timestamp = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            
            # Get time_id via helper function
            time_id = await conn.fetchval(
                "SELECT get_or_create_time($1)", timestamp
            )
            
            # Insert bar with FKs
            result = await conn.execute("""
                INSERT INTO trading_history (
                    security_id, time_id, timeframe,
                    open_price, high_price, low_price, close_price,
                    volume, vwap, trade_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (security_id, time_id, timeframe) DO NOTHING
            """, 
                security_id, time_id, timeframe.lower(),
                bar["o"], bar["h"], bar["l"], bar["c"],
                bar["v"], bar.get("vw"), bar.get("n", 0)
            )
            
            if result == "INSERT 0 1":
                inserted += 1
            else:
                skipped += 1
            
            # Progress indicator
            if (idx + 1) % 100 == 0:
                print(f"   Progress: {idx + 1}/{len(bars)} bars processed...")
        
        print(f"\n✅ Complete!")
        print(f"   Inserted: {inserted} new bars")
        print(f"   Skipped: {skipped} duplicate bars")
        
        # Verify data
        count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM trading_history th
            WHERE th.security_id = $1
        """, security_id)
        
        print(f"   Total bars for {symbol}: {count}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await conn.close()

async def main():
    """Main entry point"""
    
    # Fetch data for AAPL
    await fetch_and_store_bars("AAPL", "5Min", 5)
    
    print(f"\n{'='*60}")
    print("✅ Data population complete!")
    print(f"{'='*60}\n")
    
    print("Next steps:")
    print("1. Test pattern detection: curl -X POST http://localhost:5004/api/v1/patterns/detect -H 'Content-Type: application/json' -d '{\"symbol\":\"AAPL\",\"timeframe\":\"5min\"}'")
    print("2. Add more symbols as needed")
    print("3. Set up automated data fetching")

if __name__ == "__main__":
    asyncio.run(main())
