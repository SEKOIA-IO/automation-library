ARG python_version=3.14

# --- STAGE 1: Builder ---
FROM python:${python_version}-slim AS builder

# Install uv
RUN pip install uv

# Optimize uv for container builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv

WORKDIR /app

# Copy dependency definition files
COPY pyproject.toml uv.lock /app

# Install dependencies with local cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-editable --no-install-project

# --- STAGE 2: Runtime ---
FROM python:${python_version}-slim AS runtime

# Set real-time outputs
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user
RUN useradd -m -u 10001 -s /bin/bash sekoiaio-runtime

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application files and explicitly assign ownership to the non-root user
COPY --chown=sekoiaio-runtime:sekoiaio-runtime . .

USER sekoiaio-runtime

ENTRYPOINT ["uv", "run", "python", "./main.py"]
