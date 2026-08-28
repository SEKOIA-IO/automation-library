import uuid

import pytest
from pydantic import ValidationError

from sekoiaio.operation_center.get_alert import GetAlert

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/alerts/"
apikey = "fake_api_key"


@pytest.mark.parametrize("alert_uuid", ["781b21f0-4961-450e-b7ed-80e66b04ac87", "ALEhcq5cVfVZ"])
def test_get_alert_by_uuid(requests_mock, alert_uuid):
    action = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"uuid": str(alert_uuid), "stix": True, "cases": True}
    expected_response = {"uuid": str(alert_uuid), "short_id": "ALtest", "status": {"name": "Ongoing"}}

    requests_mock.get(base_url + str(alert_uuid), json=expected_response)

    results: dict = action.run(arguments)

    assert results == expected_response
    assert requests_mock.call_count == 1
    history = requests_mock.request_history
    assert history[0].method == "GET"
    assert history[0].url == f"{base_url}{alert_uuid}?stix=true&cases=true"


def test_get_alert_by_uuid_returns_none_if_http_error(requests_mock):
    action = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = uuid.uuid4()
    arguments = {"uuid": str(alert_uuid)}

    requests_mock.get(base_url + str(alert_uuid), status_code=404)

    results: dict = action.run(arguments)
    assert results is None
    assert action.error_message is not None
    assert any(log["level"] == "error" for log in action.logs)


def test_get_alert_returns_none_if_uuid_empty(requests_mock):
    action = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"uuid": ""}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_get_alert_returns_none_if_uuid_invalid(requests_mock):
    action = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"uuid": "not-a-uuid"}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_get_alert_returns_none_if_uuid_missing(requests_mock):
    action = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments: dict = {}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_get_alert_drops_unset_booleans(requests_mock):
    """`stix`/`cases` left untouched in the node arrive as False, not as None.

    `exclude_none` cannot drop them, so they used to be sent as active
    parameters. They must be omitted, exactly like in the Search Alerts action.
    """
    action = GetAlert()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = "781b21f0-4961-450e-b7ed-80e66b04ac87"
    arguments = {"uuid": alert_uuid, "stix": False, "cases": True}

    requests_mock.get(base_url + alert_uuid, json={"uuid": alert_uuid})

    action.run(arguments)

    url = requests_mock.request_history[0].url
    assert "stix" not in url
    assert url.endswith("?cases=true")
