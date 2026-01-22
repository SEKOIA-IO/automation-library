# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-01-22 - 2.8.10

### Changed

- Added internals field to AWS asset connectors

## 2025-12-15 - 2.8.9

### Changed

- Update user type detection to use Okta roles instead of userType profile field
- Add group privileges to user asset connector groups

## 2025-12-08 - 2.8.8

### Changed

- Add checkpoint from SDK

## 2025-12-01 - 2.8.7

### Changed

- Improve test coverage for user asset connector with comprehensive tests for new fields

## 2025-11-25 - 2.8.6

### Added

- Add additional user fields to asset connector (display_name, domain, uid_alt, type_id, type)

## 2025-11-25 - 2.8.5

### Added

- Fix the issue when work with SecretString

## 2025-11-12 - 2.8.4

### Added

- Add events cache to deduplicate events

## 2025-10-06 - 2.8.3

### Changed

- Update conf asset connector

## 2025-09-30 - 2.8.2

### Fixed

- Fix account validator

## 2025-09-16 - 2.8.1

### Changed

- Add user and device asset connectors

## 2024-05-28 - 2.8.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 2.7.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 2.6.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-07-25 - 2.4.1

### Changed

- Save the most recent date seen when an exception is raised in the loop
