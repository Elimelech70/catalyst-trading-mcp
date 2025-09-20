#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: simple_v42_env_setup.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Simple environment setup without heavy dependencies

REVISION HISTORY:
v4.2.0 (2025-09-20) - Dependency-free environment setup
- No external dependencies required
- Interactive configuration of all v4.2 variables
- Secure credential handling
- .env file generation with proper formatting
- Basic validation without connection testing

Description of Service:
Lightweight setup script that configures all required environment variables
for Catalyst Trading System v4.2 without requiring external dependencies.
Connection testing will be done during actual deployment.
"""

import os
import sys
import getpass
from typing import Dict, Optional
from datetime import datetime

class SimpleEnvironmentSetup:
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
        
    def setup_database_url(self):
        """Setup database URL"""
        print("\n🗄️ DATABASE CONFIGURATION")
        print("-" * 40)
        
        existing = self.existing_env.get("DATABASE_URL", "")
        if existing:
            print(f"Current: {existing[:50]}...")
            use_existing = self.get_input("Use existing database URL? (y/n)", "y").lower()
            if use_existing == 'y':
                self.env_vars["DATABASE_URL"] = existing
                print("✅ Using existing database URL")
                return
                
        print("\nEnter your DigitalOcean PostgreSQL connection details:")
        print("(You can find these in your DigitalOcean dashboard)")
        
        # Get connection components
        host = self.get_input("Database Host (e.g., db-postgresql-nyc3-12345-do-user-67890-0.b.db.ondigitalocean.com)")
        port = self.get_input("Database Port", "25060")
        database = self.get_input("Database Name", "catalyst_trading")
        username = self.get_input("Database Username", "doadmin")
        password = self.get_input("Database Password", secret=True)
        
        if not all([host, port, database, username, password]):
            print("❌ All database fields are required!")
            return self.setup_database_url()
            
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
            use_existing = self.get_input("Use existing Redis URL? (y/n)", "y").lower()
            if use_existing == 'y':
                self.env_vars["REDIS_URL"] = existing
                self.env_vars["REDIS_PASSWORD"] = self.existing_env.get("REDIS_PASSWORD", "RedisCatalyst2025!SecureCache")
                print("✅ Using existing Redis URL")
                return
                
        # Use Docker Redis (simplest option)
        print("Using Docker Redis (recommended for initial setup)")
        redis_password = self.get_input("Redis Password", "RedisCatalyst2025!SecureCache")
        redis_url = f"redis://:{redis_password}@redis:6379/0"
                
        self.env_vars["REDIS_URL"] = redis_url
        self.env_vars["REDIS_PASSWORD"] = redis_password
        print("✅ Redis URL configured for Docker")
        
    def setup_api_keys(self):
        """Setup API keys"""
        print("\n🔑 API KEYS CONFIGURATION")
        print("-" * 40)
        
        # Alpha Vantage API Key
        print("\n📊 Alpha Vantage API Key (for market data)")
        print("🔗 Get free key at: https://www.alphavantage.co/support/#api-key")
        
        existing_av = self.existing_env.get("ALPHA_VANTAGE_API_KEY", "")
        if existing_av:
            print(f"Current: {existing_av[:8]}***")
            
        alpha_vantage_key = self.get_input("Alpha Vantage API Key", existing_av)
        
        if not alpha_vantage_key:
            print("⚠️ Alpha Vantage API key is required for market data")
            print("Please get a free key and run this setup again")
            
        self.env_vars["ALPHA_VANTAGE_API_KEY"] = alpha_vantage_key
        
        # Finnhub API Key
        print("\n📈 Finnhub API Key (for real-time data)")
        print("🔗 Get free key at: https://finnhub.io/register")
        
        existing_fh = self.existing_env.get("FINNHUB_API_KEY", "")
        if existing_fh:
            print(f"Current: {existing_fh[:8]}***")
            
        finnhub_key = self.get_input("Finnhub API Key", existing_fh)
        
        if not finnhub_key:
            print("⚠️ Finnhub API key is required for real-time data")
            print("Please get a free key and run this setup again")
            
        self.env_vars["FINNHUB_API_KEY"] = finnhub_key
        
        print("✅ API keys configured")
        
    def setup_risk_parameters(self):
        """Setup risk management parameters (NEW in v4.2)"""
        print("\n🛡️ RISK MANAGEMENT PARAMETERS (v4.2)")
        print("-" * 40)
        print("Configure safety limits for automated trading:")
        print("(These are critical for protecting your capital)")
        
        # Max Daily Loss
        existing_loss = self.existing_env.get("MAX_DAILY_LOSS", "2000")
        print(f"\n💰 Maximum Daily Loss Limit")
        print("How much money are you willing to lose in a single day?")
        max_daily_loss = self.get_input("Maximum Daily Loss ($)", existing_loss)
        self.env_vars["MAX_DAILY_LOSS"] = max_daily_loss
        
        # Max Position Risk
        existing_pos_risk = self.existing_env.get("MAX_POSITION_RISK", "0.02")
        print(f"\n📊 Position Risk Limit")
        print("What percentage of your account can each trade risk?")
        print("0.01 = 1%, 0.02 = 2%, 0.05 = 5%")
        max_position_risk = self.get_input("Maximum Position Risk", existing_pos_risk)
        self.env_vars["MAX_POSITION_RISK"] = max_position_risk
        
        # Position Size Multiplier
        existing_multiplier = self.existing_env.get("POSITION_SIZE_MULTIPLIER", "1.0")
        print(f"\n⚖️ Position Size Multiplier")
        print("Adjustment factor for position sizes (1.0 = normal, 0.5 = half size, 2.0 = double)")
        position_multiplier = self.get_input("Position Size Multiplier", existing_multiplier)
        self.env_vars["POSITION_SIZE_MULTIPLIER"] = position_multiplier
        
        # Max Portfolio Risk
        existing_portfolio_risk = self.existing_env.get("MAX_PORTFOLIO_RISK", "0.05")
        print(f"\n🏦 Total Portfolio Risk")
        print("Maximum total risk across all positions combined")
        max_portfolio_risk = self.get_input("Maximum Portfolio Risk", existing_portfolio_risk)
        self.env_vars["MAX_PORTFOLIO_RISK"] = max_portfolio_risk
        
        # Risk Free Rate
        existing_risk_free = self.existing_env.get("RISK_FREE_RATE", "0.05")
        print(f"\n📈 Risk Free Rate")
        print("Current risk-free rate for performance calculations (e.g., 10-year Treasury)")
        risk_free_rate = self.get_input("Risk Free Rate", existing_risk_free)
        self.env_vars["RISK_FREE_RATE"] = risk_free_rate
        
        # Max Positions
        existing_max_pos = self.existing_env.get("MAX_POSITIONS", "5")
        print(f"\n🔢 Maximum Positions")
        print("Maximum number of trades open at the same time")
        max_positions = self.get_input("Maximum Concurrent Positions", existing_max_pos)
        self.env_vars["MAX_POSITIONS"] = max_positions
        
        print("✅ Risk parameters configured")
        
        # Show summary of risk settings
        print(f"\n📋 RISK SUMMARY:")
        print(f"• Daily loss limit: ${max_daily_loss}")
        print(f"• Risk per trade: {float(max_position_risk)*100:.1f}%")
        print(f"• Total portfolio risk: {float(max_portfolio_risk)*100:.1f}%")
        print(f"• Max positions: {max_positions}")
        
    def setup_trading_parameters(self):
        """Setup trading-specific parameters"""
        print("\n💰 TRADING PARAMETERS")
        print("-" * 40)
        
        # Account size
        existing_balance = self.existing_env.get("ACCOUNT_BALANCE", "10000")
        print("What is your trading account size?")
        account_balance = self.get_input("Account Balance ($)", existing_balance)
        self.env_vars["ACCOUNT_BALANCE"] = account_balance
        
        # Trading mode
        existing_mode = self.existing_env.get("DEFAULT_TRADING_MODE", "normal")
        print("\nChoose your default trading mode:")
        print("• conservative: Lower risk, fewer trades")
        print("• normal: Balanced approach")
        print("• aggressive: Higher risk, more trades")
        trading_mode = self.get_input("Default Trading Mode", existing_mode)
        self.env_vars["DEFAULT_TRADING_MODE"] = trading_mode
        
        # Scan frequency
        existing_freq = self.existing_env.get("SCAN_FREQUENCY", "300")
        print("\nHow often should the system scan for opportunities?")
        print("300 = 5 minutes, 600 = 10 minutes, 900 = 15 minutes")
        scan_frequency = self.get_input("Market Scan Frequency (seconds)", existing_freq)
        self.env_vars["SCAN_FREQUENCY"] = scan_frequency
        
        print("✅ Trading parameters configured")
        
    def setup_service_ports(self):
        """Setup service port configuration"""
        print("\n🔌 SERVICE PORTS (v4.2)")
        print("-" * 40)
        print("Using standard port configuration (you can change these later)")
        
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
        
        use_defaults = self.get_input("Use default ports (5000-5009)? (y/n)", "y").lower()
        
        if use_defaults == 'y':
            self.env_vars.update(ports)
            print("✅ Default ports configured")
        else:
            for env_var, default_port in ports.items():
                service_name = env_var.replace('_PORT', '').replace('_', ' ').title()
                port = self.get_input(f"{service_name} Port", default_port)
                self.env_vars[env_var] = port
            print("✅ Custom ports configured")
            
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
            
            # Set proper permissions
            os.chmod('.env', 0o600)
            print("✅ .env file permissions set to 600 (owner read/write only)")
            
        except Exception as e:
            print(f"❌ Failed to generate .env file: {e}")
            return False
            
        return True
        
    def print_summary(self):
        """Print setup summary"""
        print("\n" + "=" * 60)
        print("🎯 CATALYST TRADING SYSTEM v4.2 ENVIRONMENT SETUP COMPLETE")
        print("=" * 60)
        
        print(f"📅 Setup completed at: {datetime.now().isoformat()}")
        print(f"📁 Environment file: {os.path.abspath('.env')}")
        
        print(f"\n📋 CONFIGURATION SUMMARY:")
        print(f"🗄️ Database: {self.env_vars['DATABASE_URL'][:50]}...")
        print(f"🛡️ Daily Loss Limit: ${self.env_vars['MAX_DAILY_LOSS']}")
        print(f"📊 Position Risk: {float(self.env_vars['MAX_POSITION_RISK'])*100:.1f}% per trade")
        print(f"🔢 Max Positions: {self.env_vars['MAX_POSITIONS']}")
        print(f"💰 Account Size: ${self.env_vars['ACCOUNT_BALANCE']}")
        print(f"⚙️ Trading Mode: {self.env_vars['DEFAULT_TRADING_MODE']}")
        
        print(f"\n🚀 NEXT STEPS:")
        print("1. ✅ Environment configured - ready for deployment!")
        print("2. 🚀 Deploy services: python3 ./scripts/deploy_v42_services.py")
        print("3. 🧪 Test deployment: docker-compose ps")
        print("4. 📊 Monitor services: docker-compose logs -f")
        
        print(f"\n🔒 SECURITY NOTES:")
        print("• .env file permissions set to 600 (secure)")
        print("• Backup created of previous .env file")
        print("• Never commit .env to version control")
        
        print(f"\n⚠️ IMPORTANT:")
        print("• Connection testing will happen during deployment")
        print("• Make sure your API keys are valid before deploying")
        print("• Review risk parameters - they control your trading safety!")
        
        print("\n🎉 Ready to deploy Catalyst Trading System v4.2!")
        
    def run_setup(self):
        """Run complete setup process"""
        print("🎯 Catalyst Trading System v4.2 Environment Setup")
        print("=" * 60)
        print("This script will configure all required environment variables")
        print("for the v4.2 deployment with risk management.\n")
        
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
            
            # Generate .env file
            if self.generate_env_file():
                self.print_summary()
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

def main():
    """Main setup function"""
    if os.geteuid() == 0:
        print("⚠️ Warning: Running as root user")
        
    setup = SimpleEnvironmentSetup()
    success = setup.run_setup()
    
    if success:
        print("\n✅ Environment setup completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Environment setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(130)