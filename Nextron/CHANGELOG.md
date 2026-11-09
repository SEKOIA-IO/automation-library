# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2026-11-09 - 1.0.1

### Added

- Add an account validator that checks the API key against THOR Cloud and THOR Cloud Lite.

### Fixed

- Mark a scan as forwarded only when the intake accepted all of its events, so delivery errors no longer lose scans.
- Forward and persist scans one at a time to bound memory usage and avoid resending delivered scans after a restart.
- Do not forward scans again when Days Back is raised; scans no earlier window covered are still backfilled.
- Skip scans with encrypted logs with a single warning instead of one parse error per line.
- Stop the connector promptly instead of waiting for the end of the polling interval.

## 2026-09-10 - 1.0.0

### Added

- Add support for Nextron THOR Cloud.
- Add an action to link an existing or create a new THOR Cloud campaign, then generate a campaign-scoped launcher URL and OS-specific bootstrap command.

### Changed

- Improve the launcher action form with separate existing/new campaign variants, named account scan profiles, and RFC 3339 campaign expiration dates.
