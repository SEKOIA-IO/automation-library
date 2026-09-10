import pytest
import requests_mock
from sekoiaio.operation_center.assets_merge import Arguments, Response, MergeAssets

module_base_url = "https://api.sekoia.io"
apikey = "fake_api_key"


def test_asset_merge(requests_mock):
    # Mock the HTTP response

    mock_response = {"status_code": 200, "headers": {"Content-Type": "application/json"}}
    requests_mock.post(
        "https://api.sekoia.io/v2/asset-management/assets/merge",
        status_code=mock_response["status_code"],
        headers=mock_response["headers"],
    )

    # Create the arguments
    arguments = Arguments(
        destination="f6867c2e-a68d-4f33-a903-f14d21c85b9e",
        sources=["3ed892b7-5fc8-42b9-af2e-448775c090f2", "96b74f9e-52f5-4aa8-be9d-47011dd09478"],
    )

    # Instantiate and run the action
    action = MergeAssets()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    result = action.run(arguments)

    # Interprete the dict correctly if the response is serialized to a dict:
    if isinstance(result, dict):
        result = Response(**result)

    # Assert the response
    assert isinstance(result, Response)
    assert result.status_code == mock_response["status_code"]
    assert result.headers["Content-Type"] == mock_response["headers"]["Content-Type"]


def test_asset_merge_with_dict_arguments(requests_mock):
    requests_mock.post(
        "https://api.sekoia.io/v2/asset-management/assets/merge",
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    action = MergeAssets()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    result = action.run(
        {
            "destination": "f6867c2e-a68d-4f33-a903-f14d21c85b9e",
            "sources": ["3ed892b7-5fc8-42b9-af2e-448775c090f2"],
        }
    )

    assert isinstance(result, dict)
    assert result["status_code"] == 200


def test_asset_merge_logs_error_on_http_failure(requests_mock):
    requests_mock.post(
        "https://api.sekoia.io/v2/asset-management/assets/merge",
        status_code=500,
        headers={"Content-Type": "application/json"},
    )

    action = MergeAssets()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    result = action.run(
        {
            "destination": "f6867c2e-a68d-4f33-a903-f14d21c85b9e",
            "sources": ["3ed892b7-5fc8-42b9-af2e-448775c090f2"],
        }
    )

    assert result["status_code"] == 500
    assert action.error_message is not None
    assert "HTTP Request failed" in action.error_message
