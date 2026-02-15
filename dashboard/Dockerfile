# Multi-stage Dockerfile for Dashboard (API + Web)
# Build: docker build -t dashboard -f dashboard/Dockerfile .

# ============================================================
# Stage 1: Build Next.js frontend
# ============================================================
FROM node:20-alpine AS web-builder

WORKDIR /app/web
COPY dashboard/web/package.json dashboard/web/package-lock.json ./
RUN npm ci
COPY dashboard/web/ ./
RUN npm run build

# ============================================================
# Stage 2: Dashboard API (Python) + static Next.js output
# ============================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY dashboard/api/requirements.txt /tmp/api-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt

# Copy bot source (needed by dashboard API for imports)
COPY src/ /app/src/
COPY dashboard/api/ /app/dashboard/api/

# Copy Next.js standalone build
COPY --from=web-builder /app/web/.next/standalone /app/dashboard/web/
COPY --from=web-builder /app/web/.next/static /app/dashboard/web/.next/static
COPY --from=web-builder /app/web/public /app/dashboard/web/public

# Create non-root user
RUN groupadd -r dashuser && useradd -r -g dashuser -d /app -s /sbin/nologin dashuser
RUN chown -R dashuser:dashuser /app
USER dashuser

EXPOSE 8000 3000

# Default: start the FastAPI backend
CMD ["uvicorn", "dashboard.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
