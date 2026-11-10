# syntax=docker/dockerfile:1

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN pip install .

COPY --from=web /web/dist ./static
RUN mkdir -p /app/data/raw && chown -R app:app /app

USER app
ENV UPLIFTLAB_STATIC_DIR=/app/static \
    UPLIFTLAB_DATA_DIR=/app/data/raw

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "upliftlab.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
