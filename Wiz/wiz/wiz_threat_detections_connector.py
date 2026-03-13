from datetime import datetime, timezone
from typing import Any

from dateutil.parser import isoparse

from . import Result, WizConnector


class WizThreatDetectionsConnector(WizConnector):
    """WizThreatDetectionsConnector."""

    name = "WizThreatDetectionsConnector"

    async def get_events(self, start_date: datetime, cursor: str | None = None) -> Result:
        new_last_event_date = start_date

        response = await self.wiz_gql_client.get_threat_detections(
            start_date=start_date,
            after=cursor,
        )

        threat_detections: list[dict[str, Any]] = response.result
        # createdAt field to check the most recent date seen
        for detection in threat_detections:
            alert_created_at = isoparse(detection["createdAt"]).astimezone(timezone.utc)
            if alert_created_at > new_last_event_date:
                new_last_event_date = alert_created_at

        return Result(
            has_next_page=response.has_next_page,
            end_cursor=response.end_cursor,
            new_last_event_date=new_last_event_date,
            data=threat_detections,
        )
