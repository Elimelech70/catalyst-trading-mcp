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

# Create placeholder Python files for processors, indicators, patterns
echo "🐍 Creating placeholder Python files..."

# Pattern detection placeholder files
cat > services/pattern/patterns/__init__.py << 'EOF'
"""
Pattern Detection Module
Placeholder file for Docker build
"""
pass
EOF

cat > services/pattern/patterns/base_pattern.py << 'EOF'
"""
Base Pattern Detection Class
Placeholder implementation
"""

class BasePattern:
    def __init__(self, name):
        self.name = name
        
    def detect(self, data):
        """Placeholder pattern detection"""
        return {"detected": False, "confidence": 0.0}
EOF

cat > services/pattern/patterns/hammer.py << 'EOF'
"""
Hammer Pattern Detection
Placeholder implementation
"""
from .base_pattern import BasePattern

class HammerPattern(BasePattern):
    def __init__(self):
        super().__init__("hammer")
        
    def detect(self, data):
        return {"detected": False, "confidence": 0.0}
EOF

# Technical indicators placeholder files
cat > services/technical/indicators/__init__.py << 'EOF'
"""
Technical Indicators Module
Placeholder file for Docker build
"""
pass
EOF

cat > services/technical/indicators/rsi.py << 'EOF'
"""
RSI Indicator
Placeholder implementation
"""

def calculate_rsi(data, period=14):
    """Placeholder RSI calculation"""
    return 50.0  # Neutral RSI
EOF

cat > services/technical/indicators/macd.py << 'EOF'
"""
MACD Indicator
Placeholder implementation
"""

def calculate_macd(data, fast=12, slow=26, signal=9):
    """Placeholder MACD calculation"""
    return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
EOF

cat > services/technical/indicators/bollinger.py << 'EOF'
"""
Bollinger Bands Indicator
Placeholder implementation
"""

def calculate_bollinger_bands(data, period=20, std_dev=2):
    """Placeholder Bollinger Bands calculation"""
    return {"upper": 100.0, "middle": 99.0, "lower": 98.0}
EOF

# News processors placeholder files
cat > services/news/processors/__init__.py << 'EOF'
"""
News Processing Module
Placeholder file for Docker build
"""
pass
EOF

cat > services/news/processors/sentiment.py << 'EOF'
"""
Sentiment Analysis Processor
Placeholder implementation
"""

def analyze_sentiment(text):
    """Placeholder sentiment analysis"""
    return {"sentiment": "neutral", "score": 0.0, "confidence": 0.5}
EOF

cat > services/news/processors/catalyst.py << 'EOF'
"""
Catalyst Detection Processor
Placeholder implementation
"""

def detect_catalyst(article):
    """Placeholder catalyst detection"""
    return {"is_catalyst": False, "catalyst_type": "none", "impact": "low"}
EOF

cat > services/news/sources/__init__.py << 'EOF'
"""
News Sources Module
Placeholder file for Docker build
"""
pass
EOF

cat > services/news/sources/alpha_vantage.py << 'EOF'
"""
Alpha Vantage News Source
Placeholder implementation
"""

class AlphaVantageNews:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def get_news(self, symbol):
        return []  # Placeholder empty news
EOF

# Reporting static files
mkdir -p services/reporting/static/{css,js,images}

cat > services/reporting/static/css/style.css << 'EOF'
/* Catalyst Trading System - Reporting Styles */
body {
    font-family: 'Arial', sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header {
    text-align: center;
    color: #333;
    border-bottom: 2px solid #007acc;
    padding-bottom: 10px;
    margin-bottom: 20px;
}

.metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin: 20px 0;
}

.metric-card {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 6px;
    border-left: 4px solid #007acc;
}
EOF

cat > services/reporting/static/js/dashboard.js << 'EOF'
// Catalyst Trading System - Dashboard JavaScript
console.log('Catalyst Trading Dashboard Loaded');

// Placeholder dashboard functionality
const Dashboard = {
    init: function() {
        console.log('Dashboard initialized');
        this.loadMetrics();
    },
    
    loadMetrics: function() {
        // Placeholder metrics loading
        console.log('Loading metrics...');
    },
    
    updateCharts: function() {
        // Placeholder chart updates
        console.log('Updating charts...');
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    Dashboard.init();
});
EOF

# Create placeholder image
cat > services/reporting/static/images/logo.svg << 'EOF'
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" fill="#007acc"/>
  <text x="50" y="55" text-anchor="middle" fill="white" font-size="12">CT</text>
</svg>
EOF

# Chart templates
cat > services/reporting/charts/profit_loss.json << 'EOF'
{
  "chart_type": "line",
  "title": "Profit & Loss",
  "x_axis": "time",
  "y_axis": "pnl",
  "data_source": "trading_metrics",
  "refresh_interval": 60
}
EOF

cat > services/reporting/charts/risk_metrics.json << 'EOF'
{
  "chart_type": "gauge",
  "title": "Risk Score",
  "data_source": "risk_metrics",
  "thresholds": {
    "low": 30,
    "medium": 70,
    "high": 90
  },
  "refresh_interval": 30
}
EOF

# Create placeholder model files
echo "🤖 Creating placeholder model files..."

cat > services/pattern/models/hammer_model.json << 'EOF'
{
  "model_type": "pattern_detection",
  "pattern": "hammer",
  "version": "1.0.0",
  "parameters": {
    "body_ratio_threshold": 0.3,
    "wick_ratio_threshold": 2.0,
    "confidence_threshold": 0.65
  },
  "created_at": "2025-09-20T00:00:00Z"
}
EOF

cat > services/technical/models/rsi_config.json << 'EOF'
{
  "indicator": "rsi",
  "version": "1.0.0",
  "parameters": {
    "period": 14,
    "overbought": 70,
    "oversold": 30,
    "smoothing": "sma"
  },
  "created_at": "2025-09-20T00:00:00Z"
}
EOF

# Create data placeholder files
echo "📊 Creating placeholder data files..."

cat > services/pattern/data/sample_patterns.json << 'EOF'
{
  "patterns": [
    {"name": "hammer", "count": 0},
    {"name": "doji", "count": 0},
    {"name": "engulfing", "count": 0}
  ],
  "last_updated": "2025-09-20T00:00:00Z"
}
EOF

cat > services/news/data/sample_articles.json << 'EOF'
{
  "articles": [],
  "last_updated": "2025-09-20T00:00:00Z",
  "sources": ["alpha_vantage", "finnhub", "newsapi"]
}
EOF

# Create .gitkeep files for remaining empty directories
echo "📝 Creating .gitkeep files..."
find services/ -type d -empty -exec touch {}/.gitkeep \;

# Create requirements.txt files for each service
echo "📦 Creating requirements.txt files..."

cat > services/pattern/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.4
numpy==1.24.3
asyncpg==0.29.0
aioredis==2.0.1
pydantic==2.5.1
python-multipart==0.0.6
EOF

cat > services/technical/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.4
numpy==1.24.3
asyncpg==0.29.0
aioredis==2.0.1
pydantic==2.5.1
talib-binary==0.4.26
EOF

cat > services/news/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
aiohttp==3.9.1
asyncpg==0.29.0
aioredis==2.0.1
pydantic==2.5.1
textblob==0.17.1
vaderSentiment==3.3.2
EOF

cat > services/reporting/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
jinja2==3.1.2
asyncpg==0.29.0
aioredis==2.0.1
pydantic==2.5.1
plotly==5.17.0
matplotlib==3.8.2
EOF

# Print summary
echo ""
echo "✅ Complete Directory Structure with Placeholders Created!"
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
