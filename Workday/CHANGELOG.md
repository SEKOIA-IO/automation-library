# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.2.1 - 2026-07-13

### Changed

- Wire up the previously-unused Prometheus metrics: `workday_checkpoint_age_seconds` is now
  updated on every checkpoint load and save, and `workday_activity_logs_duplicated_total` /
  `workday_activity_logs_forwarded_total` are incremented during collection and intake forwarding.

### Fixed

- HTTP client retry tests no longer perform real 60s sleeps on 401/429 responses, cutting the
  client test suite from minutes to under a second.
- Added tests for event-cache TTL cleanup and malformed-timestamp resilience.

## 0.2.0 - 2026-06-25

### Fixed

- Activity logging was capped at 10,000 events per time window because the `instancesReturned`
  API parameter was hardcoded to `1`. High-volume tenants silently lost every event beyond that
  cap. The parameter is now configurable (`instances_returned`, 1-25). It defaults to `1`
  (10,000 records per window, the most performant setting); high-volume tenants can raise it up to
  `25` (250,000 records per window).
- The collection checkpoint was saved at the start of each cycle. A truncated or interrupted
  collection therefore advanced past events that were never collected, losing them permanently.
  The checkpoint is now saved only after the whole window has been fetched and yielded.

### Added

- Configurable `instances_returned` connector setting.
- `workday_activity_logs_truncated_total` metric and a warning log raised when a window saturates
  the `instancesReturned` pool, so truncation is no longer silent.
