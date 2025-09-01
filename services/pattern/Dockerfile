# Name of Application: Catalyst Trading System
# Name of file: services/pattern/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for Pattern Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY patterns/ ./patterns/
COPY models/ ./models/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5002/health')" || exit 1

# Run the service
CMD ["python", "-u", "pattern-service.py"]
