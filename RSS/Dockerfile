FROM python:3.11

WORKDIR /app

RUN pip install poetry

# Install dependencies
COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false && poetry install --only main

COPY . .

# Create user
RUN useradd -ms /bin/bash sekoiaio-runtime

# Create the folder for the cache
RUN mkdir /var/cache/symphony_rss_module && chown sekoiaio-runtime:sekoiaio-runtime /var/cache/symphony_rss_module && chmod u+rwx /var/cache/symphony_rss_module


USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
