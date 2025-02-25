from datetime import datetime, timezone
from typing import Any

from dateutil.parser import isoparse

from wiz import Result, WizConnector


class WizAuditLogsConnector(WizConnector):
    """WizAuditLogsConnector."""

    name = "WizAuditLogsConnector"

    async def get_events(self, start_date: datetime, cursor: str | None = None) -> Result:
        new_last_event_date = start_date

        response = await self.wiz_gql_client.get_audit_logs(
            start_date=start_date,
            after=cursor,
        )

        audit_logs: list[dict[str, Any]] = response.result
        # timestamp field to check the most recent date seen
        for audit_log in audit_logs:
            alert_created_at = isoparse(audit_log["timestamp"]).astimezone(timezone.utc)
            if alert_created_at > new_last_event_date:
                new_last_event_date = alert_created_at

        return Result(
            has_next_page=response.has_next_page,
            end_cursor=response.end_cursor,
            new_last_event_date=new_last_event_date,
            data=audit_logs,
        )
