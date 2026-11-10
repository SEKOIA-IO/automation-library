# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-11-10

### Added

- Add the user guide `docs/user_guide_easyvista_request_lifecycle_with_playbook.md`, which builds a repeatable playbook covering the full ticket lifecycle

### Changed

- Align the `Dockerfile` with the other automation modules: same uv install (`/uv` and `/uvx`), `uv sync` options and comments

### Fixed

- Fix `Read-only file system: '/tmp/tls'` error at action start by symlinking `/tmp` to `/dev/shm` in `Dockerfile`

## [1.0.0] - 2026-11-09

### Added

- Add the EasyVista Service Manager integration with account validation, Bearer token or Basic authentication, TLS verification, and configurable credentials
- Add a shared API client with HTTPS enforcement, URL encoding, response error handling, credential redaction, and safe retry rules
- Add 17 synchronous playbook actions:
  - `Create Request / Incident`
  - `Update Request / Incident`
  - `Close Request / Incident`
  - `Suspend Request / Incident`
  - `Restart Request / Incident`
  - `View Requests / Incidents list`
  - `View Request / Incident`
  - `View Request / Incident Comment`
  - `View Request / Incident Problem`
  - `Upload and attach a Document to a Request / Incident`
  - `Get the list of Documents of a Request / Incident`
  - `Get a specific Document of a Request / Incident`
  - `Delete a request document`
  - `Create an action related to an incident`
  - `Create Task`
  - `Get Questionnaires from non terminated actions`
  - `Get questionnaire from specific actions`
- Document module setup, authentication, action inputs, API behavior, and known EasyVista tenant limitations
- Add automated tests for action mappings, API errors, authentication, retry behavior, and descriptor consistency
