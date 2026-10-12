import pytest
import requests_mock

from onyphe.errors import MissingAPIkey
from onyphe.utils import get_with_paging

url = "https://www.onyphe.io/api/v2/simple/datascan/example"
apikey = "f" * 64


def test_get_with_paging_without_params():
    with requests_mock.Mocker() as mock:
        mock.get(url, json={"count": 1, "error": 0, "results": [{"ip": "1.1.1.1"}], "status": "ok"})

        result = get_with_paging(url, {"apikey": apikey})

    assert mock.call_count == 1
    assert mock.request_history[0].qs == {"apikey": [apikey]}
    assert result["count"] == 1
    assert result["results"] == [{"ip": "1.1.1.1"}]
    assert result["status"] == "ok"


def test_get_with_paging_reports_onyphe_error():
    with requests_mock.Mocker() as mock:
        mock.get(url, json={"count": 0, "error": 3, "message": "Invalid query", "status": "nok"})

        result = get_with_paging(url, {"apikey": apikey}, params={"page": 1})

    assert mock.call_count == 1
    assert result["error"] == 3
    assert result["message"] == "Invalid query"
    assert result["status"] == "nok"


def test_get_with_paging_requires_apikey():
    with requests_mock.Mocker() as mock:
        with pytest.raises(MissingAPIkey) as excinfo:
            get_with_paging(url, {})

    assert mock.call_count == 0
    assert str(excinfo.value) == "MissingAPIkey The endpoint you are requesting requires an API key"


def test_missing_apikey_custom_message():
    assert str(MissingAPIkey("custom")) == "MissingAPIkey custom"
