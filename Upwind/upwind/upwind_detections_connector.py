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

        url = f"{self.module.configuration.base_url}/v1alpha1/detections"

        async with self.session.get(url=url, params=params, headers=headers, timeout=self.request_timeout) as response:
            response.raise_for_status()
            payload = await response.json()

        if isinstance(payload, list):
            return UpwindPage(items=payload)

        if isinstance(payload, dict):
            items = payload.get("items") or payload.get("detections") or payload.get("results") or []
            next_page_token = payload.get("next_page_token") or payload.get("next")
            if isinstance(items, list):
                return UpwindPage(items=items, next_page_token=next_page_token)

        return UpwindPage(items=[])
