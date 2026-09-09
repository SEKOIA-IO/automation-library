from typing import ClassVar
from management.common.query_filter import QueryFilter
from management.mgmtsdk_v2_1.services.threat_notes import ThreatNoteQueryFilter
from pydantic import BaseModel

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.filters import BaseFilters


class ThreatNoteFilters(BaseFilters):
    account_ids: list[str] | None = None
    group_ids: list[str] | None = None
    site_ids: list[str] | None = None
    agent_ids: list[str] | None = None
    ids: list[str] | None = None

    query_filter_class: ClassVar[type[QueryFilter]] = ThreatNoteQueryFilter


class CreateThreatNoteArguments(BaseModel):
    filters: ThreatNoteFilters | None = None
    text: str

    def get_query_filters(self):
        if not self.filters:
            raise ValueError("Filters are required to create a threat note !!")
        return self.filters.to_query_filter()


class CreateThreatNoteResults(BaseModel):
    affected: int


class CreateThreatNoteAction(SentinelOneAction):
    name = "Create Threat Note"
    description = "Create a threat note in SentinelOne"
    results_model = CreateThreatNoteResults

    def run(self, arguments: CreateThreatNoteArguments):
        result = self.client.threats_notes.create_threat_note(
            arguments.text, query_filter=arguments.get_query_filters()
        )
        return result.json["data"]
