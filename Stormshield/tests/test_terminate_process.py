import os
import pytest
import requests_mock

from stormshield_module.process_actions import TerminateProcessAction


@pytest.mark.skipif(
    "{'STORMSHIELD_API_TOKEN', 'STORMSHIELD_URL', 'STORMSHIELD_AGENT_ID'}.issubset(os.environ.keys()) == False"
)
def test_integration_process_terminate_with_CD(symphony_storage):
    module_configuration = {
        "api_token": os.environ["STORMSHIELD_API_TOKEN"],
        "url": os.environ["STORMSHIELD_URL"],
    }
    action = TerminateProcessAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = {"id": os.environ["STORMSHIELD_AGENT_ID"], "processPath": os.environ["STORMSHIELD_PROCESS_PATH"]}

    response = action.run(arguments)

    assert response is not None
    assert response["status"] == "success"


@pytest.fixture
def process_terminate_message():
    return {
        "taskId": "4050026d-9880-49ff-a658-b995c608464b",
        "status": "Succeeded",
        "requestTime": "2000-31-12T23:50:00Z",
        "startTime": "2000-31-12T23:51:00Z",
        "endTime": "2000-31-12T23:59:59Z",
        "errorCode": 0,
        "errorMessage": "string",
    }


def test_integration_process_terminate(symphony_storage, process_terminate_message):
    module_configuration = {
        "api_token": "token",
        "url": "https://stormshield-api-example.eu/",
    }
    action = TerminateProcessAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://stormshield-api-example.eu/rest/api/v1/agents/foo/tasks/process-termination",
            json=process_terminate_message,
        )

        arguments = {"id": "foo", "processPath": "C:\\Windows\\system32\\notepad.exe"}
        response = action.run(arguments)

        assert response is not None
        assert response["status"].lower() == "succeeded"
