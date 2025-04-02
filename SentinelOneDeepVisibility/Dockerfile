FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y git nano

RUN pip install poetry

# To retrieve the AWS package locally 
RUN git clone https://github.com/SEKOIA-IO/automation-library

WORKDIR /app/automation-library/build/

COPY . .

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install --only main

# Clean /tmp from poetry installations
RUN rm -rf /tmp/*

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
