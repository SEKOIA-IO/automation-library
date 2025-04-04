import requests
from akamai.edgegrid import EdgeGridAuth
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry


class ApiClient(requests.Session):
    def __init__(self, client_token: str, client_secret: str, access_token: str, nb_retries: int = 5):
        super().__init__()
        self.auth = EdgeGridAuth(client_token=client_token, client_secret=client_secret, access_token=access_token)
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=1,  # https://techdocs.akamai.com/siem-integration/reference/rate-limits
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
