FROM python:3.14

WORKDIR /app

RUN apt-get update && apt-get install -y git nano

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# To retrieve the AWS package locally (referenced as ../AWS in pyproject.toml)
RUN git clone https://github.com/SEKOIA-IO/automation-library

WORKDIR /app/automation-library/CrowdStrike/

COPY . .

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Make the project virtual environment the default interpreter
ENV PATH="/app/automation-library/CrowdStrike/.venv/bin:$PATH"

RUN useradd -ms /bin/bash sekoiaio-runtime

# The sekoia_automation SDK hardcodes writes to /tmp/tls.
# Since the K8s environment enforces a read-only root filesystem,
# we replace /tmp with a symlink to /dev/shm (which K8s always mounts as a writable tmpfs).
# This transparently redirects all hardcoded /tmp writes into memory.
RUN rm -rf /tmp && ln -s /dev/shm /tmp
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
