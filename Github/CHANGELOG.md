# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2024-06-11 - 1.10.2

### Changed

- Fix refresh token with pem file timeout
- Added paging support for github api response

## 2024-05-30 - 1.10.1

### Changed

- Fix the way to compute the lag on events, when no events were fetched from the API

## 2024-05-28 - 1.10.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-03-29 - 1.9.0

### Changed

- Update `sekoia-automation-sdk` to the latest version (1.12.2) and
  make use of SDK features to forward events to Sekoia.io.

## 2024-02-13 - 1.8.2

### Changed

- Update `sekoia-automation-sdk` to the latest version (1.12.0) to fix
  support for connectors (not yet released).

## 2024-02-13 - 1.8.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 1.7.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-09-08 - 1.5.0

### Changed

- Use fully async way of fetching data from the API
- Add option to use pem file instead of api key

## 2023-06-13 - 1.0.0

### Added

- Initial version of the connector
