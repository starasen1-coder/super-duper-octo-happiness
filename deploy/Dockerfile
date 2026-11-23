FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY agent-reach/requirements-api.txt /tmp/requirements-api.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-api.txt \
    && useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin research-api

COPY agent-reach/agent_reach /app/agent_reach

USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "agent_reach.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
