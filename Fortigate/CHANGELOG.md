# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-12 - 1.31.1

### Changed

- Upgrade sekoia-automation-sdk to 1.23.1 and validate action arguments with native Pydantic v2 models

### Fixed

- Reject a missing or empty `name`, `fqdn` or `ip` before calling the firewalls
- Reject an `ip` that is not an IPv4 address in the add IP address action
- Read the `associated-interface` argument declared in the add IP address and add FQDN manifests
- Disable local user: log a firewall timeout and continue with the next firewall instead of failing

## 2026-07-15 - 1.31.0

### Added

- Added a configuration parameter to control TLS certificate verification for all Fortigate actions

## 2025-12-24 - 1.30.0

### Added

- Added action fortigate_disable_local_user

## 2025-04-07 - 1.29.1

### Fixed

- Fix the output of the `Add new Address group to a Fortigate firewall` action

## 2024-05-28 - 1.29.0

### Added

- Added VDOM as a parameter

## 2024-05-28 - 1.28.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.27.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
