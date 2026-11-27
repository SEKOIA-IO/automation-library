# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-11-27 - 1.21.0

### Added

- Add the `Get Sophos Fusion detections` connector, to collect the detections of Sophos Fusion (Security Operations) with the Sophos Detections GraphQL API on tenants upgraded to Sophos Fusion
- Add the optional module setting `graphql_api_url` (default `https://api.taegis.sophos.com`)

### Changed

- Query IoC from data lake: check the Sophos Fusion markers of the tenant at startup and once a day, and log an error when the tenant is upgraded, since the XDR Query API then returns no new IoC. When the markers are unavailable, warn once a day after 30 days without IoC
- Raise the minimum supported Python version to `3.14`
- Migrate project dependency management from Poetry to uv (`pyproject.toml` PEP 621 + `uv.lock`), with `mise` tasks and `ruff` instead of `black`, `isort` and `autoflake`
- Upgrade `sekoia-automation-sdk` to `1.28.1` and regenerate `uv.lock` with the latest versions of all dependencies
- Move the actions to `sophos_module/actions/` and the triggers to `sophos_module/triggers/`, and lay out `tests/` like `sophos_module/` (one `test_<file>.py` per module file)
- Query IoC from data lake: log the details of failed queries (HTTP status and error payload of the query post, error fields of a failed execution), with a hint about the `Service Principal Forensics` role on `403`

### Fixed

- Authentication: replace the deprecated `datetime.utcnow()` with a timezone-aware date (deprecation warnings on Python 3.14)
- Events and IoC triggers: compute the events lag from timestamps with or without fractional seconds and time offset, instead of failing on any format other than `%Y-%m-%dT%H:%M:%S.%fZ`

## 2026-11-24 - 1.20.1

### Fixed

- User assets: send the login of a domain user without its domain prefix (`CORP\jdoe` and `CORP/jdoe` become `jdoe`, the domain stays in `user.domain`), so the user matches the account seen in events. A local machine account keeps its prefix, and a user synced from Active Directory is never taken for one
- The field mapping changes, so the next run fetches all the users again

## 2026-07-06 - 1.20.0

### Changed

- Map `exchangeLogin` to `user.uid_alt`
- Extract domain prefix from domain-qualified names into `user.domain`
- Detect AD domain accounts (`DOMAIN/username` format) as `LDAP_ACCOUNT` instead of `UNKNOWN`
- Classify local Windows machine accounts (`COMPUTERNAME\username`) as `UserTypeId.SYSTEM` instead of `USER`

## 2026-06-29 - 1.19.2

### Fixed

- Fix naming convention of the Sophos asset connectors.

## 2026-06-29 - 1.19.1

### Fixed

- Fix anonymization of the Sophos User Asset Connector tests.

## 2026-06-29 - 1.19.0

### Added

- Add Sophos User Asset Connector (`SophosUserAssetConnector`) that collects directory users from the Sophos Central API

## 2026-06-05 - 1.18.3

### Fixed

- Fix the sophos api problem by using a cache to store the assets and avoid calling the API too much

## 2026-05-04 - 1.18.2

### Fixed

- Fix the samples in the asset connector YAML file (`device_mapping.yml`)

## 2026-04-27 - 1.18.1

### Fixed

- Fix how we register the Sophos account validator in the main module

## 2026-04-23 - 1.18.0

### Added

- Add Sophos Device Asset Connector (`SophosDeviceAssetConnector`) that collects endpoint inventory from the Sophos Central API
- Add account validator for the Sophos Device Asset Connector (`SophosAccountValidator`, registered as `sophos_account_validator`)

## 2025-12-15 - 1.17.6

### Fixed

- Update last seen "from" date in query
- Enforce 30-day limit for a "from" date

### Changed

- Update sekoia sdk to 1.21.2
- Use Checkpoint class from SDK

## 2025-11-13 - 1.17.5

### Fixed

- Add retries on transient HTTP errors

### Changed

- Update sekoia sdk to 1.21.1

## 2025-09-19 - 1.17.4

### Changed

- Release actions

## 2025-04-02 - 1.17.3

### Fixed

- Authenticate the connectors at the beginning and stop if the authentication fails

## 2024-11-20 - 1.17.2

### Fixed

- Add the ratelimit per day
- Increase the frequency to 5 minutes

## 2024-10-08 - 1.17.1

### Fixed

- Update the event lag when no events are retrieved from the API

## 2024-10-02 - 1.17.0

### Added

- Added Sophos EDR endpoint actions

## 2024-08-06 - 1.16.5

### Fixed

- Fixed the default ratelimiting

## 2024-08-02 - 1.16.4

### Fixed

- Jsonify events that goes to intakes

## 2024-07-10 - 1.16.3

### Fixed

- Change the expected status code from responses

## 2024-07-09 - 1.16.2

### Fixed

- Set max time window to fetch events as 30 days
- Add more logs

## 2024-06-06 - 1.16.1

### Fixed

- Fix the way to compute the lag on events, when no events were fetched from the API

## 2024-05-28 - 1.16.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.15.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-23 - 1.14.0

### Added

- Collecting events lag metric

## 2023-11-22 - 1.13.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-09-07 - 1.11.10

### Changed

- Fix the way to handle the HTTP exceptions

## 2023-07-26 - 1.11.9

### Changed

- fix metrics

## 2023-07-24 - 1.11.8

### Changed

- Fix the way to handle exception in the EDR connector
- Add more logs

## 2023-07-18 - 1.11.7

### Added

- add more logs
- Add an interval between two requests in the XDR connector
- Improve the way to handle failing requests

## 2023-07-13 - 1.11.0

### Changed

- Bump sdk version

## 2023-07-12 - 1.10.0

### Changed

- Bump sdk version

## 2023-06-30 - 1.9.1

### Added

- First time to add the Sophos EDR connector with query
