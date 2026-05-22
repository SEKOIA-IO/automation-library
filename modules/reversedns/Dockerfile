FROM python:3.12-slim

WORKDIR /app

# Installation de la version exacte de Poetry
RUN pip install poetry==2.4.1

# Copie des fichiers de dépendances verrouillés
COPY pyproject.toml poetry.lock ./

# Installation des paquets sans créer d'environnement virtuel interne
RUN poetry config virtualenvs.create false && poetry install --only main --no-interaction

# Copie du reste du projet
COPY . .

# Sécurisation avec un utilisateur non-root
RUN useradd -ms /bin/bash sekoiaio-runtime
USER sekoiaio-runtime

ENTRYPOINT [ "python", "./main.py" ]
