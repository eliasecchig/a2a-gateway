FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY gateway/ gateway/
COPY samples/__init__.py samples/dummy_agent.py samples/

RUN uv sync --no-dev

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app /app

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "gateway"]
