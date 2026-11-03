# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-10-02

### Changed

- Upgrade `sekoia-automation-sdk` to `1.26.0`
- Raise the minimum supported Python version to `3.11` in both `pyproject.toml` and `Dockerfile` because `sekoia-automation-sdk` `1.26.0` requires Python `>=3.11`
- Upgrade project dependencies to their latest compatible versions

### Fixed

- Prevent worker crashes on non-JSON/empty HTTP error bodies, which could amplify ingestion delays under repeated retries
- Stabilize per-log-type checkpoint updates by preserving the previous cursor when `@nextPage` is empty or missing
- Add low-noise batch diagnostics with a compact structured summary (fetched/forwarded counts, event time window, lag, retries, and timeouts)
- Add high-lag warnings with built-in rate-limiting to avoid log spam while surfacing prolonged catch-up phases
- Track request retry/timeout counts per batch to improve correlation between network instability and delayed alerting
- Increase test coverage to 100%
- Generalize the use of `pytest.mark.parametrize` across test suites where applicable

## [1.1.15] - 2026-01-07

### Changed

- Remove the beta flag from the connector

## [1.1.14] - 2025-05-13

### Fixed

- Filter already collected events

## [1.1.13] - 2025-05-13

### Fixed

- Handle temporary errors when fetching events

## [1.1.12] - 2025-04-10

### Fixed

- Use cursor token in the pagination

## [1.1.11] - 2025-03-20

### Fixed

- Fix condition to stop iteration over the list of events

## [1.1.10] - 2025-03-20

### Fixed

- Fix asyncio loop in thread

## [1.1.9] - 2025-03-19

### Fixed

- Set the Accept-Encoding header in requests

## [1.1.8] - 2025-03-19

### Fixed

- Fix the pagination

## [1.1.7] - 2025-03-12

### Fixed

- Fix memory issues: Use generators instead of lists when fetching events

## [1.1.6] - 2025-01-31

### Fixed

- Fix the pagination

## [1.1.5] - 2025-01-24

### Changed

- Downgrade the log level for Authentication errors (temporary reverted)

## [1.1.4] - 2025-01-24

### Fixed

- Verify that start date is after 7 days ago

## [1.1.3] - 2025-01-15

### Fixed

- Increase the period between two fetch of mimecast events (The batches of events are available every 15 minutes)

## [1.1.2] - 2025-01-15

### Fixed

- Fix the initialization of the client

## [1.1.1] - 2025-01-15

### Fixed

- Initialize the API client in the run method

## [1.1.0] - 2024-11-26

### Added

- Add `av`, `delivery`, `internal email protect`, `impersonation protect`, `attachment protect`, `spam`, `url protect` logs support

### Changed

- Change the way rate limiting works - now it is shared across the threads

## [1.0.2] - 2024-11-14

### Fixed

- Stop the connector if the authentication failed or if the permissions are denied

## [1.0.1] - 2024-07-30

### Changed

- Change the way to log some information
- Change the way to log message when no events are forwarded

### Fixed

- Fix the way to compute the events lag

## [1.0.0] - 2024-06-14

### Added

- Initial version of the connector
