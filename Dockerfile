FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install --prefix=/install .

FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 librdkafka1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 commerce_analytics \
    && useradd --uid 1000 --gid commerce_analytics --shell /bin/bash --create-home commerce_analytics
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=commerce_analytics:commerce_analytics src/ ./src/
COPY --chown=commerce_analytics:commerce_analytics data/sample/ ./data/sample/
USER commerce_analytics
EXPOSE 8001
ENTRYPOINT ["python", "-m", "commerce_analytics.main"]
CMD ["--help"]
