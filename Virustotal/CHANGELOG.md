# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- Validate VirusTotal entrypoint arguments with native Pydantic v2 types: `ip` now uses `IPvAnyAddress`, `url` now uses `HttpUrl`, and polymorphic `resource`, free-text `comment`, path-like `file`, and hash `hash` remain non-empty strings
- Bump `sekoia-automation-sdk` to 1.23.1

## 2026-07-09 - 1.28.1

### Fixed

- Validate the `hash`, `url`, `ip`, `resource`, `comment`, and `file` VirusTotal action arguments with Pydantic, rejecting empty or missing values before any HTTP request or file I/O

## 2024-05-28 - 1.28.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.27.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
