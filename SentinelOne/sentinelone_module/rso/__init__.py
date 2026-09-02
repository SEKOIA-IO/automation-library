from typing import ClassVar
from management.common.query_filter import QueryFilter
from management.mgmtsdk_v2_1.services.remote_scripts import RemoteScriptsQueryFilter

from sentinelone_module.filters import BaseFilters


class RemoteScriptsFilters(BaseFilters):
    account_ids: list[str] | None = None
    group_ids: list[str] | None = None
    ids: list[str] | None = None
    site_ids: list[str] | None = None
    query: str | None = None

    query_filter_class: ClassVar[type[QueryFilter]] = RemoteScriptsQueryFilter
