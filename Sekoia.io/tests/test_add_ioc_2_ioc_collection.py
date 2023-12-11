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


@pytest.fixture
def add_ioc_response():
    return {"task_id": "00000000-0000-0000-0000-000000000000"}


def add_ioc(arguments_success, add_ioc_response):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    expected_response = add_ioc_response

    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=expected_response,
        )
        results: dict = action.run(arguments_success)

        assert results == add_ioc_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"


def add_ioc_failed(arguments_failure, add_ioc_response):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    expected_response = add_ioc_response

    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            status_code=400,
        )
        results: dict = action.run(arguments_failure)

        assert result["status_code"] == 400
        assert mock.call_count == 1
