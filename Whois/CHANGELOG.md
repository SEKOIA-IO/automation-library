# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-07-11 - 1.25.1

### Fixed

- Validate the `query` argument via a native Pydantic v2 model using a `NonEmptyStr` alias backed by `StringConstraints`, rejecting missing/empty/blank values before performing the WHOIS lookup without narrowing the field beyond a plain string

### Changed

- Bump `sekoia-automation-sdk` to 1.23.1

## 2025-02-08 - 1.25.0

### Fixed

- Fix PywhoisError exception
- Upgrade sekoia-automation-sdk and python-whois

## 2024-05-28 - 1.24.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.23.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
