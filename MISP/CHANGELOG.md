# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased


## 2026-03-05 - 2.8.11

### Added

- Added IOC value validation before pushing to the IOC Collection: each extracted value is validated against a regex pattern matching its MISP type (IPv4, domain, URL, MD5, SHA1, SHA256) — invalid values are skipped with a warning log instead of being sent to the API

### Fixed

- Fixed Sekoia IOC Collection API calls being blocked by the corporate proxy: requests to the internal Sekoia API now always bypass the proxy (`trust_env=False`, `verify=False` on the session) — the proxy configuration in the module only applies to MISP connectivity
- Fixed `NO_PROXY` bypass failing due to trailing newline (`\n`) in the environment variable value: `urllib.request.getproxies()` preserves the newline which breaks hostname matching in `requests` — now stripped with `.strip()`
- Fixed old attributes from re-published MISP events being re-fetched and re-sent to the IOC Collection: the MISP search now filters on both `publish_timestamp` (event publication date) and `timestamp` (attribute modification date), so only attributes actually created or modified within the configured time window are retrieved

### Changed

- Added a 5-second pause between IOC batches when pushing to the Sekoia IOC Collection API to avoid overwhelming the endpoint
- Increased the deduplication cache capacity from 10 000 to 100 000 attribute UUIDs

## 2026-03-03 - 2.8.10

### Fixed

- Fixed proxy bypass not working for internal hostnames listed in `NO_PROXY`: `urllib.request.getproxies()` returns the key `'no'` but `requests` expects `'no_proxy'`, causing all requests to go through the proxy regardless of `NO_PROXY`
- Fixed HTTP 202 responses being treated as errors when pushing IOCs to the IOC Collection
- Fixed `STIXConverter.add_custom()` method missing, causing `AttributeError` when converting unsupported MISP attribute types
- Fixed `initialize_misp_types()` mutating the global `mispTypesMapping` dict, causing cross-test pollution when running the test suite
- Fixed `handler()` in `STIXConverter` catching internal `KeyError` exceptions too broadly, masking real errors
- Fixed `valid_from` field in STIX `Indicator` objects using a date-only string (`YYYY-MM-DD`) instead of the required datetime format (`YYYY-MM-DDT00:00:00Z`)

### Changed

- HTTP 202 responses from the IOC Collection API now log the async `task_id` instead of misleading `0 created/updated/ignored` counts

### Added

- More observability on the trigger logs


## 2026-01-29 - 2.8.3

### Added

- Automatic proxy detection from environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`) when no explicit proxy configuration is provided in module settings
- Type annotations for improved code quality and IDE support

### Changed

- Proxy configuration now uses `urllib.request.getproxies()` as fallback when `http_proxy`/`https_proxy` are not set in module configuration

## 2024-05-28 - 2.8.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 2.7.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
