# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.5.1 - 2026-10-26

### Changed

- Exclude the lint dependencies from the Docker image

## [Unreleased]

## [0.5.0] - 2026-10-19

### Added

- Enrich action outputs:
  - action `Delete a message`: `user`
  - action `Forward a message`: `comment`, `recipients`, `user`
  - action `Get a message`: `user`
  - action `Search messages`: `has_more`, `messages[].network_message_id`, `message_ids`, `query_type`, `query_value`, `returned_count`, `scan_limit_reached`, `total_results`, `user`
  - action `Send a message`: `bcc`, `cc`, `content_type`, `from`, `importance`, `recipients`, `save_to_sent_items`, `sender`, `subject`, `user`
  - action `Update a message`: `action`, `bcc`, `cc`, `importance`, `recipients`, `sender`, `status`, `updated_from`, `updated_sender`, `updated_subject`, `user`

### Changed

- Refactor `Search messages` for identifier-resolution playbooks:
  - rename inputs to `max_messages_to_return` and `return_most_recent_first`
  - remove legacy `item_index`
  - add paginated fallback for `email_local_id` via `@odata.nextLink`
- Update playbook/workflow tests to use `Search messages` for Foreach-based selection
- For actions `Get a message`, `Delete a message`, `Forward a message`, and `Update a message`, accept `message_id` as either a raw string or a `Foreach` item object containing `message_id` (for example `{{ node.x.default.value }}`), so each search result can be chained directly
- Extract shared helpers in `MicrosoftGraphActionBase` (`message_id` resolution, recipient building, payload cleanup)
- Harmonize action logs with consistent key/value messages
- Upgrade `sekoia-automation-sdk` to `1.27.0`
- Remove the logo background
- Raise the minimum supported Python version to `3.14`
- Migrate project dependency management from Poetry to uv (`pyproject.toml` PEP 621 + `uv.lock`)

### Fixed

- Fix `email_local_id` false negatives with bounded, paginated fallback (`FALLBACK_PAGE_SIZE=50`, `FALLBACK_MAX_MESSAGES_SCANNED=1000`)
- Enforce the 1,000-item scan cap by slicing each page to the remaining budget
- Normalize empty optional identifiers before fallback filtering
- Preserve Microsoft Graph `sender` in `Update a message` results (do not overwrite from input)
- Sort `results.properties` keys alphabetically across action descriptors

### Removed

- Remove action `Resolve a message` (never deployed in FRA1)

## [0.4.0] - 2026-08-28

### Changed

- Normalize `results` payload field names to `snake_case` for `search_messages`, `resolve_message`, `get_message`, and `update_message`
- Rename resolved Graph identifier field from `graph_message_id` to `message_id` in action `results`
- Rename `search_messages` top-level output from `value` to `messages`
- Rename message fields in `results` from Graph-style camelCase to snake_case (`internet_message_id`, `received_date_time`, `to_recipients`, `body_preview`)
- Document lint and test commands in README and align lint tooling configuration for local validation

### Fixed

- Remove redundant top-level identifier duplication in message action `results` by exposing a single canonical `message_id` field
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

- Add a `Search messages` action to search messages by Internet Message-ID or NetworkMessageId
- Add a `Resolve a message` action to select a unique Graph item ID from search candidates

### Changed

- Migrate argument and configuration models to Pydantic v2

### Fixed

- Increase automated test coverage to 100%
- Add a fallback lookup for `email_local_id` queries in search/resolve actions when Graph returns `InefficientFilter` or no results

## [0.1.2] - 2025-09-22

### Added

- Add action to send emails

## [0.1.1] - 2025-02-07

### Changed

- Improve error logging
