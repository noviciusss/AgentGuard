FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/agentguard/.venv

WORKDIR /opt/agentguard

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages ./packages
COPY docs ./docs
COPY benchmarks ./benchmarks
COPY tests ./tests
COPY Makefile ./Makefile

RUN pip install --no-cache-dir uv==0.13.0 \
    && uv sync --locked --all-extras --all-packages --no-dev

EXPOSE 8000

CMD ["uv", "run", "--locked", "--package", "agentguard-server", "uvicorn", "agentguard_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
