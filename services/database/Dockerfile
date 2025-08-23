# Name of Application: Catalyst Trading System
# Name of file: Dockerfile (Database Service)
# Version: 1.0.0
# Last Updated: 2025-08-23
# Purpose: Docker configuration for Database MCP Service

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/database/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY services/shared/ ./services/shared/

# Copy service code
COPY services/database/ ./services/database/

# Copy MCP database client library
COPY services/shared/mcp_database_client.py ./

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Expose port
EXPOSE 5010

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5010/health || exit 1

# Run the service
CMD ["python", "services/database/database-mcp-service.py"]