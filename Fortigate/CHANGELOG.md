# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-07-09 - 1.30.1

### Changed

- Upgraded sekoia-automation-sdk to 1.23.1, aligned the module with Python 3.11, and migrated Pydantic argument models from the `pydantic.v1` shim to native Pydantic v2 to avoid v1/v2 model-mixing errors

### Fixed

- Validate the FQDN, IP address, local user name, and address group name entrypoint arguments via Pydantic models, using `IPvAnyAddress` for `add_ip_address.ip` and non-empty strings for FQDN/name fields where no stricter built-in Fortigate-safe type is available

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
