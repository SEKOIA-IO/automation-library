# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Unit tests for the LocateRisk connector covering CSV parsing, empty rows, HTTP errors, and BOM handling.

### Changed

- Declared connector secrets only in the module manifest (removed the redundant Pydantic `json_schema_extra` flag).
- Aligned `pyproject.toml` project version with the module manifest version.
- Added a description for the `report_url` module configuration field.

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
