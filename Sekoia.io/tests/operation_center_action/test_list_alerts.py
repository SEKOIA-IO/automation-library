import uuid
from urllib.parse import parse_qs, urlparse

from sekoiaio.operation_center import ListAlerts

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/alerts"
apikey = "fake_api_key"


def test_list_alerts(requests_mock):
    action = ListAlerts()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = uuid.uuid4()
    arguments = {
        "match[uuid]": str(alert_uuid),
        "date[created_at]": "2025-11-12T07:38:22.000+00:00,2025-11-12T08:38:22.000+00:00",
    }
    expected_response = {"total": 0, "items": []}

    requests_mock.get(base_url, json=expected_response)

    results: dict = action.run(arguments)

    assert results == expected_response
    assert requests_mock.call_count == 1
    history = requests_mock.request_history
    assert history[0].method == "GET"
    assert (
        history[0].url
        == f"{base_url}?match%5Buuid%5D={alert_uuid}&date%5Bcreated_at%5D=2025-11-12T07%3A38%3A22.000%2B00%3A00%2C2025-11-12T08%3A38%3A22.000%2B00%3A00"
    )


def test_list_alerts_drops_empty_and_false_parameters(requests_mock):
    """Only parameters the user actually set must be sent, mirroring the API.

    Empty strings, None and boolean False are unset filters injected by the
    platform node; sending them makes the API return no results.
    """
    action = ListAlerts()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {
        "match[title]": "",  # unset filter -> must be dropped
        "match[rule_name]": "",  # unset filter -> must be dropped
        "match[rule_uuid]": None,  # unset filter -> must be dropped
        "is_assigned_to_case": False,  # unset bool -> must be dropped
        "visible": True,  # set bool -> must be kept
        "limit": 20,  # int -> must be kept
        "offset": 0,  # int 0 -> must be kept (not confused with False/empty)
        "match[status_name]": "ongoing",  # set filter -> must be kept
    }
    expected_response = {"total": 0, "items": []}
    requests_mock.get(base_url, json=expected_response)

    action.run(arguments)

    url = requests_mock.request_history[0].url
    sent = requests_mock.request_history[0].qs
    # dropped
    assert "match[title]" not in sent
    assert "match[rule_name]" not in sent
    assert "match[rule_uuid]" not in sent
    assert "is_assigned_to_case" not in sent
    # kept
    assert sent["limit"] == ["20"]
    assert sent["offset"] == ["0"]
    assert sent["match[status_name]"] == ["ongoing"]
    # booleans normalized to lowercase, never Python's capital "True"
    assert "visible=true" in url
    assert "visible=True" not in url


def test_list_alerts_forwards_resolved_title_and_custom_field(requests_mock):
    """Alerts without a custom title display their rule name as title.

    `match[title]` misses them; `match[resolved_title]` is the filter matching
    the displayed title, so it must reach the API along with `match[custom_field]`.
    """
    action = ListAlerts()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    title = "CrowdStrike Falcon Intrusion Detection Informational Severity"
    custom_field = "123e4567-e89b-12d3-a456-426614174000:Phishing"
    arguments = {
        "match[title]": "",
        "match[resolved_title]": title,
        "match[custom_field]": custom_field,
    }
    requests_mock.get(base_url, json={"total": 0, "items": []})

    action.run(arguments)

    sent = parse_qs(urlparse(requests_mock.request_history[0].url).query)
    assert sent == {"match[resolved_title]": [title], "match[custom_field]": [custom_field]}
