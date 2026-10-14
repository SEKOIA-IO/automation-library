# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2026-10-14 - 1.1.0

### Changed

- Reuse the stream cursor between batches instead of creating a new query each time
- Create a new query from the last event date when the stream cursor is rejected

### Fixed

- Respect the SIEM integration API rate limit (one call per minute)
- Use the maximum page size (500) to reduce the number of API calls
- Save the checkpoint after each forwarded page instead of at the end of the batch
- Wait before retrying after an error instead of retrying immediately
- Fix the error message logged on failed API requests

## 2026-01-07 - 1.0.0

### Changed

- Release of the module
