FROM python:3.14-bookworm

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

# The sekoia_automation SDK hardcodes writes to /tmp/tls.
# Since the runtime enforces a read-only root filesystem,
# redirect /tmp writes to shared memory.
RUN rm -rf /tmp && ln -s /dev/shm /tmp

USER sekoiaio-runtime

ENTRYPOINT ["python", "./main.py"]
