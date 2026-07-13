# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-07-09 - 1.21.1

### Fixed

- Validate entrypoint arguments via native Pydantic v2 models instead of the `pydantic.v1` compatibility shim, rejecting missing/empty/blank values before sending HTTP requests (`alert_uuid` as `UUID`, `base_url` as `HttpUrl`, `api_key` and `message` kept as non-empty strings)
- Bump `sekoia-automation-sdk` to 1.23.1

## 2024-05-28 - 1.21.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.20.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
