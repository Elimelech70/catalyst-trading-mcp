#!/bin/bash
"""
Name of Application: Catalyst Trading System
Name of file: create_missing_directories.sh
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Create all missing directories and placeholders for Docker builds

REVISION HISTORY:
v4.2.0 (2025-09-20) - Complete directory structure creation
- Creates all directories expected by Dockerfiles
- Adds placeholder files to prevent empty directory issues
- Ensures Docker builds can complete successfully
- Includes README files explaining directory purposes
"""

echo "🏗️ Creating Missing Directories for Catalyst Trading System v4.2"
echo "================================================================"

# Create base service directories if they don't exist
echo "📁 Creating base service directories..."
mkdir -p services/{pattern,technical,news,reporting,risk-manager}

# Pattern Service Directories
echo "📊 Creating Pattern service directories..."
mkdir -p services/pattern/{models,patterns,data,config}
touch services/pattern/models/.gitkeep
touch services/pattern/patterns/.gitkeep
touch services/pattern/data/.gitkeep
touch services/pattern/config/.gitkeep

# Create Pattern README
cat > services/pattern/models/README.md << 'EOF'
# Pattern Detection Models

This directory contains machine learning models and configuration files for pattern detection.

## Contents:
- `*.pkl` - Trained pattern recognition models
- `*.json` - Model configuration files
- `*.yaml` - Pattern detection parameters

## Usage:
Models are loaded automatically by the pattern detection service.
EOF

cat > services/pattern/patterns/README.md << 'EOF'
# Pattern Definitions

This directory contains pattern definitions and templates.

## Contents:
- `*.py` - Pattern detection algorithms
- `*.json` - Pattern configuration files
- `*.yaml` - Pattern parameters

## Usage:
Pattern definitions are loaded by the pattern service.
EOF

# Technical Service Directories  
echo "📈 Creating Technical service directories..."
mkdir -p services/technical/{models,indicators,data,config}
touch services/technical/models/.gitkeep
touch services/technical/indicators/.gitkeep
touch services/technical/data/.gitkeep
touch services/technical/config/.gitkeep

# Create Technical README
cat > services/technical/indicators/README.md << 'EOF'
# Technical Indicators

This directory contains technical analysis indicators and calculations.

## Contents:
- `*.py` - Custom technical indicators
- `*.json` - Indicator configuration files
- `*.yaml` - Technical analysis parameters

## Usage:
Indicators are loaded by the technical analysis service.
EOF

# News Service Directories
echo "📰 Creating News service directories..."
mkdir -p services/news/{processors,sources,data,config}
touch services/news/processors/.gitkeep
touch services/news/sources/.gitkeep
touch services/news/data/.gitkeep
touch services/news/config/.gitkeep

# Create News README
cat > services/news/processors/README.md << 'EOF'
# News Processors

This directory contains news processing and sentiment analysis modules.

## Contents:
- `*.py` - News processing algorithms
- `*.json` - Processor configuration files
- `*.yaml` - Sentiment analysis parameters

## Usage:
Processors are loaded by the news analysis service.
EOF

cat > services/news/sources/README.md << 'EOF'
# News Sources

This directory contains news source configurations and adapters.

## Contents:
- `*.py` - News source adapters
- `*.json` - Source configuration files
- `*.yaml` - API endpoint configurations

## Usage:
Source configurations are loaded by the news service.
EOF

# Reporting Service Directories
echo "📊 Creating Reporting service directories..."
mkdir -p services/reporting/{static,charts,templates,data}
touch services/reporting/static/.gitkeep
touch services/reporting/charts/.gitkeep
touch services/reporting/templates/.gitkeep
touch services/reporting/data/.gitkeep

# Create Reporting README
cat > services/reporting/static/README.md << 'EOF'
# Static Assets

This directory contains static assets for the reporting service.

## Contents:
- `css/` - Stylesheets
- `js/` - JavaScript files
- `images/` - Image assets
- `fonts/` - Font files

## Usage:
Static files are served by the reporting service web interface.
EOF

cat > services/reporting/charts/README.md << 'EOF'
# Chart Templates

This directory contains chart templates and configurations.

## Contents:
- `*.json` - Chart configuration templates
- `*.yaml` - Chart styling parameters
- `*.py` - Custom chart generators

## Usage:
Chart templates are used by the reporting service.
EOF

# Risk Manager Service Directories (make sure it exists)
echo "🛡️ Creating Risk Manager service directories..."
mkdir -p services/risk-manager/{config,data,models}
touch services/risk-manager/config/.gitkeep
touch services/risk-manager/data/.gitkeep
touch services/risk-manager/models/.gitkeep

# Create Risk Manager README
cat > services/risk-manager/config/README.md << 'EOF'
# Risk Management Configuration

This directory contains risk management configuration files.

## Contents:
- `risk_parameters.yaml` - Risk parameter configurations
- `portfolio_limits.json` - Portfolio limit settings
- `emergency_procedures.yaml` - Emergency stop procedures

## Usage:
Configuration files are loaded by the risk management service.
EOF

# Scanner Service Directories (ensure complete)
echo "🔍 Creating Scanner service directories..."
mkdir -p services/scanner/{data,config,filters}
touch services/scanner/data/.gitkeep
touch services/scanner/config/.gitkeep
touch services/scanner/filters/.gitkeep

# Trading Service Directories
echo "💰 Creating Trading service directories..."
mkdir -p services/trading/{strategies,data,config}
touch services/trading/strategies/.gitkeep
touch services/trading/data/.gitkeep
touch services/trading/config/.gitkeep

# Orchestration Service Directories
echo "🎭 Creating Orchestration service directories..."
mkdir -p services/orchestration/{config,data,logs}
touch services/orchestration/config/.gitkeep
touch services/orchestration/data/.gitkeep
touch services/orchestration/logs/.gitkeep

# Create global directories that might be needed
echo "🌐 Creating global directories..."
mkdir -p {logs,data,models,config,reports,backups}
touch logs/.gitkeep
touch data/.gitkeep
touch models/.gitkeep
touch config/.gitkeep
touch reports/.gitkeep
touch backups/.gitkeep

# Create sample configuration files
echo "⚙️ Creating sample configuration files..."

# Sample pattern configuration
cat > services/pattern/config/patterns.yaml << 'EOF'
# Pattern Detection Configuration
patterns:
  hammer:
    confidence_threshold: 0.65
    body_ratio: 0.3
    wick_ratio: 2.0
  
  doji:
    confidence_threshold: 0.55
    body_ratio: 0.1
    
  engulfing:
    confidence_threshold: 0.70
    volume_confirmation: true

timeframes:
  - "1m"
  - "5m"
  - "15m"
  - "1h"
  - "1d"
EOF

# Sample technical indicators configuration
cat > services/technical/config/indicators.yaml << 'EOF'
# Technical Indicators Configuration
indicators:
  rsi:
    period: 14
    overbought: 70
    oversold: 30
    
  macd:
    fast: 12
    slow: 26
    signal: 9
    
  bollinger_bands:
    period: 20
    std_dev: 2.0
    
  moving_averages:
    sma_short: 20
    sma_long: 50
    ema_short: 9
    ema_long: 21
EOF

# Sample news sources configuration
cat > services/news/config/sources.yaml << 'EOF'
# News Sources Configuration
sources:
  alpha_vantage:
    enabled: true
    api_key_env: "ALPHA_VANTAGE_API_KEY"
    rate_limit: 5  # calls per minute
    
  finnhub:
    enabled: true
    api_key_env: "FINNHUB_API_KEY"
    rate_limit: 30  # calls per minute
    
  newsapi:
    enabled: true
    api_key_env: "NEWS_API_KEY"
    rate_limit: 100  # calls per day

sentiment:
  providers:
    - "textblob"
    - "vader"
  threshold: 0.1
EOF

# Sample risk management configuration
cat > services/risk-manager/config/risk_parameters.yaml << 'EOF'
# Risk Management Parameters
risk_limits:
  max_daily_loss: 2000.0
  max_position_risk: 0.02  # 2% per trade
  max_portfolio_risk: 0.05  # 5% total
  max_positions: 5
  position_size_multiplier: 1.0

stop_loss:
  atr_multiple: 2.0
  min_stop_distance: 0.01  # 1%
  max_stop_distance: 0.05  # 5%

take_profit:
  atr_multiple: 3.0
  risk_reward_ratio: 1.5

emergency:
  daily_loss_threshold: 0.8  # 80% of max daily loss
  consecutive_losses: 3
  drawdown_threshold: 0.1  # 10%
EOF

# Set appropriate permissions
echo "🔒 Setting directory permissions..."
find services/ -type d -exec chmod 755 {} \;
find services/ -type f -exec chmod 644 {} \;

# Create .gitkeep files for empty directories that might be needed
echo "📝 Creating .gitkeep files..."
find services/ -type d -empty -exec touch {}/.gitkeep \;

# Print summary
echo ""
echo "✅ Directory Structure Created Successfully!"
echo "=========================================="
echo ""
echo "📁 Created directories for:"
echo "  🛡️ Risk Manager (v4.2 NEW)"
echo "  🔍 Scanner" 
echo "  📊 Pattern Detection"
echo "  📈 Technical Analysis"
echo "  📰 News Analysis"
echo "  📊 Reporting"
echo "  💰 Trading"
echo "  🎭 Orchestration"
echo ""
echo "📄 Created configuration files:"
echo "  • Pattern detection parameters"
echo "  • Technical indicator settings"
echo "  • News source configurations"
echo "  • Risk management parameters"
echo ""
echo "🚀 Ready for Docker deployment!"
echo "Next step: python3 deploy_v42_simple.py"
echo ""

# List the structure for verification
echo "📋 Directory Structure:"
echo "======================"
tree services/ 2>/dev/null || find services/ -type d | sed 's/^/  /'
echo ""
echo "🎯 All Docker build dependencies satisfied!"
