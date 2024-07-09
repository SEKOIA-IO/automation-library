# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-07-09 - 1.19.1

### Changed

- Filter on specific event_simpleName values

## 2024-05-28 - 1.19.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-03-18 - 1.18.1

### Fixed

- Change the way to paginate CrowdStrike responses
- Add intermediate steps when deleting indicators

## 2024-03-17 - 1.18.0

### Added

- Add method to remove expired indicators
- Add method to remove old indicators

## 2024-02-21 - 1.17.4

### Added

- Add some logs for http response

## 2024-02-13 - 1.17.3

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-02-12 - 1.17.2

### Fixed

- Add timer thread to EventStreamReader


## 2024-01-19 - 1.16.1

### Fixed

- Change the way to handle graceful shutdown
- Change the way to consume events in the queue

## 2024-01-05 - 1.15.3

### Fixed

- Catch errors in the event forwarder

## 2023-12-15 - 1.15.2

### Fixed

- Add a ratelimiter for the authentication requests

## 2023-12-05 - 1.15.1

### Fixed

- Fixed default refresh time
- Fixed bug with an exception propagation

## 2023-11-22 - 1.15.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-08 - 1.14.3

### Fixed

- fix metrics

## 2023-10-31 - 1.14.2

### Changed

- Revert changes of user-agent to interact with intake
- Add additional user-agent to work with api

## 2023-10-31 - 1.14.1

### Changed

- Update connector to use new format of user-agent when push to intake

## 2023-09-07 - 1.12.1

### Changed

- Catch any exception at the root level and log them
