import os
import pytest
import requests_mock

from stormshield_module.quarantined_file_actions import QuarantineFileAction


@pytest.mark.skipif(
    "{'STORMSHIELD_API_TOKEN', 'STORMSHIELD_URL', 'STORMSHIELD_AGENT_ID', 'STORMSHIELD_FILE_PATH'}.issubset(os.environ.keys()) == False"
)
def test_integration_quarantine_file_with_CD(symphony_storage):
    module_configuration = {
        "api_token": os.environ["STORMSHIELD_API_TOKEN"],
        "url": os.environ["STORMSHIELD_URL"],
    }
    action = QuarantineFileAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = {"id": os.environ["STORMSHIELD_AGENT_ID"], "filePath": os.environ["STORMSHIELD_FILE_PATH"]}

    response = action.run(arguments)

    assert response is not None
    assert response["status"] == "success"


@pytest.fixture
def quarantine_file_message():
    return {
        "taskId": "4050026d-9880-49ff-a658-b995c608464b",
        "status": "Succeeded",
        "requestTime": "2000-31-12T23:50:00Z",
        "startTime": "2000-31-12T23:51:00Z",
        "endTime": "2000-31-12T23:59:59Z",
        "errorCode": 0,
        "errorMessage": "string",
    }


def test_integration_quarantine_file(symphony_storage, quarantine_file_message):
    module_configuration = {
        "api_token": "token",
        "url": "https://stormshield-api-example.eu/",
    }
    action = QuarantineFileAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://stormshield-api-example.eu/rest/api/v1/agents/foo/tasks/file-quarantine",
            json=quarantine_file_message,
        )

        arguments = {"id": "foo", "filePath": "C:\\Users\\admin\\Downloads\\malware.exe"}
        response = action.run(arguments)

        assert response is not None
        assert response["status"].lower() == "succeeded"
