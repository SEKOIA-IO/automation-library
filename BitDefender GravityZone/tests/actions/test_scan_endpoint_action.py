import requests_mock
from bitdefender.actions.scan_endpoint_action import ScanEndpointAction


def test_create_scan_endpoint(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = ScanEndpointAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/network",
            json={"result": True},
            status_code=200,
        )
        arguments = {
            "targetIds": ["5b680f6fb1a43d860a7b23c1"],
            "type": 1,
            "returnAllTaskIds": False,
        }
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_create_scan_endpoint_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = ScanEndpointAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/network",
            json={"error": "Invalid target ID"},
            status_code=400,
        )
        arguments = {"targetIds": ["invalid_id"], "type": 2, "returnAllTaskIds": False}

        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/network"
            )
