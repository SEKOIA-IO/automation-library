import os

import pytest

from harfanglab.endpoint_actions import EndpointAgentDeisolationAction


@pytest.mark.skipif(
    "{'HARFANGLAB_API_TOKEN', 'HARFANGLAB_URL', 'HARFANGLAB_AGENT_ID'}.issubset(os.environ.keys()) == False"
)
def test_integration_isolate_agent(symphony_storage):
    module_configuration = {
        "api_token": os.environ["HARFANGLAB_API_TOKEN"],
        "url": os.environ["HARFANGLAB_URL"],
    }
    action = EndpointAgentDeisolationAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = {"id": os.environ["HARFANGLAB_AGENT_ID"]}

    response = action.run(arguments)

    assert response is not None
    assert len(response.get("unrequested", [])) > 0
