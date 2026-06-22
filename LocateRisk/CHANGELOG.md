# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.3.1 - 2026-06-22

### Fixed

- Fixed the Docker build failure (`"/uv": not found`) by copying the `uv`/`uvx` binaries from the standalone `ghcr.io/astral-sh/uv:latest` image (which exposes them at the root) instead of `astral/uv:python3.11-trixie`, where they live under `/usr/local/bin/`.

## 0.3.0 - 2026-06-19

### Added

- Added `metrics.py` exposing Prometheus metrics (`symphony_module_locaterisk_collected_messages`, plus common `forwarded_events` and `forward_events_duration`) and wired them into the connector's polling loop.

## 0.2.0 - 2026-06-17

### Added

- Unit tests for the LocateRisk connector covering CSV parsing, empty rows, HTTP errors, and BOM handling.
- Mounted a `urllib3` retry adapter on the connector's `requests` session so transient HTTP errors (429/502/503) are retried with back-off instead of dropping the polling cycle.
- Added `isort` to the dev dependency group to match the configured `[tool.isort]` section.

### Changed

- Marked `api_key` and `scan_id` with `Field(json_schema_extra={"secret": True})` so the Pydantic models stay the source of truth for the manifest `secrets` array on regeneration (mypy-clean, non-deprecated form).
- Aligned `pyproject.toml` project version with the module manifest version (`0.2.0`).
- Replaced the blocking `time.sleep()` between polling cycles with `self._stop_event.wait()` so the connector shuts down promptly when stopped.
- Added a description for the `report_url` module configuration field.
- Extracted the report CSV URL construction into a `_build_report_url()` helper for a single source of truth.
- Guarded the "No events to push this cycle" log behind an error flag so failed polling cycles no longer log as empty successful ones.
- Consolidated dev dependencies into a single `[dependency-groups]` table in `pyproject.toml` (removed the duplicate `[project.dependency-group.dev]` block).

### Removed

- Stale `poetry.lock` file (the module uses `uv`).

### Renamed (internal)

- Module class `LocateriskModule` → `LocateRiskModule`.
- Connector class `LocateriskConnector` → `LocateRiskScanReportConnector`.
- Connector manifest `connector_locateriskconnector.json` → `connector_locaterisk_scan_report.json`.
- Connector implementation `locaterisk_modules/connector.py` → `locaterisk_modules/connector_locaterisk_scan_report.py`.
- `docker_parameters` value `LocateriskConnector` → `locaterisk_scan_report` (snake_case, matches repo convention).

## 0.1.8 - 2026-05-26

### Fixed

- Resolved an issue with the report URL in the connector.

## 0.1.7 - 2026-05-26

### Added

- Connector now transforms CSV responses into JSON before parsing.

## 0.1.6 - 2026-05-22

### Fixed

- Added sanitization of incoming data so the parser handles the response reliably.

## 0.1.5 - 2026-05-22

### Changed

- Removed the CSV-to-JSON transformation from the connector.

## 0.1.4 - 2026-05-22

### Changed

- Switched response encoding from `utf-8` to `utf-8-sig` to handle BOM-prefixed CSV payloads.

## 0.1.3 - 2026-05-22

### Added

- Added `utf-8` encoding to the connector response.

## 0.1.2 - 2026-05-22

### Changed

- Updated the module logo (squared) and applied connector modifications.

## 0.1.1 - 2026-05-22

### Added

- Connector support for CSV import.

## 0.1.0 - 2026-05-22

### Added

- Initial release of the LocateRisk module with the report-export connector.
- Module configuration with `api_key`, `scan_id`, and configurable `report_url`.
