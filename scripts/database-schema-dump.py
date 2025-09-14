#!/usr/bin/env python3
"""
Catalyst Trading System - Database Schema Dumper
Name of Application: Catalyst Trading System
Name of file: dump_schema.py
Version: 1.0.0
Last Updated: 2025-09-14
Purpose: Dump complete database schema to file for analysis

REVISION HISTORY:
v1.0.0 (2025-09-14) - Schema dump utility
- Lists all tables with columns and types
- Shows indexes and constraints
- Outputs to shareable file
"""

import psycopg2
import os
from datetime import datetime
import json

def dump_schema():
    """Dump complete database schema to file"""
    
    # Get connection string
    print("="*60)
    print("🎩 Catalyst Trading System - Schema Dumper")
    print("="*60)
    print("\nEnter your DigitalOcean connection string:")
    print("(or press Enter to use DATABASE_URL env variable)")
    
    db_url = input("\nConnection string: ").strip()
    if not db_url:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            print("No connection string provided!")
            return
    
    try:
        print("\nConnecting to database...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Create output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"database_schema_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"CATALYST TRADING SYSTEM - DATABASE SCHEMA DUMP\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("="*80 + "\n\n")
            
            # Get database info
            cur.execute("SELECT current_database(), version();")
            db_name, version = cur.fetchone()
            f.write(f"Database: {db_name}\n")
            f.write(f"PostgreSQL Version: {version.split(',')[0]}\n")
            f.write("\n" + "="*80 + "\n\n")
            
            # Get all tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = cur.fetchall()
            
            f.write(f"TOTAL TABLES: {len(tables)}\n")
            f.write("-"*80 + "\n")
            for table in tables:
                f.write(f"  • {table[0]}\n")
            f.write("\n" + "="*80 + "\n\n")
            
            # For each table, get detailed info
            for table in tables:
                table_name = table[0]
                f.write(f"TABLE: {table_name}\n")
                f.write("-"*80 + "\n")
                
                # Get columns
                cur.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        character_maximum_length,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position;
                """, (table_name,))
                
                columns = cur.fetchall()
                f.write(f"Columns ({len(columns)}):\n")
                
                for col in columns:
                    col_name = col[0]
                    data_type = col[1]
                    max_length = col[2]
                    nullable = col[3]
                    default = col[4]
                    
                    # Format type
                    if max_length:
                        type_str = f"{data_type}({max_length})"
                    else:
                        type_str = data_type
                    
                    # Format nullable
                    null_str = "NULL" if nullable == 'YES' else "NOT NULL"
                    
                    # Format default
                    default_str = f"DEFAULT {default[:30]}" if default else ""
                    
                    f.write(f"  - {col_name:<30} {type_str:<20} {null_str:<10} {default_str}\n")
                
                # Get indexes
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = %s
                    AND schemaname = 'public';
                """, (table_name,))
                
                indexes = cur.fetchall()
                if indexes:
                    f.write(f"\nIndexes ({len(indexes)}):\n")
                    for idx in indexes:
                        f.write(f"  - {idx[0]}\n")
                
                # Get foreign keys
                cur.execute("""
                    SELECT
                        tc.constraint_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = %s;
                """, (table_name,))
                
                foreign_keys = cur.fetchall()
                if foreign_keys:
                    f.write(f"\nForeign Keys ({len(foreign_keys)}):\n")
                    for fk in foreign_keys:
                        f.write(f"  - {fk[1]} -> {fk[2]}.{fk[3]}\n")
                
                f.write("\n")
            
            # Check for specific columns that services are looking for
            f.write("="*80 + "\n")
            f.write("CRITICAL COLUMN CHECKS (for v4.1 compatibility):\n")
            f.write("-"*80 + "\n")
            
            critical_checks = [
                ('orders', 'status'),
                ('orders', 'order_id'),
                ('positions', 'status'),
                ('positions', 'position_id'),
                ('pattern_detections', 'profitable'),
                ('pattern_detections', 'detection_id'),
                ('trading_cycles', 'cycle_id'),
                ('trading_cycles', 'status')
            ]
            
            for table, column in critical_checks:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """, (table, column))
                exists = cur.fetchone()[0] > 0
                status = "✅ EXISTS" if exists else "❌ MISSING"
                f.write(f"  {table}.{column:<20} {status}\n")
            
            # Check if pattern_detections exists at all
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'pattern_detections'
            """)
            pattern_exists = cur.fetchone()[0] > 0
            f.write(f"\nPattern Detections Table: {'✅ EXISTS' if pattern_exists else '❌ MISSING'}\n")
            
            # Check for pattern_analysis (alternative table)
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'pattern_analysis'
            """)
            pattern_analysis_exists = cur.fetchone()[0] > 0
            if pattern_analysis_exists:
                f.write(f"Pattern Analysis Table: ✅ EXISTS (might need to be renamed/migrated)\n")
            
            f.write("\n" + "="*80 + "\n")
            f.write("END OF SCHEMA DUMP\n")
            f.write("="*80 + "\n")
        
        print(f"\n✅ Schema dumped to: {filename}")
        print(f"File size: {os.path.getsize(filename):,} bytes")
        print("\nYou can now share this file to show the current database state.")
        
        conn.close()
        return filename
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None

if __name__ == "__main__":
    dump_schema()