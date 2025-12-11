
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-12-11 - 1.0.4

### Changed

- Replace `requests` library by `httpx`, with the HTTP/2.0 support, for making HTTP requests
- Deprecate the old connectors

## 2025-11-28 - 1.0.3

### Fixed

- Add jitter strategy to retry mechanism to avoid thundering herd issue
- Increase timeout for API requests to 5 minutes
- Decrease checkpoint ignore_older_than to 7 days
- Decrease the batch size to 200 events per request


## 2025-06-11 - 1.0.2

### Added

- Add new connector and trigger for Ubika Cloud Protector Next Gen

## 2024-09-02 - 1.0.1

### Fixed

- Fix the way to compute the lag on events, when no events were fetched from the API

## 2024-05-28 - 1.0.0

### Changed

- Upgrade sekoia-automation-sdk
