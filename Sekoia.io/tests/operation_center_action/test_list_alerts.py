import uuid

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
