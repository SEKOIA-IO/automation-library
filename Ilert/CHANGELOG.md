# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- Upgraded `sekoia-automation-sdk` to 1.23.1 and migrated `pydantic.v1`-shim models to native Pydantic v2 to avoid a v1/v2 model-mixing error

## 2026-07-09 - 1.0.1

### Fixed

- Validate the `alert_uuid`, `api_key`, and `base_url` arguments via a Pydantic model, with `alert_uuid` parsed as `UUID`, `base_url` parsed as `HttpUrl`, and `api_key` kept as a non-empty string while still rejecting missing/empty/blank values before fetching and forwarding the alert

## 2026-04-10 - 1.0.0

### Added

- Initial release
- Trigger Alert action: forwards raw Sekoia.io alert to ilert Events API
