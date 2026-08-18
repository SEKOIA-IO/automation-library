# Changelog

## [0.3.0] - 2026-08-17

- Refactored the detections connector onto the SDK `iterate()` loop to restore forwarded/lag/duration metrics.
- Removed the redundant `batch_size` connector setting (the SDK chunks events by size).

## [0.2.0] - 2026-08-14

- Initial version of the Upwind automation module.
- Added the Upwind detections connector to collect detections and forward events to Sekoia.io intake.
- Authenticated to the Upwind API using OAuth2 client credentials.
- Added connector and trigger definitions.
- Added unit tests.
