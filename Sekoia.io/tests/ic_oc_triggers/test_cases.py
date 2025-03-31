import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from sekoiaio.triggers.cases import (
    CaseAlertsUpdatedTrigger,
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

    yield case_trigger


@pytest.fixture
def sample_siccaseapi_mock(sample_siccaseapi):
    case_uuid = sample_siccaseapi.get("uuid")
    mock = requests_mock.Mocker()
    mock.get(f"http://fake.url/api/v1/sic/cases/{case_uuid}", json=sample_siccaseapi)

    yield mock


def test_securitycasestrigger_init(case_trigger):
    assert type(case_trigger) == SecurityCasesTrigger


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

    yield trigger


@pytest.fixture
def case_updated_trigger(module_configuration, symphony_storage):
    trigger = CaseUpdatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    yield trigger


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
        assert case_created_trigger.send_event.called


def test_case_filter_by_assignees(
    case_created_trigger,
    samplenotif_case_created,
    sample_siccaseapi_mock,
    sample_siccaseapi,
):
    case_created_trigger.send_event = MagicMock()
    with sample_siccaseapi_mock:
        # no match
        case_created_trigger.configuration = {"assignees_filter": ["foo"]}
        case_created_trigger.handle_event(samplenotif_case_created)
        assert not case_created_trigger.send_event.called

        # match assignee
        case_created_trigger.configuration = {"assignees_filter": [sample_siccaseapi["assignees"][0]]}
        case_created_trigger.handle_event(samplenotif_case_created)
        assert case_created_trigger.send_event.called


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
        assert case_updated_trigger.send_event.called

        # match short_id
        case_updated_trigger.configuration = {"case_uuids_filter": [sample_siccaseapi["short_id"]]}
        case_updated_trigger.handle_event(samplenotif_case_updated)
        assert case_updated_trigger.send_event.called
