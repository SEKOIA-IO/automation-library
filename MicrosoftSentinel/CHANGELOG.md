# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-26 - 1.1.1

### Changed

- Migrated module from Poetry to uv (Python 3.14, ruff, mypy, mise)
- Upgraded sekoia-automation-sdk from 1.18.2 to 1.27.0
- Moved to pydantic v2 APIs (`model_fields`, `json_schema_extra`)

### Fixed

- Persist the incidents checkpoint so the connector resumes from the last collected incident after a restart

## 2026-05-27 - 1.1.0

### Added
- Fetch and forward incident entities from the list-entities endpoint.

## 2025-02-03 - 1.0.0

### Added

- Add the connector for the first time