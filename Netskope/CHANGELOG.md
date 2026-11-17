# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.17.0] - 2026-11-17

### Added

- Add playbook remediation actions:
  - `deploy_url_policy`
  - `quarantine_file`
  - `restrict_file_shares`
  - `restrict_user_to_group`
  - `revoke_user_sessions`
  - `update_dlp_incident_status`

## [1.16.1] - 2026-10-13

### Fixed

- Derive a dedicated index from the consumer group for each event type, to avoid concurrent consumers sharing the same Netskope iterator

### Added

- Add an optional `start_timestamp` parameter to start the collection of a new consumer group from a given date; changing it repositions the existing indexes at the new date
- Log an explicit warning when Netskope reports a concurrency conflict (409) on an index

## [1.16.0] - 2026-10-13

### Changed

- Migrate module from Poetry to uv

## [1.15.0] - 2026-07-16

### Added

- Add blocklist management actions:
  - `append_to_blocklist`
  - `get_blocklist`
  - `remove_from_blocklist`
  - `replace_blocklist`

### Changed

- Import pydantic v2 and adapt source code and tests
- Upgrade `sekoia-automation-sdk` package version
- Regenerate _poetry.lock_ file

## [1.14.0] - 2026-06-10

### Added

- Add a `security_check_only` option on the Netskope Events connector to collect only security-check alerts (malware, malsite, DLP)

### Changed

- Remove the standalone `netskope_security_check_connector` (UUID `9e292f7e-146f-4839-926e-dac6ba8a6275`); enable the `security_check_only` option on the Netskope Events connector instead

## [1.13.1] - 2026-06-09

### Fixed

- Add trigger configuration for security check

## [1.13.0] - 2026-05-11

### Added

- Add a `netskope_security_check_connector` that collects Netskope sandbox / security-check alerts

## [1.12.0] - 2026-04-23

### Fixed

- Stop consumer when Netskope SDK throws Incorrect Token error

### Changed

- Upgrade `sekoia-automation-sdk`

## [1.11.1] - 2024-12-13

### Fixed

- Fix generating index name

## [1.11.0] - 2024-10-30

### Changed

- Upgrade `sekoia-automation-sdk`

## [1.10.5] - 2024-08-02

### Added

- Add an additional logger

### Fixed

- Handle failures when decoding the incoming message

## [1.10.4] - 2024-07-10

### Fixed

- Change the way the event lag is computed

## [1.10.3] - 2024-07-02

### Added

- Add the user-agent to the Netskope Events connector

## [1.10.2] - 2024-04-23

### Fixed

- Add an interceptor on connection timeout for the Netskope Events connector

## [1.10.1] - 2024-02-13

### Changed

- Change `event_lags` metrics from Histogram to Gauge

## [1.9.3] - 2024-01-02

### Changed

- Set `base_url` property as nullable and update the Netskope Events connector to check this property

## [1.9.0] - 2023-12-22

### Added

- Add a connector for the Netskope Transaction events

## [1.8.0] - 2023-11-22

### Changed

- Upgrade `sekoia-automation-sdk` to 1.8.1

## [1.7.1] - 2023-11-15

### Changed

- Update `netskopesdk` dependency to the latest upstream version

## [1.4.0] - 2023-06-27

### Changed

- Update `netskopesdk` dependency to the latest upstream version
- Update PIP requirements
