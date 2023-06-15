import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase


class ApiClient(requests.Session):
    def __init__(self, auth: AuthBase, nb_retries: int = 5):
        super().__init__()
        self.auth = auth
        self.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(total=nb_retries, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            ),
        )
