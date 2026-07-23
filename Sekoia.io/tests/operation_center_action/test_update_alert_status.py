import uuid

from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sekoiaio.operation_center.update_alert_status import UpdateAlertStatus

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


def test_patch_alert_status_only_accept_valid_status_or_action_uuid(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "random_status", "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}/workflow", json={})

    results: dict = action.run(arguments)
    assert results == None

    arguments = {"status": str(uuid.uuid4()), "uuid": alert_uuid}
    results: dict = action.run(arguments)
    assert results == None


def test_patch_alert_status_fails(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_uuid = str(uuid.uuid4())
    arguments = {"status": "8f206505-af6d-433e-93f4-775d46dc7d0f", "uuid": alert_uuid}

    requests_mock.patch(f"{base_url}/{alert_uuid}/workflow", json={}, status_code=500)
    with patch("tenacity.nap.time"):
        with pytest.raises(Exception):
            action.run(arguments)


def test_patch_alert_status_returns_none_if_uuid_empty(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"status": "PENDING", "uuid": ""}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_patch_alert_status_returns_none_if_uuid_invalid(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"status": "PENDING", "uuid": "not-a-uuid"}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_patch_alert_status_returns_none_if_status_empty(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    arguments = {"status": "", "uuid": str(uuid.uuid4())}

    with pytest.raises(ValidationError):
        action.run(arguments)
    assert requests_mock.call_count == 0


def test_patch_alert_status_accepts_short_id(requests_mock):
    action = UpdateAlertStatus()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    alert_short_id = "AL1234567"
    arguments = {"status": "PENDING", "uuid": alert_short_id}

    requests_mock.patch(f"{base_url}/{alert_short_id}/workflow", json={})

    results: dict = action.run(arguments)
    assert results == {}
