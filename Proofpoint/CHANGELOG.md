# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-10-26 - 1.17.0

### Changed

- Migrated module from Poetry to uv (Python 3.14, ruff, mypy, mise)
- Upgrade sekoia-automation-sdk to `1.27.0` (constraint `>=1.14.0,<2`)
- TAP: configuration migrated to pydantic v2 (annotated `frequency` field)

### Fixed

- TAP: persist the checkpoint (`queryEndTime`) so that collection resumes from the last retrieved date after a restart
- TAP: only advance the checkpoint once the events have been pushed to the intake

## 2026-02-13 - 1.16.1

### Fixed

- Fix the case when the timestamp is a string instead of a datetime object

## 2024-05-28 - 1.16.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.15.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-12-14 - 1.14.1

### Fixed

- Fix the way to handle user-provided datetime

## 2023-11-22 - 1.14.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
