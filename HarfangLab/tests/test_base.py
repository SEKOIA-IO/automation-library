import json
from typing import ClassVar

import pytest
from sekoia_automation.exceptions import MissingActionArgumentError, MissingActionArgumentFileError

from harfanglab.endpoint_actions import EndpointAgentIsolationAction


def test_base_get_url(symphony_storage):
    module_configuration = {
        "api_token": "token",
        "url": "http://harfang.url/",
    }
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    action.module.configuration = module_configuration
    url = action.get_url({"id": "foo"})
    assert url == "http://harfang.url/api/data/endpoint/Agent/foo/isolate/"


class _ActionWithQueryParameters(EndpointAgentIsolationAction):
    endpoint = "/api/data/endpoint/Agent/{id}/"
    query_parameters: ClassVar[list[str]] = ["limit", "isolated", "missing"]


def test_base_get_url_with_query_parameters(symphony_storage):
    action = _ActionWithQueryParameters(data_path=symphony_storage)
    action.module.configuration = {"api_token": "token", "url": "http://harfang.url/"}
    arguments = {"id": "foo", "limit": 10, "isolated": True, "other": "kept"}

    url = action.get_url(arguments)

    assert url == "http://harfang.url/api/data/endpoint/Agent/foo/?limit=10&isolated=1"
    assert arguments == {"other": "kept"}


def test_base_get_headers(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    action.module.configuration = {"api_token": "token", "url": "http://harfang.url/"}

    assert action.get_headers() == {"Authorization": "Token token"}


def test_json_argument_direct_value(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)

    assert action.json_argument("ids", {"ids": ["a", "b"]}) == ["a", "b"]
    assert action._result_as_file is False


def test_json_argument_from_file(symphony_storage):
    (symphony_storage / "ids.json").write_text(json.dumps(["a", "b"]))
    action = EndpointAgentIsolationAction(data_path=symphony_storage)

    assert action.json_argument("ids", {"ids_path": "ids.json"}) == ["a", "b"]
    assert action._result_as_file is True


def test_json_argument_missing_file(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)

    with pytest.raises(MissingActionArgumentFileError):
        action.json_argument("ids", {"ids_path": "does-not-exist.json"})


def test_json_argument_missing_required(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)

    with pytest.raises(MissingActionArgumentError):
        action.json_argument("ids", {})


def test_json_argument_missing_optional(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)

    assert action.json_argument("ids", {}, required=False) is None
