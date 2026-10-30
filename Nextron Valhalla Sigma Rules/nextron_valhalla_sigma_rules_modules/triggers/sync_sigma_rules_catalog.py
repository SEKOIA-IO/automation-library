import re
from collections import Counter
from dataclasses import dataclass, field
from typing import cast

import yaml
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from nextron_valhalla_sigma_rules_modules.client import ValhallaClient
from nextron_valhalla_sigma_rules_modules.models import NextronValhallaSigmaRulesModuleConfiguration
from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaAPIError,
    SekoiaClient,
    SekoiaRuleNotFoundError,
    rule_tag_names,
)
from nextron_valhalla_sigma_rules_modules.sigma_mapper import (
    DEFAULT_ALERT_UUID,
    MARKER_TAG,
    SEVERITY_MAP,
    STATUS_RANK,
    TAG_ALERT_UUID_MAP,
    UUID_TAG_PREFIX,
    convert_parsed_to_ecs,
    sigma_rule_to_catalog_payload,
)

UUID_MAP_FILE = "valhalla-sigma-catalog-uuid-map.json"
FEED_STATE_FILE = "valhalla-sigma-feed-state.json"
TOP_UNMAPPED_REPORT = 5
DEFAULT_MIN_LEVEL = "medium"
DEFAULT_MIN_STATUS = "stable"

# Disable-pass safety (B2): a feed that shrank by more than this ratio
# against the last accepted size is treated as suspicious (truncated
# response, key switched to the demo key, …) and the disable pass is
# skipped. If the smaller size persists for FEED_SHRINK_CONFIRM_RUNS
# consecutive syncs it is accepted as the new normal.
MAX_FEED_SHRINK_RATIO = 0.2
FEED_SHRINK_CONFIRM_RUNS = 3

_ATTACK_TECHNIQUE_TAG = re.compile(r"^attack\.(t\d{4}(?:\.\d{3})?)$", re.IGNORECASE)


def _normalize_names(names) -> frozenset[str]:
    """Build the preserve matcher set from the trigger config.

    Non-list input → empty set (disables the check). Whitespace is
    stripped and empty entries are dropped so copy-paste from the Sekoia
    UI tolerates stray spaces or blank lines.
    """
    if not isinstance(names, list):
        return frozenset()
    return frozenset(n.strip() for n in names if isinstance(n, str) and n.strip())


def _extract_valhalla_id(server_rule: dict) -> str | None:
    """Return the Valhalla UUID encoded in the rule's ``uuid-*`` tag, or
    ``None`` if there is none."""
    for name in sorted(rule_tag_names(server_rule)):
        if name.startswith(UUID_TAG_PREFIX):
            return name[len(UUID_TAG_PREFIX) :]
    return None


def _attack_technique_ids(tags) -> list[str]:
    """``attack.t1059.001`` → ``T1059.001`` for every technique tag, in order."""
    out: list[str] = []
    for tag in tags or []:
        if isinstance(tag, str):
            m = _ATTACK_TECHNIQUE_TAG.match(tag.strip())
            if m and m.group(1).upper() not in out:
                out.append(m.group(1).upper())
    return out


@dataclass
class CatalogScan:
    """Snapshot of every catalog rule this integration owns, taken once at
    the start of a sync. ``rules_by_uuid`` replaces the per-rule GET."""

    rules_by_uuid: dict[str, dict] = field(default_factory=dict)
    server_marker_count: int = 0
    duplicate_markers: int = 0
    local_overridden: int = 0

    def stats(self) -> dict:
        return {
            "server_marker_count": self.server_marker_count,
            "duplicate_markers": self.duplicate_markers,
            "local_overridden": self.local_overridden,
        }


class SyncSigmaRulesCatalog(Trigger):
    def run(self) -> None:
        # Trigger arguments arrive as a dict; the module configuration is
        # validated into ``NextronValhallaSigmaRulesModuleConfiguration``.
        args: dict = self.configuration if isinstance(self.configuration, dict) else {}
        min_level = args.get("min_sigma_level", DEFAULT_MIN_LEVEL)
        min_status = args.get("min_sigma_status", DEFAULT_MIN_STATUS)
        if min_level not in SEVERITY_MAP:
            raise ValueError(f"min_sigma_level={min_level!r} is not one of {sorted(SEVERITY_MAP)}")
        if min_status not in STATUS_RANK:
            raise ValueError(f"min_sigma_status={min_status!r} is not one of {sorted(STATUS_RANK)}")
        self._min_severity = SEVERITY_MAP[min_level]
        self._min_status_rank = STATUS_RANK[min_status]
        self._enabled = args.get("enabled", False)
        self._disable_removed = bool(args.get("disable_removed", False))
        self._preserve_rule_names = _normalize_names(args.get("preserve_rule_names", []))
        frequency = args.get("frequency", 86400)

        cfg = cast(NextronValhallaSigmaRulesModuleConfiguration, self.module.configuration)
        self._valhalla = ValhallaClient(cfg.valhalla_api_key)
        self._sekoia = SekoiaClient(cfg.sekoia_base_url, cfg.sekoia_api_key)
        self._community_uuid = cfg.community_uuid or None
        self._validate_alert_types()

        # SDK pattern: the first iteration runs immediately, then wait on
        # the stop-event so SIGINT/SIGTERM from Sekoia's playbook runner
        # unblocks us within the same tick instead of hanging on the next
        # sleep interval.
        while self.running:
            try:
                self._sync_once()
            except Exception as exc:
                self.log_exception(exc, message="Failed to sync Valhalla Sigma to Rules Catalog")
            self._stop_event.wait(frequency)

    # ------------------------------------------------------------------
    # Startup checks
    # ------------------------------------------------------------------

    def _validate_alert_types(self) -> None:
        """Fail fast if the hard-coded alert-type UUIDs don't exist on this
        tenant — otherwise every create would be rejected with a 400."""
        required = {DEFAULT_ALERT_UUID} | {uuid for _, uuid in TAG_ALERT_UUID_MAP}
        try:
            known = {t.get("uuid") for t in self._sekoia.list_alert_types()}
        except Exception as exc:
            self.log(
                f"Could not list alert types to validate them ({exc}); continuing without the check.",
                level="warning",
            )
            return
        missing = sorted(required - known)
        if missing:
            raise ValueError(
                f"Alert type UUID(s) {missing} used by the Sigma→catalog mapping do not exist on this "
                f"Sekoia tenant. Rules cannot be created until they are available."
            )

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def _rule_passes_filter(self, parsed: dict) -> bool:
        """Return True when the rule's Sigma ``level`` and ``status``
        both exist and meet the configured minimums. Rules missing
        either field are always filtered out."""
        level = (parsed.get("level") or "").lower()
        status = (parsed.get("status") or "").lower()
        level_score = SEVERITY_MAP.get(level)
        status_rank = STATUS_RANK.get(status)
        if level_score is None or status_rank is None:
            return False
        return level_score >= self._min_severity and status_rank >= self._min_status_rank

    def _is_preserved(self, server_rule: dict) -> bool:
        """An entry of ``preserve_rule_names`` matches the server rule's name
        or any of its tags (e.g. ``uuid-<valhalla_id>``)."""
        if not self._preserve_rule_names:
            return False
        name = (server_rule.get("name") or "").strip()
        if name and name in self._preserve_rule_names:
            return True
        return bool(rule_tag_names(server_rule) & self._preserve_rule_names)

    def _sync_once(self) -> None:
        # Errors (feed fetch, catalog scan) propagate to ``run()``, which logs
        # them once. A scan failure aborts the sync: continuing on a partial
        # map would create duplicates and mis-identify stale rules.
        rules = self._valhalla.get_sigma_feed()
        created = 0
        updated = 0
        preserved = 0
        failed = 0
        skipped_unmapped = 0
        filtered_out = 0
        interrupted = False
        unmapped_field_counter: Counter[str] = Counter()
        first_failure_logged = False
        seen_in_feed: set[str] = set()
        passed_filter: set[str] = set()
        unparsed: set[str] = set()
        with PersistentJSON(UUID_MAP_FILE, self.data_path) as id_map:
            scan = self._scan_catalog(id_map)
            for rule in rules:
                if not self.running:
                    interrupted = True
                    break
                valhalla_id = rule.get("id")
                if not valhalla_id:
                    continue
                seen_in_feed.add(valhalla_id)

                content = rule.get("content", "")
                try:
                    parsed_rule = yaml.safe_load(content)
                except yaml.YAMLError:
                    parsed_rule = None
                if not isinstance(parsed_rule, dict):
                    unparsed.add(valhalla_id)
                    skipped_unmapped += 1
                    unmapped_field_counter["<yaml-parse-error>"] += 1
                    continue

                if not self._rule_passes_filter(parsed_rule):
                    filtered_out += 1
                    continue
                passed_filter.add(valhalla_id)

                parsed, unmapped = convert_parsed_to_ecs(parsed_rule)
                if parsed is None:
                    skipped_unmapped += 1
                    for f in unmapped:
                        unmapped_field_counter[f] += 1
                    continue

                body = sigma_rule_to_catalog_payload(rule, parsed, self._enabled)
                if self._community_uuid:
                    body["community_uuid"] = self._community_uuid
                refs = self._attack_refs(parsed.get("tags"))
                if refs:
                    body["related_object_refs"] = refs
                try:
                    sekoia_uuid = id_map.get(valhalla_id)
                    server_rule = scan.rules_by_uuid.get(sekoia_uuid) if sekoia_uuid else None
                    if server_rule is None:
                        # Never synced, or the mapped rule is no longer in the
                        # catalog (deleted in Sekoia) — create it.
                        if sekoia_uuid:
                            del id_map[valhalla_id]
                        body["enabled"] = self._enabled
                        id_map[valhalla_id] = self._sekoia.create_rule(body)
                        created += 1
                    elif self._is_preserved(server_rule):
                        # Operator listed this rule in ``preserve_rule_names``
                        # to protect their hand-edits. ``disable_removed`` still
                        # applies independently.
                        preserved += 1
                    else:
                        # Keep the user's per-rule ``enabled`` choice.
                        body["enabled"] = bool(server_rule.get("enabled", self._enabled))
                        try:
                            self._sekoia.update_rule(sekoia_uuid, body)
                            updated += 1
                        except SekoiaRuleNotFoundError:
                            # Deleted between the scan and now.
                            del id_map[valhalla_id]
                            body["enabled"] = self._enabled
                            id_map[valhalla_id] = self._sekoia.create_rule(body)
                            created += 1
                except Exception as exc:
                    failed += 1
                    # Log the first failure loudly with the full body so the
                    # user can see exactly what shape the API rejected.
                    if not first_failure_logged:
                        self.log(
                            f"First rule sync failure (subsequent failures "
                            f"counted but not individually logged). "
                            f"Rule id={valhalla_id}, name={body.get('name')!r}. "
                            f"Sent body: {body}. Error: {exc}",
                            level="error",
                        )
                        first_failure_logged = True

            skip_reason = "interrupted" if interrupted else self._check_feed_size(len(rules))
            if skip_reason:
                disable_counts = self._skipped_disable_counts(skip_reason, len(rules))
            else:
                disable_counts = self._disable_removed_rules(id_map, scan, seen_in_feed, passed_filter, unparsed)

        top_unmapped = dict(unmapped_field_counter.most_common(TOP_UNMAPPED_REPORT))
        self.log(
            f"Catalog sync: created={created} updated={updated} "
            f"preserved={preserved} failed={failed} "
            f"skipped_unmapped={skipped_unmapped} "
            f"filtered_out={filtered_out} total_rules={len(rules)} "
            f"scan={scan.stats()} "
            f"disable_counts={disable_counts} "
            f"top_unmapped={top_unmapped}",
            level="info",
        )
        self.send_event(
            event_name="valhalla-sigma-catalog-sync",
            event={
                "created": created,
                "updated": updated,
                "preserved": preserved,
                "failed": failed,
                "skipped_unmapped": skipped_unmapped,
                "skipped_filter": filtered_out,
                "total_rules": len(rules),
                "top_unmapped": top_unmapped,
                **scan.stats(),
                **disable_counts,
            },
        )

    def _attack_refs(self, tags) -> list[str]:
        """STIX ``attack-pattern`` ids for the rule's ATT&CK technique tags.

        Optional enrichment: lookups are cached for the life of the trigger
        and a failed or unknown lookup just omits that ref. If the API key
        may not read the intelligence objects (HTTP 401/403), lookups are
        switched off after one warning instead of failing per technique.
        """
        if not hasattr(self, "_attack_cache"):
            self._attack_cache: dict[str, str | None] = {}
            self._attack_lookups_enabled = True
        cache = self._attack_cache
        refs: list[str] = []
        for technique in _attack_technique_ids(tags):
            if technique not in cache:
                if not self._attack_lookups_enabled:
                    break
                try:
                    cache[technique] = self._sekoia.find_attack_pattern(technique)
                except SekoiaAPIError as exc:
                    if exc.status_code in (401, 403):
                        self._attack_lookups_enabled = False
                        self.log(
                            "ATT&CK technique linking disabled: the Sekoia API key may not read "
                            f"intelligence objects (HTTP {exc.status_code}). Grant read access to "
                            "the intelligence (CTI) objects to link imported rules to ATT&CK.",
                            level="warning",
                        )
                        break
                    cache[technique] = None
                    self.log(f"ATT&CK lookup for {technique} failed: {exc}", level="warning")
                except Exception as exc:
                    cache[technique] = None
                    self.log(f"ATT&CK lookup for {technique} failed: {exc}", level="warning")
            stix_id = cache[technique]
            if stix_id:
                refs.append(stix_id)
        return refs

    def _scan_catalog(self, id_map) -> CatalogScan:
        """Reconcile the local id-map with the Sekoia catalog.

        Lists every catalog rule carrying the integration marker tag
        (server-side ``match[tag_name]`` filter), optionally restricted to
        the configured community. For rules that also carry a
        ``uuid-<valhalla_id>`` tag the mapping is merged into the local
        id-map, so a fresh trigger instance (new playbook, recreated
        trigger, wiped data volume) picks up existing rules instead of
        creating duplicates.

        When several rules carry the same ``uuid-*`` tag (e.g. a user
        duplicated an imported rule to tune it), the UUID already in the
        local map wins; otherwise the first listed. The others are logged.

        Any listing error propagates: the caller must not continue on a
        partial scan.
        """
        scan = CatalogScan()
        uuids_by_vid: dict[str, list[str]] = {}
        communities: set[str] = set()
        for rule in self._sekoia.iter_rules(tag_name=MARKER_TAG, community_uuid=self._community_uuid):
            sekoia_uuid = rule.get("uuid")
            if not sekoia_uuid:
                continue
            scan.rules_by_uuid[sekoia_uuid] = rule
            if rule.get("community_uuid"):
                communities.add(rule["community_uuid"])
            vid = _extract_valhalla_id(rule)
            if vid:
                uuids_by_vid.setdefault(vid, []).append(sekoia_uuid)

        if not self._community_uuid and len(communities) > 1:
            raise RuntimeError(
                f"Rules imported by this integration exist in {len(communities)} communities "
                f"({sorted(communities)}). Set `community_uuid` in the module configuration so the "
                f"sync only touches one community."
            )

        for vid, uuids in uuids_by_vid.items():
            local = id_map.get(vid)
            chosen = local if local in uuids else uuids[0]
            if len(uuids) > 1:
                scan.duplicate_markers += len(uuids) - 1
                others = [u for u in uuids if u != chosen]
                self.log(
                    f"Several catalog rules carry the marker uuid-{vid}: keeping {chosen!r}, "
                    f"ignoring {others}. Delete the duplicates in the Sekoia UI.",
                    level="warning",
                )
            if local and local != chosen:
                scan.local_overridden += 1
                self.log(
                    f"Local id-map pointed uuid-{vid} at {local!r}, which is not in the catalog; using {chosen!r}.",
                    level="warning",
                )
            id_map[vid] = chosen
        scan.server_marker_count = len(uuids_by_vid)
        return scan

    # ------------------------------------------------------------------
    # Disable pass
    # ------------------------------------------------------------------

    def _check_feed_size(self, feed_size: int) -> str:
        """Return a skip reason for the disable pass, or ``""``.

        Persists the last accepted feed size. A shrink of more than
        ``MAX_FEED_SHRINK_RATIO`` is only accepted after it persisted for
        ``FEED_SHRINK_CONFIRM_RUNS`` consecutive syncs.
        """
        if feed_size == 0:
            return "empty_feed"
        with PersistentJSON(FEED_STATE_FILE, self.data_path) as state:
            reference = state.get("reference_size")
            if isinstance(reference, int) and feed_size < reference * (1 - MAX_FEED_SHRINK_RATIO):
                shrink_runs = int(state.get("shrink_runs", 0)) + 1
                if shrink_runs < FEED_SHRINK_CONFIRM_RUNS:
                    state["shrink_runs"] = shrink_runs
                    return "feed_shrank"
            state["reference_size"] = feed_size
            state["shrink_runs"] = 0
        return ""

    def _skipped_disable_counts(self, reason: str, feed_size: int) -> dict:
        self.log(
            f"Disable pass skipped ({reason}): feed has {feed_size} rules. No rule was disabled in this run.",
            level="warning",
        )
        return {
            "to_disable": 0,
            "newly_disabled": 0,
            "already_disabled": 0,
            "already_gone": 0,
            "disable_failed": 0,
            "disable_skipped_reason": reason,
        }

    def _disable_removed_rules(
        self,
        id_map,
        scan: CatalogScan,
        seen_in_feed: set[str],
        passed_filter: set[str],
        unparsed: set[str],
    ) -> dict:
        """Disable rules we previously synced that no longer belong.

        Candidate: ``valhalla_id`` in the id-map AND (not in the current
        feed OR now below the configured thresholds), excluding rules whose
        YAML failed to parse this run (their status is unknown).

        Uses the dedicated disable endpoint, which flips only ``enabled``.
        Server state comes from the catalog scan, so ``to_disable`` counts
        only candidates that still exist and are enabled.

        The id-map entry is kept after disabling so a reappearing rule
        resumes updating in place. With ``disable_removed`` off this is a
        dry-run that only counts ``to_disable``.
        """
        to_disable = 0
        newly_disabled = 0
        already_disabled = 0
        already_gone = 0
        disable_failed = 0
        skip_reason = ""
        first_failure_logged = False
        for vid in list(id_map):
            if vid in unparsed or (vid in seen_in_feed and vid in passed_filter):
                continue
            if not self.running:
                skip_reason = "interrupted"
                break
            sekoia_uuid = id_map[vid]
            server_rule = scan.rules_by_uuid.get(sekoia_uuid)
            if server_rule is None:
                already_gone += 1
                del id_map[vid]
                continue
            if not server_rule.get("enabled", False):
                already_disabled += 1
                continue
            to_disable += 1
            if not self._disable_removed:
                continue  # dry-run
            try:
                self._sekoia.disable_rule(sekoia_uuid)
                newly_disabled += 1
            except SekoiaRuleNotFoundError:
                already_gone += 1
                del id_map[vid]
            except Exception as exc:
                disable_failed += 1
                if not first_failure_logged:
                    self.log(
                        f"First disable-pass failure. valhalla_id={vid}, sekoia_uuid={sekoia_uuid}. Error: {exc}",
                        level="error",
                    )
                    first_failure_logged = True
        return {
            "to_disable": to_disable,
            "newly_disabled": newly_disabled,
            "already_disabled": already_disabled,
            "already_gone": already_gone,
            "disable_failed": disable_failed,
            "disable_skipped_reason": skip_reason,
        }
