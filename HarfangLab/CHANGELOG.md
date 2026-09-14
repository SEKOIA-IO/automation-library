# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-09-04 - 1.31.11

### Fixed

- Fix device asset connector: remove incorrect `vendor_name` value ("HarfangLab") from the device inventory mapping sample; `vendor_name` should reflect the device hardware vendor, not the product name

## 2026-08-27 - 1.31.10

### Fixed

- Fix typo in software asset connector feature flag key (`feature-flags` → `feature_flags`)

## 2026-08-27 - 1.31.9

### Changed

- Update software asset connector default frequency to 1 day (86400s) and minimum frequency to 3 hours (10800s)

## 2026-07-30 - 1.31.8

### Changed

- Pin Docker base image to `python:3.14-bookworm` for reproducible runtime builds.

## 2026-07-07 - 1.31.7

### Added

- Add `feature-flag` to the software asset connector

## 2026-07-03 - 1.31.6

### Fixed

- Fix `400 Bad Request` when triggering jobs (get process list, get pipe list, download file) by sending the `targets` payload with the `agents`/`groups` keys expected by the HarfangLab `job/batch` API instead of `agent_ids`/`group_ids`
- Fix dockerfile to use the correct `uv` version

## 2026-06-11 - 1.31.0

### Changed

- Migrated module from Poetry to uv

## 2026-06-10 - 1.30.2

### Fixed

- Fix asset connector validation error by accepting UUID values for `ioc_ruleset`, `sigma_ruleset`, and `yara_ruleset` policy fields (HarfangLab API returns UUIDs, not integers)

## 2026-04-30 - 1.30.1

### Added

- Add gateway MAC address to device network interface information

## 2026-04-29 - 1.30.0

### Added

- Add software asset connector to fetch application inventory from HarfangLab agents

## 2026-04-20 - 1.29.8

### Changed

- Update sekoia-automation-sdk to 1.22.5

## 2026-04-03 - 1.29.7

### Changed

- Update the yaml file for asset connector

## 2026-03-26 - 1.29.6

### Added

- Add option to update security events statuses along with a threat status

## 2026-02-23 - 1.29.5

### Changed

- Upgrade sekoia-automation-sdk to 1.22.3

### Fixed

- Fix OCSF device field by removing vendor_name property

## 2026-02-11 - 1.29.4

### Added

- Add asset connector mapping files for HarfangLab device assets

## 2025-02-09 - 1.29.3

### Changed

- Upgrade sekoia-automation-sdk to 1.22.2

## 2026-02-02 - 1.29.2

### Fixed

- Fix the way to save action results to a file

## 2026-02-02 - 1.29.1

### Fixed

- add the `[DEPRECATED]` tag to deprecated actions

## 2026-02-02 - 1.29.0

### Changed

- Change the flow for Job endpoints
- Add new Get Processes and Get Pipes actions to return actual processes and pipes
- Add option for Get Processes and Get Pipes to save processes/pipes data to file

## 2026-01-29 - 1.28.17

### Changed

- Update asset connector name

## 2026-01-23 - 1.28.16

### Changed

- Update internals field inside arguments of HarfangLab asset connectors

## 2025-10-28 - 1.28.15

### Added

- Add error logging to account validator

## 2025-10-27 - 1.28.14

### Changed

- fix dockerfile SSL issue

## 2025-10-06 - 1.28.13

### Changed

- Update conf asset connector

## 2025-09-30 - 1.28.12

### Changed

- Update sdk version
- Add batch size parameter to the asset connector

## 2025-09-19 - 1.28.11

### Changed

- Update asset connector name

## 2025-09-16 - 1.28.10

### Changed

- Update sekoia-automation-sdk
- Update Asset connector

## 2025-09-10 - 1.28.9

### Fixed

- Fix enum class values
- 
## 2025-09-08 - 1.28.8

### Added

- Add extra exception to the credential validator

## 2025-08-20 - 1.28.7

### Added

- Add some logs on harfanglab asset connector

## 2025-08-19 - 1.28.6

### Added

- Some Fix harfanglab asset connector

## 2025-08-19 - 1.28.5

### Added

- Fix harfanglab asset connector


## 2025-08-08 - 1.28.4

### Added

- Add timeout exception to the credential validator

## 2025-08-08 - 1.28.3

### Added

- Add some additional logs to the asset connector

## 2025-08-04 - 1.28.2

### Fixed

- Handling checkpoint

## 2025-06-04 - 1.28.1

### Fixed

- Upgrade the sekoia-automation-sdk

## 2025-06-04 - 1.28.0

### Added

- Device asset connector

## 2025-06-04 - 1.27.1

### Fixed

- Fix Job actions

## 2025-05-30 - 1.27.0

### Fixed

- Use new endpoint in actions instead of the deprecated one

## 2025-05-20 - 1.26.1

### Added

- Update return type for agent telemetry action

## 2025-05-20 - 1.26.0

### Added

- Added action to retrieve agent telemetry

## 2024-10-24 - 1.25.0

### Added

- Added action to add comment to a threat
- Added action to update threat status
- Added action to create IOCs

## 2024-10-17 - 1.24.0

### Added

- Added functionality to download a file on endpoint

## 2024-08-01 - 1.23.1

### Fixed

- IP are now taken from the `ip` field and put in the `ip` field of the getter.

## 2024-07-26 - 1.23.0

### Changed

- Added functionality to obtain hostnames from an IP address

## 2024-05-28 - 1.22.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.21.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
