from urllib.parse import unquote as url_decoder

import pytest
import requests_mock

from sekoiaio.operation_center import (
    GetAlert,
    ListAlerts,
    AddEventsToACase,
    RemoveEventFromCase,
    CreateCase,
    UpdateCase,
    DeleteCase,
    GetCase,
    ListsCases,
    PostCommentOnCase,
    GetCustomStatus,
    GetCustomPriority,
    GetCustomVerdict,
)

module_base_url = "http://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"
case_expected_response = {
    "uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f",
    "short_id": "string",
    "created_at": "string",
    "created_by": "string",
    "created_by_type": "string",
    "updated_at": "string",
    "updated_by": "string",
    "updated_by_type": "string",
    "title": "string",
    "description": "string",
    "priority": "medium",
    "status": "string",
    "status_uuid": "5ca52387-a6f7-45c3-a713-856468ffbdd7",
    "community_uuid": "e391588b-4c35-45eb-a5af-211fba0cde08",
    "subscribers": [{"avatar_uuid": "bed24c33-9044-41b5-96c5-024eb9b0c439", "type": "string"}],
    "tags": ["string"],
    "number_of_comments": 0,
    "first_seen_at": "2019-08-24T14:15:22Z",
    "last_seen_at": "2019-08-24T14:15:22Z",
    "manual": True,
    "is_supplied": True,
    "verdict_uuid": "6108af3c-010d-4cae-915e-70c748f0e58e",
    "verdict": {"description": "string", "label": "string", "level": 0, "stage": "string"},
    "custom_status_uuid": "c1ccc455-a896-4e7c-8f4d-b99df293a381",
    "custom_status": {"description": "string", "label": "string", "level": 0, "stage": "string"},
    "custom_priority_uuid": "f47455f5-1211-4723-9c4e-63d8752ec65f",
    "custom_priority": {"description": "string", "label": "string", "level": 0, "color": "string"},
    "number_of_alerts": 0,
    "alerts": [
        {
            "uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f",
            "title": "string",
            "created_at": 0,
            "created_by": "string",
            "created_by_type": "string",
            "updated_at": 0,
            "updated_by": "string",
            "updated_by_type": "string",
            "community_uuid": "e391588b-4c35-45eb-a5af-211fba0cde08",
            "short_id": "string",
            "entity": {"uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f", "name": "string"},
            "urgency": {"current_value": 0, "value": 0, "severity": 0, "criticity": 0, "display": "string"},
            "alert_type": {"value": "string", "category": "string"},
            "status": {"uuid": "string", "name": "string", "description": "string"},
            "rule": {
                "uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f",
                "name": "string",
                "severity": 0,
                "type": "string",
                "pattern": "string",
            },
            "detection_type": "string",
            "source": "string",
            "target": "string",
            "similar": 0,
            "details": "string",
            "ttps": [{"id": "string", "type": "string", "name": "string", "description": "string"}],
            "adversaries": [{"id": "string", "type": "string", "name": "string", "description": "string"}],
            "stix": {},
            "kill_chain_short_id": "string",
            "number_of_unseen_comments": 0,
            "number_of_total_comments": 0,
            "first_seen_at": "2019-08-24T14:15:22Z",
            "last_seen_at": "2019-08-24T14:15:22Z",
            "assets": ["497f6eca-6276-4993-bfeb-53cbbbba6f08"],
            "time_to_ingest": 0,
            "time_to_detect": 0,
            "time_to_acknowledge": 0,
            "time_to_respond": 0,
            "time_to_resolve": 0,
            "intake_uuids": ["497f6eca-6276-4993-bfeb-53cbbbba6f08"],
            "cases": [
                {"short_id": "string", "name": "string", "is_supplied": True, "manual": True, "status": "string"}
            ],
        }
    ],
}


def test_list_alerts_success():
    action: ListAlerts = ListAlerts()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "alerts"
    expected_response = {"items": [], "total": 0}
    arguments = {"match[entity_uuid]": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}?match[entity_uuid]=fake_uuid"


def test_get_alert_success():
    action: GetAlert = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "alerts/fake_uuid"
    expected_response = {
        "community_uuid": "string",
        "countermeasures": [],
        "cases": [],
        "updated_at": 0,
        "source": "string",
        "updated_by_type": "string",
        "stix": {},
        "comments": [],
        "updated_by": "string",
        "details": "string",
        "entity": {"uuid": "string", "name": "string"},
        "target": "string",
        "created_by": "string",
        "history": [],
        "rule": {
            "name": "string",
            "description": "string",
            "uuid": "string",
            "type": "string",
            "severity": 0,
            "pattern": "string",
        },
        "kill_chain_short_id": "string",
        "short_id": "string",
        "alert_type": {"value": "string", "category": "string"},
        "created_at": 0,
        "created_by_type": "string",
        "is_incident": False,
        "status": {"description": "string", "uuid": "string", "name": "string"},
        "event_uuids": [],
        "uuid": "string",
        "similar": 0,
        "urgency": {
            "value": 0,
            "criticity": 0,
            "severity": 0,
            "display": "string",
            "current_value": 0,
        },
    }
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_get_alert_missing_arg():
    action: GetAlert = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {}

    with requests_mock.Mocker() as mock:
        pytest.raises(KeyError, action.run, arguments)

        assert mock.call_count == 0


def test_add_events_to_case():
    action: AddEventsToACase = AddEventsToACase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid/events"
    expected_response = {}
    arguments = {"uuid": "fake_uuid", "event_ids": ["fake_event_uuid"]}

    with requests_mock.Mocker() as mock:
        mock.post(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_remove_event_from_case():
    action: RemoveEventFromCase = RemoveEventFromCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid/events/fake_event_uuid"
    expected_response = {}
    arguments = {"case_uuid": "fake_uuid", "event_id": "fake_event_uuid"}

    with requests_mock.Mocker() as mock:
        mock.delete(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "DELETE"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_create_case():
    action: CreateCase = CreateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases"

    arguments = {"title": "title"}

    with requests_mock.Mocker() as mock:
        mock.post(f"{base_url}{ressource}", json=case_expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_delete_case():
    action: DeleteCase = DeleteCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid"

    arguments = {"case_uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.delete(f"{base_url}{ressource}", json=case_expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "DELETE"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_get_case():
    action: GetCase = GetCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid"

    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=case_expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_update_case():
    action: UpdateCase = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid"

    arguments = {"uuid": "fake_uuid", "title": "title"}

    with requests_mock.Mocker() as mock:
        mock.patch(f"{base_url}{ressource}", json=case_expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "PATCH"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_list_cases_success():
    action: ListsCases = ListsCases()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases"
    expected_response = {
        "items": [
            {
                "uuid": "b7978324-90f6-46c4-a454-98f0b4d75579",
                "short_id": "short id",
                "created_at": "2025-11-21T16:05:28.495Z",
                "created_by": "created by",
                "created_by_type": "created by type",
                "updated_at": "2025-11-21T16:05:28.495Z",
                "updated_by": "updated by",
                "updated_by_type": "updated by type",
                "title": "title",
                "description": "This is a *description*",
                "priority": "medium",
                "status": "status",
                "status_uuid": "3209c136-5228-4d1d-a5ff-ff2fa7cba76c",
                "community_uuid": "cfa4ca81-7d07-4a09-bc85-2105b167a567",
                "subscribers": [{"avatar_uuid": "5e4ec73e-6330-4283-ac76-a36fbbd911a6", "type": "type"}],
                "tags": ["tags"],
                "number_of_comments": 0,
                "first_seen_at": "2025-11-21T16:05:28.495Z",
                "last_seen_at": "2025-11-21T16:05:28.495Z",
                "manual": True,
                "is_supplied": True,
                "verdict_uuid": "dc36dcd3-92dc-4649-8d8c-0825876382c4",
                "verdict": {"description": "This is a *description*", "label": "label", "level": 0, "stage": "stage"},
                "custom_status_uuid": "5e19d293-2663-4163-bf39-e128468f04bc",
                "custom_status": {
                    "description": "This is a *description*",
                    "label": "label",
                    "level": 0,
                    "stage": "stage",
                },
                "custom_priority_uuid": "aac0c542-55c1-4af8-b591-1e2893c11e70",
                "custom_priority": {
                    "description": "This is a *description*",
                    "label": "label",
                    "level": 0,
                    "color": "color",
                },
                "description_updated_manually": True,
                "priority_updated_manually": True,
                "custom_fields": [
                    {
                        "uuid": "63a8da06-c0a7-4378-8df7-92abdbe59585",
                        "community_uuid": "81a8a799-06f3-490e-8c4e-47e1022e34d3",
                        "name": "name",
                        "slug": "slug",
                        "description": "This is a *description*",
                        "type": "text",
                        "options": [{"uuid": "221fc7f8-5e70-40d1-af77-50d395dd8b1e", "value": "value"}],
                        "color": "color",
                        "auto_added_to_case": True,
                        "value": None,
                    }
                ],
            }
        ],
        "total": 0,
    }
    arguments = {"match[community_uuid]": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}?match[community_uuid]=fake_uuid"


def test_post_comment_on_case():
    action: PostCommentOnCase = PostCommentOnCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "cases/fake_uuid/comments"
    expected_response = {
        "uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f",
        "content": "string",
        "created_at": "string",
        "created_by": "string",
        "created_by_type": "string",
        "updated_at": "string",
    }
    arguments = {"uuid": "fake_uuid", "content": "content"}

    with requests_mock.Mocker() as mock:
        mock.post(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_get_custom_status():
    action: GetCustomStatus = GetCustomStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "custom_statuses/fake_uuid"
    expected_response = {
        "name": "string",
        "description": "string",
        "stage": "string",
    }
    arguments = {"status_uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_get_custom_priority():
    action: GetCustomPriority = GetCustomPriority()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "custom_priorities/fake_uuid"
    expected_response = {
        "name": "string",
        "description": "string",
        "level": 0,
    }
    arguments = {"priority_uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_get_custom_verdict():
    action: GetCustomVerdict = GetCustomVerdict()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "custom_verdicts/fake_uuid"
    expected_response = {
        "name": "string",
        "description": "string",
        "stage": "string",
    }
    arguments = {"verdict_uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        action.run(arguments)
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"
