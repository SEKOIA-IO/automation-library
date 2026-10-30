import requests_mock
from bitdefender.actions.remove_block_action import RemoveBlockAction
from bitdefender.models import RemoveBlockActionRequest


def test_remove_block(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = RemoveBlockAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json={"result": True},
            status_code=200,
        )
        arguments = RemoveBlockActionRequest(ids=["block_id_1", "block_id_2"])
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_remove_block_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = RemoveBlockAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json={"error": "Invalid endpoint ID"},
            status_code=400,
        )
        arguments = RemoveBlockActionRequest(ids=["invalid_id"])

        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents"
            )
