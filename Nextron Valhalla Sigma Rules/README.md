# Nextron Valhalla Sigma Rules

Syncs the [Nextron Valhalla](https://valhalla.nextron-systems.com) Sigma feed into the Sekoia Rules Catalog so the rules execute in Sekoia's detection engine.

## Configuration

| Field | Required | Default | Description |
|---|---|---|---|
| `valhalla_api_key` | no | Public demo key | API key from valhalla.nextron-systems.com. The default demo key only grants the community feed; a paid key unlocks the full ruleset. |
| `sekoia_api_key` | **yes** | — | Bearer token from Sekoia (**Settings → Workspace → API Keys**). Needs write access to the Rules Catalog. |
| `sekoia_base_url` | no | `https://api.sekoia.io` | Region-specific base URL. FRA1 uses the default; for FRA2 / MCO1 / UAE1 use `https://app.<region>.sekoia.io/api`. |

Both API keys are stored as secrets.

## Trigger — Sync Sigma Rules Catalog

Docker parameter: `sync-sigma-rules-catalog`

Fetches the Valhalla Sigma feed on a fixed interval, converts each rule's `detection` block from Sigma field names to ECS, and pushes the result to `/v1/sic/conf/rules-catalog/rules`. New rules are `POST`ed; rules the integration has seen before are `PUT` in place using a persisted Valhalla-ID → Sekoia-UUID map.

### Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `frequency` | integer (seconds) | `86400` (24h) | Pull frequency. Minimum 3600. |
| `enabled` | boolean | `false` | When false, rules land in the catalog disabled and operators opt in per rule. |
| `min_sigma_level` | enum | `informational` | Minimum Sigma `level`. Rules missing `level` are always skipped. |
| `min_sigma_status` | enum | `experimental` | Minimum Sigma `status`. Rules with status `deprecated`/`unsupported` are never imported. |

### Result event

```json
{
  "created": <int>,
  "updated": <int>
}
```

## Known limitations

- **Rules with multiple `Hashes` keys in one selection block.** The sync trigger rewrites the first `Hashes` / `Hashes|<mod>` key it finds inside a selection and preserves other keys verbatim. Valhalla's current feed never emits this shape; a rule that does will land under `skipped_unmapped`.
- **Multi-algo `Hashes` lists (`[MD5=…, SHA256=…]`) become AND-across-algo keys rather than OR-over-files.** This matches the semantic for IOC rules that enumerate a fingerprint per file (one hash per algo per event), which is how Valhalla ships them. See the `_apply_hashes_transform` docstring for the exact approximation.
- **Rules dropped from the Valhalla feed are not disabled automatically.** Set the sync trigger's `disable_removed=true` to disable them (dry-run by default).
- **Hand edits in Sekoia are overwritten by the next sync by default.** To protect a rule you've tuned, copy its exact name from the Sekoia Rules Catalog UI into the sync trigger's `preserve_rule_names` list (empty by default). Subsequent syncs skip the PUT for every rule whose current name matches an entry in that list and count it under `preserved` on the summary event. Match is case-sensitive; surrounding whitespace is tolerated. `disable_removed` still fires on preserved rules — content stays intact, only `enabled` can flip. Caveat: if Nextron ever renames a rule upstream, the stale entry stops matching and the rule gets overwritten on the next sync.

## How it works

1. **Fetch** — `POST https://valhalla.nextron-systems.com/api/v1/getsigma` with the Valhalla API key returns the Sigma feed as JSON.
2. **Parse & filter** — each rule's YAML `content` is parsed; rules failing the `min_sigma_level` / `min_sigma_status` filter are dropped.
3. **ECS conversion** — the `detection:` block is walked and every Sigma field name is rewritten to its ECS equivalent (falling back to a context-aware lookup for fields whose ECS target depends on `logsource.category`). Rules with unmapped fields are skipped.
4. **Push** — a Sekoia Rules Catalog body is built from the parsed rule (name, description, severity, effort, `alert_type_uuid` derived from MITRE tactic tags, tags including the `nextron-valhalla` marker) and either POSTed (first seen) or PUT (subsequent syncs).
5. **State** — Sekoia UUIDs are persisted in `valhalla-sigma-catalog-uuid-map.json` under the trigger's data path so repeat syncs don't create duplicates.

## Development

From this directory:

```bash
uv sync
uv run pytest tests/ -v
```
