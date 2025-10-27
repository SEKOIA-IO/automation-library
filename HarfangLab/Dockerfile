FROM python:3.11

WORKDIR /app

# Update CA certificates to fix SSL verification issues
RUN apt-get update && apt-get upgrade -y ca-certificates && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

# Install dependencies
COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false && poetry install --only main

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]