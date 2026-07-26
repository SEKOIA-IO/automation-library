# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-07-10 - 1.24.1

### Fixed

- Validate the `ip`/`cidr` arguments of `IKnowIPHistoryAction`, `IKnowIPExistAction`, and `IKnowIPListAction` via Pydantic models, using `IPvAnyAddress` for `ip` and `IPvAnyNetwork` for `cidr` to reject missing, blank, and invalidly shaped values before issuing API calls.

### Changed

- Upgraded `sekoia-automation-sdk` to 1.23.1 and migrated `pydantic.v1`-shim models to native Pydantic v2 to avoid a v1/v2 model-mixing error.

## 2024-05-28 - 1.24.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 1.23.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
