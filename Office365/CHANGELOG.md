# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-08-21 - 2.17.10

### Added

- Added more verbose logging for auth errors

## 2024-07-03 - 2.17.9

### Fixed

- Change the way to close the Office365 client

## 2024-07-03 - 2.17.8

### Fixed

- Change the way to close the Office365 client

## 2024-07-03 - 2.17.7

### Fixed

- Fix the checkpoint system when the context doesn't exist

## 2024-07-01 - 2.17.6

### Fixed

- Fix run_until_complete method

## 2024-07-01 - 2.17.5

### Fixed

- Move async main stuff in a dedicated async method

## 2024-06-26 - 2.17.4

### Fixed

- Fix the dates used to pull the contents

## 2024-06-26 - 2.17.3

### Fixed

- Fix the way to get the content of HTTP errors

## 2024-06-25 - 2.17.2

### Fixed

- Update the internal cursor when saving a new date in the checkpoint

## 2024-06-24 - 2.17.1

### Fixed

- Fix the way to use the event loop

## 2024-06-17 - 2.17.0

### Changed

- Transform Office365 Management API connector as asynchronous connector

## 2024-06-12 - 2.16.1

### Added

- Declare Office365 Management API connector as trigger

## 2024-05-28 - 2.16.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-05-28- 2.15.1

### Fixed

- Add the intake key argument in the configuration of the `management_api` logs collector

## 2024-02-28- 2.15.0

### Added

- Added `management_api` logs collector

### Changed

- Splited the module into two submodules to separate `management_api` from `message_trace`

## 2024-02-13 - 2.14.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 2.13.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-08 - 2.12.1

### Fixed

- Fix metrics
