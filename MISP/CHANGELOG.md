# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased


## 2026-01-29 - 2.8.3

### Added

- Automatic proxy detection from environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`) when no explicit proxy configuration is provided in module settings
- Type annotations for improved code quality and IDE support

### Changed

- Proxy configuration now uses `urllib.request.getproxies()` as fallback when `http_proxy`/`https_proxy` are not set in module configuration

## 2024-05-28 - 2.8.0

### Changed

- Upgrade sekoia-automation-sdk

## 2023-11-22 - 2.7.0

### Changed

- Upgrade dependencies: Sekoia-automation-SDK 1.8.1
