import pytest
import requests_mock

from sentinelone_module.agents.init_scan import InitiateScanAction, InitiateScanArguments


@pytest.fixture(scope="module")
def arguments():
    return InitiateScanArguments()


def test_init_scan(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    agent_action = InitiateScanAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/agents/actions/initiate-scan",
            json={"data": {"affected": 1}},
        )

        results = agent_action.run(arguments)

        assert results["affected"] > 0
