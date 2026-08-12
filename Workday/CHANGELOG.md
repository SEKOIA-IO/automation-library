# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.3.0 - 2026-08-12

### Fixed

- The deduplication cache was rewritten to disk once per event, capping the connector at
  ~227,000 events/day. Deduplication is now in-memory and persisted once per cycle.
- Page fetches were retried in an unbounded loop, so a durably failing page never advanced the
  checkpoint nor surfaced an error. Retries are now bounded with exponential backoff; past that
  budget the cycle flushes what it collected and aborts without saving the checkpoint, so the
  window is retried in full rather than skipped.
- The heartbeat is now refreshed on every cycle, not only on a successful intake push, so a slow
  or quiet window no longer makes the connector look hung.
- Removed the per-event debug logs (hundreds of thousands of lines per cycle).

### Changed

- **Breaking (metrics only):** metrics moved to the `symphony_module_common` /
  `symphony_module_workday` namespaces with an `intake_key` label. 
- The deduplication cache is a bounded `LRUCache` (100,000 entries) instead of a 48h retention.
  Caches written by earlier versions are migrated in place.
- Collection windows are capped at 60 minutes, a backlog being walked one window per cycle.
  Larger windows exceeded the `instancesReturned` pool and were silently truncated.
- Module configuration fields now carry self-contained descriptions explaining exactly what to
  enter, where to find it in Workday, and in what format. The previous descriptions merely
  restated the field names ("Workday Host" for `workday_host`), which gave no indication that
  `workday_host` must exclude the scheme or that `tenant_name` is the URL path segment rather
  than the company display name.
- Added `pattern` constraints on `workday_host` and `tenant_name` to reject the most common
  input mistakes (a full URL pasted into the host field, slashes in the tenant name).

### Added

- `events_lags` gauge (how far behind real time the collection is) and
  `forward_events_duration` histogram.
- Regression tests covering deduplication, cache bounding and migration, window capping and
  backlog catch-up.

## 0.2.2 - 2026-07-16

### Changed

- Wire up the previously-unused Prometheus metrics: `workday_checkpoint_age_seconds` is now
  updated on every checkpoint load and save, and `workday_activity_logs_duplicated_total` /
  `workday_activity_logs_forwarded_total` are incremented during collection and intake forwarding.

### Fixed

- HTTP client retry tests no longer perform real 60s sleeps on 401/429 responses, cutting the
  client test suite from minutes to under a second.

### Added

- Expanded the test suite to 99% coverage: event-cache TTL cleanup and malformed-timestamp
  resilience, HTTP-client response-shape parsing and error paths (token refresh, 401/429/5xx,
  session guards), and the `_async_run` loop (nominal, auth failure, generic-error retry, and
  intake push failure).

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
