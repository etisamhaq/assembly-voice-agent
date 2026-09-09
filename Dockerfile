# Second Chair - production image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so a code change does not invalidate the wheel layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY demo.py check_llm.py ./

# Non-root, and an audit directory it can actually write to.
RUN useradd --create-home --uid 10001 secondchair \
    && mkdir -p /tmp/audit \
    && chown -R secondchair:secondchair /app /tmp/audit
USER secondchair

ENV PORT=8000 \
    SC_AUDIT_DIR=/tmp/audit
EXPOSE 8000

# Shell form so Render's injected $PORT is expanded; exec so uvicorn is PID 1
# and receives SIGTERM directly (clean WebSocket shutdown on redeploy).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 20"]
