# Name of Application: Catalyst Trading System
# Name of file: services/database/Dockerfile
# Version: 1.0.0
# Last Updated: 2025-09-19
# Purpose: Docker container for Database MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-09-19) - Initial creation
# - Database MCP Service container
# - Connects to DigitalOcean Managed PostgreSQL
# - Provides MCP protocol interface on port 5010

# Description of Service:
# Containerizes the Database MCP Service that provides a unified
# MCP interface for all database operations, connecting to the
# DigitalOcean Managed PostgreSQL database.

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir \
    asyncpg==0.29.0 \
    redis==5.0.1 \
    mcp==1.0.0 \
    fastmcp==0.1.0 \
    structlog==24.1.0 \
    python-dotenv==1.0.0 \
    aiohttp==3.9.1 \
    websockets==12.0 \
    pydantic==2.5.0

# Copy shared utilities and database service
COPY services/shared/ ./services/shared/
COPY services/database/database-mcp-service.py ./

# Set Python path to include the app directory
ENV PYTHONPATH=/app:$PYTHONPATH

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=database-mcp-service
ENV SERVICE_PORT=5010

# Expose the MCP service port
EXPOSE 5010

# Health check to ensure service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import aiohttp, asyncio; asyncio.run(aiohttp.ClientSession().get('http://localhost:5010/health'))" || exit 1

# Run the database MCP service
CMD ["python", "database-mcp-service.py"]