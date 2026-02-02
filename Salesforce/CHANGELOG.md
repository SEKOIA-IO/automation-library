# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-02-02 - 1.8.0

### Added

- Timestepper for orchestrating event collection with configurable time windows
- Log file ID cache to prevent re-processing duplicate files
- New configuration parameters `hours_ago` and `timedelta`

### Changed

- Event collection now uses bounded time windows instead of open-ended queries
- Improved lag monitoring with proper EVENTS_LAG metric calculation

## 2026-01-19 - 1.7.4

### Changed

- Throw critical error if unable to use refresh token
- Update sekoia-automation-sdk to 1.22.1

## 2025-12-22 - 1.7.3

### Fixed

- Fix the default value for Daily logs fetching

## 2025-09-18 - 1.7.2

### Fixed

- Add retry on auth error

## 2025-09-18 - 1.7.1

### Changed

- Change the way to compute the filters for the query

### Fixed

- Change the way to define the log type

## 2024-10-30 - 1.7.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-05-28 - 1.6.1

### Changed

- Add an option to fetch `Daily` logs

## 2024-05-28 - 1.6.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-04-24 - 1.5.4

### Changed

- Remove the beta flag from the connector

## 2024-02-13 - 1.5.3

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-02-02 - 1.5.2

### Fixed

- Fix on the configuration option for frequency

## 2024-02-02 - 1.5.1

### Added

- Configuration option for frequency

## 2024-01-24 - 1.4.12

### Added

- Configuration option for salesforce api rate limit.
- Correct log message when is unable to authorize with salesforce api.

## 2023-11-21 - 1.4.11

### Fixed

- Fix connector startup problems

## 2023-11-08 - 1.4.8

### Fixed

- Fix rate limiting and change configuration of the module

## 2023-11-08 - 1.4.6

### Fixed

- Fix metrics

## 2023-09-28 - 1.3.0

### Changed

- Change the way of how events pushed to the intake. Use async wrapper for that

## 2023-07-20 - 1.2.5

### Added

- add beta flag

## 2023-06-13 - 1.0.0

### Added

- initial version of the connector
