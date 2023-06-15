import os
import time

import pytest
import requests_mock

from sentinelone_module.agents.isolation import (
    DeisolateEndpointAction,
    IsolateEndpointAction,
    IsolateEndpointArguments,
)
from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule


@pytest.fixture(scope="module")
def arguments():
    return IsolateEndpointArguments(ids=["1234567890"])


def test_endpoint_isolation(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    isolate_action = IsolateEndpointAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/agents/actions/disconnect",
            json={"data": {"affected": 1}},
        )
        results = isolate_action.run(arguments)

        assert results["affected"] > 0


def test_endpoint_deisolation(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    deisolate_action = DeisolateEndpointAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/agents/actions/connect",
            json={"data": {"affected": 1}},
        )
        results = deisolate_action.run(arguments)

        assert results["affected"] > 0


@pytest.mark.skipif(
    "{'SENTINELONE_HOSTNAME', 'SENTINELONE_API_TOKEN', 'SENTINELONE_AGENT_ID'}.issubset(os.environ.keys()) == False"
)
def test_isolation_and_deisolation_actions(symphony_storage):
    module = SentinelOneModule()
    module.configuration = SentinelOneConfiguration(
        hostname=os.environ["SENTINELONE_HOSTNAME"],
        api_token=os.environ["SENTINELONE_API_TOKEN"],
    )
    arguments = IsolateEndpointArguments(ids=[os.environ["SENTINELONE_AGENT_ID"]])

    isolate_action = IsolateEndpointAction(module=module, data_path=symphony_storage)
    results = isolate_action.run(arguments)
    assert results is not None
    assert results["affected"] > 0

    time.sleep(5)

    deisolate_action = DeisolateEndpointAction(module=module, data_path=symphony_storage)
    results = deisolate_action.run(arguments)
    assert results is not None
    assert results["affected"] > 0
