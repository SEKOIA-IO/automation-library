from management.mgmtsdk_v2_1.services.remote_scripts import RemoteScriptsQueryFilter

from sentinelone_module.filters import BaseFilters


class RemoteScriptsFilters(BaseFilters):
    account_ids: list[str] | None
    group_ids: list[str] | None
    ids: list[str] | None
    site_ids: list[str] | None
    query: str | None

    class Config:
        query_filter_class = RemoteScriptsQueryFilter
