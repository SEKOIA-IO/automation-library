from sekoiaio.operation_center import CreateCase, UpdateCase

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"

CASE_UUID = "095be615-a8ad-4c33-8e9c-c7612fbf6c9f"
CLOSED_STATUS_UUID = "c1ccc455-a896-4e7c-8f4d-b99df293a381"
HIGH_PRIORITY_UUID = "f47455f5-1211-4723-9c4e-63d8752ec65f"
TRUE_POSITIVE_UUID = "6108af3c-010d-4cae-915e-70c748f0e58e"

CASE = {"uuid": CASE_UUID, "short_id": "CAfake", "title": "title", "tags": ["phishing", "ext:INC001"]}
CUSTOM_STATUSES = {
    "items": [
        {"uuid": "5ca52387-a6f7-45c3-a713-856468ffbdd7", "label": "In progress"},
        {"uuid": CLOSED_STATUS_UUID, "label": "Closed"},
    ],
    "total": 2,
}


def make_action(action_class):
    action = action_class()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    return action


def test_create_case_forwards_the_arguments_without_extra_calls(requests_mock):
    action = make_action(CreateCase)
    requests_mock.post(f"{base_url}cases", json=CASE)

    results = action.run({"title": "title", "custom_status_uuid": CLOSED_STATUS_UUID})

    assert results == CASE
    assert requests_mock.call_count == 1
    assert requests_mock.last_request.json() == {"title": "title", "custom_status_uuid": CLOSED_STATUS_UUID}


def test_create_case_resolves_the_names(requests_mock):
    action = make_action(CreateCase)
    statuses = requests_mock.get(f"{base_url}custom_statuses", json=CUSTOM_STATUSES)
    requests_mock.get(
        f"{base_url}custom_priorities", json={"items": [{"uuid": HIGH_PRIORITY_UUID, "label": "High"}], "total": 1}
    )
    requests_mock.get(
        f"{base_url}custom_verdicts",
        json={"items": [{"uuid": TRUE_POSITIVE_UUID, "label": "Confirmed attack"}], "total": 1},
    )
    requests_mock.post(f"{base_url}cases", json=CASE)

    action.run(
        {
            "title": "title",
            "custom_status_uuid": " closed ",
            "custom_priority_uuid": "HIGH",
            "verdict_uuid": "Confirmed attack",
        }
    )

    assert statuses.last_request.qs["match[type]"] == ["case"]
    assert requests_mock.last_request.json() == {
        "title": "title",
        "custom_status_uuid": CLOSED_STATUS_UUID,
        "custom_priority_uuid": HIGH_PRIORITY_UUID,
        "verdict_uuid": TRUE_POSITIVE_UUID,
    }


def test_create_case_lists_the_valid_names_on_unknown_name(requests_mock):
    action = make_action(CreateCase)
    requests_mock.get(f"{base_url}custom_statuses", json=CUSTOM_STATUSES)
    create = requests_mock.post(f"{base_url}cases", json=CASE)

    assert action.run({"title": "title", "custom_status_uuid": "Resolved"}) is None

    assert action.error_message == "Unknown case status 'Resolved'. Valid names: Closed, In progress"
    assert not create.called


def test_create_case_rejects_an_ambiguous_name(requests_mock):
    action = make_action(CreateCase)
    requests_mock.get(
        f"{base_url}custom_statuses",
        json={"items": [{"uuid": "a", "label": "Closed"}, {"uuid": "b", "label": "closed"}], "total": 2},
    )
    create = requests_mock.post(f"{base_url}cases", json=CASE)

    assert action.run({"title": "title", "custom_status_uuid": "Closed"}) is None

    assert "Several case status values are named 'Closed'" in action.error_message
    assert not create.called


def test_create_case_reports_a_lookup_error(requests_mock):
    action = make_action(CreateCase)
    requests_mock.get(f"{base_url}custom_verdicts", status_code=403, json={"message": "Permission denied"})

    assert action.run({"title": "title", "verdict_uuid": "Confirmed attack"}) is None

    assert action.error_message == "GET api/v1/sic/custom_verdicts failed with status 403: Permission denied"


def test_update_case_resolves_the_status_name(requests_mock):
    action = make_action(UpdateCase)
    requests_mock.get(f"{base_url}custom_statuses", json=CUSTOM_STATUSES)
    update = requests_mock.patch(f"{base_url}cases/{CASE_UUID}", json=CASE)

    action.run({"uuid": CASE_UUID, "custom_status_uuid": "Closed"})

    assert update.last_request.json() == {"custom_status_uuid": CLOSED_STATUS_UUID}
