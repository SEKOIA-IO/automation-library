import os

import pytest

from harfanglab.endpoint_actions import EndpointGroupDeisolationAction


@pytest.mark.skipif(
    "{'HARFANGLAB_API_TOKEN', 'HARFANGLAB_URL', 'HARFANGLAB_GROUP_ID'}.issubset(os.environ.keys()) == False"
)
def test_integration_isolate_group(symphony_storage):
    module_configuration = {
        "api_token": os.environ["HARFANGLAB_API_TOKEN"],
        "url": os.environ["HARFANGLAB_URL"],
    }
    action = EndpointGroupDeisolationAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    arguments = {"id": os.environ["HARFANGLAB_GROUP_ID"]}

    response = action.run(arguments)

    assert response is not None
    assert len(response.get("unrequested", [])) > 0
