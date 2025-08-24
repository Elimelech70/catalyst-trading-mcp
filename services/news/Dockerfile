FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/news/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/news/*.py ./

RUN mkdir -p /app/logs /app/data

ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=news-service

EXPOSE 5008

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5008/health || exit 1

RUN pip install anthropic

CMD ["python", "news-service.py"]
