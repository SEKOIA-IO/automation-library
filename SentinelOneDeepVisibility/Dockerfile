FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y git nano

RUN pip install poetry
RUN pip install virtualenv==20.28.1
RUN echo pouet

# To retrieve the AWS package locally 
RUN git clone https://github.com/SEKOIA-IO/automation-library -b fix/AWSMemoryIssue

WORKDIR /app/automation-library/build/

COPY . .

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install --only main

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
