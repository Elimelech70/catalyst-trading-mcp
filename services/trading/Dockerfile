# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Trading Execution Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Trading Execution MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Trade execution and position management
# - Added proper environment configuration
# - Executes trades for top 5 high-confidence signals

# Description of Service:
# The Trading Execution Service manages order placement, position tracking,
# and risk management. Executes trades for the top 5 opportunities with
# automated stop-loss and take-profit management. Port 5005.

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY services/trading/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/trading/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=trading-service
ENV SERVICE_PORT=5005
ENV MCP_TRANSPORT=websocket

# Expose MCP service port
EXPOSE 5005

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5005/health || exit 1

# Run the MCP trading execution service
CMD ["python", "trading-service.py"]