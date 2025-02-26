import os
import pytest
import requests_mock

from stormshield_module.wait_task import WaitForTaskCompletionAction


@pytest.mark.skipif(
    "{'STORMSHIELD_API_TOKEN', 'STORMSHIELD_URL', 'STORMSHIELD_AGENT_ID'}.issubset(os.environ.keys()) == False"
)
def test_integration_wait_task_with_CD(symphony_storage):
    module_configuration = {
        "api_token": os.environ["STORMSHIELD_API_TOKEN"],
        "url": os.environ["STORMSHIELD_URL"],
    }
    action = WaitForTaskCompletionAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = {"task_id": os.environ["STORMSHIELD_AGENT_ID"]}

    response = action.run(arguments)

    assert response is not None
    assert response["status"] == "success"


@pytest.fixture
def wait_task_succeded_message():
    return {
        "taskId": "4050026d-9880-49ff-a658-b995c608464b",
        "status": "Succeeded",
        "requestTime": "2000-31-12T23:50:00Z",
        "startTime": "2000-31-12T23:51:00Z",
        "endTime": "2000-31-12T23:59:59Z",
        "errorCode": 0,
        "errorMessage": "string",
    }


@pytest.fixture
def wait_task_failed_message():
    return {
        "taskId": "4050026d-9880-49ff-a658-b995c608464b",
        "status": "Failed",
        "requestTime": "2000-31-12T23:50:00Z",
        "startTime": "2000-31-12T23:51:00Z",
        "endTime": "2000-31-12T23:59:59Z",
        "errorCode": 0,
        "errorMessage": "Error message",
    }


def test_integration_wait_task_failed(symphony_storage, wait_task_failed_message):
    module_configuration = {
        "api_token": "token",
        "url": "https://stormshield-api-example.eu/",
    }
    action = WaitForTaskCompletionAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://stormshield-api-example.eu/rest/api/v1/agents/tasks/foo",
            json=wait_task_failed_message,
        )

        arguments = {"task_id": "foo"}

        with pytest.raises(Exception) as excinfo:
            action.run(arguments)

        assert str(excinfo.value) == f"The remote task execution has failed: Error message"


def test_integration_wait_task_succeeded(symphony_storage, wait_task_succeded_message):
    module_configuration = {
        "api_token": "token",
        "url": "https://stormshield-api-example.eu/",
    }
    action = WaitForTaskCompletionAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://stormshield-api-example.eu/rest/api/v1/agents/tasks/foo",
            json=wait_task_succeded_message,
        )

        arguments = {"task_id": "foo"}
        response = action.run(arguments)

        assert response is not None
        assert response["status"].lower() == "succeeded"
