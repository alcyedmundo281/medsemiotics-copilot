FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
# The read endpoints serve tracked configuration; without it the deployed API has nothing to read.
COPY config ./config

RUN pip install --upgrade pip     && pip install . "uvicorn[standard]"

EXPOSE 8080

CMD ["sh", "-c", "uvicorn medsemiotics.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
