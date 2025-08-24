# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Technical Analysis Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Technical Analysis MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Technical indicators and signal generation
# - Added proper environment configuration
# - Generates signals for top 5 pattern-confirmed stocks

# Description of Service:
# The Technical Analysis Service calculates indicators and generates
# trading signals for the top 5 candidates. Provides entry/exit points,
# stop losses, and confidence scores based on technical setups. Port 5003.

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
COPY services/technical/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/technical/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=technical-service
ENV SERVICE_PORT=5003
ENV MCP_TRANSPORT=websocket

# Expose MCP service port
EXPOSE 5003

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Run the MCP technical analysis service
CMD ["python", "technical-service.py"]