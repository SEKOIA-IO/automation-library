# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- Deduplicate ESET vulnerability findings by identity (device UUID, scope, vulnerability id and CVE) instead of by `lastDetectTime`. The `/v1/device-vulnerabilities` endpoint has no time filter, and ESET refreshes `lastDetectTime` on every rescan, so the previous high-water mark either skipped nothing or hid findings whose severity or patch status had changed. The stored checkpoint is now pruned on each cycle to the findings ESET still reports, so it stays bounded by the live inventory. Existing deployments collect the full vulnerability inventory once on upgrade.

### Fixed

- Collect every vulnerability variant carried by a `/v1/device-vulnerabilities` item. An item exposing an application, an operating system and a package vulnerability at the same time previously produced a single finding and silently dropped the others.

## 2026-08-06 - 1.2.0

### Added

- Declare the ESET to OCSF field mappings of the device and vulnerability asset connectors, so that the checkpoint is automatically reset and all assets re-collected whenever a mapping changes.

### Fixed

- Implement `get_mapped_fields` and `reset_checkpoint` on both asset connectors, which sekoia-automation-sdk 1.24.0 made abstract.

## 2026-07-03 - 1.1.0

### Added

- Add ESET vulnerability asset connector.
- Map ESET `patchAvailable` and `riskScore` to OCSF `is_fix_available` and `risk_score` (requires sekoia-automation-sdk >= 1.24.0).

## 2025-06-28 - 1.0.2

### Added

- Add new asset device connector for ESET Protect to support new asset device API endpoints.

## 2025-08-04 - 1.0.1

### Fixed

- Add required header to all requests to the ESET API.
