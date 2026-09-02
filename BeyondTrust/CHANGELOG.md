# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-09-01 - 1.4.0

### Added

- Add the customer and representative details (public/private IP addresses, hostname, OS) to the events of the
  PRA platform connector, correlated to the performer of each event through its `gsnumber`
- Add the `gsnumber` of the performer and of the destination of each event
- Add the session wide `file_transfer_count`, `file_move_count` and `file_delete_count` counters

## 2026-04-30 - 1.3.0

### Added

- Add Team connector for BeyondTrust PRA

## 2026-04-28 - 1.2.0

### Added

- Add Vault Account Activity connector for BeyondTrust PRA

## 2026-03-26 - 1.1.0

### Added

- Add syslog connector for BeyondTrust PRA

## 2026-01-16 - 1.0.2

### Fixed

- Fix the condition to log API errors when listing sessions

## 2025-12-23 - 1.0.1

### Fixed

- Fix the logger when facing an API error when listing sessions

## 2025-06-10 - 1.0.0

### Fixed

- return when the connector faces an API error 

## 2025-02-12 - 0.2.0

### Changed

- Changed the way we gather sessions
