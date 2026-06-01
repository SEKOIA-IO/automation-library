FROM python:3.14

WORKDIR /app

RUN pip install uv

# Install dependencies
COPY uv.lock pyproject.toml /app/
RUN uv sync --frozen --no-dev --compile-bytecode

COPY . .

RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
