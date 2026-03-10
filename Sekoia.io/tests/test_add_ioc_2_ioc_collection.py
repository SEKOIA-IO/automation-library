import pytest
import requests_mock

from sekoiaio.intelligence_center.add_ioc_to_ioc_collection import AddIOCtoIOCCollectionAction


@pytest.fixture
def arguments_success():
    return {
        "indicators": ["8.8.8.8", "192.168.1.2", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"],
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
    }


@pytest.fixture
def args_valid_domain():
    return {
        "indicators": ["www.sekoia.io"],
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "domain",
    }


@pytest.fixture
def arguments_with_valid_for():
    return {
        "indicators": ["8.8.8.8", "192.168.1.2", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"],
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
        "valid_for": "90",
    }


@pytest.fixture
def arguments_with_invalid_indicators():
    return {
        "indicators": "8.8.8.8",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
        "valid_for": "90",
    }


@pytest.fixture
def arguments_invalid_type():
    return {
        "indicators": ["8.8.8.8"],
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "invalid",
    }


@pytest.fixture
def arguments_http_error():
    return {
        "indicators": ["8.8.8.8"],
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP",
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

        history = mock.request_history
        assert mock.call_count == 2
        assert history[0].method == "POST"


def test_add_ioc_domain(args_valid_domain):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(args_valid_domain)

        history = mock.request_history
        assert mock.call_count == 1
        assert history[0].method == "POST"


def test_add_ioc_with_validity(arguments_with_valid_for):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(arguments_with_valid_for)

        history = mock.request_history
        assert mock.call_count == 2
        assert history[0].method == "POST"
        assert "valid_until" in history[0].text


def test_add_ioc_should_raise_error_on_invalid_indicator(arguments_with_invalid_indicators):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    with pytest.raises(ValueError):
        action.run(arguments_with_invalid_indicators)


def test_add_ioc_incorrect_type(arguments_invalid_type):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    action.run(arguments_invalid_type)
    assert action._error is not None


@pytest.fixture
def arguments_single_indicator_ipv4():
    return {
        "indicator": "8.8.8.8",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
    }


@pytest.fixture
def arguments_single_indicator_ipv6():
    return {
        "indicator": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
    }


@pytest.fixture
def arguments_single_indicator_domain():
    return {
        "indicator": "www.sekoia.io",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "domain",
    }


@pytest.fixture
def arguments_single_indicator_with_valid_for():
    return {
        "indicator": "8.8.8.8",
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
        "valid_for": "30",
    }


@pytest.fixture
def arguments_no_indicators():
    return {
        "ioc_collection_id": "ioc-collection--00000000-0000-0000-0000-000000000000",
        "indicator_type": "IP address",
    }


def test_add_ioc_single_indicator_ipv4(arguments_single_indicator_ipv4):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(arguments_single_indicator_ipv4)

        history = mock.request_history
        assert mock.call_count == 1
        assert history[0].method == "POST"
        assert "8.8.8.8" in history[0].text


def test_add_ioc_single_indicator_ipv6(arguments_single_indicator_ipv6):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(arguments_single_indicator_ipv6)

        history = mock.request_history
        assert mock.call_count == 1
        assert history[0].method == "POST"
        assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" in history[0].text


def test_add_ioc_single_indicator_domain(arguments_single_indicator_domain):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(arguments_single_indicator_domain)

        history = mock.request_history
        assert mock.call_count == 1
        assert history[0].method == "POST"


def test_add_ioc_single_indicator_with_valid_for(arguments_single_indicator_with_valid_for):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
        )
        action.run(arguments_single_indicator_with_valid_for)

        history = mock.request_history
        assert mock.call_count == 1
        assert history[0].method == "POST"
        assert "valid_until" in history[0].text


def test_add_ioc_no_indicators_raises_error(arguments_no_indicators):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    with pytest.raises(
        ValueError, match="Indicators should be list type, or you should provide a single indicator value"
    ):
        action.run(arguments_no_indicators)


def test_add_ioc_failed(arguments_http_error):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"message": "IOC Collection not found", "code": "INTHREAT2500"}
    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/ioc-collections/ioc-collection--00000000-0000-0000-0000-000000000000/indicators/text",
            json=response,
            status_code=404,
        )

        action.run(arguments_http_error)
        assert action._error is not None
