# Nextron Valhalla Sigma Rules

Sekoia automation module that syncs the [Nextron Valhalla](https://valhalla.nextron-systems.com) Sigma rule feed into the [Sekoia](https://www.sekoia.io) Rules Catalog. Rules are pulled on a schedule, field names are rewritten from Sigma conventions to the ECS fields Sekoia's parsers emit, and each rule is created on first sight and updated in place on later syncs.

## Why use it

Sekoia's Rules Catalog does not ship a commercial Sigma feed as a first-party source. Valhalla is Nextron's catalog of Sigma and YARA rules. This integration feeds the Sigma half of it into Sekoia, where the rules run in the detection engine next to native Sekoia content — no hand-authoring, no importing rules one at a time.

Rules whose fields can't be mapped to an ECS field Sekoia actually emits are skipped (and counted) rather than pushed in a state where they would never match.

## Prerequisites

- Sekoia workspace with API access. Note your region — `https://api.sekoia.io` (FRA1) is the default; FRA2 / MCO1 / UAE1 use `https://app.<region>.sekoia.io/api`.
- Sekoia API key with the permissions *Manage rules and alert filters* and *View Rules Catalog* (Settings → Workspace → API Keys). Optional: *View intelligence* or *View intelligence with limited access* lets the sync link rules to their ATT&CK techniques; without it the sync logs one warning and skips the linking.
- Valhalla API key from [valhalla.nextron-systems.com](https://valhalla.nextron-systems.com). The public demo key `1111…` (sixty-four ones) is the built-in default and grants the community feed.

## How to use

1. In Sekoia, go to **Configure → Integrations**, search for **Valhalla**, and install it.
2. **Configure → Playbooks → + New playbook**. Start from scratch, then pick the **Sync Valhalla Sigma rules into Sekoia Rules Catalog** trigger.
3. Create an account for the trigger with your Valhalla API key, Sekoia API key and Sekoia base URL (and `community_uuid` if your key sees several communities).
4. Set the trigger arguments (see below). Defaults import `medium`+ / `experimental`+ rules, disabled.
5. Save and turn the playbook on. The first sync runs immediately; imported rules appear in **Detect → Rules Catalog**, tagged `nextron-valhalla`.

## How a sync works

1. Fetch the Valhalla feed; transient errors (timeouts, HTTP 429/5xx) are retried. A malformed response fails the run (it is never treated as an empty feed). After a failed run the trigger tries again after 15 minutes, then after 30 more minutes; at most 2 such early retries run within 24 hours, after that it waits the normal `frequency`.
2. List every catalog rule tagged `nextron-valhalla` (one paginated scan, scoped to `community_uuid` if set). Each synced rule also carries a `uuid-<valhalla_id>` tag, so the scan rebuilds the Valhalla → Sekoia mapping from the catalog itself — a new playbook or a re-created trigger picks up existing rules instead of creating duplicates. If the scan fails, the run aborts. A known rule missing from the scan is looked up directly and only re-created if Sekoia answers 404, so a listing that misses a rule never duplicates it.
3. Keep rules that meet `min_sigma_level` / `min_sigma_status` and convert them to ECS. A rule with unexpected field types is skipped and counted under `<malformed>` in `top_unmapped`; it doesn't stop the run.
4. Create rules that aren't in the catalog yet (with `enabled` as configured); update the others in place. An update replaces the Valhalla content (name, description, detection, severity, tags) and keeps the rule's `enabled` state and the settings made in Sekoia (entities, assets, parameters, event fields, similarity strategy, validity, threats linked by the user). Rules listed in `preserve_rule_names` are not updated. Imported rules whose new version can't be converted keep their catalog version and are counted under `stale`.
5. Re-enable: rules carrying the `valhalla-auto-disabled` tag are enabled again (and the tag removed) once they are back in the feed and meet the thresholds — in the same update for regular rules, as they are for preserved or `stale` ones. Rules you disabled yourself carry no tag and are never touched.
6. Disable pass (`disable_removed`): rules that left the feed or fell below the thresholds are disabled and get the `valhalla-auto-disabled` tag — never deleted. The disable sends the catalog rule back unchanged apart from `enabled` and the tag.
7. Emit a `valhalla-sigma-catalog-sync` summary event.

## Sync trigger arguments

| Argument | Default | Description |
|---|---|---|
| `frequency` | `86400` | Seconds between syncs (minimum `3600`). |
| `enabled` | `false` | Whether newly created rules are enabled. Existing rules keep their current state. |
| `min_sigma_level` | `medium` | Minimum Sigma `level` (`informational` … `critical`). Rules without a level are skipped. |
| `min_sigma_status` | `experimental` | Minimum Sigma `status` (`experimental` < `test` < `stable`). `deprecated` / `unsupported` are never imported. |
| `disable_removed` | `false` | Disable rules that left the feed or fell below the thresholds and tag them `valhalla-auto-disabled`; any trigger configuration re-enables them if they come back. `false` is a dry-run that only counts them (`to_disable`). |
| `preserve_rule_names` | `""` | Rules whose content is never updated. Text field: one entry per line, or entries separated by `;`. An entry matches the rule's name in the catalog **or** one of its tags — use `uuid-<valhalla_id>` to target a single rule, since names aren't unique. |

## Summary event

| Field | Meaning |
|---|---|
| `created` / `updated` / `preserved` / `failed` | Per-rule outcome of this run. |
| `skipped_unmapped` / `skipped_filter` / `total_rules` | Rules not convertible, below the thresholds, and the feed size. |
| `stale` | Imported rules kept at their catalog version because the new version couldn't be converted (the first five names are logged). |
| `top_unmapped` | The five most frequent reasons rules were not convertible. |
| `server_marker_count` | Catalog rules recognised through their `uuid-*` tag. |
| `duplicate_markers` | Extra catalog rules carrying an already-seen `uuid-*` tag (see logs; delete the copies). |
| `local_overridden` | Local mapping entries corrected from the catalog. |
| `re_enabled` / `reenable_failed` | Rules switched off by an earlier disable pass that came back and were enabled again (or failed to). |
| `reenable_conflicts` | Rules this configuration re-enabled in its previous sync that another trigger disabled again (see logs). |
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

- **Settings made in Sekoia are kept, content changes are not.** Updates keep entities, assets, parameters, event fields, similarity strategy, validity, threats you linked and the `enabled` state; alert filters are separate objects and are never touched. Changes to the content (name, description, detection, severity, tags) are overwritten. To keep those, add the rule to `preserve_rule_names`; it then no longer receives Valhalla updates, but `disable_removed` still applies to it.
- **Re-enabling only covers the integration's own disables.** The disable pass tags the rules it switches off with `valhalla-auto-disabled`. Any trigger configuration re-enables tagged rules once they return and removes the tag, so the record survives a new configuration. A rule you disabled yourself has no tag and stays disabled; if you re-enable a tagged rule yourself, the tag is removed so a later manual disable stays yours.
- **Disable-pass safety.** The disable pass is skipped when the feed is empty, or when it shrank by more than 20% compared to the last accepted size (e.g. a truncated response, or the key switched to the demo key). A smaller feed is only accepted once it persisted for 3 consecutive syncs. Rules whose YAML failed to parse or that were skipped as malformed in a run are never disabled in that run.
- **Use one sync trigger per community.** The disable pass acts on every rule the integration imported into the community. A second trigger with stricter thresholds would disable rules imported by the first one, and the first would re-enable them on its next sync. The trigger that re-enables them reports this under `reenable_conflicts` with a warning.
- **Concurrent first syncs can duplicate rules.** Two triggers starting at the same moment both see an empty catalog and both create the rules. Later syncs log the copies under `duplicate_markers`; delete them in the UI.
- **Removing the `nextron-valhalla` tag doesn't detach a rule.** The trigger still knows the rule and looks it up directly; the next update puts the tag back. To stop updates, use `preserve_rule_names`.
- **Duplicating an imported rule copies its `uuid-*` tag.** The rule already known to the trigger keeps being updated; the copy is ignored and logged.

## Conversion notes

- Field targets are chosen per `logsource.product`: Windows rules use the SigmaHQ Windows map plus overrides verified against Sekoia's Windows parser; macOS and Zeek rules use their own maps. Windows `event_data` catch-alls (`Status`, `Path`, `Details`, …) are only applied to Windows rules.
- A rule is skipped (`skipped_unmapped`) when a field has no target, when two fields of one selection resolve to the same ECS field (`<collision:…>`), or when a `|fieldref` value names an unmappable field.
- `Hashes` values are split per algorithm into the fields the parser emits for that category (`process.hash.*`, `dll.hash.*` for image loads, `file.hash.*` for file-hash events; IMPHASH → `*.pe.imphash`). A list mixing algorithms becomes an OR over one map per algorithm, so an event without SHA1 still matches on MD5. Algorithms the parser never emits for the category are dropped; `|all` keeps AND semantics.
- The rule payload contains the Sigma `logsource` block and the converted `detection` block. `logsource` is informational: Sekoia's detection engine only evaluates `detection`, so it doesn't restrict which events a rule runs on.
- The Sigma `status` is added as a tag (`status-stable`, `status-test`, `status-experimental`). Sekoia's `effort` field describes the expected analysis effort, which Sigma doesn't define, so every rule gets the same value (`2`).
- ATT&CK technique tags (`attack.t1059.001`) are linked as `related_object_refs`; tactic tags pick the alert type. Sigma `references` are appended to the description (the API's `references` field is read-only).

## Repository layout

```
main.py                                        # entry point; registers the sync trigger
manifest.json                                  # module manifest (version, config schema, secrets)
trigger_sync_sigma_rules_catalog.json          # sync trigger manifest
nextron_valhalla_sigma_rules_modules/
  client.py                                    # Valhalla HTTP client (retries)
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
