# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-11-25 - 1.0.2

### Fixed

- Add a timeout to the Thinkst Canary API calls, so a hung request fails and is logged instead of blocking the collection.
- Forward the events of a page even when acknowledging its incidents fails.
- Accept incidents without the `events_count` or `events_list` fields instead of failing on the whole page.

## 2026-11-06 - 1.0.1

### Fixed

- Handle non-200 API responses without attempting to parse error bodies as JSON.
- Add retries on 500 errors.

## 2024-07-30 - 1.0.0

### Added

- Initial version of the connector
