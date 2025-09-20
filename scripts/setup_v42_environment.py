#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: setup_v42_environment.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Interactive environment variable setup for v4.2 deployment

REVISION HISTORY:
v4.2.0 (2025-09-20) - Complete v4.2 environment setup
- Interactive configuration of all required variables
- Validation of database and Redis connections
- API key validation and testing
- Risk management parameter setup
- Secure credential handling
- .env file generation with proper formatting
- Environment validation and testing

Description of Service:
Interactive setup script that guides users through configuring all required
environment variables for the Catalyst Trading System v4.2, including the
new risk management parameters and API credentials.
"""

import os
import sys
import getpass
import asyncio
import asyncpg
import aioredis
import aiohttp
from typing import Dict, Optional, Tuple
import re
from datetime import datetime
import json

class EnvironmentSetup:
    def __init__(self):
        self.env_vars: Dict[str, str] = {}
        self.existing_env: Dict[str, str] = {}
        self.load_existing_env()
        
    def load_existing_env(self):
        """Load existing .env file if it exists"""
        if os.path.exists('.env'):
            try:
                with open('.env', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self.existing_env[key] = value.strip('"\'')
                print(f"✅ Loaded {len(self.existing_env)} existing environment variables")
            except Exception as e:
                print(f"⚠️ Could not load existing .env file: {e}")
        else:
            print("ℹ️ No existing .env file found - will create new one")
            
    def get_input(self, prompt: str, default: Optional[str] = None, secret: bool = False) -> str:
        """Get user input with optional default and secret handling"""
        if default:
            display_prompt = f"{prompt} [{default}]: "
        else:
            display_prompt = f"{prompt}: "
            
        if secret:
            value = getpass.getpass(display_prompt)
        else:
            value = input(display_prompt)
            
        return value.strip() if value.strip() else (default or "")
        
    def validate_url(self, url: str, url_type: str) -> bool:
        """Validate URL format"""
        if url_type == "database":
            return url.startswith("postgresql://") or url.startswith("postgres://")
        elif url_type == "redis":
            return url.startswith("redis://") or url.startswith("rediss://")
        return False
        
    async def test_database_connection(self, database_url: str) -> bool:
        """Test database connection"""
        try:
            conn = await asyncpg.connect(database_url)
            result = await conn.fetchval("SELECT 1")
            await conn.close()
            return result == 1
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
            
    async def test_redis_connection(self, redis_url: str) -> bool:
        """Test Redis connection"""
        try:
            redis = aioredis.from_url(redis_url)
            await redis.ping()
            await redis.close()
            return True
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return False
            
    async def test_api_key(self, api_key: str, provider: str) -> bool:
        """Test API key validity"""
        try:
            async with aiohttp.ClientSession() as session:
                if provider == "alpha_vantage":
                    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={api_key}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return "Global Quote" in data
                            
                elif provider == "finnhub":
                    url = f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={api_key}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return "c" in data  # Current price field
                            
        except Exception as e:
            print(f"❌ API test failed for {provider}: {e}")
            
        return False
        
    def setup_database_url(self):
        """Setup database URL"""
        print("\n🗄️ DATABASE CONFIGURATION")
        print("-" * 40)
        
        existing = self.existing_env.get("DATABASE_URL", "")
        if existing:
            print(f"Current: {existing[:50]}...")
            
        print("Enter your DigitalOcean PostgreSQL connection details:")
        
        # Get connection components
        host = self.get_input("Database Host", 
                             existing.split('@')[1].split(':')[0] if existing and '@' in existing else "")
        port = self.get_input("Database Port", "25060")
        database = self.get_input("Database Name", "catalyst_trading")
        username = self.get_input("Database Username", "doadmin")
        password = self.get_input("Database Password", secret=True)
        
        # Build URL
        database_url = f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require"
        
        self.env_vars["DATABASE_URL"] = database_url
        print("✅ Database URL configured")
        
    def setup_redis_url(self):
        """Setup Redis URL"""
        print("\n🔴 REDIS CONFIGURATION")
        print("-" * 40)
        
        existing = self.existing_env.get("REDIS_URL", "")
        if existing:
            print(f"Current: {existing[:50]}...")
            
        # Option for internal Redis (via Docker) or external
        use_docker = self.get_input("Use Docker Redis? (y/n)", "y").lower() == 'y'
        
        if use_docker:
            # Default Docker Redis setup
            redis_password = self.get_input("Redis Password", "RedisCatalyst2025!SecureCache")
            redis_url = f"redis://:{redis_password}@redis:6379/0"
        else:
            # External Redis
            print("Enter your external Redis connection details:")
            host = self.get_input("Redis Host", "localhost")
            port = self.get_input("Redis Port", "6379")
            password = self.get_input("Redis Password (optional)", secret=True)
            database = self.get_input("Redis Database", "0")
            
            if password:
                redis_url = f"redis://:{password}@{host}:{port}/{database}"
            else:
                redis_url = f"redis://{host}:{port}/{database}"
                
        self.env_vars["REDIS_URL"] = redis_url
        self.env_vars["REDIS_PASSWORD"] = password if 'password' in locals() else "RedisCatalyst2025!SecureCache"
        print("✅ Redis URL configured")
        
    def setup_api_keys(self):
        """Setup API keys"""
        print("\n🔑 API KEYS CONFIGURATION")
        print("-" * 40)
        
        # Alpha Vantage API Key
        print("\n📊 Alpha Vantage API Key (for market data)")
        print("Get free key at: https://www.alphavantage.co/support/#api-key")
        
        existing_av = self.existing_env.get("ALPHA_VANTAGE_API_KEY", "")
        if existing_av:
            print(f"Current: {existing_av[:8]}***")
            
        alpha_vantage_key = self.get_input("Alpha Vantage API Key", existing_av)
        self.env_vars["ALPHA_VANTAGE_API_KEY"] = alpha_vantage_key
        
        # Finnhub API Key
        print("\n📈 Finnhub API Key (for real-time data)")
        print("Get free key at: https://finnhub.io/register")
        
        existing_fh = self.existing_env.get("FINNHUB_API_KEY", "")
        if existing_fh:
            print(f"Current: {existing_fh[:8]}***")
            
        finnhub_key = self.get_input("Finnhub API Key", existing_fh)
        self.env_vars["FINNHUB_API_KEY"] = finnhub_key
        
        print("✅ API keys configured")
        
    def setup_risk_parameters(self):
        """Setup risk management parameters (NEW in v4.2)"""
        print("\n🛡️ RISK MANAGEMENT PARAMETERS (v4.2)")
        print("-" * 40)
        print("Configure safety limits for automated trading:")
        
        # Max Daily Loss
        existing_loss = self.existing_env.get("MAX_DAILY_LOSS", "2000")
        max_daily_loss = self.get_input("Maximum Daily Loss ($)", existing_loss)
        self.env_vars["MAX_DAILY_LOSS"] = max_daily_loss
        
        # Max Position Risk
        existing_pos_risk = self.existing_env.get("MAX_POSITION_RISK", "0.02")
        max_position_risk = self.get_input("Maximum Position Risk (0.02 = 2%)", existing_pos_risk)
        self.env_vars["MAX_POSITION_RISK"] = max_position_risk
        
        # Position Size Multiplier
        existing_multiplier = self.existing_env.get("POSITION_SIZE_MULTIPLIER", "1.0")
        position_multiplier = self.get_input("Position Size Multiplier", existing_multiplier)
        self.env_vars["POSITION_SIZE_MULTIPLIER"] = position_multiplier
        
        # Max Portfolio Risk
        existing_portfolio_risk = self.existing_env.get("MAX_PORTFOLIO_RISK", "0.05")
        max_portfolio_risk = self.get_input("Maximum Portfolio Risk (0.05 = 5%)", existing_portfolio_risk)
        self.env_vars["MAX_PORTFOLIO_RISK"] = max_portfolio_risk
        
        # Risk Free Rate
        existing_risk_free = self.existing_env.get("RISK_FREE_RATE", "0.05")
        risk_free_rate = self.get_input("Risk Free Rate (0.05 = 5%)", existing_risk_free)
        self.env_vars["RISK_FREE_RATE"] = risk_free_rate
        
        # Max Positions
        existing_max_pos = self.existing_env.get("MAX_POSITIONS", "5")
        max_positions = self.get_input("Maximum Concurrent Positions", existing_max_pos)
        self.env_vars["MAX_POSITIONS"] = max_positions
        
        print("✅ Risk parameters configured")
        
    def setup_trading_parameters(self):
        """Setup trading-specific parameters"""
        print("\n💰 TRADING PARAMETERS")
        print("-" * 40)
        
        # Account size
        existing_balance = self.existing_env.get("ACCOUNT_BALANCE", "10000")
        account_balance = self.get_input("Account Balance ($)", existing_balance)
        self.env_vars["ACCOUNT_BALANCE"] = account_balance
        
        # Trading mode
        existing_mode = self.existing_env.get("DEFAULT_TRADING_MODE", "normal")
        trading_mode = self.get_input("Default Trading Mode (aggressive/normal/conservative)", existing_mode)
        self.env_vars["DEFAULT_TRADING_MODE"] = trading_mode
        
        # Scan frequency
        existing_freq = self.existing_env.get("SCAN_FREQUENCY", "300")
        scan_frequency = self.get_input("Market Scan Frequency (seconds)", existing_freq)
        self.env_vars["SCAN_FREQUENCY"] = scan_frequency
        
        print("✅ Trading parameters configured")
        
    def setup_service_ports(self):
        """Setup service port configuration"""
        print("\n🔌 SERVICE PORTS (v4.2)")
        print("-" * 40)
        
        ports = {
            "ORCHESTRATION_PORT": "5000",
            "SCANNER_PORT": "5001", 
            "PATTERN_PORT": "5002",
            "TECHNICAL_PORT": "5003",
            "RISK_MANAGER_PORT": "5004",  # NEW in v4.2
            "TRADING_PORT": "5005",
            "NEWS_PORT": "5008",
            "REPORTING_PORT": "5009"
        }
        
        for env_var, default_port in ports.items():
            existing = self.existing_env.get(env_var, default_port)
            port = self.get_input(f"{env_var.replace('_', ' ').title()}", existing)
            self.env_vars[env_var] = port
            
        print("✅ Service ports configured")
        
    def setup_optional_parameters(self):
        """Setup optional parameters"""
        print("\n⚙️ OPTIONAL PARAMETERS")
        print("-" * 40)
        
        # Logging level
        existing_log = self.existing_env.get("LOG_LEVEL", "INFO")
        log_level = self.get_input("Log Level (DEBUG/INFO/WARNING/ERROR)", existing_log)
        self.env_vars["LOG_LEVEL"] = log_level
        
        # Environment
        existing_env_type = self.existing_env.get("ENVIRONMENT", "production")
        env_type = self.get_input("Environment Type (development/staging/production)", existing_env_type)
        self.env_vars["ENVIRONMENT"] = env_type
        
        # Debug mode
        existing_debug = self.existing_env.get("DEBUG", "false")
        debug = self.get_input("Debug Mode (true/false)", existing_debug)
        self.env_vars["DEBUG"] = debug
        
        print("✅ Optional parameters configured")
        
    async def validate_connections(self):
        """Validate all configured connections"""
        print("\n🔍 VALIDATING CONNECTIONS")
        print("-" * 40)
        
        validation_results = []
        
        # Test Database
        print("🗄️ Testing database connection...")
        try:
            db_valid = await self.test_database_connection(self.env_vars["DATABASE_URL"])
            if db_valid:
                print("✅ Database connection successful")
                validation_results.append(("Database", True))
            else:
                print("❌ Database connection failed")
                validation_results.append(("Database", False))
        except Exception as e:
            print(f"❌ Database test error: {e}")
            validation_results.append(("Database", False))
            
        # Test Redis (only if not using Docker)
        if not self.env_vars["REDIS_URL"].startswith("redis://:"):
            print("🔴 Testing Redis connection...")
            try:
                redis_valid = await self.test_redis_connection(self.env_vars["REDIS_URL"])
                if redis_valid:
                    print("✅ Redis connection successful")
                    validation_results.append(("Redis", True))
                else:
                    print("❌ Redis connection failed")
                    validation_results.append(("Redis", False))
            except Exception as e:
                print(f"❌ Redis test error: {e}")
                validation_results.append(("Redis", False))
        else:
            print("ℹ️ Redis (Docker) - will validate during deployment")
            validation_results.append(("Redis", True))
            
        # Test API Keys
        if self.env_vars.get("ALPHA_VANTAGE_API_KEY"):
            print("📊 Testing Alpha Vantage API...")
            av_valid = await self.test_api_key(self.env_vars["ALPHA_VANTAGE_API_KEY"], "alpha_vantage")
            if av_valid:
                print("✅ Alpha Vantage API key valid")
                validation_results.append(("Alpha Vantage", True))
            else:
                print("❌ Alpha Vantage API key invalid")
                validation_results.append(("Alpha Vantage", False))
                
        if self.env_vars.get("FINNHUB_API_KEY"):
            print("📈 Testing Finnhub API...")
            fh_valid = await self.test_api_key(self.env_vars["FINNHUB_API_KEY"], "finnhub")
            if fh_valid:
                print("✅ Finnhub API key valid")
                validation_results.append(("Finnhub", True))
            else:
                print("❌ Finnhub API key invalid")
                validation_results.append(("Finnhub", False))
                
        return validation_results
        
    def generate_env_file(self):
        """Generate .env file"""
        print("\n📝 GENERATING .ENV FILE")
        print("-" * 40)
        
        # Create backup of existing file
        if os.path.exists('.env'):
            backup_name = f'.env.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            os.rename('.env', backup_name)
            print(f"✅ Backed up existing .env to {backup_name}")
            
        # Generate new .env file
        try:
            with open('.env', 'w') as f:
                f.write("# Catalyst Trading System v4.2 Environment Configuration\n")
                f.write(f"# Generated on {datetime.now().isoformat()}\n")
                f.write("# DO NOT COMMIT THIS FILE TO VERSION CONTROL\n\n")
                
                # Database Configuration
                f.write("# Database Configuration\n")
                f.write(f'DATABASE_URL="{self.env_vars["DATABASE_URL"]}"\n\n')
                
                # Redis Configuration
                f.write("# Redis Configuration\n")
                f.write(f'REDIS_URL="{self.env_vars["REDIS_URL"]}"\n')
                f.write(f'REDIS_PASSWORD="{self.env_vars["REDIS_PASSWORD"]}"\n\n')
                
                # API Keys
                f.write("# API Keys\n")
                f.write(f'ALPHA_VANTAGE_API_KEY="{self.env_vars["ALPHA_VANTAGE_API_KEY"]}"\n')
                f.write(f'FINNHUB_API_KEY="{self.env_vars["FINNHUB_API_KEY"]}"\n\n')
                
                # Risk Management (NEW in v4.2)
                f.write("# Risk Management Parameters (v4.2)\n")
                f.write(f'MAX_DAILY_LOSS={self.env_vars["MAX_DAILY_LOSS"]}\n')
                f.write(f'MAX_POSITION_RISK={self.env_vars["MAX_POSITION_RISK"]}\n')
                f.write(f'POSITION_SIZE_MULTIPLIER={self.env_vars["POSITION_SIZE_MULTIPLIER"]}\n')
                f.write(f'MAX_PORTFOLIO_RISK={self.env_vars["MAX_PORTFOLIO_RISK"]}\n')
                f.write(f'RISK_FREE_RATE={self.env_vars["RISK_FREE_RATE"]}\n')
                f.write(f'MAX_POSITIONS={self.env_vars["MAX_POSITIONS"]}\n\n')
                
                # Trading Parameters
                f.write("# Trading Parameters\n")
                f.write(f'ACCOUNT_BALANCE={self.env_vars["ACCOUNT_BALANCE"]}\n')
                f.write(f'DEFAULT_TRADING_MODE={self.env_vars["DEFAULT_TRADING_MODE"]}\n')
                f.write(f'SCAN_FREQUENCY={self.env_vars["SCAN_FREQUENCY"]}\n\n')
                
                # Service Ports
                f.write("# Service Ports (v4.2)\n")
                f.write(f'ORCHESTRATION_PORT={self.env_vars["ORCHESTRATION_PORT"]}\n')
                f.write(f'SCANNER_PORT={self.env_vars["SCANNER_PORT"]}\n')
                f.write(f'PATTERN_PORT={self.env_vars["PATTERN_PORT"]}\n')
                f.write(f'TECHNICAL_PORT={self.env_vars["TECHNICAL_PORT"]}\n')
                f.write(f'RISK_MANAGER_PORT={self.env_vars["RISK_MANAGER_PORT"]}\n')
                f.write(f'TRADING_PORT={self.env_vars["TRADING_PORT"]}\n')
                f.write(f'NEWS_PORT={self.env_vars["NEWS_PORT"]}\n')
                f.write(f'REPORTING_PORT={self.env_vars["REPORTING_PORT"]}\n\n')
                
                # Optional Parameters
                f.write("# Optional Parameters\n")
                f.write(f'LOG_LEVEL={self.env_vars["LOG_LEVEL"]}\n')
                f.write(f'ENVIRONMENT={self.env_vars["ENVIRONMENT"]}\n')
                f.write(f'DEBUG={self.env_vars["DEBUG"]}\n')
                
            print("✅ .env file generated successfully")
            
        except Exception as e:
            print(f"❌ Failed to generate .env file: {e}")
            return False
            
        return True
        
    def print_summary(self, validation_results):
        """Print setup summary"""
        print("\n" + "=" * 60)
        print("🎯 CATALYST TRADING SYSTEM v4.2 ENVIRONMENT SETUP COMPLETE")
        print("=" * 60)
        
        print(f"📅 Setup completed at: {datetime.now().isoformat()}")
        print(f"📁 Environment file: {os.path.abspath('.env')}")
        
        print(f"\n🔍 VALIDATION RESULTS:")
        for component, status in validation_results:
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {component}")
            
        # Count successful validations
        successful = sum(1 for _, status in validation_results if status)
        total = len(validation_results)
        
        print(f"\n📊 Overall: {successful}/{total} validations passed")
        
        if successful == total:
            print("🟢 All validations passed - ready for deployment!")
            
            print(f"\n🚀 NEXT STEPS:")
            print("1. 🔒 Secure your .env file: chmod 600 .env")
            print("2. 🚀 Deploy services: python3 ./scripts/deploy_v42_services.py")
            print("3. 🧪 Test deployment: docker-compose ps")
            print("4. 📊 Monitor services: docker-compose logs -f")
            
        else:
            print("🟡 Some validations failed - review and fix before deployment")
            
            print(f"\n🛠️ TROUBLESHOOTING:")
            print("• Check database credentials and network access")
            print("• Verify API keys are active and have proper permissions")
            print("• Ensure Redis server is accessible")
            print("• Test connections manually if needed")
            
        print(f"\n📋 CONFIGURATION SUMMARY:")
        print(f"• Database: {self.env_vars['DATABASE_URL'][:30]}...")
        print(f"• Risk Management: ${self.env_vars['MAX_DAILY_LOSS']} daily limit")
        print(f"• Position Risk: {float(self.env_vars['MAX_POSITION_RISK'])*100:.1f}% per trade")
        print(f"• Max Positions: {self.env_vars['MAX_POSITIONS']}")
        print(f"• Account Size: ${self.env_vars['ACCOUNT_BALANCE']}")
        
        print("\n🎉 Ready to deploy Catalyst Trading System v4.2!")
        
    async def run_setup(self):
        """Run complete setup process"""
        print("🎯 Catalyst Trading System v4.2 Environment Setup")
        print("=" * 60)
        print("This script will guide you through configuring all required")
        print("environment variables for the v4.2 deployment.\n")
        
        try:
            # Core configuration
            self.setup_database_url()
            self.setup_redis_url()
            self.setup_api_keys()
            
            # NEW in v4.2: Risk Management
            self.setup_risk_parameters()
            
            # Trading and service configuration
            self.setup_trading_parameters()
            self.setup_service_ports()
            self.setup_optional_parameters()
            
            # Validate connections
            validation_results = await self.validate_connections()
            
            # Generate .env file
            if self.generate_env_file():
                self.print_summary(validation_results)
                return True
            else:
                print("❌ Failed to generate environment file")
                return False
                
        except KeyboardInterrupt:
            print("\n⚠️ Setup interrupted by user")
            return False
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            return False

async def main():
    """Main setup function"""
    if os.geteuid() == 0:
        print("⚠️ Warning: Running as root user")
        
    setup = EnvironmentSetup()
    success = await setup.run_setup()
    
    if success:
        print("\n✅ Environment setup completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Environment setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(130)