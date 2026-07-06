import uuid

from unittest.mock import patch

import pytest
from sekoiaio.operation_center.update_alert_status import (
    NonRetryableAlertStatusError,
    UpdateAlertStatus,
)

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/alerts"
apikey = "fake_api_key"


def test_patch_alert_status(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "PENDING", "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}/workflow", json={})

    results: dict = action.run(arguments)
    assert results == {}


def test_patch_alert_status_support_action_uuid(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "8f206505-af6d-433e-93f4-775d46dc7d0f", "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}/workflow", json={})

    results: dict = action.run(arguments)
    assert results == {}


def test_patch_alert_status_rejects_unknown_status_values(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "random_status", "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}/workflow", json={})
    requests_mock.get(module_base_url + "api/v1/sic/custom_statuses", json={"items": []})

    results: dict | None = action.run(arguments)
    assert results is None

    arguments = {"status": "not-a-valid-uuid", "uuid": alert_uuid}
    results = action.run(arguments)
    assert results is None


def test_patch_alert_status_support_custom_status_uuid(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    custom_status_uuid = str(uuid.uuid4())
    arguments = {"status": custom_status_uuid, "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}", json={})

    results: dict = action.run(arguments)
    assert results == {}


def test_patch_alert_status_support_custom_status_name(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    custom_status_uuid = str(uuid.uuid4())
    arguments = {"status": "ImONit", "uuid": alert_uuid}

    requests_mock.get(
        module_base_url + "api/v1/sic/custom_statuses",
        json={
            "items": [
                {
                    "uuid": custom_status_uuid,
                    "label": "ImONit",
                    "description": "My in progress custom status",
                }
            ]
        },
    )
    requests_mock.patch(f"{base_url}/{alert_uuid}", json={})

    results: dict = action.run(arguments)
    assert results == {}


def test_patch_alert_status_support_custom_status_name_from_name_field(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    custom_status_uuid = str(uuid.uuid4())
    arguments = {"status": "my-custom-status", "uuid": alert_uuid}

    requests_mock.get(
        module_base_url + "api/v1/sic/custom_statuses",
        json={
            "data": [
                {
                    "uuid": custom_status_uuid,
                    "name": "My-Custom-Status",
                    "description": "custom status resolved from name field",
                }
            ]
        },
    )
    requests_mock.patch(f"{base_url}/{alert_uuid}", json={})

    results: dict = action.run(arguments)
    assert results == {}


def test_patch_alert_status_support_custom_statuses_container(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    custom_status_uuid = str(uuid.uuid4())
    arguments = {"status": "mystatus", "uuid": alert_uuid}

    requests_mock.get(
        module_base_url + "api/v1/sic/custom_statuses",
        json={
            "custom_statuses": [
                {
                    "uuid": custom_status_uuid,
                    "label": "MyStatus",
                    "description": "custom status from custom_statuses key",
                }
            ]
        },
    )
    requests_mock.patch(f"{base_url}/{alert_uuid}", json={})

    results: dict = action.run(arguments)
    assert results == {}


def test_patch_alert_status_custom_status_lookup_fails_on_server_error(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "random_status", "uuid": alert_uuid}

    requests_mock.get(module_base_url + "api/v1/sic/custom_statuses", json={}, status_code=500)

    with patch("tenacity.nap.time"):
        with pytest.raises(Exception):
            action.run(arguments)


def test_patch_alert_status_custom_status_lookup_fails_on_client_error_without_retry(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "random_status", "uuid": alert_uuid}

    requests_mock.get(module_base_url + "api/v1/sic/custom_statuses", text="forbidden", status_code=403)

    with patch("tenacity.nap.time") as nap_mock:
        with pytest.raises(NonRetryableAlertStatusError):
            action.run(arguments)

    nap_mock.assert_not_called()


def test_patch_alert_status_custom_status_lookup_fails_on_invalid_json_without_retry(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "random_status", "uuid": alert_uuid}

    requests_mock.get(module_base_url + "api/v1/sic/custom_statuses", text="not-json")

    with patch("tenacity.nap.time") as nap_mock:
        with pytest.raises(NonRetryableAlertStatusError):
            action.run(arguments)

    nap_mock.assert_not_called()


def test_extract_custom_statuses_unexpected_payload_raises_value_error():
    with pytest.raises(ValueError):
        UpdateAlertStatus._extract_custom_statuses({"unexpected": "format"})


def test_patch_alert_status_fails(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "8f206505-af6d-433e-93f4-775d46dc7d0f", "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}/workflow", json={}, status_code=500)
    with patch("tenacity.nap.time"):
        with pytest.raises(Exception):
            action.run(arguments)
