# Sekoia Formatter

A powerful text formatting module for the Sekoia automation platform that applies Python f-string style templates with automatic epoch timestamp conversion to readable datetime formats.

## Features

- **Python f-string formatting**: Use familiar Python f-string syntax for text templating
- **Automatic epoch conversion**: Automatically detects and converts Unix epoch timestamps to datetime objects
- **Datetime formatting**: Apply datetime formatting codes to epoch timestamps
- **Flexible data types**: Support for strings, numbers, booleans, lists, dictionaries, and more
- **Format specifications**: Full support for Python format specifications (alignment, padding, number formatting)
- **Error handling**: Comprehensive error handling with detailed logging

## Installation

This module is built for the Sekoia automation platform and requires:

- Python >= 3.11
- `sekoia-automation-sdk`

Install dependencies using `uv`:

```bash
uv sync
```

## Usage

### Basic Example

```python
from sekoia_formatter_modules.action_format import FormatAction, FormatArguments

# Create action instance
action = FormatAction()

# Format a simple template
arguments = FormatArguments(
    template="Hello {name}!",
    data='{"name": "World"}'
)

result = action.run(arguments)
# Output: {"formatted_text": "Hello World!"}
```

### Epoch Timestamp Conversion

The module automatically detects and converts Unix epoch timestamps (numbers > 1000000000) to datetime objects:

```python
arguments = FormatArguments(
    template="Event occurred on {timestamp:%Y-%m-%d %H:%M:%S}",
    data='{"timestamp": 1704067200}'
)

result = action.run(arguments)
# Output: {"formatted_text": "Event occurred on 2024-01-01 00:00:00"}
```

### Multiple Variables

```python
arguments = FormatArguments(
    template="User {name} (ID: {user_id}) logged in at {login_time:%Y-%m-%d %H:%M}",
    data='{"name": "Alice", "user_id": 12345, "login_time": 1704067200}'
)

result = action.run(arguments)
# Output: User Alice (ID: 12345) logged in at 2024-01-01 00:00
```

### Format Specifications

Python format specifications are fully supported:

```python
# Number formatting
arguments = FormatArguments(
    template="Price: ${amount:.2f}, Discount: {discount:.1%}",
    data='{"amount": 19.99, "discount": 0.15}'
)
# Output: Price: $19.99, Discount: 15.0%

# Text alignment
arguments = FormatArguments(
    template="Left: '{text:<10}' Right: '{text:>10}' Center: '{text:^10}'",
    data='{"text": "Hi"}'
)
# Output: Left: 'Hi        ' Right: '        Hi' Center: '    Hi    '

# Number bases
arguments = FormatArguments(
    template="Hex: {num:x}, Binary: {num:b}",
    data='{"num": 255}'
)
# Output: Hex: ff, Binary: 11111111
```

## Module Structure

```
SekoiaFormatter/
├── sekoia_formatter_modules/
│   ├── __init__.py          # Module initialization
│   ├── models.py            # Configuration models
│   └── action_format.py     # Main formatting action
├── tests/
│   ├── conftest.py          # Test configuration
│   ├── test_action_format.py # Comprehensive test suite
│   └── __init__.py
├── main.py                  # Module entry point
├── manifest.json            # Module manifest
├── pyproject.toml           # Project configuration
├── Dockerfile               # Container configuration
└── README.md                # This file
```

## API Reference

### FormatArguments

Input model for the format action.

**Fields:**
- `template` (str): Template string with Python f-string style placeholders (e.g., `"Hello {name}!"`)
- `data` (str): JSON string containing the variables to format into the template (e.g., `'{"name": "value"}'`)

### FormatResponse

Output model for the format action.

**Fields:**
- `formatted_text` (str): The formatted output text

### FormatAction

The main action class that performs the formatting.

**Methods:**
- `run(arguments: FormatArguments) -> FormatResponse`: Execute the formatting action

**Features:**
- Parses JSON data string
- Automatically converts epoch timestamps (numbers > 1000000000) to datetime objects
- Formats template using Python f-string syntax
- Comprehensive error handling and logging

## Development

### Running Tests

```bash
# Run tests with coverage
pytest

# Run tests with detailed output
pytest -v

# Generate coverage report
pytest --cov=sekoia_formatter_modules --cov-report=html
```

### Test Coverage

The module has comprehensive test coverage including:
- Simple and complex formatting scenarios
- Epoch timestamp conversion
- Error handling (missing variables, invalid templates, invalid JSON)
- Format specifications (alignment, padding, number formatting)
- Edge cases (empty strings, None values, special characters)
- Unicode support
- Multiple data types

### Code Quality

The project uses:
- **Black**: Code formatting (line length: 119)
- **isort**: Import sorting
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting

## Docker

Build and run the module using Docker:

```bash
# Build the image
docker build -t sekoia-formatter .

# Run the container
docker run sekoia-formatter
```

## Versioning

Current version: **0.2.0**

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Error Handling

The module handles various error scenarios:

- **Invalid JSON**: Returns error when data field contains invalid JSON
- **Missing variables**: Returns error when template references undefined variables
- **Invalid template**: Returns error when template has syntax errors
- **General exceptions**: Catches and logs unexpected errors

All errors are logged using the Sekoia automation SDK logging system.

## License

This module is part of the Sekoia automation platform.

## Contributing

1. Ensure all tests pass
2. Maintain test coverage above 5%
3. Follow Black code style (line length: 119)
4. Add tests for new features
5. Update CHANGELOG.md

## Support

For issues and questions, please refer to the Sekoia automation platform documentation.
