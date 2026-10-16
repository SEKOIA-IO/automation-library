# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-12 - 1.23.2

### Changed

- Validate the arguments of all actions with Pydantic v2 models instead of the `get_arg_*` helpers
- Bump sekoia-automation-sdk to 1.23.1

### Fixed

- Reject a negative `budget` and a `first_page` lower than 1
- Reject a domain with an empty label, such as `.com` or `example..com`
- Declare in the datascan manifest that exactly one of `ip` or `string` is required

## 2024-05-28 - 1.23.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.22.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
