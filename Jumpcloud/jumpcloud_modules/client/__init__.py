import requests
from requests.adapters import HTTPAdapter, Retry

from jumpcloud_modules.client.auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        apikey: str,
        nb_retries: int = 5,
        default_headers: dict[str, str] = None,
    ):
        super().__init__()

        if default_headers is not None:
            self.headers.update(default_headers)

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
