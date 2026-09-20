# syntax=docker/dockerfile:1

# --- Builder stage: install dependencies into a venv --------------------
FROM python:3.12-slim AS builder

# Some backend deps (e.g. scikit-learn's transitive deps) may need to
# compile from source depending on platform/wheel availability.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY pyproject.toml ./
# Editable install needs *something* importable at this path; the real
# source is copied in below, in both stages, after dependency resolution
# so dependency layers stay cached across source-only changes.
RUN mkdir agents api && touch agents/__init__.py api/__init__.py

# CPU-only torch first: sentence-transformers pulls in plain `torch`,
# whose default PyPI wheel bundles NVIDIA/CUDA libraries this CPU-only
# service never uses (~9GB of the image otherwise). Installing the CPU
# wheel up front satisfies that dependency before it's resolved any other
# way.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install .

# --- Final stage: slim runtime image -------------------------------------
FROM python:3.12-slim AS final

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --no-create-home appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Only what's needed to run the service: app code + the data the pipeline
# reads at runtime (mock watchlist, sample/golden cases, policy docs).
# pyproject.toml, scripts/, and .egg-info are dev/eval-only and excluded.
COPY main.py db.py ./
COPY agents/ ./agents/
COPY api/ ./api/
COPY data/ ./data/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
