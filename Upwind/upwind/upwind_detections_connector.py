from datetime import datetime
from typing import Any

from upwind import UpwindConnector, UpwindPage


class UpwindDetectionsConnector(UpwindConnector):
    name = "UpwindDetectionsConnector"

    async def fetch_page(self, since: datetime, page_token: str | None = None) -> UpwindPage:
        params: dict[str, Any] = {
            "updated_after": since.isoformat().replace("+00:00", "Z"),
            "limit": self.configuration.page_size,
        }
        if page_token:
            params["page_token"] = page_token

        headers = {
            "Authorization": f"Bearer {self.module.configuration.api_token.get_secret_value()}",
            "Accept": "application/json",
        }

        url = f"{self.module.configuration.base_url}/v1/organizations/{self.module.configuration.organization_id}/threat-detections"

        async with self.session() as session:
            async with session.get(url=url, params=params, headers=headers, timeout=self.request_timeout) as response:
                response.raise_for_status()
                payload = await response.json()

        if isinstance(payload, list):
            return UpwindPage(items=payload)

        if isinstance(payload, dict):
            # API v1 returns threat-detections array in dict response
            items = payload.get("threat-detections", [])
            next_page_token = payload.get("next_page_token")
            if isinstance(items, list):
                return UpwindPage(items=items, next_page_token=next_page_token)

        return UpwindPage(items=[])
