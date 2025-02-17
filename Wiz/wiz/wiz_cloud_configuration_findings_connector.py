from datetime import datetime, timezone
from typing import Any

from dateutil.parser import isoparse

from wiz import Result, WizConnector


class WizCloudConfigurationFindingsConnector(WizConnector):
    """WizCloudConfigurationFindingsConnector."""

    name = "WizCloudConfigurationFindingsConnector"

    async def get_events(self, start_date: datetime, cursor: str | None = None) -> Result:
        new_last_event_date = start_date

        response = await self.wiz_gql_client.get_cloud_configuration_findings(
            start_date=start_date,
            after=cursor,
        )

        findings: list[dict[str, Any]] = response.result
        # analyzedAt field to check the most recent date seen
        for finding in findings:
            finding_analyzed_at = isoparse(finding["analyzedAt"]).astimezone(timezone.utc)
            if finding_analyzed_at > new_last_event_date:
                new_last_event_date = finding_analyzed_at

        return Result(
            has_next_page=response.has_next_page,
            end_cursor=response.end_cursor,
            new_last_event_date=new_last_event_date,
            data=findings,
        )
