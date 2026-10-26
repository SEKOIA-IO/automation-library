FROM python:3.14-bookworm

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/

# Install dependencies
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-default-groups --no-install-project

# Make the project virtual environment the default interpreter
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime

# The sekoia_automation SDK hardcodes writes to /tmp/tls.
# Since the K8s environment enforces a read-only root filesystem, 
# we replace /tmp with a symlink to /dev/shm (which K8s always mounts as a writable tmpfs).
# This transparently redirects all hardcoded /tmp writes into memory.
RUN rm -rf /tmp && ln -s /dev/shm /tmp

USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]