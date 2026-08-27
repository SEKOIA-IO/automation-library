# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-08-27

### Changed

- Document lint and test commands in README and align lint tooling configuration for local validation

### Fixed

- Accept `client_secret` from playbook runtime whether provided as raw string or `SecretStr`-like value
- Prevent action startup failure caused by `AttributeError: 'str' object has no attribute 'get_secret_value'` in playbook executions

## [0.3.0] - 2026-08-27

### Added

- Add a structured `results` schema for `Get a message` action (`GetMessageResults`) to expose key message fields for playbook variable mapping
- Add a structured `results` schema for `Update a message` action (`UpdateMessageResults`) to expose key message fields for post-update chaining
- Add fixture-driven mapping tests to validate `Message-ID` and `NetworkMessageId` usage in `search_messages` and `resolve_message`
- Add a linear chaining test (`resolve -> get -> update -> forward`) to validate `graph_message_id` and `target_message_id` propagation

### Changed

- Enrich `results` payload from message actions:
  - `Delete a message`: expose minimal observability outputs `action`, `status`, and `target_message_id`
  - `Forward a message`: expose minimal observability outputs `action`, `status`, and `target_message_id`
  - `Get a message`: expose structured message fields and `graph_message_id` alias (equal to `id`)
  - `Resolve a message`: expose `graph_message_id`, `selected_message`, `selected_index`, `messages`, and `total_results`
  - `Search messages`: expose `value` candidates for downstream filtering/inspection
  - `Send a message`: expose minimal observability outputs `action`, `status`, and `target_message_id`
  - `Update a message`: expose structured message fields and `graph_message_id` alias (equal to `id`)
- Harmonize action JSON argument metadata across message actions (`description`, identifier wording, and mailbox user field wording)
- Harmonize the `user` argument type metadata in `send_message` with the other actions (`string` without `email` format)
- Harmonize `target_message_id` result wording across `forward_message`, `send_message`, and `delete_a_message`
- Migrate Poetry development dependencies from deprecated `[tool.poetry.dev-dependencies]` to `[tool.poetry.group.dev.dependencies]`
- Configure Poetry to use an in-project virtual environment (`.venv`) to isolate project dependencies from the global environment
- Refresh dependency lock file with a full lock regeneration (`poetry lock --regenerate`)

### Fixed

- Align send/update runtime validation and schema constraints (required fields, bounded `top`, and at-least-one update field guard)
- Enable action-to-action chaining for message remediation flows by exposing `graph_message_id` and candidate search outputs
- Improve resilience of `email_local_id` message lookup with fallback behavior when Graph returns `InefficientFilter` or empty filtered results

## [0.2.0] - 2026-08-25

### Added

- Added a `Search messages` action to search messages by Internet Message-ID or NetworkMessageId
- Added a `Resolve a message` action to select a unique Graph item ID from search candidates

### Changed

- Migrate argument and configuration models to Pydantic v2

### Fixed

- Increase automated test coverage to 100%
- Added a fallback lookup for `email_local_id` queries in search/resolve actions when Graph returns `InefficientFilter` or no results

## [0.1.2] - 2025-09-22

### Added

- Added action to send emails

## [0.1.1] - 2025-02-07

### Changed

- Improved error logging
