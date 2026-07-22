FROM python:3.11-slim-bookworm

# Install uv from astral/uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create the non-root user
RUN useradd -ms /bin/bash sekoiaio-runtime

# Set working directory
WORKDIR /app

# Make the uv-managed venv the default Python
ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project --no-dev --compile-bytecode

# Copy application source
COPY . .

# Switch to non-root user
USER sekoiaio-runtime

# Set the entrypoint
ENTRYPOINT [ "python", "./main.py" ]
