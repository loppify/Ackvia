FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]