# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2026-11-03 - 1.0.0

### Added
- Initial release.
- Sync trigger that imports the Nextron Valhalla Sigma feed into the Sekoia
  Rules Catalog on a schedule: rules are created on first sight and updated
  in place afterwards, keeping each rule's `enabled` state.
- Filters `min_sigma_level` and `min_sigma_status`; `enabled` for newly
  created rules.
- Sigma → ECS field conversion per `logsource.product`, verified against
  Sekoia's Windows parser. Rules with unmappable or colliding fields are
  skipped and counted instead of being pushed.
- Every rule carries the tags `nextron-valhalla`, `uuid-<valhalla_id>` and
  `status-<sigma status>`. A catalog scan at the start of each sync rebuilds
  the Valhalla → Sekoia mapping from these tags, so a new trigger
  configuration doesn't create duplicates.
- `preserve_rule_names`: rules matched by name or tag are not updated.
- `disable_removed`: disables rules that left the feed or fell below the
  thresholds, through the dedicated disable endpoint. Skipped on an empty
  feed, a feed that shrank by more than 20% (until that persists for 3
  syncs), or a stopped run. Rules it disabled are re-enabled once they are
  back in the feed; rules disabled by the user are never touched.
- Optional `community_uuid` module setting for keys that see several
  communities.
- ATT&CK techniques linked as `related_object_refs` via the light
  intelligence objects endpoint; skipped after one warning if the key may
  not read it.
- Startup check that the alert-type UUIDs used by the mapping exist.
- `valhalla-sigma-catalog-sync` summary event with per-run counters.
