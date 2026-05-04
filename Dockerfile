FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_SYSTEM_PYTHON=1

COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r pyproject.toml

COPY . .

ENTRYPOINT ["python", "processor.py"]
