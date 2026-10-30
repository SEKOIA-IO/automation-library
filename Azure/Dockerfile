FROM python:3.13

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

USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
