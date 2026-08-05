from unittest.mock import Mock, patch

import pytest
import requests

from sekoiaio.operation_center.update_case import UpdateCase

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/cases"
apikey = "fake_api_key"


def test_update_case_success(requests_mock):
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    case_uuid = "case-123"
    requests_mock.patch(f"{base_url}/{case_uuid}", json={"uuid": case_uuid, "title": "updated"})

    result = action.run({"uuid": case_uuid, "title": "updated"})
    assert result == {"uuid": case_uuid, "title": "updated"}


def test_update_case_ignores_empty_description_when_reopening(requests_mock):
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    case_uuid = "case-123"
    requests_mock.patch(f"{base_url}/{case_uuid}", json={"uuid": case_uuid})

    action.run({"uuid": case_uuid, "status_uuid": "open-status", "description": ""})

    sent_payload = requests_mock.request_history[0].json()
    assert sent_payload == {"status_uuid": "open-status"}


def test_update_case_retries_read_timeout_then_succeeds():
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ok_response = Mock()
    ok_response.status_code = 200
    ok_response.ok = True
    ok_response.content = b"{}"
    ok_response.json.return_value = {}

    with patch("sekoiaio.operation_center.update_case.requests.patch") as patched_request:
        patched_request.side_effect = [requests.ReadTimeout("timeout"), ok_response]

        with patch("tenacity.nap.time"):
            result = action.run({"uuid": "case-123", "title": "updated"})

    assert result == {}
    assert patched_request.call_count == 2


def test_update_case_timeout_error_is_explicit():
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with patch("sekoiaio.operation_center.update_case.requests.patch") as patched_request:
        patched_request.side_effect = requests.ReadTimeout("timeout")

        with patch("tenacity.nap.time"):
            with pytest.raises(RuntimeError, match="Timed out while updating case after retries"):
                action.run({"uuid": "case-123", "description": "very large description"})


def test_update_case_timeout_with_description_falls_back_without_description():
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ok_response = Mock()
    ok_response.status_code = 200
    ok_response.ok = True
    ok_response.content = b"{}"
    ok_response.json.return_value = {}

    with patch.object(action, "perform_request") as perform_request:
        perform_request.side_effect = [requests.ReadTimeout("timeout"), ok_response]
        result = action.run({"uuid": "case-123", "status_uuid": "open-status", "description": "big payload"})

    assert result == {}
    assert perform_request.call_count == 2
    first_payload = perform_request.call_args_list[0].kwargs["payload"]
    second_payload = perform_request.call_args_list[1].kwargs["payload"]
    assert first_payload == {"status_uuid": "open-status", "description": "big payload"}
    assert second_payload == {"status_uuid": "open-status"}


def test_update_case_only_empty_description_does_not_call_api(requests_mock):
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    result = action.run({"uuid": "case-123", "description": ""})

    assert result == {}
    assert requests_mock.request_history == []
