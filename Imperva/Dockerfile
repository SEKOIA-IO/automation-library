FROM python:3.11

WORKDIR /app

RUN pip install poetry

# Install dependencies
RUN apt-get update -y && \
    apt-get -y install swig && \
    rm -rf /var/lib/apt/lists/*
COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false && poetry install --only main

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
