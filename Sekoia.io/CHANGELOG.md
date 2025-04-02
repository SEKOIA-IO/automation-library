# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-04-02 - 2.67.10

### Fixed

Support for file input - action synchronize asset - Fix output type


## 2025-03-20 - 2.67.9

### Added

- Addition of cases actions and triggers

## 2025-03-03 - 2.67.8

### Fixed

Support for file input - action synchronize asset - Fix output type

## 2025-03-18 - 2.67.7

### Fixed

Fix the return variable for the Get Common Values module


## 2025-02-04 - 2.67.6

### Added

Support for file input - action synchronize asset

## 2025-02-10 - 2.67.5

### Changed

- Update `Update Alert Status by name` to add a comment when changing alert status

## 2025-02-10 - 2.67.4

### Added

- Update Alert trigger with rule_names_filter
 
## 2025-01-27 - 2.67.3

### Fixed

- Fix `docker-parameters` of new action to update statuses by name

## 2025-01-21 - 2.67.2

### Changed

- Update the module description

## 2025-01-03 - 2.67.1

### Fixed

- Fix `list asset` action's arguments types
- Fix `create asset`'s url


## 2024-12-18 - 2.67.0

### Added

- Add an action to create a case
- Add an action to modify a case
- Add an action to get the details of a case
- Add an action to add a comment to a case

## 2024-12-09 - 2.66.2

### Changed

- Change `Update Alert Status` to support `status names` as input 

## 2024-12-12 - 2.66.1

### Added

- Add an action to add events to a case

## 2024-12-10 - 2.65.12

### Changed

- Update synchronize asset action

## 2024-11-27 - 2.65.7

### Changed

- Update get alert action with an option to get the associated cases




## 2024-11-27 - 2.65.4

### Changed

- Add list, create and delete actions using asset management V2

## 2024-11-14 - 2.65.1

### Changed

- Add synchronize asset action

## 2024-11-12 - 2.65.0

### Changed

- Remove attribute `rule.description` when fetching alerts

## 2024-11-04 - 2.64.8

### Fixed

- Revert `Update Alert Status` changes from 2.64.7 to maintain compatibility

## 2024-10-18 - 2.64.7

### Changed

- Change `Update Alert Status` to support `status names` as input 

## 2024-10-08 - 2.64.6

### Changed

- Changed the displayed name of the module

## 2024-10-08 - 2.64.5

### Added

- Add a module to merge assets


## 2024-10-08 - 2.64.4

### Changed

- Return more information in Sekoia Alert comment trigger 

## 2024-10-04 - 2.64.3

### Changed

- Bump SDK

## 2024-10-03 - 2.64.2

### Fixed

- Fix required arguments in the `activate countermeasure` action

## 2024-08-30 - 2.64.1

### Changed

- Bump SDK to latest version

## 2024-08-12 - 2.64.0

### Changed

- Enforce default and limit specified in action manifests

## 2024-08-02 - 2.63.0

### Changed

- No need for a configuration for all Sekoia.io modules

## 2024-07-23 - 2.62.1

### Fixed

- Fixes potential errors in URLs

## 2024-07-23 - 2.62.0

### Changed

- Improve logging when fetching an alert failed.

## 2024-07-08 - 2.61.1

### Fixed

- Add miminum, maximum and default value for actions with limit parameter

## 2024-06-10 - 2.60.6

### Fixed

- Fixing typo on action_delete_rule.json

## 2024-06-10 - 2.60.5

### Changed

- Addition of default values on json files

## 2024-06-05 - 2.60.4

### Changed

- Fix docker_parameters for rule actions and add them to main.py

## 2024-06-04 - 2.60.3

### Changed

- Updated uuids of rules actions

## 2024-05-31 - 2.60.2

### Added

- Add Rules actions

## 2024-05-29 - 2.60.1

### Changed

- Ignore authenticated messages

## 2024-05-28 - 2.60.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-05-17 - 2.59.1

### Changed

- Add output results to Get context action
- Add some tests

## 2024-01-18 - 2.58.3

### Fixed

- Do not push empty bundles to the IC

## 2024-01-15 - 2.58.2

### Changed

- Improve 'Add IOC to IOC Collection' action

## 2024-01-04 - 2.58.1

### Changed

- Change description of rule filter to avoid confusion for users

## 2024-01-04 - 2.57.1

### Fixed

- Log an error when Alert API is not available after 10 retries.

## 2024-01-04 - 2.57.0

### Changed

- Read v2 notifications from Sekoia.io’s `liveapi`.

## 2024-01-04 - 2.56.3

### Changed

- Change log level from error to info when receiving a non v1 event

## 2023-12-12 - 2.56.1

### Changed

- Fix parameter names for add an IOC to an IOC Collection action

## 2023-12-12 - 2.56.0

### Added

- Action to add an IOC to an IOC Collection

## 2023-12-07 - 2.55.0

### Added

- Add heartbeat for triggers

## 2023-12-08 - 2.54.1

### Changed

- Fix retry policy when getting events

## 2023-12-01 - 2.54.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.2

## 2023-11-23 - 2.53.0

### Added

- Add support for custom CA certs bundle in triggers

## 2023-11-22 - 2.52.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-10-31 - 2.50.0

### Changed

- Update get context action

## 2023-10-10 - 2.47.0

### Added

- Add the action that let us get reports from a specific term

