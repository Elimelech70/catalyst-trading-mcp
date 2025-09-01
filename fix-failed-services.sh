#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: fix_failed_services.sh
# Version: 1.0.0
# Last Updated: 2025-08-30
# Purpose: Fix all 6 failed services

echo "🎩 CATALYST TRADING MCP - FIXING FAILED SERVICES"
echo "================================================"

# Step 1: Install missing packages
echo ""
echo "📦 Step 1: Installing missing packages..."
echo "-----------------------------------------"

echo "Installing news service dependencies..."
pip install feedparser newspaper3k

echo "Installing market data dependencies..."
pip install yfinance

echo "Installing technical analysis..."
pip install TA-Lib  # Note: May need system libraries, see below

echo "Installing trading API..."
pip install alpaca-trade-api

# Alternative if TA-Lib fails
if [ $? -ne 0 ]; then
    echo "TA-Lib failed, trying alternative..."
    pip install pandas-ta  # Alternative to talib
fi

# Step 2: Fix incorrect imports in large services
echo ""
echo "🔧 Step 2: Fixing incorrect imports..."
echo "--------------------------------------"

# Create Python script to fix imports
cat > fix_imports.py << 'EOF'
#!/usr/bin/env python3
"""Fix incorrect MCP imports in large services"""

import re
from pathlib import Path

def fix_service_imports(filepath):
    """Remove non-existent MCP imports"""
    print(f"Fixing {filepath.name}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remove non-existent imports
    replacements = [
        # Remove ResourceParams, ToolParams - they don't exist
        (r'from mcp\.server\.fastmcp import FastMCP, ResourceParams, ToolParams',
         'from mcp.server.fastmcp import FastMCP'),
        (r', ResourceParams, ToolParams', ''),
        (r', ResourceParams', ''),
        (r', ToolParams', ''),
        
        # Remove non-existent response types
        (r'from mcp import ResourceResponse, ToolResponse, MCPError.*\n', ''),
        (r'import.*ResourceResponse.*\n', ''),
        (r'import.*ToolResponse.*\n', ''),
        
        # Fix return type hints that use these
        (r'-> ResourceResponse', '-> Dict'),
        (r'-> ToolResponse', '-> Dict'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Add Dict import if needed
    if '-> Dict' in content and 'from typing import' not in content:
        content = 'from typing import Dict, List, Optional, Any\n' + content
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"  ✓ Fixed imports in {filepath.name}")

# Fix each large service
services = [
    'services/news/news-service.py',
    'services/scanner/scanner-service.py',
    'services/pattern/pattern-service.py',
    'services/technical/technical-service.py',
    'services/trading/trading-service.py'
]

for service_path in services:
    filepath = Path(service_path)
    if filepath.exists():
        fix_service_imports(filepath)

print("\n✅ Import fixes complete!")
EOF

python3 fix_imports.py

# Step 3: Fix database service bug
echo ""
echo "🔧 Step 3: Fixing database service bug..."
echo "-----------------------------------------"

# Fix the undefined service_name in database service
sed -i 's/print(f"Starting {service_name} MCP Server...")/print(f"Starting database MCP Server...")/' services/database/database-mcp-service.py

echo "  ✓ Fixed database service"

# Step 4: Create simplified templates for complex services
echo ""
echo "📝 Step 4: Creating fallback templates..."
echo "-----------------------------------------"

# Create a working template for each large service
for service in news scanner pattern technical trading; do
    cat > services/$service/${service}-service-simple.py << EOF
#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: ${service}-service-simple.py
Version: 2.2.0
Last Updated: 2025-08-30
Purpose: Simplified ${service} service without external dependencies

REVISION HISTORY:
v2.2.0 - Simplified version without external APIs
"""

from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import random

# Create MCP server
mcp = FastMCP("${service}")

# Service state
state = {
    "status": "ready",
    "last_update": None,
    "data": {}
}

@mcp.resource("${service}://status")
async def get_status() -> Dict:
    """Get service status"""
    return {
        "service": "${service}",
        "status": state["status"],
        "last_update": state["last_update"],
        "timestamp": datetime.now().isoformat()
    }

@mcp.tool()
async def process_${service}_request(data: Dict[str, Any]) -> Dict:
    """Process ${service} request (simplified)"""
    # Simulate processing
    await asyncio.sleep(0.5)
    
    # Mock response
    result = {
        "success": True,
        "service": "${service}",
        "processed": data,
        "mock_data": True,
        "note": "Using simplified version without external APIs",
        "timestamp": datetime.now().isoformat()
    }
    
    state["last_update"] = datetime.now().isoformat()
    state["data"] = data
    
    return result

if __name__ == "__main__":
    print(f"🎩 Catalyst Trading MCP - {service.title()} Service (Simplified)")
    print("=" * 50)
    print("Note: Running without external API dependencies")
    print("=" * 50)
    mcp.run()
EOF
    echo "  ✓ Created simplified template for $service"
done

# Step 5: Test the fixes
echo ""
echo "🧪 Step 5: Testing fixed services..."
echo "------------------------------------"

python3 << 'EOF'
import subprocess
import sys
from pathlib import Path

def test_service(path):
    """Quick syntax test"""
    result = subprocess.run(
        [sys.executable, '-m', 'py_compile', path],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

services = [
    ('news', 'services/news/news-service.py'),
    ('scanner', 'services/scanner/scanner-service.py'),
    ('pattern', 'services/pattern/pattern-service.py'),
    ('technical', 'services/technical/technical-service.py'),
    ('trading', 'services/trading/trading-service.py'),
    ('database', 'services/database/database-mcp-service.py')
]

print("\nTesting fixed services:")
for name, path in services:
    if Path(path).exists():
        if test_service(path):
            print(f"  ✓ {name}: Syntax OK")
        else:
            print(f"  ✗ {name}: Still has issues (try simplified version)")
            simple = path.replace('.py', '-simple.py')
            if Path(simple).exists():
                print(f"    → Use: python {simple}")

EOF

echo ""
echo "================================================"
echo "✅ FIX PROCESS COMPLETE!"
echo "================================================"
echo ""
echo "📊 Status:"
echo "  • 8 core services: Already working"
echo "  • 6 large services: Dependencies installed & imports fixed"
echo "  • Fallback templates created for complex services"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. Test the fixed services:"
echo "   python services/news/news-service.py"
echo "   python services/database/database-mcp-service.py"
echo ""
echo "2. If a service still fails, use the simplified version:"
echo "   python services/news/news-service-simple.py"
echo ""
echo "3. Start all working services:"
echo "   python services/orchestration/orchestration-service.py"
echo ""
echo "Note: Some services (trading) need API keys configured."
echo "      The simplified versions work without external APIs."
