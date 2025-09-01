#!/bin/bash
# Catalyst Trading MCP - Quick Start Script

echo "🎩 Catalyst Trading MCP - Quick Start"
echo "===================================="

# Check Python version
python3 --version

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install mcp asyncpg redis aiohttp structlog python-dotenv

# Start services
echo ""
echo "🚀 Starting services..."

# Start PostgreSQL and Redis with Docker
if command -v docker &> /dev/null; then
    echo "Starting PostgreSQL and Redis with Docker..."
    docker-compose up -d postgres redis
else
    echo "⚠️  Docker not found. Please start PostgreSQL and Redis manually."
fi

# Run test suite
echo ""
echo "🧪 Running tests..."
python3 test_mcp_services.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the orchestration service:"
echo "  python services/orchestration/orchestration-service.py"
echo ""
echo "To configure Claude Desktop:"
echo "  Copy the contents of claude-desktop-config.json to Claude Desktop settings"
