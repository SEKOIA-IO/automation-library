# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-06-10 - 1.14.0

### Added

- New `security_check_only` option on the Netskope Events connector to collect only security-check alerts (malware, malsite, DLP).

### Changed

- Removed the standalone `netskope_security_check_connector` (UUID `9e292f7e-146f-4839-926e-dac6ba8a6275`). Enable the `security_check_only` option on the Netskope Events connector instead.

## 2026-06-09 - 1.13.1

### Fixed

- Added trigger configuration for security check.

## 2026-05-11 - 1.13.0

### Added

- New `netskope_security_check_connector` that collects Netskope sandbox / security-check

## 2026-04-23 - 2.0.0

### Added

- Add blocklist management actions:
    - append to blocklist
    - delete blocklist
    - replace blocklist
- Add required `api_token` parameter to manifest, for Netskope api authentication

## 2026-04-23 - 1.12.0

### Fixed

- Stop consumer when Netskope SDK throws Incorrect Token error

### Changed

- Upgrade sekoia-automation-sdk

## 2024-12-13 - 1.11.1

### Fixed

- Fix generating index name

## 2024-10-30 - 1.11.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-08-02 - 1.10.5

### Added

- add additional logger

### Fixed

- Handle when failing to decode the incoming message

## 2024-07-10 - 1.10.4

### Fixed

- Change the way to compute the event lag

## 2024-07-02 - 1.10.3

### Added

- Add the user-agent to the Netskope Events connector

## 2024-04-23 - 1.10.2

### Fixed

- Add interceptor on connection timeout for Netskope Events connector.


## 2024-02-13 - 1.10.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-01-02 - 1.9.3

### Changed

- Set `base_url` property as nullable and update the Netskope Events connector to check this property

## 2023-12-22 - 1.9.0

### Added

- New connector for the Netskope Transaction events

## 2023-11-22 - 1.8.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-15 - 1.7.1

### Changed

- Update `netskopesdk` dependency to the latest upstream version.

## 2023-06-27 - 1.4.0

### Changed

- Update `netskopesdk` dependency to the latest upstream version.
- Update PIP requirements.
