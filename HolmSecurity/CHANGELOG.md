# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-08-18

### Added

- Vulnerability asset connector that collects the vulnerability findings of the scanned
  network assets from `GET /v2/net-assets/report/vulnerabilities/` and maps them to the
  OCSF Vulnerability Finding model. Findings reference their network asset through the
  device uid and hostname only, since the device asset connector publishes the full
  inventory under the same uids
- Device asset connector now also collects the scanned network assets from
  `GET /v2/net-assets` and publishes them as OCSF Device Inventory Info events alongside
  the agent-managed devices
- `get_mapped_fields` and `reset_checkpoint` on both asset connectors, enabling automatic
  checkpoint reset when the field mapping changes (required by sekoia-automation-sdk 1.24.0)

### Changed

- Account validator now checks both inventories, `GET /v2/devices` and `GET /v2/net-assets`
- Bump `sekoia-automation-sdk` to 1.24.0

### Fixed

- Pagination now uses the `limit` query parameter on every endpoint. The Holm API
  paginates with `limit`/`offset` and silently ignores `page_size`, so the device asset
  connector was always fetching the server default page size
- CVSS base scores of `0.0` are no longer dropped from the emitted vulnerabilities
- Holm vulnerability statuses are mapped to the documented legend (`0 - New`,
  `1 - Active`, `2 - Reopened`, `3 - Closed`). A reopened finding was reported as closed
  and a closed finding as newly created
- Malformed timestamps no longer abort a collection cycle: the affected record is skipped
- `max_severity` of a device agent is accepted both as the integer reported by the API and
  as a bucket name, instead of failing the whole page

## [1.1.0] - 2026-07-31

### Added

- Add holm logo to the module folder
- Update the connector description

## [1.0.0] - 2026-07-17

### Added

- Holm Security module with API token authentication
- Account validator
- Device asset connector that collects agent-managed devices from `GET /v2/devices` and maps them to the OCSF Device Inventory Info model
