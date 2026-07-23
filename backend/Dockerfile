FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY entrypoint.sh ./

RUN uv sync --frozen --no-dev \
    && chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["/app/entrypoint.sh"]
