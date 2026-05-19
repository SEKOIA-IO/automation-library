from typing import Any

from .connector_microsoft_defender_xdr import (
    BaseGraphAPIConfiguration,
    BaseMicrosoftDefenderGraphAPIConnector,
)


class MicrosoftDefenderGraphAPIIncidentsConfiguration(BaseGraphAPIConfiguration):
    expand_alerts: bool = False


class MicrosoftDefenderGraphAPIIncidents(BaseMicrosoftDefenderGraphAPIConnector):
    """Fetch incidents from Microsoft Graph Security API (/security/incidents).

    Uses the same Graph application scope as the alerts connector
    (`https://graph.microsoft.com/.default`), so a single app registration with
    `SecurityIncident.Read.All` + `SecurityAlert.Read.All` covers both.
    """

    configuration: MicrosoftDefenderGraphAPIIncidentsConfiguration

    endpoint_url = "https://graph.microsoft.com/v1.0/security/incidents"
    timestamp_field = "createdDateTime"
    id_field = "id"
    context_cursor_key = "most_recent_date_requested_incidents"
    events_cache_context_key = "incidents_events_cache"

    def extra_query_params(self) -> dict[str, Any]:
        if self.configuration.expand_alerts:
            return {"$expand": "alerts"}
        return {}
