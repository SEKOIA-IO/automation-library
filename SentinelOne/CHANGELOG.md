# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-01-10 - 1.20.3

### Fixed

- Fix caching problem

## 2025-03-03 - 1.20.2

### Fixed

- Fix sentinelone action uppercase arguments problem


## 2025-01-10 - 1.20.1

### Fixed

- Fix for singularity connector for iteration through correct list of items

## 2025-01-07 - 1.20.0

### Changed

- Update the SentinelOne Singularity connector to fetch detailed alerts

## 2024-12-06 - 1.19.10

### Added

- Add the new configuration part in sentinelOne action

## 2024-12-16 - 1.19.9

### Changed

- discard already collected alerts in the singularity connector

### Fixed

- Fix the start_time parameter into milliseconds in the singularity connector

## 2024-12-13 - 1.19.8

### Fixed

- Fix the pagination system in the SentinelOne Singularity connector

## 2024-12-10 - 1.19.7

### Changed

- Handle the timeout exception


## 2024-12-10 - 1.19.6

### Fixed

- Fix the product name in the SentineOne Identity connector

## 2024-12-04 - 1.19.5

### Fixed

- Set hostname and api_token as required in the module configuration

## 2024-12-04 - 1.19.4

### Fixed

- Fix the declaration of the create IoCs action

## 2024-12-04 - 1.19.3

### Fixed

- Fix the metrics

## 2024-12-03 - 1.19.2

### Fixed

- Fix the startDateTime parameter

## 2024-12-03 - 1.19.1

### Fixed

- Fix the way to compute the address of the tenant in the SentinelOne Singularity Identity connector

## 2024-11-30 - 1.19.0

### Added

- Support for SentinelOne Singularity Identity

## 2024-11-28 - 1.18.7

### Added

- Add the account ids to required fields in create iocs actions


## 2024-11-28 - 1.18.6

### Fixed

- Fix the result problem in create iocs action

## 2024-09-23 - 1.18.5

### Added

- Add Beta flag to new actions

## 2024-09-19 - 1.18.4

### Added

- Add source to data sent

## 2024-09-19 - 1.18.3

### Fixed

- Fix Ioc type problem

## 2024-09-18 - 1.18.2

### Fixed

- Fix create_iocs type problem

## 2024-09-18 - 1.18.1

### Changed

- Update analyst_verdict variable

## 2024-09-06 - 1.18.0

### Added

- Add some new actions to sentinelone

## 2024-08-27 - 1.17.6

### Changed

- Change the name of the triggers

## 2024-08-27 - 1.17.5

### Changed

- Change the name of the connectors

## 2024-08-26 - 1.17.4

### Fixed

- handle threats as a dictionary, instead of an object
- declare batch_duration variable

## 2024-08-08 - 1.17.3

### Changed

- filter events to discard already collected ones

## 2024-08-07 - 1.17.2

### Changed

- externalize the method to get the most recent date seen from the events

### Fixed

- fix the interactions with the context to be thread-safe
- use the most recent date seen when query new events

## 2024-08-06 - 1.17.1

### Changed

- Change the way to log messages from the connector

### Fixed

- Handle when an exception occurs during the collect of events

## 2024-07-30 - 1.17.0

### Added

- Added connector for SentinelOne logs

## 2024-05-28 - 1.16.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-03-14 - 1.15.3

### Changed

- Upgrade the SentinelOne logo

## 2024-01-26 - 1.15.0

### Changed

- Fix tenacity loop not handling the case where the query is still running.
- Fix tenacity loop retrying even if the query is failed or in error.
- Update DeepVisibilityEvent pydantic basemodel according to DeepVisibility documentation and tests.

## 2023-12-14 - 1.14.1

### Changed

- Upgrade dependencies

## 2023-11-22 - 1.14.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
