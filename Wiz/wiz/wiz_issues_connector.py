from datetime import datetime, timezone
from typing import Any

from dateutil.parser import isoparse

from wiz import Result, WizConnector


class WizIssuesConnector(WizConnector):
    """WizIssuesConnector."""

    name = "WizIssuesConnector"

    async def get_events(self, start_date: datetime, cursor: str | None = None) -> Result:
        new_last_event_date = start_date

        response = await self.wiz_gql_client.get_alerts(
            start_date=start_date,
            after=cursor,
        )

        alerts: list[dict[str, Any]] = response.result
        # createdAt field to check the most recent date seen
        for alert in alerts:
            alert_created_at = isoparse(alert["createdAt"]).astimezone(timezone.utc)
            if alert_created_at > new_last_event_date:
                new_last_event_date = alert_created_at

        return Result(
            has_next_page=response.has_next_page,
            end_cursor=response.end_cursor,
            new_last_event_date=new_last_event_date,
            data=alerts,
        )
