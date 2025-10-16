#!/bin/bash
# Name of Application: Catalyst Trading MCP
# Name of file: fix-orchestration-service.sh
# Version: 1.0.0
# Last Updated: 2025-10-16
# Purpose: Fix orchestration service FastMCP API changes

# REVISION HISTORY:
# v1.0.0 (2025-10-16) - Fix FastMCP on_initialize method

echo "🔧 Fixing Orchestration Service..."

# Navigate to the service directory
cd /root/catalyst-trading-mcp/services/orchestration

# The FastMCP API has changed - on_initialize is no longer used
# Instead, initialization happens in the constructor or using lifespan events

# First, let's check what's on line 295
echo "📋 Checking current code at line 295..."
sed -n '290,300p' orchestration-service.py

# Remove the @mcp.on_initialize() decorator and move initialization logic
# Create a temporary fix file
cat > fix_orchestration.py << 'EOF'
# This script removes the problematic on_initialize decorator
import fileinput
import sys

fixing = False
skip_next = False

for line in fileinput.input('orchestration-service.py', inplace=True):
    if '@mcp.on_initialize()' in line:
        skip_next = True
        # Don't print this line
        continue
    elif skip_next and 'async def' in line:
        # Convert to a regular function that runs at startup
        print("# Initialization moved to startup")
        print("async def initialize_mcp():")
        skip_next = False
    else:
        print(line, end='')
EOF

# Apply the fix
python3 fix_orchestration.py

# Add startup call if not present
echo "📝 Adding initialization call at startup..."
cat >> orchestration-service.py << 'EOF'

# Run initialization at startup
if __name__ == "__main__":
    import asyncio
    
    async def startup():
        # Initialize MCP resources
        if 'initialize_mcp' in globals():
            await initialize_mcp()
        
        # Run the MCP server
        mcp.run()
    
    try:
        asyncio.run(startup())
    except KeyboardInterrupt:
        print("Shutting down...")
EOF

# Clean up
rm -f fix_orchestration.py

# Rebuild the Docker image
echo "🔨 Rebuilding Docker image..."
docker-compose build orchestration

# Restart the service
echo "🔄 Restarting service..."
docker-compose restart orchestration

echo "✅ Orchestration Service fix complete!"