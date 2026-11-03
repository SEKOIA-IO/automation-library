# Changelog

## [0.4.1] - 2026-08-18

### Changed

- Store the boundary checkpoint in a dedicated `boundary_context.json` file to avoid overwriting the SDK checkpoint that owns `context.json`.

### Fixed

- Strip the timezone from the checkpoint datetime yielded to the SDK so lag metrics are computed correctly.

## [0.4.0] - 2026-08-18

### Fixed

- Fix Upwind category in manifest.json to be "Network" instead of "Cloud".

## [0.3.0] - 2026-08-17

### Changed

- Refactored the detections connector onto the SDK `iterate()` loop to restore forwarded/lag/duration metrics.

### Removed

- Removed the redundant `batch_size` connector setting (the SDK chunks events by size).

## [0.2.0] - 2026-08-14

### Added

- Initial version of the Upwind automation module.
- Added the Upwind detections connector to collect detections and forward events to Sekoia.io intake.
- Authenticated to the Upwind API using OAuth2 client credentials.
- Added connector and trigger definitions.
- Added unit tests.
