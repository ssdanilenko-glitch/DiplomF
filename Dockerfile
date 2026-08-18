# syntax=docker/dockerfile:1.7

# ========== STAGE 1: BUILDER ==========
FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

WORKDIR /app

# Копируем все исходники проекта
COPY app/ ./app/
COPY bot/ ./bot/
COPY express_bot/ ./express_bot/
COPY migrations/ ./migrations/
COPY alembic.ini pyproject.toml uv.lock ./

# Устанавливаем зависимости (без --frozen, чтобы uv подтянул актуальные версии из pyproject.toml)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# ========== STAGE 2: RUNTIME ==========
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:8000/ready', timeout=3).status == 200 else sys.exit(1)" \
    || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]