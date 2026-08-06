# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased


## 2026-07-20 - 0.6.0

### Changed

- Update Flare description in `manifest.json` to provide a more detailed overview of the integration's capabilities and purpose.

## 2026-07-20 - 0.5.0

### Changed

- Speed up event collection by streaming events to the intake in batches of 100 (instead of a single push at the end) and advancing the checkpoint on page boundaries
- Remove the SDK's default 1s-per-page delay by pacing both page and event requests with the configured `throttle_seconds`, and lower its minimum to `0`
- Rely on the Flare SDK's built-in session/retry policy and drop the redundant custom `requests.Session`
- Simplify the connector by removing the stale-cursor retry and verbose diagnostics helpers

### Fixed

- Align event feed paging with the Flare SDK documentation by using `/firework/v4/events/tenant/_search`
- Comply with Flare v4 global search validation by always capping `page_size` to 10

## 2026-07-20 - 0.4.0

### Fixed

- Reuse the connector's configured limiter as the SDK's per-event limiter (`_events_limiter`) to stop double-throttling events, and clarify the `throttle_seconds` description
- Regenerate `poetry.lock` to match `pyproject.toml`
- Fix `isort` ordering in `tests/conftest.py`
- Modernize `pyproject.toml` (`tool.poetry.group.dev.dependencies`, `tool.mypy` strict config)
- Redirect hardcoded SDK writes to `/tmp/tls` into writable `/dev/shm` in the container image to avoid read-only filesystem failures

### Added

- Prometheus metrics (`OUTCOMING_EVENTS`, `EVENTS_LAG`, `FORWARD_EVENTS_DURATION`) for the Flare events trigger
- Mark `api_key` as a secret field on `FlareIOModuleConfiguration`

## 2026-07-10 - 0.3.0

### Changed

- Migrated module from Poetry to uv

## 2026-06-08 - 0.2.0

### Added

- Add Flare events pull trigger using the official `flareio` SDK
- Add account validator based on `/tokens/test`

## 2026-06-08 - 0.1.0

### Added

- Initial module scaffolding for Flare.io
