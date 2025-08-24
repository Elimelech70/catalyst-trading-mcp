# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Orchestration Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Orchestration MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Corrected service startup command
# - Added proper environment configuration
# - Primary Claude Desktop connection endpoint

# Description of Service:
# The Orchestration Service is the main MCP server that Claude connects to.
# It coordinates all trading operations and manages workflows across services.
# Exposed on port 5000 as the primary WebSocket MCP endpoint.

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
COPY services/orchestration/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/orchestration/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=orchestration-service
ENV SERVICE_PORT=5000
ENV MCP_TRANSPORT=websocket

# Expose MCP service port (Primary Claude endpoint)
EXPOSE 5000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the MCP orchestration service
CMD ["python", "orchestration-service.py"]