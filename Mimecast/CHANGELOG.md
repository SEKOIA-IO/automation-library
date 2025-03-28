# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-03-20 - 1.1.11

### Fixed

- Fix condition to stop iteration over the list of events

## 2025-03-20 - 1.1.10

### Fixed

- Fix asyncio loop in thread

## 2025-03-19 - 1.1.9

### Fixed

- Set the Accept-Encoding header in requests

## 2025-03-19 - 1.1.8

### Fixed

- Fix the pagination

## 2025-03-12 - 1.1.7

### Fixed

- Fix memory issues: Use generators instead of lists when fetching events

## 2025-01-31 - 1.1.6

### Fixed

- Fixed the pagination

## 2025-01-24 - 1.1.5

### Changed

- Downgrade the log level for Authentication errors (temporary reverted)

## 2025-01-24 - 1.1.4

### Fixed

- Verify that start date is after 7 days ago

## 2025-01-15 - 1.1.3

### Fixed

- Increase the period between two fetch of mimecast events (The batches of events are available every 15 minutes)

## 2025-01-15 - 1.1.2

### Fixed

- Fix the initialization of the client

## 2025-01-15 - 1.1.1

### Fixed

- Initialize the API client in the run method

## 2024-11-26 - 1.1.0

### Added

- Added `av`, `delivery`, `internal email protect`, `impersonation protect`, `attachment protect`, `spam`, `url protect` logs support

### Changed

- Changed the way rate limiting works - now it is shared across the threads

## 2024-11-14 - 1.0.2

### Fixed

- Stop the connector if the authentication failed or if the permissions are denied

## 2024-07-30 - 1.0.1

### Changed

- Changed the way to log some information
- Changed the way to log message when no events are forwarded

### Fixed

- Fixed the way to compute the events lag

## 2024-06-14 - 1.0.0

### Added

- Initial version of the connector
