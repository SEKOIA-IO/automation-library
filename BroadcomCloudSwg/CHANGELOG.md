# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2024-10-30 - 1.2.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-05-28 - 1.1.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-03-08 - 1.0.12

### Fixed

- update offsets each time after processing file

## 2024-03-05 - 1.0.11

### Added

- save offsets for last 24 hour.

## 2024-03-05 - 1.0.10

### Fixed

- remove some logs
- update limits

## 2024-02-20 - 1.0.9

### Fixed

- remove processed file
- add retry 

## 2024-02-20 - 1.0.8

### Fixed

- exclude lines that already processed
- perform processing during decompressing
- unblock main execution io when we push to intake

## 2024-02-20 - 1.0.7

### Changed

- increase the lower limit of the authorized date, in the past, of the last event to 24h

## 2024-02-20 - 1.0.6

### Fixed

- Use env variable as configuration for push events to intake parallelism

## 2024-02-13 - 1.0.5

### Fixed

- Use different method to push data to intake

## 2024-02-13 - 1.0.4

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-02-09 - 1.0.3

### Added

- Additional logs to session initialization

## 2024-02-08 - 1.0.2

### Fixed

- Update rate limiter settings
- Handle empty zip file 

## 2024-02-07 - 1.0.1

### Fixed

- Remove group by before push data to intake

## 2024-01-29 - 1.0.0

### Added

- The initial version of the module
