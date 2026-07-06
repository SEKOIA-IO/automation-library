FROM python:3.11

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml /app/
RUN poetry config virtualenvs.create false && poetry install --only main --no-root

COPY . /app/

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT ["python", "/app/main.py"]
