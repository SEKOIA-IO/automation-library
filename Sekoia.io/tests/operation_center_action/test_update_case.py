from unittest.mock import patch

from requests import Response

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

    ok_response = Response()
    ok_response.status_code = 200
    ok_response._content = b"{}"
    ok_response.headers["Content-Type"] = "application/json"

    with patch("sekoia_automation.action.requests.request") as patched_request:
        patched_request.side_effect = [TimeoutError("timeout"), ok_response]

        with patch("tenacity.nap.time"):
            result = action.run({"uuid": "case-123", "title": "updated"})

    assert result == {}
    assert patched_request.call_count == 2


def test_update_case_timeout_with_only_description_skips_reduced_empty_payload():
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with patch("sekoia_automation.action.requests.request") as patched_request:
        patched_request.side_effect = TimeoutError("timeout")

        with patch("tenacity.nap.time"):
            result = action.run({"uuid": "case-123", "description": "very large description"})

    assert result == {}
    assert action.error_message is None


def test_update_case_timeout_with_description_falls_back_without_description():
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with patch.object(action, "_execute_http_request") as execute_http_request:
        execute_http_request.side_effect = [None, {}]
        result = action.run({"uuid": "case-123", "status_uuid": "open-status", "description": "big payload"})

    assert result == {}
    assert execute_http_request.call_count == 2
    first_payload = execute_http_request.call_args_list[0].kwargs["body"]
    second_payload = execute_http_request.call_args_list[1].kwargs["body"]
    assert first_payload == {"status_uuid": "open-status", "description": "big payload"}
    assert second_payload == {"status_uuid": "open-status"}


def test_update_case_only_empty_description_does_not_call_api(requests_mock):
    action = UpdateCase()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    result = action.run({"uuid": "case-123", "description": ""})

    assert result == {}
    assert requests_mock.request_history == []
