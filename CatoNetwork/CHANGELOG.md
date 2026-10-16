# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-16 - 1.6.0

### Changed

- Migrate from Poetry to uv and mise, build on Python 3.14
- Upgrade sekoia-automation-sdk to 1.27.0 (minimum 1.26), gql 3.5.3 and pydantic v2
- Remove the unused `logger` package and use per-instance rate limiters
- Add optional `frequency` argument (default 60 s, minimum 1) to the connector and trigger: refetch immediately while events are returned, sleep when the feed is empty (previously polled non-stop)
- Report API errors to the platform with exponential backoff
- Log one platform message per forwarded batch and nothing for empty polls
- Raise `critical` only after 3 consecutive authentication failures matching known messages
- Raise a single `critical` when the intake keeps rejecting the same batch; the marker is never skipped
- Measure the `EVENTS_LAG` metric from the newest event

### Fixed

- Silence gql transport INFO logs that dumped full request and response payloads (customer data) to container logs
- Save the marker only after the intake acknowledged every event; previously it was saved before the push, so events could be lost
- Drop oversized events with a warning and count them in the metrics
- Set explicit 60 s timeouts and reuse the gql session

### Security

- Enable TLS certificate verification; it was effectively disabled by gql's default `ssl=False`

## 2026-07-01 - 1.5.2

### Fixed

- Accept Cato account IDs from 4 to 8 digits in module configuration

## 2024-07-08 - 1.5.1

### Fixed

- Update the length of the accountID to 5 digits

## 2024-05-28 - 1.5.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.4.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 1.3.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-08 - 1.2.2

### Fixed

- fix metrics

## 2023-10-27 - 1.2.1

### Changed

- remove BETA flag

## 2023-10-25 - 1.2.0

### Changed

- Fix run method

## 2023-10-25 - 1.1.0

### Changed

- update dependencies

## 2023-09-13 - 1.0.2

### Changed

- add BETA flag

## 2023-08-30 - 1.0.1

### Changed

- add ALPHA flag

## 2023-08-04 - 1.0.0

### Added

- initial version of the connector
