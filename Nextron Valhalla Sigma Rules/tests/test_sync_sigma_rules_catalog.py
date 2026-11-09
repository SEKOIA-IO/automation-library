import json
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock

import pytest
from sekoia_automation.exceptions import ModuleConfigurationError, TriggerConfigurationError

from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaAPIError,
    SekoiaClient,
    SekoiaRuleNotFoundError,
    rule_tag_names,
)
from nextron_valhalla_sigma_rules_modules.sigma_mapper import SEVERITY_MAP
from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import (
    AUTO_DISABLED_TAG,
    FEED_STATE_FILE,
    REENABLED_LAST_RUN_KEY,
    UUID_MAP_FILE,
    SyncSigmaRulesCatalog,
    _attack_technique_ids,
    _normalize_names,
)


def _rule_yaml(title: str, level: str = "medium", status: str = "stable") -> str:
    """Build a minimal Sigma rule YAML that uses only Tier-1 mappable fields."""
    return (
        f"title: {title}\n"
        f"detection:\n"
        f"  selection:\n"
        f"    CommandLine|contains: '{title}'\n"
        f"  condition: selection\n"
        f"level: {level}\n"
        f"status: {status}\n"
    )


SEVERITY_HIGH = SEVERITY_MAP["high"]

SAMPLE_RULES = [
    {"id": "valhalla-a", "filename": "a.yml", "content": _rule_yaml("A")},
    {"id": "valhalla-b", "filename": "b.yml", "content": _rule_yaml("B", "high")},
]


def _unmappable_version_of_a() -> dict:
    """A new feed version of rule A that can't be converted to ECS."""
    content = (
        "title: A\ndetection:\n  selection:\n    RareCustomField: x\n  condition: selection\n"
        "level: medium\nstatus: stable\n"
    )
    return {"id": "valhalla-a", "filename": "a.yml", "content": content}


class FakeCatalog:
    """In-memory stand-in for the Sekoia Rules Catalog. Rules created by one
    sync are returned by the next sync's scan, like on a real tenant.

    Rules use the API's shapes (``alert_type`` object, tag objects) and PUT
    replaces the whole rule, as verified on a tenant: a field an update
    leaves out is reset. ``disabled`` / ``reenabled`` record the rules the
    integration switched off (marker added) or on again (marker removed).
    """

    DEFAULTS: ClassVar[dict] = {
        "entities": [],
        "all_entities": True,
        "exclude_entities": False,
        "assets": [],
        "all_assets": True,
        "exclude_assets": False,
        "parameters": None,
        "event_fields": [],
        "similarity_strategy": None,
        "valid_until": None,
        "deprecation_message": None,
        "false_positives": None,
        "goal": None,
        "datasources": [],
        "related_object_refs": [],
    }

    def __init__(self):
        self.rules: dict[str, dict] = {}
        self.disabled: list[str] = []
        self.reenabled: list[str] = []

    def _store(self, uuid, body, community_uuid):
        if "alert_type_uuid" not in body:
            raise SekoiaAPIError("alert_type_uuid: Field required", status_code=400)
        tags = body.get("tags", [])
        if not all(isinstance(t, str) for t in tags):
            raise SekoiaAPIError("tags: Input should be a valid string", status_code=400)
        refs = {}
        for key in ("entities", "assets", "datasources"):
            if not all(isinstance(x, str) for x in body.get(key) or []):
                raise SekoiaAPIError(f"{key}: Input should be a valid UUID", status_code=400)
            if key in body:
                refs[key] = [{"uuid": x} for x in body[key] or []]  # GET returns objects
        rule = {**self.DEFAULTS, **{k: v for k, v in body.items() if k not in ("alert_type_uuid", "tags")}, **refs}
        rule.update(
            uuid=uuid,
            community_uuid=community_uuid,
            alert_type={"uuid": body["alert_type_uuid"], "category_name": "intrusions"},
            alert_category={"uuid": "cat-1", "name": "intrusions"},
            tags=[{"uuid": f"t-{t}", "name": t} for t in tags],
        )
        self.rules[uuid] = rule

    def create(self, body):
        uuid = f"sekoia-{body['name']}"
        while uuid in self.rules:
            uuid += "+"
        self._store(uuid, body, body.get("community_uuid", "c-1"))
        return uuid

    def get(self, uuid):
        if uuid not in self.rules:
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        return dict(self.rules[uuid])

    def update(self, uuid, body):
        if uuid not in self.rules:
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        before = self.rules[uuid]
        self._store(uuid, body, before["community_uuid"])
        after = self.rules[uuid]
        marked_before = AUTO_DISABLED_TAG in rule_tag_names(before)
        marked_after = AUTO_DISABLED_TAG in rule_tag_names(after)
        if marked_after and not marked_before and before["enabled"] and not after["enabled"]:
            self.disabled.append(uuid)
        if marked_before and not marked_after and not before["enabled"] and after["enabled"]:
            self.reenabled.append(uuid)

    def iter_rules(self, tag_name=None, community_uuid=None, **_):
        for rule in list(self.rules.values()):
            names = {t["name"] for t in rule["tags"]}
            if tag_name and tag_name not in names:
                continue
            if community_uuid and rule.get("community_uuid") != community_uuid:
                continue
            yield dict(rule)


def _outdate(trigger, *uuids):
    """Make catalog rules look outdated (as if Nextron changed them), so the
    next sync really updates them instead of skipping them as unchanged."""
    for uuid in uuids or list(trigger.catalog.rules):
        trigger.catalog.rules[uuid]["description"] = "outdated"


def _marked(trigger) -> list[str]:
    """Catalog rules carrying the auto-disabled marker."""
    return sorted(u for u, r in trigger.catalog.rules.items() if AUTO_DISABLED_TAG in rule_tag_names(r))


@pytest.fixture
def trigger(data_storage, monkeypatch):
    from nextron_valhalla_sigma_rules_modules.triggers import sync_sigma_rules_catalog as sync_mod

    # Ordinary tests drop rules from a 2-rule feed; switch the B2 shrink
    # guard off here. The ``guarded`` fixture re-enables it.
    monkeypatch.setattr(sync_mod, "MAX_FEED_SHRINK_RATIO", 1.0)
    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t._valhalla = MagicMock()
    t._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    catalog = FakeCatalog()
    t.catalog = catalog
    # spec= makes a call to a method SekoiaClient doesn't define fail.
    t._sekoia = MagicMock(spec=SekoiaClient)
    t._sekoia.create_rule.side_effect = catalog.create
    t._sekoia.get_rule.side_effect = catalog.get
    t._sekoia.update_rule.side_effect = catalog.update
    t._sekoia.iter_rules.side_effect = catalog.iter_rules
    t._sekoia.find_attack_pattern.return_value = None
    t._enabled = False
    t._disable_removed = False
    t._preserve_rule_names = frozenset()
    t._community_uuid = None
    # Permissive defaults: every rule with status experimental+ and any
    # Sigma level passes.
    t._min_severity = 10  # informational
    t._min_status_rank = 1  # experimental
    t.send_event = MagicMock()
    t._send_logs_to_api = MagicMock()
    return t


def test_first_sync_posts_all_rules_and_persists_uuids(trigger, data_storage):
    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 2
    assert trigger._sekoia.update_rule.call_count == 0

    trigger.send_event.assert_called_once()
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 2
    assert event["updated"] == 0
    assert event["failed"] == 0
    assert event["skipped_unmapped"] == 0
    assert event["total_rules"] == 2

    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map == {"valhalla-a": "sekoia-A", "valhalla-b": "sekoia-B"}


def test_ecs_conversion_is_applied_before_post(trigger):
    trigger._sync_once()

    posted = trigger._sekoia.create_rule.call_args_list[0].args[0]
    assert "process.command_line" in posted["payload"]
    assert "CommandLine" not in posted["payload"]


def test_second_sync_skips_unchanged_rules(trigger):
    """Should-fix 2 (round 4): an unchanged feed sends no PUT at all."""
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 0
    trigger.send_event.assert_called_once()
    event = trigger.send_event.call_args.kwargs["event"]
    assert event == {
        "created": 0,
        "updated": 0,
        "unchanged": 2,
        "preserved": 0,
        "failed": 0,
        "skipped_unmapped": 0,
        "stale": 0,
        "skipped_filter": 0,
        "skipped_no_id": 0,
        "total_rules": 2,
        "top_unmapped": {},
        "server_marker_count": 2,
        "duplicate_markers": 0,
        "local_overridden": 0,
        "re_enabled": 0,
        "reenable_failed": 0,
        "reenable_conflicts": 0,
        "to_disable": 0,
        "newly_disabled": 0,
        "already_disabled": 0,
        "already_gone": 0,
        "disable_failed": 0,
        "disable_skipped_reason": "",
    }


def test_updated_content_reaches_put_body(trigger):
    """Rule with an id already in the id-map, whose Valhalla content
    changed between syncs: PUT must target the stored sekoia_uuid and
    carry the new content in its body."""
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()

    # Same valhalla-a id, but the selection value changed.
    updated_a = {
        "id": "valhalla-a",
        "filename": "a.yml",
        "content": (
            "title: A\n"
            "detection:\n"
            "  selection:\n"
            "    CommandLine|contains: 'A-updated'\n"
            "  condition: selection\n"
            "level: medium\n"
            "status: stable\n"
        ),
    }
    trigger._valhalla.get_sigma_feed.return_value = [updated_a, SAMPLE_RULES[1]]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0

    calls_by_uuid = {call.args[0]: call.args[1] for call in trigger._sekoia.update_rule.call_args_list}
    # Sekoia UUID is the one seeded on the first sync (from the id-map);
    # the untouched rule B is skipped as unchanged.
    assert list(calls_by_uuid) == ["sekoia-A"]
    assert "A-updated" in calls_by_uuid["sekoia-A"]["payload"]
    event = trigger.send_event.call_args.kwargs["event"]
    assert (event["updated"], event["unchanged"]) == (1, 1)


def test_third_sync_only_posts_new_rule(trigger):
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()

    new_rule = {"id": "valhalla-c", "filename": "c.yml", "content": _rule_yaml("C")}
    trigger._valhalla.get_sigma_feed.return_value = [*SAMPLE_RULES, new_rule]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 1
    assert trigger._sekoia.update_rule.call_count == 0  # A and B unchanged
    created_body = trigger._sekoia.create_rule.call_args.args[0]
    assert created_body["name"] == "C"


def test_skips_rules_without_valhalla_id(trigger):
    trigger._valhalla.get_sigma_feed.return_value = [
        {"filename": "no_id.yml", "content": _rule_yaml("NoID")},
        SAMPLE_RULES[0],
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 1
    created_body = trigger._sekoia.create_rule.call_args.args[0]
    assert created_body["name"] == "A"


def test_rules_with_unmapped_fields_are_skipped_not_posted(trigger):
    unmapped = {
        "id": "valhalla-unmapped",
        "filename": "unmapped.yml",
        "content": (
            "title: Unmapped\n"
            "detection:\n"
            "  selection:\n"
            "    RareCustomField|contains: 'foo'\n"
            "    AnotherUnknown: bar\n"
            "  condition: selection\n"
            "level: medium\n"
            "status: stable\n"
        ),
    }
    trigger._valhalla.get_sigma_feed.return_value = [unmapped]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 0

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 0
    assert event["skipped_unmapped"] == 1
    assert event["top_unmapped"]["RareCustomField"] == 1
    assert event["top_unmapped"]["AnotherUnknown"] == 1


def test_top_unmapped_is_ranked_by_frequency(trigger):
    def mk(valhalla_id, field):
        return {
            "id": valhalla_id,
            "filename": f"{valhalla_id}.yml",
            "content": (
                f"title: {valhalla_id}\n"
                f"detection:\n"
                f"  selection:\n"
                f"    {field}: x\n"
                f"  condition: selection\n"
                f"level: medium\n"
                f"status: stable\n"
            ),
        }

    trigger._valhalla.get_sigma_feed.return_value = [
        mk("a", "Common"),
        mk("b", "Common"),
        mk("c", "Common"),
        mk("d", "Rare"),
    ]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_unmapped"] == 4
    assert event["top_unmapped"] == {"Common": 3, "Rare": 1}


def test_per_rule_errors_do_not_abort_sync(trigger):
    trigger._sekoia.create_rule.side_effect = [
        RuntimeError("boom on A"),
        "sekoia-B",
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 2
    trigger.send_event.assert_called_once()
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 1
    assert event["failed"] == 1
    assert event["skipped_unmapped"] == 0


def test_valhalla_feed_error_propagates_without_side_effects(trigger):
    """The error is logged once by ``run()``; the sync itself touches nothing."""
    trigger._valhalla.get_sigma_feed.side_effect = RuntimeError("feed down")

    with pytest.raises(RuntimeError, match="feed down"):
        trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    trigger.send_event.assert_not_called()


def test_catalog_scan_error_aborts_sync(trigger):
    """B1: a failing scan must abort — never continue on a partial map."""

    def broken_scan(**_):
        yield {"uuid": "x", "tags": [{"name": "nextron-valhalla"}]}
        raise RuntimeError("HTTP 502 mid-scan")

    trigger._sekoia.iter_rules.side_effect = broken_scan

    with pytest.raises(RuntimeError, match="mid-scan"):
        trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 0
    trigger.send_event.assert_not_called()


def test_rule_deleted_in_catalog_is_recreated(trigger, data_storage):
    """A mapped UUID absent from the catalog scan and answering 404 is stale
    (the rule was deleted in Sekoia): drop it and create the rule again, no
    PUT."""
    trigger._sync_once()
    trigger.catalog.rules.clear()  # user deleted both rules in the UI
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 0
    assert trigger._sekoia.create_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 2
    assert event["failed"] == 0
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert set(id_map.values()) == set(trigger.catalog.rules)


def test_update_404_race_falls_back_to_create(trigger):
    """Rule present in the scan but deleted before the PUT: 404 → create."""
    trigger._sync_once()
    _outdate(trigger)
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.side_effect = SekoiaRuleNotFoundError("gone", status_code=404)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 2
    assert event["updated"] == 0


def test_update_403_counts_as_failed_not_stale(trigger, data_storage):
    """S1: a 403 on PUT is a failure — the mapping is kept and nothing is
    re-created (that would duplicate the rule on every run)."""
    trigger._sync_once()
    _outdate(trigger)
    before = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.side_effect = SekoiaAPIError("HTTP 403", status_code=403)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["failed"] == 2
    assert event["created"] == 0
    assert trigger._sekoia.create_rule.call_count == 0
    assert json.loads((Path(data_storage) / UUID_MAP_FILE).read_text()) == before


# ---------------------------------------------------------------------------
# Scan misses: a mapped rule absent from the scan is confirmed by GET
# ---------------------------------------------------------------------------


def _scan_returns_nothing(trigger):
    """Simulate a scan gap: the rules exist, but the listing misses them."""
    trigger._sekoia.iter_rules.side_effect = lambda **_: iter(())


def test_scan_miss_of_existing_rule_updates_instead_of_duplicating(trigger, data_storage):
    trigger._sync_once()
    _outdate(trigger)
    before = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    _scan_returns_nothing(trigger)
    trigger._sekoia.create_rule.reset_mock()

    trigger._sync_once()

    assert trigger._sekoia.get_rule.call_count == 2
    assert trigger._sekoia.create_rule.call_count == 0
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["updated"] == 2
    assert event["created"] == 0
    assert json.loads((Path(data_storage) / UUID_MAP_FILE).read_text()) == before


def test_scan_miss_keeps_server_enabled_flag(trigger):
    trigger._sync_once()
    _outdate(trigger)
    trigger.catalog.rules["sekoia-A"]["enabled"] = True
    _scan_returns_nothing(trigger)

    trigger._sync_once()

    bodies = {c.args[0]: c.args[1] for c in trigger._sekoia.update_rule.call_args_list}
    assert bodies["sekoia-A"]["enabled"] is True
    assert bodies["sekoia-B"]["enabled"] is False


def test_scan_miss_get_error_counts_as_failed_and_keeps_mapping(trigger, data_storage):
    """S1: only a 404 means the rule is gone. A 403 on the confirming GET is
    a failure; re-creating would duplicate the rule."""
    trigger._sync_once()
    before = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    _scan_returns_nothing(trigger)
    trigger._sekoia.get_rule.side_effect = SekoiaAPIError("HTTP 403", status_code=403)
    trigger._sekoia.create_rule.reset_mock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["failed"] == 2
    assert event["created"] == 0
    assert trigger._sekoia.create_rule.call_count == 0
    assert json.loads((Path(data_storage) / UUID_MAP_FILE).read_text()) == before


def test_scan_miss_unexpected_get_body_counts_as_failed(trigger):
    trigger._sync_once()
    _scan_returns_nothing(trigger)
    trigger._sekoia.get_rule.side_effect = None
    trigger._sekoia.get_rule.return_value = ["not", "a", "rule"]
    trigger._sekoia.create_rule.reset_mock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["failed"] == 2
    assert trigger._sekoia.create_rule.call_count == 0


def test_scan_miss_rule_in_other_community_is_not_ours(trigger, data_storage):
    """S3: with ``community_uuid`` set, a rule found by GET in another
    community is not touched; the rule is created in the configured one."""
    trigger._community_uuid = "c-1"
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]
    (Path(data_storage) / UUID_MAP_FILE).write_text(json.dumps({"valhalla-a": "elsewhere"}))
    trigger.catalog.rules = {
        "elsewhere": _catalog_rule("elsewhere", "nextron-valhalla", "uuid-valhalla-a", community="c-2"),
    }

    trigger._sync_once()

    assert trigger._sekoia.get_rule.call_args.args == ("elsewhere",)
    assert trigger._sekoia.update_rule.call_count == 0
    assert trigger._sekoia.create_rule.call_args.args[0]["community_uuid"] == "c-1"


def test_rule_without_marker_tag_is_updated_and_retagged(trigger):
    """Removing the ``nextron-valhalla`` tag hides the rule from the scan,
    but the mapped UUID is confirmed by GET: the rule is updated (which puts
    the tag back) instead of being duplicated."""
    trigger._sync_once()
    for rule in trigger.catalog.rules.values():
        rule["tags"] = [t for t in rule["tags"] if t["name"] != "nextron-valhalla"]
    trigger._sekoia.create_rule.reset_mock()

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 2
    for call in trigger._sekoia.update_rule.call_args_list:
        assert "nextron-valhalla" in call.args[1]["tags"]


def test_rules_found_by_scan_are_not_fetched_again(trigger):
    trigger._sync_once()
    trigger._sync_once()

    assert trigger._sekoia.get_rule.call_count == 0


def test_scan_ignores_a_rule_listed_twice(trigger):
    """Offset paging over a changing list can return a rule twice; that is
    not a duplicate marker."""
    trigger._sync_once()
    _outdate(trigger)
    rule = dict(trigger.catalog.rules["sekoia-A"])
    trigger._sekoia.iter_rules.side_effect = lambda **_: iter([rule, rule])
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["duplicate_markers"] == 0
    assert event["updated"] == 1
    assert not [c for c in trigger.log.call_args_list if "Several catalog rules" in c.args[0]]


# ---------------------------------------------------------------------------
# Malformed rules must not abort the sync
# ---------------------------------------------------------------------------


def _explode_on_rule_a(monkeypatch):
    """Make the conversion of rule A raise, as an unexpected field type in a
    future feed rule would."""
    from nextron_valhalla_sigma_rules_modules.triggers import sync_sigma_rules_catalog as sync_mod

    real = sync_mod.convert_parsed_to_ecs

    def convert(parsed):
        if parsed.get("title") == "A":
            raise TypeError("unexpected type")
        return real(parsed)

    monkeypatch.setattr(sync_mod, "convert_parsed_to_ecs", convert)


def test_malformed_rule_is_skipped_and_sync_completes(trigger, monkeypatch):
    _explode_on_rule_a(monkeypatch)
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 1
    assert event["skipped_unmapped"] == 1
    assert event["top_unmapped"] == {"<malformed>": 1}
    warnings = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"]
    assert len(warnings) == 1
    assert "valhalla-a" in warnings[0].args[0]


def test_malformed_rule_is_not_a_disable_candidate(trigger, monkeypatch):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    _explode_on_rule_a(monkeypatch)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 0
    assert trigger.catalog.disabled == []


@pytest.mark.parametrize(
    "content, expected",
    [
        pytest.param(None, "skipped_unmapped", id="null-content"),
        pytest.param(123, "skipped_unmapped", id="int-content"),
        pytest.param(_rule_yaml("A").replace("level: medium", "level: 5"), "skipped_filter", id="int-level"),
        pytest.param(
            _rule_yaml("A").replace("status: stable", "status: [stable]"), "skipped_filter", id="list-status"
        ),
        pytest.param(_rule_yaml("A").replace("title: A", "title: 2024"), "created", id="int-title"),
        pytest.param(_rule_yaml("A") + "tags: attack.execution\n", "created", id="string-tags"),
        pytest.param(_rule_yaml("A") + "description: 42\nreferences: https://x\n", "created", id="scalar-text"),
    ],
)
def test_unusual_field_types_do_not_abort_sync(trigger, content, expected):
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "valhalla-a", "filename": "a.yml", "content": content},
        SAMPLE_RULES[1],
    ]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["failed"] == 0
    if expected == "created":
        assert event["created"] == 2
    else:
        assert event[expected] == 1
        assert event["created"] == 1  # rule B still goes through


def test_rules_missing_level_are_filtered_out(trigger):
    yaml_no_level = (
        "title: NoLevel\n"
        "detection:\n"
        "  selection:\n    CommandLine|contains: 'x'\n"
        "  condition: selection\n"
        "status: stable\n"
    )
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "valhalla-x", "filename": "x.yml", "content": yaml_no_level},
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_filter"] == 1
    assert event["created"] == 0


def test_rules_missing_status_are_filtered_out(trigger):
    yaml_no_status = (
        "title: NoStatus\n"
        "detection:\n"
        "  selection:\n    CommandLine|contains: 'x'\n"
        "  condition: selection\n"
        "level: medium\n"
    )
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "valhalla-y", "filename": "y.yml", "content": yaml_no_status},
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_filter"] == 1


def test_rules_below_min_level_are_filtered_out(trigger):
    trigger._min_severity = 70  # high
    # SAMPLE_RULES: A=medium (skipped), B=high (kept).
    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 1
    posted = trigger._sekoia.create_rule.call_args.args[0]
    assert posted["name"] == "B"
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_filter"] == 1
    assert event["created"] == 1


def test_rules_below_min_status_are_filtered_out(trigger):
    trigger._min_status_rank = 3  # stable
    trigger._valhalla.get_sigma_feed.return_value = [
        *SAMPLE_RULES,
        {"id": "valhalla-exp", "filename": "exp.yml", "content": _rule_yaml("Experimental", status="experimental")},
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_filter"] == 1


@pytest.mark.parametrize("status", ["deprecated", "unsupported"])
def test_deprecated_and_unsupported_are_never_imported(trigger, status):
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "v-x", "filename": "x.yml", "content": _rule_yaml("X", status=status)},
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0


def test_stale_put_then_failed_post_counts_as_failed(trigger):
    """If the create fallback also fails, the rule counts as failed."""
    trigger._sync_once()
    _outdate(trigger)
    trigger._sekoia.update_rule.side_effect = SekoiaRuleNotFoundError("gone", status_code=404)
    trigger._sekoia.create_rule.side_effect = RuntimeError("POST also broken")

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 0
    assert event["updated"] == 0
    assert event["failed"] == 2


# ---------------------------------------------------------------------------
# Preserve user's ``enabled`` choice on update (blocker #1 — GET-then-PUT)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("server_enabled", [True, False])
def test_update_keeps_server_enabled_flag(trigger, server_enabled):
    """The user's per-rule ``enabled`` choice, read from the catalog scan,
    is re-sent on update — whatever the trigger's ``enabled`` default."""
    trigger._sync_once()
    _outdate(trigger)
    for rule in trigger.catalog.rules.values():
        rule["enabled"] = server_enabled
    trigger._enabled = not server_enabled
    trigger._sekoia.update_rule.reset_mock()

    trigger._sync_once()

    bodies = [c.args[1] for c in trigger._sekoia.update_rule.call_args_list]
    assert len(bodies) == 2
    assert all(b["enabled"] is server_enabled for b in bodies)


def test_sync_does_not_get_each_rule(trigger):
    """S15: the scan provides the server state; no per-rule GET."""
    trigger._sync_once()
    trigger._sync_once()

    assert trigger._sekoia.get_rule.call_count == 0


# ---------------------------------------------------------------------------
# Argument validation (should-fix #6)
# ---------------------------------------------------------------------------


def test_invalid_min_level_raises(trigger):
    trigger.configuration = {"min_sigma_level": "bogus"}
    trigger.module = MagicMock()
    with pytest.raises(TriggerConfigurationError, match="min_sigma_level"):
        trigger.run()


def test_invalid_min_status_raises(trigger):
    trigger.configuration = {"min_sigma_status": "bogus"}
    trigger.module = MagicMock()
    with pytest.raises(TriggerConfigurationError, match="min_sigma_status"):
        trigger.run()


def test_default_thresholds_are_medium_and_experimental(monkeypatch, data_storage):
    """Without explicit arguments, run() filters on medium / experimental,
    and the manifest declares the same defaults."""
    from nextron_valhalla_sigma_rules_modules.triggers import sync_sigma_rules_catalog as sync_mod

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)

    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {}
    t._stop_event.set()  # apply the arguments, then exit before syncing
    t.run()
    assert t._min_severity == SEVERITY_MAP["medium"]
    assert t._min_status_rank == 1  # experimental

    manifest = json.loads((Path(__file__).parent.parent / "trigger_sync_sigma_rules_catalog.json").read_text())
    args = manifest["arguments"]["properties"]
    assert args["min_sigma_level"]["default"] == "medium"
    assert args["min_sigma_status"]["default"] == "experimental"


# ---------------------------------------------------------------------------
# Stop-event shutdown (should-fix #2)
# ---------------------------------------------------------------------------


def test_run_exits_when_stop_event_is_set(monkeypatch, data_storage):
    """Pre-set the stop event; run() must return without iterating."""
    import threading

    from nextron_valhalla_sigma_rules_modules.triggers import (
        sync_sigma_rules_catalog as sync_mod,
    )

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)

    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"frequency": 60}
    t._sync_once = MagicMock()
    t._stop_event.set()  # loop guard sees running=False, exits immediately

    th = threading.Thread(target=t.run)
    th.start()
    th.join(timeout=5)
    assert not th.is_alive(), "run() should exit when stop event is set"
    assert t._sync_once.call_count == 0


def test_run_exits_after_stop_during_wait(monkeypatch, data_storage):
    """Trigger runs, we call stop() while it's waiting on the next
    iteration — _stop_event.wait() returns early and the loop exits."""
    import threading
    import time

    from nextron_valhalla_sigma_rules_modules.triggers import (
        sync_sigma_rules_catalog as sync_mod,
    )

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)

    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"frequency": 3600}  # long sleep so we're definitely waiting
    t._sync_once = MagicMock()

    th = threading.Thread(target=t.run)
    th.start()
    time.sleep(0.2)  # let it get into _stop_event.wait()
    t.stop()
    th.join(timeout=5)
    assert not th.is_alive(), "run() should exit when stop() is called mid-wait"
    assert t._sync_once.call_count >= 1


def test_run_logs_sync_errors_once_and_keeps_looping(monkeypatch, data_storage):
    """Nit: the error is caught and logged in ``run()`` only."""
    import threading
    import time

    from nextron_valhalla_sigma_rules_modules.triggers import (
        sync_sigma_rules_catalog as sync_mod,
    )

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)

    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"frequency": 3600}
    t._sync_once = MagicMock(side_effect=RuntimeError("boom"))
    t.log_exception = MagicMock()

    th = threading.Thread(target=t.run)
    th.start()
    time.sleep(0.2)
    t.stop()
    th.join(timeout=5)
    assert t.log_exception.call_count == 1


def _run_with_clock(monkeypatch, data_storage, outcomes, frequency=86400):
    """Run the trigger loop with a fake clock that advances by each wait.
    ``outcomes`` lists the sync results (an exception = failed sync); the
    loop stops after the last one. Returns the waits."""
    from nextron_valhalla_sigma_rules_modules.triggers import (
        sync_sigma_rules_catalog as sync_mod,
    )

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)

    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"frequency": frequency}
    t._sync_once = MagicMock(side_effect=outcomes)
    t.log_exception = MagicMock()
    clock = {"now": 1000.0}
    waits: list[float] = []

    def wait(delay):
        waits.append(delay)
        clock["now"] += delay
        if len(waits) == len(outcomes):
            t._stop_event.set()

    monkeypatch.setattr(sync_mod.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(t._stop_event, "wait", wait)

    t.run()
    return waits


def test_failed_sync_is_retried_at_most_twice_a_day(monkeypatch, data_storage):
    """A failed sync is retried after 15 then 30 min; once two early
    retries ran in the last 24 h, the next attempt waits ``frequency``."""
    from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import FAILURE_RETRY_DELAY

    down = RuntimeError("feed down")
    waits = _run_with_clock(monkeypatch, data_storage, [down, down, down, None])

    assert waits == [FAILURE_RETRY_DELAY, 2 * FAILURE_RETRY_DELAY, 86400, 86400]


def test_retries_are_allowed_again_after_24_hours(monkeypatch, data_storage):
    from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import FAILURE_RETRY_DELAY

    down = RuntimeError("feed down")
    waits = _run_with_clock(monkeypatch, data_storage, [down] * 6)

    assert waits == [FAILURE_RETRY_DELAY, 2 * FAILURE_RETRY_DELAY, 86400] * 2


def test_success_between_failures_does_not_reset_the_daily_cap(monkeypatch, data_storage):
    """The cap counts retries in the last 24 h, not per failure streak:
    with hourly syncs, a second outage the same day gets one retry left."""
    from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import FAILURE_RETRY_DELAY

    down = RuntimeError("feed down")
    waits = _run_with_clock(monkeypatch, data_storage, [down, None, down, down, down], frequency=3600)

    assert waits == [FAILURE_RETRY_DELAY, 3600, 2 * FAILURE_RETRY_DELAY, 3600, 3600]


@pytest.mark.parametrize(
    "frequency, failed, recent_retries, expected",
    [
        (86400, False, 0, 86400),
        (86400, True, 0, 900),
        (86400, True, 1, 1800),
        (86400, True, 2, 86400),
        (3600, True, 0, 900),
        (1200, True, 1, 1200),
    ],
)
def test_next_delay(frequency, failed, recent_retries, expected):
    assert SyncSigmaRulesCatalog._next_delay(frequency, failed, recent_retries) == expected


def test_per_rule_loop_stops_when_trigger_stops(trigger):
    """S5: ``self.running`` is checked per rule; an interrupted run skips
    the disable pass."""
    calls = {"n": 0}
    original = trigger._sekoia.create_rule.side_effect

    def create_then_stop(body):
        calls["n"] += 1
        trigger._stop_event.set()
        return original(body)

    trigger._sekoia.create_rule.side_effect = create_then_stop
    trigger._disable_removed = True

    trigger._sync_once()

    assert calls["n"] == 1
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 1
    assert event["disable_skipped_reason"] == "interrupted"


def _alert_types_client(uuids):
    client = MagicMock(spec=SekoiaClient)
    client.list_alert_types.return_value = [{"uuid": u} for u in uuids]
    return client


def test_validate_alert_types_passes_when_all_exist(trigger):
    from nextron_valhalla_sigma_rules_modules.sigma_mapper import DEFAULT_ALERT_UUID, TAG_ALERT_UUID_MAP

    trigger._sekoia = _alert_types_client([DEFAULT_ALERT_UUID, *(u for _, u in TAG_ALERT_UUID_MAP)])
    trigger._validate_alert_types()


def test_validate_alert_types_fails_fast_on_missing_uuid(trigger):
    """S16: a hard-coded alert type unknown to the tenant fails at startup
    with a clear message instead of a 400 on every create."""
    trigger._sekoia = _alert_types_client(["something-else"])
    with pytest.raises(ModuleConfigurationError, match="do not exist on this Sekoia tenant"):
        trigger._validate_alert_types()


def test_validate_alert_types_tolerates_listing_failure(trigger):
    trigger._sekoia = MagicMock(spec=SekoiaClient)
    trigger._sekoia.list_alert_types.side_effect = RuntimeError("403")
    trigger.log = MagicMock()
    trigger._validate_alert_types()
    assert trigger.log.call_args.kwargs["level"] == "warning"


# ---------------------------------------------------------------------------
# preserve_rule_names — per-rule opt-out from Valhalla overwrites
# ---------------------------------------------------------------------------


def test_normalize_names_strips_whitespace_and_drops_empties():
    assert _normalize_names(["  A rule  ", "Another", " ", ""]) == frozenset({"A rule", "Another"})


def test_normalize_names_other_types_return_empty():
    assert _normalize_names(None) == frozenset()
    assert _normalize_names({"A": True}) == frozenset()
    assert _normalize_names("") == frozenset()


def test_normalize_names_splits_text_on_lines_and_semicolons():
    text = "A rule, with a comma\n  uuid-123 ;Another\r\n\n; "
    assert _normalize_names(text) == frozenset({"A rule, with a comma", "uuid-123", "Another"})


def test_normalize_names_drops_non_string_entries():
    assert _normalize_names(["A", 123, None, "B"]) == frozenset({"A", "B"})


def test_preserve_rule_names_skips_update_when_server_name_matches(trigger):
    """A rule whose server-side name appears in the configured list is NOT
    PUT with Valhalla content; the counter increments."""
    trigger._sync_once()  # populate id_map; both rules then exist
    _outdate(trigger)
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._preserve_rule_names = frozenset({"A"})

    trigger._sync_once()

    # A was preserved → no PUT for A; B was updated normally.
    assert trigger._sekoia.update_rule.call_count == 1
    assert trigger._sekoia.update_rule.call_args.args[0] == "sekoia-B"
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 1
    assert event["updated"] == 1


def test_preserve_rule_names_tolerates_whitespace_on_server_name(trigger):
    """Server-returned names with stray whitespace still match a trimmed
    entry in the preserve list — operators who copy-paste from the UI
    shouldn't get bitten by a trailing space."""
    trigger._sync_once()
    _outdate(trigger)
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._preserve_rule_names = frozenset({"A"})

    trigger.catalog.rules["sekoia-A"]["name"] = "  A  "

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 1
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 1


def test_preserve_rule_names_absent_updates_normally(trigger):
    """Empty preserve list → both rules get the usual PUT; preserved=0."""
    trigger._sync_once()
    _outdate(trigger)
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 0
    assert event["updated"] == 2


def test_preserve_rule_names_mismatched_name_does_not_preserve(trigger):
    """Case-sensitive exact match: a lowercase entry does not match the
    server's PascalCase name."""
    trigger._sync_once()
    _outdate(trigger)
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._preserve_rule_names = frozenset({"a"})  # lowercase; server is "A"
    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 0


def test_preserve_rule_names_does_not_affect_posts(trigger, data_storage):
    """A brand-new Valhalla rule whose title happens to match a preserve
    entry is still created — the preserve check only guards the update
    path (no catalog rule yet, nothing to compare against)."""
    trigger._preserve_rule_names = frozenset({"New"})
    trigger._valhalla.get_sigma_feed.return_value = [
        {
            "id": "valhalla-new",
            "filename": "new.yml",
            "content": (
                "title: New\n"
                "detection:\n"
                "  selection:\n    CommandLine|contains: 'x'\n"
                "  condition: selection\n"
                "level: medium\n"
                "status: stable\n"
            ),
        }
    ]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 1
    assert trigger._sekoia.update_rule.call_count == 0
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 1
    assert event["preserved"] == 0


def test_disable_pass_still_fires_on_preserved_rule(trigger, data_storage):
    """A preserved rule that leaves the feed is still disabled by
    ``disable_removed=true`` — preserve protects content, not lifecycle."""
    trigger._sync_once()
    for rule in trigger.catalog.rules.values():
        rule["enabled"] = True
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True
    trigger._preserve_rule_names = frozenset({"A"})

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["newly_disabled"] == 1
    assert trigger.catalog.disabled == ["sekoia-A"]
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False


def test_preserve_entry_matches_uuid_tag(trigger):
    """Nit: names aren't unique, so an entry may also be the rule's
    ``uuid-<valhalla_id>`` tag."""
    trigger._sync_once()
    _outdate(trigger)
    trigger._sekoia.update_rule.reset_mock()
    trigger._preserve_rule_names = frozenset({"uuid-valhalla-a"})

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 1
    assert [c.args[0] for c in trigger._sekoia.update_rule.call_args_list] == ["sekoia-B"]


# ---------------------------------------------------------------------------
# Catalog scan — rebuild id-map from server-side uuid-* tags
# ---------------------------------------------------------------------------


def _catalog_rule(uuid, *tags, name="R", enabled=False, community="c-1"):
    return {
        "uuid": uuid,
        "name": name,
        "enabled": enabled,
        "community_uuid": community,
        "tags": [{"uuid": f"t-{t}", "name": t} for t in tags],
    }


def test_scan_builds_id_map_from_uuid_tags(trigger, data_storage):
    """Fresh trigger (empty id-map), catalog already holds the rules → they
    are updated, not duplicated."""
    trigger.catalog.rules = {
        "sekoia-A": _catalog_rule("sekoia-A", "nextron-valhalla", "uuid-valhalla-a", name="A"),
        "sekoia-B": _catalog_rule("sekoia-B", "nextron-valhalla", "uuid-valhalla-b", name="B"),
    }

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["server_marker_count"] == 2
    assert event["duplicate_markers"] == 0
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map == {"valhalla-a": "sekoia-A", "valhalla-b": "sekoia-B"}


def test_scan_uses_server_side_tag_filter(trigger):
    trigger._sync_once()
    kwargs = trigger._sekoia.iter_rules.call_args.kwargs
    assert kwargs["tag_name"] == "nextron-valhalla"
    assert kwargs["community_uuid"] is None


def test_scan_duplicate_markers_first_listed_wins_without_local_entry(trigger):
    trigger.catalog.rules = {
        "sekoia-A-1": _catalog_rule("sekoia-A-1", "nextron-valhalla", "uuid-valhalla-a", name="A"),
        "sekoia-A-2": _catalog_rule("sekoia-A-2", "nextron-valhalla", "uuid-valhalla-a", name="A"),
    }
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["duplicate_markers"] == 1
    assert event["server_marker_count"] == 1
    assert trigger._sekoia.update_rule.call_args.args[0] == "sekoia-A-1"
    warnings = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"]
    assert any("sekoia-A-2" in str(c) for c in warnings)


def test_scan_duplicate_markers_prefer_local_mapping(trigger, data_storage):
    """S4: a user duplicated an imported rule to tune it (the uuid tag is
    copied). The rule already in the local map keeps being updated, even
    if the user's copy is listed first."""
    (Path(data_storage) / UUID_MAP_FILE).write_text(json.dumps({"valhalla-a": "sekoia-original"}))
    trigger.catalog.rules = {
        "sekoia-user-copy": _catalog_rule("sekoia-user-copy", "nextron-valhalla", "uuid-valhalla-a", name="A tuned"),
        "sekoia-original": _catalog_rule("sekoia-original", "nextron-valhalla", "uuid-valhalla-a", name="A"),
    }
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]

    trigger._sync_once()

    assert [c.args[0] for c in trigger._sekoia.update_rule.call_args_list] == ["sekoia-original"]
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["duplicate_markers"] == 1
    assert event["local_overridden"] == 0


def test_scan_overrides_local_entry_missing_from_catalog(trigger, data_storage):
    """Local map points at a UUID the catalog doesn't have; the catalog's
    rule carrying the uuid tag is used instead."""
    (Path(data_storage) / UUID_MAP_FILE).write_text(json.dumps({"valhalla-a": "stale-uuid"}))
    trigger.catalog.rules = {
        "fresh-uuid": _catalog_rule("fresh-uuid", "nextron-valhalla", "uuid-valhalla-a", name="A"),
    }
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["local_overridden"] == 1
    assert trigger._sekoia.update_rule.call_args.args[0] == "fresh-uuid"
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map["valhalla-a"] == "fresh-uuid"


def test_legacy_rule_without_uuid_tag_is_updated_via_local_map(trigger, data_storage):
    """Rules synced before the uuid tag existed are still found through the
    local map (the scan lists every marker-tagged rule) and get the tag on
    the next update."""
    (Path(data_storage) / UUID_MAP_FILE).write_text(json.dumps({"valhalla-a": "legacy"}))
    trigger.catalog.rules = {"legacy": _catalog_rule("legacy", "nextron-valhalla", name="A")}
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    uuid, body = trigger._sekoia.update_rule.call_args.args
    assert uuid == "legacy"
    assert "uuid-valhalla-a" in body["tags"]


def test_scan_aborts_when_rules_span_several_communities(trigger):
    """S3: without ``community_uuid`` the sync refuses to touch rules in
    more than one community."""
    trigger.catalog.rules = {
        "x": _catalog_rule("x", "nextron-valhalla", "uuid-valhalla-a", community="c-1"),
        "y": _catalog_rule("y", "nextron-valhalla", "uuid-valhalla-b", community="c-2"),
    }

    with pytest.raises(ModuleConfigurationError, match="community_uuid"):
        trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 0
    assert trigger._sekoia.create_rule.call_count == 0


def test_configured_community_filters_scan_and_is_sent(trigger):
    trigger._community_uuid = "c-2"
    trigger.catalog.rules = {
        "x": _catalog_rule("x", "nextron-valhalla", "uuid-valhalla-a", name="A", community="c-1"),
        "y": _catalog_rule("y", "nextron-valhalla", "uuid-valhalla-b", name="B", community="c-2"),
    }

    trigger._sync_once()

    assert trigger._sekoia.iter_rules.call_args.kwargs["community_uuid"] == "c-2"
    # A exists only in c-1 → created in c-2; B updated in c-2.
    created = trigger._sekoia.create_rule.call_args.args[0]
    assert created["name"] == "A"
    assert created["community_uuid"] == "c-2"
    uuid, body = trigger._sekoia.update_rule.call_args.args
    assert uuid == "y"
    assert body["community_uuid"] == "c-2"


def test_scan_ignores_rules_without_marker_tag(trigger):
    """Server rules that lack the ``nextron-valhalla`` marker (unrelated
    user-created rules) are skipped by the scan — not added to id-map."""
    trigger._sekoia.iter_rules.return_value = [
        {"uuid": "foreign-rule", "tags": ["uuid-valhalla-a"]},  # no marker tag
        {"uuid": "another-foreign", "tags": ["attack.t1059"]},
    ]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["server_marker_count"] == 0
    # The Valhalla rules go through the POST branch since nothing in the
    # scan claimed them.
    assert trigger._sekoia.create_rule.call_count == 2


def test_scan_ignores_marker_rules_without_uuid_tag(trigger):
    """Server rules carrying the integration marker but no uuid-* tag
    (legacy rules from before this fix) are skipped by the scan. They
    stay orphaned until the operator deletes them manually — intentional
    per project decision: cleanup is a manual step, not auto-reclaimed."""
    trigger._sekoia.iter_rules.return_value = [
        {"uuid": "legacy-rule", "tags": ["nextron-valhalla", "attack.t1059"]},
    ]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["server_marker_count"] == 0


def test_scan_accepts_plain_string_tags(trigger, data_storage):
    trigger.catalog.rules = {
        "sekoia-A": {
            "uuid": "sekoia-A",
            "name": "A",
            "enabled": False,
            "tags": [{"name": "nextron-valhalla"}, {"name": "uuid-valhalla-a"}],
        },
    }
    trigger._sekoia.iter_rules.side_effect = lambda **_: iter(
        [{**trigger.catalog.rules["sekoia-A"], "tags": ["nextron-valhalla", "uuid-valhalla-a"]}]
    )
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]

    trigger._sync_once()

    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map["valhalla-a"] == "sekoia-A"


def test_posted_body_carries_uuid_tag(trigger):
    """A brand-new rule POST includes the per-rule uuid-* tag so a
    future scan from any playbook can rebuild the mapping."""
    trigger._sync_once()

    posted = trigger._sekoia.create_rule.call_args_list[0].args[0]
    tag_names = posted["tags"]
    assert "nextron-valhalla" in tag_names
    assert "uuid-valhalla-a" in tag_names


# ---------------------------------------------------------------------------
# disable_removed (should-fix #4)
# ---------------------------------------------------------------------------


def _enable_all(trigger):
    for rule in trigger.catalog.rules.values():
        rule["enabled"] = True


def test_disable_removed_dry_run_counts_but_doesnt_disable(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 1
    assert event["newly_disabled"] == 0
    assert trigger.catalog.disabled == []


def test_disable_adds_marker_and_keeps_everything_else(trigger):
    """The disable sends the catalog rule back with ``enabled`` off and the
    marker tag; user settings and content stay as they are."""
    trigger._sync_once()
    _enable_all(trigger)
    rule_a = trigger.catalog.rules["sekoia-A"]
    rule_a.update(event_fields=[{"field": "process.name"}], similarity_strategy=["host.name"], parameters=[{"k": 1}])
    before = dict(rule_a)
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 1
    assert event["newly_disabled"] == 1
    assert trigger.catalog.disabled == ["sekoia-A"]
    after = trigger.catalog.rules["sekoia-A"]
    assert after["enabled"] is False
    assert rule_tag_names(after) == rule_tag_names(before) | {AUTO_DISABLED_TAG}
    unchanged = {k for k in before if k not in ("enabled", "tags")}
    assert {k: after[k] for k in unchanged} == {k: before[k] for k in unchanged}


def test_disable_removed_also_covers_rules_now_below_threshold(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._min_severity = SEVERITY_HIGH
    trigger._disable_removed = True

    trigger._sync_once()

    assert trigger.catalog.disabled == ["sekoia-A"]


def test_already_disabled_is_counted_not_in_to_disable(trigger):
    """Nit: ``to_disable`` only counts rules that are still enabled."""
    trigger._sync_once()  # rules created with enabled=False
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["already_disabled"] == 1
    assert event["to_disable"] == 0
    assert trigger.catalog.disabled == []


def test_already_gone_drops_idmap(trigger, data_storage):
    trigger._sync_once()
    del trigger.catalog.rules["sekoia-A"]
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["already_gone"] == 1
    assert event["to_disable"] == 0
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" not in id_map


def test_reappearing_rule_resumes_update_in_place(trigger, data_storage):
    """A rule disabled on sync N and reappearing on sync N+1 is updated in
    place with its old UUID — the id-map entry was kept."""
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()

    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert "sekoia-A" in [c.args[0] for c in trigger._sekoia.update_rule.call_args_list]
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
    assert trigger.send_event.call_args.kwargs["event"]["re_enabled"] == 1


# ---------------------------------------------------------------------------
# Re-enable after the disable pass (marker tag in the catalog)
# ---------------------------------------------------------------------------


def _auto_disable_a(trigger):
    """Sync, enable everything, then let the disable pass switch off A."""
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False
    assert _marked(trigger) == ["sekoia-A"]


def _puts_for(trigger, uuid) -> int:
    return sum(1 for c in trigger._sekoia.update_rule.call_args_list if c.args[0] == uuid)


def test_dry_run_adds_no_marker(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    trigger._sync_once()

    assert _marked(trigger) == []
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True


def test_returning_rule_is_reenabled_in_its_update(trigger):
    """The re-enable rides on the normal update: one PUT, new content,
    ``enabled`` on, marker gone."""
    _auto_disable_a(trigger)
    trigger._sekoia.update_rule.reset_mock()
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    assert _puts_for(trigger, "sekoia-A") == 1
    assert trigger.catalog.reenabled == ["sekoia-A"]
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
    assert _marked(trigger) == []
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["re_enabled"] == 1
    assert (event["updated"], event["unchanged"]) == (1, 1)


def test_rule_disabled_by_user_is_never_reenabled(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger.catalog.rules["sekoia-A"]["enabled"] = False  # user's choice, no marker

    trigger._sync_once()

    assert trigger.catalog.reenabled == []
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False
    assert trigger.send_event.call_args.kwargs["event"]["re_enabled"] == 0


def test_rule_still_missing_stays_disabled(trigger):
    _auto_disable_a(trigger)

    trigger._sync_once()  # A still not in the feed

    assert trigger.catalog.reenabled == []
    assert _marked(trigger) == ["sekoia-A"]
    assert trigger.send_event.call_args.kwargs["event"]["already_disabled"] == 1


def test_rule_reenabled_by_user_loses_the_marker(trigger):
    """Once the user re-enabled the rule, a later manual disable is theirs."""
    _auto_disable_a(trigger)
    trigger.catalog.rules["sekoia-A"]["enabled"] = True
    trigger._disable_removed = False  # dry-run keeps A enabled while it is missing
    trigger._sync_once()
    assert _marked(trigger) == []

    trigger.catalog.rules["sekoia-A"]["enabled"] = False
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    trigger._sync_once()

    assert trigger.catalog.reenabled == []
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False


def test_rule_back_above_threshold_is_reenabled(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._min_severity = SEVERITY_HIGH
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False

    trigger._min_severity = SEVERITY_MAP["informational"]
    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
    assert trigger.send_event.call_args.kwargs["event"]["re_enabled"] == 1
    assert _marked(trigger) == []


def test_new_configuration_reenables_marked_rules(trigger, data_storage):
    """The record lives in the catalog: a configuration with empty local
    storage re-enables rules another configuration disabled."""
    _auto_disable_a(trigger)
    for f in Path(data_storage).iterdir():
        f.unlink()
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
    assert trigger.catalog.reenabled == ["sekoia-A"]
    assert trigger._sekoia.create_rule.call_count == 2  # only the first sync created


def test_preserved_rule_is_reenabled_without_content_update(trigger):
    _auto_disable_a(trigger)
    trigger.catalog.rules["sekoia-A"]["description"] = "hand-edited"
    trigger._preserve_rule_names = frozenset({"A"})
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    rule_a = trigger.catalog.rules["sekoia-A"]
    assert rule_a["enabled"] is True
    assert rule_a["description"] == "hand-edited"
    assert _marked(trigger) == []
    assert trigger.send_event.call_args.kwargs["event"]["re_enabled"] == 1


def test_unconvertible_rule_is_reenabled_as_is(trigger):
    _auto_disable_a(trigger)
    trigger._valhalla.get_sigma_feed.return_value = [_unmappable_version_of_a(), SAMPLE_RULES[1]]

    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
    assert _marked(trigger) == []
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["re_enabled"] == 1
    assert event["stale"] == 1


def test_reenable_update_not_found_recreates_the_rule(trigger):
    _auto_disable_a(trigger)
    original = trigger._sekoia.update_rule.side_effect

    def gone_for_a(uuid, body):
        if uuid == "sekoia-A":
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        return original(uuid, body)

    trigger._sekoia.update_rule.side_effect = gone_for_a
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["re_enabled"] == 0
    assert event["reenable_failed"] == 0
    assert event["created"] == 1


def test_reenable_error_is_counted_and_retried_next_sync(trigger):
    _auto_disable_a(trigger)
    original = trigger._sekoia.update_rule.side_effect

    def boom_for_a(uuid, body):
        if uuid == "sekoia-A":
            raise RuntimeError("boom")
        return original(uuid, body)

    trigger._sekoia.update_rule.side_effect = boom_for_a
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["reenable_failed"] == 1
    assert event["failed"] == 1
    assert _marked(trigger) == ["sekoia-A"]
    errors = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "error"]
    assert len(errors) == 1

    trigger._sekoia.update_rule.side_effect = original
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True


def test_preserved_reenable_error_is_counted_not_failed(trigger):
    _auto_disable_a(trigger)
    trigger._preserve_rule_names = frozenset({"A"})
    original = trigger._sekoia.update_rule.side_effect

    def boom_for_a(uuid, body):
        if uuid == "sekoia-A":
            raise RuntimeError("boom")
        return original(uuid, body)

    trigger._sekoia.update_rule.side_effect = boom_for_a
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["reenable_failed"] == 1
    assert event["failed"] == 0
    assert event["preserved"] == 1


def test_reenable_conflict_with_another_trigger_is_reported(trigger, data_storage):
    """A rule this configuration re-enabled is disabled again by another
    trigger (simulated) and re-enabled once more: that's a conflict."""
    _auto_disable_a(trigger)
    trigger._disable_removed = False
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    trigger._sync_once()
    state = json.loads((Path(data_storage) / FEED_STATE_FILE).read_text())
    assert state[REENABLED_LAST_RUN_KEY] == ["valhalla-a"]

    rule_a = trigger.catalog.rules["sekoia-A"]  # another trigger disables A again
    rule_a["enabled"] = False
    rule_a["tags"] = [*rule_a["tags"], {"uuid": "t-m", "name": AUTO_DISABLED_TAG}]
    trigger.log = MagicMock()
    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["reenable_conflicts"] == 1
    assert event["re_enabled"] == 1
    warnings = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"]
    assert len(warnings) == 1
    assert "another trigger" in warnings[0].args[0]


def test_no_conflict_without_reenable_in_last_run(trigger):
    _auto_disable_a(trigger)
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    assert trigger.send_event.call_args.kwargs["event"]["reenable_conflicts"] == 0


# ---------------------------------------------------------------------------
# Disable-pass error paths
# ---------------------------------------------------------------------------


def _drop_a_from_feed(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]


def _fail_disables(trigger, exc):
    """Make every disabling PUT (``enabled`` off) raise ``exc``."""
    original = trigger._sekoia.update_rule.side_effect

    def update(uuid, body):
        if body.get("enabled") is False:
            raise exc
        return original(uuid, body)

    trigger._sekoia.update_rule.side_effect = update


def test_disable_not_found_counts_already_gone_and_drops_idmap(trigger, data_storage):
    _drop_a_from_feed(trigger)
    _fail_disables(trigger, SekoiaRuleNotFoundError("gone", status_code=404))

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["already_gone"] == 1
    assert event["newly_disabled"] == 0
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" not in id_map


def test_disable_error_counts_failed_and_logs_once(trigger, data_storage):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._min_severity = SEVERITY_MAP["critical"]  # both rules become candidates
    _fail_disables(trigger, RuntimeError("boom"))
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["disable_failed"] == 2
    assert event["newly_disabled"] == 0
    errors = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "error"]
    assert len(errors) == 1
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert set(id_map) == {"valhalla-a", "valhalla-b"}
    assert _marked(trigger) == []


def test_stop_during_disable_pass_reports_interrupted(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._min_severity = SEVERITY_MAP["critical"]  # both rules become candidates
    original = trigger._sekoia.update_rule.side_effect

    def disable_then_stop(uuid, body):
        original(uuid, body)
        if body.get("enabled") is False:
            trigger._stop_event.set()

    trigger._sekoia.update_rule.side_effect = disable_then_stop

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["disable_skipped_reason"] == "interrupted"
    assert event["newly_disabled"] == 1
    assert len(trigger.catalog.disabled) == 1
    assert len(_marked(trigger)) == 1


# ---------------------------------------------------------------------------
# Disable-pass safety (B2)
# ---------------------------------------------------------------------------


@pytest.fixture
def guarded(trigger, monkeypatch):
    """The trigger with the real feed-shrink guard (the default fixture
    disables it so ordinary tests can drop rules from a 2-rule feed)."""
    from nextron_valhalla_sigma_rules_modules.triggers import sync_sigma_rules_catalog as sync_mod

    monkeypatch.setattr(sync_mod, "MAX_FEED_SHRINK_RATIO", 0.2)
    feed = [{"id": f"v-{i}", "filename": f"{i}.yml", "content": _rule_yaml(f"R{i}")} for i in range(10)]
    trigger._valhalla.get_sigma_feed.return_value = list(feed)
    trigger._disable_removed = True
    trigger._sync_once()
    _enable_all(trigger)
    trigger.feed = feed
    return trigger


def test_empty_feed_skips_disable_pass(guarded):
    guarded._valhalla.get_sigma_feed.return_value = []

    guarded._sync_once()

    event = guarded.send_event.call_args.kwargs["event"]
    assert event["disable_skipped_reason"] == "empty_feed"
    assert guarded.catalog.disabled == []


def test_feed_shrinking_beyond_ratio_skips_disable_pass(guarded):
    guarded._valhalla.get_sigma_feed.return_value = guarded.feed[:5]

    guarded._sync_once()

    event = guarded.send_event.call_args.kwargs["event"]
    assert event["disable_skipped_reason"] == "feed_shrank"
    assert guarded.catalog.disabled == []


def test_small_shrink_still_disables(guarded):
    guarded._valhalla.get_sigma_feed.return_value = guarded.feed[:9]

    guarded._sync_once()

    event = guarded.send_event.call_args.kwargs["event"]
    assert event["disable_skipped_reason"] == ""
    assert event["newly_disabled"] == 1


def test_persistent_shrink_is_accepted_after_confirm_runs(guarded, data_storage):
    from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import FEED_SHRINK_CONFIRM_RUNS

    guarded._valhalla.get_sigma_feed.return_value = guarded.feed[:5]
    for _ in range(FEED_SHRINK_CONFIRM_RUNS - 1):
        guarded._sync_once()
        assert guarded.send_event.call_args.kwargs["event"]["disable_skipped_reason"] == "feed_shrank"

    guarded._sync_once()

    event = guarded.send_event.call_args.kwargs["event"]
    assert event["disable_skipped_reason"] == ""
    assert event["newly_disabled"] == 5
    state = json.loads((Path(data_storage) / FEED_STATE_FILE).read_text())
    assert state["reference_size"] == 5
    assert state["shrink_runs"] == 0


def test_shrink_counter_resets_when_feed_recovers(guarded, data_storage):
    guarded._valhalla.get_sigma_feed.return_value = guarded.feed[:5]
    guarded._sync_once()
    guarded._valhalla.get_sigma_feed.return_value = list(guarded.feed)
    guarded._sync_once()

    state = json.loads((Path(data_storage) / FEED_STATE_FILE).read_text())
    assert state == {"reference_size": 10, "shrink_runs": 0}


def test_unparsable_rule_is_not_a_disable_candidate(trigger):
    """A rule whose YAML fails to parse this run has an unknown status; it
    must not be disabled as "below threshold"."""
    trigger._sync_once()
    _enable_all(trigger)
    trigger._disable_removed = True
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "valhalla-a", "filename": "a.yml", "content": "title: [unclosed"},
        SAMPLE_RULES[1],
    ]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 0
    assert trigger.catalog.disabled == []


# ---------------------------------------------------------------------------
# ATT&CK related_object_refs (suggestion)
# ---------------------------------------------------------------------------


def test_attack_technique_ids_parsing():
    tags = ["attack.execution", "attack.t1059.001", "ATTACK.T1027", "attack.t1059.001", "cve.2021-1", 7]
    assert _attack_technique_ids(tags) == ["T1059.001", "T1027"]


def test_related_object_refs_set_from_technique_tags(trigger):
    trigger._valhalla.get_sigma_feed.return_value = [
        {
            "id": "v-t",
            "filename": "t.yml",
            "content": _rule_yaml("T") + "tags:\n  - attack.t1059.001\n  - attack.t9999\n",
        }
    ]
    trigger._sekoia.find_attack_pattern.side_effect = lambda t: "attack-pattern--1" if t == "T1059.001" else None

    trigger._sync_once()

    body = trigger._sekoia.create_rule.call_args.args[0]
    assert body["related_object_refs"] == ["attack-pattern--1"]


def test_attack_lookups_are_cached_and_failures_tolerated(trigger):
    rules = [
        {"id": f"v-{i}", "filename": f"{i}.yml", "content": _rule_yaml(f"T{i}") + "tags:\n  - attack.t1059\n"}
        for i in range(3)
    ]
    trigger._valhalla.get_sigma_feed.return_value = rules
    trigger._sekoia.find_attack_pattern.side_effect = RuntimeError("inthreat down")
    trigger.log = MagicMock()

    trigger._sync_once()

    assert trigger._sekoia.find_attack_pattern.call_count == 1
    assert trigger._sekoia.create_rule.call_count == 3
    assert "related_object_refs" not in trigger._sekoia.create_rule.call_args.args[0]

    # A failure is not cached: the next sync asks again. A real answer
    # ("no such technique") is cached.
    trigger._sekoia.find_attack_pattern.side_effect = None
    trigger._sekoia.find_attack_pattern.return_value = None
    trigger._sync_once()
    assert trigger._sekoia.find_attack_pattern.call_count == 2
    trigger._sync_once()
    assert trigger._sekoia.find_attack_pattern.call_count == 2


def _attack_feed(trigger):
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "valhalla-a", "filename": "a.yml", "content": _rule_yaml("A") + "tags:\n  - attack.t1059\n"}
    ]


def test_failed_attack_lookup_keeps_the_link_and_is_retried(trigger):
    """Should-fix (round 5): one transient lookup error must not remove the
    rule's ATT&CK link until the trigger restarts."""
    _attack_feed(trigger)
    trigger._sekoia.find_attack_pattern.return_value = "attack-pattern--1"
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["related_object_refs"] == ["attack-pattern--1"]

    trigger._sekoia.find_attack_pattern.side_effect = SekoiaAPIError("HTTP 502", status_code=502)
    trigger._attack_cache.clear()  # as after a restart: the technique must be looked up
    trigger.log = MagicMock()
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["related_object_refs"] == ["attack-pattern--1"]
    assert trigger._sekoia.update_rule.call_count == 0  # nothing to change

    trigger._sekoia.find_attack_pattern.side_effect = None
    trigger._sync_once()
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["related_object_refs"] == ["attack-pattern--1"]
    assert trigger._sekoia.find_attack_pattern.call_count == 3  # 1st sync, failure, retry


def test_failed_attack_lookup_keeps_the_link_on_update(trigger):
    _attack_feed(trigger)
    trigger._sekoia.find_attack_pattern.return_value = "attack-pattern--1"
    trigger._sync_once()
    trigger.catalog.rules["sekoia-A"]["related_object_refs"] = ["attack-pattern--1", "malware--user"]
    _outdate(trigger)
    trigger._sekoia.find_attack_pattern.side_effect = RuntimeError("inthreat down")
    trigger._attack_cache.clear()
    trigger.log = MagicMock()

    trigger._sync_once()

    rule = trigger.catalog.rules["sekoia-A"]
    assert rule["description"] != "outdated"  # the update went through
    assert rule["related_object_refs"] == ["attack-pattern--1", "malware--user"]


def test_rule_created_during_lookup_outage_is_linked_next_sync(trigger):
    _attack_feed(trigger)
    trigger._sekoia.find_attack_pattern.side_effect = SekoiaAPIError("HTTP 502", status_code=502)
    trigger.log = MagicMock()
    trigger._sync_once()
    assert not trigger.catalog.rules["sekoia-A"].get("related_object_refs")

    trigger._sekoia.find_attack_pattern.side_effect = None
    trigger._sekoia.find_attack_pattern.return_value = "attack-pattern--1"
    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["related_object_refs"] == ["attack-pattern--1"]


def test_attack_lookups_stop_after_permission_error(trigger):
    """A key without intelligence read access gets one warning, not one per
    technique, and the sync continues without refs."""
    rules = [
        {"id": f"v-{i}", "filename": f"{i}.yml", "content": _rule_yaml(f"T{i}") + f"tags:\n  - attack.t10{i}0\n"}
        for i in range(5)
    ]
    trigger._valhalla.get_sigma_feed.return_value = rules
    trigger._sekoia.find_attack_pattern.side_effect = SekoiaAPIError("HTTP 403", status_code=403)
    trigger.log = MagicMock()

    trigger._sync_once()

    assert trigger._sekoia.find_attack_pattern.call_count == 1
    assert trigger._sekoia.create_rule.call_count == 5
    warnings = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"]
    assert len(warnings) == 1
    assert "ATT&CK technique linking disabled" in warnings[0].args[0]


# ---------------------------------------------------------------------------
# User settings survive updates (#1)
# ---------------------------------------------------------------------------

USER_SETTINGS = {
    "entities": [{"uuid": "e-1"}],
    "all_entities": False,
    "assets": [{"uuid": "asset-1"}],
    "all_assets": False,
    "parameters": [{"name": "p", "value": 1}],
    "event_fields": [{"field": "process.name"}],
    "similarity_strategy": ["host.name"],
}


def test_update_keeps_user_settings(trigger):
    trigger._sync_once()
    _outdate(trigger)
    trigger.catalog.rules["sekoia-A"].update(USER_SETTINGS)

    trigger._sync_once()

    rule_a = trigger.catalog.rules["sekoia-A"]
    assert {k: rule_a[k] for k in USER_SETTINGS} == USER_SETTINGS


def test_update_sends_entities_and_datasources_as_uuids(trigger):
    """GET returns them as objects; PUT expects UUIDs (reviewer, round 3)."""
    trigger._sync_once()
    _outdate(trigger)
    trigger.catalog.rules["sekoia-A"].update(
        entities=[{"uuid": "e-1", "name": "HQ"}], all_entities=False, datasources=[{"uuid": "d-1", "name": "Sysmon"}]
    )

    trigger._sync_once()

    body = next(c.args[1] for c in reversed(trigger._sekoia.update_rule.call_args_list) if c.args[0] == "sekoia-A")
    assert body["entities"] == ["e-1"]
    assert body["datasources"] == ["d-1"]
    assert body["all_entities"] is False


def test_update_still_replaces_valhalla_content(trigger):
    trigger._sync_once()
    trigger.catalog.rules["sekoia-A"]["description"] = "hand-edited"
    trigger.catalog.rules["sekoia-A"]["name"] = "renamed"

    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["name"] == "A"
    assert trigger.catalog.rules["sekoia-A"]["description"] != "hand-edited"


def test_update_keeps_user_threats_and_replaces_attack_links(trigger):
    trigger._sekoia.find_attack_pattern.return_value = "attack-pattern--new"
    trigger._valhalla.get_sigma_feed.return_value = [
        {"id": "valhalla-a", "filename": "a.yml", "content": _rule_yaml("A") + "tags:\n  - attack.t1059\n"}
    ]
    trigger._sync_once()
    _outdate(trigger)
    trigger.catalog.rules["sekoia-A"]["related_object_refs"] = ["attack-pattern--old", "malware--user"]

    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["related_object_refs"] == ["attack-pattern--new", "malware--user"]


def test_update_keeps_attack_links_when_lookups_are_off(trigger):
    trigger._sync_once()
    _outdate(trigger)
    trigger.catalog.rules["sekoia-A"]["related_object_refs"] = ["attack-pattern--old", "malware--user"]
    trigger._attack_cache = {}
    trigger._attack_lookups_enabled = False

    trigger._sync_once()

    assert trigger.catalog.rules["sekoia-A"]["related_object_refs"] == ["attack-pattern--old", "malware--user"]


# ---------------------------------------------------------------------------
# Rules kept at an older version (#4)
# ---------------------------------------------------------------------------


def test_unconvertible_new_version_counts_as_stale_and_keeps_rule(trigger):
    trigger._sync_once()
    before = dict(trigger.catalog.rules["sekoia-A"])
    trigger._valhalla.get_sigma_feed.return_value = [_unmappable_version_of_a(), SAMPLE_RULES[1]]
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["stale"] == 1
    assert event["skipped_unmapped"] == 1
    assert trigger.catalog.rules["sekoia-A"] == before
    infos = [c.args[0] for c in trigger.log.call_args_list if "older version" in c.args[0]]
    assert len(infos) == 1 and "'A'" in infos[0]


def test_new_rule_that_cannot_be_converted_is_not_stale(trigger):
    trigger._valhalla.get_sigma_feed.return_value = [_unmappable_version_of_a()]

    trigger._sync_once()

    assert trigger.send_event.call_args.kwargs["event"]["stale"] == 0


def test_malformed_imported_rule_counts_as_stale(trigger, monkeypatch):
    trigger._sync_once()
    _explode_on_rule_a(monkeypatch)

    trigger._sync_once()

    assert trigger.send_event.call_args.kwargs["event"]["stale"] == 1


# ---------------------------------------------------------------------------
# Preserve list as a text field (#2)
# ---------------------------------------------------------------------------


def test_preserve_rule_names_is_a_text_field_in_the_manifest():
    manifest = json.loads((Path(__file__).parent.parent / "trigger_sync_sigma_rules_catalog.json").read_text())
    arg = manifest["arguments"]["properties"]["preserve_rule_names"]
    assert arg["type"] == "string"
    assert arg["default"] == ""
    results = manifest["results"]["properties"]
    assert {"stale", "reenable_conflicts", "re_enabled", "reenable_failed"} <= set(results)


def test_run_reads_preserve_text(monkeypatch, data_storage):
    from nextron_valhalla_sigma_rules_modules.triggers import sync_sigma_rules_catalog as sync_mod

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)
    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"preserve_rule_names": "A\nuuid-123; B"}
    t._stop_event.set()

    t.run()

    assert t._preserve_rule_names == frozenset({"A", "uuid-123", "B"})


def _put_bodies(trigger, uuid) -> list[dict]:
    return [c.args[1] for c in trigger._sekoia.update_rule.call_args_list if c.args[0] == uuid]


# ---------------------------------------------------------------------------
# Round 4: scan miss in the disable pass (must-fix 1)
# ---------------------------------------------------------------------------


def _untag(trigger, uuid):
    rule = trigger.catalog.rules[uuid]
    rule["tags"] = [t for t in rule["tags"] if t["name"] != "nextron-valhalla"]


def test_untagged_rule_dropped_from_feed_is_disabled_not_forgotten(trigger, data_storage):
    trigger._sync_once()
    _enable_all(trigger)
    _untag(trigger, "sekoia-A")  # README: removing the tag is safe
    trigger._disable_removed = True
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["newly_disabled"] == 1
    assert event["already_gone"] == 0
    assert trigger.catalog.disabled == ["sekoia-A"]
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map["valhalla-a"] == "sekoia-A"


def test_scan_miss_confirmed_gone_in_disable_pass(trigger, data_storage):
    trigger._sync_once()
    _untag(trigger, "sekoia-A")
    original = trigger._sekoia.get_rule.side_effect

    def gone_for_a(uuid):
        if uuid == "sekoia-A":
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        return original(uuid)

    trigger._sekoia.get_rule.side_effect = gone_for_a
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    trigger._sync_once()

    assert trigger.send_event.call_args.kwargs["event"]["already_gone"] == 1
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" not in id_map


def test_scan_miss_lookup_error_in_disable_pass_keeps_mapping(trigger, data_storage):
    trigger._sync_once()
    _untag(trigger, "sekoia-A")
    trigger._sekoia.get_rule.side_effect = SekoiaAPIError("HTTP 403", status_code=403)
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    trigger._sync_once()

    assert trigger.send_event.call_args.kwargs["event"]["disable_failed"] == 1
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map["valhalla-a"] == "sekoia-A"


# ---------------------------------------------------------------------------
# Round 4: unchanged rules are not PUT (should-fix 2)
# ---------------------------------------------------------------------------


def test_removed_false_positives_still_trigger_an_update(trigger):
    with_fp = {"id": "valhalla-a", "filename": "a.yml", "content": _rule_yaml("A") + "falsepositives:\n  - Admins\n"}
    trigger._valhalla.get_sigma_feed.return_value = [with_fp]
    trigger._sync_once()
    assert trigger.catalog.rules["sekoia-A"]["false_positives"] == "Admins"
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]

    trigger._sync_once()

    assert len(_put_bodies(trigger, "sekoia-A")) == 1
    assert trigger.catalog.rules["sekoia-A"]["false_positives"] is None


def test_tag_order_does_not_count_as_a_change(trigger):
    trigger._sync_once()
    rule_a = trigger.catalog.rules["sekoia-A"]
    rule_a["tags"] = list(reversed(rule_a["tags"]))
    trigger._sekoia.update_rule.reset_mock()

    trigger._sync_once()

    assert _put_bodies(trigger, "sekoia-A") == []


def test_stale_marker_on_enabled_rule_forces_an_update(trigger):
    trigger._sync_once()
    rule_a = trigger.catalog.rules["sekoia-A"]
    rule_a["enabled"] = True
    rule_a["tags"] = [*rule_a["tags"], {"uuid": "t-m", "name": AUTO_DISABLED_TAG}]

    trigger._sync_once()

    assert len(_put_bodies(trigger, "sekoia-A")) == 1
    assert _marked(trigger) == []
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True


# ---------------------------------------------------------------------------
# Round 4: re-read before sending a whole rule back (should-fix 3)
# ---------------------------------------------------------------------------


def _edit_on_get(trigger, uuid, **changes):
    """Simulate a user edit saved after the scan: applied right before the
    integration re-reads the rule."""
    original = trigger._sekoia.get_rule.side_effect

    def get(u):
        if u == uuid:
            trigger.catalog.rules[uuid].update(changes)
        return original(u)

    trigger._sekoia.get_rule.side_effect = get


def test_disable_keeps_an_edit_made_during_the_sync(trigger):
    _drop_a_from_feed(trigger)
    _edit_on_get(trigger, "sekoia-A", event_fields=[{"field": "edited.during.sync"}])

    trigger._sync_once()

    rule_a = trigger.catalog.rules["sekoia-A"]
    assert rule_a["enabled"] is False
    assert rule_a["event_fields"] == [{"field": "edited.during.sync"}]


def test_rule_disabled_by_user_during_the_sync_is_not_touched(trigger):
    _drop_a_from_feed(trigger)
    _edit_on_get(trigger, "sekoia-A", enabled=False)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["already_disabled"] == 1
    assert event["newly_disabled"] == 0
    assert _marked(trigger) == []


def test_reenable_as_is_keeps_an_edit_made_during_the_sync(trigger):
    _auto_disable_a(trigger)
    trigger._preserve_rule_names = frozenset({"A"})
    _edit_on_get(trigger, "sekoia-A", parameters=[{"name": "p", "value": 2}])
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    rule_a = trigger.catalog.rules["sekoia-A"]
    assert rule_a["enabled"] is True
    assert rule_a["parameters"] == [{"name": "p", "value": 2}]


def test_reenable_as_is_skips_a_rule_the_user_enabled_during_the_sync(trigger):
    _auto_disable_a(trigger)
    trigger._preserve_rule_names = frozenset({"A"})
    _edit_on_get(trigger, "sekoia-A", enabled=True)
    trigger._sekoia.update_rule.reset_mock()
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["re_enabled"] == 0
    assert event["reenable_failed"] == 0


# ---------------------------------------------------------------------------
# Round 4: effort and deprecation message are user-owned (should-fix 4)
# ---------------------------------------------------------------------------


def test_update_keeps_effort_and_deprecation_but_resets_alert_type(trigger):
    trigger._sync_once()
    _outdate(trigger)
    rule_a = trigger.catalog.rules["sekoia-A"]
    generated_alert_type = rule_a["alert_type"]["uuid"]
    rule_a.update(effort=4, deprecation_message="Use rule X", alert_type={"uuid": "user-choice"})

    trigger._sync_once()

    rule_a = trigger.catalog.rules["sekoia-A"]
    assert rule_a["effort"] == 4
    assert rule_a["deprecation_message"] == "Use rule X"
    assert rule_a["alert_type"]["uuid"] == generated_alert_type


# ---------------------------------------------------------------------------
# Round 4: nits
# ---------------------------------------------------------------------------


def test_rules_without_id_are_counted(trigger):
    trigger._valhalla.get_sigma_feed.return_value = [
        {"filename": "x.yml", "content": _rule_yaml("X")},
        SAMPLE_RULES[0],
    ]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_no_id"] == 1
    assert event["created"] == 1


def test_config_error_from_the_sync_stops_run(monkeypatch, data_storage):
    """Several communities without ``community_uuid`` is a configuration
    error: run() lets it through to the SDK instead of retrying."""
    from nextron_valhalla_sigma_rules_modules.triggers import sync_sigma_rules_catalog as sync_mod

    monkeypatch.setattr(sync_mod, "ValhallaClient", MagicMock())
    monkeypatch.setattr(sync_mod, "SekoiaClient", MagicMock())
    monkeypatch.setattr(sync_mod.SyncSigmaRulesCatalog, "_validate_alert_types", lambda self: None)
    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"frequency": 3600}
    t._sync_once = MagicMock(side_effect=ModuleConfigurationError("several communities"))

    with pytest.raises(ModuleConfigurationError):
        t.run()
    assert t._sync_once.call_count == 1


def test_drop_marker_failure_is_logged_and_sync_continues(trigger):
    _auto_disable_a(trigger)
    trigger.catalog.rules["sekoia-A"]["enabled"] = True  # user re-enabled it
    trigger._disable_removed = False
    original = trigger._sekoia.update_rule.side_effect

    def boom_for_a(uuid, body):
        if uuid == "sekoia-A":
            raise RuntimeError("boom")
        return original(uuid, body)

    trigger._sekoia.update_rule.side_effect = boom_for_a
    trigger.log = MagicMock()

    trigger._sync_once()

    warnings = [c.args[0] for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"]
    assert any("Could not remove" in w for w in warnings)
    assert _marked(trigger) == ["sekoia-A"]
    trigger.send_event.assert_called()


def test_stale_rule_with_stale_marker_loses_the_marker(trigger):
    _auto_disable_a(trigger)
    trigger.catalog.rules["sekoia-A"]["enabled"] = True  # user re-enabled it
    trigger._valhalla.get_sigma_feed.return_value = [_unmappable_version_of_a(), SAMPLE_RULES[1]]

    trigger._sync_once()

    assert _marked(trigger) == []
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
    assert trigger.send_event.call_args.kwargs["event"]["stale"] == 1


def test_rule_gone_before_disable_counts_already_gone(trigger, data_storage):
    _drop_a_from_feed(trigger)
    original = trigger._sekoia.get_rule.side_effect

    def gone_for_a(uuid):
        if uuid == "sekoia-A":
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        return original(uuid)

    trigger._sekoia.get_rule.side_effect = gone_for_a

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert (event["already_gone"], event["newly_disabled"]) == (1, 0)
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" not in id_map


def test_reread_error_before_disable_counts_failed(trigger):
    _drop_a_from_feed(trigger)
    trigger._sekoia.get_rule.side_effect = SekoiaAPIError("HTTP 500", status_code=500)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert (event["to_disable"], event["disable_failed"], event["newly_disabled"]) == (1, 1, 0)
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is True
