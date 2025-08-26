import requests_mock
from bitdefender.actions.push_block_action import PushBlockAction
from bitdefender.models import BlockListModel, RuleModel, HashModel, PathModel, ConnectionModel


def test_push_hash_block(symphony_storage):
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
        ).dict(exclude_none=True, by_alias=True)

        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_push_path_block(symphony_storage):
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
            type="path",
            rules=[RuleModel(details=PathModel(path="/path/to/file"))],
        ).dict(exclude_none=True, by_alias=True)

        response = action.run(arguments)
        assert response is not None
        assert response == {"result": True}


def test_push_connection_block(symphony_storage):
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
            type="connection",
            rules=[RuleModel(details=ConnectionModel(ruleName="BlockConnection"))],
        ).dict(exclude_none=True, by_alias=True)

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
        ).dict(exclude_none=True, by_alias=True)
        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents"
            )
