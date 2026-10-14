# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-10-14

### Added

- Enrich action outputs:
  - action `Delete a message`:
    - `user`: The echo of the user identifier used for this action
  - action `Forward a message`:
    - `comment`: The optional comment included in the forwarded message
    - `recipients`: The recipient email addresses used by the action
    - `user`: The echo of the user identifier used for this action
  - action `Get a message`:
    - `user`: The echo of the user identifier used for this action
  - action `Search messages`:
    - `has_more`: The indicator that is true when Graph indicates additional pages may exist
    - `message_ids`: The list of Microsoft Graph message item IDs extracted from returned messages
    - `network_message_id`: The NetworkMessageId extracted from Graph extended properties when available
    - `query_type`: The identifier type used for the search
    - `query_value`: The search identifier value, or concatenated values when both identifiers are provided
    - `returned_count`: The alias of total_results for explicit count-based playbook conditions
    - `total_results`: The number of messages returned in this response
    - `user`: The echo of the user identifier used for this action, reusable in downstream playbook nodes
  - action `Send a message`:
    - `bcc`: The list of BCC recipient email addresses used by the action
    - `cc`: The list of CC recipient email addresses used by the action
    - `content_type`: The content type of the message body used by the action
    - `from`: The mailbox owner email address used in the From header
    - `importance`: The importance level of the message used by the action
    - `recipients`: The recipient email addresses used by the action
    - `save_to_sent_items`: The setting that controls whether the message is saved in Sent Items
    - `sender`: The sender email address used by the action
    - `subject`: The subject of the message used by the action
    - `user`: The echo of the user identifier used for this action
  - action `Update a message`:
    - `action`: The action technical identifier
    - `bcc`: The updated list of BCC recipient email addresses used by the action
    - `cc`: The updated list of CC recipient email addresses used by the action
    - `importance`: The importance level of the message used by the action
    - `original_from`: The original mailbox owner email address provided in the input From header
    - `original_subject`: The original subject provided in the input
    - `recipients`: The updated list of recipient email addresses used by the action
    - `sender`: The updated sender email address used by the action
    - `status`: The execution status
    - `user`: The echo of the user identifier used for this action

### Changed

- Refactor `Search messages` for identifier-resolution playbooks:
  - rename inputs to `max_messages_to_return` and `return_most_recent_first`
  - remove legacy `item_index` input to keep a list-oriented selection model
  - improve `email_local_id` fallback behavior with paginated scanning via `@odata.nextLink`
- Refactor playbook and workflow tests to use `Search messages` as the source of message selection for Foreach-based flows
- Allow `message_id` arguments to accept either a string ID or a message object containing `message_id` for `Foreach` operator compatibility
- Factorize shared action helpers in `MicrosoftGraphActionBase` for `message_id` resolution, recipient generation, and payload cleanup
- Harmonize action logging messages with a consistent descriptive style and structured key/value context

### Fixed

- Fix false-negative lookups for `email_local_id` by bounding and paginating client-side fallback scanning (`FALLBACK_PAGE_SIZE=50`, `FALLBACK_MAX_MESSAGES_SCANNED=1000`)

### Removed

- Remove action `Resolve a message` (safe since it was never deployed on FRA1 region)

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
