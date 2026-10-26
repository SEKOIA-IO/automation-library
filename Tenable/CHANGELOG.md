# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-26 - 1.0.20

### Fixed

- Device IP, OS, hostnames, network interfaces, cloud location and timestamps are filled again for assets read from the asset export
- Fix duplicate vulnerabilities on every run
- State changes (fixed, reopened) of an already sent vulnerability are always sent
- No more missed vulnerabilities: the checkpoint is saved only after a complete export and once every batch is accepted by Sekoia.io
- First run collects all open and reopened vulnerabilities; an old checkpoint is no longer moved forward
- Same device hostname fallback (hostname, name, FQDN) whatever the asset source
- A failed asset export no longer triggers a new export for every vulnerability
- A temporary error on the asset details endpoint no longer loses the finding: the checkpoint stops at that finding so it is fetched again on the next cycle
- An incomplete cycle (asset API error, refused batch) is retried after a delay instead of immediately
- Findings with an unknown state are sent as Create instead of being skipped

### Changed

- The existing checkpoint is reused: no full re-fetch on upgrade
- Asset cache refreshed every 6 hours
- `device.name` falls back to the hostname, then the FQDN
- REOPENED findings are sent with the OCSF activity name `Update`
- Descriptions and references are capped to the platform limits
- Tenable API payloads with explicit `null` values are accepted
- Mapping code split into `TenableVulnerabilityMapper`, `TenableDeviceMapper` and helper functions; mapping documentation updated

## 2026-08-28 - 1.0.19

### Changed

- Add dedicated Pydantic model files split by endpoint: `models/vuln_export_model.py` (Export Vulnerabilities), `models/assets_export_model.py` (Export Assets v2), `models/asset_details_model.py` (Get Asset Details)
- Migrate `vulnerability_asset.py` to use new split Pydantic models (`Vulnerability` from `vuln_export_model`, `AssetDetails` and `NetworkInterface` from `asset_details_model`) instead of the legacy monolithic `model.py`
- Add missing fields to all models

## 2026-07-29 - 1.0.18

### Fixed

- Fix `AssetInfo` model to accept float values for `aes_score_v3` and `acr_score_v3` fields returned by the Tenable API
- Fix `TagsObject` model to accept `None` for the `added_by` field

## 2026-05-20 - 1.0.17

### Changed

- Update asset connector name to "Tenable Vulnerability Management"
- Skip vulnerabilities with no CVE IDs to avoid creating assets with incomplete information
- Increment the polling interval of the connector

## 2026-04-20 - 1.0.16

### Changed

- Introduce Pydantic models (`AssetInfo`, `Vulnerability`, `Plugin`, `VulnAsset`, and related sub-models) in `model.py` to strongly type Tenable API responses
- Upgrade `sekoia-automation-sdk` to version 1.22.5 to leverage the latest features and improvements

## 2026-04-10 - 1.0.15

### Fixed

- Fix field mappings in `vulnerability_mapping.yml` to align with the actual OCSF models.

## 2026-03-11 - 1.0.14

### Changed

- Truncate plugin description to the first sentence and append "See more details on Tenable" to avoid database field overflow

## 2026-03-04 - 1.0.13

### Changed

- Use exported assets instead of fetching asset details for each vulnerability

## 2026-02-23 - 1.0.12

### Changed

- Upgrade sekoia-automation-sdk to 1.22.3

## 2026-02-06 - 1.0.11

### Changed

- Add for the first time the vulnerability mapping yml file

## 2025-02-09 - 1.0.10

### Changed

- Upgrade sekoia-automation-sdk to 1.22.2

## 2026-01-29 - 1.0.9

### Changed

- Update asset connector name

## 2026-01-23 - 1.0.8

### Changed

- Update internals field inside arguments of Tenable asset connectors

## 2026-01-22 - 1.0.7

### Changed

- Added internals field to Tenable asset connectors

## 2025-01-12 - 1.0.6

### Fixed

- Fix the way we handle CVE IDs

## 2025-01-08 - 1.0.5

### Changed

- Update hostname field

## 2025-12-18 - 1.0.4

### Changed

- Add device to asset mapping
- Add some extra fields
- Update sdk version to 1.22.0
- Add exceptions to the connector

## 2025-10-06 - 1.0.3

### Changed

- Update conf asset connector

## 2025-09-30 - 1.0.2

### Changed

- Update the sdk version to 1.21.0
- Add batch size configuration to the connector settings

## 2025-09-19 - 1.0.1

### Changed

- Update asset connector name
- Add module run method


## 2025-08-15 - 1.0.0

### Added

- Add for the first time the vulnerability asset connector
