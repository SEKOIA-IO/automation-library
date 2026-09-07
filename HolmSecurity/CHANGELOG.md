# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.1] - 2026-09-03

### Fixed

- Both asset connectors no longer abort a whole collection cycle when the Holm API
  reports a field as `null` instead of omitting it. A pydantic default only applies to
  an absent key, so a single `"risk_score": null` or `"open_ports": null` on one network
  asset failed the validation of the entire page and no asset was ever pushed
- `emails` of a device is a list of `{email, username}` objects, not a list of addresses

### Changed

- Every optional field of the Holm API models is now nullable, following the published
  API schema: a `null` is kept as `null` instead of being replaced by a fabricated
  default. An absent `risk_score` is no longer reported as a score of `0`, and a real
  score of `0` is now reported instead of being dropped

## [1.3.0] - 2026-08-20

### Added

- Device asset connector now also collects the scanned network assets from
  `GET /v2/net-assets` and publishes them as OCSF Device Inventory Info events
  alongside the agent-managed devices. They share the deduplication cache but keep
  their own `last_detected` cursor

## [1.2.1] - 2026-08-20

### Fixed

- Replace `assert isinstance` guards with explicit `if/raise TypeError` to prevent silent failures when Python runs with the `-O` optimization flag

## [1.2.0] - 2026-08-18

### Added

- Vulnerability asset connector that collects the vulnerability findings.

### Changed

- Account validator now checks both inventories, `GET /v2/devices` and `GET /v2/net-assets`
- Bump `sekoia-automation-sdk` to 1.24.0

### Fixed

- Pagination now uses the `limit` query parameter on every endpoint.
- CVSS base scores of `0.0` are no longer dropped from the emitted vulnerabilities

## [1.1.0] - 2026-07-31

### Added

- Add holm logo to the module folder
- Update the connector description

## [1.0.0] - 2026-07-17

### Added

- Holm Security module with API token authentication
- Account validator
- Device asset connector that collects agent-managed devices from `GET /v2/devices` and maps them to the OCSF Device Inventory Info model
