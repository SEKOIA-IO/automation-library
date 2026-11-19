from typing import Any, cast

import requests_mock
from bitdefender.actions.get_block_list_action import GetBlockListAction
from bitdefender.models import (
    GetBlockListActionRequest,
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
            perPage=30,
        )
        response = action.run(arguments)
        assert response is not None
        assert response == {
            "result": {
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
            perPage=150,
        )
        try:
            action.run(arguments)
        except BaseException as e:
            assert (
                str(e)
                == "400 Client Error: None for url: mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents"
            )


def test_get_block_list_handles_path_connection_and_skips_unknown(symphony_storage):
    module_configuration = {
        "api_key": "token",
        "url": "mock://cloudgz.gravityzone.bitdefender.com",
    }
    action = GetBlockListAction(data_path=symphony_storage)
    action.module.configuration = module_configuration

    payload = {
        "result": {
            "total": 3,
            "page": 1,
            "per_page": 30,
            "pages_count": 1,
            "items": [
                {
                    "type": "path",
                    "id": "p1",
                    "details": {"path": "/tmp/bad.bin"},
                },
                {
                    "type": "connection",
                    "id": "c1",
                    "details": {"direction": "outbound"},
                },
                {
                    "type": "unsupported",
                    "id": "x1",
                    "details": {},
                },
            ],
        }
    }

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "mock://cloudgz.gravityzone.bitdefender.com/api/v1.2/jsonrpc/incidents",
            json=payload,
            status_code=200,
        )
        arguments = GetBlockListActionRequest(page=1, perPage=30)
        response = cast(dict[str, Any], action.run(arguments))

    result_items = response["result"]["items"]
    assert len(result_items) == 2
    assert result_items[0]["type"] == "path"
    assert result_items[1]["type"] == "connection"
