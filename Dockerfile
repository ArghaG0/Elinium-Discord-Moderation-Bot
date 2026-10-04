FROM python:3.13.5-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-cache

FROM python:3.13.5-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --gid 10001 elinium && useradd --uid 10001 --gid elinium --no-create-home elinium
COPY --from=builder /app/.venv /app/.venv
COPY main.py ./
COPY cogs/ ./cogs/
COPY config/ ./config/
COPY db/ ./db/
COPY utils/ ./utils/
USER 10001:10001
ENTRYPOINT ["/app/.venv/bin/python", "main.py"]
