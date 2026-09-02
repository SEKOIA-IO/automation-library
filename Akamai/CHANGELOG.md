# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-09-02

### Added

- Increase test coverage to 100% across connector, models, and logging modules with targeted branch tests and regression tests
- Add defensive handling for malformed Akamai stream lines, per-event processing failures, non-dict `httpMessage` payloads, and pagination context entries without offset
- Add concise docstrings to each connector method to improve code readability and maintainability

### Changed

- Standardize connector logging on `self.log(message=..., level=...)` with concise single-line `key=value` messages and explicit request-id fields by source
- Add privacy-safe and sampled diagnostics for high-frequency warning/debug paths to reduce log noise while preserving troubleshooting context
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
