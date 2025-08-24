FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/technical/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/technical/*.py ./

RUN mkdir -p /app/logs /app/data

ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=technical-service

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

CMD ["python", "technical-service.py"]
