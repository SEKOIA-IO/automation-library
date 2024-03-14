# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-03-14 - 1.15.3

### Changed

- Upgrade the SentinelOne logo

## 2023-12-14 - 1.14.1

### Changed

- Upgrade dependencies

## 2023-11-22 - 1.14

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1

## 2024-01-26 - 1.15.1

### Changed
- Fix tenacity loop not handling the case where the query is still running.
- Fix tenacity loop retrying even if the query is failed or in error.
- Update DeepVisibilityEvent pydantic basemodel according to DeepVisibility documentation and tests.
