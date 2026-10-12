# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2026-10-12 - 0.1.4

### Fixed

- Added Pydantic-based validation to the actions so `alert_id`, `note`, `file_path`, `agent_guid` and `agent_guids` (and each of its items) reject missing or empty values, and `process_id` must be greater than zero before any API call

### Changed

- Upgraded `sekoia-automation-sdk` to `1.23.1`, aligned the module to Python 3.11+, and migrated shared and action argument models from the `pydantic.v1` compatibility shim to native Pydantic v2 to avoid v1/v2 model-mixing errors

## 2025-08-08 - 0.1.1

### Fixed

- Fixed input form for the `Terminate Process` action
