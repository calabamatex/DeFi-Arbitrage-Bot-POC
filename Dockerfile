# =============================================================
# Flash Loan Arbitrage / Liquidation Bot — Production Dockerfile
# =============================================================
# Multi-stage build: slim runtime, non-root user, healthcheck.
#
# Build:
#   docker build -t arb-bot .
#
# Run (arbitrage):
#   docker run --env-file .env arb-bot
#
# Run (liquidation):
#   docker run --env-file .env arb-bot python run_liquidation_bot.py
# =============================================================

# ---------- stage 1: builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies (needed for psycopg2-binary, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- stage 2: runtime ----------
FROM python:3.11-slim

# Install only the runtime library for PostgreSQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r botuser && useradd -r -g botuser -d /app -s /sbin/nologin botuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ src/
COPY config/ config/
COPY run_bot.py .
COPY run_liquidation_bot.py .

# Create directories for logs and data (writable by botuser)
RUN mkdir -p /app/logs /app/data && chown -R botuser:botuser /app

USER botuser

# Health check — requires the health endpoint from Phase 4.
# Until then, just verify the process is running.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || kill -0 1

# Default: run the arbitrage bot
ENV PYTHONUNBUFFERED=1
CMD ["python", "run_bot.py"]
