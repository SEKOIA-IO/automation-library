from typing import ClassVar
from management.common.query_filter import QueryFilter
from management.mgmtsdk_v2.services.threat import ThreatQueryFilter

from sentinelone_module.filters import BaseFilters


class ThreatFilters(BaseFilters):
    account_ids: list[str] | None = None
    agent_ids: list[str] | None = None
    group_ids: list[str] | None = None
    site_ids: list[str] | None = None
    query: str | None = None

    query_filter_class: ClassVar[type[QueryFilter]] = ThreatQueryFilter
