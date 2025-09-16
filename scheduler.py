#!/usr/bin/env python3
import time
import requests
import psycopg2
import os
from datetime import datetime

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://doadmin:AVNS_COlEfvzem_NMElg7hd_@catalyst-trading-db-do-user-23488393-0.l.db.ondigitalocean.com:25060/catalyst_trading?sslmode=require')

def get_active_cycle():
    """Get active trading cycle configuration"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT cycle_id, scan_frequency, status 
        FROM trading_cycles 
        WHERE status = 'active' 
        LIMIT 1
    """)
    result = cur.fetchone()
    conn.close()
    return result

def trigger_scan():
    """Trigger scanner service"""
    try:
        # Try various endpoints
        endpoints = [
            'http://localhost:5001/scan',
            'http://localhost:5001/scan/market', 
            'http://localhost:5001/candidates'
        ]
        
        for endpoint in endpoints:
            try:
                if 'candidates' in endpoint:
                    response = requests.get(endpoint)
                else:
                    response = requests.post(endpoint)
                print(f"[{datetime.now()}] Scan triggered: {endpoint} - Status: {response.status_code}")
                if response.status_code == 200:
                    break
            except:
                continue
    except Exception as e:
        print(f"Error triggering scan: {e}")

def main():
    print("Starting Catalyst Trading Scheduler...")
    
    while True:
        cycle = get_active_cycle()
        
        if cycle:
            cycle_id, scan_frequency, status = cycle
            print(f"Active cycle: {cycle_id}, scanning every {scan_frequency} seconds")
            
            # Trigger scan
            trigger_scan()
            
            # Wait for next scan
            time.sleep(scan_frequency)
        else:
            print("No active trading cycle found. Waiting...")
            time.sleep(60)

if __name__ == "__main__":
    main()