# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2024-10-30 - 1.11.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-10-14 - 1.10.3

### Fixed

- Improve logs

## 2024-10-14 - 1.10.2

### Added

- Add more logs to observer the EDR connector

## 2024-09-19 - 1.10.1

### Changed

- Change auth scopes

## 2024-09-13 - 1.10.0

### Changed

- Change event loop initialization and token refresh workflow

## 2024-09-13 - 1.9.4

### Added

- More logs over token refresh interval

## 2024-08-09 - 1.9.3

### Fixed

- Update retry interval to minimum 5 seconds

## 2024-08-08 - 1.9.2

### Fixed

- Ensure we have a fresh access token when the previous one expired

## 2024-08-07 - 1.9.1

### Fixed

- fix labels on metrics

## 2024-08-06 - 1.9.0

### Fixed

- add support of changed structure for Trellix alerts response

## 2024-07-31 - 1.8.6

### Fixed

- add pause when an exception is raised

## 2024-07-31 - 1.8.5

### Added

- add frequency parameter with connectors pause
- add a daily rate limiting parameter

### Changed

- move rate-limiting and page size parameters in connectors configuration

## 2024-07-29 - 1.8.4

### Changed

- add a safety margin for the refresh token

### Fixed

- add retries on failed http requests
- handle 429 HTTP responses

## 2024-07-23 - 1.8.3

### Fixed

- Raise exception on authentication when facing 4xx status code
- Fix the way to compute the authentication url

## 2024-07-22 - 1.8.2

### Changed

- Update the loggers

## 2024-07-15 - 1.8.1

### Fixed

- Improve the way to handle errors on authentication

## 2024-05-28 - 1.8.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.7.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-02-12 - 1.7.1

### Added

- Add logo

## 2023-11-23 - 1.6.1

### Added

- Add connector for Trellix EDR

## 2023-11-22 - 1.6.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-08 - 1.5.1

### Fixed

- Fix metrics

## 2023-09-28 - 1.3.0

### Changed

- Change the way of how events pushed to the intake. Use async wrapper for that

## 2023-08-18 - 1.2.1

### Changed

- Fix the configuration for the connector

## 2023-07-05 - 1.0.0

### Added

- Initial version of the module
