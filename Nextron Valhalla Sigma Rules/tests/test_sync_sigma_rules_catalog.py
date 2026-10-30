import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaClient,
    SekoiaRuleNotFoundError,
)
from nextron_valhalla_sigma_rules_modules.sigma_mapper import SEVERITY_MAP
from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import (
    FEED_STATE_FILE,
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


class FakeCatalog:
    """In-memory stand-in for the Sekoia Rules Catalog. Rules created by one
    sync are returned by the next sync's scan, like on a real tenant."""

    def __init__(self):
        self.rules: dict[str, dict] = {}

    def create(self, body):
        uuid = f"sekoia-{body['name']}"
        while uuid in self.rules:
            uuid += "+"
        self.rules[uuid] = {
            "uuid": uuid,
            "name": body["name"],
            "enabled": body["enabled"],
            "community_uuid": body.get("community_uuid", "c-1"),
            "tags": [{"uuid": f"t-{t}", "name": t} for t in body.get("tags", [])],
        }
        return uuid

    def update(self, uuid, body):
        if uuid not in self.rules:
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        self.rules[uuid].update(name=body["name"], enabled=body["enabled"])

    def disable(self, uuid):
        if uuid not in self.rules:
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        self.rules[uuid]["enabled"] = False

    def iter_rules(self, tag_name=None, community_uuid=None, **_):
        for rule in list(self.rules.values()):
            names = {t["name"] for t in rule["tags"]}
            if tag_name and tag_name not in names:
                continue
            if community_uuid and rule.get("community_uuid") != community_uuid:
                continue
            yield dict(rule)


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
    t._sekoia.update_rule.side_effect = catalog.update
    t._sekoia.disable_rule.side_effect = catalog.disable
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


def test_second_sync_puts_existing_rules(trigger):
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 2
    trigger.send_event.assert_called_once()
    event = trigger.send_event.call_args.kwargs["event"]
    assert event == {
        "created": 0,
        "updated": 2,
        "preserved": 0,
        "failed": 0,
        "skipped_unmapped": 0,
        "skipped_filter": 0,
        "total_rules": 2,
        "top_unmapped": {},
        "server_marker_count": 2,
        "duplicate_markers": 0,
        "local_overridden": 0,
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
    assert trigger._sekoia.update_rule.call_count == 2

    calls_by_uuid = {call.args[0]: call.args[1] for call in trigger._sekoia.update_rule.call_args_list}
    # Sekoia UUID is the one seeded on the first sync (from the id-map).
    assert "sekoia-A" in calls_by_uuid
    updated_body = calls_by_uuid["sekoia-A"]
    assert "A-updated" in updated_body["payload"]
    # Sanity: the untouched rule still ships its original selection value.
    assert "B" in calls_by_uuid["sekoia-B"]["payload"]


def test_third_sync_only_posts_new_rule(trigger):
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()

    new_rule = {"id": "valhalla-c", "filename": "c.yml", "content": _rule_yaml("C")}
    trigger._valhalla.get_sigma_feed.return_value = [*SAMPLE_RULES, new_rule]

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 1
    assert trigger._sekoia.update_rule.call_count == 2
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
    """A mapped UUID absent from the catalog scan is stale (the rule was
    deleted in Sekoia): drop it and create the rule again, no PUT."""
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
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.side_effect = SekoiaRuleNotFoundError("gone", status_code=404)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 2
    assert event["updated"] == 0


def test_update_403_counts_as_failed_not_stale(trigger, data_storage):
    """S1: a 403 on PUT is a failure — the mapping is kept and nothing is
    re-created (that would duplicate the rule on every run)."""
    from nextron_valhalla_sigma_rules_modules.sekoia_client import SekoiaAPIError

    trigger._sync_once()
    before = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.side_effect = SekoiaAPIError("HTTP 403", status_code=403)

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["failed"] == 2
    assert event["created"] == 0
    assert trigger._sekoia.create_rule.call_count == 0
    assert json.loads((Path(data_storage) / UUID_MAP_FILE).read_text()) == before


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
    with pytest.raises(ValueError, match="min_sigma_level"):
        trigger.run()


def test_invalid_min_status_raises(trigger):
    trigger.configuration = {"min_sigma_status": "bogus"}
    trigger.module = MagicMock()
    with pytest.raises(ValueError, match="min_sigma_status"):
        trigger.run()


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
    with pytest.raises(ValueError, match="do not exist on this Sekoia tenant"):
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


def test_normalize_names_non_list_returns_empty():
    assert _normalize_names(None) == frozenset()
    assert _normalize_names("A rule") == frozenset()
    assert _normalize_names({"A": True}) == frozenset()


def test_normalize_names_drops_non_string_entries():
    assert _normalize_names(["A", 123, None, "B"]) == frozenset({"A", "B"})


def test_preserve_rule_names_skips_update_when_server_name_matches(trigger):
    """A rule whose server-side name appears in the configured list is NOT
    PUT with Valhalla content; the counter increments."""
    trigger._sync_once()  # populate id_map; both rules then exist
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
    assert trigger._sekoia.disable_rule.call_args.args[0] == "sekoia-A"
    assert trigger.catalog.rules["sekoia-A"]["enabled"] is False


def test_preserve_entry_matches_uuid_tag(trigger):
    """Nit: names aren't unique, so an entry may also be the rule's
    ``uuid-<valhalla_id>`` tag."""
    trigger._sync_once()
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

    with pytest.raises(RuntimeError, match="community_uuid"):
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
    assert trigger._sekoia.disable_rule.call_count == 0


def test_disable_removed_uses_dedicated_endpoint(trigger):
    """S13: disabling goes through ``disable_rule`` — no rebuilt PUT body."""
    trigger._sync_once()
    _enable_all(trigger)
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True
    trigger._sekoia.update_rule.reset_mock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 1
    assert event["newly_disabled"] == 1
    assert trigger._sekoia.disable_rule.call_args.args == ("sekoia-A",)
    assert [c.args[0] for c in trigger._sekoia.update_rule.call_args_list] == ["sekoia-B"]


def test_disable_removed_also_covers_rules_now_below_threshold(trigger):
    trigger._sync_once()
    _enable_all(trigger)
    trigger._min_severity = SEVERITY_HIGH
    trigger._disable_removed = True

    trigger._sync_once()

    assert trigger._sekoia.disable_rule.call_args.args == ("sekoia-A",)


def test_already_disabled_is_counted_not_in_to_disable(trigger):
    """Nit: ``to_disable`` only counts rules that are still enabled."""
    trigger._sync_once()  # rules created with enabled=False
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["already_disabled"] == 1
    assert event["to_disable"] == 0
    assert trigger._sekoia.disable_rule.call_count == 0


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
    assert guarded._sekoia.disable_rule.call_count == 0


def test_feed_shrinking_beyond_ratio_skips_disable_pass(guarded):
    guarded._valhalla.get_sigma_feed.return_value = guarded.feed[:5]

    guarded._sync_once()

    event = guarded.send_event.call_args.kwargs["event"]
    assert event["disable_skipped_reason"] == "feed_shrank"
    assert guarded._sekoia.disable_rule.call_count == 0


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
    assert state == {"reference_size": 5, "shrink_runs": 0}


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
    assert trigger._sekoia.disable_rule.call_count == 0


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


def test_attack_lookups_stop_after_permission_error(trigger):
    """A key without intelligence read access gets one warning, not one per
    technique, and the sync continues without refs."""
    from nextron_valhalla_sigma_rules_modules.sekoia_client import SekoiaAPIError

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
