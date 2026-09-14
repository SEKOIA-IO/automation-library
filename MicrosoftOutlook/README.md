# Microsoft Outlook Automation Module

## Linter Commands

Run all commands below from the project root.

### Prerequisites

```bash
poetry install
```

### Check Linters

```bash
poetry run black --check .
poetry run isort --check-only .
poetry run mypy .
poetry run ruff check .
```

### Auto-fix When Possible

```bash
poetry run black .
poetry run isort .
poetry run ruff check . --fix
```

### Single Command (Full Validation)

```bash
poetry run black --check . && poetry run isort --check-only . && poetry run mypy . && poetry run ruff check .
```

### Run Tests

```bash
poetry run python -m pytest --junit-xml=junit.xml --cov-report term --cov-report xml:coverage.xml --cov . --cov-config pyproject.toml -vv
```
