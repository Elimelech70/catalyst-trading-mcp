# Name of Application: Catalyst Trading System
# Name of file: services/news/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-09-01
# Purpose: Docker container for News Service v4.1

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('vader_lexicon'); nltk.download('punkt')"

# Copy service code
COPY *.py ./

# Copy directories (now they exist)
COPY models/ ./models/
COPY sources/ ./sources/
COPY processors/ ./processors/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5008/health')" || exit 1

# Run the service
CMD ["python", "-u", "news-service.py"]
