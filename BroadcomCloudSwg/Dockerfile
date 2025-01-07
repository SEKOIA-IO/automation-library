FROM python:3.11

WORKDIR /app

# Explicitly install gcc and libssl-dev for cryptography
RUN apt-get install -y gcc libssl-dev

RUN pip install poetry

# Install dependencies
COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false && poetry install --only main

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
