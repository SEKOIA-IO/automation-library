# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-07-24 - 1.42.0

### Changed

- Handling of submission without file

## 2025-07-23 - 1.41.0

### Changed

- Improve handling of key error exception to improve signature check routing

## 2025-07-21 - 1.40.0

### Changed

- Fix a bug in the option `excluded_signed`: to handle multiple signatures available

## 2025-02-05 - 1.39.0

### Changed

- Fix a minor bug related to incorrect domain_port format

## 2025-01-06 - 1.38.0

### Changed

- Add the option `exclude_suspicious_analysis`: filter out binary without enough dynamic analysis (<2) or a score gape between behavioral analysis

## 2024-09-13 - 1.37.0

### Changed

- Add the option `exclude_signed`: filter out binary with a trusted signature

## 2024-05-28 - 1.36.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.35.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
