import pytest
import requests

from sophos_module.actions.action_sophos_edr_deisolate import ActionSophosEDRDeIsolateEndpoint
from sophos_module.actions.action_sophos_edr_isolate import ActionSophosEDRIsolateEndpoint
from tests.actions.conftest import DATA_REGION, ENDPOINT_ID

ISOLATION_URL = f"{DATA_REGION}/endpoint/v1/endpoints/{ENDPOINT_ID}/isolation"


def isolation_status(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "lastEnabledAt": "2024-10-03 09.50.54 UTC",
        "lastEnabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
        "lastDisabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
    }


@pytest.fixture
def action(module):
    return ActionSophosEDRIsolateEndpoint(module)


@pytest.mark.parametrize("enabled, label", [(True, "enabled"), (False, "disabled")])
def test_set_isolation_status_already_in_the_desired_state(action, mock_api, enabled, label):
    mock_api.get(ISOLATION_URL, json=isolation_status(enabled))

    result = action.set_isolation_status(ENDPOINT_ID, enabled=enabled)

    assert result == {**isolation_status(enabled), "message": f"Already {label}"}
    assert not any(request.method == "PATCH" for request in mock_api.request_history)


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize(
    "comment, expected_body",
    [(None, {}), ("isolated by Sekoia.io", {"comment": "isolated by Sekoia.io"})],
)
def test_set_isolation_status_changes_the_state(action, mock_api, enabled, comment, expected_body):
    mock_api.get(ISOLATION_URL, json=isolation_status(not enabled))
    mock_api.patch(ISOLATION_URL, json=isolation_status(enabled))

    assert action.set_isolation_status(ENDPOINT_ID, enabled=enabled, comment=comment) == isolation_status(enabled)
    assert mock_api.last_request.json() == {"enabled": enabled, **expected_body}


def test_set_isolation_status_changed_too_recently(action, mock_api):
    mock_api.get(ISOLATION_URL, json=isolation_status(False))
    mock_api.patch(ISOLATION_URL, status_code=400, json={"requestId": "r-1", "message": "Invalid request"})

    result = action.set_isolation_status(ENDPOINT_ID, enabled=True)

    assert result == {
        **isolation_status(False),
        "requestId": "r-1",
        "error": "Isolation status was changed recently",
        "message": "We recommend that you wait for a period of time between turning endpoint isolation on and off",
    }


@pytest.mark.parametrize("status_code", [403, 404, 500])
def test_set_isolation_status_other_errors_are_raised(action, mock_api, status_code):
    mock_api.get(ISOLATION_URL, json=isolation_status(False))
    mock_api.patch(ISOLATION_URL, status_code=status_code, json={"message": "error"})

    with pytest.raises(requests.HTTPError):
        action.set_isolation_status(ENDPOINT_ID, enabled=True)


@pytest.mark.parametrize(
    "action_class, enabled",
    [(ActionSophosEDRIsolateEndpoint, True), (ActionSophosEDRDeIsolateEndpoint, False)],
)
@pytest.mark.parametrize("arguments, comment", [({}, None), ({"comment": "why"}, "why")])
def test_run(module, action_class, enabled, arguments, comment):
    action = action_class(module)
    calls = []
    action.set_isolation_status = lambda **kwargs: calls.append(kwargs) or "result"

    assert action.run({"endpoint_id": ENDPOINT_ID, **arguments}) == "result"
    assert calls == [{"endpoint_id": ENDPOINT_ID, "enabled": enabled, "comment": comment}]
