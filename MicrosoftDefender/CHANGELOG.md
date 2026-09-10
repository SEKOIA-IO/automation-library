# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2026-08-18 - 1.3.7

### Changed

- Update the minimum frequency value from 1 second to 3 hours (10800 seconds) for the device asset connector to avoid excessive API calls and potential throttling.

## 2026-08-18 - 1.3.6

### Fixed

- Fix `'NoneType' object has no attribute 'lower'` when a network interface entry has an explicit `None` type in the device asset connector.
- Fix `HTTP transport has already been closed` error when enriching multiple devices via the Graph API by properly managing the `GraphServiceClient` lifecycle with an async context manager.

## 2026-07-30 - 1.3.5

### Changed

- Device asset connector: change default `frequency` from 60 s to 86400 s (24 h).

## 2026-07-30 - 1.3.4

### Fixed

- Store the raw `lastSeen` string from the API directly as checkpoint instead of converting to `datetime` and back.

## 2026-07-30 - 1.3.3

### Fixed

- Device asset connector: use a strict `lastSeen gt <checkpoint>` filter (instead of `ge`) and store the checkpoint with microsecond precision, so the most recently seen device is no longer re-collected on every cycle. This kept the connector running back-to-back (no idle sleep) and re-pushing the same devices, driving compliance ingestion lag.

## 2026-07-24 - 1.3.2

### Fixed

- Limit incidents connector `$top` query size to 50 (while keeping alerts at 1000) to match Microsoft Graph API limits and prevent incidents request failures.

## 2026-07-20 - 1.3.1

### Fixed

- Prevent Graph API connector cursor advancement when forwarding fails, avoiding potential event loss on retries.
- Preserve original traceback by re-raising connector exceptions with `raise`.
- Add incidents trigger `results` schema and regression coverage for failed push cursor behavior.

## 2026-06-10 - 1.3.0

### Added

- New connector `connector_defender_incidents` fetching incidents from Microsoft Defender XDR through the Microsoft Graph Security API (`/security/incidents`). Reuses the same Graph application scope as the alerts connector; requires the `SecurityIncident.Read.All` permission.

## 2026-06-02 - 1.2.2

### Fixed

- Fix device asset connector checkpoint filter: use `lastSeen` instead of `firstSeen` (not filterable by Defender API), encode datetime as UTC with `Z` suffix to avoid `+00:00` breaking URL query strings

## 2026-05-26 - 1.2.1

### Fixed

- Fix `rbacGroupId` type in DefenderMachine model to accept integer values from the API

## 2026-05-06 - 1.2.0

### Added

- Add Microsoft Defender device asset connector

## 2026-03-16 - 1.1.0

### Added

- Add connector for Microsoft Defender XDR Alerts (Graph API)

## 2024-11-15 - 1.0.0

### Added

- Initial release of the module
