# Development Guidelines

## Overview

This document defines code standards, best practices, and required checks for contributing to the automation library.

## Configuration Scopes

### Module Configuration vs Component Configuration

Understanding configuration scopes is critical:

| Configuration Type | Location | Scope | Purpose | Example |
|-------------------|----------|-------|---------|---------|
| **Module Configuration** | `manifest.json` → `configuration` field | Module-wide | Account credentials, base URLs, shared settings | API keys, tenant ID, region |
| **Action Configuration** | `action_*.json` → `arguments` field | Action-specific | Input parameters for the action | User ID, email address |
| **Trigger Configuration** | `trigger_*.json` → `arguments` field | Trigger-specific | Trigger-specific settings | Polling interval, filters |
| **Connector Configuration** | `connector_*.json` → `arguments` field | Connector-specific | Connector-specific settings | Log source, frequency |

### Configuration Guidelines

- **Module configuration**: Use for authentication credentials and settings shared across all actions/triggers/connectors
- **Component configuration**: Use for parameters specific to individual actions, triggers, or connectors
- Avoid duplicating module-level configuration in component-level schemas

## Code Quality Requirements

### Type Checking with Mypy

**REQUIRED**: Run mypy type checking before submitting any pull request.

#### Command

```bash
poetry add --group dev mypy
poetry run mypy --install-types --non-interactive --ignore-missing-imports --show-column-numbers --hide-error-context .
```

#### Requirements

- Code MUST pass mypy validation without errors
- Add type hints to all function signatures
- Use `typing` module for complex types (e.g., `Optional`, `List`, `Dict`)

#### Example

```python
from typing import Optional, List, Dict
from pydantic import BaseModel

def process_users(
    user_ids: List[str],
    options: Optional[Dict[str, str]] = None
) -> List[Dict[str, str]]:
    # Implementation
    pass
```

## Versioning

### Semantic Versioning

**REQUIRED**: Follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) for all module versions.

#### Version Format

```
MAJOR.MINOR.PATCH
```

Where:
- **MAJOR**: Incompatible API changes (e.g., changing action UUID, removing parameters)
- **MINOR**: Backward-compatible functionality additions (e.g., new actions, new optional parameters)
- **PATCH**: Backward-compatible bug fixes

#### When to Increment

| Change Type | Version Increment | Example |
|------------|-------------------|---------|
| Breaking change | MAJOR | Changing action UUID, removing required field |
| New feature | MINOR | Adding new action, adding optional parameter |
| Bug fix | PATCH | Fixing incorrect API call, correcting logic error |
| Documentation | PATCH | Updating README, fixing typos |

#### Process

1. Update version in `manifest.json`:
   ```json
   {
     "version": "1.2.3"
   }
   ```

2. Document changes in `CHANGELOG.md`:
   ```markdown
   ## [1.2.3] - 2024-01-15
   ### Fixed
   - Fixed user creation API endpoint
   ```

### CHANGELOG Format

Use [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
# Changelog

## [Unreleased]

## [1.2.0] - 2024-01-15
### Added
- New "Delete User" action
- Support for bulk operations

### Changed
- Improved error handling in user creation

### Fixed
- Fixed authentication token refresh

### Deprecated
- Old authentication method (use OAuth2 instead)

## [1.1.0] - 2024-01-01
...
```

## Code Style

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Import Organization

```python
# Standard library imports
import os
import time
from typing import Optional

# Third-party imports
import requests
from pydantic import BaseModel

# Local imports
from sekoia_automation import Action
from module_name_module import ModuleConfiguration
```

### Documentation Strings

Use docstrings for classes and public methods:

```python
def fetch_user(self, user_id: str) -> Dict[str, str]:
    """
    Fetch user details from the API.
    
    Args:
        user_id: The unique identifier for the user
        
    Returns:
        Dictionary containing user details
        
    Raises:
        APIError: If the API request fails
    """
    pass
```

## Testing Requirements

- Add tests for all new actions, triggers, and connectors
- Maintain or improve code coverage
- Mock external API calls
- Test edge cases and error conditions

See [Testing documentation](testing.md) for details.

## Pull Request Guidelines

### Before Submitting

- [ ] Run mypy type checking
- [ ] Run all tests (`poetry run pytest tests/`)
- [ ] Update version in `manifest.json`
- [ ] Update `CHANGELOG.md`
- [ ] Update documentation if needed
- [ ] Ensure no linting errors

### PR Description

Include:
- Summary of changes
- Related issue numbers
- Testing performed
- Breaking changes (if any)

## Breaking Changes

### Definition

A breaking change is any modification that requires users to update their existing configurations or playbooks.

### Examples of Breaking Changes

- Changing module, action, trigger, or connector UUID
- Removing or renaming configuration parameters
- Changing parameter types (e.g., string to integer)
- Changing action output schema
- Removing actions, triggers, or connectors

### Handling Breaking Changes

1. Increment MAJOR version
2. Document in CHANGELOG with `### BREAKING CHANGES` section
3. Provide migration guide if possible
4. Update all related documentation

## Security Guidelines

- **NEVER** commit credentials, API keys, or secrets to the repository
- Use environment variables or secure configuration management
- Validate and sanitize all user inputs
- Use HTTPS for all API communications
- Follow principle of least privilege for API permissions

## Error Handling

### Best Practices

```python
from sekoia_automation import Action
from requests.exceptions import RequestException

class MyAction(Action):
    def run(self, arguments):
        try:
            response = self.api_call(arguments)
            return self.process_response(response)
        except RequestException as e:
            self.log(f"API request failed: {e}", level="error")
            raise
        except Exception as e:
            self.log(f"Unexpected error: {e}", level="error")
            raise
```

### Logging

- Use `self.log()` method for logging
- Include relevant context in log messages
- Use appropriate log levels: `debug`, `info`, `warning`, `error`

## Dependencies Management

### Adding Dependencies

1. Add to `pyproject.toml`:
   ```toml
   [tool.poetry.dependencies]
   python = "^3.10"
   new-package = "^1.0.0"
   ```

2. Lock dependencies:
   ```bash
   poetry lock
   ```

3. Document reason for new dependency

### Dependency Updates

- Keep dependencies up to date for security patches
- Test thoroughly after updating dependencies
- Document any breaking changes from dependency updates

