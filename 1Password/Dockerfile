FROM python:3.14

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

# Make the project virtual environment the default interpreter
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime

# Some dependencies (e.g. pyrate-limiter) resolve a temp directory at import time.
# The default system temp directories may not be writable in the runtime environment,
# so provide a dedicated writable directory and point TMPDIR at it.
# Use mode 1777 (world-writable + sticky bit, like /tmp) so it works even when the
# container is run with an arbitrary UID rather than the sekoiaio-runtime user.
RUN mkdir -p /app/tmp && chmod 1777 /app/tmp
ENV TMPDIR=/app/tmp

USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
