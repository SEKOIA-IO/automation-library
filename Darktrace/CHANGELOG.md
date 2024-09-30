# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2024-07-05 - 1.7.1

### Fixed

- Set the current lag to 0 when no events are fetched (because the connector is up-to-date)

## 2024-05-28 - 1.7.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-04-24 - 1.6.2

### Changed

- Remove beta flag from the connector

## 2024-02-13 - 1.6.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 1.5.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-22 - 1.4.4

### Added

- Added historicmodelonly parameter

## 2023-11-09 - 1.4.3

### Changed

- Improved last_ts update

## 2023-10-23 - 1.4.2

### Changed

- Moved to urllib3 2.x 

## 2023-06-30 - 1.4.1

### Changed

- Add additional user-agent to work with api

## 2023-10-23 - 1.4.0

### Added

- Add threading
- Add AIanalyst endpoint

## 2023-06-30 - 1.3.2

### Added

- Add a parameter to verify or not the server certificate for TLS connections

## 2023-06-30 - 1.3.1

### Added

- Add beta flag

## 2023-07-13 - 1.3.0

### Changed

- Update `sekoia-automation-sdk` dependency

## 2023-07-13 - 1.2.0

### Changed

- Update `sekoia-automation-sdk` dependency

## 2023-07-03 - 1.1.0

### Added

- Add secrets

## 2023-06-30 - 1.0.1

### Fixed

- Fix the manifest of the module

## 2023-06-30 - 1.0.0

### Added

- initial version of the connector
