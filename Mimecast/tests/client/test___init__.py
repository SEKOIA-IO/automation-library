from unittest.mock import Mock

from pyrate_limiter import Duration, Limiter, RequestRate
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from mimecast_modules.client import ApiClient
from mimecast_modules.client.retry import Retry


def test_api_client_configures_headers_and_adapters() -> None:
    limiter = Limiter(RequestRate(limit=50, interval=Duration.MINUTE))
    auth = Mock(spec=AuthBase)

    client = ApiClient(auth=auth, limiter_batch=limiter, limiter_default=limiter)

    assert client.auth is auth
    assert client.headers["Accept-Encoding"] == "gzip,deflate"

    assert "https://api.services.mimecast.com/siem/v1/batch/events/cg" in client.adapters
    assert "https://" in client.adapters

    batch_adapter = client.adapters["https://api.services.mimecast.com/siem/v1/batch/events/cg"]
    default_adapter = client.adapters["https://"]
    assert isinstance(batch_adapter, HTTPAdapter)
    assert isinstance(default_adapter, HTTPAdapter)
    assert isinstance(batch_adapter.max_retries, Retry)
    assert isinstance(default_adapter.max_retries, Retry)
