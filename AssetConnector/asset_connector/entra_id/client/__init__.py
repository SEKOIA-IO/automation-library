import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry
from datetime import datetime

from .auth import ApiKeyAuthentication


class EntraIDApiClient(requests.Session):
    token_url: str
    tenant_id: str
    current_token: str
    current_token_expiry: datetime = datetime.now()
    def __init__(
        self,
        token_url:str,
        tenant_id: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 600,
    ):
        super().__init__()
        self.token_url = token_url
        self.tenant_id = tenant_id
        self.current_token = self.refresh_token()
        self.auth = ApiKeyAuthentication(self.current_token)
        self.mount(
            "https://",
            LimiterAdapter(
                per_minute=ratelimit_per_minute,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
    
    def refresh_token(self) -> str:
        """
        Refresh the API token if needed.
        This method can be implemented to handle token refresh logic.
        """
        # Placeholder for token refresh logic
        complete_token_url = f"{self.token_url}/{self.tenant_id}/oauth2/v2.0/token"
        
        return self.auth.__api_token
