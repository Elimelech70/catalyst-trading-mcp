# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Pattern Analysis Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Pattern Analysis MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Pattern recognition and market structure analysis
# - Added proper environment configuration
# - Analyzes top 5 candidates from scanner

# Description of Service:
# The Pattern Analysis Service detects trading patterns and market
# structures in the top 5 candidates. Identifies breakouts, reversals,
# and momentum patterns with catalyst confirmation. Port 5002.

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
COPY services/pattern/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/pattern/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=pattern-service
ENV SERVICE_PORT=5002
ENV MCP_TRANSPORT=websocket

# Expose MCP service port
EXPOSE 5002

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

# Run the MCP pattern analysis service
CMD ["python", "pattern-service.py"]