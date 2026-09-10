import requests
from urllib3 import Retry

from client.auth import MoknApiKeyAuth


class ApiClient(requests.Session):
    def __init__(self, base_url: str, api_token: str, nb_retries: int = 5):
        super().__init__()

        self.base_url = base_url.rstrip("/")
        self.auth = MoknApiKeyAuth(api_token=api_token)

        adapter = requests.adapters.HTTPAdapter(
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
        )
        self.mount("http://", adapter)
        self.mount("https://", adapter)
