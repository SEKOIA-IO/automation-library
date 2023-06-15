FROM python:3.11

WORKDIR /app

RUN curl https://packages.confluent.io/deb/7.0/archive.key | gpg --dearmor > /usr/share/keyrings/confluent.gpg && \
    echo 'deb [signed-by=/usr/share/keyrings/confluent.gpg] https://packages.confluent.io/clients/deb focal main' > /etc/apt/sources.list.d/confluent.list && \
    apt-get update && \
    apt-get install -y librdkafka1 librdkafka++1 librdkafka-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install poetry

# Install dependencies
COPY poetry.lock pyproject.toml sentinel-mgmt-sdk.tar.gz /app/
RUN poetry config virtualenvs.create false && poetry install --no-dev

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
