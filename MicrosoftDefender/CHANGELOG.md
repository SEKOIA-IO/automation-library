# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2026-04-21 - 1.3.0

### Added

- New connector `connector_defender_incidents` fetching incidents from Microsoft Defender XDR through the Microsoft Graph Security API (`/security/incidents`). Reuses the same Graph application scope as the alerts connector; requires the `SecurityIncident.Read.All` permission.
- The incidents connector accepts an optional `expand_alerts` parameter to include each incident's nested alerts via `$expand=alerts`.

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
