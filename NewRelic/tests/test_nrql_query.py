import pytest
import requests_mock

from new_relic_modules import NewRelicModule
from new_relic_modules.action_nrql_query import NRQLQueryAction, NRQLQueryActionArguments


@pytest.fixture()
def new_relic_module():
    module = NewRelicModule()
    module.configuration = {"base_url": "https://api.newrelic.com", "api_key": "API_KEY"}
    return module


@pytest.fixture
def arguments():
    return NRQLQueryActionArguments(
        account_ids=[123456], query="SELECT count(*) FROM InfrastructureEvent SINCE 10 DAYS AGO"
    )


@pytest.fixture
def response_count():
    return {"data": {"actor": {"nrql": {"results": [{"count": 255}]}}}}


def test_query(data_storage, new_relic_module, arguments, response_count):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post("https://api.newrelic.com/graphql", json=response_count)
        action = NRQLQueryAction(module=new_relic_module, data_path=data_storage)
        result = action.run(arguments)

        assert result == response_count
