import base64
from datetime import datetime, timedelta

import requests
from sekoia_automation.module import Module


class AuthorizationMixin:
    http_session: requests.Session
    api_credentials: dict | None
    module: Module

    def _get_authorization_headers(self):
        access_id = self.module.configuration["access_id"]
        access_pw = self.module.configuration["access_secret"]
        digest = base64.b64encode(f"{access_id}:{access_pw}".encode()).decode("utf-8")

        return {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {digest}",
        }

    def _get_authorization_payload(self):
        data = {"grant_type": "client_credentials", "scope": "api-access"}

        if audience := self.module.configuration.get("audience"):
            data["audience"] = audience

        return data

    def _request_authorization(self):
        response = self.http_session.post(
            url=f"{self.module.configuration['base_url']}/oauth/token",
            headers=self._get_authorization_headers(),
            data=self._get_authorization_payload(),
        )

        if not response.ok:
            self.log(
                f"OAuth2 server response: {response.status_code} - {response.reason}",
                level="error",
            )
        response.raise_for_status()

        return response

    def _get_authorization(self):
        if (
            self.api_credentials is None
            or datetime.utcnow() + timedelta(seconds=300) >= self.api_credentials["expires_at"]
        ):
            current_dt = datetime.utcnow()
            response = self._request_authorization()
            self.api_credentials = response.json()
            self.api_credentials["expires_at"] = current_dt + timedelta(seconds=self.api_credentials["expires_in"])

        return f"{self.api_credentials['token_type'].title()} {self.api_credentials['access_token']}"
