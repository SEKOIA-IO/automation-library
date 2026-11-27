# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.21.0] - 2026-11-25

### Changed

- Packaging:
  - migrate the module from Poetry to uv, with mise tasks, and run it on Python 3.14
  - upgrade `sekoia-automation-sdk` to 1.27.2 and refresh the other dependencies
  - pin `aiohttp` below 3.14, as `aioresponses` (tests) is not compatible with it yet
  - lint and format the code with ruff instead of black
- Management API:
  - log the active subscriptions when the connector starts
  - centralize the classification of the errors (whether they need an action from the customer) and their remediation hints in `errors.py`
- Message Trace:
  - reuse the MSAL application between queries (OAuth), so access tokens are cached until they expire instead of being requested at every query
  - log authentication failures in a single line
  - truncate the HTTP response bodies in the error logs to 500 characters
- Tests:
  - reach 100% coverage (branches included) and treat warnings as errors
  - align the tests folder structure with the source code
  - remove duplicated tests with `pytest.mark.parametrize`
  - mock `time.sleep` to speed up retries

### Fixed

- Management API:
  - activate each Office365 subscription independently, so a failure on one content type (including network errors, timeouts and unreadable responses) no longer prevents the activation of the others
  - retry the activation of the failed subscriptions with an exponential backoff (1 minute up to 1 hour) while collecting the active ones, so the connector recovers without a restart
  - when no event can be collected (no active subscription, authentication or permission error), at startup or while running, log an actionable message and restart the connector with the same backoff: the SDK stops it with a critical error only if the error persists, instead of stopping it at once at startup or never while running
  - reactivate the subscriptions disabled while the connector is running, and do not advance the checkpoint while no subscription is active
  - add actionable error messages when Microsoft reports that the tenant does not exist (unified audit logging not enabled or not provisioned yet), and on permission errors (missing `ActivityFeed.Read`)
  - handle the network and invalid JSON errors when listing the subscriptions
  - stop logging errors on requests interrupted by the connector shutdown
- Message Trace:
  - stop sending empty log messages when an access token cannot be retrieved (OAuth)

## [2.20.7] - 2026-07-02

### Fixed

- Add intake_server to connector's manifests

## [2.20.6] - 2026-07-01

### Changed

- Add retries for reading and writing context file

## [2.20.5] - 2026-06-01

### Fixed

- Handle unexpected aiohttp session closures by raising `SessionClosedError` and rebuilding the Office365 client when needed.

## [2.20.4] - 2026-05-22

### Fixed

- Ignore AF20024 error code when activating subscriptions, as it indicates the subscription is already enabled

## [2.20.3] - 2026-04-27

### Fixed

- Log as critical when failing to activate the subscription
- Fix the way to shut down the connector

## [2.20.2] - 2026-04-16

### Fixed

- Fixed an issue where the asyncio event loop was closed after each run

## [2.20.1] - 2026-03-19

### Changed

- Deprecate old Office 365 Message Trace connectors

## [2.20.0] - 2026-03-05

### Added

- Add Office 365 Message Trace Graph API connector

### Changed

- Upgrade dependencies
- Upgrade sekoia-automation-sdk

## [2.19.1] - 2025-12-19

### Changed

- Skip expired events using their `ExpirationTime` field


## [2.19.0] - 2025-12-01

### Changed

- Improve Management API connector shutdown and error handling
- Enhance resource management with proper client closure tracking
- Fix exception handling to properly access authentication error responses
- Optimize timing logic in event forwarding loop

## [2.18.9] - 2025-10-28

### Changed

- Improve the logging when an authentication error occurs in the Management API connector

## [2.18.8] - 2024-01-13

### Fixed

- Check if the HTTP client session is defined and not closed

## [2.18.7] - 2024-01-10

### Fixed

- Save the end date of each date range in the checkpoint, in order to always progress

## [2.18.6] - 2024-01-10

### Changed

- Allow configuration the time range interval from environment variables

## [2.18.5] - 2024-12-19

### Fixed

- Always constraint the checkpoint offset in the last 7 days

## [2.18.4] - 2024-11-05

### Fixed

- Fix secrets

## [2.18.3] - 2024-11-05

### Fixed

- Change the shutdown the connector

## [2.18.2] - 2024-11-04

### Fixed

- Change the way to use the asyncio event loop

## [2.18.1] - 2024-11-04

### Fixed

- Reduce to 7 days the catch back in the past

## [2.18.0] - 2024-10-30

### Changed

- Upgrade sekoia-automation-sdk

## [2.17.10] - 2024-08-21

### Added

- Added more verbose logging for auth errors

## [2.17.9] - 2024-07-03

### Fixed

- Change the way to close the Office365 client

## [2.17.8] - 2024-07-03

### Fixed

- Change the way to close the Office365 client

## [2.17.7] - 2024-07-03

### Fixed

- Fix the checkpoint system when the context doesn't exist

## [2.17.6] - 2024-07-01

### Fixed

- Fix run_until_complete method

## [2.17.5] - 2024-07-01

### Fixed

- Move async main stuff in a dedicated async method

## [2.17.4] - 2024-06-26

### Fixed

- Fix the dates used to pull the contents

## [2.17.3] - 2024-06-26

### Fixed

- Fix the way to get the content of HTTP errors

## [2.17.2] - 2024-06-25

### Fixed

- Update the internal cursor when saving a new date in the checkpoint

## [2.17.1] - 2024-06-24

### Fixed

- Fix the way to use the event loop

## [2.17.0] - 2024-06-17

### Changed

- Transform Office365 Management API connector as asynchronous connector

## [2.16.1] - 2024-06-12

### Added

- Declare Office365 Management API connector as trigger

## [2.16.0] - 2024-05-28

### Changed

- Upgrade sekoia-automation-sdk

## [2.15.1] - 2024-05-28

### Fixed

- Add the intake key argument in the configuration of the `management_api` logs collector

## [2.15.0] - 2024-02-28

### Added

- Added `management_api` logs collector

### Changed

- Splited the module into two submodules to separate `management_api` from `message_trace`

## [2.14.2] - 2024-02-13

### Changed

- Change event_lags metrics from Histogram to Gauge

## [2.13.0] - 2023-11-22

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## [2.12.1] - 2023-11-08

### Fixed

- Fix metrics
