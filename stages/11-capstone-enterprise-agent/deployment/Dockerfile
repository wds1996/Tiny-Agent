FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY stages/11-capstone-enterprise-agent ./stages/11-capstone-enterprise-agent

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ".[stage11]"

USER appuser

EXPOSE 8000

CMD ["python", "stages/11-capstone-enterprise-agent/code/api_app.py"]
