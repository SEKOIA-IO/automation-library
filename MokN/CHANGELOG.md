# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [1.0.0] - 2026-05-26

### Changed

- Upgrade `sekoia-automation-sdk` package version
- Adapt source code and tests for pydantic v2

### Fixed

- Use pydantic v2
- Regenerate _poetry.lock_ file
- Update time-window test to use a recent relative timestamp instead of a hardcoded old date, so it stays valid with the checkpoint's 30-day retention clamp
