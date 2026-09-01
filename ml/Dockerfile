# ML pipeline image. Installs the cpi-ml package and its dependencies.
FROM python:3.11-slim AS base
WORKDIR /app

# System libs needed by psycopg2 and scientific wheels.
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY tests ./tests

RUN python -m pip install --upgrade pip \
  && python -m pip install -e ".[dev]"

# Default command shows the CLI help; pipelines are invoked explicitly.
CMD ["python", "-m", "cpi_ml.cli", "--help"]
