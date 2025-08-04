import requests_mock
from bitdefender.actions.push_block_action import PushBlockAction
from bitdefender.models import BlockListModel, RuleModel, HashModel


def test_push_block(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = PushBlockAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json={"result": True},
            status_code=200,
        )
        arguments = BlockListModel(
            type="hash",
            rules=[RuleModel(details=HashModel(algorithm="sha256", hash="abcd1234"))],
        )
        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_push_block_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = PushBlockAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json={"error": "Invalid type provided."},
            status_code=400,
        )
        arguments = BlockListModel(
            type="hash",
            rules=[RuleModel(details=HashModel(algorithm="sha256", hash="abcd1234"))],
        )
        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents"
            )
