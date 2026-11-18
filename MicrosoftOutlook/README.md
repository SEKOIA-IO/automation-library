# Microsoft Outlook Automation Module

## Linter Commands

Run all commands below from the project root.

### Prerequisites

```bash
uv sync
```

### Check Linters

```bash
uv run ruff format --check .
uv run ruff check --no-fix .
uv run mypy .
uv run python ../linter.py check --changes
```

### Auto-fix When Possible

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy .
uv run python ../linter.py fix --changes
```

### Single Command (Full Validation)

```bash
uv run ruff format --check . && uv run ruff check --no-fix . && uv run mypy . && uv run python ../linter.py check --changes
```

### Run Tests

```bash
uv run python -m pytest --junit-xml=junit.xml --cov-report term --cov-report xml:coverage.xml --cov . --cov-config pyproject.toml -vv
```
