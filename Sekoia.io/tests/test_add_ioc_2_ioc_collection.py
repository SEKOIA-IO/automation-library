import pytest
import requests_mock

from sekoiaio.intelligence_center.add_ioc_to_ioc_collection import AddIOCtoIOCCollectionAction


@pytest.fixture
def arguments_success():
    return {
        "indicators": "8.8.8.8",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "ipv4-addr.value",
    }


@pytest.fixture
def arguments_failure():
    return {
        "indicators": "8.8.8.8",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "invalid",
    }


def test_add_ioc(arguments_success):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(arguments_success)

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"


def test_add_ioc_failed(arguments_failure):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            status_code=400,
        )
        action.run(arguments_failure)

        assert mock.call_count == 1
        assert action._error is not None
