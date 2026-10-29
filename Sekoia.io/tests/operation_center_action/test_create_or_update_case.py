from urllib.parse import parse_qs, urlparse

import pytest

from sekoiaio.operation_center.create_or_update_case import CLOSED_STATUS_UUID, CreateOrUpdateCase

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"

CASE_UUID = "095be615-a8ad-4c33-8e9c-c7612fbf6c9f"
OTHER_CASE_UUID = "5a1f3c2e-7b9d-4e8f-a0b1-c2d3e4f5a6b7"
COMMUNITY_UUID = "e391588b-4c35-45eb-a5af-211fba0cde08"
AVATAR_UUID = "bed24c33-9044-41b5-96c5-024eb9b0c439"
TEMPLATE_UUID = "7d7ad2a8-9a3e-4fd6-8a43-5d0b3b5a9a20"
HIGH_UUID = "f47455f5-1211-4723-9c4e-63d8752ec65f"
MEDIUM_UUID = "8e0c1b2a-3d4e-4f5a-9b6c-7d8e9f0a1b2c"
LOW_UUID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
EXTERNAL_ID_FIELD = "2f1d3f4e-9b1a-4c55-8f0e-3f6b1a2c9d10"
SOURCE_FIELD = "a3b5c7d9-1e2f-4a6b-8c0d-2e4f6a8b0c1d"
SENTINEL_OPTION = "5b0d8f7e-4c3a-4b2d-9e1f-0a1b2c3d4e5f"
EDR_OPTION = "6c1e9a8f-5d4b-4c3e-8f2a-1b2c3d4e5f60"

TAG = "ext:sentinel:1234"
PRIORITIES = {
    "items": [
        {"uuid": HIGH_UUID, "label": "High", "level": 0},
        {"uuid": MEDIUM_UUID, "label": "Medium", "level": 1},
        {"uuid": LOW_UUID, "label": "Low", "level": 2},
    ],
    "total": 3,
}
CUSTOM_FIELDS = {
    "items": [
        {"uuid": EXTERNAL_ID_FIELD, "name": "External ID", "type": "text", "options": []},
        {
            "uuid": SOURCE_FIELD,
            "name": "Source",
            "type": "single_select",
            "options": [{"uuid": SENTINEL_OPTION, "value": "Sentinel"}, {"uuid": EDR_OPTION, "value": "EDR"}],
        },
    ],
    "total": 2,
}


def make_case(**fields):
    return {
        "uuid": CASE_UUID,
        "short_id": "CAfake",
        "title": "Suspicious sign-in",
        "tags": [TAG],
        "custom_status": {"label": "In progress", "stage": "in_progress"},
        "custom_priority_uuid": MEDIUM_UUID,
        "custom_fields": [],
        **fields,
    }


@pytest.fixture
def action(requests_mock):
    requests_mock.get(f"{base_url}custom_priorities", json=PRIORITIES)
    requests_mock.get(f"{base_url}custom-fields", json=CUSTOM_FIELDS)
    action = CreateOrUpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    return action


def requests_to(requests_mock, method, path):
    return [
        request
        for request in requests_mock.request_history
        if request.method == method and urlparse(request.url).path == f"/api/v1/sic/{path}"
    ]


def test_creates_the_case_of_a_new_incident(action, requests_mock):
    search = requests_mock.get(f"{base_url}cases", json={"items": [], "total": 0})
    created = make_case(tags=[TAG, "phishing"])
    create = requests_mock.post(f"{base_url}cases", json=created)

    results = action.run(
        {
            "source": "sentinel",
            "external_id": "1234",
            "title": "Suspicious sign-in",
            "description": "From Sentinel",
            "priority": "High",
            "tags": ["phishing", "ext:sentinel:1234"],
            "custom_fields": {"External ID": "1234", "Source": "Sentinel"},
            "assignees": [AVATAR_UUID],
            "community_uuid": COMMUNITY_UUID,
        }
    )

    assert parse_qs(urlparse(search.last_request.url).query) == {
        "match[tags]": [TAG],
        "match[type]": ["manual,automatic"],
        "with_custom_statuses": ["true"],
        "sort": ["created_at"],
        "direction": ["asc"],
        "limit": ["100"],
        "match[community_uuid]": [COMMUNITY_UUID],
    }
    assert create.last_request.json() == {
        "title": "Suspicious sign-in",
        "tags": [TAG, "phishing"],
        "description": "From Sentinel",
        "custom_priority_uuid": HIGH_UUID,
        "community_uuid": COMMUNITY_UUID,
        "custom_fields": [
            {"uuid": EXTERNAL_ID_FIELD, "value": "1234"},
            {"uuid": SOURCE_FIELD, "value": [SENTINEL_OPTION]},
        ],
        "subscribers": [{"avatar_uuid": AVATAR_UUID, "type": "assignee"}],
    }
    assert results == {
        "case_uuid": CASE_UUID,
        "short_id": "CAfake",
        "outcome": "created",
        "matched_by": None,
        "case": created,
    }


def test_applies_the_template_to_the_created_case(action, requests_mock):
    requests_mock.get(f"{base_url}cases", json={"items": [], "total": 0})
    requests_mock.post(f"{base_url}cases", json=make_case())
    apply = requests_mock.post(f"{base_url}case-templates/{TEMPLATE_UUID}/apply", status_code=204)
    with_template = make_case(custom_fields=[{"uuid": SOURCE_FIELD, "value": [EDR_OPTION]}])
    requests_mock.get(f"{base_url}cases/{CASE_UUID}", json=with_template)

    results = action.run(
        {"source": "sentinel", "external_id": "1234", "title": "Suspicious sign-in", "template_uuid": TEMPLATE_UUID}
    )

    assert apply.last_request.json() == {"uuids": [CASE_UUID]}
    assert results["case"] == with_template


def test_updates_the_open_case_of_a_known_incident(action, requests_mock):
    case = make_case(
        tags=[TAG, "identity"],
        custom_fields=[
            {"uuid": EXTERNAL_ID_FIELD, "name": "External ID", "value": None},
            {"uuid": SOURCE_FIELD, "name": "Source", "value": [SENTINEL_OPTION]},
        ],
    )
    requests_mock.get(f"{base_url}cases", json={"items": [case], "total": 1})
    update = requests_mock.patch(f"{base_url}cases/{CASE_UUID}", json=case)
    update_fields = requests_mock.patch(f"{base_url}cases/{CASE_UUID}/custom-fields", json={})
    comment = requests_mock.post(f"{base_url}cases/{CASE_UUID}/comments", json={})
    requests_mock.get(f"{base_url}cases/{CASE_UUID}", json=case)
    create = requests_mock.post(f"{base_url}cases", json=case)

    results = action.run(
        {
            "source": "sentinel",
            "external_id": "1234",
            "title": "Suspicious sign-in, updated",
            "priority": "High",
            "tags": ["phishing"],
            "custom_fields": {"External ID": "1234", "Source": "EDR"},
            "comment": "Severity raised to High in Sentinel",
        }
    )

    assert not create.called
    assert update.last_request.json() == {"custom_priority_uuid": HIGH_UUID, "tags": [TAG, "identity", "phishing"]}
    # Only the empty field is filled, the other keeps its value, and all are sent back
    assert update_fields.last_request.json() == {
        "custom_fields": [
            {"uuid": EXTERNAL_ID_FIELD, "value": "1234"},
            {"uuid": SOURCE_FIELD, "value": [SENTINEL_OPTION]},
        ]
    }
    assert comment.last_request.json() == {"content": "Severity raised to High in Sentinel"}
    assert results["outcome"] == "updated"
    assert results["matched_by"] == "external_id"


def test_never_lowers_the_priority_nor_resends_unchanged_tags(action, requests_mock):
    case = make_case(custom_priority_uuid=HIGH_UUID)
    requests_mock.get(f"{base_url}cases", json={"items": [case], "total": 1})
    requests_mock.get(f"{base_url}cases/{CASE_UUID}", json=case)

    results = action.run(
        {
            "source": "sentinel",
            "external_id": "1234",
            "title": "Suspicious sign-in",
            "priority": "Low",
            "tags": [TAG.upper()],
        }
    )

    assert results["outcome"] == "updated"
    assert not requests_to(requests_mock, "PATCH", f"cases/{CASE_UUID}")
    assert not requests_to(requests_mock, "POST", f"cases/{CASE_UUID}/comments")


def test_only_comments_the_closed_case_of_a_known_incident(action, requests_mock):
    case = make_case(custom_status={"label": "Closed", "stage": "closed"})
    requests_mock.get(f"{base_url}cases", json={"items": [case], "total": 1})
    comment = requests_mock.post(f"{base_url}cases/{CASE_UUID}/comments", json={})
    requests_mock.get(f"{base_url}cases/{CASE_UUID}", json=case)

    results = action.run(
        {
            "source": "sentinel",
            "external_id": "1234",
            "title": "Suspicious sign-in",
            "priority": "High",
            "tags": ["phishing"],
            "comment": "Incident closed in Sentinel",
        }
    )

    assert comment.last_request.json() == {"content": "Incident closed in Sentinel"}
    assert not requests_to(requests_mock, "PATCH", f"cases/{CASE_UUID}")
    assert not requests_to(requests_mock, "POST", "cases")
    assert results["outcome"] == "updated"


def test_prefers_the_open_case_to_a_closed_one(action, requests_mock):
    closed = make_case(uuid=OTHER_CASE_UUID, custom_status=None, status_uuid=CLOSED_STATUS_UUID)
    opened = make_case()
    requests_mock.get(f"{base_url}cases", json={"items": [closed, opened], "total": 2})
    comment = requests_mock.post(f"{base_url}cases/{CASE_UUID}/comments", json={})
    requests_mock.get(f"{base_url}cases/{CASE_UUID}", json=opened)

    results = action.run({"source": "sentinel", "external_id": "1234", "title": "t", "comment": "again"})

    assert comment.called
    assert results["case_uuid"] == CASE_UUID


def test_escapes_the_commas_of_the_incident_tag(action, requests_mock):
    search = requests_mock.get(f"{base_url}cases", json={"items": [], "total": 0})
    create = requests_mock.post(f"{base_url}cases", json=make_case())

    action.run({"source": " crowdstrike ", "external_id": "ldt:1,2", "title": "Detection"})

    assert parse_qs(urlparse(search.last_request.url).query)["match[tags]"] == ["ext:crowdstrike:ldt:1%2C2"]
    assert create.last_request.json()["tags"] == ["ext:crowdstrike:ldt:1%2C2"]


@pytest.mark.parametrize(
    "arguments,error",
    [
        ({"external_id": "1234", "title": "t"}, "`source` and `external_id` are required to identify the incident"),
        (
            {"source": "sentinel", "external_id": "1234", "title": "t", "priority": "Urgent"},
            "Unknown case priority 'Urgent'. Valid names: High, Low, Medium",
        ),
        (
            {"source": "sentinel", "external_id": "1234", "title": "t", "custom_fields": {"Ticket": "1"}},
            "Unknown custom field 'Ticket'. Valid names: External ID, Source",
        ),
        ({"source": "sentinel", "external_id": "1234"}, "`title` is required to create the case of a new incident"),
    ],
)
def test_reports_invalid_arguments_without_any_change(action, requests_mock, arguments, error):
    requests_mock.get(f"{base_url}cases", json={"items": [], "total": 0})
    create = requests_mock.post(f"{base_url}cases", json=make_case())

    assert action.run(arguments) is None

    assert action.error_message == error
    assert not create.called
