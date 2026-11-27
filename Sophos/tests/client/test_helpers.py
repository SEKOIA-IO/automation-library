from unittest.mock import Mock

import pytest
import requests
import urllib3

from sophos_module.client.helpers import retry, retry_strategy


def http_error(status_code: int | None) -> requests.HTTPError:
    response = None
    if status_code is not None:
        response = requests.Response()
        response.status_code = status_code
    return requests.HTTPError(response=response)


@pytest.mark.parametrize(
    "error",
    [
        http_error(429),
        http_error(503),
        http_error(None),
        requests.Timeout(),
        requests.ConnectionError(),
        urllib3.exceptions.TimeoutError(),
    ],
)
def test_retry_on_transient_errors(error):
    func = Mock(side_effect=[error, "ok"])
    assert retry(max_retries=3)(func)() == "ok"
    assert func.call_count == 2


@pytest.mark.parametrize("error", [http_error(400), http_error(403), ValueError("boom")])
def test_no_retry_on_other_errors(error):
    func = Mock(side_effect=error)
    with pytest.raises(type(error)):
        retry(max_retries=3)(func)()
    assert func.call_count == 1


def test_retry_strategy_stops_after_max_retries():
    func = Mock(side_effect=http_error(500))
    with pytest.raises(requests.HTTPError):
        retry_strategy(max_retries=2)(func)()
    assert func.call_count == 2
