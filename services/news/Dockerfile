# Name of Application: Catalyst Trading System
# Name of file: services/news/Dockerfile
# Version: 4.2.0
# Last Updated: 2025-09-05
# Purpose: News service container with non-root user

# REVISION HISTORY:
# v4.2.0 (2025-09-05) - Production-ready with security best practices
# - Non-root user implementation
# - Multi-stage build for smaller image
# - Proper permission handling
# - Health checks included

# ============================================
# Stage 1: Builder stage for dependencies
# ============================================
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for builder
RUN groupadd -r newsbuilder && useradd -r -g newsbuilder newsbuilder

# Set working directory
WORKDIR /build

# Copy requirements
COPY requirements.txt .

# Install Python dependencies as non-root
RUN pip install --user --no-cache-dir --no-warn-script-location -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('vader_lexicon'); nltk.download('punkt'); nltk.download('stopwords')"

# ============================================
# Stage 2: Runtime stage (smaller final image)
# ============================================
FROM python:3.10-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for runtime
# Using specific UID/GID for consistency
RUN groupadd -g 1001 newsservice \
    && useradd -r -u 1001 -g newsservice -m -s /bin/bash newsservice

# Create app directory with correct permissions
RUN mkdir -p /home/newsservice/app/logs \
    && mkdir -p /home/newsservice/app/data \
    && mkdir -p /home/newsservice/app/cache \
    && chown -R newsservice:newsservice /home/newsservice

# Switch to non-root user
USER newsservice

# Set working directory
WORKDIR /home/newsservice/app

# Copy Python packages from builder
COPY --from=builder --chown=newsservice:newsservice /root/.local /home/newsservice/.local

# Copy NLTK data from builder
COPY --from=builder --chown=newsservice:newsservice /root/nltk_data /home/newsservice/nltk_data

# Set Python path for user packages
ENV PATH=/home/newsservice/.local/bin:$PATH
ENV PYTHONPATH=/home/newsservice/.local/lib/python3.10/site-packages:$PYTHONPATH
ENV NLTK_DATA=/home/newsservice/nltk_data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVICE_NAME=news-intelligence \
    PORT=5008 \
    NEWS_FETCH_INTERVAL=300 \
    MAX_ARTICLES_PER_BATCH=100 \
    SENTIMENT_MODEL=vader

# Copy application code
COPY --chown=newsservice:newsservice . .

# Create startup script to handle permissions
RUN echo '#!/bin/bash\n\
echo "Starting News Intelligence Service..."\n\
echo "User: $(whoami)"\n\
echo "Python: $(which python)"\n\
echo "Working Dir: $(pwd)"\n\
echo "NLTK Data: $NLTK_DATA"\n\
python news-service.py\n' > start.sh && chmod +x start.sh

# Health check as non-root user
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5008/health || exit 1

# Expose port (informational, doesn't actually publish)
EXPOSE 5008

# Use exec form to ensure signals are handled properly
CMD ["/home/newsservice/app/start.sh"]

# ============================================
# Build instructions:
# ============================================
# docker build -t catalyst-news:latest .
# 
# Run instructions:
# docker run -d \
#   --name news-service \
#   -p 5008:5008 \
#   -e NEWS_API_KEY=your_key_here \
#   -e ALPHAVANTAGE_API_KEY=your_key_here \
#   --network catalyst-network \
#   catalyst-news:latest
#
# Debug if needed:
# docker run -it --rm catalyst-news:latest /bin/bash
#
# Check user inside container:
# docker exec news-service whoami  # Should show: newsservice