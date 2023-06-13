"""
Defines generic tests for Onyphe resources, define relevant fixtures and import as:
```
from generic_onyphe_tests import *  # noqa: F401, F403
```
"""


import pytest
import requests_mock
from requests.exceptions import HTTPError, TooManyRedirects

from onyphe.errors import MissingAPIkey

base_url = "https://www.onyphe.io/api/v2/simple/"


apikey = "f" * 64


def test_success_paging(OnypheAction, ressource, arguments, result, result_page_0, result_page_1):
    action: OnypheAction = OnypheAction()
    action.module.configuration = {"apikey": apikey}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}", json=result_page_0)
        mock.get(f"{base_url}{ressource}?page=2&apikey={apikey}", json=result_page_1)

        arguments.update({"budget": 2})
        results: dict = action.run(arguments)

        assert results == result
        assert mock.call_count > 0
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"

        if result_page_1 != {}:
            assert mock.call_count == 2
            assert history[1].method == "GET"
            assert history[1].url == f"{base_url}{ressource}?page=2&apikey={apikey}"
        else:
            assert mock.call_count == 1


def test_invalidIP(OnypheAction, bad_ressource, bad_arguments):
    action: OnypheAction = OnypheAction()
    action.module.configuration = {"apikey": apikey}

    with requests_mock.Mocker() as mock:
        mock.get("{base_url}{bad_ressource}", json={}, status_code=404, reason="Not Found")

        for exception, args in bad_arguments:
            pytest.raises(exception, action.run, args)

        assert mock.call_count == 0


def test_quota(OnypheAction, ressource, arguments, result, result_page_0, result_page_1):
    # action should raise an error is no data is retrieved
    # or return a partial result if some data has been retrieved
    # with error message in results["message"]
    action: OnypheAction = OnypheAction()
    action.module.configuration = {"apikey": apikey}
    arguments.update({"budget": 3})

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{base_url}{ressource}?page=1&apikey={apikey}",
            json={"error": 20, "message": "rate limit reached", "status": "nok"},
            status_code=429,
            reason="Too Many Requests",
        )
        mock.get(f"{base_url}{ressource}?page=2&apikey={apikey}", json=result_page_1)

        pytest.raises(HTTPError, action.run, arguments)

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"

    if result_page_1 == {}:
        # skip remaining tests
        return

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}", json=result_page_0)
        mock.get(
            f"{base_url}{ressource}?page=2&apikey={apikey}",
            status_code=429,
            reason="Too Many Requests",
        )

        results: dict = action.run(arguments)

        assert results["error"] == -1
        results["error"] = 0  # init value for full results comparison

        assert results["status"] == "nok"
        results["status"] = "ok"  # init value for full results comparison

        assert results["message"] == "429 Too Many Requests"
        del results["message"]  # init value for full results comparison

        assert results == result_page_0

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"
        assert history[1].method == "GET"
        assert history[1].url == f"{base_url}{ressource}?page=2&apikey={apikey}"

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}", json=result_page_0)
        mock.get(
            f"{base_url}{ressource}?page=2&apikey={apikey}",
            json={"error": 20, "message": "rate limit reached", "status": "nok"},
            status_code=429,
            reason="Too Many Requests",
        )

        results: dict = action.run(arguments)

        assert results["error"] == 20
        results["error"] = 0  # init value for full results comparison

        assert results["status"] == "nok"
        results["status"] = "ok"  # init value for full results comparison

        assert results["message"] == "rate limit reached"
        del results["message"]  # init value for full results comparison

        assert results == result_page_0

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"
        assert history[1].method == "GET"
        assert history[1].url == f"{base_url}{ressource}?page=2&apikey={apikey}"


def test_missing_api_key(OnypheAction, arguments):
    action: OnypheAction = OnypheAction()
    action.module.configuration = {}

    with requests_mock.Mocker() as mock:
        pytest.raises(MissingAPIkey, action.run, arguments)

        assert mock.call_count == 0


def test_invalid_json(OnypheAction, ressource, arguments, result, result_page_0, result_page_1):
    # action should raise an error is no data is retrieved
    # or return a partial result if some data has been retrieved
    # with error message in results["message"]
    action: OnypheAction = OnypheAction()
    action.module.configuration = {"apikey": apikey}
    arguments.update({"budget": 3})

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}")
        mock.get(f"{base_url}{ressource}?page=2&apikey={apikey}", json=result_page_1)

        pytest.raises(ValueError, action.run, arguments)

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"

    if result_page_1 == {}:
        # skip remaining test
        return

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}", json=result_page_0)
        mock.get(f"{base_url}{ressource}?page=2&apikey={apikey}")

        results: dict = action.run(arguments)

        assert results["error"] == -1
        results["error"] = 0  # init value for full results comparison

        assert results["status"] == "nok"
        results["status"] = "ok"  # init value for full results comparison

        assert results["message"] == "JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
        del results["message"]  # init value for full results comparison

        assert results == result_page_0

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"
        assert history[1].method == "GET"
        assert history[1].url == f"{base_url}{ressource}?page=2&apikey={apikey}"


def test_network_error(OnypheAction, ressource, arguments, result, result_page_0, result_page_1):
    # action should raise an error is no data is retrieved
    # or return a partial result if some data has been retrieved
    # with error message in results["message"]
    action: OnypheAction = OnypheAction()
    action.module.configuration = {"apikey": apikey}
    arguments.update({"budget": 3})

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}", exc=TooManyRedirects())
        mock.get(f"{base_url}{ressource}?page=2&apikey={apikey}", json=result_page_1)

        pytest.raises(TooManyRedirects, action.run, arguments)

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"

    if result_page_1 == {}:
        # skip remaining test
        return

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}?page=1&apikey={apikey}", json=result_page_0)
        mock.get(f"{base_url}{ressource}?page=2&apikey={apikey}", exc=TooManyRedirects())

        results: dict = action.run(arguments)

        assert results["error"] == -1
        results["error"] = 0  # init value for full results comparison

        assert results["status"] == "nok"
        results["status"] = "ok"  # init value for full results comparison

        assert results["message"] == "TooManyRedirects()"
        del results["message"]  # init value for full results comparison

        assert results == result_page_0

        assert mock.call_count == 2
        history = mock.request_history
        assert history[0].method == "GET"
        assert history[0].url == f"{base_url}{ressource}?page=1&apikey={apikey}"
        assert history[1].method == "GET"
        assert history[1].url == f"{base_url}{ressource}?page=2&apikey={apikey}"
