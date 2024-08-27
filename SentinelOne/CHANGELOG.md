# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-08-27 - 1.17.6

### Changed

- Change the name of the triggers

## 2024-08-27 - 1.17.5

### Changed

- Change the name of the connectors

## 2024-08-26 - 1.17.4

### Fixed

- handle threats as a dictionary, instead of an object
- declare batch_duration variable

## 2024-08-08 - 1.17.3

### Changed

- filter events to discard already collected ones

## 2024-08-07 - 1.17.2

### Changed

- externalize the method to get the most recent date seen from the events

### Fixed

- fix the interactions with the context to be thread-safe
- use the most recent date seen when query new events

## 2024-08-06 - 1.17.1

### Changed

- Change the way to log messages from the connector

### Fixed

- Handle when an exception occurs during the collect of events

## 2024-07-30 - 1.17.0

### Added

- Added connector for SentinelOne logs

## 2024-05-28 - 1.16.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-03-14 - 1.15.3

### Changed

- Upgrade the SentinelOne logo

## 2024-01-26 - 1.15.0

### Changed

- Fix tenacity loop not handling the case where the query is still running.
- Fix tenacity loop retrying even if the query is failed or in error.
- Update DeepVisibilityEvent pydantic basemodel according to DeepVisibility documentation and tests.

## 2023-12-14 - 1.14.1

### Changed

- Upgrade dependencies

## 2023-11-22 - 1.14.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
