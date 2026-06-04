FROM python:3.11-slim

# Create a non-root user
RUN useradd -m sekoiaio-runtime
USER sekoiaio-runtime
WORKDIR /home/sekoiaio-runtime

# Install Poetry
RUN pip install --user poetry

# Copy project files
COPY --chown=sekoiaio-runtime:sekoiaio-runtime pyproject.toml poetry.lock* ./
COPY --chown=sekoiaio-runtime:sekoiaio-runtime CHANGELOG.md manifest.json action_dns_reverse_search.json ./
COPY --chown=sekoiaio-runtime:sekoiaio-runtime main.py ./
COPY --chown=sekoiaio-runtime:sekoiaio-runtime dns_modules/ ./dns_modules/

# Install dependencies
ENV PATH="/home/sekoiaio-runtime/.local/bin:${PATH}"
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

ENTRYPOINT ["python", "main.py"]
