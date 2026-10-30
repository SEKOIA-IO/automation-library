import requests_mock
from bitdefender.actions.kill_process_action import KillProcessAction


def test_kill_process(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = KillProcessAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/network",
            json={"result": True},
            status_code=200,
        )
        arguments = {
            "processId": "12345",
            "path": "/var/log",
            "endpointId": "endpoint123",
        }
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_kill_process_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = KillProcessAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/network",
            json={"error": "Invalid target ID"},
            status_code=400,
        )
        arguments = {
            "processId": "12345",
            "path": "/var/log",
            "endpointId": "endpoint123",
        }

        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.0/jsonrpc/network"
            )
