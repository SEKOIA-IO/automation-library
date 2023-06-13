from management.mgmtsdk_v2.services.threat import ThreatQueryFilter

from sentinelone_module.filters import BaseFilters


class ThreatFilters(BaseFilters):
    account_ids: list[str] | None
    agent_ids: list[str] | None
    group_ids: list[str] | None
    site_ids: list[str] | None
    query: str | None

    class Config:
        query_filter_class = ThreatQueryFilter
