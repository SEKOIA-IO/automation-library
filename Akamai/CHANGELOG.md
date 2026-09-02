# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-09-02

### Added

- Enrich operational logs across fetching, pagination, deduplication, checkpoint updates, and batch lifecycle to improve observability
- Increase test coverage to 100% across connector, models, and logging modules with targeted branch tests and regression tests
- Add defensive handling for malformed Akamai stream lines, per-event processing failures, and pagination context entries without offset
- Add warning logs for newly handled error cases to keep ingestion resilient while preserving troubleshooting context
- Add concise docstrings to each connector method to improve code readability and maintainability

### Changed

- Harmonize connector logging by using `self.log(message=..., level=...)` consistently to improve log visibility in Loki/Grafana
- Add privacy-safe diagnostics when malformed HTTP header lines are ignored by reporting counts and malformation types only, without logging raw header line content
- Normalize request identifier semantics in logs by distinguishing `event_request_id`, `api_request_id`, and `api_error_*` fields by source
- Use concise single-line log messages with searchable `key=value` context to optimize Loki/Grafana parsing and querying
- Rename and reorganize test files to align with source modules (`connector_akamai_waf`, `metrics`, `models`)

### Fixed

- Fix a crash in HTTP header parsing (`ValueError: not enough values to unpack`) caused by malformed header lines returned by the Akamai SIEM stream
- Make header parsing resilient to malformed input (missing separator, empty key, non-string headers) so event ingestion continues instead of stopping
- Handle missing `requestId` and invalid or missing `httpMessage.start` values without breaking batch processing

### Removed

- Remove module-level logger usage after standardizing on `self.log(message=..., level=...)` across the connector

## [1.0.1] - 2026-04-16

### Changed

- Optimize Akamai WAF event fetching by streaming events in chunks instead of accumulating a full page in memory

## [1.0.0] - 2026-01-07

### Changed

- Release module
