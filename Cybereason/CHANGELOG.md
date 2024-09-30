# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2024-06-06 - 1.13.2

### Fixed

- Fix the way to compute the lag on events, when no events were fetched from the API

## 2024-05-30 - 1.13.1

### Fixed

- Fix the way to compute the lag on events, when no events were fetched from the API

## 2024-05-28 - 1.13.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-13 - 1.12.1

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2023-11-22 - 1.11.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2023-09-27 - 1.9.7

### Changed

- add more logs

## 2023-09-25 - 1.9.6

### Fixed

- fixed incorrect logging messages

## 2023-09-18 - 1.9.5

### Added

- support the new endpoint 

## 2023-09-07 - 1.9.4

### Changed

- wait when failing to authenticate or forward events

## 2023-08-28 - 1.9.3

### Changed

- revert the join on groupIds

## 2023-08-21 - 1.9.2

### Changed

- join groupIds with a comma as separator
