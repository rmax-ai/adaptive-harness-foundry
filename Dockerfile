FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev

COPY src/ src/
COPY configs/ configs/
COPY data/ data/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "harness_foundry.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
