# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY stages/10-production-deployment/code/service_app.py ./service_app.py

RUN python -m pip install --upgrade pip && \
    python -m pip install ".[stage10]" && \
    useradd --create-home --uid 10001 appuser

USER appuser
EXPOSE 8000

CMD ["python", "service_app.py"]
