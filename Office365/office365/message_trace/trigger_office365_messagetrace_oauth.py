from datetime import datetime
from posixpath import join as urljoin

import msal
import requests
from requests import Response

from office365.message_trace.base import (
    O365BaseConfig,
    Office365MessageTraceBaseTrigger,
)


class O365Config(O365BaseConfig):
    client_id: str
    client_secret: str
    tenant_id: str
    timedelta: int = 5
    frequency: int = 60
    start_time: int = 1


class Office365MessageTraceTrigger(Office365MessageTraceBaseTrigger):
    """
    This trigger fetches events from Office 365 MessageTrace
    """

    configuration: O365Config

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.scopes: list = ["https://outlook.office365.com/.default"]
        self.base_url = "https://login.microsoftonline.com/"

    def _get_access_token(self) -> str | None:  # pragma: no cover
        client_id: str = self.configuration.client_id
        client_secret: str = self.configuration.client_secret
        authority = urljoin(self.base_url, self.configuration.tenant_id.lstrip("/"))

        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret,
        )

        result_token_silent: dict | None = app.acquire_token_silent(scopes=self.scopes, account=None)

        if result_token_silent:
            return result_token_silent["access_token"]

        result: dict = app.acquire_token_for_client(scopes=self.scopes)
        if "access_token" in result:
            self.log(
                message="Access token successfully provided by Microsoft API.",
                level="info",
            )
            return result["access_token"]

        self.log(message=result.get("error"), level="error")
        self.log(message=result.get("error_description"), level="error")
        self.log(message=result.get("correlation_id"), level="error")
        return None

    def _get_http_header(self) -> dict:
        access_token = self._get_access_token()
        if not access_token:
            return {}

        return {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}

    def query_api(self, start: datetime, end: datetime) -> list[str]:
        self.log(message=f"Querying timerange {start} to {end}.", level="info")
        params = {
            "$format": "json",
            "$filter": f"StartDate eq datetime'{start.isoformat()}' and EndDate eq datetime'{end.isoformat()}'",
        }

        for attempt in self._retry():
            with attempt:
                response: Response = requests.get(
                    url=self.messagetrace_api_url,
                    headers=self._get_http_header(),
                    params=params,
                    timeout=120,
                )

        return self.manage_response(response)
