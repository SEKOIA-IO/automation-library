# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-12 - 1.1.2

### Fixed

- Trigger Alert: validate the `alert_uuid`, `api_key` and `base_url` arguments with Pydantic, rejecting missing, empty or malformed values before fetching and forwarding the alert. `alert_uuid` accepts a UUID or an alert short id (`AL` followed by 10 alphanumeric characters)
- Reject `base_url` values containing a query or a fragment

## 2026-07-30 - 1.1.1

### Changed

- Pin Docker base image to `python:3.14-bookworm` for reproducible runtime builds.

## 2026-07-23 - 1.1.0

### Changed

- Migrated module from Poetry to uv

## 2026-04-10 - 1.0.0

### Added

- Initial release
- Trigger Alert action: forwards raw Sekoia.io alert to ilert Events API
