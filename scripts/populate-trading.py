#!/usr/bin/env python3
"""
Fetch historical bars from Alpaca and store in trading_history
"""
import os
import asyncpg
import asyncio
from datetime import datetime, timedelta
import aiohttp

DATABASE_URL = os.getenv("DATABASE_URL")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://data.alpaca.markets")

async def fetch_and_store_bars(symbol: str, timeframe: str = "5Min", days: int = 5):
    """Fetch bars from Alpaca and store in trading_history"""
    
    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Get security_id
        security_id = await conn.fetchval(
            "SELECT get_or_create_security($1)", symbol
        )
        print(f"✅ Security ID for {symbol}: {security_id}")
        
        # Prepare Alpaca request
        end = datetime.now()
        start = end - timedelta(days=days)
        
        url = f"{ALPACA_BASE_URL}/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": timeframe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": 10000
        }
        headers = {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
        }
        
        # Fetch from Alpaca
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
        
        if "bars" not in data:
            print(f"❌ No bars returned: {data}")
            return
        
        bars = data["bars"]
        print(f"✅ Fetched {len(bars)} bars from Alpaca")
        
        # Insert into trading_history
        inserted = 0
        for bar in bars:
            timestamp = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            
            # Get time_id
            time_id = await conn.fetchval(
                "SELECT get_or_create_time($1)", timestamp
            )
            
            # Insert bar
            await conn.execute("""
                INSERT INTO trading_history (
                    security_id, time_id, timeframe,
                    open_price, high_price, low_price, close_price,
                    volume, vwap, trade_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (security_id, time_id, timeframe) DO NOTHING
            """, security_id, time_id, timeframe.lower(),
                bar["o"], bar["h"], bar["l"], bar["c"],
                bar["v"], bar.get("vw"), bar.get("n", 0)
            )
            inserted += 1
        
        print(f"✅ Inserted {inserted} bars into trading_history")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fetch_and_store_bars("AAPL", "5Min", 5))