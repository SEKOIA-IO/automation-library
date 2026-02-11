# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-02-11 - 2.10.15

### Added

- Add asset connector mapping files for Microsoft Entra ID user assets

## 2026-02-09 - 2.10.14

### Fixed

- Fix typo in the User Reset Password action manifest

## 2026-02-09 - 2.10.13

### Added

- New action in order to reset user password

### Changed

- Deprecate the old action to reset user password

## 2026-02-06 - 2.10.12

### Fixed

- Fix code formatting and linting issues
- Refactor asset connector implementation

## 2026-02-06 - 2.10.11

### Changed

- Migrate EntraID asset connector from synchronous to asynchronous implementation
- Update sekoia-automation-sdk dependency to version 1.21.3

## 2026-01-29 - 2.10.10

### Changed

- Update asset connector name

## 2026-01-23 - 2.10.9

### Changed

- Update internals field inside arguments of Entra ID asset connector

## 2026-01-22 - 2.10.8

### Changed

- Added internals field to Microsoft Entra ID asset connectors

## 2026-01-14 - 2.10.7

### Fixed

- Specify scopes when work with reset password action

## 2025-12-11 - 2.10.6

### Added

- Add organization (org) field to user assets connector, mapping company name and office location from Microsoft Entra ID
- Fix admin roles fetching in user assets connector

## 2025-11-12 - 2.10.5

### Fixed

- Fix asset loop issues in Entra ID module (issue #1059)

## 2025-10-31 - 2.10.4

### Fixed

- Fix account validator configuration access to use typed attributes

## 2025-10-30 - 2.10.3

### Fixed

- Fix the problem of early closed async loop

## 2025-10-20 - 2.10.2

### Fixed

- Fix asset connector

## 2025-10-20 - 2.10.1

### Fixed

- Fix incorrect field id for object id in "Delete App" action
- Fix incorrect description for the id field in "Revoke Sign in" action

## 2025-10-10 - 2.10.0

### Added

- Microsoft Entra ID Graph Api Connector
## 2025-10-06 - 2.9.2

### Changed

- Update conf asset connector

## 2025-09-19 - 2.9.1

### Fixed

- Update Sekoia SDK and Asset configuration

## 2025-09-19 - 2.9.0

### Fixed

- Fix async loop

## 2025-09-19 - 2.8.9

### Fixed

- Fix json configuration

## 2025-09-19 - 2.8.8

### Fixed

- Fix log error and add module AzureADConfiguration

## 2025-09-19 - 2.8.7

### Fixed

- Add some logs and change the title for asset connector

## 2025-09-16 - 2.8.6

### Fixed

- Add asset connectors

## 2024-10-15 - 2.8.5

### Fixed

- Get user action

## 2024-09-25 - 2.8.4

### Fixed

- Change result to dict

## 2024-09-25 - 2.8.3

### Fixed

- Fix results json ( Add items to results )

## 2024-09-25 - 2.8.2

### Fixed

- Fix results json type

## 2024-09-24 - 2.8.1

### Fixed

- Fix user authentification action

## 2024-05-28 - 2.8.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-28 - 2.7.0

### Changed

- Change the name of the module to Microsoft Entra ID

### Fixed

- Remove credentials from required fields (as the module support OAUTH2.0 and delegated account authentication)

## 2023-11-22 - 2.6.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-11-03 - 2.5.3

### Changed

- Some fixes in classes after testing

## 2023-11-02 - 2.5.2

### Added

- Add a class for async actions

## 2023-10-31 - 2.5.0

### Changed

- Add 3 actions : Delete app, Revoke sign in, Reset password
- Update 5 actions : Disable User, Enable user, Get sign in, Get User, Get User authentication methods
