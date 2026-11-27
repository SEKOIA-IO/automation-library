from sophos_module.actions.action_sophos_edr_deisolate import ActionSophosEDRDeIsolateEndpoint
from tests.actions.conftest import DATA_REGION, ENDPOINT_ID

ISOLATION_URL = f"{DATA_REGION}/endpoint/v1/endpoints/{ENDPOINT_ID}/isolation"


def test_deisolate_endpoint(module, mock_api):
    mock_api.get(ISOLATION_URL, json={"enabled": True})
    mock_api.patch(ISOLATION_URL, json={"enabled": False})

    result = ActionSophosEDRDeIsolateEndpoint(module).run({"endpoint_id": ENDPOINT_ID, "comment": "back to normal"})

    assert result == {"enabled": False}
    assert mock_api.last_request.json() == {"enabled": False, "comment": "back to normal"}
