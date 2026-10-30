# Nextron Valhalla Sigma Rules

Sekoia automation module that syncs the [Nextron Valhalla](https://valhalla.nextron-systems.com) Sigma rule feed into the [Sekoia](https://www.sekoia.io) Rules Catalog. Rules are pulled on a schedule, field names are rewritten from Sigma conventions to the ECS fields Sekoia's parsers emit, and each rule is created on first sight and updated in place on later syncs.

## Why use it

Sekoia's Rules Catalog does not ship a commercial Sigma feed as a first-party source. Valhalla is Nextron's catalog of Sigma and YARA rules. This integration feeds the Sigma half of it into Sekoia, where the rules run in the detection engine next to native Sekoia content — no hand-authoring, no importing rules one at a time.

Rules whose fields can't be mapped to an ECS field Sekoia actually emits are skipped (and counted) rather than pushed in a state where they would never match.

## Prerequisites

- Sekoia workspace with API access. Note your region — `https://api.sekoia.io` (FRA1) is the default; FRA2 / MCO1 / UAE1 use `https://app.<region>.sekoia.io/api`.
- Sekoia API key with the permissions *Manage rules and alert filters*, *View Rules Catalog* and *Manage rule settings* (Settings → Workspace → API Keys). Optional: read access to the intelligence (CTI) objects lets the sync link rules to their ATT&CK techniques; without it the sync logs one warning and skips the linking.
- Valhalla API key from [valhalla.nextron-systems.com](https://valhalla.nextron-systems.com). The public demo key `1111…` (sixty-four ones) is the built-in default and grants the community feed.

## How to use

1. In Sekoia, go to **Configure → Integrations**, search for **Valhalla**, and install it.
2. **Configure → Playbooks → + New playbook**. Start from scratch, then pick the **Sync Valhalla Sigma rules into Sekoia Rules Catalog** trigger.
3. Create an account for the trigger with your Valhalla API key, Sekoia API key and Sekoia base URL (and `community_uuid` if your key sees several communities).
4. Set the trigger arguments (see below). Defaults import `medium`+ / `stable` rules, disabled.
5. Save and turn the playbook on. The first sync runs immediately; imported rules appear in **Detect → Rules Catalog**, tagged `nextron-valhalla`.

## How a sync works

1. Fetch the Valhalla feed. A malformed response fails the run (it is never treated as an empty feed).
2. List every catalog rule tagged `nextron-valhalla` (one paginated scan, scoped to `community_uuid` if set). Each synced rule also carries a `uuid-<valhalla_id>` tag, so the scan rebuilds the Valhalla → Sekoia mapping from the catalog itself — a new playbook or a re-created trigger picks up existing rules instead of creating duplicates. If the scan fails, the run aborts.
3. Keep rules that meet `min_sigma_level` / `min_sigma_status` and convert them to ECS.
4. Create rules that aren't in the catalog yet (with `enabled` as configured); update the others in place, keeping each rule's current `enabled` state. Rules listed in `preserve_rule_names` are not updated.
5. Disable pass (`disable_removed`): rules that left the feed or fell below the thresholds are disabled through the dedicated disable endpoint — never deleted.
6. Emit a `valhalla-sigma-catalog-sync` summary event.

## Sync trigger arguments

| Argument | Default | Description |
|---|---|---|
| `frequency` | `86400` | Seconds between syncs (minimum `3600`). |
| `enabled` | `false` | Whether newly created rules are enabled. Existing rules keep their current state. |
| `min_sigma_level` | `medium` | Minimum Sigma `level` (`informational` … `critical`). Rules without a level are skipped. |
| `min_sigma_status` | `stable` | Minimum Sigma `status` (`experimental` < `test` < `stable`). `deprecated` / `unsupported` are never imported. |
| `disable_removed` | `false` | Disable rules that left the feed or fell below the thresholds. `false` is a dry-run that only counts them (`to_disable`). |
| `preserve_rule_names` | `[]` | Rules that are never updated. An entry matches the rule's name in the catalog **or** one of its tags — use `uuid-<valhalla_id>` to target a single rule, since names aren't unique. |

## Summary event

| Field | Meaning |
|---|---|
| `created` / `updated` / `preserved` / `failed` | Per-rule outcome of this run. |
| `skipped_unmapped` / `skipped_filter` / `total_rules` | Rules not convertible, below the thresholds, and the feed size. |
| `top_unmapped` | The five most frequent reasons rules were not convertible. |
| `server_marker_count` | Catalog rules recognised through their `uuid-*` tag. |
| `duplicate_markers` | Extra catalog rules carrying an already-seen `uuid-*` tag (see logs; delete the copies). |
| `local_overridden` | Local mapping entries corrected from the catalog. |
| `to_disable` / `newly_disabled` / `already_disabled` / `already_gone` / `disable_failed` | Disable pass counters (`to_disable` only counts rules that are still enabled). |
| `disable_skipped_reason` | `""`, or why the disable pass did not run: `empty_feed`, `feed_shrank`, `interrupted`. |

## Module configuration

| Field | Secret | Description |
|---|---|---|
| `valhalla_api_key` | yes | Valhalla API key. Defaults to the public demo key. Masked once the account is saved. |
| `sekoia_api_key` | yes | Sekoia bearer token. Masked once the account is saved. Required. |
| `sekoia_base_url` | no | Sekoia API base URL (must be `https://`). Defaults to `https://api.sekoia.io` (FRA1). |
| `community_uuid` | no | Community to sync into. Only needed when the key sees several communities (MSSP): the sync then only reads and writes rules of this community. Without it, the sync aborts if imported rules exist in more than one community. To find the UUID, open the community in Sekoia, go to **Settings → General** and copy the part of the URL between `/communities/` and `/community-details`. |

The Valhalla API URL is hardcoded to `https://valhalla.nextron-systems.com`.

## Behaviour to be aware of

- **Customisations of synced rules are overwritten.** Each update replaces the rule with the Valhalla version (only `enabled` is kept). This includes settings made in the Sekoia UI such as entities, assets, parameters or event fields. To keep a customised rule, add it to `preserve_rule_names`; it then no longer receives Valhalla updates, but `disable_removed` still applies to it.
- **Disable-pass safety.** The disable pass is skipped when the feed is empty, or when it shrank by more than 20% compared to the last accepted size (e.g. a truncated response, or the key switched to the demo key). A smaller feed is only accepted once it persisted for 3 consecutive syncs. Rules whose YAML failed to parse in a run are never disabled in that run.
- **Use `disable_removed=true` on one trigger per community only.** The disable pass acts on every rule the integration imported into the community. A second trigger with stricter thresholds would disable rules imported by the first one.
- **Concurrent first syncs can duplicate rules.** Two triggers starting at the same moment both see an empty catalog and both create the rules. Later syncs log the copies under `duplicate_markers`; delete them in the UI.
- **Duplicating an imported rule copies its `uuid-*` tag.** The rule already known to the trigger keeps being updated; the copy is ignored and logged.

## Conversion notes

- Field targets are chosen per `logsource.product`: Windows rules use the SigmaHQ Windows map plus overrides verified against Sekoia's Windows parser; macOS and Zeek rules use their own maps. Windows `event_data` catch-alls (`Status`, `Path`, `Details`, …) are only applied to Windows rules.
- A rule is skipped (`skipped_unmapped`) when a field has no target, when two fields of one selection resolve to the same ECS field (`<collision:…>`), or when a `|fieldref` value names an unmappable field.
- `Hashes` values are split per algorithm into the fields the parser emits for that category (`process.hash.*`, `dll.hash.*` for image loads, `file.hash.*` for file-hash events; IMPHASH → `*.pe.imphash`). A list mixing algorithms becomes an OR over one map per algorithm, so an event without SHA1 still matches on MD5. Algorithms the parser never emits for the category are dropped; `|all` keeps AND semantics.
- The rule payload contains the Sigma `logsource` block and the converted `detection` block.
- The Sigma `status` is added as a tag (`status-stable`, `status-test`, `status-experimental`). Sekoia's `effort` field describes the expected analysis effort, which Sigma doesn't define, so every rule gets the same value (`2`).
- ATT&CK technique tags (`attack.t1059.001`) are linked as `related_object_refs`; tactic tags pick the alert type. Sigma `references` are appended to the description (the API's `references` field is read-only).

## Repository layout

```
main.py                                        # entry point; registers the sync trigger
manifest.json                                  # module manifest (version, config schema, secrets)
trigger_sync_sigma_rules_catalog.json          # sync trigger manifest
nextron_valhalla_sigma_rules_modules/
  client.py                                    # Valhalla HTTP client
  sekoia_client.py                             # Sekoia Rules Catalog HTTP client (pooled session + retries)
  sigma_mapper.py                              # Sigma YAML → Sekoia catalog payload conversion
  ecs_field_maps.py                            # Sigma field name → ECS field name tables
  models.py                                    # module configuration model
  triggers/
    sync_sigma_rules_catalog.py
tests/                                         # pytest suite
```

## Development

```
uv sync                                        # install deps (Python 3.14)
uv run ruff check . && uv run ruff format --check . && uv run mypy .
uv run pytest
```

The `Dockerfile` builds the runtime image Sekoia executes. Bump `version` in `manifest.json` on every push-worthy change — Sekoia's importer rejects same-version reimports.
