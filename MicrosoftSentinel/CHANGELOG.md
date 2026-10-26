# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-26 - 1.1.1

### Changed

- Migrated module from Poetry to uv (Python 3.14, ruff, mypy, mise)
- Upgraded sekoia-automation-sdk from 1.18.2 to 1.27.0
- Moved to pydantic v2 APIs (`model_fields`, `json_schema_extra`)
- Request incidents in ascending creation order and advance the checkpoint after each forwarded batch
- Upgrade note: 1.1.0 never persisted its checkpoint, so the first start after upgrading from 1.1.0 forwards once again the incidents created in the last 24 hours
- Use `chunk_size` as the maximum batch size (capped to 1000) instead of a minimum
- The `events_lags` metric is measured from the checkpoint on every poll, also when no new incident is forwarded, instead of being reset to 0
- Forward an incident without entities, log a warning and count it in the `entities_fetch_errors` metric when its entities cannot be fetched (Azure error) or are malformed (deserialization or conversion error); other errors are no longer silenced

### Fixed

- Persist the incidents checkpoint so the connector resumes from the last collected incident after a restart
- Stop losing incidents that share the checkpoint timestamp: the boundary is now inclusive and already forwarded incidents are deduplicated, including after a restart
- Collect incidents written late: incidents are queried from 5 minutes before the checkpoint and the incidents already forwarded in that window are deduplicated, including after a restart
- Do not re-collect already forwarded batches when a later batch of the same poll fails
- Do not advance the checkpoint nor mark incidents as forwarded when the intake did not accept the whole batch (the SDK logs and swallows intake errors); the batch is collected again on the next poll, with a backoff
- Log a warning for the incidents bigger than 250 kB, which the SDK cannot forward, instead of dropping them silently
- Convert dates to UTC before building the incidents filter
- Stop the connector promptly instead of waiting for the end of the polling interval
- Keep polling after an Azure API error while listing incidents, with an exponential backoff (capped to 5 minutes) on consecutive failures
- Retry the poll, instead of stopping the connector, when the Azure SDK cannot deserialize an incident
- Serialize the Azure model fields of an incident (e.g. `system_data`) as objects instead of failing the poll
- Skip null entries in an incident's entities instead of stopping the connector

## 2026-05-27 - 1.1.0

### Added
- Fetch and forward incident entities from the list-entities endpoint.

## 2025-02-03 - 1.0.0

### Added

- Add the connector for the first time