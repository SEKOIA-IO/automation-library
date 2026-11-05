import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import cast

import yaml
from sekoia_automation.exceptions import ModuleConfigurationError, TriggerConfigurationError
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from nextron_valhalla_sigma_rules_modules.client import ValhallaClient
from nextron_valhalla_sigma_rules_modules.models import NextronValhallaSigmaRulesModuleConfiguration
from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaAPIError,
    SekoiaClient,
    SekoiaRuleNotFoundError,
    rule_tag_names,
    writable_rule,
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
# Tag the disable pass adds to the rules it switches off. It lives in the
# catalog, so any trigger configuration can re-enable those rules once they
# are back, while rules the user disabled (no tag) are never touched.
AUTO_DISABLED_TAG = "valhalla-auto-disabled"
# Key in FEED_STATE_FILE: Valhalla ids this configuration re-enabled in its
# last sync. Finding one disabled again means another trigger disabled it.
REENABLED_LAST_RUN_KEY = "reenabled_last_run"
# Rule settings a user changes in the Sekoia UI. An update copies them from
# the catalog: PUT replaces the whole rule, so leaving them out resets them.
USER_FIELDS = (
    "entities",
    "all_entities",
    "exclude_entities",
    "assets",
    "all_assets",
    "exclude_assets",
    "parameters",
    "event_fields",
    "similarity_strategy",
    "valid_until",
    "goal",
    "datasources",
)
ATTACK_PATTERN_PREFIX = "attack-pattern--"
STALE_REPORT = 5
TOP_UNMAPPED_REPORT = 5
DEFAULT_MIN_LEVEL = "medium"
DEFAULT_MIN_STATUS = "experimental"

# Disable-pass safety (B2): a feed that shrank by more than this ratio
# against the last accepted size is treated as suspicious (truncated
# response, key switched to the demo key, …) and the disable pass is
# skipped. If the smaller size persists for FEED_SHRINK_CONFIRM_RUNS
# consecutive syncs it is accepted as the new normal.
MAX_FEED_SHRINK_RATIO = 0.2
FEED_SHRINK_CONFIRM_RUNS = 3

# After a failed sync, retry sooner than ``frequency``: after 15 min, then
# after 30 min. At most MAX_RETRIES_PER_DAY such early retries run within
# any 24 h; once they are used up, the next attempt waits ``frequency``.
FAILURE_RETRY_DELAY = 900
MAX_RETRIES_PER_DAY = 2
RETRY_WINDOW = 86400

_ATTACK_TECHNIQUE_TAG = re.compile(r"^attack\.(t\d{4}(?:\.\d{3})?)$", re.IGNORECASE)


def _normalize_names(names) -> frozenset[str]:
    """Build the preserve matcher set from the trigger config.

    The argument is a text field: entries are separated by line breaks or
    ``;`` (not commas, which rule names may contain). A list is accepted
    too. Whitespace is stripped and empty entries are dropped so copy-paste
    from the Sekoia UI tolerates stray spaces or blank lines. Anything else
    → empty set (disables the check).
    """
    if isinstance(names, str):
        names = re.split(r"[;\r\n]", names)
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


@dataclass
class ReenableTracker:
    """Counts the re-enables of one sync.

    ``last_run`` holds the Valhalla ids this configuration re-enabled in its
    previous sync. Re-enabling one of them again means another trigger
    disabled it in between (``conflicts``).
    """

    last_run: set[str]
    log: Callable[..., None] = print
    done: set[str] = field(default_factory=set)
    re_enabled: int = 0
    failed: int = 0
    conflicts: int = 0
    logged: bool = False

    def run(self, valhalla_id: str, action: Callable[[], None], reraise: bool = False) -> None:
        """Run one re-enable. A rule that is gone (HTTP 404) is skipped;
        other errors are counted and logged once. With ``reraise`` the error
        propagates too, so the caller can count the failed update."""
        try:
            action()
        except SekoiaRuleNotFoundError:
            if reraise:
                raise
            return
        except Exception as exc:
            self.failed += 1
            if reraise:
                raise  # the caller counts and logs the failed update
            if not self.logged:
                self.log(f"First re-enable failure. valhalla_id={valhalla_id}. Error: {exc}", level="error")
                self.logged = True
            return
        self.re_enabled += 1
        self.done.add(valhalla_id)
        if valhalla_id in self.last_run:
            self.conflicts += 1

    def counts(self) -> dict:
        return {
            "re_enabled": self.re_enabled,
            "reenable_failed": self.failed,
            "reenable_conflicts": self.conflicts,
        }


class SyncSigmaRulesCatalog(Trigger):
    def run(self) -> None:
        # Trigger arguments arrive as a dict; the module configuration is
        # validated into ``NextronValhallaSigmaRulesModuleConfiguration``.
        args: dict = self.configuration if isinstance(self.configuration, dict) else {}
        min_level = args.get("min_sigma_level", DEFAULT_MIN_LEVEL)
        min_status = args.get("min_sigma_status", DEFAULT_MIN_STATUS)
        # Configuration errors use the SDK's exception types: it reports them
        # as critical and waits between restarts. Any other exception from
        # ``run()`` makes the SDK call it again immediately.
        if min_level not in SEVERITY_MAP:
            raise TriggerConfigurationError(f"min_sigma_level={min_level!r} is not one of {sorted(SEVERITY_MAP)}")
        if min_status not in STATUS_RANK:
            raise TriggerConfigurationError(f"min_sigma_status={min_status!r} is not one of {sorted(STATUS_RANK)}")
        self._min_severity = SEVERITY_MAP[min_level]
        self._min_status_rank = STATUS_RANK[min_status]
        self._enabled = args.get("enabled", False)
        self._disable_removed = bool(args.get("disable_removed", False))
        self._preserve_rule_names = _normalize_names(args.get("preserve_rule_names", ""))
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
        retry_times: list[float] = []  # when the early retries of the last 24 h run
        while self.running:
            try:
                self._sync_once()
                failed = False
            except Exception as exc:
                failed = True
                self.log_exception(exc, message="Failed to sync Valhalla Sigma to Rules Catalog")
            now = time.monotonic()
            retry_times = [t for t in retry_times if now - t < RETRY_WINDOW]
            delay = self._next_delay(frequency, failed, len(retry_times))
            if delay < frequency:
                retry_times.append(now + delay)
            self._stop_event.wait(delay)

    @staticmethod
    def _next_delay(frequency: int, failed: bool, recent_retries: int) -> int:
        """``frequency`` after a successful sync or once
        ``MAX_RETRIES_PER_DAY`` early retries ran in the last 24 h;
        otherwise ``FAILURE_RETRY_DELAY`` doubled per recent retry, capped at
        ``frequency``."""
        if not failed or recent_retries >= MAX_RETRIES_PER_DAY:
            return frequency
        return min(frequency, FAILURE_RETRY_DELAY * 2**recent_retries)

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
            raise ModuleConfigurationError(
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
        level = str(parsed.get("level") or "").lower()
        status = str(parsed.get("status") or "").lower()
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

    def _build_body(self, rule: dict, parsed: dict) -> dict:
        """Catalog body for one ECS-converted rule, plus the fields that need
        the module configuration or API lookups."""
        body = sigma_rule_to_catalog_payload(rule, parsed, self._enabled)
        if self._community_uuid:
            body["community_uuid"] = self._community_uuid
        refs = self._attack_refs(parsed.get("tags"))
        if refs:
            body["related_object_refs"] = refs
        return body

    def _keep_user_settings(self, body: dict, server_rule: dict) -> None:
        """Copy the settings a user owns from the catalog rule into an update
        body: PUT replaces the rule, so anything left out would be reset.

        Threats the user linked are kept next to the ATT&CK techniques the
        sync links. When ATT&CK lookups are switched off, the techniques
        linked earlier are kept instead of being dropped.
        """
        for key in USER_FIELDS:
            if key in server_rule:
                body[key] = server_rule[key]
        server_refs = [r for r in server_rule.get("related_object_refs") or [] if isinstance(r, str)]
        keep = [r for r in server_refs if not r.startswith(ATTACK_PATTERN_PREFIX)]
        if not getattr(self, "_attack_lookups_enabled", True):
            keep = server_refs
        refs = list(dict.fromkeys([*(body.get("related_object_refs") or []), *keep]))
        if refs:
            body["related_object_refs"] = refs

    @staticmethod
    def _is_auto_disabled(server_rule: dict) -> bool:
        """Disabled by the disable pass (not by the user) and still off."""
        return AUTO_DISABLED_TAG in rule_tag_names(server_rule) and not server_rule.get("enabled", False)

    @staticmethod
    def _has_stale_marker(server_rule: dict) -> bool:
        """Carries the marker although the user enabled the rule again: the
        marker must go, or a later manual disable would look like ours."""
        return AUTO_DISABLED_TAG in rule_tag_names(server_rule) and bool(server_rule.get("enabled", False))

    def _drop_marker(self, sekoia_uuid: str, server_rule: dict) -> None:
        """Remove the marker from a rule that is not updated in this run
        (updates drop it anyway). Bookkeeping only: errors are logged and
        the next sync tries again."""
        body = writable_rule(server_rule)
        body["tags"] = [t for t in body["tags"] if t != AUTO_DISABLED_TAG]
        try:
            self._sekoia.update_rule(sekoia_uuid, body)
        except Exception as exc:
            self.log(f"Could not remove the {AUTO_DISABLED_TAG} tag from {sekoia_uuid}: {exc}", level="warning")

    def _reenable_as_is(self, sekoia_uuid: str, server_rule: dict) -> None:
        """Enable a rule the disable pass switched off without updating its
        content (preserved rules, rules whose new version can't be
        converted): the catalog rule is sent back with ``enabled`` on and
        without the marker tag."""
        body = writable_rule(server_rule)
        body["tags"] = [t for t in body["tags"] if t != AUTO_DISABLED_TAG]
        body["enabled"] = True
        self._sekoia.update_rule(sekoia_uuid, body)

    def _confirm_missing_rule(self, sekoia_uuid: str) -> dict | None:
        """Look up a mapped rule the catalog scan did not return.

        The scan can miss a rule that still exists (the listing changed
        while it was paged through, or the user removed the marker tag), so
        a miss alone must not trigger a re-create, which would duplicate
        the rule. Returns the rule, or ``None`` when it is gone (HTTP 404) or
        belongs to another community than the configured one. Any other
        error propagates and the rule counts as failed for this run.
        """
        try:
            server_rule = self._sekoia.get_rule(sekoia_uuid)
        except SekoiaRuleNotFoundError:
            return None
        if not isinstance(server_rule, dict):
            raise SekoiaAPIError(f"GET rule {sekoia_uuid} returned an unexpected body: {server_rule!r}"[:500])
        if self._community_uuid and server_rule.get("community_uuid") not in (None, self._community_uuid):
            return None
        return server_rule

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
        first_malformed_logged = False
        seen_in_feed: set[str] = set()
        passed_filter: set[str] = set()
        unparsed: set[str] = set()
        stale_names: list[str] = []
        reenable = ReenableTracker(self._load_reenabled_last_run(), log=self.log)
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

                content = rule.get("content")
                try:
                    parsed_rule = yaml.safe_load(content) if isinstance(content, str) else None
                except yaml.YAMLError:
                    parsed_rule = None
                if not isinstance(parsed_rule, dict):
                    unparsed.add(valhalla_id)
                    skipped_unmapped += 1
                    unmapped_field_counter["<yaml-parse-error>"] += 1
                    self._note_stale(valhalla_id, id_map, scan, stale_names)
                    continue

                # One rule with unexpected field types must not abort the
                # whole sync: it is skipped and, like an unparsable rule,
                # kept out of the disable and re-enable passes.
                try:
                    passes = self._rule_passes_filter(parsed_rule)
                    parsed, unmapped = convert_parsed_to_ecs(parsed_rule) if passes else (None, [])
                    body = self._build_body(rule, parsed) if parsed is not None else None
                except Exception as exc:
                    unparsed.add(valhalla_id)
                    skipped_unmapped += 1
                    unmapped_field_counter["<malformed>"] += 1
                    self._note_stale(valhalla_id, id_map, scan, stale_names)
                    if not first_malformed_logged:
                        self.log(
                            f"Skipped malformed rule id={valhalla_id} (subsequent ones counted under "
                            f"'<malformed>' but not individually logged). Error: {exc!r}",
                            level="warning",
                        )
                        first_malformed_logged = True
                    continue

                if not passes:
                    filtered_out += 1
                    continue
                passed_filter.add(valhalla_id)

                if body is None:
                    skipped_unmapped += 1
                    for f in unmapped:
                        unmapped_field_counter[f] += 1
                    # The catalog keeps the last version that converted. If
                    # the disable pass had switched it off, it is back now.
                    server_rule = self._note_stale(valhalla_id, id_map, scan, stale_names)
                    if server_rule is not None and self._is_auto_disabled(server_rule):
                        reenable.run(valhalla_id, partial(self._reenable_as_is, id_map[valhalla_id], server_rule))
                    elif server_rule is not None and self._has_stale_marker(server_rule):
                        self._drop_marker(id_map[valhalla_id], server_rule)
                    continue

                try:
                    sekoia_uuid = id_map.get(valhalla_id)
                    server_rule = scan.rules_by_uuid.get(sekoia_uuid) if sekoia_uuid else None
                    if server_rule is None and sekoia_uuid:
                        server_rule = self._confirm_missing_rule(sekoia_uuid)
                        if server_rule is not None:
                            scan.rules_by_uuid[sekoia_uuid] = server_rule
                    if server_rule is None:
                        # Never synced, or the mapped rule is gone from the
                        # catalog (deleted in Sekoia) — create it.
                        if sekoia_uuid:
                            del id_map[valhalla_id]
                        body["enabled"] = self._enabled
                        id_map[valhalla_id] = self._sekoia.create_rule(body)
                        created += 1
                    elif self._is_preserved(server_rule):
                        # Operator listed this rule in ``preserve_rule_names``
                        # to protect their hand-edits. ``disable_removed`` still
                        # applies independently, and so does re-enabling.
                        preserved += 1
                        if self._is_auto_disabled(server_rule):
                            reenable.run(valhalla_id, partial(self._reenable_as_is, sekoia_uuid, server_rule))
                        elif self._has_stale_marker(server_rule):
                            self._drop_marker(sekoia_uuid, server_rule)
                    else:
                        # Keep the user's settings and per-rule ``enabled``
                        # choice. The generated tags never carry the marker,
                        # so a rule the disable pass switched off is enabled
                        # again in the same PUT (a second PUT built from the
                        # scan would undo this update).
                        self._keep_user_settings(body, server_rule)
                        if self._is_auto_disabled(server_rule):
                            body["enabled"] = True
                            reenable.run(
                                valhalla_id, partial(self._sekoia.update_rule, sekoia_uuid, body), reraise=True
                            )
                        else:
                            body["enabled"] = bool(server_rule.get("enabled", self._enabled))
                            self._sekoia.update_rule(sekoia_uuid, body)
                        updated += 1
                except SekoiaRuleNotFoundError:
                    # Deleted between the scan and now: create it again.
                    try:
                        del id_map[valhalla_id]
                        body["enabled"] = self._enabled
                        id_map[valhalla_id] = self._sekoia.create_rule(body)
                        created += 1
                    except Exception as exc:
                        failed += 1
                        first_failure_logged = self._log_first_failure(first_failure_logged, valhalla_id, body, exc)
                except Exception as exc:
                    failed += 1
                    first_failure_logged = self._log_first_failure(first_failure_logged, valhalla_id, body, exc)

            skip_reason = "interrupted" if interrupted else self._check_feed_size(len(rules))
            if skip_reason:
                disable_counts = self._skipped_disable_counts(skip_reason, len(rules))
            else:
                disable_counts = self._disable_removed_rules(id_map, scan, seen_in_feed, passed_filter, unparsed)
        self._save_reenabled_last_run(reenable)

        if stale_names:
            self.log(
                f"{len(stale_names)} imported rule(s) kept at an older version because the new version "
                f"could not be converted (see top_unmapped), e.g. {stale_names[:STALE_REPORT]}",
                level="info",
            )
        if reenable.conflicts:
            self.log(
                f"{reenable.conflicts} rule(s) this trigger re-enabled in its last sync were disabled again "
                f"by another trigger with 'Disable removed'. Run one sync trigger per community, or give the "
                f"trigger with 'Disable removed' filters that cover all rules you want to keep.",
                level="warning",
            )
        top_unmapped = dict(unmapped_field_counter.most_common(TOP_UNMAPPED_REPORT))
        reenable_counts = reenable.counts()
        self.log(
            f"Catalog sync: created={created} updated={updated} "
            f"preserved={preserved} failed={failed} "
            f"skipped_unmapped={skipped_unmapped} stale={len(stale_names)} "
            f"filtered_out={filtered_out} total_rules={len(rules)} "
            f"scan={scan.stats()} "
            f"reenable_counts={reenable_counts} "
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
                "stale": len(stale_names),
                "skipped_filter": filtered_out,
                "total_rules": len(rules),
                "top_unmapped": top_unmapped,
                **scan.stats(),
                **reenable_counts,
                **disable_counts,
            },
        )

    def _log_first_failure(self, logged: bool, valhalla_id: str, body: dict, exc: Exception) -> bool:
        """Log the first failure of a run loudly with the full body, so the
        user can see exactly what shape the API rejected. Returns True."""
        if not logged:
            self.log(
                f"First rule sync failure (subsequent failures "
                f"counted but not individually logged). "
                f"Rule id={valhalla_id}, name={body.get('name')!r}. "
                f"Sent body: {body}. Error: {exc}",
                level="error",
            )
        return True

    @staticmethod
    def _note_stale(valhalla_id: str, id_map, scan: CatalogScan, stale_names: list[str]) -> dict | None:
        """Record an imported rule that keeps its catalog version because the
        new feed version was skipped. Returns the catalog rule, if any."""
        sekoia_uuid = id_map.get(valhalla_id)
        server_rule = scan.rules_by_uuid.get(sekoia_uuid) if sekoia_uuid else None
        if server_rule is not None:
            stale_names.append(str(server_rule.get("name") or valhalla_id))
        return server_rule

    def _load_reenabled_last_run(self) -> set[str]:
        with PersistentJSON(FEED_STATE_FILE, self.data_path) as state:
            return set(state.get(REENABLED_LAST_RUN_KEY) or [])

    def _save_reenabled_last_run(self, reenable: ReenableTracker) -> None:
        if reenable.done == reenable.last_run:
            return
        with PersistentJSON(FEED_STATE_FILE, self.data_path) as state:
            state[REENABLED_LAST_RUN_KEY] = sorted(reenable.done)

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
                            f"intelligence objects (HTTP {exc.status_code}). Grant 'View intelligence' or "
                            "'View intelligence with limited access' to link imported rules to ATT&CK.",
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
        id-map, so a trigger with empty local storage (new trigger
        configuration, wiped data volume) picks up existing rules instead
        of creating duplicates.

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
            uuids = uuids_by_vid.setdefault(vid, []) if vid else None
            # Offset paging over a changing list can return a rule twice.
            if uuids is not None and sekoia_uuid not in uuids:
                uuids.append(sekoia_uuid)

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

        The catalog rule is sent back with ``enabled`` off and the
        ``AUTO_DISABLED_TAG`` added; everything else, including the user's
        settings, is unchanged (verified on a tenant). The tag lets any
        trigger configuration re-enable the rule once it is back, and tells
        it apart from a rule the user disabled. Server state comes from the
        catalog scan, so ``to_disable`` counts only candidates that still
        exist and are enabled.

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
                # Dry-run. A marker left on a rule the user re-enabled is
                # still cleared, so a later manual disable stays theirs.
                if self._has_stale_marker(server_rule):
                    self._drop_marker(sekoia_uuid, server_rule)
                continue
            body = writable_rule(server_rule)
            body["tags"] = sorted({*body["tags"], AUTO_DISABLED_TAG})
            body["enabled"] = False
            try:
                self._sekoia.update_rule(sekoia_uuid, body)
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
