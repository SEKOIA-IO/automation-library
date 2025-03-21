# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-03-04 - 1.52.2

### Fixed

- Change the way to handle the 401 and 500 HTTP errors from the Vade Secure API

### Changed

- Change how to pause the trigger between two fetches

## 2024-11-15 - 1.52.1

### Fixed

- Fix the declaration of the connector

## 2024-11-04 - 1.52.0

### Added

- Added connector

## 2024-10-29 - 1.51.1

### Fixed

- Stop the trigger if it fail to authenticate

## 2024-05-28 - 1.51.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-03-29 - 1.50.0

### Changed

- Move API client and authorization to a separate module

## 2024-02-13 - 1.49.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-12-20 - 1.49.1

### Fixed

- Declare pagination_limit and rate_limit parameters in the trigger configuration

## 2023-12-18 - 1.49.0

### Fixed

- In case if there is no last message, empty string for ordering

## 2023-12-18 - 1.48.0

### Added

- Use latest message datetime during next execution

## 2023-11-23 - 1.47.0

### Added

- Collecting events lag metric

## 2023-11-22 - 1.46.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
