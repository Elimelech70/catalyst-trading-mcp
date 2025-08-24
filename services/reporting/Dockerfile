FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/reporting/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/reporting/*.py ./

RUN mkdir -p /app/logs /app/data /app/reports

ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=reporting-service

EXPOSE 5009

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5009/health || exit 1

CMD ["python", "reporting-service.py"]
