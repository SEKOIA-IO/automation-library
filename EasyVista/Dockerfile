FROM python:3.11-bookworm

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /bin/
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-default-groups --no-install-project
ENV PATH="/app/.venv/bin:$PATH"
COPY . .
RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime
ENTRYPOINT ["python", "./main.py"]
