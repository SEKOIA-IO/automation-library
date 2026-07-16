# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed

- Reuse the connector's configured limiter as the SDK's per-event limiter (`_events_limiter`) to stop double-throttling events, and clarify the `throttle_seconds` description
- Regenerate `poetry.lock` to match `pyproject.toml`
- Fix `isort` ordering in `tests/conftest.py`
- Modernize `pyproject.toml` (`tool.poetry.group.dev.dependencies`, `tool.mypy` strict config)

### Added

- Prometheus metrics (`OUTCOMING_EVENTS`, `EVENTS_LAG`, `FORWARD_EVENTS_DURATION`) for the Flare events trigger
- Mark `api_key` as a secret field on `FlareIOModuleConfiguration`

## 2026-06-08 - 0.2.0

### Added

- Add Flare events pull trigger using the official `flareio` SDK
- Add account validator based on `/tokens/test`

## 2026-06-08 - 0.1.0

### Added

- Initial module scaffolding for Flare.io
