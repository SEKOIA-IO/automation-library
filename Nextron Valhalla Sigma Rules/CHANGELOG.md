# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2026-10-30 - 1.2.0

### Added
- Optional `community_uuid` module setting: scopes the catalog scan and is
  sent on every create/update. Without it the sync aborts if imported rules
  exist in more than one community.
- `disable_skipped_reason` on the summary event.
- `related_object_refs` from ATT&CK technique tags (`attack.tXXXX`), resolved
  once per technique via the intelligence API. If the API key may not read
  intelligence objects, linking is switched off after one warning.
- Sigma `references` are appended to the rule description.
- Sigma `status` as a tag: `status-<status>`.
- Startup check that the hard-coded alert-type UUIDs exist on the tenant.
- Field descriptions explain where to find the community UUID.

### Changed
- The catalog scan lists rules with the server-side `match[tag_name]` filter
  and provides the server state for the whole sync: the per-rule GET is gone.
  A failing scan aborts the run instead of continuing on a partial map.
- A mapped rule missing from the scan is re-created; a 403 is always a
  failure, never "rule deleted" (AU202 handling removed).
- Duplicate `uuid-*` markers resolve to the rule already in the local map.
- Disable pass uses `PUT /rules/{uuid}/disabled`; `to_disable` only counts
  rules that are still enabled. It is skipped when the feed is empty, shrank
  by more than 20% (until that persists for 3 syncs), or the run was stopped.
  Rules whose YAML failed to parse are never disabled.
- A missing or malformed Valhalla `rules` list fails the run instead of being
  treated as an empty feed.
- The per-rule and disable loops check the stop event; sync errors are logged
  once.
- `preserve_rule_names` entries also match rule tags (e.g. `uuid-<valhalla_id>`).
- Converter: field maps chosen by `logsource.product`; Windows `event_data`
  catch-alls only apply to Windows rules; colliding target fields and
  unmappable `|fieldref` values mark a rule unmapped; `TargetImage` /
  `TargetProcessId` / `TargetProcessGUID`, signature and PE-metadata fields
  map to `action.properties.*`; `ImageLoaded` maps to `dll.path` (image load)
  or `process.executable` (driver load); `Hashes` targets depend on the
  category and mixed algorithms become an OR (list of maps); `Initiated` is
  no longer mapped; `attack.*` tags with underscores select the alert type.
- The rule payload now includes the Sigma `logsource` block.
- `effort` is a fixed value (`2`) instead of being derived from the Sigma
  status: it describes the expected analysis effort, not rule maturity.
- Python 3.14, `sekoia-automation-sdk>=1.27.0`, sibling ruff/mypy config,
  `mise.toml`, Dockerfile with the `/tmp` → `/dev/shm` symlink.
- `sekoia_base_url` must use `https://`.

### Removed
- `tests/test_lockfile.py`.
- `"format": "password"` on the API key fields: Sekoia's account form doesn't
  use it (the 1.1.0 entry claiming masked input was wrong). The keys are
  stored as secrets and masked once the account is saved.

## 2026-10-13 - 1.1.0

### Added
- `disable_removed` sync-trigger argument (default `false`, dry-run) that
  disables rules dropped from the Valhalla feed or newly below the
  configured severity/status thresholds. Server-side body is preserved
  on disable — only `enabled` flips to false. Dry-run emits `to_disable`;
  live mode also emits `newly_disabled`, `already_disabled`,
  `already_gone`, `disable_failed`. First disable-pass failure is logged
  with full diagnostic context so repeated failures don't fail silently.
- `preserve_rule_names` sync-trigger argument (list of strings, empty by
  default). Operators copy the exact name of a rule from the Sekoia Rules
  Catalog UI into this list; subsequent syncs skip the PUT for every rule
  whose current name matches an entry (counted under the new `preserved`
  field on the summary event). Match is case-sensitive; surrounding
  whitespace is tolerated. The `disable_removed` pass still runs on
  preserved rules — content stays intact, only `enabled` can flip.
- Per-rule marker tag `uuid-<valhalla_id>` on every POST and PUT, plus a
  catalog scan at the start of every sync that rebuilds the local
  valhalla_id → sekoia_uuid id-map from the server's own tags. Makes the
  Sekoia catalog authoritative instead of the trigger's local JSON file,
  so a fresh trigger instance (new playbook, recreated trigger, wiped
  data volume) no longer POSTs duplicates for rules the tenant already
  has. New summary-event counters: `server_marker_count`,
  `duplicate_markers`, `local_overridden`. Duplicate `uuid-*` tags on
  more than one catalog rule are logged with both UUIDs so the operator
  can delete the leftover in the Sekoia UI.
- `SekoiaClient.get_rule(uuid)` helper.
- `ruff` and `mypy` to the dev dependency group.
- "Known limitations" section in README covering the `Hashes` transform's
  one-key rewrite, the multi-algo AND/OR approximation, and the
  `disable_removed` opt-in for stale rules.

### Changed
- API key fields (`valhalla_api_key`, `sekoia_api_key`) now carry
  `"format": "password"` in the module manifest so Sekoia's config UI
  renders them as masked input instead of clear text. The existing
  `configuration.secrets` list still handles runtime masking.
- Sync-trigger default thresholds raised: `min_sigma_level` default is
  now `medium` (was `informational`) and `min_sigma_status` default is
  now `stable` (was `experimental`). New playbook triggers start out
  importing a conservative, production-grade subset; operators who want
  the full feed can still broaden the thresholds in the UI. Existing
  playbooks keep whatever thresholds they already saved — defaults only
  bite on brand-new trigger instances.
- Sync trigger now observes the SDK stop event. Replaced
  `BlockingScheduler.start()` with a `while self.running:
  self._stop_event.wait(frequency)` loop and dropped the `APScheduler`
  runtime dependency.
- PUT in `update_rule` is preceded by a GET; the server's current
  `enabled` is re-sent so a rule a user disabled in the catalog stays
  disabled across syncs. `self._enabled` is only authoritative on POST
  (initial creation) and the create-after-fallback path.
- Only HTTP 404 (and HTTP 403 with Sekoia error code `AU202`) is treated
  as "rule missing server-side". Other 403 responses now surface as
  `SekoiaAPIError` so a permission/scope problem no longer looks like a
  deleted rule.
- `allowed_methods` on the retry adapter no longer includes POST: a
  read-timeout on rule creation cannot duplicate a rule.
- Invalid `min_sigma_level` or `min_sigma_status` config now raises a
  descriptive `ValueError` instead of a bare `KeyError`.
- `trigger_sync_sigma_rules_catalog.json` `results.properties` now
  declares every field the trigger emits, including the new `preserved`,
  `server_marker_count`, `duplicate_markers`, `local_overridden`, and
  disable-pass counters.
- Build/dev tooling migrated from poetry + black + isort to uv + ruff +
  mypy. `poetry.lock` removed. Coverage gate raised from 5% to 85%.
- Upgrading from 1.0.x: rules clobbered to `enabled=false` by an earlier
  version are not re-enabled retroactively — 1.1.0 only stops clobbering
  going forward. Operators must re-enable such rules in the Sekoia UI.

## 2026-08-11 - 1.0.2

### Changed
- Replaced `logo.svg` with the official Valhalla brand mark.

## 2026-08-10 - 1.0.1

### Fixed
- `convert_parsed_to_ecs` no longer mutates the caller's parsed rule dict.
  A shallow copy is taken before the ECS-converted `detection` block is
  written, so callers can safely reuse the original Sigma structure.

## 2026-07-29 - 1.0.0

### Added
- Initial release.
