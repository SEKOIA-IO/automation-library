from management.mgmtsdk_v2_1.services.threat_notes import ThreatQueryFilter
from pydantic import BaseModel

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.filters import BaseFilters


class UpdateThreatIncidentFilters(BaseFilters):
    account_ids: list[str] | None
    group_ids: list[str] | None
    site_ids: list[str] | None
    agent_ids: list[str] | None
    ids: list[str] | None
    analyst_verdicts: str | None

    class Config:
        query_filter_class = ThreatQueryFilter


class UpdateThreatIncidentArguments(BaseModel):
    filters: UpdateThreatIncidentFilters | None
    new_analyst_verdict: str | None
    status: str

    def get_query_filters(self):
        if self.filters is None:
            return None

        # Unfortunately, we can't make enum field optional. Thus, we add a value we can ignore
        if self.filters.analyst_verdicts == "-":
            self.filters.analyst_verdicts = None

        return self.filters.to_query_filter()

    def get_new_verdict(self):
        return self.new_analyst_verdict if self.new_analyst_verdict != "-" else None


class UpdateThreatIncidentResults(BaseModel):
    affected: int


class UpdateThreatIncidentAction(SentinelOneAction):
    name = "Update Threat Incident"
    description = "Update a threat incident in SentinelOne"
    results_model = UpdateThreatIncidentResults

    def run(self, arguments: UpdateThreatIncidentArguments):
        result = self.client.threats.update_threat_incident(
            incident_status=arguments.status,
            analyst_verdict=arguments.get_new_verdict(),
            query_filter=arguments.get_query_filters(),
        )
        return result.json["data"]
