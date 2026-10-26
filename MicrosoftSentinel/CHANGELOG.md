# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-26 - 1.2.0

### Changed

- Migrated module from Poetry to uv (Python 3.14, ruff, mypy, mise)
- Upgraded sekoia-automation-sdk from 1.18.2 to 1.27.0
- Moved to pydantic v2 APIs (`model_fields`, `json_schema_extra`)
- Collect incident updates: incidents are tracked on their last modification date (`lastModifiedTimeUtc`) instead of their creation date, so a status, owner or new alert change forwards the updated incident again
- Request incidents in ascending last modification order and advance the checkpoint after each forwarded batch
- Use `chunk_size` as the maximum batch size (capped to 1000) instead of a minimum
- Forward an incident without entities, log a warning and count it in the `entities_fetch_errors` metric when its entities cannot be fetched because of an Azure error; other errors are no longer silenced

### Fixed

- Persist the incidents checkpoint so the connector resumes from the last collected incident after a restart
- Stop losing incidents that share the checkpoint timestamp: the boundary is now inclusive and already forwarded incident versions are deduplicated, including after a restart
- Do not re-collect already forwarded batches when a later batch of the same poll fails
- Convert dates to UTC before building the incidents filter
- Stop the connector promptly instead of waiting for the end of the polling interval

## 2026-05-27 - 1.1.0

### Added
- Fetch and forward incident entities from the list-entities endpoint.

## 2025-02-03 - 1.0.0

### Added

- Add the connector for the first time