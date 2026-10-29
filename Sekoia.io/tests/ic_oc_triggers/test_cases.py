import json
from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
import requests_mock

from sekoiaio.triggers.cases import (
    CaseAlertsUpdatedTrigger,
    CaseCommentCreatedTrigger,
    CaseCreatedTrigger,
    CaseUpdatedTrigger,
    SecurityCasesTrigger,
)


@pytest.fixture
def case_trigger(module_configuration, symphony_storage):
    case_trigger = SecurityCasesTrigger()
    case_trigger._data_path = symphony_storage
    case_trigger.configuration = {}
    case_trigger.module.configuration = module_configuration
    case_trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    case_trigger.log = Mock()

    return case_trigger


@pytest.fixture
def sample_siccaseapi_mock(sample_siccaseapi):
    case_uuid = sample_siccaseapi.get("uuid")
    mock = requests_mock.Mocker()
    mock.get(f"http://fake.url/api/v1/sic/cases/{case_uuid}", json=sample_siccaseapi)

    return mock


def test_securitycasestrigger_init(case_trigger):
    assert type(case_trigger) is SecurityCasesTrigger


def test_securitycasestrigger_retrieve_case_from_api(case_trigger, sample_siccaseapi):
    case_uuid = sample_siccaseapi.get("uuid")

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/cases/{case_uuid}", json=sample_siccaseapi)

        case = case_trigger._retrieve_case_from_caseapi(case_uuid)
        assert sorted(case) == sorted(sample_siccaseapi)


@pytest.fixture
def case_created_trigger(module_configuration, symphony_storage):
    trigger = CaseCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    return trigger


@pytest.fixture
def case_updated_trigger(module_configuration, symphony_storage):
    trigger = CaseUpdatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    return trigger


@pytest.fixture
def case_alerts_updated_trigger(module_configuration, symphony_storage):
    trigger = CaseAlertsUpdatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    return trigger


@pytest.fixture
def case_comment_created_trigger(module_configuration, symphony_storage):
    trigger = CaseCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    return trigger


def test_casecreatedtrigger_handler_dispatch_case_message(case_created_trigger, samplenotif_case_updated):
    case_created_trigger.handle_event = Mock()

    case_created_trigger.handler_dispatcher(json.dumps(samplenotif_case_updated))
    case_created_trigger.handle_event.assert_called()


def test_casecreatedtrigger_handle_case_invalid_message(case_created_trigger):
    invalid_messages = [
        {"event_version": "1", "event_type": "case"},
        {"event_version": "1", "event_type": "case", "attributes": {}},
        {
            "event_version": "1",
            "event_type": "case",
            "attributes": {"event": "case-created"},
        },
    ]

    for message in invalid_messages:
        case_created_trigger.handler_dispatcher(json.dumps(message))


def test_single_event_triggers_updated(
    case_created_trigger,
    sample_siccaseapi_mock,
    module_configuration,
    symphony_storage,
    samplenotif_case_updated,
    sample_case_notifications,
):
    trigger = CaseUpdatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()

    with sample_siccaseapi_mock:
        # Edge case: notification with empty 'updated' attribute
        trigger.send_event.reset_mock()
        empty_updated_notification = {
            "action": "updated",
            "type": "case",
            "updated": "",
        }
        trigger.handle_event(empty_updated_notification)
        trigger.send_event.assert_not_called()

        # Edge case: notification with unexpected keys in 'updated'
        trigger.send_event.reset_mock()
        unexpected_keys_notification = {
            "action": "updated",
            "type": "case",
            "updated": {"unexpected_key": "unexpected_value"},
        }
        trigger.handle_event(unexpected_keys_notification)
        trigger.send_event.assert_not_called()

        # Calling the trigger with a case updated notification should create an event
        trigger.handle_event(samplenotif_case_updated)
        trigger.send_event.assert_called_once()

        # All other notification types should not
        for notification in sample_case_notifications:
            if notification["action"] != "updated" or notification["type"] != "case":
                trigger.handle_event(notification)

        trigger.send_event.assert_called_once()


def test_case_trigger_filter_by_mode(
    case_created_trigger,
    samplenotif_case_created,
    sample_siccaseapi_mock,
    sample_siccaseapi,
):
    case_created_trigger.send_event = MagicMock()
    with sample_siccaseapi_mock:
        # no match
        case_created_trigger.configuration = {"mode_filter": "foo"}
        case_created_trigger.handle_event(samplenotif_case_created)
        assert not case_created_trigger.send_event.called

        # match mode
        mode = "manual" if sample_siccaseapi["manual"] else "automatic"
        case_created_trigger.configuration = {"mode_filter": mode}
        case_created_trigger.handle_event(samplenotif_case_created)
        assert case_created_trigger.send_event.called


def test_case_trigger_filter_by_priorities(
    case_created_trigger,
    samplenotif_case_created,
    sample_siccaseapi_mock,
    sample_siccaseapi,
):
    case_created_trigger.send_event = MagicMock()
    with sample_siccaseapi_mock:
        # no match
        case_created_trigger.configuration = {"priority_uuids_filter": ["foo"]}
        case_created_trigger.handle_event(samplenotif_case_created)
        assert not case_created_trigger.send_event.called

        # match priority_uuid
        case_created_trigger.configuration = {"priority_uuids_filter": [sample_siccaseapi["custom_priority_uuid"]]}
        case_created_trigger.handle_event(samplenotif_case_created)
        assert case_created_trigger.send_event.call_count == 1

        # match priority_uuid
        case_created_trigger.configuration = {
            "priority_uuids_filter": [sample_siccaseapi["custom_priority_uuid"], "foo"]
        }
        case_created_trigger.handle_event(samplenotif_case_created)
        assert case_created_trigger.send_event.call_count == 2


def test_case_filter_by_assignees(
    case_alerts_updated_trigger,
    samplenotif_case_has_updated_alerts,
    sample_siccaseapi_mock,
    sample_siccaseapi,
):
    case_alerts_updated_trigger.send_event = MagicMock()
    with sample_siccaseapi_mock:
        # no match
        case_alerts_updated_trigger.configuration = {"assignees_filter": ["foo"]}
        case_alerts_updated_trigger.handle_event(samplenotif_case_has_updated_alerts)
        assert not case_alerts_updated_trigger.send_event.called

        # match assignee
        case_alerts_updated_trigger.configuration = {
            "assignees_filter": [sample_siccaseapi["subscribers"][0]["avatar_uuid"]]
        }
        case_alerts_updated_trigger.handle_event(samplenotif_case_has_updated_alerts)
        assert case_alerts_updated_trigger.send_event.call_count == 1

        # match assignee
        case_alerts_updated_trigger.configuration = {
            "assignees_filter": [sample_siccaseapi["subscribers"][0]["avatar_uuid"], "foo"]
        }
        case_alerts_updated_trigger.handle_event(samplenotif_case_has_updated_alerts)
        assert case_alerts_updated_trigger.send_event.call_count == 2


def test_case_filter_by_case_uuids(
    case_updated_trigger,
    samplenotif_case_updated,
    sample_siccaseapi_mock,
    sample_siccaseapi,
):
    case_updated_trigger.send_event = MagicMock()
    with sample_siccaseapi_mock:
        # no match
        case_updated_trigger.configuration = {"case_uuids_filter": ["foo"]}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert not case_updated_trigger.send_event.called

        # match case_uuid
        case_updated_trigger.configuration = {"case_uuids_filter": [sample_siccaseapi["uuid"]]}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 1

        # match short_id
        case_updated_trigger.configuration = {"case_uuids_filter": [sample_siccaseapi["short_id"]]}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 2

        # match case_uuid
        case_updated_trigger.configuration = {"case_uuids_filter": [sample_siccaseapi["uuid"], "foo"]}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 3

        # match short_id
        case_updated_trigger.configuration = {"case_uuids_filter": [sample_siccaseapi["short_id"], "foo"]}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 4


def test_case_combined_filters(
    case_updated_trigger,
    samplenotif_case_updated,
    sample_siccaseapi_mock,
    sample_siccaseapi,
):
    case_updated_trigger.send_event = MagicMock()
    with sample_siccaseapi_mock:
        mode = "manual" if sample_siccaseapi["manual"] else "automatic"

        # no match
        case_updated_trigger.configuration = {
            "case_uuids_filter": ["foo"],
            "assignees_filter": ["foo"],
            "mode_filter": "foo",
            "priority_uuids_filter": ["foo"],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert not case_updated_trigger.send_event.called

        # no match
        case_updated_trigger.configuration = {
            "case_uuids_filter": [sample_siccaseapi["uuid"]],
            "assignees_filter": ["foo"],
            "mode_filter": "foo",
            "priority_uuids_filter": ["foo"],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert not case_updated_trigger.send_event.called

        # no match
        case_updated_trigger.configuration = {
            "case_uuids_filter": ["foo"],
            "assignees_filter": [sample_siccaseapi["subscribers"][0]["avatar_uuid"]],
            "mode_filter": "foo",
            "priority_uuids_filter": ["foo"],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert not case_updated_trigger.send_event.called

        # no match
        case_updated_trigger.configuration = {
            "case_uuids_filter": ["foo"],
            "assignees_filter": ["foo"],
            "mode_filter": mode,
            "priority_uuids_filter": ["foo"],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert not case_updated_trigger.send_event.called

        # no match
        case_updated_trigger.configuration = {
            "case_uuids_filter": ["foo"],
            "assignees_filter": ["foo"],
            "mode_filter": "foo",
            "priority_uuids_filter": [sample_siccaseapi["custom_priority_uuid"]],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert not case_updated_trigger.send_event.called

        # match case all criteria
        case_updated_trigger.configuration = {
            "case_uuids_filter": [sample_siccaseapi["uuid"]],
            "assignees_filter": [sample_siccaseapi["subscribers"][0]["avatar_uuid"]],
            "mode_filter": mode,
            "priority_uuids_filter": [sample_siccaseapi["custom_priority_uuid"]],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 1

        # match
        case_updated_trigger.configuration = {"case_uuids_filter": [sample_siccaseapi["uuid"]], "mode_filter": mode}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 2

        # match
        case_updated_trigger.configuration = {
            "assignees_filter": [sample_siccaseapi["subscribers"][0]["avatar_uuid"]],
            "priority_uuids_filter": [sample_siccaseapi["custom_priority_uuid"]],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 3

        # match
        case_updated_trigger.configuration = {
            "case_uuids_filter": [sample_siccaseapi["uuid"]],
            "assignees_filter": [sample_siccaseapi["subscribers"][0]["avatar_uuid"]],
        }
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.call_count == 4


def case_updated_notification(case: dict, **attributes: Any) -> dict:
    """Notification sent by the Cases API when a case is updated."""
    return {
        "metadata": {
            "version": 2,
            "uuid": "927b628a-7099-4ee4-bccb-8efdb694882d",
            "created_at": "2026-10-29T10:00:00.000000+00:00",
            "community_uuid": case["community_uuid"],
        },
        "type": "case",
        "action": "updated",
        "attributes": {
            "uuid": case["uuid"],
            "short_id": case["short_id"],
            "manual": True,
            "title": case["title"],
            "priority": "medium",
            "created_at": case["created_at"],
            "custom_priority_uuid": case["custom_priority_uuid"],
            **attributes,
        },
    }


def run_case_updated(trigger, sample_siccaseapi, notification) -> dict | None:
    trigger.send_event = MagicMock()
    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/cases/{sample_siccaseapi['uuid']}", json=sample_siccaseapi)
        trigger.handle_event(notification)

    if not trigger.send_event.called:
        return None
    return trigger.send_event.call_args.kwargs["event"]


def test_case_updated_trigger_keeps_the_current_outputs(
    case_updated_trigger, sample_siccaseapi, samplenotif_case_updated
):
    event = run_case_updated(case_updated_trigger, sample_siccaseapi, samplenotif_case_updated)

    assert event == {
        "uuid": sample_siccaseapi["uuid"],
        "short_id": sample_siccaseapi["short_id"],
        "created_at": sample_siccaseapi["created_at"],
        "updated_at": sample_siccaseapi["updated_at"],
        "updated_by": sample_siccaseapi["updated_by"],
        "tags": ["tag1", "tag2"],
        "description": "I've updated my case",
        "changed_fields": ["description", "tags"],
    }


def test_case_updated_trigger_outputs_the_custom_status(case_updated_trigger, sample_siccaseapi):
    notification = case_updated_notification(
        sample_siccaseapi,
        updated={"custom_status_uuid": "6982f541-484e-4676-9a03-c2d18e66b53b", "custom_status_stage": "closed"},
        # Sent with every status change: the current verdict, which did not change
        verdict_uuid="6108af3c-010d-4cae-915e-70c748f0e58e",
        verdict_stage="true_positive",
        verdict_source="explicit",
        verdict_updated_by="a5fe93d8-e910-494b-ab83-8565fa2e5916",
    )

    event = run_case_updated(case_updated_trigger, sample_siccaseapi, notification)

    assert event["custom_status_uuid"] == "6982f541-484e-4676-9a03-c2d18e66b53b"
    assert event["custom_status_stage"] == "closed"
    # The legacy status and the unchanged verdict are not output
    assert "status_uuid" not in event
    assert "verdict_uuid" not in event


def test_case_updated_trigger_outputs_the_priority_under_both_names(case_updated_trigger, sample_siccaseapi):
    priority_uuid = "f47455f5-1211-4723-9c4e-63d8752ec65f"
    notification = case_updated_notification(sample_siccaseapi, updated={"custom_priority_uuid": priority_uuid})

    event = run_case_updated(case_updated_trigger, sample_siccaseapi, notification)

    assert event["priority_uuid"] == priority_uuid
    assert event["custom_priority_uuid"] == priority_uuid


def test_case_updated_trigger_outputs_the_verdict_details(case_updated_trigger, sample_siccaseapi):
    notification = case_updated_notification(
        sample_siccaseapi,
        updated={
            "verdict_uuid": "6108af3c-010d-4cae-915e-70c748f0e58e",
            "verdict_stage": "true_positive",
            "verdict_analysis": "Confirmed by the EDR",
            "verdict_confidence": 90,
        },
    )

    event = run_case_updated(case_updated_trigger, sample_siccaseapi, notification)

    assert event["verdict_uuid"] == "6108af3c-010d-4cae-915e-70c748f0e58e"
    assert event["verdict_stage"] == "true_positive"
    assert event["verdict_analysis"] == "Confirmed by the EDR"
    assert event["verdict_confidence"] == 90


def test_case_updated_trigger_outputs_the_custom_fields_changes(case_updated_trigger, sample_siccaseapi):
    changes = {
        "added": [{"uuid": "7d7ad2a8-9a3e-4fd6-8a43-5d0b3b5a9a20", "name": "External ID", "type": "text"}],
        "updated": [],
        "removed": [],
    }
    notification = case_updated_notification(sample_siccaseapi, custom_fields=changes)

    event = run_case_updated(case_updated_trigger, sample_siccaseapi, notification)

    assert event["custom_fields_changes"] == changes


@pytest.mark.parametrize(
    "attributes,changed_fields",
    [
        (
            {
                "updated": {
                    "custom_status_uuid": "6982f541-484e-4676-9a03-c2d18e66b53b",
                    "custom_status_stage": "closed",
                }
            },
            ["status"],
        ),
        ({"updated": {"custom_priority_uuid": "f47455f5-1211-4723-9c4e-63d8752ec65f"}}, ["priority"]),
        ({"updated": {"verdict_uuid": None, "verdict_stage": None}}, ["verdict"]),
        ({"updated": {"assignees": [], "title": "New title"}}, ["title", "assignees"]),
        (
            {
                "custom_fields": {
                    "added": [],
                    "updated": [{"uuid": "f", "name": "External ID", "type": "text"}],
                    "removed": [],
                }
            },
            ["custom_fields"],
        ),
        ({}, []),
    ],
)
def test_case_updated_trigger_outputs_the_changed_fields(
    case_updated_trigger, sample_siccaseapi, attributes, changed_fields
):
    notification = case_updated_notification(sample_siccaseapi, **attributes)

    event = run_case_updated(case_updated_trigger, sample_siccaseapi, notification)

    assert event["changed_fields"] == changed_fields


def test_case_updated_trigger_filters_on_the_changed_fields(case_updated_trigger, sample_siccaseapi):
    # Closing a case with a verdict sends one notification for the status and one for the verdict
    status_notification = case_updated_notification(
        sample_siccaseapi,
        updated={"custom_status_uuid": "6982f541-484e-4676-9a03-c2d18e66b53b", "custom_status_stage": "closed"},
    )
    verdict_notification = case_updated_notification(
        sample_siccaseapi,
        updated={"verdict_uuid": "6108af3c-010d-4cae-915e-70c748f0e58e", "verdict_stage": "true_positive"},
    )
    case_updated_trigger.configuration = {"changed_fields_filter": ["status"]}
    case_updated_trigger.send_event = MagicMock()

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/cases/{sample_siccaseapi['uuid']}", json=sample_siccaseapi)
        case_updated_trigger.handle_event(status_notification)
        case_updated_trigger.handle_event(verdict_notification)

        # The verdict notification is skipped before reading the case
        assert mock.call_count == 1

    case_updated_trigger.send_event.assert_called_once()
    assert case_updated_trigger.send_event.call_args.kwargs["event"]["custom_status_stage"] == "closed"


def test_case_updated_trigger_without_filter_creates_a_run_per_update(case_updated_trigger, sample_siccaseapi):
    case_updated_trigger.configuration = {"changed_fields_filter": []}
    notifications = [
        case_updated_notification(sample_siccaseapi, updated={"custom_status_stage": "closed"}),
        case_updated_notification(sample_siccaseapi, updated={"verdict_stage": "true_positive"}),
        # An update without any known change still creates a run, as before
        case_updated_notification(sample_siccaseapi),
    ]
    case_updated_trigger.send_event = MagicMock()

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/cases/{sample_siccaseapi['uuid']}", json=sample_siccaseapi)
        for notification in notifications:
            case_updated_trigger.handle_event(notification)

    assert case_updated_trigger.send_event.call_count == 3


def test_single_event_triggers_case_comments_added(
    module_configuration,
    symphony_storage,
    sample_siccaseapi,
    samplenotif_case_comment_created,
    sample_case_notifications,
):
    trigger = CaseCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()

    case_uuid = samplenotif_case_comment_created.get("attributes").get("case_uuid")
    comment_uuid = samplenotif_case_comment_created.get("attributes").get("uuid")

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/cases/{case_uuid}", json=sample_siccaseapi)
        mock.get(
            f"http://fake.url/api/v1/sic/cases/{case_uuid}/comments/{comment_uuid}",
            json={
                "uuid": comment_uuid,
                "content": "a new comment",
                "created_at": "2025-03-17T15:06:04.858932+00:00",
                "created_by": "a5fe93d8-e910-494b-ab83-8565fa2e5916",
                "created_by_type": "user",
                "updated_at": "2025-03-17T15:06:04.858932+00:00",
            },
        )

        trigger.handle_event(samplenotif_case_comment_created)
        trigger.send_event.assert_called_once()

        for notification in sample_case_notifications:
            if notification != samplenotif_case_comment_created:
                trigger.handle_event(notification)

        trigger.send_event.assert_called_once()


def test_invalid_events_dont_trigger_case_comments_added(
    module_configuration,
    symphony_storage,
    sample_siccaseapi,
):
    trigger = CaseCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()
    trigger.log = Mock()

    invalid_notification: dict[str, Any] = {
        "metadata": {
            "version": 2,
            "community_uuid": "6ffbe55b-d30a-4dc4-bc52-a213dce0af29",
            "uuid": "94ef1f9d-ebad-42ba-98d7-2be3447c6bd0",
            "created_at": "2019-09-06T07:07:54.830677+00:00",
        },
        "type": "case-comment",
        "action": "created",
        "attributes": {
            "content": "comment",
            "created_by": "c110d686-0b45-4ae7-b917-f15486d0f8c7",
            "created_by_type": "user",
            "case_short_id": "CAmDUb2Anct1e",
        },
    }

    trigger.handle_event(invalid_notification)
    trigger.send_event.assert_not_called()

    invalid_notification["attributes"]["case_uuid"] = "f014aac5-2d38-49f6-a47f-ff602c734d51"
    trigger.handle_event(invalid_notification)
    trigger.send_event.assert_not_called()

    with requests_mock.Mocker() as mock, patch("tenacity.nap.time"):
        invalid_notification["attributes"]["uuid"] = "ed44b802-f2ec-4cbc-bcdb-a9e31a87bcf9"

        mock.get("http://fake.url/api/v1/sic/cases/f014aac5-2d38-49f6-a47f-ff602c734d51", json={}, status_code=404)
        trigger.log.assert_not_called()
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()
        trigger.log.reset_mock()

        mock.get(
            "http://fake.url/api/v1/sic/cases/f014aac5-2d38-49f6-a47f-ff602c734d51",
            json=sample_siccaseapi,
        )
        mock.get(
            "http://fake.url/api/v1/sic/cases/f014aac5-2d38-49f6-a47f-ff602c734d51/comments/ed44b802-f2ec-4cbc-bcdb-a9e31a87bcf9",
            json={},
            status_code=404,
        )
        trigger.log.assert_not_called()
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()
        trigger.log.reset_mock()

        mock.get(
            "http://fake.url/api/v1/sic/cases/f014aac5-2d38-49f6-a47f-ff602c734d51/comments/ed44b802-f2ec-4cbc-bcdb-a9e31a87bcf9",
            text="not json",
            status_code=200,
        )
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()


@pytest.mark.parametrize(
    ("trigger_fixture", "message_fixture"),
    [
        ("case_created_trigger", "samplenotif_case_created"),
        ("case_alerts_updated_trigger", "samplenotif_case_has_updated_alerts"),
        ("case_comment_created_trigger", "samplenotif_case_comment_created"),
    ],
)
def test_triggers_ignored_by_wrong_sub_event(request, trigger_fixture, message_fixture):
    trigger = request.getfixturevalue(trigger_fixture)
    message = deepcopy(request.getfixturevalue(message_fixture))
    trigger.send_event = MagicMock()
    message["action"] = "updated"

    trigger.handle_event(message)

    trigger.send_event.assert_not_called()


@pytest.mark.parametrize(
    ("trigger_fixture", "message_fixture", "uuid_key"),
    [
        ("case_created_trigger", "samplenotif_case_created", "uuid"),
        ("case_updated_trigger", "samplenotif_case_updated", "uuid"),
        ("case_alerts_updated_trigger", "samplenotif_case_has_updated_alerts", "uuid"),
        ("case_comment_created_trigger", "samplenotif_case_comment_created", "case_uuid"),
    ],
)
def test_triggers_ignored_when_case_uuid_missing(request, trigger_fixture, message_fixture, uuid_key):
    trigger = request.getfixturevalue(trigger_fixture)
    message = deepcopy(request.getfixturevalue(message_fixture))
    trigger.send_event = MagicMock()
    message["attributes"][uuid_key] = ""

    trigger.handle_event(message)

    trigger.send_event.assert_not_called()


def test_case_comment_created_trigger_filtered_out(
    case_comment_created_trigger,
    samplenotif_case_comment_created,
    sample_siccaseapi,
):
    case_comment_created_trigger.send_event = MagicMock()
    case_comment_created_trigger.configuration = {"case_uuids_filter": ["does-not-match"]}

    case_uuid = samplenotif_case_comment_created.get("attributes").get("case_uuid")
    comment_uuid = samplenotif_case_comment_created.get("attributes").get("uuid")

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/cases/{case_uuid}", json=sample_siccaseapi)
        mock.get(
            f"http://fake.url/api/v1/sic/cases/{case_uuid}/comments/{comment_uuid}",
            json={
                "uuid": comment_uuid,
                "content": "a new comment",
                "created_at": "2025-03-17T15:06:04.858932+00:00",
                "created_by": "a5fe93d8-e910-494b-ab83-8565fa2e5916",
                "created_by_type": "user",
            },
        )

        case_comment_created_trigger.handle_event(samplenotif_case_comment_created)

    case_comment_created_trigger.send_event.assert_not_called()


@pytest.mark.parametrize(
    ("method_name", "url_path", "args", "expected_exception", "use_wrapped"),
    [
        (
            "_retrieve_case_from_caseapi",
            "api/v1/sic/cases/{case_uuid}",
            lambda case_uuid: (case_uuid,),
            requests.HTTPError,
            False,
        ),
        (
            "_retrieve_comment_from_caseapi",
            "api/v1/sic/cases/{case_uuid}/comments/{comment_uuid}",
            lambda case_uuid: (case_uuid, "ed44b802-f2ec-4cbc-bcdb-a9e31a87bcf9"),
            requests.HTTPError,
            False,
        ),
        (
            "_retrieve_case_from_caseapi",
            "api/v1/sic/cases/{case_uuid}",
            lambda case_uuid: (case_uuid,),
            Exception,
            True,
        ),
        (
            "_retrieve_comment_from_caseapi",
            "api/v1/sic/cases/{case_uuid}/comments/{comment_uuid}",
            lambda case_uuid: (case_uuid, "ed44b802-f2ec-4cbc-bcdb-a9e31a87bcf9"),
            Exception,
            True,
        ),
    ],
)
def test_retrieve_case_and_comment_errors_are_logged(
    case_trigger,
    sample_siccaseapi,
    method_name,
    url_path,
    args,
    expected_exception,
    use_wrapped,
):
    case_uuid = sample_siccaseapi.get("uuid")
    call_args = args(case_uuid)
    comment_uuid = call_args[1] if len(call_args) > 1 else None
    api_url = f"http://fake.url/{url_path.format(case_uuid=case_uuid, comment_uuid=comment_uuid)}"
    payload = "not json" if use_wrapped else "bad response"
    status_code = 200 if use_wrapped else 500

    with requests_mock.Mocker() as mock:
        mock.get(api_url, text=payload, status_code=status_code)

        method = getattr(case_trigger, method_name)

        if use_wrapped:
            if method_name == "_retrieve_case_from_caseapi":
                wrapped_case_method = SecurityCasesTrigger._retrieve_case_from_caseapi.__wrapped__
                with pytest.raises(expected_exception):
                    wrapped_case_method(case_trigger, *call_args)
            else:
                wrapped_comment_method = SecurityCasesTrigger._retrieve_comment_from_caseapi.__wrapped__
                with pytest.raises(expected_exception):
                    wrapped_comment_method(case_trigger, *call_args)
        else:
            with patch("tenacity.nap.time"), pytest.raises(expected_exception):
                method(*call_args)

        case_trigger.log.assert_called()


@pytest.mark.parametrize(
    ("trigger_fixture", "message_fixture"),
    [
        ("case_created_trigger", "samplenotif_case_created"),
        ("case_updated_trigger", "samplenotif_case_updated"),
        ("case_alerts_updated_trigger", "samplenotif_case_has_updated_alerts"),
        ("case_comment_created_trigger", "samplenotif_case_comment_created"),
    ],
)
def test_triggers_log_exception_when_case_api_fails(request, trigger_fixture, message_fixture):
    trigger = request.getfixturevalue(trigger_fixture)
    message = request.getfixturevalue(message_fixture)
    trigger.send_event = MagicMock()
    trigger.log_exception = Mock()
    trigger._retrieve_case_from_caseapi = Mock(side_effect=Exception("boom"))

    trigger.handle_event(message)

    trigger.send_event.assert_not_called()
    trigger.log_exception.assert_called_once()
