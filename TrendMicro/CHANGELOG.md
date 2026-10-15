# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.5] - 2026-10-15

### Changed

- Standardize Vision One connector logs with `self.log` and key=value context fields
- Reorganize tests to mirror `trendmicro_modules/` layout and enforce 100% coverage on that package

### Fixed

- Reset Vision One Workbench and OAT checkpoints when persisted offset is in the future
- Parameterize repetitive tests across triggers, helpers, models, and client auth while mocking batch timing to reduce test execution time
- Ensure Vision One checkpoint lock is always released when reset persistence fails

## [1.6.4] - 2026-03-24

### Changed

- Log server response in case of an error
- Ignore trailing slashes in configured URL
- Update dependencies

## [1.6.2] - 2025-08-08

### Changed

- Moved VisionOne to a separate automation module

## [1.6.1] - 2025-04-02

### Changed

- Persist latest pushed events to local cache

## [1.6.0] - 2024-12-09

### Added

- Added Trend Micro Vision One OAT connector

## [1.5.2] - 2024-12-03

### Changed

- Changed metrics labels for Workbench alerts

## [1.5.0] - 2024-11-25

### Added

- Added Trend Micro Vision One Workbench connector

## [1.4.0] - 2024-05-28

### Changed

- Upgrade sekoia-automation-sdk

## [1.3.2] - 2024-04-24

### Changed

- Remove the beta flag from the connector

## [1.3.1] - 2024-02-13

### Changed

- Change event_lags metrics from Histogram to Gauge

## [1.2.0] - 2023-11-23

### Added

- Collecting events lag metric

## [1.1.0] - 2023-11-22

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## [1.0.0] - 2023-10-17

### Added

- initial version of the connector
