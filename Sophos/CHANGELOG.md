# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.21.0] - 2026-11-27

### Added

- `[BETA] Get Sophos Fusion detections` connector: collects the Sophos Fusion detections (Security Operations) with the Detections GraphQL API, for the tenants upgraded to Sophos Fusion
- Optional module setting `graphql_api_url` (default `https://api.taegis.sophos.com`)

### Changed

- Query IoC from data lake:
  - Mark it `[DEPRECATED]`: on tenants upgraded to Sophos Fusion, the data lake no longer receives new IoCs
  - Log an error when the tenant is upgraded (Sophos Fusion check at startup, then daily, single 10-second attempt), or after 30 days without IoC when the check is unavailable
- Errors:
  - Share the collection loop of the triggers and the description of the Sophos API errors, with what to check: credentials on `401`, required role on `403`, rate limit on `429`, Sophos-side error on `5xx`
  - Show the `401` and `403` errors at most once per hour instead of once per cycle
  - Keep the triggers running on network errors (connection refused, timeout)
- Logging:
  - Show the users only the lifecycle, the errors and the Sophos Fusion upgrade; send the per-cycle diagnostics and the skipped assets to the pod logs
  - Remove the request and query ids from the error messages, so identical errors are deduplicated
- Packaging:
  - Migrate from Poetry to uv and `ruff`, and raise the minimum Python version to `3.14`
  - Upgrade `sekoia-automation-sdk` to `1.28.1` and the other dependencies
  - Move the actions and triggers to `sophos_module/actions/` and `sophos_module/triggers/`, and mirror this layout in `tests/` with 100% coverage

### Fixed

- Query IoC from data lake: stop polling a data lake query after 5 minutes, including the time of the status requests, or at once on a client error, instead of blocking the collection
- Add a 60-second timeout to the Sophos REST API and authentication requests, so a stalled connection no longer blocks a trigger or an action
- Isolate and deisolate actions: raise the HTTP errors other than `400` instead of returning nothing
- Events lag: parse the timestamps with or without fractional seconds and time offset
- Authentication: replace the deprecated `datetime.utcnow()`

## [1.20.1] - 2026-11-24

### Fixed

- User assets: send the login of a domain user without its domain prefix (`CORP\jdoe` and `CORP/jdoe` become `jdoe`, the domain stays in `user.domain`), so the user matches the account seen in events. A local machine account keeps its prefix, and a user synced from Active Directory is never taken for one
- The field mapping changes, so the next run fetches all the users again

## [1.20.0] - 2026-07-06

### Changed

- Map `exchangeLogin` to `user.uid_alt`
- Extract domain prefix from domain-qualified names into `user.domain`
- Detect AD domain accounts (`DOMAIN/username` format) as `LDAP_ACCOUNT` instead of `UNKNOWN`
- Classify local Windows machine accounts (`COMPUTERNAME\username`) as `UserTypeId.SYSTEM` instead of `USER`

## [1.19.2] - 2026-06-29

### Fixed

- Fix naming convention of the Sophos asset connectors.

## [1.19.1] - 2026-06-29

### Fixed

- Fix anonymization of the Sophos User Asset Connector tests.

## [1.19.0] - 2026-06-29

### Added

- Add Sophos User Asset Connector (`SophosUserAssetConnector`) that collects directory users from the Sophos Central API

## [1.18.3] - 2026-06-05

### Fixed

- Fix the sophos api problem by using a cache to store the assets and avoid calling the API too much

## [1.18.2] - 2026-05-04

### Fixed

- Fix the samples in the asset connector YAML file (`device_mapping.yml`)

## [1.18.1] - 2026-04-27

### Fixed

- Fix how we register the Sophos account validator in the main module

## [1.18.0] - 2026-04-23

### Added

- Add Sophos Device Asset Connector (`SophosDeviceAssetConnector`) that collects endpoint inventory from the Sophos Central API
- Add account validator for the Sophos Device Asset Connector (`SophosAccountValidator`, registered as `sophos_account_validator`)

## [1.17.6] - 2025-12-15

### Fixed

- Update last seen "from" date in query
- Enforce 30-day limit for a "from" date

### Changed

- Update sekoia sdk to 1.21.2
- Use Checkpoint class from SDK

## [1.17.5] - 2025-11-13

### Fixed

- Add retries on transient HTTP errors

### Changed

- Update sekoia sdk to 1.21.1

## [1.17.4] - 2025-09-19

### Changed

- Release actions

## [1.17.3] - 2025-04-02

### Fixed

- Authenticate the connectors at the beginning and stop if the authentication fails

## [1.17.2] - 2024-11-20

### Fixed

- Add the ratelimit per day
- Increase the frequency to 5 minutes

## [1.17.1] - 2024-10-08

### Fixed

- Update the event lag when no events are retrieved from the API

## [1.17.0] - 2024-10-02

### Added

- Added Sophos EDR endpoint actions

## [1.16.5] - 2024-08-06

### Fixed

- Fixed the default ratelimiting

## [1.16.4] - 2024-08-02

### Fixed

- Jsonify events that goes to intakes

## [1.16.3] - 2024-07-10

### Fixed

- Change the expected status code from responses

## [1.16.2] - 2024-07-09

### Fixed

- Set max time window to fetch events as 30 days
- Add more logs

## [1.16.1] - 2024-06-06

### Fixed

- Fix the way to compute the lag on events, when no events were fetched from the API

## [1.16.0] - 2024-05-28

### Changed

- Upgrade sekoia-automation-sdk

## [1.15.2] - 2024-02-13

### Changed

- Change event_lags metrics from Histogram to Gauge

## [1.14.0] - 2023-11-23

### Added

- Collecting events lag metric

## [1.13.0] - 2023-11-22

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## [1.11.10] - 2023-09-07

### Changed

- Fix the way to handle the HTTP exceptions

## [1.11.9] - 2023-07-26

### Changed

- fix metrics

## [1.11.8] - 2023-07-24

### Changed

- Fix the way to handle exception in the EDR connector
- Add more logs

## [1.11.7] - 2023-07-18

### Added

- add more logs
- Add an interval between two requests in the XDR connector
- Improve the way to handle failing requests

## [1.11.0] - 2023-07-13

### Changed

- Bump sdk version

## [1.10.0] - 2023-07-12

### Changed

- Bump sdk version

## [1.9.1] - 2023-06-30

### Added

- First time to add the Sophos EDR connector with query
