# Name of Application: Catalyst Trading System
# Service: Technical Service
# Version: 5.0.0

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r catalyst && useradd -r -g catalyst catalyst

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY technical-service.py .

# Create logs directory
RUN mkdir -p /app/logs && chown -R catalyst:catalyst /app

# Switch to non-root user
USER catalyst

# Environment variables
ENV SERVICE_PORT=5003
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Run the service
CMD ["python", "technical-service.py"]