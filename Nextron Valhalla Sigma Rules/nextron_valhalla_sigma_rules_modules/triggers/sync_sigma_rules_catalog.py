from collections import Counter

import yaml
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from nextron_valhalla_sigma_rules_modules.client import ValhallaClient
from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaClient,
    SekoiaRuleNotFoundError,
)
from nextron_valhalla_sigma_rules_modules.sigma_mapper import (
    DEFAULT_ALERT_UUID,
    MARKER_TAG,
    SEVERITY_MAP,
    STATUS_EFFORT_MAP,
    UUID_TAG_PREFIX,
    convert_parsed_to_ecs,
    sigma_rule_to_catalog_payload,
)

UUID_MAP_FILE = "valhalla-sigma-catalog-uuid-map.json"
TOP_UNMAPPED_REPORT = 5
DEFAULT_MIN_LEVEL = "medium"
DEFAULT_MIN_STATUS = "stable"


def _normalize_names(names) -> frozenset[str]:
    """Build the preserve-names matcher set from the trigger config.

    Non-list input → empty set (disables the check). Whitespace is
    stripped and empty entries are dropped so copy-paste from the Sekoia
    UI tolerates stray spaces or blank lines.
    """
    if not isinstance(names, list):
        return frozenset()
    return frozenset(
        n.strip() for n in names if isinstance(n, str) and n.strip()
    )


def _tag_name(tag) -> str:
    """Return the string name from either tag shape.

    Sekoia's GET on a rule returns tags as ``[{"uuid": ..., "name": ...}, …]``
    while our POST/PUT body sends plain strings. Both shapes carry the
    same identifying string in different places; this helper reads either.
    """
    if isinstance(tag, dict):
        return tag.get("name") or ""
    if isinstance(tag, str):
        return tag
    return ""


def _extract_valhalla_id(server_rule: dict) -> str | None:
    """Return the Valhalla UUID encoded in the rule's tags, or ``None`` if
    no ``uuid-*`` tag is present."""
    for tag in server_rule.get("tags") or []:
        name = _tag_name(tag)
        if name.startswith(UUID_TAG_PREFIX):
            return name[len(UUID_TAG_PREFIX):]
    return None


def _has_integration_marker(server_rule: dict) -> bool:
    """True when the server rule carries the ``nextron-valhalla`` tag —
    the discriminator used to decide 'this rule was created by this
    integration'."""
    return any(
        _tag_name(t) == MARKER_TAG for t in server_rule.get("tags") or []
    )

# Fields the Sekoia Rules Catalog PUT endpoint accepts. Sekoia's GET
# response additionally carries read-only metadata (`uuid`, `created_at`,
# `updated_at`, `created_by`, `community_uuid`, …) that PUT rejects, so
# the disable pass has to re-shape the GET response into this known-good
# whitelist before sending it back.
_PUT_FIELDS: tuple[str, ...] = (
    "name",
    "type",
    "description",
    "payload",
    "severity",
    "effort",
    "alert_type_uuid",
    "enabled",
    "tags",
    "false_positives",
)


def _disable_body_from_server(current: dict) -> dict:
    """Build a disable PUT body from the server's GET response.

    Copies only the fields the PUT endpoint accepts (see ``_PUT_FIELDS``)
    and forces ``enabled=False``. Tags are flattened to their names if the
    server returned the structured ``[{uuid, name}, …]`` shape — PUT expects
    plain strings.

    The server's GET often returns the alert type as an expanded object
    (``"alert_type": {"uuid": ..., "name": ...}``) rather than the flat
    ``alert_type_uuid`` string the PUT endpoint requires. Normalise it,
    falling back to ``DEFAULT_ALERT_UUID`` so the disable PUT can't be
    rejected for a missing required field.
    """
    body: dict = {k: current[k] for k in _PUT_FIELDS if k in current}
    tags = body.get("tags")
    if isinstance(tags, list):
        body["tags"] = [
            t["name"] if isinstance(t, dict) and "name" in t else t
            for t in tags
        ]
    if "alert_type_uuid" not in body:
        at = current.get("alert_type")
        if isinstance(at, dict) and at.get("uuid"):
            body["alert_type_uuid"] = at["uuid"]
        else:
            body["alert_type_uuid"] = DEFAULT_ALERT_UUID
    body["enabled"] = False
    return body


class SyncSigmaRulesCatalog(Trigger):
    def run(self):
        cfg = self.module.configuration
        self._valhalla = ValhallaClient(cfg.valhalla_api_key)
        self._sekoia = SekoiaClient(cfg.sekoia_base_url, cfg.sekoia_api_key)
        self._enabled = self.configuration.get("enabled", False)
        self._disable_removed = bool(self.configuration.get("disable_removed", False))
        self._preserve_rule_names = _normalize_names(
            self.configuration.get("preserve_rule_names", [])
        )
        min_level = self.configuration.get("min_sigma_level", DEFAULT_MIN_LEVEL)
        min_status = self.configuration.get("min_sigma_status", DEFAULT_MIN_STATUS)
        if min_level not in SEVERITY_MAP:
            raise ValueError(
                f"min_sigma_level={min_level!r} is not one of {sorted(SEVERITY_MAP)}"
            )
        if min_status not in STATUS_EFFORT_MAP:
            raise ValueError(
                f"min_sigma_status={min_status!r} is not one of {sorted(STATUS_EFFORT_MAP)}"
            )
        self._min_severity = SEVERITY_MAP[min_level]
        self._max_status_effort = STATUS_EFFORT_MAP[min_status]
        frequency = self.configuration.get("frequency", 86400)

        # SDK pattern: the first iteration runs immediately, then wait on
        # the stop-event so SIGINT/SIGTERM from Sekoia's playbook runner
        # unblocks us within the same tick instead of hanging on the next
        # sleep interval.
        while self.running:
            try:
                self._sync_once()
            except Exception as exc:
                self.log_exception(
                    exc, message="Failed to sync Valhalla Sigma to Rules Catalog"
                )
            self._stop_event.wait(frequency)

    def _rule_passes_filter(self, parsed: dict) -> bool:
        """Return True when the rule's Sigma ``level`` and ``status``
        both exist and meet the configured minimums. Rules missing
        either field are always filtered out."""
        level = (parsed.get("level") or "").lower()
        status = (parsed.get("status") or "").lower()
        level_score = SEVERITY_MAP.get(level)
        status_effort = STATUS_EFFORT_MAP.get(status)
        if level_score is None or status_effort is None:
            return False
        return (
            level_score >= self._min_severity
            and status_effort <= self._max_status_effort
        )

    def _sync_once(self):
        try:
            self._sync_once_inner()
        except Exception as exc:
            self.log_exception(
                exc, message="Failed to sync Valhalla Sigma to Rules Catalog"
            )

    def _sync_once_inner(self):
        rules = self._valhalla.get_sigma_feed()
        created = 0
        updated = 0
        preserved = 0
        failed = 0
        skipped_unmapped = 0
        filtered_out = 0
        unmapped_field_counter: Counter[str] = Counter()
        first_failure_logged = False
        seen_in_feed: set[str] = set()
        passed_filter: set[str] = set()
        with PersistentJSON(UUID_MAP_FILE, self.data_path) as id_map:
            scan_stats = self._rebuild_id_map_from_catalog(id_map)
            for rule in rules:
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

                body = sigma_rule_to_catalog_payload(
                    rule,
                    parsed,
                    self._enabled,
                )
                try:
                    if valhalla_id in id_map:
                        sekoia_uuid = id_map[valhalla_id]
                        try:
                            # Preserve the user's per-rule ``enabled`` choice:
                            # read it off the server before PUT so a rule
                            # the user disabled in the catalog stays
                            # disabled across syncs.
                            current = self._sekoia.get_rule(sekoia_uuid)
                            server_name = (current.get("name") or "").strip()
                            if server_name and server_name in self._preserve_rule_names:
                                # Operator listed this rule name in the trigger
                                # config to protect their hand-edits. Skip the
                                # overwrite entirely — the ``disable_removed``
                                # pass still runs independently if enabled.
                                preserved += 1
                                continue
                            body["enabled"] = bool(
                                current.get("enabled", self._enabled)
                            )
                            self._sekoia.update_rule(sekoia_uuid, body)
                            updated += 1
                        except SekoiaRuleNotFoundError:
                            # Stale id-map entry: the tenant-side rule
                            # was deleted (or attributed to a different
                            # key). Drop the entry and POST as new; the
                            # new rule inherits ``self._enabled``.
                            del id_map[valhalla_id]
                            body["enabled"] = self._enabled
                            new_uuid = self._sekoia.create_rule(body)
                            id_map[valhalla_id] = new_uuid
                            created += 1
                    else:
                        new_uuid = self._sekoia.create_rule(body)
                        id_map[valhalla_id] = new_uuid
                        created += 1
                except Exception as exc:
                    failed += 1
                    # Log the first failure loudly with the full POST body
                    # so the user can see exactly what shape the API rejected.
                    if not first_failure_logged:
                        self.log(
                            f"First rule sync failure (subsequent failures "
                            f"counted but not individually logged). "
                            f"Rule id={valhalla_id}, name={body.get('name')!r}. "
                            f"Sent body: {body}. Error: {exc}",
                            level="error",
                        )
                        first_failure_logged = True

            disable_counts = self._disable_removed_rules(
                id_map, seen_in_feed, passed_filter
            )

        top_unmapped = dict(unmapped_field_counter.most_common(TOP_UNMAPPED_REPORT))
        self.log(
            f"Catalog sync: created={created} updated={updated} "
            f"preserved={preserved} failed={failed} "
            f"skipped_unmapped={skipped_unmapped} "
            f"filtered_out={filtered_out} total_rules={len(rules)} "
            f"scan={scan_stats} "
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
                **scan_stats,
                **disable_counts,
            },
        )

    def _rebuild_id_map_from_catalog(self, id_map) -> dict:
        """Reconcile the local id-map with the Sekoia catalog.

        Scans every catalog rule once per sync. For each rule carrying the
        integration marker tag (``nextron-valhalla``) and a ``uuid-*`` tag,
        we extract the Valhalla UUID and build a server-side view of the
        mapping. That server view is then merged into the local id-map
        (catalog wins on conflict).

        This makes the catalog authoritative instead of the local file,
        which is important when the same Sekoia tenant is synced by more
        than one playbook / trigger instance: without the scan each trigger
        would see every Valhalla rule as "new" on its first run and POST
        duplicates. With the scan, a fresh trigger instance picks up the
        existing mappings on its first sync.

        Returns stats intended for the summary event:
        ``server_marker_count`` (rules we recognised), ``duplicate_markers``
        (same ``uuid-X`` on more than one server rule — operator must
        clean up manually), and ``local_overridden`` (local id-map
        entries the server disagreed with).
        """
        server_by_vid: dict[str, str] = {}
        duplicate_markers = 0
        for rule in self._sekoia.iter_rules():
            if not _has_integration_marker(rule):
                continue
            sekoia_uuid = rule.get("uuid")
            if not sekoia_uuid:
                continue
            vid = _extract_valhalla_id(rule)
            if not vid:
                continue
            if vid in server_by_vid:
                duplicate_markers += 1
                self.log(
                    f"Duplicate catalog rules carry the same marker uuid-{vid}: "
                    f"keeping {server_by_vid[vid]!r}, duplicate at "
                    f"{sekoia_uuid!r}. Delete the duplicate in the Sekoia UI.",
                    level="warning",
                )
                continue
            server_by_vid[vid] = sekoia_uuid

        local_overridden = 0
        for vid, uuid_val in server_by_vid.items():
            if vid in id_map and id_map[vid] != uuid_val:
                local_overridden += 1
                self.log(
                    f"Local id-map disagreed with catalog for uuid-{vid}: "
                    f"local={id_map[vid]!r}, catalog={uuid_val!r}. "
                    f"Trusting catalog.",
                    level="warning",
                )
            id_map[vid] = uuid_val

        return {
            "server_marker_count": len(server_by_vid),
            "duplicate_markers": duplicate_markers,
            "local_overridden": local_overridden,
        }

    def _disable_removed_rules(
        self,
        id_map,
        seen_in_feed: set[str],
        passed_filter: set[str],
    ) -> dict:
        """Disable rules we previously synced that no longer belong.

        Candidate: ``valhalla_id`` in the local id-map AND (not in the
        current feed OR present but now below the configured severity /
        maturity thresholds).

        Action: GET the server body, overwrite ``enabled=False``, PUT.
        Preserves any user edits to severity / tags / payload — matches
        the create/update path's "don't clobber server state" invariant.

        The id-map entry is **kept** after disabling so a reappearing
        rule resumes updating in place rather than being POSTed as a new
        rule with a fresh uuid.

        Dry-run is the default: with ``disable_removed`` off we only count
        candidates and emit ``to_disable`` on the summary event. Operators
        opt in once they trust the detection.
        """
        candidates = [
            vid
            for vid in list(id_map)
            if vid not in seen_in_feed or vid not in passed_filter
        ]
        to_disable = len(candidates)
        newly_disabled = 0
        already_disabled = 0
        already_gone = 0
        disable_failed = 0
        first_failure_logged = False
        for vid in candidates:
            sekoia_uuid = id_map[vid]
            try:
                current = self._sekoia.get_rule(sekoia_uuid)
            except SekoiaRuleNotFoundError:
                already_gone += 1
                del id_map[vid]
                continue
            except Exception as exc:
                disable_failed += 1
                if not first_failure_logged:
                    self.log(
                        f"First disable-pass failure (GET). "
                        f"valhalla_id={vid}, sekoia_uuid={sekoia_uuid}. "
                        f"Error: {exc}",
                        level="error",
                    )
                    first_failure_logged = True
                continue
            if not current.get("enabled", True):
                already_disabled += 1
                continue
            if not self._disable_removed:
                continue  # dry-run — counted under ``to_disable``
            disable_body = _disable_body_from_server(current)
            try:
                self._sekoia.update_rule(sekoia_uuid, disable_body)
                newly_disabled += 1
            except Exception as exc:
                disable_failed += 1
                if not first_failure_logged:
                    self.log(
                        f"First disable-pass failure (PUT). "
                        f"valhalla_id={vid}, sekoia_uuid={sekoia_uuid}. "
                        f"Sent body: {disable_body}. Error: {exc}",
                        level="error",
                    )
                    first_failure_logged = True
        return {
            "to_disable": to_disable,
            "newly_disabled": newly_disabled,
            "already_disabled": already_disabled,
            "already_gone": already_gone,
            "disable_failed": disable_failed,
        }
