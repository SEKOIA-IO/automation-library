import pytest
import requests_mock

from sekoiaio.intelligence_center.add_ioc_to_ioc_collection import AddIOCtoIOCCollectionAction

IOC_COLLECTION_ID = "ioc-collection--00000000-0000-0000-0000-000000000000"
INDICATORS_TEXT_ENDPOINT = f"http://fake.url/api/v2/inthreat/ioc-collections/{IOC_COLLECTION_ID}/indicators/text"


@pytest.mark.parametrize(
    "arguments, expected_call_count, expected_fragment, expect_valid_until",
    [
        (
            {
                "indicators": ["198.51.100.10", "203.0.113.20", "2001:db8::1"],
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            2,
            None,
            False,
        ),
        (
            {
                "indicators": ["www.sekoia.io"],
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "domain",
            },
            1,
            None,
            False,
        ),
        (
            {
                "indicators": ["198.51.100.10", "203.0.113.20", "2001:db8::1"],
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
                "valid_for": "90",
            },
            2,
            None,
            True,
        ),
        (
            {
                "indicator": "198.51.100.10",
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            1,
            "198.51.100.10",
            False,
        ),
        (
            {
                "indicator": "2001:db8::1",
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            1,
            "2001:db8::1",
            False,
        ),
        (
            {
                "indicator": "www.sekoia.io",
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "domain",
            },
            1,
            None,
            False,
        ),
        (
            {
                "indicator": "198.51.100.10",
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
                "valid_for": "30",
            },
            1,
            None,
            True,
        ),
    ],
    ids=[
        "ip-list",
        "domain-list",
        "ip-list-with-valid-for",
        "single-ipv4",
        "single-ipv6",
        "single-domain",
        "single-ipv4-with-valid-for",
    ],
)
def test_add_ioc_success_cases(arguments, expected_call_count, expected_fragment, expect_valid_until):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    response = {"task_id": "00000000-0000-0000-0000-000000000000"}
    with requests_mock.Mocker() as mock:
        mock.post(INDICATORS_TEXT_ENDPOINT, json=response)
        action.run(arguments)

        history = mock.request_history
        assert mock.call_count == expected_call_count
        assert history[0].method == "POST"
        if expected_fragment:
            assert any(expected_fragment in request.text for request in history)
        if expect_valid_until:
            assert any("valid_until" in request.text for request in history)


def test_add_ioc_should_raise_error_on_invalid_indicator_shape():
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}
    arguments = {
        "indicators": "198.51.100.10",
        "ioc_collection_id": IOC_COLLECTION_ID,
        "indicator_type": "IP address",
        "valid_for": "90",
    }

    with pytest.raises(ValueError):
        action.run(arguments)


def test_add_ioc_incorrect_type():
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}
    arguments = {
        "indicators": ["198.51.100.10"],
        "ioc_collection_id": IOC_COLLECTION_ID,
        "indicator_type": "invalid",
    }

    action.run(arguments)
    assert action._error is not None


@pytest.mark.parametrize(
    "arguments, error_match",
    [
        (
            {
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            "Indicators should be list type, or you should provide a single indicator value",
        ),
        (
            {
                "indicators": [],
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            "No valid IP indicators were provided",
        ),
        (
            {
                "indicators": ["198.51.100.65/32", "198.51.100.67/32"],
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            "CIDR notation is not supported",
        ),
        (
            {
                "indicators": ["198.51.100.10", "198.51.100.65/32"],
                "ioc_collection_id": IOC_COLLECTION_ID,
                "indicator_type": "IP address",
            },
            "Invalid IP indicator",
        ),
    ],
    ids=["missing-indicators", "empty-indicators-list", "cidr-input", "mixed-valid-and-invalid"],
)
def test_add_ioc_ip_validation_errors(arguments, error_match):
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    with pytest.raises(ValueError, match=error_match):
        action.run(arguments)


def test_add_ioc_failed_sets_error_on_post_failure():
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}
    arguments = {
        "indicators": ["www.sekoia.io"],
        "ioc_collection_id": IOC_COLLECTION_ID,
        "indicator_type": "domain",
    }

    response = {"message": "IOC Collection not found", "code": "INTHREAT2500"}
    with requests_mock.Mocker() as mock:
        mock.post(INDICATORS_TEXT_ENDPOINT, json=response, status_code=404)

        action.run(arguments)
        assert action._error is not None


def test_flatten_and_validate_flattens_nested_lists_and_values():
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()

    flattened = action.flatten_and_validate(["198.51.100.10", ["2001:db8::1", 42], None])

    assert flattened == ["198.51.100.10", "2001:db8::1", "42", "None"]


def test_add_ip_action_raises_on_blank_values_with_examples_in_message():
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()

    with pytest.raises(ValueError, match="Examples: 198.51.100.10, 203.0.113.7, 2001:db8::1"):
        action.add_IP_action(["   "], IOC_COLLECTION_ID, 0)


def test_add_ip_action_raises_when_no_valid_ip_is_provided():
    action: AddIOCtoIOCCollectionAction = AddIOCtoIOCCollectionAction()

    with pytest.raises(ValueError, match="No valid IP indicators were provided"):
        action.add_IP_action([], IOC_COLLECTION_ID, 0)
