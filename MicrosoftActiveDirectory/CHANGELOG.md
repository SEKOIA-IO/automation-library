# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-02-11 - 1.4.7

### Added

- Add asset connector mapping files for Microsoft Active Directory user assets

## 2025-02-09 - 1.4.6

### Changed

- Upgrade sekoia-automation-sdk to 1.22.2

## 2026-01-29 - 1.4.5

### Changed

- Update asset connector name

## 2026-01-23 - 1.4.4

### Changed

- Update internals field inside arguments of Microsoft AD asset connectors

## 2026-01-14 - 1.4.2

### Fixed

- Fixed handling of the userAccountControl attribute when returned as a list from LDAP queries
- Added some more logs for debugging


## 2025-11-20 - 1.4.1

### Fixed

- Update the capabilities of the user asset connector

## 2025-11-20 - 1.4.0

### Added

- Add for the first time user asset connector

## 2025-02-04 - 1.3.9

### Added

- Support Output file

## 2024-12-03 - 1.3.8

### Fixed

- Convert ldap search attributes to dict

## 2024-11-28 - 1.3.7

### Fixed

- Manage datetime from ldap search response

## 2024-11-27 - 1.3.6

### Fixed

- Manage empty attributes in AD search response

## 2024-11-27 - 1.3.5

### Fixed

- Manage non-serializable objects in search results

## 2024-10-30 - 1.3.4

### Fixed

- Change result type again

## 2024-10-30 - 1.3.3

### Fixed

- Change result type

## 2024-10-30 - 1.3.2

### Fixed

- Modify the module result

## 2024-10-28 - 1.3.1

### Added

- Add a module to search in AD

## 2024-05-28 - 1.3.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-12-15 - 1.2.1

### Changed

- Add some exceptions

## 2023-12-14 - 1.2.0

### Changed

- Improve the way to disable and enable account by getting the real userAccountControl.
- Add an Exception if there's no permission to do some actions

## 2023-11-29 - 1.1.0

### Changed

- Update LDAP query
- Add some tests

## 2023-11-23 - 1.0.0

### Added

- Add for the first time microsotf AD actions
