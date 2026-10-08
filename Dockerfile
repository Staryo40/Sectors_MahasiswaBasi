FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RADAR_ROOT=/app

WORKDIR /app

COPY pyproject.toml ./
COPY backend ./backend
COPY data/out ./data/out

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 radar

USER radar

EXPOSE 8000

CMD ["sh", "-c", "uvicorn radar.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
