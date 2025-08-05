import requests_mock
from bitdefender.actions.quarantine_file_action import QuarantineFileAction


def test_add_quarantine_file(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = QuarantineFileAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.1/jsonrpc/quarantine/computers",
            json={"result": True},
            status_code=200,
        )
        arguments = {
            "endpointIds": ["5b680f6fb1a43d860a7b23c1", "5b680f6fb1a43d860a7b23c2"],
            "filePath": "Z:\\path\\to\\file.txt",
        }
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_add_quarantine_file_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = QuarantineFileAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.1/jsonrpc/quarantine/computers",
            json={"error": "Invalid endpoint ID"},
            status_code=400,
        )
        arguments = {
            "endpointIds": ["invalid_id"],
            "filePath": "Z:\\path\\to\\file.txt",
        }

        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.1/jsonrpc/quarantine/computers"
            )
