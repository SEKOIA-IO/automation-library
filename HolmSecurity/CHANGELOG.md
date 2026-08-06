# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-08-03

### Added

- Vulnerability asset connector that collects findings from `GET /v2/net-assets/report/vulnerabilities/`, correlates them with managed devices from `GET /v2/devices`, and maps them to the OCSF Vulnerability Finding model
- `get_mapped_fields` and `reset_checkpoint` on both asset connectors, enabling automatic checkpoint reset when the field mapping changes (required by sekoia-automation-sdk 1.24.0)

### Changed

- Account validator updates to reflect vulnerability setup
- Bump `sekoia-automation-sdk` to 1.24.0

## [1.1.0] - 2026-07-31

### Added

- Add holm logo to the module folder
- Update the connector description

## [1.0.0] - 2026-07-17

### Added

- Holm Security module with API token authentication
- Account validator
- Device asset connector that collects agent-managed devices from `GET /v2/devices` and maps them to the OCSF Device Inventory Info model
