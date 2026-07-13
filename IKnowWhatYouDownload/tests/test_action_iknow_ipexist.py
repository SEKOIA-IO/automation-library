import pytest
import requests_mock
from pydantic import ValidationError

from iknowwhatyoudownload.action_iknow_ipexist import IKnowIPExistAction


def test_query_ip():
    action = IKnowIPExistAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        ip = "185.122.161.248"

        send_result = {"ip": ip, "exists": False}
        mock.get(f"{host}/history/exist?key={key}&ip={ip}", json=send_result)

        results = action.run({"ip": ip})
        assert results == send_result

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "GET"


@pytest.mark.parametrize("arguments", [{}, {"ip": ""}, {"ip": "   "}])
def test_query_ip_missing_ip(arguments):
    action = IKnowIPExistAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run(arguments)

    assert mock.call_count == 0


@pytest.mark.parametrize("ip", ["not-an-ip", "999.999.999.999"])
def test_query_ip_invalid_shape(ip):
    action = IKnowIPExistAction()

    key = "my-fake-api-key"
    host = "https://my-fake-host"

    action.module.configuration = {"key": key, "host": host}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run({"ip": ip})

    assert mock.call_count == 0
