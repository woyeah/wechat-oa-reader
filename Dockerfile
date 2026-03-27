FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir ".[mcp]"

RUN mkdir -p /data

ENV WECOM_DB_PATH=/data/wecom.db

# No fixed CMD — docker-compose specifies the entry point per service
# Default: wecom-mcp (for standalone use)
CMD ["wecom-mcp"]
