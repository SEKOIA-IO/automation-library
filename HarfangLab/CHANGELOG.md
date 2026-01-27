# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-01-27 - 1.29.0

### Changed

- Change the flow for Job endpoints
- Get Processes and Get Pipes actions return actual processes and pipes
- Add option to save processes/pipes data to file

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
