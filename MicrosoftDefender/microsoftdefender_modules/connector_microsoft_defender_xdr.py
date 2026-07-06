from typing import Generator

from .connector_base import (
    BaseGraphAPIConfiguration,
    BaseMicrosoftDefenderGraphAPIConnector,
)


class MicrosoftDefenderGraphAPIAlertsConfiguration(BaseGraphAPIConfiguration):
    pass


class MicrosoftDefenderGraphAPIAlerts(BaseMicrosoftDefenderGraphAPIConnector):
    configuration: MicrosoftDefenderGraphAPIAlertsConfiguration

    endpoint_url = "https://graph.microsoft.com/v1.0/security/alerts_v2"
    timestamp_field = "createdDateTime"
    id_field = "id"
    context_cursor_key = "most_recent_date_requested"
    events_cache_context_key = "events_cache"

    def process_events(self, batch: list[dict]) -> Generator[dict, None, None]:
        # Expand evidence to separate events
        for event in batch:
            alert_id = event["id"]

            # Ignore already seen
            if alert_id in self.events_cache:
                continue

            evidences = event.pop("evidence", [])
            yield event

            for evidence in evidences:
                evidence["alertId"] = alert_id
                yield evidence
