# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-02-28 - 1.5.2

### Changed

- Change the way to handle 401 and 500 HTTP errors when the connector is running

## 2024-10-29 - 1.5.1

### Fixed

- Stop the trigger if it fail to authenticate 

## 2024-05-28 - 1.5.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-04-24 - 1.4.2

### Changed

- Remove the beta flag from the connector

## 2024-02-13 - 1.4.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-01-23 - 1.3.2

### Added

- `administrator` and `quarantine` account types support

## 2023-11-23 - 1.3.0

### Added

- Collecting events lag metric

## 2023-11-22 - 1.2.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-10-12 - 1.0.5

### Fixed

- Fixed bug with a first start

## 2023-08-30 - 1.0.4

### Changed

- Switch to beta flag

## 2023-08-30 - 1.0.3

### Changed

- add ALPHA flag

## 2023-07-26 - 1.0.1

### Added

- default value for the Vade Cloud hostname field

## 2023-07-26 - 1.0.0

### Added

- initial version of the connector
