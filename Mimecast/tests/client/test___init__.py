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

    assert callable(client._notify_retry_observer)
    client.set_retry_observer(lambda: None)
    client.clear_retry_observer()


def test_api_client_notifies_retry_observer() -> None:
    limiter = Limiter(RequestRate(limit=50, interval=Duration.MINUTE))
    auth = Mock(spec=AuthBase)
    observer = Mock()

    client = ApiClient(auth=auth, limiter_batch=limiter, limiter_default=limiter)
    client.set_retry_observer(observer)
    client._notify_retry_observer()

    observer.assert_called_once()


def test_api_client_notify_retry_observer_without_registered_callback() -> None:
    limiter = Limiter(RequestRate(limit=50, interval=Duration.MINUTE))
    auth = Mock(spec=AuthBase)

    client = ApiClient(auth=auth, limiter_batch=limiter, limiter_default=limiter)
    client.clear_retry_observer()
    client._notify_retry_observer()
