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
# Since the K8s environment enforces a read-only root filesystem,
# we replace /tmp with a symlink to /dev/shm (which K8s always mounts as a writable tmpfs).
# This transparently redirects all hardcoded /tmp writes into memory.
RUN rm -rf /tmp && ln -s /dev/shm /tmp

# Create the folder for the cache
RUN mkdir /var/cache/symphony_rss_module && chown sekoiaio-runtime:sekoiaio-runtime /var/cache/symphony_rss_module && chmod u+rwx /var/cache/symphony_rss_module

USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
