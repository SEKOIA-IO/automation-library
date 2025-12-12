# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-12-12 - 1.4.0

### Changed

- Update Python version to 3.14

## 2025-11-03 - 1.3.11

### Changed

- Improve descriptions of the scan actions

## 2025-10-31 - 1.3.10

### Fixed

- Fix XQL query status comparison to handle case-insensitive status values

## 2025-09-17 - 1.3.9

### Added

- Add actions to List endpoint, Scan endpoint and Abort endpoint scanning

## 2025-08-07 - 1.3.8

### Fixed

- Add caching to avoid duplicate alerts

## 2025-08-06 - 1.3.7

### Fixed

- Fix connector issue with alert creation time

## 2025-06-13 - 1.3.6

### Fixed

- Fix quarantine action problem

## 2025-06-12 - 1.3.5

### Fixed

- Fix size of hash list problem

## 2025-06-12 - 1.3.4

### Fixed

- Fix some more endpoint problems

## 2025-06-11 - 1.3.3

### Fixed

- Fix duplicate hashes in payload
- Delete useless line

## 2025-06-11 - 1.3.2

### Fixed

- Fix small typo on query action endpoint

## 2025-06-06 - 1.3.1

### Fixed

- Fix cast class error when running actions

## 2025-05-20 - 1.3.0

### Changed

- Add new actions to the integration

## 2025-03-28 - 1.2.0

### Changed

- If there is only one event within alert, we won't separate them anymore

## 2024-11-22 - 1.1.4

### Fixed

- Fix the way to handle the responses
- Handle HTTP errors

### Changed

- Stop the connector when credentials or permissions are invalids

## 2024-08-02 - 1.1.2

### Changed

- Improve alert_url proprety

## 2024-07-08 - 1.1.1

### Fixed

- Change the way to compute event lags
- Fix the precision of the timestamps used in the connector

## 2024-05-28 - 1.1.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-15 - 1.0.3

### Changed

- Change the connector name

## 2024-02-13 - 1.0.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-02-01 - 1.0.1

### Changed

- Improve the timestamp setter ( Add one seconde to the last timestamp )

## 2024-01-23 - 1.0.0

### Added

- Add for the first time Cortex Query alerts
