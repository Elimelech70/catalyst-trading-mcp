#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: validate_v42_database.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Comprehensive validation of v4.2 database schema and functionality

REVISION HISTORY:
v4.2.0 (2025-09-20) - Complete v4.2 database validation
- Validate all v4.2 tables exist with correct structure
- Check enhanced trading_cycles and positions tables
- Verify new risk management tables
- Test triggers, constraints, and indexes
- Validate default data and functions
- Performance and integrity checks
- Generate comprehensive compliance report

Description of Service:
Comprehensive validation script that verifies the database has been properly
upgraded to v4.2 schema specifications, including all tables, constraints,
triggers, and default data required for the risk management system.
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime, date
import json
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import traceback

# === VALIDATION MODELS ===

@dataclass
class ValidationResult:
    component: str
    status: str  # "PASS", "FAIL", "WARNING", "INFO"
    message: str
    details: Any = None

@dataclass
class TableValidation:
    name: str
    exists: bool
    column_count: int
    expected_columns: List[str]
    missing_columns: List[str]
    extra_columns: List[str]
    constraints: List[str]
    indexes: List[str]

class DatabaseValidator:
    def __init__(self):
        self.connection: asyncpg.Connection = None
        self.results: List[ValidationResult] = []
        self.tables_validated: Dict[str, TableValidation] = {}
        
    async def connect(self):
        """Connect to database"""
        try:
            DATABASE_URL = os.getenv("DATABASE_URL")
            if not DATABASE_URL:
                raise ValueError("DATABASE_URL environment variable not set")
                
            self.connection = await asyncpg.connect(DATABASE_URL)
            self.add_result("CONNECTION", "PASS", "Database connection successful")
            
        except Exception as e:
            self.add_result("CONNECTION", "FAIL", f"Database connection failed: {e}")
            raise
            
    async def disconnect(self):
        """Disconnect from database"""
        if self.connection:
            await self.connection.close()
            
    def add_result(self, component: str, status: str, message: str, details: Any = None):
        """Add validation result"""
        self.results.append(ValidationResult(component, status, message, details))
        
    async def validate_all(self):
        """Run all validations"""
        print("🔍 Starting Catalyst Trading System v4.2 Database Validation")
        print("=" * 70)
        
        try:
            await self.connect()
            
            # Core validation checks
            await self.validate_basic_connectivity()
            await self.validate_required_tables()
            await self.validate_table_structures()
            await self.validate_constraints_and_indexes()
            await self.validate_triggers_and_functions()
            await self.validate_risk_management_setup()
            await self.validate_default_data()
            await self.validate_data_integrity()
            await self.test_crud_operations()
            await self.performance_checks()
            
        except Exception as e:
            self.add_result("VALIDATION", "FAIL", f"Validation failed: {e}")
            traceback.print_exc()
            
        finally:
            await self.disconnect()
            
        # Generate report
        self.generate_report()
        
    async def validate_basic_connectivity(self):
        """Test basic database operations"""
        try:
            # Test simple query
            result = await self.connection.fetchval("SELECT version()")
            self.add_result("CONNECTIVITY", "PASS", f"PostgreSQL version: {result}")
            
            # Test current schema
            schema = await self.connection.fetchval("SELECT current_schema()")
            self.add_result("SCHEMA", "PASS", f"Current schema: {schema}")
            
            # Check database encoding
            encoding = await self.connection.fetchval("SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = current_database()")
            self.add_result("ENCODING", "PASS", f"Database encoding: {encoding}")
            
        except Exception as e:
            self.add_result("CONNECTIVITY", "FAIL", f"Basic connectivity test failed: {e}")
            
    async def validate_required_tables(self):
        """Validate all required v4.2 tables exist"""
        
        # Expected v4.2 tables
        expected_tables = {
            # Core trading tables
            "trading_cycles": "Core trading cycle management",
            "positions": "Trading positions tracking", 
            "trades": "Individual trade records",
            "scan_results": "Market scan results",
            
            # Risk management tables (NEW in v4.2)
            "risk_parameters": "Dynamic risk configuration",
            "daily_risk_metrics": "Daily risk tracking",
            "risk_events": "Risk alerts and violations",
            "position_risk_metrics": "Position-level risk metrics",
            "portfolio_exposure": "Portfolio exposure tracking",
            
            # Market data tables
            "market_data": "Real-time and historical prices",
            "news_articles": "News catalyst tracking (NEW in v4.2)",
            
            # Analysis tables
            "pattern_detections": "Trading pattern results",
            "technical_indicators": "Technical analysis data",
            
            # Reporting tables
            "performance_metrics": "Performance tracking",
            "trade_journal": "Trade analysis and notes"
        }
        
        try:
            # Get all existing tables
            existing_tables = await self.connection.fetch("""
                SELECT table_name, table_type
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            
            existing_table_names = {row['table_name'] for row in existing_tables}
            
            # Check each expected table
            missing_tables = []
            found_tables = []
            
            for table_name, description in expected_tables.items():
                if table_name in existing_table_names:
                    found_tables.append(table_name)
                    self.add_result("TABLE_EXISTS", "PASS", f"✅ {table_name}: {description}")
                else:
                    missing_tables.append(table_name)
                    self.add_result("TABLE_EXISTS", "FAIL", f"❌ {table_name}: Missing - {description}")
                    
            # Check for unexpected tables
            unexpected_tables = existing_table_names - set(expected_tables.keys())
            if unexpected_tables:
                self.add_result("TABLE_UNEXPECTED", "INFO", f"Additional tables found: {', '.join(unexpected_tables)}")
                
            # Summary
            self.add_result("TABLE_SUMMARY", "INFO", 
                          f"Tables: {len(found_tables)} found, {len(missing_tables)} missing, {len(unexpected_tables)} additional",
                          {
                              "found": found_tables,
                              "missing": missing_tables, 
                              "unexpected": list(unexpected_tables)
                          })
                          
        except Exception as e:
            self.add_result("TABLE_VALIDATION", "FAIL", f"Table validation failed: {e}")
            
    async def validate_table_structures(self):
        """Validate detailed table structures"""
        
        # Define expected table structures for v4.2
        table_specs = {
            "trading_cycles": {
                "required_columns": [
                    "cycle_id", "mode", "status", "scan_frequency", "max_positions",
                    "risk_level", "started_at", "stopped_at", "stop_reason",
                    "configuration", "metrics", "created_at", "updated_at",
                    # v4.2 risk enhancements
                    "max_daily_loss", "position_size_multiplier", "total_risk_budget",
                    "used_risk_budget", "current_positions", "current_exposure", "risk_events"
                ],
                "primary_key": "cycle_id"
            },
            
            "risk_parameters": {
                "required_columns": [
                    "id", "parameter_name", "parameter_value", "parameter_type",
                    "description", "set_by", "effective_from", "effective_until",
                    "created_at", "updated_at"
                ],
                "primary_key": "id"
            },
            
            "daily_risk_metrics": {
                "required_columns": [
                    "id", "date", "cycle_id", "daily_pnl", "daily_gross_pnl",
                    "daily_fees", "daily_trades", "max_drawdown", "volatility",
                    "sharpe_ratio", "risk_score", "position_count", "total_exposure",
                    "largest_loss", "largest_win", "created_at"
                ],
                "primary_key": "id"
            },
            
            "risk_events": {
                "required_columns": [
                    "id", "event_type", "severity", "cycle_id", "symbol",
                    "message", "data", "acknowledged", "acknowledged_by",
                    "acknowledged_at", "created_at"
                ],
                "primary_key": "id"
            },
            
            "positions": {
                "required_columns": [
                    "position_id", "cycle_id", "symbol", "side", "quantity",
                    "entry_price", "current_price", "stop_loss", "take_profit",
                    "realized_pnl", "unrealized_pnl", "status", "opened_at",
                    "closed_at", "fees", "sector", "confidence", "pattern_detected",
                    # v4.2 risk enhancements
                    "position_risk", "atr_stop_distance", "risk_reward_ratio",
                    "var_estimate", "max_adverse_excursion"
                ],
                "primary_key": "position_id"
            },
            
            "news_articles": {
                "required_columns": [
                    "id", "symbol", "headline", "summary", "source", "url",
                    "published_at", "sentiment_score", "relevance_score",
                    "catalyst_type", "impact_prediction", "processed_at", "created_at"
                ],
                "primary_key": "id"
            }
        }
        
        for table_name, spec in table_specs.items():
            await self.validate_single_table_structure(table_name, spec)
            
    async def validate_single_table_structure(self, table_name: str, spec: Dict):
        """Validate structure of a single table"""
        try:
            # Get table columns
            columns = await self.connection.fetch("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = $1
                ORDER BY ordinal_position
            """, table_name)
            
            if not columns:
                self.add_result("TABLE_STRUCTURE", "FAIL", f"❌ {table_name}: Table does not exist")
                return
                
            existing_columns = {row['column_name'] for row in columns}
            required_columns = set(spec.get("required_columns", []))
            
            # Check missing columns
            missing_columns = required_columns - existing_columns
            extra_columns = existing_columns - required_columns
            
            if missing_columns:
                self.add_result("TABLE_STRUCTURE", "FAIL", 
                              f"❌ {table_name}: Missing columns: {', '.join(missing_columns)}")
            else:
                self.add_result("TABLE_STRUCTURE", "PASS", 
                              f"✅ {table_name}: All required columns present ({len(existing_columns)} total)")
                              
            if extra_columns:
                self.add_result("TABLE_STRUCTURE", "INFO", 
                              f"ℹ️ {table_name}: Extra columns: {', '.join(extra_columns)}")
                              
            # Validate primary key if specified
            if "primary_key" in spec:
                pk_column = spec["primary_key"]
                if pk_column not in existing_columns:
                    self.add_result("PRIMARY_KEY", "FAIL", 
                                  f"❌ {table_name}: Primary key column '{pk_column}' missing")
                else:
                    self.add_result("PRIMARY_KEY", "PASS", 
                                  f"✅ {table_name}: Primary key '{pk_column}' exists")
                                  
            # Store validation details
            self.tables_validated[table_name] = TableValidation(
                name=table_name,
                exists=True,
                column_count=len(existing_columns),
                expected_columns=list(required_columns),
                missing_columns=list(missing_columns),
                extra_columns=list(extra_columns),
                constraints=[],
                indexes=[]
            )
            
        except Exception as e:
            self.add_result("TABLE_STRUCTURE", "FAIL", f"❌ {table_name}: Structure validation failed: {e}")
            
    async def validate_constraints_and_indexes(self):
        """Validate database constraints and indexes"""
        try:
            # Check key constraints
            constraints = await self.connection.fetch("""
                SELECT 
                    tc.table_name,
                    tc.constraint_name,
                    tc.constraint_type,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                LEFT JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = 'public'
                ORDER BY tc.table_name, tc.constraint_type
            """)
            
            # Group by table
            table_constraints = {}
            for row in constraints:
                table = row['table_name']
                if table not in table_constraints:
                    table_constraints[table] = []
                table_constraints[table].append({
                    'name': row['constraint_name'],
                    'type': row['constraint_type'],
                    'column': row['column_name']
                })
                
            # Check critical constraints
            critical_tables = ['trading_cycles', 'positions', 'risk_parameters']
            for table in critical_tables:
                if table in table_constraints:
                    constraints_list = table_constraints[table]
                    has_primary_key = any(c['type'] == 'PRIMARY KEY' for c in constraints_list)
                    
                    if has_primary_key:
                        self.add_result("CONSTRAINTS", "PASS", f"✅ {table}: Has primary key constraint")
                    else:
                        self.add_result("CONSTRAINTS", "FAIL", f"❌ {table}: Missing primary key constraint")
                else:
                    self.add_result("CONSTRAINTS", "FAIL", f"❌ {table}: No constraints found (table missing?)")
                    
            # Check indexes
            indexes = await self.connection.fetch("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
            """)
            
            # Critical indexes to check
            expected_indexes = [
                ("trading_cycles", "status"),
                ("positions", "status"), 
                ("positions", "symbol"),
                ("risk_parameters", "parameter_name"),
                ("daily_risk_metrics", "date"),
                ("risk_events", "event_type"),
                ("news_articles", "symbol"),
                ("news_articles", "published_at")
            ]
            
            existing_indexes = {(row['tablename'], row['indexname']) for row in indexes}
            
            for table, expected_column in expected_indexes:
                # Look for index containing this column
                found_index = any(expected_column in idx[1].lower() for idx in existing_indexes if idx[0] == table)
                
                if found_index:
                    self.add_result("INDEXES", "PASS", f"✅ {table}: Index found for {expected_column}")
                else:
                    self.add_result("INDEXES", "WARNING", f"⚠️ {table}: No index found for {expected_column}")
                    
            self.add_result("INDEXES", "INFO", f"Total indexes found: {len(indexes)}")
            
        except Exception as e:
            self.add_result("CONSTRAINTS", "FAIL", f"Constraint/index validation failed: {e}")
            
    async def validate_triggers_and_functions(self):
        """Validate database triggers and functions"""
        try:
            # Check for updated_at triggers
            triggers = await self.connection.fetch("""
                SELECT 
                    trigger_name,
                    event_object_table,
                    action_statement
                FROM information_schema.triggers
                WHERE trigger_schema = 'public'
                ORDER BY event_object_table, trigger_name
            """)
            
            # Expected updated_at triggers
            tables_needing_triggers = ['trading_cycles', 'positions', 'risk_parameters', 'daily_risk_metrics']
            
            for table in tables_needing_triggers:
                has_updated_trigger = any(
                    'updated_at' in trigger['trigger_name'].lower() and trigger['event_object_table'] == table 
                    for trigger in triggers
                )
                
                if has_updated_trigger:
                    self.add_result("TRIGGERS", "PASS", f"✅ {table}: Has updated_at trigger")
                else:
                    self.add_result("TRIGGERS", "WARNING", f"⚠️ {table}: Missing updated_at trigger")
                    
            # Check for custom functions
            functions = await self.connection.fetch("""
                SELECT routine_name, routine_type
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                AND routine_type = 'FUNCTION'
                ORDER BY routine_name
            """)
            
            expected_functions = ['update_updated_at_column']
            
            for func_name in expected_functions:
                if any(f['routine_name'] == func_name for f in functions):
                    self.add_result("FUNCTIONS", "PASS", f"✅ Function exists: {func_name}")
                else:
                    self.add_result("FUNCTIONS", "WARNING", f"⚠️ Function missing: {func_name}")
                    
            self.add_result("TRIGGERS", "INFO", f"Total triggers found: {len(triggers)}")
            self.add_result("FUNCTIONS", "INFO", f"Total functions found: {len(functions)}")
            
        except Exception as e:
            self.add_result("TRIGGERS", "FAIL", f"Trigger/function validation failed: {e}")
            
    async def validate_risk_management_setup(self):
        """Validate risk management specific setup"""
        try:
            # Check if risk parameters are populated
            param_count = await self.connection.fetchval("SELECT COUNT(*) FROM risk_parameters")
            
            if param_count > 0:
                self.add_result("RISK_SETUP", "PASS", f"✅ Risk parameters configured: {param_count} parameters")
                
                # Check for essential parameters
                essential_params = [
                    'max_daily_loss', 'max_position_risk', 'max_portfolio_risk',
                    'position_size_multiplier', 'stop_loss_atr_multiple', 'max_positions'
                ]
                
                existing_params = await self.connection.fetch("""
                    SELECT parameter_name, parameter_value
                    FROM risk_parameters
                    WHERE effective_from <= NOW()
                    AND (effective_until IS NULL OR effective_until > NOW())
                """)
                
                param_names = {row['parameter_name'] for row in existing_params}
                
                for param in essential_params:
                    if param in param_names:
                        value = next(row['parameter_value'] for row in existing_params if row['parameter_name'] == param)
                        self.add_result("RISK_PARAMS", "PASS", f"✅ {param}: {value}")
                    else:
                        self.add_result("RISK_PARAMS", "WARNING", f"⚠️ Missing essential parameter: {param}")
                        
            else:
                self.add_result("RISK_SETUP", "FAIL", "❌ No risk parameters configured")
                
            # Check risk events table structure
            risk_event_count = await self.connection.fetchval("SELECT COUNT(*) FROM risk_events")
            self.add_result("RISK_EVENTS", "INFO", f"Risk events table ready: {risk_event_count} events")
            
            # Test risk metrics calculation capability
            try:
                today = date.today()
                metrics_count = await self.connection.fetchval("""
                    SELECT COUNT(*) FROM daily_risk_metrics WHERE date = $1
                """, today)
                self.add_result("RISK_METRICS", "PASS", f"✅ Daily risk metrics accessible: {metrics_count} for today")
            except Exception:
                self.add_result("RISK_METRICS", "WARNING", "⚠️ Daily risk metrics table not accessible")
                
        except Exception as e:
            self.add_result("RISK_SETUP", "FAIL", f"Risk management validation failed: {e}")
            
    async def validate_default_data(self):
        """Validate default/seed data is present"""
        try:
            # Check for any active trading cycles
            cycle_count = await self.connection.fetchval("SELECT COUNT(*) FROM trading_cycles")
            self.add_result("DEFAULT_DATA", "INFO", f"Trading cycles in database: {cycle_count}")
            
            # Check for position data
            position_count = await self.connection.fetchval("SELECT COUNT(*) FROM positions")
            self.add_result("DEFAULT_DATA", "INFO", f"Positions in database: {position_count}")
            
            # Check scan results
            scan_count = await self.connection.fetchval("SELECT COUNT(*) FROM scan_results")
            self.add_result("DEFAULT_DATA", "INFO", f"Scan results in database: {scan_count}")
            
            # Check market data
            market_data_count = await self.connection.fetchval("SELECT COUNT(*) FROM market_data")
            self.add_result("DEFAULT_DATA", "INFO", f"Market data entries: {market_data_count}")
            
        except Exception as e:
            self.add_result("DEFAULT_DATA", "WARNING", f"Default data validation failed: {e}")
            
    async def validate_data_integrity(self):
        """Validate data integrity and relationships"""
        try:
            # Check for orphaned records
            orphaned_positions = await self.connection.fetchval("""
                SELECT COUNT(*) FROM positions p
                LEFT JOIN trading_cycles tc ON p.cycle_id = tc.cycle_id
                WHERE tc.cycle_id IS NULL
            """)
            
            if orphaned_positions > 0:
                self.add_result("DATA_INTEGRITY", "WARNING", f"⚠️ {orphaned_positions} orphaned positions (no matching cycle)")
            else:
                self.add_result("DATA_INTEGRITY", "PASS", "✅ No orphaned positions found")
                
            # Check for invalid position statuses
            valid_statuses = await self.connection.fetchval("""
                SELECT COUNT(*) FROM positions 
                WHERE status NOT IN ('open', 'closed', 'pending')
            """)
            
            if valid_statuses > 0:
                self.add_result("DATA_INTEGRITY", "WARNING", f"⚠️ {valid_statuses} positions with invalid status")
            else:
                self.add_result("DATA_INTEGRITY", "PASS", "✅ All position statuses are valid")
                
            # Check for NULL values in critical fields
            null_checks = [
                ("trading_cycles", "cycle_id"),
                ("positions", "position_id"),
                ("risk_parameters", "parameter_name"),
                ("risk_parameters", "parameter_value")
            ]
            
            for table, column in null_checks:
                try:
                    null_count = await self.connection.fetchval(f"""
                        SELECT COUNT(*) FROM {table} WHERE {column} IS NULL
                    """)
                    
                    if null_count > 0:
                        self.add_result("DATA_INTEGRITY", "FAIL", f"❌ {table}.{column}: {null_count} NULL values found")
                    else:
                        self.add_result("DATA_INTEGRITY", "PASS", f"✅ {table}.{column}: No NULL values")
                except Exception:
                    self.add_result("DATA_INTEGRITY", "WARNING", f"⚠️ Could not check {table}.{column}")
                    
        except Exception as e:
            self.add_result("DATA_INTEGRITY", "FAIL", f"Data integrity validation failed: {e}")
            
    async def test_crud_operations(self):
        """Test basic CRUD operations"""
        try:
            # Test INSERT into risk_parameters
            test_param_name = f"test_param_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            await self.connection.execute("""
                INSERT INTO risk_parameters (parameter_name, parameter_value, set_by)
                VALUES ($1, $2, $3)
            """, test_param_name, 0.5, "validation_test")
            
            # Test SELECT
            result = await self.connection.fetchval("""
                SELECT parameter_value FROM risk_parameters WHERE parameter_name = $1
            """, test_param_name)
            
            if result == 0.5:
                self.add_result("CRUD_TEST", "PASS", "✅ INSERT and SELECT operations working")
            else:
                self.add_result("CRUD_TEST", "FAIL", "❌ INSERT/SELECT test failed")
                
            # Test UPDATE
            await self.connection.execute("""
                UPDATE risk_parameters SET parameter_value = $1 WHERE parameter_name = $2
            """, 0.75, test_param_name)
            
            updated_result = await self.connection.fetchval("""
                SELECT parameter_value FROM risk_parameters WHERE parameter_name = $1
            """, test_param_name)
            
            if updated_result == 0.75:
                self.add_result("CRUD_TEST", "PASS", "✅ UPDATE operation working")
            else:
                self.add_result("CRUD_TEST", "FAIL", "❌ UPDATE test failed")
                
            # Test DELETE
            await self.connection.execute("""
                DELETE FROM risk_parameters WHERE parameter_name = $1
            """, test_param_name)
            
            deleted_check = await self.connection.fetchval("""
                SELECT COUNT(*) FROM risk_parameters WHERE parameter_name = $1
            """, test_param_name)
            
            if deleted_check == 0:
                self.add_result("CRUD_TEST", "PASS", "✅ DELETE operation working")
            else:
                self.add_result("CRUD_TEST", "FAIL", "❌ DELETE test failed")
                
        except Exception as e:
            self.add_result("CRUD_TEST", "FAIL", f"CRUD operations test failed: {e}")
            
    async def performance_checks(self):
        """Basic performance checks"""
        try:
            import time
            
            # Test query performance on main tables
            tables_to_test = ['trading_cycles', 'positions', 'risk_parameters', 'daily_risk_metrics']
            
            for table in tables_to_test:
                try:
                    start_time = time.time()
                    count = await self.connection.fetchval(f"SELECT COUNT(*) FROM {table}")
                    end_time = time.time()
                    
                    duration = (end_time - start_time) * 1000  # Convert to milliseconds
                    
                    if duration < 100:  # Less than 100ms
                        self.add_result("PERFORMANCE", "PASS", f"✅ {table}: Count query took {duration:.1f}ms ({count} rows)")
                    elif duration < 1000:  # Less than 1 second
                        self.add_result("PERFORMANCE", "WARNING", f"⚠️ {table}: Count query took {duration:.1f}ms ({count} rows)")
                    else:
                        self.add_result("PERFORMANCE", "FAIL", f"❌ {table}: Count query took {duration:.1f}ms ({count} rows) - too slow")
                        
                except Exception:
                    self.add_result("PERFORMANCE", "WARNING", f"⚠️ {table}: Could not test performance (table missing?)")
                    
            # Test a more complex query
            start_time = time.time()
            try:
                result = await self.connection.fetchval("""
                    SELECT COUNT(DISTINCT cycle_id) FROM positions 
                    WHERE status = 'open' AND created_at > NOW() - INTERVAL '30 days'
                """)
                end_time = time.time()
                duration = (end_time - start_time) * 1000
                
                self.add_result("PERFORMANCE", "PASS", f"✅ Complex query took {duration:.1f}ms (result: {result})")
            except Exception:
                self.add_result("PERFORMANCE", "WARNING", "⚠️ Complex query test failed")
                
        except Exception as e:
            self.add_result("PERFORMANCE", "FAIL", f"Performance tests failed: {e}")
            
    def generate_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "=" * 70)
        print("📊 VALIDATION REPORT - Catalyst Trading System v4.2")
        print("=" * 70)
        
        # Count results by status
        status_counts = {}
        for result in self.results:
            status = result.status
            status_counts[status] = status_counts.get(status, 0) + 1
            
        # Overall summary
        total_checks = len(self.results)
        pass_count = status_counts.get("PASS", 0)
        fail_count = status_counts.get("FAIL", 0)
        warning_count = status_counts.get("WARNING", 0)
        info_count = status_counts.get("INFO", 0)
        
        print(f"\n📈 SUMMARY")
        print(f"Total checks: {total_checks}")
        print(f"✅ Passed: {pass_count}")
        print(f"❌ Failed: {fail_count}")
        print(f"⚠️ Warnings: {warning_count}")
        print(f"ℹ️ Info: {info_count}")
        
        # Calculate overall health score
        health_score = (pass_count / (pass_count + fail_count)) * 100 if (pass_count + fail_count) > 0 else 0
        
        print(f"\n🎯 OVERALL HEALTH SCORE: {health_score:.1f}%")
        
        if health_score >= 90:
            print("🟢 EXCELLENT - Database is production ready!")
        elif health_score >= 75:
            print("🟡 GOOD - Minor issues need attention")
        elif health_score >= 50:
            print("🟠 FAIR - Several issues need fixing")
        else:
            print("🔴 POOR - Major issues require immediate attention")
            
        # Detailed results by component
        print(f"\n📋 DETAILED RESULTS")
        print("-" * 50)
        
        components = {}
        for result in self.results:
            comp = result.component
            if comp not in components:
                components[comp] = []
            components[comp].append(result)
            
        for component, results in components.items():
            print(f"\n🔧 {component}")
            for result in results:
                status_icon = {
                    "PASS": "✅",
                    "FAIL": "❌", 
                    "WARNING": "⚠️",
                    "INFO": "ℹ️"
                }.get(result.status, "❓")
                
                print(f"   {status_icon} {result.message}")
                
        # Critical issues summary
        critical_issues = [r for r in self.results if r.status == "FAIL"]
        if critical_issues:
            print(f"\n🚨 CRITICAL ISSUES REQUIRING ATTENTION:")
            print("-" * 50)
            for i, issue in enumerate(critical_issues, 1):
                print(f"{i}. {issue.component}: {issue.message}")
                
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        print("-" * 50)
        
        if fail_count == 0:
            print("✅ Database is fully compliant with v4.2 specifications!")
            print("✅ All services can be deployed safely")
            print("✅ Risk management system is properly configured")
        else:
            print("🔧 Fix critical issues before deploying services")
            print("🔧 Run database upgrade script if tables are missing")
            print("🔧 Check environment variables and permissions")
            
        if warning_count > 0:
            print("⚠️ Address warnings for optimal performance")
            print("⚠️ Consider adding missing indexes for better performance")
            
        print(f"\n📅 Validation completed at: {datetime.now().isoformat()}")
        print("=" * 70)
        
        # Return overall status
        return health_score >= 75

# === MAIN EXECUTION ===

async def main():
    """Main validation execution"""
    validator = DatabaseValidator()
    
    try:
        success = await validator.validate_all()
        
        # Exit code based on validation results
        if success:
            print("\n🎉 Database validation completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Database validation found critical issues!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Validation failed with error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("DATABASE_URL"):
        print("❌ ERROR: DATABASE_URL environment variable is required")
        print("\nUsage:")
        print("export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        print("python validate_v42_database.py")
        sys.exit(1)
        
    # Run validation
    asyncio.run(main())