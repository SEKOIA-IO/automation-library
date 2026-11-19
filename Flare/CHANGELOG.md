# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-11-19 - 0.7.0

### Changed

- Mark the module as an Intelligence module, so the platform lists it as an Intelligence connector and opens it to Intelligence-only communities

## 2026-11-19 - 0.6.10

### Fixed

- Fix the wording of the log shown when the connector starts: "Starting to fetch Flare events"

## 2026-11-18 - 0.6.9

### Changed

- Log the events cut to fit the intake size limit only in the connector's output, not in the intake's logs: a first sync can cut hundreds of them. The events still above the limit are still logged in the intake's logs

## 2026-11-18 - 0.6.8

### Fixed

- Give every call to the Flare API a timeout (10 s to connect, 60 s to read), in the connector and the account validation, and retry the calls that time out: a call Flare never answered blocked the connector until the connection broke

## 2026-11-17 - 0.6.7

### Fixed

- Cut the end of the biggest fields of an event that exceeds the intake size limit, instead of letting the whole event be discarded: attachment text, lists of IP addresses, domains or URLs, `content`, then the files, credentials and emails of stealer logs and leaks. The cut fields are listed in `data.truncated_fields`
- Count the events cut (`truncated_events`) and the events still above the limit (`discarded_events`), and log each of them with its type, uid and cut fields

## 2026-11-17 - 0.6.6

### Fixed

- Retry the intermittent 500 errors of the Flare API, which the SDK does not retry: each one failed the batch and delayed the collection by `frequency` (60 s by default)

## 2026-11-17 - 0.6.5

### Added

- Add the date Flare matched the item to the tenant to the events, as `metadata.matched_at`: the item itself can be years old

## 2026-11-17 - 0.6.4

### Changed

- Fetch the details of a page's events in parallel (new `concurrency` setting, 4 by default) and read the next page meanwhile; `throttle_seconds` now spaces the calls instead of adding a wait after each one

## 2026-11-02 - 0.6.3

### Fixed

- Drop the context messages (`olders`, `newers`) embedded in chat messages, which made them exceed the intake size limit and get discarded
- Forward the fully read pages before failing on an API error (e.g. rate limiting)
- Wait for one period before retrying after a failure

## 2026-11-02 - 0.6.2

### Fixed

- Skip events whose details are no longer available on Flare (404) instead of failing the whole batch

## 2026-10-29 - 0.6.1

### Fixed

- Filter the initial collection window on `matched_at` instead of `estimated_created_at`

## 2026-07-20 - 0.6.0

### Changed

- Update Flare description in `manifest.json` to provide a more detailed overview of the integration's capabilities and purpose.

## 2026-07-30 - 0.5.1

### Changed

- Pin Docker base image to `python:3.14-bookworm` for reproducible runtime builds.

## 2026-07-20 - 0.5.0

### Changed

- Speed up event collection by streaming events to the intake in batches of 100 (instead of a single push at the end) and advancing the checkpoint on page boundaries
- Remove the SDK's default 1s-per-page delay by pacing both page and event requests with the configured `throttle_seconds`, and lower its minimum to `0`
- Rely on the Flare SDK's built-in session/retry policy and drop the redundant custom `requests.Session`
- Simplify the connector by removing the stale-cursor retry and verbose diagnostics helpers

### Fixed

- Align event feed paging with the Flare SDK documentation by using `/firework/v4/events/tenant/_search`
- Comply with Flare v4 global search validation by always capping `page_size` to 10

## 2026-07-20 - 0.4.0

### Fixed

- Reuse the connector's configured limiter as the SDK's per-event limiter (`_events_limiter`) to stop double-throttling events, and clarify the `throttle_seconds` description
- Regenerate `poetry.lock` to match `pyproject.toml`
- Fix `isort` ordering in `tests/conftest.py`
- Modernize `pyproject.toml` (`tool.poetry.group.dev.dependencies`, `tool.mypy` strict config)
- Redirect hardcoded SDK writes to `/tmp/tls` into writable `/dev/shm` in the container image to avoid read-only filesystem failures

### Added

- Prometheus metrics (`OUTCOMING_EVENTS`, `EVENTS_LAG`, `FORWARD_EVENTS_DURATION`) for the Flare events trigger
- Mark `api_key` as a secret field on `FlareIOModuleConfiguration`

## 2026-07-10 - 0.3.0

### Changed

- Migrated module from Poetry to uv

## 2026-06-08 - 0.2.0

### Added

- Add Flare events pull trigger using the official `flareio` SDK
- Add account validator based on `/tokens/test`

## 2026-06-08 - 0.1.0

### Added

- Initial module scaffolding for Flare.io
