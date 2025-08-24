# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (News Intelligence Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for News Intelligence MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Removed duplicate anthropic pip install
# - Added proper environment configuration
# - News catalyst integration service

# Description of Service:
# The News Intelligence Service collects and analyzes market-moving news
# from multiple sources. It provides real-time catalyst detection and
# sentiment analysis to drive trading decisions. Port 5008.

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
COPY services/news/requirements.txt .

# Install Python dependencies (includes anthropic)
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/news/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=news-service
ENV SERVICE_PORT=5008
ENV MCP_TRANSPORT=websocket

# Expose MCP service port
EXPOSE 5008

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5008/health || exit 1

# Run the MCP news service
CMD ["python", "news-service.py"]