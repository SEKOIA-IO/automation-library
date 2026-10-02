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
    t._enabled = False
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
        "failed": 0,
        "skipped_unmapped": 0,
        "skipped_filter": 0,
        "total_rules": 2,
        "top_unmapped": {},
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
