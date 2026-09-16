# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-09-08

### Changed
- Refactored action_format.py for improved code structure and maintainability
- Simplified test suite by removing redundant test cases
- Code cleanup: removed extra whitespace in main.py

### Added
- Enhanced dependency management with updated uv.lock

## [0.3.0] - 2026-09-08

### Fixed
- Fixed syntax error in logging statement (missing comma)
- Fixed missing return statements in exception handlers
- Improved type annotations for mypy compliance

### Changed
- Added proper type hints with `Any` type for dynamic data processing
- Restructured timestamp conversion logic for better type safety
- Code formatted with Black and passes mypy type checking

## [0.2.1] - 2026-09-08

### Changed
- Minor version update

## [0.2.0] - 2026-09-08

### Changed
- Changed `data` field from dict type to string type (JSON string) for better compatibility with Sekoia platform
- Improved module description to highlight automatic epoch timestamp conversion feature
- Enhanced error handling to include JSON parsing errors

## Unreleased

[0.4.0]: https://github.com/yourusername/SekoiaFormatter/releases/tag/v0.4.0
[0.3.0]: https://github.com/yourusername/SekoiaFormatter/releases/tag/v0.3.0
[0.2.1]: https://github.com/yourusername/SekoiaFormatter/releases/tag/v0.2.1
[0.2.0]: https://github.com/yourusername/SekoiaFormatter/releases/tag/v0.2.0
