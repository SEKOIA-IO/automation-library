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

# The Kubernetes environment likely enforces a read-only root filesystem.
# By pointing TMPDIR to /dev/shm, we utilize the container runtime's default 
# shared memory mount, which is almost always a writable tmpfs.
ENV TMPDIR=/dev/shm

USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]