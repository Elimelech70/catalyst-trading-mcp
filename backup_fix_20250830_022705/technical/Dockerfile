# Catalyst Trading MCP - Service Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y     gcc     g++     && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production

# Run the service with FastMCP
CMD ["python", "-u", "technical-service.py"]
