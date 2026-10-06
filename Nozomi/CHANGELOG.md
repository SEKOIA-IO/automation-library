# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-09-16 - 1.2.0

### Added

- Add Nozomi device asset connector that fetches Guardian/CMC assets (`query=assets`) and maps them to the OCSF Device inventory model, using `created_at` for time-based filtering and checkpointing
- Add an account validator that verifies Nozomi Networks credentials via API sign-in

## 2026-02-11 - 1.1.1

### Added

- Add headers to identify the application when calling the API

## 2025-12-09 - 1.1.0

### Added

- Add more fields to the result event.

## 2025-06-10 - 1.0.0

### Added

- Add support for Nozomi Vantage.
