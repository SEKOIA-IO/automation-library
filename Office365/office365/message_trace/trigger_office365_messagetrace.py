from datetime import datetime

import requests
from requests import Response

from office365.message_trace.base import (
    O365BaseConfig,
    Office365MessageTraceBaseTrigger,
)


class O365Config(O365BaseConfig):
    account_name: str
    account_password: str


class Office365MessageTraceTrigger(Office365MessageTraceBaseTrigger):
    """
    This trigger fetches events from Office 365 MessageTrace
    """

    configuration: O365Config

    def query_api(self, start: datetime, end: datetime) -> list[str]:
        self.log(message=f"Querying timerange {start} to {end}.", level="info")
        params = {
            "$format": "json",
            "$filter": f"StartDate eq datetime'{start.isoformat()}' and EndDate eq datetime'{end.isoformat()}'",
        }
        auth = requests.auth.HTTPBasicAuth(self.configuration.account_name, self.configuration.account_password)

        for attempt in self._retry():
            with attempt:
                response: Response = requests.get(
                    url=self.messagetrace_api_url,
                    headers=self.headers,
                    auth=auth,
                    params=params,
                    timeout=120,
                )

        return self.manage_response(response)
