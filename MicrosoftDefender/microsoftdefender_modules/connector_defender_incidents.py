from .connector_base import (
    BaseGraphAPIConfiguration,
    BaseMicrosoftDefenderGraphAPIConnector,
)


class MicrosoftDefenderGraphAPIIncidentsConfiguration(BaseGraphAPIConfiguration):
    pass


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
    top_query_limit = 50
