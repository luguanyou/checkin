FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations ./migrations

RUN groupadd --gid 10001 attendance \
    && useradd --uid 10001 --gid attendance --no-create-home attendance \
    && chown -R attendance:attendance /app

USER attendance
EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "attendance_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
