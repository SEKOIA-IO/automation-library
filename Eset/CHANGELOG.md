# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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
