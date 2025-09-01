import requests_mock
from bitdefender.actions.get_block_list_action import GetBlockListAction
from bitdefender.models import (
    GetBlockListActionRequest,
    GetBlockListActionResponse,
    ItemsModel,
    HashModel,
    PathModel,
    ConnectionModel,
)


def test_get_block_list(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = GetBlockListAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    test = {
        "result": {
            "total": 1,
            "page": 1,
            "per_page": 30,
            "pages_count": 1,
            "items": [
                {
                    "type": "hash",
                    "id": "1234",
                    "details": {"algorithm": "sha256", "hash": "abcd1234"},
                }
            ],
        }
    }

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json=test,
            status_code=200,
        )
        arguments = GetBlockListActionRequest(
            page=1,
            per_page=30,
        )
        response = action.run(arguments)
        assert response is not None
        result = response.get("result", {})
        assert result is not None
        assert result == {
            "total": 1,
            "page": 1,
            "perPage": 30,
            "pagesCount": 1,
            "items": [
                {
                    "type": "hash",
                    "id": "1234",
                    "details": {
                        "algorithm": "sha256",
                        "hash": "abcd1234",
                    },
                }
            ],
        }


def test_get_block_list_error(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = GetBlockListAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json={"error": "Invalid type provided."},
            status_code=400,
        )
        arguments = GetBlockListActionRequest(
            page=1,
            per_page=150,
        )
        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents"
            )
