import pytest
import requests_mock

from sekoiaio.intelligence_center.add_ioc_to_ioc_collection import AddIOCtoIOCCollectionAction


@pytest.fixture
def add_ioc_response():
    return { "task_id":"00000000-0000-0000-0000-000000000000" }


indicators = self.json_argument("indicators", arguments)
        ioc_collection_id = self.json_argument("ioc_collection_id", arguments)
        indicator_type = self.json_argument("indicator_type", arguments)

def add_ioc(add_ioc_response):
    arguments = {"indicators": "8.8.8.8", "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000", "indicator_type": "ipv4-addr.value"}
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    expected_response = add_ioc_response

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text", json=expected_response)
        results: dict = action.run(arguments)

        assert results == add_ioc_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
