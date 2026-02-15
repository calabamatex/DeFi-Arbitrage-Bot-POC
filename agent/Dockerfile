FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY agent/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY src/ /app/src/
COPY agent/ /app/agent/

RUN groupadd -r agentuser && useradd -r -g agentuser -d /app -s /sbin/nologin agentuser
RUN chown -R agentuser:agentuser /app
USER agentuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "agent/pm_agent.py"]
