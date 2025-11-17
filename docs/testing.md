# Testing

## Overview

All modules should include tests to verify functionality and prevent regressions. Tests ensure that actions, triggers, and connectors work correctly before deployment.

## Test Organization

### Test Directory Structure

```
ModuleName/
├── tests/
│   ├── __init__.py
│   ├── test_actions.py
│   ├── test_triggers.py
│   ├── test_connectors.py
│   └── conftest.py          # Shared fixtures
├── module_name_module/
└── main.py
```

### Test File Naming

- Test files MUST be named `test_*.py`
- Test functions MUST be named `test_*`
- Test classes MUST be named `Test*`

## Running Tests

### Execute All Tests

```bash
poetry run pytest tests/
```

### Execute Specific Test File

```bash
poetry run pytest tests/test_actions.py
```

### Execute Specific Test Function

```bash
poetry run pytest tests/test_actions.py::test_enable_user
```

### Run with Verbose Output

```bash
poetry run pytest tests/ -v
```

### Run with Coverage Report

```bash
poetry run pytest tests/ --cov=module_name_module --cov-report=html
```

## Writing Tests

### Testing Actions

```python
import pytest
from module_name_module.actions import EnableUserAction
from module_name_module import ModuleConfiguration

def test_enable_user_action():
    # Arrange
    action = EnableUserAction()
    action.module.configuration = ModuleConfiguration(
        api_key="test_key"
    )
    arguments = EnableUserAction.Arguments(
        user_id="user123"
    )
    
    # Act
    result = action.run(arguments)
    
    # Assert
    assert result.success is True
    assert result.user_email is not None
```

### Testing Triggers

```python
import pytest
from unittest.mock import Mock, patch
from module_name_module.triggers import UserEventTrigger

def test_trigger_sends_event():
    # Arrange
    trigger = UserEventTrigger()
    trigger.send_event = Mock()
    trigger.configuration = UserEventTrigger.Configuration(
        frequency=60
    )
    
    # Act
    with patch.object(trigger, 'fetch_event', return_value={"user_id": "123"}):
        trigger.run()
    
    # Assert
    trigger.send_event.assert_called_once()
```

### Testing Connectors

```python
import pytest
from unittest.mock import Mock, patch
from module_name_module.connectors import SystemLogConnector

def test_connector_forwards_events():
    # Arrange
    connector = SystemLogConnector()
    connector.publish_events_to_intake = Mock()
    connector.configuration = SystemLogConnector.Configuration(
        api_key="test_key",
        frequency=60
    )
    
    # Act
    events = [{"log": "test event"}]
    with patch.object(connector, 'fetch_events', return_value=events):
        connector.publish_events_to_intake(events)
    
    # Assert
    connector.publish_events_to_intake.assert_called_once_with(events)
```

## Best Practices

### Use Fixtures

Define shared test setup in `conftest.py`:

```python
import pytest
from module_name_module import ModuleConfiguration

@pytest.fixture
def module_configuration():
    return ModuleConfiguration(
        api_key="test_key",
        base_url="https://test.example.com"
    )

@pytest.fixture
def mock_api_client(monkeypatch):
    # Mock external API calls
    pass
```

### Mock External Dependencies

Always mock external API calls, file I/O, and network requests:

```python
from unittest.mock import patch, Mock

@patch('module_name_module.actions.requests.post')
def test_action_with_api_call(mock_post):
    mock_post.return_value = Mock(status_code=200, json=lambda: {"success": True})
    # Test implementation
```

### Test Edge Cases

Include tests for:
- Invalid input
- API errors and timeouts
- Empty responses
- Rate limiting
- Authentication failures

### Parametrized Tests

Use `pytest.mark.parametrize` for multiple test cases:

```python
@pytest.mark.parametrize("user_id,expected", [
    ("user123", True),
    ("user456", True),
    ("invalid", False),
])
def test_enable_user_multiple_cases(user_id, expected):
    # Test implementation
```

## Continuous Integration

Tests should run automatically on:
- Pull request creation
- Commits to main branch
- Release builds

Ensure all tests pass before merging code.
