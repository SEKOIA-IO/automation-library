# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-09-04

### Added

- Increase test coverage to 100% across connector, models, and logging modules with targeted branch tests and regression tests
- Add defensive handling for malformed Akamai stream lines, per-event processing failures, non-dict `httpMessage` payloads, and pagination context entries without offset
- Add concise docstrings to each connector method to improve code readability and maintainability
- Add structured raw diagnostic payload fields (`raw_event`, `raw_context`, `raw_line`, `raw_item`, `raw_http_message`) in warning/error logging paths for troubleshooting
- Add a safeguard that emits only the first log for strictly identical `process_event` exceptions (same key, exception signature, and raw-event message)
- Add configurable raw diagnostic payload truncation with `AKAMAI_RAW_LOG_MAX_LENGTH` (default: 16000)
- Add configurable exception deduplication cache size with `AKAMAI_LOG_COUNT_MAX_KEYS` (default: 10000)

### Changed

- Standardize connector logging on `self.log(message=..., level=...)` with concise single-line `key=value` messages and explicit request-id fields by source
- Rename and reorganize test files to align with source modules (`connector_akamai_waf`, `metrics`, `models`)
- Refactor repeated test scenarios with `pytest.mark.parametrize` to reduce duplication and improve maintainability
- Align `pyproject.toml` dependency declarations with directly imported runtime packages and regenerate `poetry.lock`

### Fixed

- Fix a crash in HTTP header parsing (`ValueError: not enough values to unpack`) caused by malformed header lines returned by the Akamai SIEM stream
- Make header parsing resilient to malformed input (missing separator, empty key, non-string headers) so event ingestion continues instead of stopping
- Handle missing `requestId` and invalid or missing `httpMessage.start` values without breaking batch processing
- Prevent repeated redelivery of events without `requestId` when `httpMessage.start` is invalid or missing by using a fallback payload-based deduplication key

### Removed

- Remove module-level logger usage after standardizing on `self.log(message=..., level=...)` across the connector

## [1.0.1] - 2026-04-16

### Changed

- Optimize Akamai WAF event fetching by streaming events in chunks instead of accumulating a full page in memory

## [1.0.0] - 2026-01-07

### Changed

- Release module
