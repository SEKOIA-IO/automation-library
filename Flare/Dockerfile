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

# Some dependencies (e.g. pyrate-limiter, used by requests-ratelimiter) resolve a temp
# directory at import time via tempfile.gettempdir(). The default system temp directories
# (/tmp, /var/tmp, /usr/tmp) may not be writable by the non-root runtime user in the
# deployment environment, so provide a dedicated writable directory and point TMPDIR at it.
RUN mkdir -p /app/tmp && chown sekoiaio-runtime:sekoiaio-runtime /app/tmp
ENV TMPDIR=/app/tmp

USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
