# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-05-28 - 2.14.5

### Changed

- Change the way to compute the lag

## 2024-05-23 - 2.14.4

### Fixed

- Add result model to update incident action

## 2024-05-23 - 2.14.3

### Fixed

- Add result model to actions

## 2024-05-17 - 2.14.2

### Changed

- Increase the frequency between the calls when fetching events
- Add the transaction id when logging an HTTP error

### Fixed

- Add a retry strategy when facing errors during events fetching

## 2024-05-07

- Add response field classes
- Update some methods
- Add exponential backoff retry strategy on authentication requests

## 2024-04-22 

- Add missing read rights when creating WithSecure API client

## 2024-04-03

- Add read rights when creating WithSecure API client

## 2024-03-14

- Fix issue with some actions

## 2024-02-13 - 2.13.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 2.11

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-22 - 2.10.1

### Fixed

- Fix the identifier of the new action

## 2023-11-22 - 2.10.0

### Added

- Add new action to scan devices for malwares

## 2023-10-24 - 2.9.0

### Changed

- Update dependencies

## 2023-10-02 - 2.8.0

### Changed

- Remove the beta flag
