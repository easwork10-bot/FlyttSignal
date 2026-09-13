FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.8.15
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONPATH=/app/backend/src
