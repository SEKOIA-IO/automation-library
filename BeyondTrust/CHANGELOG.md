# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [1.4.1] - 2026-09-07

### Fixed

- Handle BeyondTrust PRA platform `"No Support report information matching your chosen criteria is available."` XML responses as a no-data state instead of an error

## [1.4.0] - 2026-09-07

### Added

- Add the customer and representative details (public/private IP addresses, hostname, OS) to the events of the PRA platform connector, correlated to the performer of each event through its `gsnumber`
- Add the `gsnumber` of the performer and of the destination of each event
- Add the session-wide `file_transfer_count`, `file_move_count` and `file_delete_count` counters

### Changed

- Increase test coverage to 100%
- Normalize connector logging by using `self.log` instead of the custom structlog wrapper
- Migrate models and connector settings to Pydantic v2-compatible APIs
- Regenerate `poetry.lock` and update project dependencies
- Fix silent transitive imports by declaring explicitly imported Python packages in project dependencies

## [1.3.0] - 2026-04-30

### Added

- Add Team connector for BeyondTrust PRA

## [1.2.0] - 2026-04-28

### Added

- Add Vault Account Activity connector for BeyondTrust PRA

## [1.1.0] - 2026-03-26

### Added

- Add syslog connector for BeyondTrust PRA

## [1.0.2] - 2026-01-16

### Fixed

- Fix the condition to log API errors when listing sessions

## [1.0.1] - 2025-12-23

### Fixed

- Fix the logger when facing an API error when listing sessions

## [1.0.0] - 2025-06-10

### Fixed

- return when the connector faces an API error 

## [0.2.0] - 2025-02-12

### Changed

- Changed the way we gather sessions
