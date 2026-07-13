import pytest
import requests_mock
from pydantic import ValidationError

from iknowwhatyoudownload.action_iknow_iplist import IKnowIPListAction


def test_query_iplist():
    action = IKnowIPListAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        cidr = "14.102.240.0/20"

        send_result = {
            "CIDR": "14.102.240.0/20",
            "peers": [
                {"ip": "14.102.240.1", "date": "2016-12-10T16:49:04.000Z"},
                {"ip": "14.102.240.2", "date": "2016-12-11T16:49:04.000Z"},
                {"ip": "14.102.240.15", "date": "2016-12-12T16:49:04.000Z"},
            ],
        }
        mock.get(f"{host}/history/peers?key={key}&cidr={cidr}", json=send_result)

        results = action.run({"cidr": cidr})
        assert results == send_result

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "GET"


def test_query_iplist_invalid_cidr():
    action = IKnowIPListAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        cidr = "14.102.240.0/20"

        send_result = {"error": "INVALID_CIDR", "message": "value of cidr is invalid"}

        mock.get(f"{host}/history/peers?key={key}&cidr={cidr}", json=send_result)

        results = action.run({"cidr": cidr})
        assert results is None

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "GET"


@pytest.mark.parametrize("arguments", [{}, {"cidr": ""}, {"cidr": "   "}])
def test_query_iplist_missing_cidr(arguments):
    action = IKnowIPListAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run(arguments)

    assert mock.call_count == 0


@pytest.mark.parametrize("cidr", ["not-a-cidr", "192.168.1.1/999"])
def test_query_iplist_invalid_shape(cidr):
    action = IKnowIPListAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run({"cidr": cidr})

    assert mock.call_count == 0
