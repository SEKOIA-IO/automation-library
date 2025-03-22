# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-03-22 - 1.1.4

### Changed

- Refactor the way to read and extract the records from the S3 Objects.
  Previously: S3 objects were entirely loaded into memory and processed as whole files.
  Now: A streaming approach is used to extract each record individually, improving memory efficiency and performance.

## 2025-03-04 - 1.1.3

### Changed

- Upgrade dependencies

## 2025-03-04 - 1.1.2

### Changed

- Upgrade AWS dependency

## 2025-03-04 - 1.1.1

### Changed

- Upgrade AWS dependency

## 2024-05-28 - 1.1.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-05-21 - 1.0.2

### Added

- Add a metric for discarded events

## 2024-05-15 - 1.0.1

### Fixed

- Fix the command for the connector
