# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-10-08 - 1.15.3

### Changed

- Replace requests direct calls by an API client with retries and rate limiting

## 2025-09-18 - 1.15.2

### Fixed

- Stop the increase of the timestepper when facing API errors

### Changed

- Log a critical error when the connector is misconfigured (Authentication errors)

## 2025-09-09 - 1.15.1

### Changed

- Change the description and the default value for the `api_domain_name` parameter

## 2024-09-10 - 1.15.0

### Added

- Added saving last seen timestamp

## 2024-05-28 - 1.14.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.13.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 1.12.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-09 - 1.11.2

### Fixed

- Fix connector

## 2023-11-08 - 1.11.1

### Fixed

- Fix metrics
