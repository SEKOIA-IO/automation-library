# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-11-27 - 1.1.0

### Changed

- Collect all the incidents, acknowledged or not, so an incident acknowledged in Thinkst Canary before the connector collects it is no longer missed.
- Without a saved cursor, collect only the incidents created during the last day instead of the whole incident history.
- Forward an incident again only when its events change, so an update without new events, such as an acknowledgement, does not forward it twice.
- With the `acknowledge` option, acknowledge only the incidents that are not acknowledged yet, after their events are forwarded.

## 2026-11-27 - 1.0.2

### Fixed

- Add a timeout to the Thinkst Canary API calls, so a hung request fails and is logged instead of blocking the collection.
- Forward the events of a page even when acknowledging its incidents fails, and log how many incidents of the page were left unacknowledged.
- Save the cursor only after the events of a page are forwarded, so a failed push no longer skips the page.
- Accept incidents without the `events_count` or `events_list` fields instead of failing on the whole page.

## 2026-11-06 - 1.0.1

### Fixed

- Handle non-200 API responses without attempting to parse error bodies as JSON.
- Add retries on 500 errors.

## 2024-07-30 - 1.0.0

### Added

- Initial version of the connector
