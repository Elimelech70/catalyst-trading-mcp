# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Reporting Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Reporting MCP Service

# REVISION HISTORY:
# v1.0.0 (2025-08-23) - Initial MCP-compliant Dockerfile
# - Standardized Python 3.11 across all services
# - Added MCP components and shared utilities
# - Performance reporting and analytics
# - Added proper environment configuration
# - Reports on all 50 scanned and top 5 traded securities

# Description of Service:
# The Reporting Service provides comprehensive analytics, performance
# metrics, and trading summaries. Tracks all scanned securities (50-100)
# and detailed execution reports for traded positions. Port 5009.

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
COPY services/reporting/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and MCP components
COPY services/shared/ ./shared/

# Copy service code
COPY services/reporting/*.py ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/reports

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=reporting-service
ENV SERVICE_PORT=5009
ENV MCP_TRANSPORT=websocket

# Expose MCP service port
EXPOSE 5009

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5009/health || exit 1

# Run the MCP reporting service
CMD ["python", "reporting-service.py"]