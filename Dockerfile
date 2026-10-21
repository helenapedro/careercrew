# CareerCrew - production container image.
#
# Works locally and on a small AWS EC2 instance. The app listens on
# 0.0.0.0:7860. The MCP server is launched by the app over stdio,
# so no second long-running service is required in the container.
#
# Build:  docker build -t careercrew .
# Run:    docker run --rm -p 7860:7860 --env-file .env careercrew

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    CAREERCREW_DB_PATH=/data/careercrew.db \
    CAREERCREW_UPLOAD_DIR=/data/uploads

WORKDIR /app

# System dependencies kept minimal; build tools are not needed at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so they cache across code changes.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

# Copy the application.
COPY pyproject.toml README.md ./
COPY careercrew ./careercrew
COPY config ./config
COPY knowledge ./knowledge
COPY mcp_server ./mcp_server
COPY app.py main.py ./
COPY samples ./samples

# Run as a non-root user with a writable data dir for the SQLite store.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data/uploads \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 7860

# Healthcheck hits the Gradio root; returns 0 when the server is serving.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/', timeout=4).status==200 else 1)"

CMD ["python", "app.py"]
