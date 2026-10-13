# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-13 - 1.28.2

### Fixed

- Scan file: report a failed upload or an unavailable scan report with a clear error instead of crashing or returning "not detected"

## 2026-10-12 - 1.28.1

### Changed

- Validate action arguments with Pydantic v2 models: missing or empty values are rejected before any HTTP request or file I/O, `ip` must be an IP address and `url` an HTTP(S) URL
- Declare `minLength: 1` on required string arguments in the action manifests
- Bump `sekoia-automation-sdk` to 1.23.1

### Fixed

- Honour the `detect_treshold` argument declared in the scan file and scan URL action manifests

## 2024-05-28 - 1.28.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.27.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
