# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.3 - 2026-08-26

### Fixed

- Retry 429 and 5xx responses instead of surfacing the first one to the caller
- Keep a mid-window failure from being read as a rejected cursor and re-reading the whole window
- Hold the ids a re-read meets first in the trimmed ledger, not the ones it ends on

### Changed

- Trim the comments down to the ones that guard an invariant

## 0.1.2 - 2026-08-25

### Added

- `excluded_actions`: drop chosen Slack actions instead of forwarding them

### Fixed

- Forward an entry once when Slack repeats it inside a single page

## 0.1.1 - 2026-08-25

### Added

- Describe every connector setting in the console

### Fixed

- Render the logo at full canvas size

## 0.1.0 - 2026-08-25

### Added

- Connector fetching audit events from the Slack Audit Logs API
- Account validator checking the Slack user token
