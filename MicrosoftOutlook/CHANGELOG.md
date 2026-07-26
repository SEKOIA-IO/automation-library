# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Upgraded `sekoia-automation-sdk` to `1.23.1` and migrated `pydantic.v1`-shim models to native Pydantic v2 to avoid v1/v2 model-mixing errors.

## 2026-07-09 - 0.1.3

### Fixed

- Simplified message action argument validation by reusing a shared `NonEmptyStr` Pydantic constraint for `user` and `message_id`, still rejecting missing or blank values before calling Microsoft Graph.

## 2025-09-22 - 0.1.2

### Added

- Added action to send emails

## 2025-02-07 - 0.1.1

### Changed

- Improved error logging
