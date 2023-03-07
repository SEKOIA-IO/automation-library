import requests
from requests.adapters import HTTPAdapter, Retry

from jumpcloud_modules.client.auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        apikey: str,
        nb_retries: int = 5,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(apikey)
        self.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
