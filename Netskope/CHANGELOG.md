# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.10.2] - 2024-04-23

### Fixed

- Add interceptor on connection timeout for Netskope Events connector.


## [1.10.1] - 2024-02-13

### Changed

- Change event_lags metrics from Histogram to Gauge

## [1.9.3] - 2024-01-02

### Changed

- Set `base_url` property as nullable and update the Netskope Events connector to check this property

## [1.9.0] - 2023-12-22

### Added

- New connector for the Netskope Transaction events

## [1.8] - 2023-11-22

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## [1.7.1] - 2023-11-15

### Changed

- Update `netskopesdk` dependency to the latest upstream version.

## [1.4.0] - 2023-06-27

### Changed

- Update `netskopesdk` dependency to the latest upstream version.
- Update PIP requirements.
