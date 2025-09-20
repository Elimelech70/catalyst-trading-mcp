#!/usr/bin/env python3
"""
Wrapper script to load .env file and run deployment
"""

import os
import sys
import subprocess

def load_env_file():
    """Load .env file into environment variables"""
    env_file = '.env'
    
    if not os.path.exists(env_file):
        print("❌ .env file not found!")
        return False
        
    print("🔧 Loading environment variables from .env file...")
    
    with open(env_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
                
            # Skip lines without =
            if '=' not in line:
                continue
                
            try:
                # Split on first = only
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                    
                # Set environment variable
                os.environ[key] = value
                
            except Exception as e:
                print(f"⚠️ Warning: Could not parse line {line_num}: {line}")
                continue
    
    return True

def verify_required_vars():
    """Verify all required variables are loaded"""
    required_vars = [
        'DATABASE_URL',
        'REDIS_URL', 
        'ALPHA_VANTAGE_API_KEY',
        'FINNHUB_API_KEY',
        'MAX_DAILY_LOSS',
        'MAX_POSITION_RISK'
    ]
    
    missing = []
    present = []
    
    print("\n🔍 Checking required environment variables:")
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            present.append(var)
            # Show partial value for security
            display_value = value[:10] + "***" if len(value) > 10 else value
            print(f"✅ {var}: {display_value}")
        else:
            missing.append(var)
            print(f"❌ {var}: Not found")
            
    # Handle MAX_POSITION_RISK specifically (might be named RISK_PER_TRADE)
    if 'MAX_POSITION_RISK' in missing:
        risk_per_trade = os.environ.get('RISK_PER_TRADE')
        if risk_per_trade:
            os.environ['MAX_POSITION_RISK'] = risk_per_trade
            missing.remove('MAX_POSITION_RISK')
            present.append('MAX_POSITION_RISK')
            print(f"✅ MAX_POSITION_RISK: {risk_per_trade} (mapped from RISK_PER_TRADE)")
    
    # Add any missing v4.2 variables with defaults
    v42_defaults = {
        'POSITION_SIZE_MULTIPLIER': '1.0',
        'RISK_FREE_RATE': '0.05'
    }
    
    for var, default in v42_defaults.items():
        if not os.environ.get(var):
            os.environ[var] = default
            print(f"✅ {var}: {default} (default)")
    
    if missing:
        print(f"\n❌ Missing variables: {', '.join(missing)}")
        return False
    else:
        print(f"\n✅ All required variables present ({len(present)} total)")
        return True

def main():
    print("🎯 Catalyst Trading System v4.2 Deployment with .env Loader")
    print("=" * 65)
    
    # Load .env file
    if not load_env_file():
        sys.exit(1)
        
    # Verify required variables
    if not verify_required_vars():
        print("\n💡 Suggested fixes:")
        print("1. Check your .env file for missing variables")
        print("2. Ensure no spaces around = signs")
        print("3. Make sure values are not empty")
        sys.exit(1)
    
    # Run the deployment script
    print("\n🚀 Starting deployment script...")
    print("-" * 40)
    
    try:
        # Run deployment script with inherited environment
        result = subprocess.run([
            sys.executable, 
            './scripts/deploy_v42_simple.py'
        ], env=os.environ.copy())
        
        sys.exit(result.returncode)
        
    except FileNotFoundError:
        print("❌ Deployment script not found: ./scripts/deploy_v42_services.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to run deployment script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()