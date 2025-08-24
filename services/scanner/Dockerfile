# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Scanner Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Security Scanner MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Dynamic security scanning with news-based filtering
# - Added proper environment configuration
# - Scans 50-100 securities, narrows to top 5

# Description of Service:
# The Scanner Service dynamically identifies the most active stocks
# with news catalysts. Starts with market's most active 50-100 stocks,
# filters by news events, and delivers top opportunities. Port 5001.

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
COPY services/scanner/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/scanner/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=scanner-service
ENV SERVICE_PORT=5001
ENV MCP_TRANSPORT=websocket

# Expose MCP service port
EXPOSE 5001

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Run the MCP scanner service
CMD ["python", "scanner-service.py"]