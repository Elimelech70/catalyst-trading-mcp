FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/orchestration/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/orchestration/*.py ./

RUN mkdir -p /app/logs /app/data

ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=orchestration-service

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["python", "orchestration-service.py"]
