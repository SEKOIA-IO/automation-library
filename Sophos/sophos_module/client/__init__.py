import requests
from requests.adapters import Retry
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from sophos_module.client.auth import SophosApiAuthentication


class ApiClient(requests.Session):
    def __init__(self, auth: AuthBase, nb_retries: int = 5, ratelimit_per_second: int = 100):
        super().__init__()
        self.auth = auth
        adapter = LimiterAdapter(
            per_second=ratelimit_per_second,
            max_retries=Retry(total=nb_retries, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]),
        )
        self.mount("http://", adapter)
        self.mount("https://", adapter)


class SophosApiClient(ApiClient):
    auth: SophosApiAuthentication

    def __init__(self, auth: SophosApiAuthentication, nb_retries: int = 5, ratelimit_per_second: int = 100):
        super().__init__(auth=auth, nb_retries=nb_retries, ratelimit_per_second=ratelimit_per_second)

    def list_siem_events(self, parameters: dict | None = None) -> requests.Response:
        return self.get(
            url=(f"{self.auth.get_credentials().api_url}/siem/v1/events"),
            params=parameters,
        )
