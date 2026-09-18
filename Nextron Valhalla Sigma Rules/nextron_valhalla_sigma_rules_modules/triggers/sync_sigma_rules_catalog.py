from collections import Counter

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from nextron_valhalla_sigma_rules_modules.client import ValhallaClient
from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaClient,
    SekoiaRuleNotFoundError,
)
from nextron_valhalla_sigma_rules_modules.sigma_mapper import (
    SEVERITY_MAP,
    STATUS_EFFORT_MAP,
    convert_parsed_to_ecs,
    sigma_rule_to_catalog_payload,
)

UUID_MAP_FILE = "valhalla-sigma-catalog-uuid-map.json"
TOP_UNMAPPED_REPORT = 20
DEFAULT_MIN_LEVEL = "informational"
DEFAULT_MIN_STATUS = "experimental"


class SyncSigmaRulesCatalog(Trigger):
    def run(self):
        cfg = self.module.configuration
        self._valhalla = ValhallaClient(cfg.valhalla_api_key)
        self._sekoia = SekoiaClient(cfg.sekoia_base_url, cfg.sekoia_api_key)
        self._enabled = self.configuration.get("enabled", False)
        min_level = self.configuration.get("min_sigma_level", DEFAULT_MIN_LEVEL)
        min_status = self.configuration.get("min_sigma_status", DEFAULT_MIN_STATUS)
        self._min_severity = SEVERITY_MAP[min_level]
        self._max_status_effort = STATUS_EFFORT_MAP[min_status]
        frequency = self.configuration.get("frequency", 86400)

        self._sync_once()

        scheduler = BlockingScheduler()
        scheduler.add_job(self._sync_once, "interval", seconds=frequency)
        scheduler.start()

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
            rules = self._valhalla.get_sigma_feed()
            created = 0
            updated = 0
            failed = 0
            skipped_unmapped = 0
            filtered_out = 0
            unmapped_field_counter: Counter[str] = Counter()
            first_failure_logged = False
            with PersistentJSON(UUID_MAP_FILE, self.data_path) as id_map:
                for rule in rules:
                    valhalla_id = rule.get("id")
                    if not valhalla_id:
                        continue

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
                            try:
                                self._sekoia.update_rule(
                                    id_map[valhalla_id], body
                                )
                                updated += 1
                            except SekoiaRuleNotFoundError:
                                # Stale id-map entry: the tenant-side rule
                                # was deleted (or attributed to a different
                                # key). Drop the entry and POST as new.
                                del id_map[valhalla_id]
                                sekoia_uuid = self._sekoia.create_rule(body)
                                id_map[valhalla_id] = sekoia_uuid
                                created += 1
                        else:
                            sekoia_uuid = self._sekoia.create_rule(body)
                            id_map[valhalla_id] = sekoia_uuid
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

            top_unmapped = dict(unmapped_field_counter.most_common(TOP_UNMAPPED_REPORT))
            self.log(
                f"Catalog sync: created={created} updated={updated} "
                f"failed={failed} skipped_unmapped={skipped_unmapped} "
                f"filtered_out={filtered_out} total_rules={len(rules)} "
                f"top_unmapped={top_unmapped}",
                level="info",
            )
            self.send_event(
                event_name="valhalla-sigma-catalog-sync",
                event={
                    "created": created,
                    "updated": updated,
                    "failed": failed,
                    "skipped_unmapped": skipped_unmapped,
                    "skipped_filter": filtered_out,
                    "total_rules": len(rules),
                    "top_unmapped": top_unmapped,
                },
            )
        except Exception as exc:
            self.log_exception(
                exc, message="Failed to sync Valhalla Sigma to Rules Catalog"
            )
