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

## How it works

1. **Fetch** — `POST https://valhalla.nextron-systems.com/api/v1/getsigma` with the Valhalla API key returns the Sigma feed as JSON.
2. **Parse & filter** — each rule's YAML `content` is parsed; rules failing the `min_sigma_level` / `min_sigma_status` filter are dropped.
3. **ECS conversion** — the `detection:` block is walked and every Sigma field name is rewritten to its ECS equivalent (falling back to a context-aware lookup for fields whose ECS target depends on `logsource.category`). Rules with unmapped fields are skipped.
4. **Push** — a Sekoia Rules Catalog body is built from the parsed rule (name, description, severity, effort, `alert_type_uuid` derived from MITRE tactic tags, tags including the `nextron-valhalla` marker) and either POSTed (first seen) or PUT (subsequent syncs).
5. **State** — Sekoia UUIDs are persisted in `valhalla-sigma-catalog-uuid-map.json` under the trigger's data path so repeat syncs don't create duplicates.

## Development

From this directory:

```bash
poetry install
poetry run pytest tests/ -v
```

From the `automation-library/` repo root, to run the Sekoia compliance / homologation check:

```bash
poetry -C _utils run python compliance check --module "Nextron Valhalla Sigma Rules"
```
