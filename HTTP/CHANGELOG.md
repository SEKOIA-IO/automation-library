# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.120.5] - 2026-08-11

### Added

- Add `HTTPActionBase` to centralize HTTP response handling logic shared by HTTP actions

### Fixed

- Ensure Request URL action now effectively enforces `fail_on_http_error` parameter:
    - when `fail_on_http_error` is `true` (default), HTTP client and server errors (4xx/5xx) fail the action
    - when `fail_on_http_error` is `false`, the action returns the response payload and status code
- Extend and centralize HTTP status class handling for informational (1xx), success (2xx), redirection (3xx), client error (4xx), and server error (5xx) responses
- Increase automated test coverage to 100%

## [1.120.4] - 2026-03-26

### Fixed

- Move URL field validation to the module

## [1.120.3] - 2026-03-19

### Changed

- Update dependencies

## [1.120.2] - 2026-02-26

### Fixed

- Fix relative path variable

## [1.120.1] - 2026-01-21

### Fixed

- Fix bearer authentication

## [1.120.0] - 2026-01-13

### Added

- Add authentication fields

## [1.119.6] - 2025-10-07

### Fixed

- Convert dictionary representation provided in the params argument into actual dict

## [1.119.5] - 2025-10-03

### Changed

- Allow to supply a dictionary in the params argument

## [1.119.4] - 2025-06-30

### Fixed

- Rollback to the previous version since a new front bug was introduced

## [1.119.3] - 2025-06-26

### Fixed

- Fix URL Request schema to accept any JSON


## [1.119.2] - 2025-06-26

### Fixed

- Fix URL Request schema to accept an array of JSON for the JSON field

## [1.119.1] - 2023-11-01

### Changed

- Add additional user-agent to work with api

## [1.119.0] - 2024-05-28

### Changed

- Upgrade sekoia-automation-sdk

## [1.118.0] - 2024-01-05

### Changed

- Support 204 response with application/json header

## [1.116.0] - 2023-11-22

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
