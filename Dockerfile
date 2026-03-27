FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir ".[mcp]"

RUN mkdir -p /data && useradd -r -u 1000 -s /bin/false appuser && chown appuser:appuser /data

ENV WECOM_DB_PATH=/data/wecom.db

USER appuser

CMD ["wecom-mcp"]
