import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nextron_valhalla_sigma_rules_modules.sekoia_client import (
    SekoiaRuleNotFoundError,
)
from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import (
    UUID_MAP_FILE,
    SyncSigmaRulesCatalog,
    _disable_body_from_server,
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


SAMPLE_RULES = [
    {"id": "valhalla-a", "filename": "a.yml", "content": _rule_yaml("A")},
    {"id": "valhalla-b", "filename": "b.yml", "content": _rule_yaml("B", "high")},
]


@pytest.fixture
def trigger(data_storage):
    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t._valhalla = MagicMock()
    t._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    t._sekoia = MagicMock()
    t._sekoia.create_rule.side_effect = lambda body: f"sekoia-{body['name']}"
    # Default server state for the PUT pre-flight GET: rule is enabled=False
    # (matches _enabled=False default so update-path tests see the same
    # body["enabled"] value the pre-get-rule code used to send).
    t._sekoia.get_rule.return_value = {"enabled": False}
    # Empty catalog scan by default: no server-side marker-tagged rules.
    # Tests exercising the scan override this per-case.
    t._sekoia.iter_rules.return_value = []
    t._enabled = False
    t._disable_removed = False
    t._preserve_rule_names = frozenset()
    # Permissive defaults matching the new-user experience: every rule
    # with status experimental+ and any Sigma level passes.
    t._min_severity = 10  # informational
    t._max_status_effort = 3  # experimental
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
        "server_marker_count": 0,
        "duplicate_markers": 0,
        "local_overridden": 0,
        "to_disable": 0,
        "newly_disabled": 0,
        "already_disabled": 0,
        "already_gone": 0,
        "disable_failed": 0,
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

    calls_by_uuid = {
        call.args[0]: call.args[1]
        for call in trigger._sekoia.update_rule.call_args_list
    }
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
    trigger._valhalla.get_sigma_feed.return_value = SAMPLE_RULES + [new_rule]

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


def test_valhalla_feed_error_does_not_crash(trigger):
    trigger._valhalla.get_sigma_feed.side_effect = RuntimeError("feed down")

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    trigger.send_event.assert_not_called()


def test_stale_id_map_entry_triggers_repost(trigger, data_storage):
    """When PUT returns 403/404 (rule was deleted server-side but our
    id-map still points at it), the trigger drops the stale entry and
    POSTs the rule as new."""
    # First sync populates the map with fake UUIDs.
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    # Simulate server-side deletion: every PUT returns 403 AU202.
    trigger._sekoia.update_rule.side_effect = SekoiaRuleNotFoundError(
        "PUT ... returned HTTP 403: AU202", status_code=403
    )
    # POST succeeds with a new UUID per body.
    trigger._sekoia.create_rule.side_effect = lambda body: f"sekoia-new-{body['name']}"

    trigger._sync_once()

    # Both rules attempted PUT (failed, stale) then fell back to POST.
    assert trigger._sekoia.update_rule.call_count == 2
    assert trigger._sekoia.create_rule.call_count == 2

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 2
    assert event["updated"] == 0
    assert event["failed"] == 0

    # New UUIDs persisted; stale ones dropped.
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map == {
        "valhalla-a": "sekoia-new-A",
        "valhalla-b": "sekoia-new-B",
    }


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
    trigger._max_status_effort = 1  # stable
    # Both sample rules are stable — nothing filtered by status.
    # Now feed one with a lower status.
    trigger._valhalla.get_sigma_feed.return_value = SAMPLE_RULES + [
        {
            "id": "valhalla-exp",
            "filename": "exp.yml",
            "content": _rule_yaml("Experimental", status="experimental"),
        },
    ]

    trigger._sync_once()

    # Both sample rules imported, the experimental one is filtered.
    assert trigger._sekoia.create_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["skipped_filter"] == 1


def test_stale_put_then_failed_post_counts_as_failed(trigger):
    """If the POST fallback also fails, the rule counts as failed and the
    id-map is not repopulated."""
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._sekoia.update_rule.side_effect = SekoiaRuleNotFoundError(
        "gone", status_code=403
    )
    trigger._sekoia.create_rule.side_effect = RuntimeError("POST also broken")

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["created"] == 0
    assert event["updated"] == 0
    assert event["failed"] == 2


# ---------------------------------------------------------------------------
# Preserve user's ``enabled`` choice on update (blocker #1 — GET-then-PUT)
# ---------------------------------------------------------------------------


def test_update_preserves_user_disabled(trigger):
    """A rule the user disabled in the catalog must stay disabled on
    the next sync even if the trigger config has enabled=True."""
    trigger._enabled = True
    trigger._sync_once()  # populate id_map with POSTs
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger._sekoia.get_rule.return_value = {"enabled": False}

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 2
    for call in trigger._sekoia.update_rule.call_args_list:
        body = call.args[1]
        assert body["enabled"] is False


def test_update_preserves_user_enabled(trigger):
    """A rule the user enabled must stay enabled even if the trigger's
    default is enabled=False."""
    trigger._enabled = False
    trigger._sync_once()
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger._sekoia.get_rule.return_value = {"enabled": True}

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 2
    for call in trigger._sekoia.update_rule.call_args_list:
        body = call.args[1]
        assert body["enabled"] is True


def test_get_rule_404_falls_back_to_repost(trigger, data_storage):
    """A GET that returns 404 (rule deleted server-side) must drop the
    id-map entry and POST the rule as new — same fallback path as a 404
    on PUT. Fresh POST uses the trigger's own ``enabled`` default, not
    whatever the stale server state said."""
    trigger._sync_once()  # populate id_map
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger._sekoia.get_rule.side_effect = SekoiaRuleNotFoundError(
        "gone", status_code=404
    )
    trigger._sekoia.create_rule.side_effect = lambda body: f"sekoia-new-{body['name']}"

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 0
    assert trigger._sekoia.create_rule.call_count == 2
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map == {
        "valhalla-a": "sekoia-new-A",
        "valhalla-b": "sekoia-new-B",
    }


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

    t = SyncSigmaRulesCatalog(data_path=Path(data_storage))
    t.module = MagicMock()
    t.configuration = {"frequency": 60}
    t._sync_once = MagicMock()
    t._stop_event.set()  # loop guard sees running=False, exits immediately

    th = threading.Thread(target=t.run)
    th.start()
    th.join(timeout=5)
    assert not th.is_alive(), "run() should exit when stop event is set"


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


# ---------------------------------------------------------------------------
# preserve_rule_names — per-rule opt-out from Valhalla overwrites
# ---------------------------------------------------------------------------


def test_normalize_names_strips_whitespace_and_drops_empties():
    assert _normalize_names(["  A rule  ", "Another", " ", ""]) == frozenset(
        {"A rule", "Another"}
    )


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

    def _get(uuid):
        return {"enabled": True, "name": "A" if uuid == "sekoia-A" else "B"}
    trigger._sekoia.get_rule.side_effect = _get

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

    def _get(uuid):
        return {"enabled": True, "name": "  A  " if uuid == "sekoia-A" else "B"}
    trigger._sekoia.get_rule.side_effect = _get

    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 1
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 1


def test_preserve_rule_names_absent_updates_normally(trigger):
    """Empty preserve list → both rules get the usual PUT; preserved=0."""
    trigger._sync_once()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._sekoia.get_rule.return_value = {"enabled": True, "name": "A"}
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
    trigger._sekoia.get_rule.return_value = {"enabled": True, "name": "A"}
    trigger._sync_once()

    assert trigger._sekoia.update_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["preserved"] == 0


def test_preserve_rule_names_does_not_affect_posts(trigger, data_storage):
    """A brand-new Valhalla rule whose title happens to match a preserve
    entry is still POSTed — the preserve check only guards the update
    path (no id_map entry yet means no GET, no name comparison)."""
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
    """A preserved rule that then leaves the Valhalla feed must still be
    disabled by ``disable_removed=true`` — the preserve list protects
    content, not lifecycle."""
    trigger._sync_once()  # populate id_map
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    # A drops from the feed AND is on the preserve list.
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._disable_removed = True
    trigger._preserve_rule_names = frozenset({"A"})

    def _get(uuid):
        return {"enabled": True, "name": "A" if uuid == "sekoia-A" else "B"}
    trigger._sekoia.get_rule.side_effect = _get

    trigger._sync_once()

    # A is disabled (enabled=false PUT) despite the preserve entry.
    # B is updated normally.
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["newly_disabled"] == 1
    disable_puts = [
        c for c in trigger._sekoia.update_rule.call_args_list
        if c.args[1].get("enabled") is False
    ]
    assert len(disable_puts) == 1


# ---------------------------------------------------------------------------
# Catalog scan — rebuild id-map from server-side uuid-* tags
# ---------------------------------------------------------------------------


def test_scan_builds_id_map_from_uuid_tags(trigger, data_storage):
    """Fresh id-map, server already carries uuid tags → id-map is rebuilt
    from the catalog, so the sync loop PUTs (no POSTs, no duplicates)."""
    trigger._sekoia.iter_rules.return_value = [
        {
            "uuid": "sekoia-A",
            "tags": ["nextron-valhalla", "uuid-valhalla-a"],
        },
        {
            "uuid": "sekoia-B",
            "tags": ["nextron-valhalla", "uuid-valhalla-b"],
        },
    ]
    # get_rule by default returns {"enabled": False} — fine for update path.

    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    assert trigger._sekoia.update_rule.call_count == 2
    event = trigger.send_event.call_args.kwargs["event"]
    assert event["server_marker_count"] == 2
    assert event["duplicate_markers"] == 0
    assert event["local_overridden"] == 0
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map == {"valhalla-a": "sekoia-A", "valhalla-b": "sekoia-B"}


def test_scan_detects_duplicate_markers(trigger):
    """Two server rules carrying the same uuid-X tag → warning logged,
    first-seen wins, counter increments."""
    trigger._sekoia.iter_rules.return_value = [
        {
            "uuid": "sekoia-A-original",
            "tags": ["nextron-valhalla", "uuid-valhalla-a"],
        },
        {
            "uuid": "sekoia-A-duplicate",
            "tags": ["nextron-valhalla", "uuid-valhalla-a"],
        },
    ]
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["duplicate_markers"] == 1
    assert event["server_marker_count"] == 1  # first-seen only
    # First-seen UUID is the one that ends up in the sync path.
    assert trigger._sekoia.update_rule.call_args_list[0].args[0] == "sekoia-A-original"
    # Warning was logged with both uuids and the clean-up hint.
    warnings = [
        c for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"
    ]
    assert any("sekoia-A-duplicate" in str(c) for c in warnings)


def test_scan_overrides_local_on_conflict(trigger, data_storage):
    """Local id-map says valhalla-a → stale-uuid; catalog says fresh-uuid.
    Scan trusts the catalog; local_overridden counter increments."""
    (Path(data_storage) / UUID_MAP_FILE).write_text(
        json.dumps({"valhalla-a": "stale-uuid"})
    )
    trigger._sekoia.iter_rules.return_value = [
        {
            "uuid": "fresh-uuid",
            "tags": ["nextron-valhalla", "uuid-valhalla-a"],
        },
    ]
    # Narrow the feed to one rule so this test asserts a single update path.
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]
    trigger.log = MagicMock()

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["local_overridden"] == 1
    assert trigger._sekoia.update_rule.call_args.args[0] == "fresh-uuid"
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert id_map["valhalla-a"] == "fresh-uuid"


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


def test_scan_accepts_dict_shape_tags(trigger, data_storage):
    """Sekoia's GET-returned tags shape is ``[{uuid, name}, …]``. The scan
    reads either shape (dict or plain string)."""
    trigger._sekoia.iter_rules.return_value = [
        {
            "uuid": "sekoia-A",
            "tags": [
                {"uuid": "t1", "name": "nextron-valhalla"},
                {"uuid": "t2", "name": "uuid-valhalla-a"},
            ],
        },
    ]
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[0]]

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["server_marker_count"] == 1
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


def test_disable_body_strips_server_read_only_fields():
    """Sekoia's GET response carries read-only fields (uuid, created_at,
    created_by, …) that PUT rejects. The disable pass must strip them
    before round-tripping or every PUT 400s."""
    server_body = {
        "uuid": "sk-1",
        "created_at": "2026-10-01T00:00:00Z",
        "created_by": "key-uuid",
        "updated_at": "2026-10-10T00:00:00Z",
        "community_uuid": "comm-123",
        "name": "A rule",
        "type": "sigma",
        "description": "desc",
        "payload": "detection: {}",
        "severity": 50,
        "effort": 2,
        "alert_type_uuid": "alert-uuid",
        "enabled": True,
        "tags": ["attack.t1059", "nextron-valhalla"],
        "false_positives": "noise",
    }
    body = _disable_body_from_server(server_body)
    # Enabled flipped.
    assert body["enabled"] is False
    # Writable fields preserved.
    for k in ("name", "type", "description", "payload", "severity", "effort",
              "alert_type_uuid", "tags", "false_positives"):
        assert body[k] == server_body[k], k
    # Read-only fields stripped.
    for k in ("uuid", "created_at", "created_by", "updated_at", "community_uuid"):
        assert k not in body, k


def test_disable_body_normalises_expanded_alert_type_object():
    """Sekoia's GET returns ``alert_type`` as ``{uuid, name}`` but PUT
    requires a flat ``alert_type_uuid`` string. Pull the uuid out of the
    expanded object."""
    server_body = {
        "name": "A",
        "type": "sigma",
        "payload": "detection: {}",
        "enabled": True,
        "alert_type": {
            "uuid": "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168",
            "name": "exfiltration",
        },
    }
    body = _disable_body_from_server(server_body)
    assert body["alert_type_uuid"] == "0b7c0b5b-da8e-4e43-a2e1-11cb5a40f168"
    assert "alert_type" not in body
    assert body["enabled"] is False


def test_disable_body_falls_back_to_default_alert_type_when_missing():
    """If the server returned neither a flat ``alert_type_uuid`` nor an
    expanded ``alert_type`` object, substitute ``DEFAULT_ALERT_UUID`` so
    the required-field validator can't reject the PUT."""
    from nextron_valhalla_sigma_rules_modules.sigma_mapper import DEFAULT_ALERT_UUID
    server_body = {
        "name": "A",
        "type": "sigma",
        "payload": "detection: {}",
        "enabled": True,
    }
    body = _disable_body_from_server(server_body)
    assert body["alert_type_uuid"] == DEFAULT_ALERT_UUID
    assert body["enabled"] is False


def test_disable_body_prefers_flat_alert_type_uuid_over_expanded():
    """When both are present (hypothetical), the flat one wins — it's the
    shape PUT expects natively."""
    server_body = {
        "name": "A",
        "type": "sigma",
        "payload": "detection: {}",
        "enabled": True,
        "alert_type_uuid": "flat-uuid",
        "alert_type": {"uuid": "nested-uuid", "name": "x"},
    }
    body = _disable_body_from_server(server_body)
    assert body["alert_type_uuid"] == "flat-uuid"


def test_disable_body_flattens_structured_tags():
    """Sekoia returns tags as ``[{uuid, name}, …]`` on GET but PUT expects
    plain strings. The helper flattens so the round-trip is accepted."""
    server_body = {
        "name": "A rule",
        "type": "sigma",
        "payload": "detection: {}",
        "enabled": True,
        "tags": [
            {"uuid": "t1", "name": "attack.t1059"},
            {"uuid": "t2", "name": "nextron-valhalla"},
            "already-a-string",
        ],
    }
    body = _disable_body_from_server(server_body)
    assert body["tags"] == ["attack.t1059", "nextron-valhalla", "already-a-string"]
    assert body["enabled"] is False


def test_disable_removed_dry_run_counts_but_doesnt_put(trigger, data_storage):
    """With disable_removed=False (default) a rule dropped from the feed
    appears in ``to_disable`` but is NOT PUT with enabled=false."""
    trigger._sync_once()  # populate id_map with both A and B
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    # A drops from the feed; B stays.
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._sekoia.get_rule.return_value = {"enabled": False}

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 1
    assert event["newly_disabled"] == 0
    # No extra PUTs for the disable pass — just the update PUT for B.
    assert trigger._sekoia.update_rule.call_count == 1
    # id_map keeps A (reappearing rule resumes update in place).
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" in id_map


def test_disable_removed_puts_rule_with_enabled_false(trigger, data_storage):
    """With disable_removed=True, a dropped rule gets GET-then-PUT with
    enabled=false. Other server fields on the body are preserved."""
    trigger._sync_once()  # populate id_map
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()

    trigger._disable_removed = True
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._sekoia.get_rule.return_value = {
        "enabled": True,
        "name": "A",
        "severity": 42,  # must round-trip
    }

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 1
    assert event["newly_disabled"] == 1

    disable_puts = [
        c for c in trigger._sekoia.update_rule.call_args_list
        if c.args[1].get("severity") == 42
    ]
    assert len(disable_puts) == 1
    assert disable_puts[0].args[1]["enabled"] is False
    # Server body round-tripped — no clobber of severity.
    assert disable_puts[0].args[1]["severity"] == 42

    # id_map entry kept so reappearing rule resumes update.
    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" in id_map


def test_already_disabled_is_counted(trigger):
    """Rules already disabled server-side are counted under
    ``already_disabled`` and no PUT is sent for them."""
    trigger._sync_once()
    trigger._sekoia.update_rule.reset_mock()
    trigger.send_event.reset_mock()
    trigger._disable_removed = True

    # A drops from the feed; GET on A returns already-disabled.
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    def _get(uuid):
        return {"enabled": uuid != "sekoia-A"}  # sekoia-A is disabled
    trigger._sekoia.get_rule.side_effect = _get

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["to_disable"] == 1
    assert event["already_disabled"] == 1
    assert event["newly_disabled"] == 0
    disable_puts = [
        c for c in trigger._sekoia.update_rule.call_args_list
        if c.args[0] == "sekoia-A"
    ]
    assert len(disable_puts) == 0


def test_already_gone_drops_idmap(trigger, data_storage):
    """A disable candidate whose GET returns ``SekoiaRuleNotFoundError``
    is counted under ``already_gone`` and the id-map entry is dropped
    (nothing left to disable)."""
    trigger._sync_once()
    trigger.send_event.reset_mock()
    trigger._disable_removed = True

    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]

    def _get(uuid):
        if uuid == "sekoia-A":
            raise SekoiaRuleNotFoundError("gone", status_code=404)
        return {"enabled": True}
    trigger._sekoia.get_rule.side_effect = _get

    trigger._sync_once()

    event = trigger.send_event.call_args.kwargs["event"]
    assert event["already_gone"] == 1

    id_map = json.loads((Path(data_storage) / UUID_MAP_FILE).read_text())
    assert "valhalla-a" not in id_map


def test_reappearing_rule_resumes_update_in_place(trigger, data_storage):
    """A rule disabled on sync N and then reappearing on sync N+1 goes
    down the UPDATE path (GET-then-PUT) with its old sekoia_uuid, not a
    fresh POST — because the id-map entry was kept."""
    trigger._sync_once()  # populate; id_map["valhalla-a"] = "sekoia-A"
    original_a_uuid = json.loads(
        (Path(data_storage) / UUID_MAP_FILE).read_text()
    )["valhalla-a"]
    trigger._sekoia.create_rule.reset_mock()
    trigger._sekoia.update_rule.reset_mock()
    trigger._disable_removed = True
    trigger._sekoia.get_rule.return_value = {"enabled": True}

    # Sync 2: A missing, B present. A gets disabled.
    trigger._valhalla.get_sigma_feed.return_value = [SAMPLE_RULES[1]]
    trigger._sync_once()
    trigger._sekoia.update_rule.reset_mock()
    trigger._sekoia.create_rule.reset_mock()

    # Sync 3: A returns. Expect UPDATE with the same sekoia_uuid.
    trigger._valhalla.get_sigma_feed.return_value = list(SAMPLE_RULES)
    trigger._sync_once()

    assert trigger._sekoia.create_rule.call_count == 0
    update_uuids = [c.args[0] for c in trigger._sekoia.update_rule.call_args_list]
    assert original_a_uuid in update_uuids
