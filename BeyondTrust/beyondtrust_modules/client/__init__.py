import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import BeyondTrustApiAuthentication


class ApiClient(requests.Session):
    def __init__(
        self, base_url: str, client_id: str, client_secret: str, ratelimit_per_second: int = 20, nb_retries: int = 5
    ):
        super().__init__()
        self._base_url = base_url
        self.auth = BeyondTrustApiAuthentication(base_url=base_url, client_id=client_id, client_secret=client_secret)
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

    def get_session_listing(self, end_time: int) -> requests.Response:
        return self.post(
            f"{self._base_url}/api/reporting",
            data={"generate_report": "AccessSessionListing", "duration": 0, "end_time": end_time},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )

    def get_session(self, session_id: str) -> requests.Response:
        return self.post(
            f"{self._base_url}/api/reporting",
            data={"generate_report": "AccessSession", "lsid": session_id},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )

    def get_syslog(self) -> requests.Response:
        return self.post(
            f"{self._base_url}/api/reporting",
            data={"generate_report": "Syslog"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=120,
            stream=True,
        )
