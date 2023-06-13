import os

import pytest
import requests_mock

from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule
from sentinelone_module.rso import RemoteScriptsFilters
from sentinelone_module.rso.execute import (
    ExecuteRemoteScriptAction,
    ExecuteRemoteScriptArguments,
    ExecuteRemoteScriptResult,
    ExecuteRemoteScriptSettings,
    OutputDestination,
)


@pytest.fixture(scope="module")
def arguments():
    return ExecuteRemoteScriptArguments(
        script_id="1234566789",
        output_destination=OutputDestination.sentinel_cloud,
        task_description="My integration task",
        timeout=60,
        settings=ExecuteRemoteScriptSettings(
            password="Mypa$$w0rd",
            inputParams="'--download -u https://app.sekoia.io/assets/files/SEKOIA-IO-intake.pem",
        ),
        filters=RemoteScriptsFilters(ids=["1234567"]),
    )


def test_execute_remote_scripts(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    action = ExecuteRemoteScriptAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        # flake8: noqa
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/execute",
            json={"data": {"parentTaskId": "1234567890", "affected": 1}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/status?parentTaskId__in=1234567890",
            json={
                "data": [
                    {
                        "status": "completed",
                        "detailedStatus": "The execution terminated in failure",
                        "parentTaskId": "1234567890",
                        "agentId": "0123456789",
                        "siteId": "9012345678",
                        "scriptResultsSignature": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
                    }
                ]
            },
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/fetch-file?agentId=0123456789&siteId=9012345678&signature=01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b&signatureType=SHA256",
            json={
                "data": {
                    "downloadUrl": "https://eu-central-1-prod-remote-scripts-uploads.s3.eu-central-1.amazonaws.com/rso-results/ac529cce62f2adc2a8219dd527c1eac0308cd3ff2b3820bf79b2bd852fa4e8ae?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIASLITH25OTWGUADEA%2F20220804%2Feu-central-1%2Fs3%2Faws4_request&X-Amz-Date=20220804T084521Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&response-content-disposition=filename%3Dac529cce62f2adc2a8219dd527c1eac0308cd3ff2b3820bf79b2bd852fa4e8ae.zip&X-Amz-Signature=41eae839d234bc1ceead142617a75d00c1079a4c2858bb840b99230a188562b1",
                    "fileName": "ac529cce62f2adc2a8219dd527c1eac0308cd3ff2b3820bf79b2bd852fa4e8ae.zip",
                }
            },
        )
        # flake8: qa
        result = action.run(arguments)
        assert result is not None
        assert result.get("status") == "succeed"
        # flake8: noqa
        assert (
            result.get("result_file", {}).get("download_url")
            == "https://eu-central-1-prod-remote-scripts-uploads.s3.eu-central-1.amazonaws.com/rso-results/ac529cce62f2adc2a8219dd527c1eac0308cd3ff2b3820bf79b2bd852fa4e8ae?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIASLITH25OTWGUADEA%2F20220804%2Feu-central-1%2Fs3%2Faws4_request&X-Amz-Date=20220804T084521Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&response-content-disposition=filename%3Dac529cce62f2adc2a8219dd527c1eac0308cd3ff2b3820bf79b2bd852fa4e8ae.zip&X-Amz-Signature=41eae839d234bc1ceead142617a75d00c1079a4c2858bb840b99230a188562b1"
        )
        # flake8: qa


def test_execute_remote_scripts_failed(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    action = ExecuteRemoteScriptAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/execute",
            json={"data": {"parentTaskId": "1234567890", "affected": 1}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/status?parentTaskId__in=1234567890",
            json={
                "data": [
                    {
                        "status": "failed",
                        "detailedStatus": "The execution terminated in failure",
                        "parentTaskId": "1234567890",
                    }
                ]
            },
        )
        result = action.run(arguments)

        assert result["status"] == "failed"


def test_execute_remote_scripts_cancelled(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    action = ExecuteRemoteScriptAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/execute",
            json={"data": {"parentTaskId": "1234567890", "affected": 1}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/status?parentTaskId__in=1234567890",
            json={
                "data": [
                    {
                        "status": "canceled",
                        "detailedStatus": "Execution canceled by user",
                        "parentTaskId": "1234567890",
                    }
                ]
            },
        )
        result = action.run(arguments)

        assert result["status"] == "canceled"


def test_execute_remote_scripts_exhausted_retries(symphony_storage, sentinelone_hostname, sentinelone_module):
    arguments = ExecuteRemoteScriptArguments(
        script_id="1234566789",
        output_destination=OutputDestination.sentinel_cloud,
        task_description="My integration task",
        timeout=1,
        settings=ExecuteRemoteScriptSettings(
            password="Mypa$$w0rd",
            inputParams="'--download -u https://app.sekoia.io/assets/files/SEKOIA-IO-intake.pem",
        ),
        filters=RemoteScriptsFilters(ids=["1234567"]),
    )
    action = ExecuteRemoteScriptAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/execute",
            json={"data": {"parentTaskId": "1234567890", "affected": 1}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/remote-scripts/status?parentTaskId__in=1234567890",
            json={
                "data": [
                    {
                        "status": "in_progress",
                        "detailedStatus": "Execution in progress",
                        "parentTaskId": "1234567890",
                    }
                ]
            },
        )
        result = action.run(arguments)

        assert result["status"] == "timeout"


@pytest.mark.skipif(
    "{'SENTINELONE_HOSTNAME', 'SENTINELONE_API_TOKEN', 'SENTINELONE_AGENT_ID', 'SENTINELONE_REMOTE_SCRIPT_ID'}.issubset(os.environ.keys()) == False"  # noqa
)
def test_execute_remote_scripts_integration(symphony_storage):
    module = SentinelOneModule()
    module.configuration = SentinelOneConfiguration(
        hostname=os.environ["SENTINELONE_HOSTNAME"],
        api_token=os.environ["SENTINELONE_API_TOKEN"],
    )
    arguments = ExecuteRemoteScriptArguments(
        script_id=os.environ["SENTINELONE_REMOTE_SCRIPT_ID"],
        output_destination=OutputDestination.sentinel_cloud,
        task_description="My integration task",
        timeout=360,
        settings=ExecuteRemoteScriptSettings(
            password="Mypa$$w0rd",
            inputParams="--download -u https://app.sekoia.io/assets/files/SEKOIA-IO-intake.pem",
            scriptRuntimeTimeoutSeconds=340,
        ),
        filters=RemoteScriptsFilters(ids=[os.environ["SENTINELONE_AGENT_ID"]]),
    )

    action = ExecuteRemoteScriptAction(module=module, data_path=symphony_storage)
    result = action.run(arguments)
    assert result is not None
    assert result["status"] == "succeed"
