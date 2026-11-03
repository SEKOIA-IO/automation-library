from urllib.parse import parse_qs, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from easyvista import EasyVistaConfiguration


class CredentialConfigurationError(ValueError):
    pass


class IdempotentRetryAdapter(HTTPAdapter):
    """urllib3 also retries POST connection failures unless explicitly prevented."""

    def __init__(self):
        super().__init__(
            max_retries=Retry(
                total=2,
                connect=2,
                read=0,
                status=2,
                other=0,
                backoff_factor=1,
                status_forcelist=(502, 503, 504),
                allowed_methods=frozenset({"GET", "PUT", "DELETE"}),
                respect_retry_after_header=False,
                raise_on_status=False,
            )
        )
        self.no_retry = HTTPAdapter(max_retries=0)

    def send(self, request, **kwargs):
        append_values = parse_qs(urlsplit(request.url).query).get("append", [])
        is_append = request.method == "PUT" and any(value.casefold() in {"true", "1"} for value in append_values)
        if is_append or request.method not in self.max_retries.allowed_methods:
            return self.no_retry.send(request, **kwargs)
        return super().send(request, **kwargs)

    def close(self):
        self.no_retry.close()
        super().close()


class ApiClient(requests.Session):
    def __init__(self, configuration: EasyVistaConfiguration):
        super().__init__()
        self.verify = configuration.verify_ssl
        self.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        if configuration.use_token:
            if not configuration.token:
                raise CredentialConfigurationError("`token` is required when `use_token` is true")
            self.headers["Authorization"] = f"Bearer {configuration.token}"
        else:
            if not configuration.username or not configuration.password:
                raise CredentialConfigurationError("`username` and `password` are required when `use_token` is false")
            self.auth = (configuration.username, configuration.password)
        self.mount("https://", IdempotentRetryAdapter())
        self.mount("http://", IdempotentRetryAdapter())

    def request(self, method, url, **kwargs):
        if urlsplit(url).scheme != "https":
            raise ValueError("EasyVista API requests must use HTTPS")
        kwargs.setdefault("timeout", 60)
        kwargs.setdefault("verify", self.verify)
        kwargs.setdefault("allow_redirects", False)
        return super().request(method, url, **kwargs)
