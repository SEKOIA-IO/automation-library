import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import HTTPBasicAuth


class ApiClient(requests.Session):
    def __init__(self, username: str, api_key: str, nb_retries: int = 5):
        super().__init__()
        self.auth = HTTPBasicAuth(username=username, password=api_key)
        self.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                )
            ),
        )
