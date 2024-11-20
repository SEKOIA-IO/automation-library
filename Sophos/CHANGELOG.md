# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2024-11-20 - 1.17.2

### Fixed

- Add the ratelimit per day
- Increase the frequency to 5 minutes

## 2024-10-08 - 1.17.1

### Fixed

- Update the event lag when no events are retrieved from the API

## 2024-10-02 - 1.17.0

### Added

- Added Sophos EDR endpoint actions

## 2024-08-06 - 1.16.5

### Fixed

- Fixed the default ratelimiting

## 2024-08-02 - 1.16.4

### Fixed

- Jsonify events that goes to intakes

## 2024-07-10 - 1.16.3

### Fixed

- Change the expected status code from responses

## 2024-07-09 - 1.16.2

### Fixed

- Set max time window to fetch events as 30 days
- Add more logs

## 2024-06-06 - 1.16.1

### Fixed

- Fix the way to compute the lag on events, when no events were fetched from the API

## 2024-05-28 - 1.16.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.15.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-23 - 1.14.0

### Added

- Collecting events lag metric

## 2023-11-22 - 1.13.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-09-07 - 1.11.10

### Changed

- Fix the way to handle the HTTP exceptions

## 2023-07-26 - 1.11.9

### Changed

- fix metrics

## 2023-07-24 - 1.11.8

### Changed

- Fix the way to handle exception in the EDR connector
- Add more logs

## 2023-07-18 - 1.11.7

### Added

- add more logs
- Add an interval between two requests in the XDR connector
- Improve the way to handle failing requests

## 2023-07-13 - 1.11.0

### Changed

- Bump sdk version

## 2023-07-12 - 1.10.0

### Changed

- Bump sdk version

## 2023-06-30 - 1.9.1

### Added

- First time to add the Sophos EDR connector with query
